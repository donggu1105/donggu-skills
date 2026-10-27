#!/usr/bin/env python3
"""Render a card-news spec (JSON) to 1080x1350 PNGs + one PDF with headless Chrome.

Usage:
    render_cards.py SPEC.json --out DIR [--theme NAME] [--no-pdf] [--chrome PATH]

Exit codes: 0 ok · 1 usage/spec/render error · 2 rendered but QA found problems.

Stdlib + optional Pillow (PDF merge). No Playwright, no SaaS. Chrome is found via
$CARD_NEWS_CHROME, then the usual macOS/Linux locations.
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL_DIR = HERE.parent
W, H = 1080, 1350
CARD_TYPES = ("cover", "stat", "point", "quote", "list", "compare", "steps", "closing")
REQUIRED = {
    "cover": ("title",),
    "stat": ("value", "label"),
    "point": ("title", "body"),
    "quote": ("quote",),
    "list": ("title", "items"),
    "compare": ("title", "left", "right"),
    "steps": ("title", "items"),
    "closing": ("title",),
}
LIMITS = {"items": 5, "title_chars": 60, "stat_value_chars": 6}
# Nothing inside a card image is clickable: Instagram has no in-image links, LinkedIn strips links from
# document PDFs. A URL or a click/tap verb in the CTA is a fake button → rejected at validation.
FAKE_CTA = re.compile(r"https?://|www\.|\.(?:kr|com|io|net|org|ai|app|dev)(?:/|\b)|클릭|눌러|누르|탭하|터치|click|tap\b", re.IGNORECASE)
IMAGE_MODES = ("full", "band", "inline")
LAYOUTS = ("classic", "cinematic")  # cinematic: cover treatment on every card — photo + gradient + white type, no chrome
IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".webp")
CHROME_CANDIDATES = (
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
    "google-chrome", "chromium", "chromium-browser", "chrome",
)


class SpecError(ValueError):
    pass


# ---------- spec ----------

def validate_spec(spec: dict) -> list[dict]:
    cards = spec.get("cards")
    if not isinstance(cards, list) or not cards:
        raise SpecError("spec.cards must be a non-empty list")
    layout = spec.get("layout", "classic")
    if layout not in LAYOUTS:
        raise SpecError(f"spec.layout {layout!r} not in {LAYOUTS}")
    bd = spec.get("backdrop")
    if layout == "cinematic":
        for i, card in enumerate(cards, 1):
            if isinstance(card, dict) and not card.get("image") and not bd:
                raise SpecError(f"card {i}: layout 'cinematic' needs a photo on every card — add image.src or a set-level backdrop")
    if bd is not None:
        if not isinstance(bd, dict) or not bd.get("src"):
            raise SpecError("spec.backdrop must be an object with 'src'")
        if not str(bd["src"]).lower().endswith(IMAGE_EXTS):
            raise SpecError(f"spec.backdrop.src must be one of {IMAGE_EXTS}")
        if "overlay" in bd and not (isinstance(bd["overlay"], (int, float)) and 0 <= float(bd["overlay"]) <= 1):
            raise SpecError("spec.backdrop.overlay must be a number between 0 and 1")
        tint = bd.get("tint", 0.86)
        if not isinstance(tint, (int, float)) or not 0.5 <= float(tint) <= 1.0:
            raise SpecError("spec.backdrop.tint must be a number between 0.5 and 1 (how much of the theme bg shows through)")
    for i, card in enumerate(cards, 1):
        t = card.get("type")
        if t not in CARD_TYPES:
            raise SpecError(f"card {i}: unknown type {t!r}; allowed {CARD_TYPES}")
        for key in REQUIRED[t]:
            if not card.get(key):
                raise SpecError(f"card {i} ({t}): missing field {key!r}")
        if t in ("list", "steps") and len(card["items"]) > LIMITS["items"]:
            raise SpecError(f"card {i} ({t}): max {LIMITS['items']} items")
        if t == "compare":
            for side in ("left", "right"):
                if not isinstance(card[side], dict) or not card[side].get("title"):
                    raise SpecError(f"card {i} (compare): {side} needs a title")
        if len(str(card.get("title", ""))) > LIMITS["title_chars"]:
            raise SpecError(f"card {i}: title longer than {LIMITS['title_chars']} chars")
        if t == "closing" and card.get("cta") and FAKE_CTA.search(str(card["cta"])):
            raise SpecError(f"card {i} (closing): cta {card['cta']!r} is a URL or a click verb — nothing in the image is clickable. "
                            "Use a platform-native action (저장 / 공유 / 댓글 / 프로필 링크 / 첫 댓글) and put the URL in the caption.")
        if t == "stat" and len(str(card["value"])) > LIMITS["stat_value_chars"]:
            raise SpecError(f"card {i} (stat): value longer than {LIMITS['stat_value_chars']} chars — one short number per slide; move detail to label/context")
        img = card.get("image")
        if img is not None:
            if not isinstance(img, dict) or not img.get("src"):
                raise SpecError(f"card {i}: image must be an object with 'src'")
            mode = img.get("mode", "band")
            if mode not in IMAGE_MODES:
                raise SpecError(f"card {i}: image.mode {mode!r} not in {IMAGE_MODES}")
            if not str(img["src"]).lower().endswith(IMAGE_EXTS):
                raise SpecError(f"card {i}: image.src must be one of {IMAGE_EXTS}")
            z = img.get("zoom", 1.0)
            if not isinstance(z, (int, float)) or not 1.0 <= float(z) <= 2.0:
                raise SpecError(f"card {i}: image.zoom must be a number between 1 and 2")
            fd = img.get("fade", 0.42)
            if not isinstance(fd, (int, float)) or not 0.2 <= float(fd) <= 0.9:
                raise SpecError(f"card {i}: image.fade must be between 0.2 and 0.9 (fraction of the band where the dissolve starts)")
            if t == "compare" and mode == "inline":
                raise SpecError(f"card {i}: compare cards take 'full' or 'band' images only")
    return cards


def resolve_image(src: str, spec_dir: Path) -> Path:
    """Local path (absolute, or relative to the spec file). Remote URLs are not fetched — download first."""
    if re.match(r"^https?://", src):
        raise SpecError(f"image.src is a URL ({src[:60]}…); download it next to the spec and reference the file")
    p = Path(src).expanduser()
    if not p.is_absolute():
        p = (spec_dir / p).resolve()
    if not p.is_file():
        raise SpecError(f"image not found: {p}")
    return p


def load_theme(name: str, skill_dir: Path = SKILL_DIR) -> dict:
    path = Path(name) if name.endswith(".json") else skill_dir / "themes" / f"{name}.json"
    if not path.is_file():
        raise SpecError(f"theme not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


# ---------- html ----------

_INLINE_BOLD = re.compile(r"\*\*(.+?)\*\*")


def rich(text: str) -> str:
    """Escape, then allow **bold** and line breaks only."""
    parts = []
    for i, line in enumerate(str(text).split("\n")):
        esc = html.escape(line, quote=True)
        esc = _INLINE_BOLD.sub(r'<strong class="em">\1</strong>', esc)
        parts.append(esc)
    return "<br>".join(parts)


def _items_html(items: list, numbered: bool) -> str:
    out = []
    for n, it in enumerate(items, 1):
        marker = f'<span class="num">{n:02d}</span>' if numbered else '<span class="dot"></span>'
        out.append(f'<li>{marker}<span class="it">{rich(it)}</span></li>')
    tag = "ol" if numbered else "ul"
    return f'<{tag} class="items {"steps" if numbered else "bullets"}">{"".join(out)}</{tag}>'


def card_body_html(card: dict) -> str:
    t = card["type"]
    if t == "cover":
        sub = f'<p class="sub" data-qa="sub">{rich(card["subtitle"])}</p>' if card.get("subtitle") else ""
        kicker = f'<p class="kicker">{rich(card["kicker"])}</p>' if card.get("kicker") else ""
        return f'<div class="cover">{kicker}<h1 class="title big" data-qa="title">{rich(card["title"])}</h1>{sub}</div>'
    if t == "stat":
        kicker = f'<p class="kicker">{rich(card["kicker"])}</p>' if card.get("kicker") else ""
        unit = f'<span class="stat-unit">{rich(card["unit"])}</span>' if card.get("unit") else ""
        ctx = f'<p class="stat-context" data-qa="body">{rich(card["context"])}</p>' if card.get("context") else ""
        src = f'<p class="stat-source" data-qa="source">{rich(card["source"])}</p>' if card.get("source") else ""
        num = rich(card["value"]).replace("1", '<span class="k1">1</span>')  # optical kern: the 1's foot leaves a hole
        return (f'<div class="stat">{kicker}'
                f'<p class="stat-value" data-qa="value"><span class="stat-num">{num}</span>{unit}</p>'
                f'<h2 class="stat-label" data-qa="label">{rich(card["label"])}</h2>{ctx}{src}</div>')
    if t == "point":
        return (f'<h2 class="title" data-qa="title">{rich(card["title"])}</h2>'
                f'<div class="body" data-qa="body">{rich(card["body"])}</div>')
    if t == "quote":
        who = f'<p class="who" data-qa="who">{rich(card["who"])}</p>' if card.get("who") else ""
        return f'<div class="quote-wrap"><span class="qmark">“</span><blockquote class="quote" data-qa="body">{rich(card["quote"])}</blockquote>{who}</div>'
    if t in ("list", "steps"):
        lead = f'<p class="lead" data-qa="lead">{rich(card["lead"])}</p>' if card.get("lead") else ""
        return (f'<h2 class="title" data-qa="title">{rich(card["title"])}</h2>{lead}'
                f'<div class="body" data-qa="body">{_items_html(card["items"], numbered=(t == "steps"))}</div>')
    if t == "compare":
        cols = []
        for side, cls in (("left", "l"), ("right", "r")):
            s = card[side]
            body = f'<div class="col-body">{rich(s.get("body", ""))}</div>' if s.get("body") else ""
            cols.append(f'<div class="col {cls}" data-qa="col-{cls}"><p class="col-title">{rich(s["title"])}</p>{body}</div>')
        foot = f'<p class="foot" data-qa="foot">{rich(card["footer"])}</p>' if card.get("footer") else ""
        return (f'<h2 class="title" data-qa="title">{rich(card["title"])}</h2>'
                f'<div class="compare" data-qa="body">{"".join(cols)}</div>{foot}')
    if t == "closing":
        body = f'<div class="body" data-qa="body">{rich(card["body"])}</div>' if card.get("body") else ""
        cta = f'<p class="cta" data-qa="cta">{rich(card["cta"])}</p>' if card.get("cta") else ""
        return f'<div class="closing"><h2 class="title" data-qa="title">{rich(card["title"])}</h2>{body}{cta}</div>'
    raise SpecError(f"unhandled type {t}")


def image_block(card: dict, spec_dir: Path | None, spec: dict | None = None) -> tuple[str, str, str, str, str]:
    """Returns (mode, outer_block_html, inline_html, focus, overlay, zoom, fade) for the card's image, if any.
    In the cinematic layout every card is `full`: its own image, else the set backdrop."""
    cinematic = (spec or {}).get("layout") == "cinematic"
    img = card.get("image")
    if not img and cinematic and (spec or {}).get("backdrop"):
        bd = spec["backdrop"]
        img = {"src": bd["src"], "focus": bd.get("focus", "50% 50%"), "overlay": bd.get("overlay", 0.84), "alt": ""}
    if not img:
        return "text", "", "", "50% 50%", "0.72", "1.0", "0.42"
    mode = "full" if cinematic else img.get("mode", "band")
    src = img["src"]
    if spec_dir is not None:
        src = resolve_image(src, spec_dir).as_uri()
    alt = html.escape(img.get("alt", ""), quote=True)
    focus = html.escape(str(img.get("focus", "50% 50%")), quote=True)
    overlay = str(float(img.get("overlay", 0.72)))
    zoom = str(float(img.get("zoom", 1.0)))
    fade = str(float(img.get("fade", 0.42)))
    tag = f'<img src="{html.escape(src, quote=True)}" alt="{alt}" data-qa-img="{mode}">'
    if mode == "full":
        return mode, f'<div class="bg">{tag}</div>', "", focus, overlay, zoom, fade
    if mode == "band":
        return mode, f'<div class="band">{tag}</div>', "", focus, overlay, zoom, fade
    return mode, "", f'<div class="inline-img" data-qa="image">{tag}</div>', focus, overlay, zoom, fade


def wash_block(card: dict, mode: str, spec: dict, spec_dir: Path | None) -> tuple[str, str, str]:
    """A blurred, tinted copy of a photo behind the whole card, so text and band cards keep the
    cover's atmosphere instead of dropping to flat white. Returns (wash_html, class, tint).
    - full cards: none (the photo already fills the card)
    - band cards: their own photo (the band dissolves into the page)
    - text cards: the set-level `backdrop` photo
    - `"wash": false` on a card opts out."""
    if mode == "full" or card.get("wash") is False:
        return "", "", "0.86"
    src = None
    tint = 0.86
    bd = spec.get("backdrop")
    if mode == "band" and card.get("image"):
        src = card["image"]["src"]
        if bd:
            tint = float(bd.get("tint", tint))
    elif bd:
        src, tint = bd["src"], float(bd.get("tint", tint))
    if not src or spec_dir is None:
        return "", "", "0.86"
    src = resolve_image(src, spec_dir).as_uri()
    tag = f'<img src="{html.escape(src, quote=True)}" alt="" data-qa-img="wash">'
    return f'<div class="wash">{tag}</div>', "has-wash", str(tint)


def build_card_html(card: dict, index: int, total: int, spec: dict, theme: dict,
                    template_path: Path | None = None, spec_dir: Path | None = None) -> str:
    template = (template_path or SKILL_DIR / "templates" / "card.html").read_text(encoding="utf-8")
    font_stack = ", ".join(f'"{f}"' for f in theme["fonts"]) + ", sans-serif"
    mode, outer, inline, focus, overlay, zoom, fade = image_block(card, spec_dir, spec)
    wash, wash_cls, wash_tint = wash_block(card, mode, spec, spec_dir)
    layout = spec.get("layout", "classic")
    content = card_body_html(card)
    if inline:
        # inline image sits after the title (list/steps/point) or after the body (closing/cover/quote)
        marker = "</h2>" if "</h2>" in content and card["type"] in ("point", "list", "steps") else None
        if marker:
            head, tail = content.split(marker, 1)
            content = head + marker + inline + tail
        else:
            content = content + inline
    mapping = {
        "LANG": theme.get("lang", "ko"),
        "W": str(W), "H": str(H),
        "FONT_STACK": font_stack,
        "FONT_CHECK": theme["fonts"][0],
        "BG": theme["bg"], "INK": theme["ink"], "MUTED": theme["muted"],
        "ACCENT": theme["accent"], "ACCENT_SOFT": theme["accent_soft"], "LINE": theme["line"],
        "ACCENT_ON_DARK": theme.get("accent_on_dark", theme["accent_soft"]),
        "SURFACE": theme["surface"],
        "SERIES": html.escape(spec.get("series", "")),
        "HANDLE": html.escape(spec.get("handle", theme.get("handle", ""))),
        "PAGE": f"{index:02d} / {total:02d}",
        "META_BLOCK": "" if layout == "cinematic" else
            f'<div class="meta" data-qa="meta"><span class="series">{html.escape(spec.get("series", ""))}</span>'
            f'<span class="page">{index:02d} / {total:02d}</span></div>',
        "FOOTER_BLOCK": (f'<div class="footer" data-qa="footer"><span class="handle">{html.escape(spec.get("handle", theme.get("handle", "")))}</span></div>'
                         if index in (1, total) else "") if layout == "cinematic" else
            f'<div class="footer" data-qa="footer"><span class="handle">{html.escape(spec.get("handle", theme.get("handle", "")))}</span>'
            f'<span class="page">{index:02d} / {total:02d}</span></div>',
        "TYPE": card["type"],
        "MODE": mode,
        "LAYOUT": layout,
        "IMAGE_BLOCK": outer,
        "WASH_BLOCK": wash,
        "WASH_CLASS": wash_cls,
        "WASH_TINT": wash_tint,
        "FOCUS": focus,
        "OVERLAY": overlay,
        "ZOOM": zoom,
        "FADE": fade,
        "CONTENT": content,
    }
    out = template
    for k, v in mapping.items():
        out = out.replace("{{" + k + "}}", v)
    leftover = re.findall(r"{{[A-Z_]+}}", out)
    if leftover:
        raise SpecError(f"template placeholders unresolved: {sorted(set(leftover))}")
    return out


# ---------- chrome ----------

def find_chrome(explicit: str | None = None) -> str | None:
    for cand in ([explicit] if explicit else []) + [os.environ.get("CARD_NEWS_CHROME")] + list(CHROME_CANDIDATES):
        if not cand:
            continue
        if os.path.sep in cand:
            if os.path.isfile(cand) and os.access(cand, os.X_OK):
                return cand
        else:
            found = shutil.which(cand)
            if found:
                return found
    return None


def render_png(chrome: str, html_path: Path, png_path: Path, profile_dir: Path) -> dict:
    """Screenshot one card and return the embedded QA probe result."""
    cmd = [
        chrome, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run",
        "--no-default-browser-check", f"--user-data-dir={profile_dir}", "--force-device-scale-factor=1",
        f"--window-size={W},{H}", "--virtual-time-budget=4000", "--run-all-compositor-stages-before-draw",
        f"--screenshot={png_path}", "--dump-dom", html_path.resolve().as_uri(),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if proc.returncode != 0 or not png_path.is_file():
        raise RuntimeError(f"chrome failed for {html_path.name}: rc={proc.returncode}\n{proc.stderr[-800:]}")
    m = re.search(r'data-qa-result="([^"]*)"', proc.stdout)
    if not m:
        return {"probe": "missing"}
    return json.loads(html.unescape(m.group(1)))


def merge_pdf(pngs: list[Path], pdf_path: Path) -> bool:
    try:
        from PIL import Image
    except ImportError:
        return False
    images = [Image.open(p).convert("RGB") for p in pngs]
    images[0].save(pdf_path, save_all=True, append_images=images[1:], resolution=144.0)
    for im in images:
        im.close()
    return True


# ---------- qa ----------

def qa_card(index: int, card: dict, probe: dict, png: Path) -> tuple[dict, list[dict]]:
    problems = []
    report = {"index": index, "type": card["type"], "png": png.name, "font_available": probe.get("font", False),
              "elements": probe.get("items", [])}
    if probe.get("probe") == "missing":
        problems.append({"card": index, "kind": "probe-missing", "detail": "QA script did not run"})
        return report, problems
    if not probe.get("font"):
        problems.append({"card": index, "kind": "font-fallback", "detail": "primary font not available to Chrome"})
    safe_bottom = round(H * 0.90)   # platform UI overlays the bottom 10 %; the footer sits exactly on this line
    safe_right = round(W * 0.93)
    chrome_ids = {"meta", "footer"}
    footer = next((el for el in probe.get("items", []) if el["id"] == "footer"), None)
    content_floor = footer["top"] - 8 if footer else safe_bottom
    for el in probe.get("items", []):
        if el.get("overflow"):
            problems.append({"card": index, "kind": "overflow", "element": el["id"], "detail": "text clipped inside its box"})
        if el["id"] in chrome_ids:
            continue
        if el.get("bottom", 0) > content_floor:
            problems.append({"card": index, "kind": "safe-area", "element": el["id"],
                             "detail": f"bottom {el['bottom']}px runs into the footer/bottom 10 % (limit {content_floor}px)"})
        if el.get("right", 0) > safe_right:
            problems.append({"card": index, "kind": "safe-area", "element": el["id"], "detail": f"right {el['right']}px > {safe_right}px"})
    for a, b in probe.get("overlaps", []):
        problems.append({"card": index, "kind": "overlap", "element": f"{a}+{b}", "detail": "boxes overlap"})
    for im in probe.get("images", []):
        report.setdefault("images", []).append(im)
        if not im.get("loaded"):
            problems.append({"card": index, "kind": "image", "element": im.get("id"), "detail": "image failed to load (path? format?)"})
        elif im.get("w", 0) < 900:
            problems.append({"card": index, "kind": "image-small", "element": im.get("id"), "detail": f"source only {im.get('w')}px wide; will look soft at 1080"})
    if footer and abs(footer["bottom"] - safe_bottom) > 6:
        problems.append({"card": index, "kind": "layout", "element": "footer", "detail": f"footer bottom {footer['bottom']}px, expected ≈{safe_bottom}px (layout collapsed?)"})
    try:
        from PIL import Image
        with Image.open(png) as im:
            if im.size != (W, H):
                problems.append({"card": index, "kind": "size", "detail": f"{im.size} != {(W, H)}"})
    except ImportError:
        pass
    return report, problems


# ---------- main ----------

def render(spec_path: Path, out: Path, theme_name: str | None, chrome_path: str | None, make_pdf: bool) -> int:
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    cards = validate_spec(spec)
    theme = load_theme(theme_name or spec.get("theme") or "donggu")
    chrome = find_chrome(chrome_path)
    if not chrome:
        print("ERROR: no headless Chrome/Chromium found; set --chrome or $CARD_NEWS_CHROME", file=sys.stderr)
        return 1
    out.mkdir(parents=True, exist_ok=True)
    html_dir = out / "html"
    html_dir.mkdir(exist_ok=True)
    total = len(cards)
    pngs, reports, problems = [], [], []
    with tempfile.TemporaryDirectory(prefix="cardnews-chrome-") as profile:
        for i, card in enumerate(cards, 1):
            page = build_card_html(card, i, total, spec, theme, spec_dir=spec_path.resolve().parent)
            html_path = html_dir / f"{i:02d}.html"
            html_path.write_text(page, encoding="utf-8")
            png_path = out / f"{i:02d}.png"
            probe = render_png(chrome, html_path, png_path, Path(profile))
            report, probs = qa_card(i, card, probe, png_path)
            pngs.append(png_path)
            reports.append(report)
            problems.extend(probs)
            print(f"card {i:02d}/{total:02d} {card['type']:<8} {'OK' if not probs else 'ISSUES ' + str(len(probs))}")
    pdf_ok = False
    if make_pdf:
        pdf_ok = merge_pdf(pngs, out / "cards.pdf")
        if not pdf_ok:
            problems.append({"card": 0, "kind": "pdf", "detail": "Pillow missing; PDF not written"})
    qa = {"spec": str(spec_path), "theme": theme.get("name", theme_name), "chrome": chrome,
          "cards_total": total, "pdf": pdf_ok, "cards": reports, "problems": problems}
    (out / "qa.json").write_text(json.dumps(qa, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n{total} PNG → {out}  pdf={'yes' if pdf_ok else 'no'}  problems={len(problems)}  (qa.json)")
    return 2 if problems else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spec", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--theme", default=None, help="theme name in themes/ or a path to a .json")
    ap.add_argument("--chrome", default=None)
    ap.add_argument("--no-pdf", action="store_true")
    a = ap.parse_args(argv)
    try:
        return render(a.spec, a.out, a.theme, a.chrome, make_pdf=not a.no_pdf)
    except (SpecError, RuntimeError, json.JSONDecodeError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
