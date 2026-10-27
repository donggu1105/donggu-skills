#!/usr/bin/env python3
"""prepare_story.py — make-story-image 출력 → 스토리 payload 계약.

네트워크·실제 vault 없이 돈다: 노트·qa.json·NN.jpg는 tempfile 폴더, 업로더는 mock.
"""
import contextlib
import datetime
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
import urllib.error
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "skills" / "publish-sns"


def _load(name):
    spec = importlib.util.spec_from_file_location(name, SKILL_DIR / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


MOD = _load("prepare_story")

NOTE_NAME = "Instagram - FDE 해커톤 모집.md"
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def jpeg_bytes(seed):
    return b"\xff\xd8\xff\xe0\x00\x10JFIF\x00" + bytes([seed % 256]) * 8 + b"\xff\xd9"


def note_text(*, account="beyonddeploy", status="published", story_section=True, channel="instagram"):
    return (
        "---\n"
        "type: channel_pack\n"
        f"channel: {channel}\n"
        + (f"account: {account}\n" if account is not None else "")
        + f"status: {status}\n"
        "---\n\n"
        "# FDE 해커톤 모집\n\n"
        "## 장별 카피\n\n![[Attachments/set/01.png]]\n\n"
        "## 캡션\n\n본문.\n\n#FDE\n\n"
        + ("## 스토리\n\n- 01: 모집 공지\n- 02: 링크 스티커 자리\n\n" if story_section else "")
    )


class FixedDateTime(datetime.datetime):
    @classmethod
    def now(cls, tz=None):
        return cls(2026, 10, 28, 9, 8, 7)


class StoryCase(unittest.TestCase):
    ENV = {"SUPABASE_URL": "https://example.supabase.co",
           "SUPABASE_SERVICE_KEY": "sk-test-secret-value-123"}

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name).resolve()
        self.frames = self.root / "story-out"
        self.frames.mkdir()
        self.write_frames(2)
        self.write_qa(2)
        self.note = self.root / NOTE_NAME
        self.note.write_text(note_text(), encoding="utf-8")

    def write_frames(self, count, *, png_at=None):
        for i in range(1, count + 1):
            data = PNG_MAGIC + b"\x00" * 8 if i == png_at else jpeg_bytes(i)
            (self.frames / f"{i:02d}.jpg").write_bytes(data)
            # 검수용 PNG·clean PNG는 발행 프레임으로 세지 않는다.
            (self.frames / f"{i:02d}.png").write_bytes(PNG_MAGIC)
            (self.frames / f"{i:02d}-clean.png").write_bytes(PNG_MAGIC)

    def write_qa(self, total, problems=()):
        (self.frames / "qa.json").write_text(json.dumps({
            "frames_total": total, "size": [1080, 1920],
            "safe": {"top": 250, "bottom": 340}, "frames": [], "problems": list(problems),
        }), encoding="utf-8")

    def run_main(self, *args):
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = MOD.main([str(self.note), "--frames", str(self.frames), *args])
        return code, stdout.getvalue(), stderr.getvalue()

    def upload_run(self, *args, side_effect=None):
        calls = []

        def fake_upload(local_path, key_path, bucket, base_url, service_key):
            calls.append((Path(local_path).name, key_path, bucket))
            if side_effect:
                raise side_effect
            return f"{base_url}/storage/v1/object/public/{bucket}/{key_path}"

        with mock.patch.dict(os.environ, self.ENV), mock.patch.object(
            MOD.blog, "upload", side_effect=fake_upload,
        ), mock.patch("datetime.datetime", FixedDateTime):
            code, out, err = self.run_main(*args)
        return code, out, err, calls


class PrepareStoryTests(StoryCase):
    def test_two_frames_produce_two_payloads_with_topic_suffix(self):
        code, out, err, calls = self.upload_run("--slug", "fdethon")
        self.assertEqual(0, code, err)
        folder = "instagram/2026/10-28/fdethon-story-090807"
        self.assertEqual(
            [("01.jpg", f"{folder}/01.jpg", "sns-media"), ("02.jpg", f"{folder}/02.jpg", "sns-media")],
            calls,
        )
        payloads = json.loads(out)
        self.assertEqual(2, len(payloads))
        public = "https://example.supabase.co/storage/v1/object/public/sns-media/"
        for n, item in enumerate(payloads, 1):
            self.assertEqual({"channel", "operation", "topic", "note_path", "payload"}, set(item))
            self.assertEqual("instagram", item["channel"])
            self.assertEqual("story", item["operation"])
            self.assertEqual(f"FDE 해커톤 모집 (스토리 {n})", item["topic"])
            self.assertEqual(str(self.note), item["note_path"])
            self.assertEqual(
                {"image_url": f"{public}{folder}/{n:02d}.jpg", "account": "beyonddeploy"},
                item["payload"],
            )
        # status: published여도 막지 않고, `## 스토리`가 있으면 경고도 없다.
        self.assertNotIn("no_story_section", err)
        for stream in (out, err):
            self.assertNotIn(self.ENV["SUPABASE_SERVICE_KEY"], stream)

    def test_qa_problems_exit_2(self):
        self.write_qa(2, problems=[{"frame": 1, "kind": "safe-top", "element": "title"}])
        code, out, err, calls = self.upload_run()
        self.assertEqual(2, code)
        self.assertEqual("", out)
        self.assertEqual([], calls)
        self.assertIn("problems", err)

    def test_frame_count_mismatch_exit_2(self):
        self.write_qa(3)
        code, out, _err, calls = self.upload_run()
        self.assertEqual(2, code)
        self.assertEqual("", out)
        self.assertEqual([], calls)

    def test_missing_qa_json_exit_2(self):
        (self.frames / "qa.json").unlink()
        code, _out, _err, calls = self.upload_run()
        self.assertEqual(2, code)
        self.assertEqual([], calls)

    def test_jpg_with_png_bytes_exit_3(self):
        self.write_frames(2, png_at=2)
        code, out, err, calls = self.upload_run()
        self.assertEqual(3, code)
        self.assertEqual("", out)
        self.assertEqual([], calls)
        self.assertIn('"real_format": "PNG"', err)

    def test_account_alias_beyond_deploy(self):
        self.note.write_text(note_text(account="beyond-deploy"), encoding="utf-8")
        code, out, err = self.run_main("--dry-run")
        self.assertEqual(0, code, err)
        self.assertEqual({"beyonddeploy"}, {p["payload"]["account"] for p in json.loads(out)})

    def test_account_missing_or_outside_allowed_exit_2(self):
        for account in (None, "someone"):
            with self.subTest(account=account):
                self.note.write_text(note_text(account=account), encoding="utf-8")
                code, out, _err = self.run_main("--dry-run")
                self.assertEqual(2, code)
                self.assertEqual("", out)
        self.note.write_text(note_text(account="donggu"), encoding="utf-8")
        code, _out, _err = self.run_main("--dry-run", "--account", "beyonddeploy")
        self.assertEqual(2, code)

    def test_frame_option_emits_only_that_frame(self):
        code, out, err, calls = self.upload_run("--slug", "fdethon", "--frame", "2")
        self.assertEqual(0, code, err)
        self.assertEqual([("02.jpg", "instagram/2026/10-28/fdethon-story-090807/02.jpg", "sns-media")], calls)
        payloads = json.loads(out)
        self.assertEqual(1, len(payloads))
        self.assertEqual("FDE 해커톤 모집 (스토리 2)", payloads[0]["topic"])
        for bad in ("0", "3"):
            with self.subTest(frame=bad):
                code, out, _err = self.run_main("--dry-run", "--frame", bad)
                self.assertEqual(2, code)

    def test_dry_run_uses_placeholders_without_env_or_upload(self):
        with mock.patch.object(MOD.blog, "upload") as upload, mock.patch.object(
            MOD.blog, "load_env"
        ) as load_env:
            code, out, err = self.run_main("--dry-run")
        self.assertEqual(0, code, err)
        self.assertEqual(["dry-run://01", "dry-run://02"],
                         [p["payload"]["image_url"] for p in json.loads(out)])
        upload.assert_not_called()
        load_env.assert_not_called()

    def test_missing_story_section_warns_but_proceeds(self):
        self.note.write_text(note_text(story_section=False), encoding="utf-8")
        code, out, err = self.run_main("--dry-run")
        self.assertEqual(0, code, err)
        self.assertEqual(2, len(json.loads(out)))
        self.assertIn('"warning": "no_story_section"', err)

    def test_non_instagram_note_exit_2(self):
        self.note.write_text(note_text(channel="threads"), encoding="utf-8")
        code, _out, _err = self.run_main("--dry-run")
        self.assertEqual(2, code)

    def test_upload_failure_exit_1(self):
        code, out, err, calls = self.upload_run(
            side_effect=urllib.error.URLError("connection refused"),
        )
        self.assertEqual(1, code)
        self.assertEqual("", out)
        self.assertEqual(1, len(calls))
        self.assertNotIn(self.ENV["SUPABASE_SERVICE_KEY"], err)


if __name__ == "__main__":
    unittest.main()
