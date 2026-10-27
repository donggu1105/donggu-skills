"""Contracts for skills/make-story-image.

Pure checks always run. The render check needs a headless Chrome/Chromium and is skipped when none is installed.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "make-story-image"
RENDERER = SKILL / "scripts" / "render_story.py"
sys.path.insert(0, str(SKILL / "scripts"))

import render_story  # noqa: E402


def frame(**kw):
    base = {"type": "hook", "title": "제목", "image": {"src": "assets/room-presenter.jpg"}}
    base.update(kw)
    return base


class PackagingTest(unittest.TestCase):
    def test_skill_files_and_runtime_neutral_wording(self):
        text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        self.assertTrue(text.startswith("---\nname: make-story-image\n"))
        for banned in ("AskUserQuestion", "skill_view(", "MEDIA:", "~/.hermes/profiles"):
            with self.subTest(banned=banned):
                self.assertNotIn(banned, text)
        for rel in ("scripts/render_story.py", "templates/story.html", "examples/sample-story.json",
                    "references/story-spec.md", "references/asset-cleanup.md"):
            self.assertTrue((SKILL / rel).is_file(), rel)

    def test_sample_spec_validates(self):
        spec = json.loads((SKILL / "examples" / "sample-story.json").read_text(encoding="utf-8"))
        frames = render_story.validate_spec(spec)
        self.assertEqual(2, len(frames))
        self.assertEqual("cta", frames[1]["type"])


class SpecValidationTest(unittest.TestCase):
    def test_story_is_1_to_5_frames(self):
        with self.assertRaises(render_story.SpecError):
            render_story.validate_spec({"frames": []})
        with self.assertRaises(render_story.SpecError):
            render_story.validate_spec({"frames": [frame()] * 6})

    def test_urls_and_click_verbs_are_refused_everywhere(self):
        for field, value in (("title", "지금 클릭"), ("body", "beyonddeploy.kr 로"), ("sticker", "https://x.y"),
                             ("kicker", "탭하세요")):
            with self.subTest(field=field):
                with self.assertRaises(render_story.SpecError):
                    render_story.validate_spec({"frames": [frame(**{field: value})]})

    def test_remote_images_are_refused(self):
        with self.assertRaises(render_story.SpecError):
            render_story.validate_spec({"frames": [frame(image={"src": "https://cdn/x.jpg"})]})

    def test_field_limits_cut_words_not_type(self):
        with self.assertRaises(render_story.SpecError):
            render_story.validate_spec({"frames": [frame(title="가" * 41)]})
        render_story.validate_spec({"frames": [frame(title="가" * 20 + "\n" + "나" * 20)]})  # \n not counted

    def test_theme_resolves_from_card_news_themes(self):
        theme = render_story.load_theme("beyond-deploy")
        self.assertEqual("beyond-deploy", theme["name"])

    def test_sticker_frame_builds_review_and_clean_html(self):
        spec = json.loads((SKILL / "examples" / "sample-story.json").read_text(encoding="utf-8"))
        theme = render_story.load_theme("beyond-deploy")
        f = render_story.validate_spec(spec)[1]
        review = render_story.build_frame_html(f, 2, 2, spec, theme, SKILL / "examples")
        clean = render_story.build_frame_html(f, 2, 2, spec, theme, SKILL / "examples", guide_off=True)
        self.assertIn('data-qa="sticker"', review)
        self.assertNotIn('data-qa="sticker"', clean)
        self.assertIn("mode-full", review)


@unittest.skipUnless(render_story.find_chrome(), "headless Chrome not available")
class RenderTest(unittest.TestCase):
    def test_renders_png_jpg_and_qa(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "out"
            proc = subprocess.run([sys.executable, str(RENDERER), str(SKILL / "examples" / "sample-story.json"),
                                   "--out", str(out)], capture_output=True, text=True, timeout=300)
            self.assertIn(proc.returncode, (0, 2), proc.stderr)
            qa = json.loads((out / "qa.json").read_text(encoding="utf-8"))
            self.assertEqual(2, qa["frames_total"])
            self.assertEqual([1080, 1920], qa["size"])
            for i in (1, 2):
                self.assertTrue((out / f"{i:02d}.png").is_file())
                self.assertTrue((out / f"{i:02d}.jpg").is_file())
            self.assertTrue((out / "02-clean.png").is_file(), "sticker frame gets a clean publish render")
            self.assertFalse((out / "01-clean.png").exists())
            self.assertEqual([], qa["problems"], qa["problems"])
            for fr in qa["frames"]:
                self.assertTrue(fr["font_available"])
                self.assertLessEqual(fr["jpeg_bytes"], 8 * 1024 * 1024)


if __name__ == "__main__":
    unittest.main()
