"""Contracts for donggu-docs:make-card-news.

Pure checks always run. The render check needs a headless Chrome/Chromium and is
skipped when none is installed (the renderer itself reports that case clearly).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "donggu-docs"
SKILL = PACKAGE / "skills" / "make-card-news"
RENDERER = SKILL / "scripts" / "render_cards.py"
sys.path.insert(0, str(SKILL / "scripts"))

import render_cards  # noqa: E402  (imported after sys.path tweak)


def manifest_scalar(path: Path, key: str) -> str:
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith(f"{key}:"):
            return line.split(":", 1)[1].strip().strip('"')
    raise AssertionError(f"{key} missing in {path}")


class PackagingTest(unittest.TestCase):
    def test_skill_files_and_runtime_neutral_wording(self):
        text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        self.assertTrue(text.startswith("---\nname: make-card-news\n"))
        for banned in ("AskUserQuestion", "skill_view(", "MEDIA:", "~/.hermes/profiles"):
            with self.subTest(banned=banned):
                self.assertNotIn(banned, text)
        for required in (
            SKILL / "scripts" / "render_cards.py",
            SKILL / "templates" / "card.html",
            SKILL / "themes" / "beyond-deploy.json",
            SKILL / "themes" / "donggu.json",
            SKILL / "references" / "card-spec.md",
            SKILL / "references" / "platform-specs.md",
            SKILL / "references" / "tool-landscape.md",
            SKILL / "examples" / "sample-bd.json",
        ):
            with self.subTest(path=required.relative_to(ROOT)):
                self.assertTrue(required.is_file())

    def test_docs_plugin_version_bumped_everywhere(self):
        claude = json.loads((PACKAGE / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
        marketplace = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
        entry = next(item for item in marketplace["plugins"] if item["name"] == "donggu-docs")
        self.assertEqual(claude["version"], entry["version"])
        self.assertEqual("1.2.0", claude["version"])
        readme = (PACKAGE / "README.md").read_text(encoding="utf-8")
        self.assertIn("skills-2", readme)
        self.assertIn("make-card-news", readme)
        root_readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("donggu-docs:make-card-news", root_readme)
        self.assertIn("v1.2.0", root_readme)

    def test_sns_package_still_free_of_card_news(self):
        # The SNS domain retired its card-news skill on purpose; the new skill lives in docs.
        for path in (PACKAGE.parent / "donggu-sns").rglob("*.md"):
            self.assertNotIn("make-card-news", path.read_text(encoding="utf-8"), path)


class SpecAndHtmlTest(unittest.TestCase):
    def setUp(self):
        self.spec = json.loads((SKILL / "examples" / "sample-bd.json").read_text(encoding="utf-8"))
        self.theme = render_cards.load_theme("beyond-deploy", SKILL)

    def test_sample_spec_validates_and_covers_every_card_type(self):
        cards = render_cards.validate_spec(self.spec)
        self.assertGreaterEqual(len(cards), 5)
        self.assertEqual({c["type"] for c in cards}, set(render_cards.CARD_TYPES))

    def test_validate_rejects_unknown_type_and_missing_fields(self):
        with self.assertRaises(render_cards.SpecError):
            render_cards.validate_spec({"cards": [{"type": "hero", "title": "x"}]})
        with self.assertRaises(render_cards.SpecError):
            render_cards.validate_spec({"cards": [{"type": "point", "title": "제목만"}]})
        with self.assertRaises(render_cards.SpecError):
            render_cards.validate_spec({"cards": []})
        with self.assertRaises(render_cards.SpecError):  # stat needs value + label
            render_cards.validate_spec({"cards": [{"type": "stat", "value": "100"}]})
        with self.assertRaises(render_cards.SpecError):  # one number per slide: value must be short
            render_cards.validate_spec({"cards": [{"type": "stat", "value": "1,234,567,890", "label": "x"}]})

    def test_stat_card_markup_puts_number_first_and_names_the_source(self):
        card = {"type": "stat", "kicker": "케이스 토크 4회차 동안", "value": "100", "unit": "여 명",
                "label": "FDE와 AX 실무자를 만났습니다", "context": "첫 모임은 두 FDE의 사례로 시작했습니다.",
                "source": "beyonddeploy.kr 필드노트"}
        html = render_cards.build_card_html(card, index=3, total=8, spec=self.spec, theme=self.theme)
        self.assertIn('class="stat"', html)
        self.assertLess(html.index('data-qa="value"'), html.index('data-qa="label"'))
        self.assertIn('data-qa="source"', html)
        self.assertIn("type-stat", html)
        # label is headline-sized: it shares the .title size token, not the body one
        self.assertRegex(html, r"\.stat-label\s*\{[^}]*font-size:\s*var\(--title-size\)")

    def test_html_escapes_and_keeps_korean_word_breaks(self):
        card = {"type": "point", "title": "<script>x</script>", "body": "줄1\n**강조**"}
        html = render_cards.build_card_html(card, index=1, total=3, spec=self.spec, theme=self.theme)
        self.assertNotIn("<script>x</script>", html)
        self.assertIn("&lt;script&gt;", html)
        self.assertIn("<br>", html)
        self.assertIn("<strong", html)
        self.assertIn("word-break: keep-all", html)
        self.assertIn("1080px", html)
        self.assertIn("1350px", html)
        self.assertIn("01 / 03", html)
        self.assertIn(self.theme["accent"], html)
        self.assertIn('data-qa-result', html)  # QA probe script is embedded

    def test_sample_uses_images_in_every_mode_and_ships_the_files(self):
        cards = render_cards.validate_spec(self.spec)
        modes = {c["image"].get("mode", "band") for c in cards if c.get("image")}
        self.assertTrue({"full", "band"} <= modes, modes)
        spec_dir = SKILL / "examples"
        for c in cards:
            if c.get("image"):
                p = render_cards.resolve_image(c["image"]["src"], spec_dir)
                self.assertTrue(p.is_file(), p)
                self.assertLess(p.stat().st_size, 400_000, f"{p.name}: keep sample photos small")
                self.assertTrue(c["image"].get("alt"), f"{c['type']}: image needs alt text")

    def test_image_spec_validation(self):
        base = {"type": "point", "title": "t", "body": "b"}
        for bad in (
            {"src": "x.gif"},                        # unsupported extension
            {"src": "x.jpg", "mode": "hero"},        # unknown mode
            {"src": "x.jpg", "zoom": 3},             # zoom out of range
            {"src": "x.jpg", "fade": 1.5},           # fade out of range
            "assets/x.jpg",                          # must be an object
        ):
            with self.assertRaises(render_cards.SpecError, msg=bad):
                render_cards.validate_spec({"cards": [dict(base, image=bad)]})
        with self.assertRaises(render_cards.SpecError):  # compare takes no inline image
            render_cards.validate_spec({"cards": [{"type": "compare", "title": "t",
                "left": {"title": "a", "body": "b"}, "right": {"title": "c", "body": "d"},
                "image": {"src": "x.jpg", "mode": "inline"}}]})
        with self.assertRaises(render_cards.SpecError):  # URLs are not fetched
            render_cards.resolve_image("https://example.com/a.jpg", SKILL)
        with self.assertRaises(render_cards.SpecError):  # missing file
            render_cards.resolve_image("assets/does-not-exist.jpg", SKILL / "examples")

    def test_image_modes_render_to_distinct_markup(self):
        img = SKILL / "examples" / "assets" / "lounge-wide.jpg"
        for mode, needle in (("full", 'class="bg"'), ("band", 'class="band"'), ("inline", 'class="inline-img"')):
            card = {"type": "point", "title": "t", "body": "b",
                    "image": {"src": str(img), "mode": mode, "focus": "30% 40%", "overlay": 0.8, "zoom": 1.2}}
            html = render_cards.build_card_html(card, index=1, total=1, spec=self.spec, theme=self.theme,
                                                spec_dir=SKILL / "examples")
            self.assertIn(needle, html, mode)
            self.assertIn(f"mode-{mode}", html)
            self.assertIn("--focus: 30% 40%", html)
            self.assertIn("--zoom: 1.2", html)
            self.assertIn(img.as_uri(), html)  # file:// so Chrome can load it without a server
            self.assertIn('data-qa-img', html)  # probe reports load state
        plain = render_cards.build_card_html({"type": "point", "title": "t", "body": "b"},
                                             index=1, total=1, spec=self.spec, theme=self.theme)
        self.assertIn("mode-text", plain)
        self.assertNotIn("<img", plain)  # no spec_dir → no wash either; relative src must never leak into HTML
        no_bd = dict(self.spec); no_bd.pop("backdrop", None)
        plain2 = render_cards.build_card_html({"type": "point", "title": "t", "body": "b"},
                                              index=1, total=1, spec=no_bd, theme=self.theme, spec_dir=SKILL / "examples")
        self.assertNotIn("<img", plain2)

    def test_backdrop_wash_ties_text_and_band_cards_to_the_cover(self):
        img = SKILL / "examples" / "assets" / "lounge-wide.jpg"
        spec = dict(self.spec, backdrop={"src": str(img), "tint": 0.84})
        # text card: set-level backdrop becomes a blurred wash behind the content
        text = render_cards.build_card_html({"type": "point", "title": "t", "body": "b"},
                                            index=1, total=1, spec=spec, theme=self.theme, spec_dir=SKILL / "examples")
        self.assertIn('class="wash"', text)
        self.assertIn('data-qa-img="wash"', text)
        self.assertRegex(text, r'<div class="card [^"]*has-wash')
        self.assertIn("--wash-tint: 0.84", text)
        # band card: wash comes from its own photo so the band dissolves into itself
        other = SKILL / "examples" / "assets" / "lounge-close.jpg"
        band = render_cards.build_card_html({"type": "point", "title": "t", "body": "b",
                                             "image": {"src": str(other), "mode": "band"}},
                                            index=1, total=1, spec=spec, theme=self.theme, spec_dir=SKILL / "examples")
        self.assertIn('class="band"', band)
        self.assertEqual(band.count(other.as_uri()), 2, "band photo should appear as band and as wash")
        self.assertNotIn(img.as_uri(), band)
        # full-bleed card: no wash (the cover look is untouched)
        full = render_cards.build_card_html({"type": "cover", "title": "t",
                                             "image": {"src": str(other), "mode": "full"}},
                                            index=1, total=1, spec=spec, theme=self.theme, spec_dir=SKILL / "examples")
        self.assertNotIn('class="wash"', full)
        self.assertNotRegex(full, r'<div class="card [^"]*has-wash')
        # per-card opt-out
        bare = render_cards.build_card_html({"type": "point", "title": "t", "body": "b", "wash": False},
                                            index=1, total=1, spec=spec, theme=self.theme, spec_dir=SKILL / "examples")
        self.assertNotIn('class="wash"', bare)
        # sample ships with a backdrop so the set is continuous out of the box
        self.assertIn("backdrop", self.spec)
        with self.assertRaises(render_cards.SpecError):
            render_cards.validate_spec({"backdrop": {"src": "x.gif"}, "cards": [{"type": "point", "title": "t", "body": "b"}]})


class RenderTest(unittest.TestCase):
    def setUp(self):
        self.chrome = render_cards.find_chrome(os.environ.get("CARD_NEWS_CHROME"))
        if not self.chrome:
            self.skipTest("no headless Chrome/Chromium available")

    def test_renders_png_set_pdf_and_qa_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out"
            proc = subprocess.run(
                [sys.executable, str(RENDERER), str(SKILL / "examples" / "sample-bd.json"),
                 "--out", str(out), "--theme", "beyond-deploy"],
                capture_output=True, text=True, timeout=240,
            )
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            pngs = sorted(out.glob("[0-9][0-9].png"))
            spec = json.loads((SKILL / "examples" / "sample-bd.json").read_text(encoding="utf-8"))
            self.assertEqual(len(pngs), len(spec["cards"]))
            self.assertTrue((out / "cards.pdf").is_file())
            self.assertEqual(len(sorted((out / "html").glob("*.html"))), len(pngs))
            qa = json.loads((out / "qa.json").read_text(encoding="utf-8"))
            self.assertEqual(qa["cards_total"], len(pngs))
            self.assertEqual(qa["problems"], [], qa)
            self.assertTrue(qa["cards"][0]["font_available"], qa["cards"][0])
            try:
                from PIL import Image
            except ImportError:  # pragma: no cover
                return
            with Image.open(pngs[0]) as im:
                self.assertEqual(im.size, (1080, 1350))

    def test_overflowing_body_is_reported_and_exit_code_2(self):
        spec = {
            "theme": "beyond-deploy",
            "handle": "@test",
            "cards": [
                {"type": "point", "title": "넘침 테스트", "body": "가나다라 마바사 " * 120},
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            spec_path = Path(tmp) / "spec.json"
            spec_path.write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
            out = Path(tmp) / "out"
            proc = subprocess.run(
                [sys.executable, str(RENDERER), str(spec_path), "--out", str(out), "--no-pdf"],
                capture_output=True, text=True, timeout=120,
            )
            self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
            qa = json.loads((out / "qa.json").read_text(encoding="utf-8"))
            self.assertTrue(any(p["kind"] == "overflow" for p in qa["problems"]), qa)

    def test_broken_image_is_reported_not_silently_blank(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "bad.jpg"
            bad.write_bytes(b"not really a jpeg")
            spec = {"theme": "beyond-deploy", "handle": "@test", "cards": [
                {"type": "point", "title": "이미지 깨짐", "body": "본문", "image": {"src": "bad.jpg", "mode": "band"}}]}
            spec_path = Path(tmp) / "spec.json"
            spec_path.write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
            out = Path(tmp) / "out"
            proc = subprocess.run([sys.executable, str(RENDERER), str(spec_path), "--out", str(out), "--no-pdf"],
                                  capture_output=True, text=True, timeout=120)
            self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
            qa = json.loads((out / "qa.json").read_text(encoding="utf-8"))
            self.assertTrue(any(p["kind"] == "image" for p in qa["problems"]), qa)


if __name__ == "__main__":
    unittest.main()
