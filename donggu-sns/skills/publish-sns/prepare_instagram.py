#!/usr/bin/env python3
"""
prepare_instagram.py — 인스타그램 채널 노트에서 발행 payload(`image_urls` + `caption`)를 준비한다.

흐름: frontmatter 확인 → `## 장별 카피`의 `![[...]]` 임베드 추출(노트 등장 순서 = 이미지 순서) →
`## 캡션` 섹션에서 첫 단락~마지막 해시태그 줄을 캡션으로 → 재발행·동의 고지 게이트 →
이미지 검증(존재·매직바이트·포맷·크기·MANIFEST 해시) → Supabase storage(public 버킷)에
upsert 업로드 → 어댑터 프리뷰에 그대로 넣을 JSON을 stdout으로.

왜 필요? Threads·LinkedIn은 노트 섹션에서 본문을 읽고, 블로그는 prepare_blog_images.py가
임베드를 공개 URL로 바꾼다. 인스타그램만 사람이 PNG를 골라 올리고 URL을 복사해 왔다.
그 사이에 순서가 바뀌거나 수정 전 파일이 올라가는 일을 이 단계가 막는다.

사용:
  python3 prepare_instagram.py "<Instagram - 제목.md>" [--slug SLUG] [--bucket sns-media] \
      [--out <file>] [--dry-run] [--force-consent] [--force-republish]
키(.env 자동탐색, prepare_blog_images.load_env): SUPABASE_SERVICE_KEY, SUPABASE_URL
  탐색: $SNS_ENV → ~/workspace/projects/n8n/.env → ~/.env   (--dry-run이면 읽지 않음)
storage 경로(upload_images.py와 동일): instagram/<YYYY>/<MM-DD>/<slug>-<HHMMSS>/<NN><ext>
종료코드: 0=성공, 1=업로드 실패, 2=노트·캡션·이미지 규격 위반, 3=확장자와 실제 바이트 불일치,
         4=동의 고지 미완료, 5=이미 게시됨(재발행 방지)
출력(stdout): payload JSON 하나. (stderr): 로그 JSON 한 줄씩. 비밀값은 어디에도 넣지 않는다.
"""
import argparse
import datetime
import hashlib
import json
import os
import re
import sys
import urllib.error
from dataclasses import dataclass, field
from pathlib import Path

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
import prepare_blog_images as blog  # noqa: E402  vault·.env·매직바이트·업로드 규칙을 공유한다

CHANNEL = "instagram"
NOTE_PREFIX = "Instagram - "
MAX_IMAGES = 10
MAX_CAPTION_CHARS = 2200
MAX_HASHTAGS = 30
MAX_IMAGE_BYTES = 8 * 1024 * 1024
CONSENT_PHRASE = "고지 후 게시 가능"
CARDS_SECTION = "장별 카피"
CAPTION_SECTIONS = ("캡션 초안 (인스타그램)", "캡션")
CONSENT_SECTION = "사진과 동의"

SECTION_RE = re.compile(r"^## (.+?)\s*$", re.MULTILINE)
EMBED_RE = re.compile(r"!\[\[([^\]|]+?)(?:\|[^\]]*)?\]\]")
WIKILINK_RE = re.compile(r"(?<!!)\[\[([^\]|#]+)(?:[#|][^\]]*)?\]\]")
HASHTAG_RE = re.compile(r"(?<!\S)#[^\s#]+")
HASHTAG_LINE_RE = re.compile(r"^#[^\s#]")
MANIFEST_ROW_RE = re.compile(r"^\|\s*([^|]+?)\s*\|\s*([0-9a-fA-F]{64})\s*\|", re.MULTILINE)


class PrepareError(Exception):
    def __init__(self, code, message, **details):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details


@dataclass
class InstagramNote:
    frontmatter: dict
    embeds: list
    caption: str
    consent_links: list
    consent_required: bool = False
    warnings: list = field(default_factory=list)


def _warn(warnings, code, **details):
    entry = {"code": code, **details}
    warnings.append(entry)
    blog.log({"warning": code, **details})


def _split_frontmatter(text):
    """최상위 `key: value`만 읽는다(목록·중첩은 무시). frontmatter가 없으면 ({}, text)."""
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        return {}, text
    for end in range(1, len(lines)):
        if lines[end].strip() == "---":
            fm = {}
            for line in lines[1:end]:
                m = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", line)
                if m:
                    fm[m.group(1)] = m.group(2).strip().strip('"').strip("'")
            return fm, "\n".join(lines[end + 1:])
    return {}, text


def _sections(body):
    """`## 제목` → 다음 `## ` 전까지의 본문(`###` 소제목은 섹션 안에 남는다)."""
    matches = list(SECTION_RE.finditer(body))
    out = {}
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        out.setdefault(m.group(1).strip(), body[m.end():end])
    return out


def _extract_caption(section):
    """첫 단락부터 마지막 해시태그 줄까지. 해시태그 줄 뒤 단락은 편집 메모로 버린다.
    반환: (caption, 해시태그 줄을 찾았는지)."""
    lines = [line.rstrip() for line in section.split("\n")]
    start = next((i for i, line in enumerate(lines) if line.strip()), None)
    if start is None:
        return "", False
    last_tag = None
    for i in range(start, len(lines)):
        if HASHTAG_LINE_RE.match(lines[i].strip()):
            last_tag = i
    if last_tag is None:
        return "\n".join(lines[start:]).strip(), False
    return "\n".join(lines[start:last_tag + 1]).strip(), True


def count_hashtags(caption):
    return len(HASHTAG_RE.findall(caption))


def parse_instagram_note(text: str) -> InstagramNote:
    """노트 텍스트만 보고 구조를 뽑는다(파일·네트워크 접근 없음). 규격 판정은 validate_note."""
    fm, body = _split_frontmatter(text.replace("\r\n", "\n"))
    sections = _sections(body)
    warnings = []

    embeds = [e.strip() for e in EMBED_RE.findall(sections.get(CARDS_SECTION, ""))]
    for pos, embed in enumerate(embeds, 1):
        stem = os.path.splitext(os.path.basename(embed))[0]
        if stem.isdigit() and int(stem) != pos:  # 정본은 노트 순서, 파일 번호는 참고
            warnings.append({"code": "embed_order_mismatch", "position": pos,
                             "file": os.path.basename(embed)})
    cards = fm.get("cards", "")
    if cards.isdigit() and int(cards) != len(embeds):
        warnings.append({"code": "cards_count_mismatch", "frontmatter_cards": int(cards),
                         "embeds": len(embeds)})

    caption_section = next((sections[t] for t in CAPTION_SECTIONS if t in sections), None)
    caption = ""
    if caption_section is not None:
        caption, has_tags = _extract_caption(caption_section)
        if caption and not has_tags:
            warnings.append({"code": "no_hashtag_line"})

    consent = sections.get(CONSENT_SECTION)
    links = []
    for target in WIKILINK_RE.findall(consent or ""):
        target = target.strip()
        if os.path.basename(target).startswith("KakaoTalk - ") and target not in links:
            links.append(target)

    return InstagramNote(
        frontmatter=fm,
        embeds=embeds,
        caption=caption,
        consent_links=links,
        consent_required=consent is not None and CONSENT_PHRASE in consent,
        warnings=warnings,
    )


def validate_note(note, force_republish=False, warnings=None):
    """채널·재발행·캡션·임베드 수 규격. 위반이면 PrepareError(2 또는 5)."""
    channel = note.frontmatter.get("channel", "")
    if channel != CHANNEL:
        raise PrepareError(2, f"channel이 instagram이 아님: {channel or '(없음)'}")
    if note.frontmatter.get("status") == "published":
        if not force_republish:
            raise PrepareError(5, "이미 게시된 노트(status: published) — 재발행하려면 --force-republish")
        _warn(warnings if warnings is not None else [], "forced_republish")
    caption = note.caption
    if not caption:
        raise PrepareError(2, "캡션이 비어 있음 — `## 캡션` 또는 `## 캡션 초안 (인스타그램)` 섹션 확인")
    if len(caption) > MAX_CAPTION_CHARS:
        raise PrepareError(2, f"캡션 {len(caption)}자 — 인스타그램 한도 {MAX_CAPTION_CHARS}자 초과")
    tags = count_hashtags(caption)
    if tags > MAX_HASHTAGS:
        raise PrepareError(2, f"해시태그 {tags}개 — 인스타그램 한도 {MAX_HASHTAGS}개 초과")
    if "![[" in caption:
        raise PrepareError(2, "캡션에 `![[` 임베드가 남아 있음")
    if not 1 <= len(note.embeds) <= MAX_IMAGES:
        raise PrepareError(
            2, f"`## {CARDS_SECTION}` 이미지 임베드 {len(note.embeds)}개 — 1~{MAX_IMAGES}개여야 함"
        )


def _within(root, path):
    return path == root or root in path.parents


def resolve_embed(vault_root: Path, embed: str) -> Path:
    """임베드를 실제 파일로. 경로가 있으면 vault 루트 기준 그 경로만 본다(같은 이름의 다른
    `01.png`를 집지 않도록). 파일명뿐이면 prepare_blog_images와 같은 규칙(vault 재귀 탐색)."""
    root = Path(vault_root).resolve()
    embed = embed.strip()
    if "/" in embed:
        candidate = (root / embed).resolve()
        if _within(root, candidate) and candidate.is_file():
            return candidate
        raise FileNotFoundError(embed)
    found = blog.find_file(embed, [str(root)])
    if found:
        return Path(found)
    raise FileNotFoundError(embed)


def resolve_note_link(vault_root, target):
    """`[[경로/노트]]` 위키링크 → .md 파일. 못 찾으면 None."""
    name = target if target.endswith(".md") else target + ".md"
    try:
        return resolve_embed(vault_root, name)
    except FileNotFoundError:
        return None


def check_consent(note, vault_root, force_consent=False, warnings=None):
    """`## 사진과 동의`가 `고지 후 게시 가능`이면 연결된 카톡 고지 노트가 published여야 한다."""
    if not note.consent_required:
        return
    pending = []
    if not note.consent_links:
        pending.append({"link": None, "reason": "고지 노트([[KakaoTalk - …]]) 링크 없음"})
    for target in note.consent_links:
        path = resolve_note_link(vault_root, target)
        if path is None:
            pending.append({"link": target, "reason": "고지 노트를 찾지 못함"})
            continue
        fm, _ = _split_frontmatter(path.read_text(encoding="utf-8").replace("\r\n", "\n"))
        if fm.get("status") != "published":
            pending.append({"link": target, "status": fm.get("status") or "(없음)"})
    if not pending:
        return
    if not force_consent:
        raise PrepareError(4, "동의 고지 미완료 — 고지 노트가 published가 아님", pending=pending)
    _warn(warnings if warnings is not None else [], "forced_consent", pending=pending)


def read_manifest(path):
    """MANIFEST.md의 `| 파일 | SHA-256 | 바이트 |` 표 → {파일: sha256}."""
    text = Path(path).read_text(encoding="utf-8")
    return {name: sha.lower() for name, sha in MANIFEST_ROW_RE.findall(text)}


def inspect_images(paths, warnings):
    """업로드 전 게이트. 위반이면 PrepareError(2 또는 3)."""
    problems = blog.verify_bytes_match_extension([str(p) for p in paths])
    if problems:
        for base, fmt, ext, head in problems:
            blog.log({
                "extension_mismatch": base,
                "real_format": fmt or "unrecognized",
                "extension": ext,
                "magic": head.hex(),
                "fix": blog.mismatch_fix(base, fmt, ext),
            })
        raise PrepareError(
            3,
            f"{len(problems)}개 이미지의 확장자와 실제 바이트가 다름 — 업로드 중단. "
            "이대로 발행하면 발행기 preflight가 승인 소모 후 거부한다.",
        )

    pngs = []
    for path in paths:
        with open(path, "rb") as fh:
            fmt = blog.sniff_format(fh.read(16))
        if fmt not in {"JPEG", "PNG"}:
            raise PrepareError(2, f"{path.name}: {fmt} — 인스타그램은 JPEG/PNG만 허용")
        if fmt == "PNG":
            pngs.append(path.name)
        size = path.stat().st_size
        if size > MAX_IMAGE_BYTES:
            raise PrepareError(2, f"{path.name}: {size} bytes — 8 MB 한도 초과")
    if pngs:
        _warn(warnings, "png_will_be_reencoded_by_instagram", files=pngs)

    for folder in dict.fromkeys(p.parent for p in paths):
        manifest = folder / "MANIFEST.md"
        if not manifest.is_file():
            _warn(warnings, "no_manifest", folder=folder.name)
            continue
        table = read_manifest(manifest)
        for path in (p for p in paths if p.parent == folder):
            expected = table.get(path.name)
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
            if expected != actual:
                raise PrepareError(
                    2,
                    f"{path.name}: MANIFEST.md SHA-256와 다름 — 적재 뒤 파일이 바뀜(재적재 후 재실행)",
                    expected=expected or "(MANIFEST에 없음)",
                    actual=actual,
                )


def default_slug(note_path, now=None):
    """storage 키용 슬러그. Supabase Storage는 비ASCII 키를 `InvalidKey`(400)로 거부하므로
    (2026-10-26 실측) ASCII만 남긴다. 한글 제목처럼 ASCII가 남지 않으면 `ig-<YYYYMMDD>`."""
    stem = Path(note_path).stem
    if stem.startswith(NOTE_PREFIX):
        stem = stem[len(NOTE_PREFIX):]
    slug = re.sub(r"[^a-z0-9-]+", "-", stem.lower()).strip("-")
    slug = re.sub(r"-{2,}", "-", slug)[:60].strip("-")
    if len(slug) < 3 or not re.search(r"[a-z]", slug):
        # 한글 제목에서 숫자만 남은 '4-100' 같은 슬러그는 폴더 이름으로 쓸모가 없다.
        now = now or datetime.datetime.now()
        return f"ig-{now:%Y%m%d}"
    return slug


def note_topic(note_path, frontmatter):
    if frontmatter.get("title"):
        return frontmatter["title"]
    stem = Path(note_path).stem
    return stem[len(NOTE_PREFIX):] if stem.startswith(NOTE_PREFIX) else stem


def storage_folder(slug, now, channel=CHANNEL):
    """upload_images.py와 같은 폴더 규칙."""
    return f"{channel}/{now:%Y}/{now:%m-%d}/{slug}-{now:%H%M%S}"


def object_key(folder, index, path):
    """upload_images.py와 같은 파일 규칙: <NN><ext>."""
    ext = os.path.splitext(str(path))[1] or ".png"
    return f"{folder}/{index:02d}{ext}"


def prepare(a, warnings):
    note_path = Path(a.note).resolve()
    if not note_path.is_file():
        raise PrepareError(2, f"노트 없음: {note_path}")
    note = parse_instagram_note(note_path.read_text(encoding="utf-8"))
    for entry in note.warnings:
        _warn(warnings, **entry)
    validate_note(note, a.force_republish, warnings)

    found_root = blog.find_vault_root(str(note_path.parent))
    if found_root is None:
        _warn(warnings, "vault_root_not_found", fallback=str(note_path.parent))
    vault_root = Path(found_root or note_path.parent)
    check_consent(note, vault_root, a.force_consent, warnings)

    paths, missing = [], []
    for embed in note.embeds:
        try:
            paths.append(resolve_embed(vault_root, embed))
        except FileNotFoundError:
            missing.append(embed)
    if missing:
        for m in missing:
            blog.log({"unresolved": m})
        raise PrepareError(2, f"{len(missing)}개 이미지 못 찾음 — 업로드 중단")
    inspect_images(paths, warnings)

    slug = a.slug or default_slug(note_path)
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}", slug):
        raise PrepareError(2, f"slug는 ASCII 영숫자·'-'만 허용(storage InvalidKey 방지): {slug!r}")
    folder = storage_folder(slug, datetime.datetime.now())

    image_urls = []
    if a.dry_run:
        image_urls = [f"dry-run://{i:02d}" for i in range(1, len(paths) + 1)]
    else:
        blog.load_env()
        base_url = (os.environ.get("SUPABASE_URL") or blog.DEFAULT_URL).rstrip("/")
        service_key = os.environ.get("SUPABASE_SERVICE_KEY")
        if not service_key:
            raise PrepareError(2, "SUPABASE_SERVICE_KEY 없음 — .env 확인")
        for i, path in enumerate(paths, 1):
            key_path = object_key(folder, i, path)
            try:
                url = blog.upload(str(path), key_path, a.bucket, base_url, service_key)
            except urllib.error.HTTPError as exc:
                body = exc.read()[:300].decode("utf-8", "replace")
                raise PrepareError(1, f"업로드 실패 {path.name}: HTTP {exc.code}",
                                   response=body, uploaded=len(image_urls))
            except (urllib.error.URLError, OSError) as exc:
                raise PrepareError(1, f"업로드 실패 {path.name}: {exc}", uploaded=len(image_urls))
            image_urls.append(url)
            blog.log({"uploaded": path.name, "url": url})

    caption = note.caption
    return {
        "channel": CHANNEL,
        "operation": "publish",
        "topic": note_topic(note_path, note.frontmatter),
        "note_path": str(note_path),
        "payload": {"image_urls": image_urls, "caption": caption},
        "image_count": len(image_urls),
        "caption_chars": len(caption),
        "caption_first_line": caption.split("\n", 1)[0],
        "hashtags": count_hashtags(caption),
        "folder": folder,
        "dry_run": bool(a.dry_run),
        "warnings": warnings,
    }


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("note")
    ap.add_argument("--slug", default=None, help="storage 경로 슬러그(생략 시 노트 파일명에서)")
    ap.add_argument("--bucket", default="sns-media")
    ap.add_argument("--out", default=None, help="stdout과 같은 JSON을 이 파일에도 저장")
    ap.add_argument("--dry-run", action="store_true", help="업로드 없이 payload 모양만 출력")
    ap.add_argument("--force-consent", action="store_true", help="동의 고지 게이트 우회(stderr 기록)")
    ap.add_argument("--force-republish", action="store_true", help="status: published 게이트 우회")
    a = ap.parse_args(argv)

    warnings = []
    try:
        result = prepare(a, warnings)
    except PrepareError as exc:
        blog.log({"error": exc.message, "exit_code": exc.code, **exc.details})
        return exc.code

    out = json.dumps(result, ensure_ascii=False, indent=2)
    sys.stdout.write(out + "\n")
    if a.out:
        with open(a.out, "w", encoding="utf-8") as fh:
            fh.write(out + "\n")
    blog.log({"done": True, "count": result["image_count"], "folder": result["folder"],
              "dry_run": result["dry_run"]})
    return 0


if __name__ == "__main__":
    sys.exit(main())
