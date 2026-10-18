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


if __name__ == "__main__":
    unittest.main()
