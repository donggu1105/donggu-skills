#!/usr/bin/env python3
"""Render a story spec (JSON) to 1080x1920 story PNGs (+ JPEG copies for the Instagram API) with headless Chrome.

A story is one or more full-bleed frames. Each frame: one image (own asset, never a remote URL), a kicker,
a headline, an optional line of body copy, and an optional `sticker` block — an empty, labelled area in the
lower third where the host places the native link sticker in the Instagram app. Nothing in the frame is a
button: the Instagram API publishes a story image only, link/mention/poll stickers exist in the app alone.

Usage:
  python3 render_story.py SPEC.json --out OUT_DIR [--theme NAME|path.json] [--chrome PATH]

Exit: 0 = rendered clean, 2 = rendered with QA problems (see OUT_DIR/qa.json), 1 = spec/render error.
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
CARD_NEWS_DIR = SKILL_DIR.parent / "make-card-news"
W, H = 1080, 1920
SAFE_TOP, SAFE_BOTTOM = 250, 340          # Instagram story UI: profile row on top, reply bar at the bottom
MAX_JPEG_BYTES = 8 * 1024 * 1024
FRAME_TYPES = ("hook", "detail", "cta")
FIELD_LIMITS = {"kicker": 28, "title": 40, "body": 90, "sticker": 24}
BLOCKED_CTA = re.compile(r"https?://|www\.|\.kr\b|\.com\b|클릭|눌러|탭하|터치", re.I)


class SpecError(ValueError):
    pass


def _s(v) -> str:
    return "" if v is None else str(v)


def validate_spec(spec: dict) -> list[dict]:
    if not isinstance(spec, dict) or not isinstance(spec.get("frames"), list) or not spec["frames"]:
        raise SpecError("spec needs a non-empty `frames` list")
    if len(spec["frames"]) > 5:
        raise SpecError("a story set is at most 5 frames — more becomes a carousel, use make-card-news")
    out = []
    for i, f in enumerate(spec["frames"], 1):
        if not isinstance(f, dict):
            raise SpecError(f"frame {i}: not an object")
        t = f.get("type", "hook")
        if t not in FRAME_TYPES:
            raise SpecError(f"frame {i}: type must be one of {FRAME_TYPES}")
        if not _s(f.get("title")).strip():
            raise SpecError(f"frame {i}: `title` is required")
        for k, lim in FIELD_LIMITS.items():
            if k in f and len(_s(f[k]).replace("\n", "")) > lim:
                raise SpecError(f"frame {i}: `{k}` longer than {lim} chars — cut words, never shrink type")
        for k in ("title", "body", "sticker", "kicker"):
            if k in f and BLOCKED_CTA.search(_s(f[k])):
                raise SpecError(f"frame {i}: `{k}` contains a URL or a click verb — stories link only via the native sticker")
        img = f.get("image") or spec.get("backdrop")
        if not img or not _s(img.get("src")).strip():
            raise SpecError(f"frame {i}: needs `image.src` (or a set `backdrop`)")
        if re.match(r"^https?://", _s(img.get("src"))):
            raise SpecError(f"frame {i}: remote image URLs are refused — copy the asset next to the spec")
        out.append({**f, "type": t})
    return out


def resolve_image(src: str, spec_dir: Path) -> Path:
    p = Path(src)
    if not p.is_absolute():
        p = (spec_dir / p).resolve()
    if not p.is_file():
        raise SpecError(f"image not found: {src}")
    return p


def load_theme(name: str) -> dict:
    """Themes are shared with make-card-news (same token names); a path to a .json works too."""
    p = Path(name)
    if not name.endswith(".json"):
        for base in (SKILL_DIR / "themes", CARD_NEWS_DIR / "themes"):
            cand = base / f"{name}.json"
            if cand.is_file():
                p = cand
                break
    if not p.is_file():
        raise SpecError(f"theme not found: {name}")
    theme = json.loads(p.read_text(encoding="utf-8"))
    for k in ("fonts", "bg", "ink", "muted", "accent", "accent_soft", "line", "surface"):
        if k not in theme:
            raise SpecError(f"theme {p.name} lacks `{k}`")
    return theme


def rich(text: str) -> str:
    t = html.escape(_s(text))
    t = re.sub(r"\*\*(.+?)\*\*", r'<span class="em">\1</span>', t)
    return t.replace("\n", "<br>")


def build_frame_html(frame: dict, index: int, total: int, spec: dict, theme: dict, spec_dir: Path,
                     template_path: Path | None = None, guide_off: bool = False) -> str:
    template = (template_path or SKILL_DIR / "templates" / "story.html").read_text(encoding="utf-8")
    img = frame.get("image") or spec["backdrop"]
    src = resolve_image(img["src"], spec_dir).as_uri()
    sticker = _s(frame.get("sticker")).strip()
    body = _s(frame.get("body")).strip()
    mapping = {
        "LANG": theme.get("lang", "ko"),
        "W": str(W), "H": str(H),
        "SAFE_TOP": str(SAFE_TOP), "SAFE_BOTTOM": str(SAFE_BOTTOM),
        "FONT_STACK": ", ".join(f'"{f}"' for f in theme["fonts"]) + ", sans-serif",
        "FONT_CHECK": theme["fonts"][0],
        "BG": theme["bg"], "INK": theme["ink"], "MUTED": theme["muted"], "ACCENT": theme["accent"],
        "ACCENT_SOFT": theme["accent_soft"], "ACCENT_ON_DARK": theme.get("accent_on_dark", theme["accent_soft"]),
        "IMG_SRC": html.escape(src, quote=True),
        "IMG_ALT": html.escape(_s(img.get("alt")), quote=True),
        "FOCUS": html.escape(_s(img.get("focus", "50% 50%")), quote=True),
        "OVERLAY": str(float(img.get("overlay", 0.78))),
        "ZOOM": str(float(img.get("zoom", 1.0))),
        "MODE": "full" if img.get("mode") == "full" else "top",
        "BAND_H": str(int(img.get("band", 1000))),
        "TYPE": frame["type"],
        "KICKER": rich(frame.get("kicker", "")),
        "TITLE": rich(frame["title"]),
        "BODY_BLOCK": f'<p class="body" data-qa="body">{rich(body)}</p>' if body else "",
        "STICKER_BLOCK": (f'<div class="sticker" data-qa="sticker"><span class="sticker-label">{html.escape(sticker)}</span>'
                          f'<span class="sticker-hint">여기에 링크 스티커를 올려요 — 이 안내는 게시 전 사라짐</span></div>')
                         if (sticker and not guide_off) else "",
        "HANDLE": html.escape(spec.get("handle", theme.get("handle", ""))),
        "PAGE": f"{index}/{total}" if total > 1 else "",
    }
    out = template
    for k, v in mapping.items():
        out = out.replace("{{" + k + "}}", v)
    leftover = re.findall(r"{{[A-Z_]+}}", out)
    if leftover:
        raise SpecError(f"template placeholders unresolved: {sorted(set(leftover))}")
    return out


def find_chrome(explicit: str | None = None) -> str | None:
    cands = [explicit, os.environ.get("CARD_NEWS_CHROME"),
             "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
             "/Applications/Chromium.app/Contents/MacOS/Chromium",
             shutil.which("google-chrome"), shutil.which("chromium"), shutil.which("chromium-browser")]
    return next((c for c in cands if c and Path(c).exists()), None)


def render_png(chrome: str, html_path: Path, png_path: Path, profile_dir: Path) -> dict:
    cmd = [chrome, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run",
           "--no-default-browser-check", f"--user-data-dir={profile_dir}", "--force-device-scale-factor=1",
           f"--window-size={W},{H}", "--virtual-time-budget=4000", "--run-all-compositor-stages-before-draw",
           f"--screenshot={png_path}", "--dump-dom", html_path.resolve().as_uri()]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if proc.returncode != 0 or not png_path.is_file():
        raise RuntimeError(f"chrome failed for {html_path.name}: rc={proc.returncode}\n{proc.stderr[-800:]}")
    m = re.search(r'data-qa-result="([^"]*)"', proc.stdout)
    return json.loads(html.unescape(m.group(1))) if m else {"probe": "missing"}


def to_jpeg(png: Path, jpg: Path) -> int:
    """Instagram's publishing API accepts JPEG only. Returns the byte size."""
    from PIL import Image  # Pillow is already a dependency of make-card-news (PDF merge)
    im = Image.open(png).convert("RGB")
    for q in (92, 88, 84, 80):
        im.save(jpg, "JPEG", quality=q, optimize=True, progressive=True)
        if jpg.stat().st_size <= MAX_JPEG_BYTES:
            break
    return jpg.stat().st_size


def qa_frame(index: int, frame: dict, probe: dict, png: Path, jpg_bytes: int) -> tuple[dict, list[dict]]:
    problems: list[dict] = []
    report = {"index": index, "type": frame["type"], "png": png.name, "jpeg_bytes": jpg_bytes,
              "font_available": probe.get("font", False), "elements": probe.get("items", [])}
    if probe.get("probe") == "missing":
        problems.append({"frame": index, "kind": "probe-missing", "detail": "QA script did not run"})
        return report, problems
    if not probe.get("font"):
        problems.append({"frame": index, "kind": "font-fallback", "detail": "primary font not loaded"})
    for el in probe.get("items", []):
        if el.get("overflow"):
            problems.append({"frame": index, "kind": "overflow", "element": el["id"]})
        if el["id"] in ("kicker", "title", "body", "sticker") and el["top"] < SAFE_TOP:
            problems.append({"frame": index, "kind": "safe-top", "element": el["id"], "detail": f"top {el['top']} < {SAFE_TOP}"})
        if el["id"] in ("kicker", "title", "body", "sticker") and el["bottom"] > H - SAFE_BOTTOM:
            problems.append({"frame": index, "kind": "safe-bottom", "element": el["id"], "detail": f"bottom {el['bottom']} > {H - SAFE_BOTTOM}"})
        if el["left"] < 0 or el["right"] > W:
            problems.append({"frame": index, "kind": "bounds", "element": el["id"]})
    for a, b in probe.get("overlaps", []):
        problems.append({"frame": index, "kind": "overlap", "elements": [a, b]})
    for im in probe.get("images", []):
        if not im.get("loaded"):
            problems.append({"frame": index, "kind": "image-missing"})
        elif im.get("w", 0) < 1080 or im.get("h", 0) < 1350:
            problems.append({"frame": index, "kind": "image-small", "detail": f"{im.get('w')}x{im.get('h')} will look soft at 1080x1920"})
    if jpg_bytes > MAX_JPEG_BYTES:
        problems.append({"frame": index, "kind": "jpeg-too-large", "detail": f"{jpg_bytes} bytes > 8 MB"})
    return report, problems


def render(spec_path: Path, out: Path, theme_name: str | None, chrome_path: str | None) -> int:
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    frames = validate_spec(spec)
    theme = load_theme(theme_name or spec.get("theme", "beyond-deploy"))
    chrome = find_chrome(chrome_path)
    if not chrome:
        print("no Chrome/Chromium found (set CARD_NEWS_CHROME)", file=sys.stderr)
        return 1
    out.mkdir(parents=True, exist_ok=True)
    (out / "html").mkdir(exist_ok=True)
    reports, problems = [], []
    with tempfile.TemporaryDirectory(prefix="story-chrome-") as profile:
        for i, frame in enumerate(frames, 1):
            page = build_frame_html(frame, i, len(frames), spec, theme, spec_path.parent)
            html_path = out / "html" / f"{i:02d}.html"
            html_path.write_text(page, encoding="utf-8")
            png_path = out / f"{i:02d}.png"
            probe = render_png(chrome, html_path, png_path, Path(profile))
            # the publishable file never carries the sticker guide: it is a review overlay, not artwork
            if _s(frame.get("sticker")).strip():
                clean = build_frame_html(frame, i, len(frames), spec, theme, spec_path.parent, guide_off=True)
                clean_html = out / "html" / f"{i:02d}-clean.html"
                clean_html.write_text(clean, encoding="utf-8")
                render_png(chrome, clean_html, out / f"{i:02d}-clean.png", Path(profile))
                jpg_bytes = to_jpeg(out / f"{i:02d}-clean.png", out / f"{i:02d}.jpg")
            else:
                jpg_bytes = to_jpeg(png_path, out / f"{i:02d}.jpg")
            rep, probs = qa_frame(i, frame, probe, png_path, jpg_bytes)
            reports.append(rep)
            problems.extend(probs)
            print(f"frame {i:02d}/{len(frames):02d} {frame['type']:<6} {'OK' if not probs else 'QA ' + str(len(probs))}")
    qa = {"frames_total": len(frames), "size": [W, H], "safe": {"top": SAFE_TOP, "bottom": SAFE_BOTTOM},
          "frames": reports, "problems": problems}
    (out / "qa.json").write_text(json.dumps(qa, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n{len(frames)} story frame(s) → {out}  NN.png=review (sticker guide), NN.jpg=publish  problems={len(problems)}  (qa.json)")
    return 2 if problems else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spec", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--theme", default=None, help="theme name (this skill's or make-card-news' themes/) or a .json path")
    ap.add_argument("--chrome", default=None)
    a = ap.parse_args(argv)
    try:
        return render(a.spec, a.out, a.theme, a.chrome)
    except (SpecError, RuntimeError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
