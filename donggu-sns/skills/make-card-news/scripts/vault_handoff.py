#!/usr/bin/env python3
"""File a rendered card-news set into the Obsidian vault.

    vault_handoff.py SPEC.json --out OUT_DIR --title "제목" --channel instagram
                     [--area "FDE 커뮤니티 (Beyond Deploy)"] [--vault PATH] [--date YYYY-MM-DD]
                     [--source-url URL] [--source "[[wikilink]]" ...] [--caption-file F]
                     [--consent "…"] [--dry-run]

What it does, in the order the vault's AGENTS.md demands (assets first, then the note that links them):

  1. refuses unless OUT_DIR/qa.json says problems == [] and every PNG exists
  2. copies PNGs + cards.pdf + the spec (as cards.json) + its assets/ into
       <area>/Attachments/<date> - <title> (카드뉴스)/        with MANIFEST.md (sha256 per file)
  3. writes one channel note
       <area>/Content/<Channel>/<Channel> - <title>.md        type: channel_pack · status: draft
     holding the per-card copy, the caption draft, consent status, editorial notes, and embeds of the PNGs
  4. adds one line to Content/INDEX, the channel INDEX and Attachments/INDEX and bumps their `updated`

It never overwrites an existing note (reports "exists"), never sets published fields, never touches
anything outside those folders, and never writes signed URLs. Publishing is a separate approval (publish-sns).
Vault path: --vault, else $OBSIDIAN_VAULT_PATH, else the vault marked open in Obsidian's obsidian.json.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
from datetime import date as _date
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import render_cards  # noqa: E402

CHANNEL_DIR = {"instagram": "Instagram", "linkedin": "LinkedIn", "blog": "Blog", "kakaotalk": "KakaoTalk", "threads": "Threads"}
AREA_KEY = {"FDE 커뮤니티 (Beyond Deploy)": "fde-community"}
SIGNED_URL = re.compile(r"https?://\S*(?:supabase\.co/storage/v1/object/sign|token=|X-Amz-Signature)\S*", re.IGNORECASE)


class HandoffError(RuntimeError):
    pass


# ---------- vault ----------

def resolve_vault(explicit: str | None) -> Path:
    import os
    for cand in (explicit, os.environ.get("OBSIDIAN_VAULT_PATH")):
        if cand:
            p = Path(cand).expanduser()
            if p.is_dir():
                return p
            raise HandoffError(f"vault path not found: {p}")
    cfg = Path.home() / "Library/Application Support/obsidian/obsidian.json"
    if cfg.is_file():
        vaults = json.loads(cfg.read_text(encoding="utf-8")).get("vaults", {})
        opened = [v["path"] for v in vaults.values() if v.get("open")] or [v["path"] for v in vaults.values()]
        for path in opened:
            if Path(path).is_dir():
                return Path(path)
    raise HandoffError("no vault: pass --vault or set $OBSIDIAN_VAULT_PATH")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def safe_title(title: str) -> str:
    # Obsidian forbids these in file names; keep everything else (Korean, spaces, commas are fine)
    return re.sub(r'[\\/:*?"<>|#^\[\]]', " ", title).strip()


# ---------- copy extraction ----------

def card_lines(card: dict) -> list[str]:
    """Plain-text copy of one card, markup stripped, for the note (the spec keeps the markup)."""
    def plain(s: str) -> str:
        return s.replace("**", "").replace("\u00a0", " ").replace("\n", " / ")
    t = card["type"]
    out = []
    if card.get("kicker"):
        out.append(f"- 킥커: {plain(card['kicker'])}")
    if t == "stat":
        out.append(f"- 숫자: {plain(str(card['value']))}{plain(card.get('unit', ''))}")
        out.append(f"- 문장: {plain(card['label'])}")
        if card.get("context"):
            out.append(f"- 보조: {plain(card['context'])}")
        if card.get("source"):
            out.append(f"- 기준: {plain(card['source'])}")
    elif t == "quote":
        out.append(f"- 인용: {plain(card['quote'])}")
        if card.get("who"):
            out.append(f"- 출처 표기: {plain(card['who'])}")
    else:
        out.append(f"- 제목: {plain(card['title'])}")
        if card.get("subtitle"):
            out.append(f"- 부제: {plain(card['subtitle'])}")
        if card.get("lead"):
            out.append(f"- 리드: {plain(card['lead'])}")
        if card.get("body"):
            out.append(f"- 본문: {plain(card['body'])}")
        if card.get("items"):
            for i, it in enumerate(card["items"], 1):
                out.append(f"- 항목 {i}: {plain(it)}")
        if t == "compare":
            for side, label in (("left", "왼쪽"), ("right", "오른쪽")):
                s = card[side]
                out.append(f"- {label}: {plain(s['title'])} — {plain(s.get('body', ''))}")
            if card.get("footer"):
                out.append(f"- 마무리: {plain(card['footer'])}")
        if card.get("cta"):
            out.append(f"- 행동 문구: {plain(card['cta'])}")
    if card.get("image"):
        img = card["image"]
        desc = img.get("alt") or Path(img["src"]).name
        out.append(f"- 사진: {Path(img['src']).name} — {desc}")
    return out


# ---------- writers ----------

def bump_updated(text: str, day: str) -> str:
    if re.search(r"^updated: .*$", text, flags=re.M):
        return re.sub(r"^updated: .*$", f"updated: {day}", text, count=1, flags=re.M)
    return text


def insert_line(text: str, heading: str, line: str, *, key: str | None = None) -> str:
    """Insert `line` into the section `heading` (after its last bullet). Creates the section before `## 연결`
    (or at the end) if missing. No-op when the line — or another line carrying `key` (the note link) — exists."""
    if line in text or (key and key in text):
        return text
    lines = text.split("\n")
    try:
        start = next(i for i, l in enumerate(lines) if l.strip() == heading)
    except StopIteration:
        anchor = next((i for i, l in enumerate(lines) if l.strip() == "## 연결"), len(lines))
        block = [heading, "", line, ""]
        lines[anchor:anchor] = block
        return "\n".join(lines)
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    last_bullet = max((i for i in range(start + 1, end) if lines[i].startswith("- ")), default=None)
    at = last_bullet + 1 if last_bullet is not None else start + 2
    lines.insert(at, line)
    return "\n".join(lines)


def write_index_line(path: Path, heading: str, line: str, day: str, dry_run: bool, key: str | None = None) -> str:
    if not path.is_file():
        return "missing"
    text = path.read_text(encoding="utf-8")
    new = bump_updated(insert_line(text, heading, line, key=key), day)
    if new == text:
        return "unchanged"
    if not dry_run:
        path.write_text(new, encoding="utf-8")
    return "updated"


def handoff(*, spec_path: Path, out_dir: Path, vault: Path, area: str, channel: str, title: str, date: str | None,
            source_url: str, caption: str, consent_note: str, extra_sources: list[str], dry_run: bool) -> dict:
    day = date or _date.today().isoformat()
    channel = channel.lower()
    if channel not in CHANNEL_DIR:
        raise HandoffError(f"channel {channel!r} not in {sorted(CHANNEL_DIR)}")
    area_dir = vault / area
    if not area_dir.is_dir():
        raise HandoffError(f"area folder not found: {area_dir}")
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    cards = render_cards.validate_spec(spec)
    qa_path = out_dir / "qa.json"
    if not qa_path.is_file():
        raise HandoffError(f"{qa_path} missing — render first")
    qa = json.loads(qa_path.read_text(encoding="utf-8"))
    if qa.get("problems"):
        raise HandoffError(f"qa.json lists {len(qa['problems'])} problem(s); fix and re-render before filing")
    pngs = [out_dir / f"{i:02d}.png" for i in range(1, len(cards) + 1)]
    missing = [p.name for p in pngs if not p.is_file()]
    if missing:
        raise HandoffError(f"PNGs missing in {out_dir}: {missing}")
    if SIGNED_URL.search(json.dumps(spec, ensure_ascii=False)) or SIGNED_URL.search(caption or ""):
        raise HandoffError("spec/caption contains a signed URL — strip it; the vault keeps public URLs only")

    stitle = safe_title(title)
    att_dir = area_dir / "Attachments" / f"{day} - {stitle} (카드뉴스)"
    ch_dir = area_dir / "Content" / CHANNEL_DIR[channel]
    note_path = ch_dir / f"{CHANNEL_DIR[channel]} - {stitle}.md"
    rel_att = f"{area}/Attachments/{att_dir.name}"
    rel_note = f"{area}/Content/{CHANNEL_DIR[channel]}/{note_path.stem}"
    result = {"attachments": str(att_dir), "note": {"path": str(note_path), "status": "planned"}, "index": {}, "dry_run": dry_run}

    # 1) assets first
    copied: list[tuple[str, Path]] = []
    if not dry_run:
        att_dir.mkdir(parents=True, exist_ok=True)
        (att_dir / "assets").mkdir(exist_ok=True)
    for p in pngs + [out_dir / "cards.pdf"]:
        if p.is_file():
            copied.append((p.name, p))
    spec_copy = dict(spec)
    spec_copy["source"] = SIGNED_URL.sub("[signed url removed]", str(spec.get("source", "")))
    for card in spec_copy.get("cards", []):
        if card.get("image"):
            card["image"] = dict(card["image"], src=f"assets/{Path(card['image']['src']).name}")
    if spec_copy.get("backdrop"):
        spec_copy["backdrop"] = dict(spec_copy["backdrop"], src=f"assets/{Path(spec_copy['backdrop']['src']).name}")
    asset_srcs = {Path(c["image"]["src"]).name: render_cards.resolve_image(c["image"]["src"], spec_path.parent)
                  for c in cards if c.get("image")}
    if spec.get("backdrop"):
        asset_srcs[Path(spec["backdrop"]["src"]).name] = render_cards.resolve_image(spec["backdrop"]["src"], spec_path.parent)
    manifest = [f"# MANIFEST — {stitle} (카드뉴스)", "", f"- 적재일: {day}", f"- 제작: 스킬 `make-card-news` (donggu-skills)",
                f"- 출처: {source_url or '(미기재)'}", "", "| 파일 | SHA-256 | 바이트 |", "|---|---|---|"]
    if not dry_run:
        for name, src in copied:
            shutil.copy2(src, att_dir / name)
        for name, src in asset_srcs.items():
            shutil.copy2(src, att_dir / "assets" / name)
        (att_dir / "cards.json").write_text(json.dumps(spec_copy, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        for f in sorted(att_dir.rglob("*")):
            if f.is_file() and f.name != "MANIFEST.md":
                manifest.append(f"| {f.relative_to(att_dir)} | {sha256(f)} | {f.stat().st_size} |")
        (att_dir / "MANIFEST.md").write_text("\n".join(manifest) + "\n", encoding="utf-8")
        try:
            import subprocess
            subprocess.run(["xattr", "-dr", "com.apple.quarantine", str(att_dir)], capture_output=True)
        except Exception:
            pass
    result["files"] = [n for n, _ in copied] + ["cards.json", "MANIFEST.md"] + [f"assets/{n}" for n in asset_srcs]

    # 2) the channel note
    if note_path.is_file():
        result["note"]["status"] = "exists"
    else:
        sources = [f'  - "{s}"' for s in extra_sources]
        if source_url:
            sources.insert(0, f'  - "{source_url}"')
        fm = ["---", "type: channel_pack", f"channel: {channel}", f"area: {AREA_KEY.get(area, 'fde-community')}",
              "status: draft", "visibility: internal", f"created: {day}", f"updated: {day}",
              "topics: [beyond-deploy, case-talk, content, card-news]", "format: card-news", f"cards: {len(cards)}"]
        if sources:
            fm += ["sources:"] + sources
        fm.append("---")
        body = [f"# {title}", "",
                f"> [!note] 카드뉴스 {len(cards)}장 · 미게시", 
                f"> 제작은 스킬 `make-card-news`(donggu-skills), 편집 원본은 `{rel_att}/cards.json`. 게시 뒤에 `status: published`와 `published_at`·`published_url`을 남긴다. 게시는 별도 승인(`publish-sns`).", "",
                "## 장별 카피", ""]
        for i, card in enumerate(cards, 1):
            body.append(f"### {i:02d} · {card['type']}")
            body.append(f"![[{rel_att}/{i:02d}.png]]")
            body += card_lines(card)
            body.append("")
        body += ["## 캡션 초안", "", caption.strip() if caption.strip() else "(미작성 — `writing-social-content`로 작성)", "",
                 "## 사진과 동의", "",
                 consent_note.strip() if consent_note.strip() else "(확인 전)", "",
                 f"- 사진 원본·해시: [[{rel_att}/MANIFEST|MANIFEST]]", "",
                 "## 편집 판단", "",
                 "- 디자인: 표지 톤(사진 전면 + 어두운 그라데이션 + 흰 글자)을 전 장에 적용, 선·라벨·페이지 번호 없음 — 2026-10-25 호스트 선택.",
                 "- 이미지 안에 링크·버튼을 넣지 않음(인스타 캐러셀·링크드인 문서 PDF는 이미지 내 링크가 동작하지 않음). 링크는 캡션·첫 댓글·프로필.",
                 "- 수치·사실은 출처 글에서 그대로 가져왔고 새 사실을 더하지 않음.", "",
                 "## 연결", "",
                 f"[[{area}/Content/{CHANNEL_DIR[channel]}/INDEX - {CHANNEL_DIR[channel]}|{CHANNEL_DIR[channel]}]] · "
                 f"[[{area}/Content/INDEX - Content|콘텐츠]] · [[{rel_att}/MANIFEST|첨부 자료]]", ""]
        if not dry_run:
            note_path.write_text("\n".join(fm + [""] + body), encoding="utf-8")
        result["note"]["status"] = "created"

    # 3) index lines
    note_link = f"[[{rel_note}|{title}]]"
    key = f"[[{rel_note}|"
    result["index"]["channel"] = write_index_line(ch_dir / f"INDEX - {CHANNEL_DIR[channel]}.md", "## 카드뉴스",
                                                 f"- {note_link} — {len(cards)}장, {day} 제작, 미게시", day, dry_run, key)
    result["index"]["content"] = write_index_line(area_dir / "Content" / "INDEX - Content.md", "## 카드뉴스",
                                                 f"- {note_link} — {CHANNEL_DIR[channel]}, {len(cards)}장, {day}. 제작 절차는 스킬 `make-card-news`", day, dry_run, key)
    result["index"]["attachments"] = write_index_line(area_dir / "Attachments" / "INDEX - Attachments.md", "## 공식 콘텐츠 자료",
                                                     f"- `{att_dir.name}/` — 카드뉴스 PNG {len(cards)}장·PDF·편집 원본 cards.json·사진 {len(asset_srcs)}장 (해시는 MANIFEST). 원고: {note_link}", day, dry_run, key)
    return result


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spec", type=Path)
    ap.add_argument("--out", type=Path, required=True, help="render output dir (PNGs, cards.pdf, qa.json)")
    ap.add_argument("--title", required=True)
    ap.add_argument("--channel", default="instagram", choices=sorted(CHANNEL_DIR))
    ap.add_argument("--area", default="FDE 커뮤니티 (Beyond Deploy)")
    ap.add_argument("--vault", default=None)
    ap.add_argument("--date", default=None)
    ap.add_argument("--source-url", default="")
    ap.add_argument("--source", action="append", default=[], help="extra wikilink source, repeatable")
    ap.add_argument("--caption-file", type=Path, default=None)
    ap.add_argument("--consent", default="")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    try:
        vault = resolve_vault(a.vault)
        caption = a.caption_file.read_text(encoding="utf-8") if a.caption_file else ""
        res = handoff(spec_path=a.spec, out_dir=a.out, vault=vault, area=a.area, channel=a.channel, title=a.title,
                      date=a.date, source_url=a.source_url, caption=caption, consent_note=a.consent,
                      extra_sources=a.source, dry_run=a.dry_run)
    except (HandoffError, render_cards.SpecError, OSError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
