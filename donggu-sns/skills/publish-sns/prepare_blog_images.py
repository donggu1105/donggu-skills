#!/usr/bin/env python3
"""
prepare_blog_images.py — tistory/maily 발행 전, 본문의 Obsidian 이미지 임베드를
공개 URL 표준 마크다운으로 바꾼다.

  ![[geudwi-hero.jpg]]  →  ![](https://….supabase.co/storage/v1/object/public/sns-media/blog/…/geudwi-hero.jpg)

흐름: 본문에서 `![[...]]` 이미지 임베드 추출 → vault에서 파일 찾기 →
Supabase storage(public 버킷)에 업로드(upsert) → 본문 치환 → 치환본을 stdout으로.

왜 필요? 사용자가 지정한 노트나 저장 파이프라인이 로컬 위키링크 이미지를 포함할 수 있지만,
로컬 위키링크 이미지는 native publisher payload에 그대로 넣으면 발행본에서 깨진다.
이 단계가 그 다리를 놓는다.

사용:
  python3 prepare_blog_images.py <note.md> [--slug SLUG] [--bucket sns-media] \
      [--out <file>]   # 생략 시 stdout
키(.env 자동탐색): SUPABASE_SERVICE_KEY, SUPABASE_URL
  탐색: $SNS_ENV → ~/workspace/projects/n8n/.env → ~/.env
종료코드: 0=치환 완료(또는 임베드 없음), 2=해결 못한 이미지 있음(업로드 안 함, 그대로 둠),
         3=확장자와 실제 바이트 불일치(업로드 안 함 — 재인코딩 후 재실행)
출력(stderr): 업로드/치환 로그 JSON 한 줄씩.
"""
import argparse
import datetime
import json
import mimetypes
import os
import re
import sys
import urllib.request

EMBED_RE = re.compile(r"!\[\[([^\]|]+?\.(?:jpg|jpeg|png|webp|gif))(?:\|[^\]]*)?\]\]", re.IGNORECASE)
DEFAULT_URL = "https://fvfayignxybdyyravorg.supabase.co"

# 매직넘버 → 그 바이트를 담을 수 있는 확장자.
# 스토리지는 Content-Type을 **확장자**에서 만들기 때문에 `.jpg` 이름의 PNG도
# `200 image/jpeg`로 보인다. 발행기 preflight의 magic 검사는 승인이 이미 소모된
# dispatch 시점에야 실패하므로, 업로드 전에 여기서 막는다.
_SIGNATURES = [
    (b"\xff\xd8\xff", "JPEG", {".jpg", ".jpeg"}),
    (b"\x89PNG\r\n\x1a\n", "PNG", {".png"}),
    (b"GIF87a", "GIF", {".gif"}),
    (b"GIF89a", "GIF", {".gif"}),
    (b"RIFF", "WEBP", {".webp"}),
]


def sniff_format(head: bytes):
    """실제 바이트에서 포맷명을 판정한다. 모르면 None."""
    for magic, name, _exts in _SIGNATURES:
        if head.startswith(magic):
            if name == "WEBP" and head[8:12] != b"WEBP":
                continue
            return name
    return None


def _allowed_exts(fmt):
    for _magic, name, exts in _SIGNATURES:
        if name == fmt:
            return exts
    return set()


def verify_bytes_match_extension(paths):
    """확장자와 실제 바이트가 일치하는지 검사. 불일치 목록을 반환한다."""
    problems = []
    for path in paths:
        with open(path, "rb") as fh:
            head = fh.read(16)
        fmt = sniff_format(head)
        ext = os.path.splitext(path)[1].lower()
        base = os.path.basename(path)
        if fmt is None:
            problems.append((base, None, ext, head[:8]))
        elif ext not in _allowed_exts(fmt):
            problems.append((base, fmt, ext, head[:8]))
    return problems


def log(obj):
    sys.stderr.write(json.dumps(obj, ensure_ascii=False) + "\n")


def load_env():
    need = ("SUPABASE_SERVICE_KEY", "SUPABASE_URL")
    if all(os.environ.get(k) for k in need):
        return
    for c in (os.environ.get("SNS_ENV"),
              os.path.expanduser("~/workspace/projects/n8n/.env"),
              os.path.expanduser("~/.env")):
        if not c or not os.path.isfile(c):
            continue
        for line in open(c, encoding="utf-8"):
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.strip()
            if k in need and not os.environ.get(k):
                os.environ[k] = v.strip().strip('"').strip("'")


def find_file(basename, search_roots):
    """basename(파일명)을 search_roots 아래에서 재귀 탐색. 첫 일치 반환."""
    for root in search_roots:
        if not root or not os.path.isdir(root):
            continue
        for dirpath, _dirs, files in os.walk(root):
            if basename in files:
                return os.path.join(dirpath, basename)
    return None


def upload(local_path, key_path, bucket, base_url, service_key):
    """Supabase storage에 upsert 업로드. 성공 시 public URL 반환."""
    ctype = mimetypes.guess_type(local_path)[0] or "application/octet-stream"
    obj_url = f"{base_url}/storage/v1/object/{bucket}/{key_path}"
    with open(local_path, "rb") as f:
        data = f.read()
    req = urllib.request.Request(obj_url, data=data, method="POST", headers={
        "Authorization": f"Bearer {service_key}",
        "apikey": service_key,
        "Content-Type": ctype,
        "x-upsert": "true",
        "Cache-Control": "max-age=31536000",
    })
    urllib.request.urlopen(req, timeout=60).read()
    return f"{base_url}/storage/v1/object/public/{bucket}/{key_path}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("note")
    ap.add_argument("--slug", default=None, help="storage 경로 슬러그(생략 시 이미지 폴더명 추론)")
    ap.add_argument("--bucket", default="sns-media")
    ap.add_argument("--out", default=None, help="치환본 저장 경로(생략 시 stdout)")
    ap.add_argument("--date", default=None, help="YYYY-MM-DD storage 날짜(생략 시 오늘)")
    a = ap.parse_args()

    load_env()
    base_url = (os.environ.get("SUPABASE_URL") or DEFAULT_URL).rstrip("/")
    service_key = os.environ.get("SUPABASE_SERVICE_KEY")
    if not service_key:
        log({"error": "SUPABASE_SERVICE_KEY 없음 — .env 확인"})
        sys.exit(2)

    note = os.path.abspath(a.note)
    content = open(note, encoding="utf-8").read()
    note_dir = os.path.dirname(note)
    vault_root = None
    p = note_dir
    while p != os.path.dirname(p):  # vault 루트: .obsidian 보유 폴더
        if os.path.isdir(os.path.join(p, ".obsidian")):
            vault_root = p
            break
        p = os.path.dirname(p)
    search_roots = [note_dir, vault_root]

    embeds = list(dict.fromkeys(EMBED_RE.findall(content)))  # 순서보존 중복제거
    if not embeds:
        log({"info": "이미지 임베드 없음 — 본문 그대로"})
        out = content
        if a.out:
            open(a.out, "w", encoding="utf-8").write(out)
        else:
            sys.stdout.write(out)
        return

    date = a.date or datetime.date.today().isoformat()
    yyyy, mmdd = date[:4], date[5:].replace("-", "-")
    resolved, missing = {}, []
    slug = a.slug
    for name in embeds:
        fp = find_file(os.path.basename(name), search_roots)
        if not fp:
            missing.append(name)
            continue
        resolved[name] = fp
        if not slug:  # _img/<slug>/file.jpg → <slug>
            parent = os.path.basename(os.path.dirname(fp))
            slug = parent if parent and parent != "_img" else "post"

    if missing:
        for m in missing:
            log({"unresolved": m})
        log({"error": f"{len(missing)}개 이미지 못 찾음 — 업로드/치환 중단", "note": note})
        sys.exit(2)

    # 업로드 전 게이트: 확장자와 실제 바이트가 다르면 여기서 멈춘다.
    # 이걸 통과시키면 발행기 preflight가 dispatch 시점에 image_validation_failed로
    # 죽이는데, 그때는 사용자 승인이 이미 소모된 뒤다.
    problems = verify_bytes_match_extension(list(resolved.values()))
    if problems:
        for base, fmt, ext, head in problems:
            log({
                "extension_mismatch": base,
                "real_format": fmt or "unrecognized",
                "extension": ext,
                "magic": head.hex(),
                "fix": (
                    f"sips -s format jpeg -s formatOptions 92 '{base}' --out '{base}'"
                    if ext in {".jpg", ".jpeg"} else
                    f"확장자를 실제 포맷({fmt})에 맞추거나 해당 포맷으로 재인코딩"
                ),
            })
        log({
            "error": (
                f"{len(problems)}개 이미지의 확장자와 실제 바이트가 다름 — 업로드 중단. "
                "이대로 발행하면 발행기 preflight가 승인 소모 후 거부한다."
            ),
            "note": note,
        })
        sys.exit(3)

    out = content
    cover_url = None
    for idx, (name, fp) in enumerate(resolved.items()):
        base = os.path.basename(fp)
        key_path = f"blog/{yyyy}/{mmdd}/{slug}/{base}"
        url = upload(fp, key_path, a.bucket, base_url, service_key)
        if idx == 0:  # 첫 이미지(hero) = 대표이미지(cover) 후보
            cover_url = url
        # ![[name]] 및 ![[name|alt]] 모두 치환
        pat = re.compile(r"!\[\[" + re.escape(name) + r"(?:\|[^\]]*)?\]\]")
        out = pat.sub(f"![]({url})", out)
        log({"uploaded": base, "url": url})

    # cover(hero) URL을 사이드카로 — 발행 시 tistory cover_image로 전달
    if cover_url and a.out:
        with open(a.out + ".cover", "w", encoding="utf-8") as cf:
            cf.write(cover_url)
    log({"cover_image": cover_url})

    if a.out:
        open(a.out, "w", encoding="utf-8").write(out)
        log({"done": True, "out": a.out, "count": len(resolved), "cover": cover_url})
    else:
        sys.stdout.write(out)
        log({"done": True, "count": len(resolved), "cover": cover_url})


if __name__ == "__main__":
    main()
