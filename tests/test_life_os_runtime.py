#!/usr/bin/env python3
import importlib.util
from datetime import date
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import threading
import types
import unittest
from unittest import mock
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "donggu-obsidian" / "runtime" / "life_os.py"


def load_module():
    spec = importlib.util.spec_from_file_location("donggu_life_os_runtime", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


life_os = load_module()
LifeOSRuntime = life_os.LifeOSRuntime


class LifeOSRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.vault = self.base / "vault"
        template = self.vault / "Life OS/0. PeriodicNotes/Templates/Daily.md"
        template.parent.mkdir(parents=True)
        template.write_text(
            "## Project List\n<% LifeOS.Project.snapshot() %>\n\n"
            "## Daily Record\n%%Your Record%%\n\n"
            "## Habit\n- [ ] Breakfast\n\n"
            "```LifeOS\nTaskDoneListByTime\n```\n",
            encoding="utf-8",
        )
        self.runtime = LifeOSRuntime(
            vault_root=self.vault,
            state_root=self.base / "state",
            timezone=ZoneInfo("Asia/Seoul"),
            cache_roots=tuple(
                self.base / "cache" / kind for kind in ("images", "audio", "documents")
            ),
            max_attachment_bytes=32 * 1024 * 1024,
        )

    def test_start_daily_renders_known_snapshot_and_preserves_template_blocks(self):
        result = self.runtime.start_daily(date(2026, 8, 7))
        text = Path(result["path"]).read_text(encoding="utf-8")
        self.assertNotIn("<%", text)
        self.assertIn("- [ ] Breakfast", text)
        self.assertIn("```LifeOS\nTaskDoneListByTime\n```", text)
        self.assertIn("<!-- life-os:record:start -->", text)
        self.assertEqual(1, result["next_question"])

    def test_start_daily_rejects_symlinked_year_with_existing_daily(self):
        day = date(2026, 8, 7)
        external_year = self.base / "external-periodic/2026"
        external_daily = external_year / "Daily/08/2026-08-07.md"
        external_daily.parent.mkdir(parents=True)
        original = "## Daily Record\nexternal content\n"
        external_daily.write_text(original, encoding="utf-8")
        (self.vault / "Life OS/0. PeriodicNotes/2026").symlink_to(
            external_year, target_is_directory=True,
        )

        with self.assertRaises(life_os.LifeOSError):
            self.runtime.start_daily(day)

        self.assertEqual(original, external_daily.read_text(encoding="utf-8"))

    def test_status_rejects_missing_life_root_after_runtime_construction(self):
        (self.vault / "Life OS").rename(self.vault / "Life OS removed")

        with self.assertRaises(life_os.LifeOSError):
            self.runtime.status(date(2026, 8, 7))

    def test_start_daily_rejects_template_replaced_by_symlink(self):
        day = date(2026, 8, 7)
        template = self.vault / "Life OS/0. PeriodicNotes/Templates/Daily.md"
        external = self.base / "external-template.md"
        external.write_text("## Daily Record\nexternal template\n", encoding="utf-8")
        template.rename(template.with_name("Daily original.md"))
        template.symlink_to(external)

        with self.assertRaises(life_os.LifeOSError):
            self.runtime.start_daily(day)

        self.assertFalse(self.runtime.daily_path(day).exists())

    def test_record_changes_only_bounded_block(self):
        self.runtime.start_daily(date(2026, 8, 7))
        path = self.runtime.daily_path(date(2026, 8, 7))
        original = path.read_text(encoding="utf-8")
        before, after = original.split("<!-- life-os:record:start -->", 1)
        _block, suffix = after.split("<!-- life-os:record:end -->", 1)
        self.runtime.record(
            "answer", message_text="산책을 했다", message_key="s1:1",
            target_date=date(2026, 8, 7),
        )
        updated = path.read_text(encoding="utf-8")
        self.assertTrue(updated.startswith(before + "<!-- life-os:record:start -->"))
        self.assertTrue(updated.endswith("<!-- life-os:record:end -->" + suffix))
        self.assertIn("산책을 했다", updated)

    def test_questions_followups_pause_resume_and_completion(self):
        day = date(2026, 8, 7)
        self.runtime.start_daily(day)
        first = self.runtime.record(
            "answer", message_text="회의가 길었다", message_key="s1:1",
            follow_up_question="무엇이 가장 힘들었나?", target_date=day,
        )
        self.assertEqual("무엇이 가장 힘들었나?", first["question"])
        second = self.runtime.record(
            "answer", message_text="결정이 계속 바뀐 점", message_key="s1:2",
            target_date=day,
        )
        self.assertEqual(2, second["next_question"])
        paused = self.runtime.record(
            "pause", message_text="그만", message_key="s1:3", target_date=day,
        )
        self.assertEqual("paused", paused["status"])
        resumed = self.runtime.record(
            "resume", message_text="이어서 하자", message_key="s1:4", target_date=day,
        )
        self.assertEqual("active", resumed["status"])
        for index in range(2, 6):
            result = self.runtime.record(
                "answer", message_text=f"답변 {index}", message_key=f"s1:{index + 3}",
                target_date=day,
            )
        self.assertEqual("completed", result["status"])

    def test_capture_appends_timestamped_entry_without_starting_daily(self):
        result = self.runtime.record(
            "capture", message_text="책 아이디어", message_key="s2:1",
            target_date=date(2026, 8, 7),
        )
        text = Path(result["path"]).read_text(encoding="utf-8")
        self.assertIn("# Capture — 2026-08-07", text)
        self.assertIn("책 아이디어", text)
        self.assertFalse(self.runtime.daily_path(date(2026, 8, 7)).exists())

    def test_capture_rejects_symlinked_parent_with_existing_dated_file(self):
        day = date(2026, 8, 7)
        external = self.base / "external-capture"
        external.mkdir()
        external_note = external / f"{day.isoformat()}.md"
        original = "external content\n"
        external_note.write_text(original, encoding="utf-8")
        (self.vault / "Life OS/-1. Capture").symlink_to(external, target_is_directory=True)

        with self.assertRaises(life_os.LifeOSError):
            self.runtime.record(
                "capture", message_text="must not escape", message_key="escape:existing",
                target_date=day,
            )

        self.assertEqual(original, external_note.read_text(encoding="utf-8"))

    def test_capture_rejects_symlinked_parent_without_dated_file(self):
        day = date(2026, 8, 7)
        external = self.base / "external-empty-capture"
        external.mkdir()
        external_note = external / f"{day.isoformat()}.md"
        (self.vault / "Life OS/-1. Capture").symlink_to(external, target_is_directory=True)

        with self.assertRaises(life_os.LifeOSError):
            self.runtime.record(
                "capture", message_text="must not create", message_key="escape:absent",
                target_date=day,
            )

        self.assertFalse(external_note.exists())

    def test_capture_rejects_life_root_replaced_by_symlink(self):
        day = date(2026, 8, 7)
        original_life = self.vault / "Life OS"
        moved_life = self.vault / "Life OS original"
        external = self.base / "external-life"
        external.mkdir()
        original_life.rename(moved_life)
        original_life.symlink_to(external, target_is_directory=True)

        with self.assertRaises(life_os.LifeOSError):
            self.runtime.record(
                "capture", message_text="outside?", message_key="capture:life-swap",
                target_date=day,
            )

        self.assertFalse((external / "-1. Capture").exists())

    def test_capture_rejects_fifo_promptly_without_mutation(self):
        day = date(2026, 8, 7)
        capture_directory = self.vault / "Life OS/-1. Capture"
        capture_directory.mkdir()
        fifo = capture_directory / f"{day.isoformat()}.md"
        os.mkfifo(fifo)
        original_names = tuple(path.name for path in capture_directory.iterdir())
        finished = threading.Event()
        outcome = []

        def record_capture():
            try:
                self.runtime.record(
                    "capture", message_text="must not block", message_key="fifo:1",
                    target_date=day,
                )
            except Exception as exc:
                outcome.append(exc)
            finally:
                finished.set()

        thread = threading.Thread(target=record_capture, daemon=True)
        thread.start()
        completed_promptly = finished.wait(0.2)
        if not completed_promptly:
            writer_fd = os.open(fifo, os.O_WRONLY | os.O_NONBLOCK)
            os.close(writer_fd)
            self.assertTrue(finished.wait(1), "blocked Capture read did not terminate")
        thread.join(1)

        self.assertTrue(completed_promptly, "Capture FIFO open blocked before type validation")
        self.assertEqual(1, len(outcome))
        self.assertIsInstance(outcome[0], life_os.LifeOSError)
        self.assertTrue(stat.S_ISFIFO(fifo.lstat().st_mode))
        self.assertEqual(original_names, tuple(path.name for path in capture_directory.iterdir()))

    def test_followups_are_durable_bounded_and_non_recursive(self):
        day = date(2026, 8, 7)
        self.runtime.start_daily(day)
        with self.assertRaises(life_os.LifeOSError):
            self.runtime.record(
                "answer", message_text="첫 답", message_key="follow:invalid",
                follow_up_question=" " * 10, target_date=day,
            )
        first = self.runtime.record(
            "answer", message_text="첫 답", message_key="follow:1",
            follow_up_question="  첫 꼬리질문?  ", target_date=day,
        )
        self.assertEqual(
            {"for_question": 1, "question": "첫 꼬리질문?"},
            first["pending_follow_up"],
        )
        restored = self.runtime.status(day)
        self.assertEqual(first["pending_follow_up"], restored["pending_follow_up"])
        no_recursion = self.runtime.record(
            "answer", message_text="꼬리 답", message_key="follow:2",
            follow_up_question="이 질문은 생성되지 않음", target_date=day,
        )
        self.assertIsNone(no_recursion["pending_follow_up"])
        self.assertEqual(1, no_recursion["follow_up_count"])

        second = self.runtime.record(
            "answer", message_text="둘째 답", message_key="follow:3",
            follow_up_question="둘째 꼬리질문?", target_date=day,
        )
        self.assertEqual(2, second["follow_up_count"])
        self.runtime.record(
            "skip", message_text="건너뛰기", message_key="follow:4", target_date=day,
        )
        limited = self.runtime.record(
            "answer", message_text="셋째 답", message_key="follow:5",
            follow_up_question="x" * 301, target_date=day,
        )
        self.assertEqual(2, limited["follow_up_count"])
        self.assertIsNone(limited["pending_follow_up"])

    def test_answer_and_skip_cannot_consume_paused_follow_up(self):
        for offset, operation in enumerate(("answer", "skip"), start=7):
            with self.subTest(operation=operation):
                day = date(2026, 8, offset)
                self.runtime.start_daily(day)
                self.runtime.record(
                    "answer", message_text="첫 답", message_key=f"paused:{operation}:answer",
                    follow_up_question="꼬리질문?", target_date=day,
                )
                paused = self.runtime.record(
                    "pause", message_text="그만", message_key=f"paused:{operation}:pause",
                    target_date=day,
                )
                path = self.runtime.daily_path(day)
                original = path.read_text(encoding="utf-8")

                with self.assertRaises(life_os.LifeOSError):
                    self.runtime.record(
                        operation, message_text="일찍 온 답", message_key=f"paused:{operation}:early",
                        target_date=day,
                    )

                self.assertEqual(original, path.read_text(encoding="utf-8"))
                self.assertEqual(paused, self.runtime.status(day))

    def test_skip_and_free_record_preserve_question_progress(self):
        day = date(2026, 8, 7)
        free = self.runtime.record(
            "free_record", message_text="자유 기록", message_key="free:1",
            target_date=day,
        )
        self.assertEqual("not_started", free["status"])
        self.assertEqual(1, free["next_question"])
        text = Path(free["path"]).read_text(encoding="utf-8")
        self.assertIn("— Free Record", text)

        self.runtime.start_daily(day)
        skipped = self.runtime.record(
            "skip", message_text="건너뛰기", message_key="free:2", target_date=day,
        )
        self.assertEqual([1], skipped["skipped"])
        self.assertEqual(2, skipped["next_question"])

    def test_daily_and_capture_message_keys_are_idempotent(self):
        day = date(2026, 8, 7)
        self.runtime.start_daily(day)
        self.runtime.record(
            "answer", message_text="첫 답", message_key="daily:1", target_date=day,
        )
        current = self.runtime.record(
            "answer", message_text="둘째 답", message_key="daily:2", target_date=day,
        )
        duplicate = self.runtime.record(
            "answer", message_text="다른 내용", message_key="daily:1", target_date=day,
        )
        self.assertTrue(duplicate["duplicate"])
        self.assertEqual(current["next_question"], duplicate["next_question"])

        first_capture = self.runtime.record(
            "capture", message_text="첫 캡처", message_key="capture:1", target_date=day,
        )
        self.runtime.record(
            "capture", message_text="둘째 캡처", message_key="capture:2", target_date=day,
        )
        duplicate_capture = self.runtime.record(
            "capture", message_text="다른 내용", message_key="capture:1", target_date=day,
        )
        self.assertTrue(duplicate_capture["duplicate"])
        capture_text = Path(first_capture["path"]).read_text(encoding="utf-8")
        self.assertEqual(1, capture_text.count("첫 캡처"))
        self.assertNotIn("다른 내용", capture_text)

    def test_attachment_numbering_hash_reuse_and_direct_links(self):
        cache = self.base / "cache/documents"
        cache.mkdir(parents=True)
        first = cache / "uuid-report.PDF"
        first.write_bytes(b"same bytes")
        day = date(2026, 8, 7)
        self.runtime.start_daily(day)
        result = self.runtime.record(
            "answer", message_text="첨부했어", message_key="s3:1",
            attachment_paths=[first], target_date=day,
        )
        stored = self.vault / "Life OS/Attachments/A001 - report.pdf"
        self.assertEqual(b"same bytes", stored.read_bytes())
        self.assertIn("[[Life OS/Attachments/A001 - report.pdf]]", Path(result["path"]).read_text())
        duplicate = cache / "another-name.pdf"
        duplicate.write_bytes(b"same bytes")
        self.runtime.record(
            "answer", message_text="같은 파일", message_key="s3:2",
            attachment_paths=[duplicate], target_date=day,
        )
        self.assertEqual([stored], list((self.vault / "Life OS/Attachments").iterdir()))

    def test_status_reports_only_bounded_canonical_attachment_references(self):
        cache = self.base / "cache/documents"
        cache.mkdir(parents=True)
        source = cache / "uuid-status.pdf"
        source.write_bytes(b"status attachment")
        day = date(2026, 8, 7)
        self.runtime.start_daily(day)

        recorded = self.runtime.record(
            "answer", message_text="첨부", message_key="status:attachment",
            attachment_paths=[source], target_date=day,
        )
        expected = ["[[Life OS/Attachments/A001 - status.pdf]]"]
        self.assertEqual(expected, recorded.get("attachments"))

        path = self.runtime.daily_path(day)
        path.write_text(
            path.read_text(encoding="utf-8")
            + "\noutside [[Life OS/Attachments/A999 - outside.pdf]]\n",
            encoding="utf-8",
        )
        self.assertEqual(expected, self.runtime.status(day).get("attachments"))

    def test_empty_and_noncanonical_attachment_references_are_not_reported(self):
        day = date(2026, 8, 7)
        self.assertEqual([], self.runtime.status(day).get("attachments"))
        self.runtime.start_daily(day)
        path = self.runtime.daily_path(day)
        text = path.read_text(encoding="utf-8")
        path.write_text(
            text.replace(
                "### Daily Check-in\n\n",
                "### Daily Check-in\n\n[[Life OS/Attachments/A1 - bad.pdf]]\n",
            ),
            encoding="utf-8",
        )
        self.assertEqual([], self.runtime.status(day).get("attachments"))

    def test_runtime_accepts_explicit_temporary_attachment_policy(self):
        roots = (self.base / "explicit-cache/documents",)
        runtime = LifeOSRuntime(
            vault_root=self.vault,
            state_root=self.base / "explicit-state",
            timezone=ZoneInfo("Asia/Seoul"),
            cache_roots=roots,
            max_attachment_bytes=1234,
        )
        self.assertEqual(roots, runtime.cache_roots)
        self.assertEqual(1234, runtime.max_attachment_bytes)

    def test_default_attachment_policy_uses_canonical_legacy_cache_at_record_time(self):
        legacy = self.base / "legacy_document_cache"
        legacy.mkdir()
        source = legacy / "uuid-legacy.pdf"
        source.write_bytes(b"legacy")
        calls = []

        def get_hermes_dir(new_subpath, old_name):
            calls.append((new_subpath, old_name))
            return legacy if new_subpath == "cache/documents" else self.base / new_subpath

        module = types.SimpleNamespace(get_hermes_dir=get_hermes_dir)
        with mock.patch.dict(sys.modules, {"hermes_constants": module}):
            runtime = LifeOSRuntime(
                vault_root=self.vault,
                state_root=self.base / "legacy-state",
                timezone=ZoneInfo("Asia/Seoul"),
            )
            day = date(2026, 8, 7)
            runtime.start_daily(day)
            runtime.record(
                "answer", message_text="legacy", message_key="legacy:1",
                attachment_paths=[source], target_date=day,
            )

        self.assertEqual(
            [
                ("cache/images", "image_cache"),
                ("cache/audio", "audio_cache"),
                ("cache/documents", "document_cache"),
            ],
            calls,
        )
        self.assertEqual(
            b"legacy",
            (self.vault / "Life OS/Attachments/A001 - legacy.pdf").read_bytes(),
        )

    def test_default_attachment_policy_tracks_active_profile_change_at_record_time(self):
        first_cache = self.base / "profiles/first/cache/documents"
        second_cache = self.base / "profiles/second/cache/documents"
        first_cache.mkdir(parents=True)
        second_cache.mkdir(parents=True)
        first = first_cache / "uuid-first.pdf"
        second = second_cache / "uuid-second.pdf"
        first.write_bytes(b"first")
        second.write_bytes(b"second")
        active = {"documents": first_cache}

        def get_hermes_dir(new_subpath, old_name):
            del old_name
            kind = new_subpath.rsplit("/", 1)[-1]
            return active.get(kind, self.base / "profiles/first" / new_subpath)

        module = types.SimpleNamespace(get_hermes_dir=get_hermes_dir)
        with mock.patch.dict(sys.modules, {"hermes_constants": module}):
            runtime = LifeOSRuntime(
                vault_root=self.vault,
                state_root=self.base / "profile-state",
                timezone=ZoneInfo("Asia/Seoul"),
            )
            day = date(2026, 8, 7)
            runtime.start_daily(day)
            runtime.record(
                "answer", message_text="first", message_key="profile:1",
                attachment_paths=[first], target_date=day,
            )
            active["documents"] = second_cache
            runtime.record(
                "answer", message_text="second", message_key="profile:2",
                attachment_paths=[second], target_date=day,
            )

        self.assertEqual(
            ["A001 - first.pdf", "A002 - second.pdf"],
            sorted(path.name for path in runtime.attachments_root.iterdir()),
        )

    def test_rejects_symlink_cache_path_and_preserves_pending_question(self):
        outside = self.base / "outside.pdf"
        outside.write_bytes(b"secret")
        cache = self.base / "cache/documents"
        cache.mkdir(parents=True)
        link = cache / "link.pdf"
        link.symlink_to(outside)
        day = date(2026, 8, 7)
        self.runtime.start_daily(day)
        with self.assertRaisesRegex(life_os.LifeOSError, "cache attachment"):
            self.runtime.record(
                "answer", message_text="첨부", message_key="s4:1",
                attachment_paths=[link], target_date=day,
            )
        self.assertEqual(1, self.runtime.status(day)["next_question"])

    def test_attachment_cache_type_size_and_path_validation_is_fail_closed(self):
        cache = self.base / "cache/documents"
        cache.mkdir(parents=True)
        outside = self.base / "outside.pdf"
        outside.write_bytes(b"outside")
        oversized = cache / "large.pdf"
        oversized.write_bytes(b"12345")
        fifo = cache / "pipe.pdf"
        os.mkfifo(fifo)
        self.runtime.max_attachment_bytes = 4
        day = date(2026, 8, 7)
        self.runtime.start_daily(day)

        for index, source in enumerate((outside, oversized, fifo), start=1):
            with self.subTest(source=source.name):
                with self.assertRaisesRegex(life_os.LifeOSError, "cache attachment"):
                    self.runtime.record(
                        "answer", message_text="invalid", message_key=f"security:{index}",
                        attachment_paths=[source], target_date=day,
                    )
                self.assertEqual(1, self.runtime.status(day)["next_question"])
        self.assertFalse((self.vault / "Life OS/Attachments").exists())

    def test_attachment_rejects_file_swapped_to_symlink_before_descriptor_open(self):
        cache = self.base / "cache/documents"
        cache.mkdir(parents=True)
        source = cache / "uuid-race.pdf"
        outside = self.base / "outside-race.pdf"
        source.write_bytes(b"same bytes")
        outside.write_bytes(b"same bytes")
        day = date(2026, 8, 7)
        self.runtime.start_daily(day)
        real_open = life_os.os.open
        swapped = False

        def swap_file_before_open(path, flags, *args, **kwargs):
            nonlocal swapped
            if path == source.name and kwargs.get("dir_fd") is not None and not swapped:
                source.unlink()
                source.symlink_to(outside)
                swapped = True
            return real_open(path, flags, *args, **kwargs)

        with mock.patch.object(life_os.os, "open", side_effect=swap_file_before_open):
            with self.assertRaisesRegex(life_os.LifeOSError, "cache attachment"):
                self.runtime.record(
                    "answer", message_text="race", message_key="race:1",
                    attachment_paths=[source], target_date=day,
                )
        self.assertTrue(swapped)
        self.assertEqual(1, self.runtime.status(day)["next_question"])
        attachments = self.vault / "Life OS/Attachments"
        self.assertFalse(attachments.exists() and any(attachments.iterdir()))

    def test_attachment_rejects_parent_traversal_spelled_under_cache_root(self):
        cache = self.base / "cache/documents"
        cache.mkdir(parents=True)
        outside = self.base / "outside-traversal.pdf"
        outside.write_bytes(b"outside")
        traversal = cache / ".." / ".." / outside.name
        day = date(2026, 8, 7)
        self.runtime.start_daily(day)

        with self.assertRaisesRegex(life_os.LifeOSError, "cache attachment"):
            self.runtime.record(
                "answer", message_text="traversal", message_key="traversal:1",
                attachment_paths=[traversal], target_date=day,
            )
        self.assertEqual(1, self.runtime.status(day)["next_question"])

    def test_attachment_rejects_intermediate_cache_parent_swapped_to_symlink(self):
        cache = self.base / "cache/documents"
        nested = cache / "nested"
        nested.mkdir(parents=True)
        source = nested / "uuid-nested.pdf"
        source.write_bytes(b"trusted bytes")
        outside = self.base / "outside-cache"
        outside.mkdir()
        (outside / source.name).write_bytes(b"outside bytes")
        moved = cache / "original-nested"
        real_open = life_os.os.open
        swapped = False

        def swap_parent_before_open(path, flags, *args, **kwargs):
            nonlocal swapped
            if path == "nested" and kwargs.get("dir_fd") is not None and not swapped:
                nested.rename(moved)
                nested.symlink_to(outside, target_is_directory=True)
                swapped = True
            return real_open(path, flags, *args, **kwargs)

        day = date(2026, 8, 7)
        self.runtime.start_daily(day)
        with mock.patch.object(life_os.os, "open", side_effect=swap_parent_before_open):
            with self.assertRaisesRegex(life_os.LifeOSError, "cache attachment"):
                self.runtime.record(
                    "answer", message_text="nested", message_key="nested-race:1",
                    attachment_paths=[source], target_date=day,
                )

        self.assertTrue(swapped)
        self.assertEqual(1, self.runtime.status(day)["next_question"])
        attachments = self.vault / "Life OS/Attachments"
        self.assertFalse(attachments.exists() and any(attachments.iterdir()))

    def test_attachment_name_is_sanitized_and_conflicting_destination_is_rejected(self):
        cache = self.base / "cache/documents"
        cache.mkdir(parents=True)
        source = cache / "uuid-Quarter\nReport: Q3.PDF"
        source.write_bytes(b"quarterly")
        day = date(2026, 8, 7)
        self.runtime.start_daily(day)
        self.runtime.record(
            "answer", message_text="report", message_key="name:1",
            attachment_paths=[source], target_date=day,
        )
        stored = self.vault / "Life OS/Attachments/A001 - Quarter Report Q3.pdf"
        self.assertEqual(b"quarterly", stored.read_bytes())

        conflict_source = cache / "uuid-other.txt"
        conflict_source.write_bytes(b"other")
        conflict = self.vault / "Life OS/Attachments/A002 - other.txt"
        conflict.write_bytes(b"occupied")
        with mock.patch.object(self.runtime, "_next_attachment_number", return_value=2):
            with self.assertRaises(life_os.LifeOSError):
                self.runtime.record(
                    "answer", message_text="conflict", message_key="name:2",
                    attachment_paths=[conflict_source], target_date=day,
                )
        self.assertEqual(b"occupied", conflict.read_bytes())
        self.assertEqual(2, self.runtime.status(day)["next_question"])

    def test_attachment_name_removes_obsidian_wikilink_delimiters(self):
        cache = self.base / "cache/documents"
        cache.mkdir(parents=True)
        source = cache / "uuid-Quarter]]#Report^Q3|alias.PDF"
        source.write_bytes(b"safe link")
        day = date(2026, 8, 7)
        self.runtime.start_daily(day)

        result = self.runtime.record(
            "answer", message_text="safe", message_key="wikilink:1",
            attachment_paths=[source], target_date=day,
        )

        stored = self.vault / "Life OS/Attachments/A001 - Quarter Report Q3 alias.pdf"
        self.assertEqual(b"safe link", stored.read_bytes())
        text = Path(result["path"]).read_text(encoding="utf-8")
        self.assertIn("[[Life OS/Attachments/A001 - Quarter Report Q3 alias.pdf]]", text)
        self.assertNotIn("#Report", text)

    def test_attachment_write_rejects_life_root_replaced_by_symlink(self):
        cache = self.base / "cache/documents"
        cache.mkdir(parents=True)
        source = cache / "uuid-escape.pdf"
        source.write_bytes(b"must stay")
        day = date(2026, 8, 7)
        self.runtime.start_daily(day)
        external = self.base / "external-life"
        (self.vault / "Life OS").rename(external)
        (self.vault / "Life OS").symlink_to(external, target_is_directory=True)

        with self.assertRaises(life_os.LifeOSError):
            self.runtime.record(
                "answer", message_text="escape", message_key="ancestor:1",
                attachment_paths=[source], target_date=day,
            )

        attachments = external / "Attachments"
        self.assertFalse(attachments.exists() and any(attachments.iterdir()))

    def test_attachment_publish_never_replaces_racing_conflict(self):
        cache = self.base / "cache/documents"
        cache.mkdir(parents=True)
        source = cache / "uuid-conflict.pdf"
        source.write_bytes(b"new bytes")
        day = date(2026, 8, 7)
        self.runtime.start_daily(day)
        destination = self.vault / "Life OS/Attachments/A001 - conflict.pdf"
        real_link = life_os.os.link

        def occupy_then_link(source_name, destination_name, *args, **kwargs):
            destination.parent.mkdir(exist_ok=True)
            destination.write_bytes(b"racing bytes")
            return real_link(source_name, destination_name, *args, **kwargs)

        with mock.patch.object(life_os.os, "link", side_effect=occupy_then_link):
            with self.assertRaises(life_os.LifeOSError):
                self.runtime.record(
                    "answer", message_text="conflict", message_key="conflict:race",
                    attachment_paths=[source], target_date=day,
                )

        self.assertEqual(b"racing bytes", destination.read_bytes())
        self.assertEqual(1, self.runtime.status(day)["next_question"])

    def test_attachment_rename_crash_is_recovered_by_hash_on_retry(self):
        cache = self.base / "cache/documents"
        cache.mkdir(parents=True)
        source = cache / "uuid-crash.pdf"
        source.write_bytes(b"recover me")
        day = date(2026, 8, 7)
        self.runtime.start_daily(day)
        failed = False

        def fail_after_attachment_rename(source_path, destination_path, *args, **kwargs):
            nonlocal failed
            result = real_link(source_path, destination_path, *args, **kwargs)
            if not failed:
                failed = True
                raise OSError("injected post-attachment-rename crash")
            return result

        real_link = life_os.os.link
        with mock.patch.object(life_os.os, "link", side_effect=fail_after_attachment_rename):
            with self.assertRaises(life_os.LifeOSError):
                self.runtime.record(
                    "answer", message_text="first try", message_key="crash:attachment",
                    attachment_paths=[source], target_date=day,
                )
        self.assertEqual(1, self.runtime.status(day)["next_question"])

        retry = cache / "uuid-retry.pdf"
        retry.write_bytes(b"recover me")
        result = self.runtime.record(
            "answer", message_text="first try", message_key="crash:attachment",
            attachment_paths=[retry], target_date=day,
        )
        attachment_names = [path.name for path in self.runtime.attachments_root.iterdir()]
        self.assertEqual(["A001 - crash.pdf"], attachment_names)
        text = Path(result["path"]).read_text(encoding="utf-8")
        self.assertEqual(1, text.count("[[Life OS/Attachments/A001 - crash.pdf]]"))
        self.assertFalse(any(name.startswith(".life-os-") for name in attachment_names))

    def test_note_rename_crash_reuses_attachment_and_commits_once_on_retry(self):
        cache = self.base / "cache/documents"
        cache.mkdir(parents=True)
        source = cache / "uuid-note-crash.pdf"
        source.write_bytes(b"note recovery")
        day = date(2026, 8, 7)
        self.runtime.start_daily(day)
        note_path = self.runtime.daily_path(day)
        original = note_path.read_text(encoding="utf-8")
        real_replace = life_os.os.replace

        def fail_before_note_rename(source_path, destination_path, *args, **kwargs):
            if destination_path == note_path.name and kwargs.get("dst_dir_fd") is not None:
                raise OSError("injected pre-note-rename crash")
            return real_replace(source_path, destination_path, *args, **kwargs)

        with mock.patch.object(life_os.os, "replace", side_effect=fail_before_note_rename):
            with self.assertRaises(life_os.LifeOSError):
                self.runtime.record(
                    "answer", message_text="note try", message_key="crash:note",
                    attachment_paths=[source], target_date=day,
                )
        self.assertEqual(original, note_path.read_text(encoding="utf-8"))

        result = self.runtime.record(
            "answer", message_text="note try", message_key="crash:note",
            attachment_paths=[source], target_date=day,
        )
        self.assertEqual(["A001 - note-crash.pdf"], [path.name for path in self.runtime.attachments_root.iterdir()])
        text = Path(result["path"]).read_text(encoding="utf-8")
        self.assertEqual(1, text.count("%% life-os-message: crash:note %%"))
        self.assertEqual(1, text.count("[[Life OS/Attachments/A001 - note-crash.pdf]]"))

    def test_concurrent_records_are_serialized_with_sequential_attachments(self):
        cache = self.base / "cache/documents"
        cache.mkdir(parents=True)
        sources = []
        for index in range(8):
            source = cache / f"uuid-item-{index}.txt"
            source.write_bytes(f"attachment {index}".encode())
            sources.append(source)
        day = date(2026, 8, 7)
        self.runtime.start_daily(day)
        barrier = threading.Barrier(8)
        errors = []

        def record(index):
            try:
                barrier.wait()
                self.runtime.record(
                    "free_record", message_text=f"concurrent {index}",
                    message_key=f"thread:{index}", attachment_paths=[sources[index]],
                    target_date=day,
                )
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=record, args=(index,)) for index in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(5)

        self.assertFalse(any(thread.is_alive() for thread in threads))
        self.assertEqual([], errors)
        text = self.runtime.daily_path(day).read_text(encoding="utf-8")
        for index in range(8):
            self.assertEqual(1, text.count(f"%% life-os-message: thread:{index} %%"))
        state_match = life_os._STATE_PATTERN.search(text)
        self.assertIsNotNone(state_match)
        json.loads(state_match.group(1))
        numbers = sorted(
            int(path.name.split(" ", 1)[0][1:]) for path in self.runtime.attachments_root.iterdir()
        )
        self.assertEqual(list(range(1, 9)), numbers)

    def test_target_date_prefers_unfinished_yesterday_until_today_starts(self):
        class FixedDateTime(life_os.datetime):
            @classmethod
            def now(cls, tz=None):
                return cls(2026, 8, 7, 12, 0, tzinfo=tz)

        yesterday = date(2026, 8, 6)
        today = date(2026, 8, 7)
        self.runtime.start_daily(yesterday)
        with mock.patch.object(life_os, "datetime", FixedDateTime):
            self.assertEqual(yesterday, self.runtime.resolve_target_date())
            self.assertEqual(yesterday.isoformat(), self.runtime.status()["date"])
            self.assertEqual(yesterday, self.runtime.resolve_target_date("yesterday"))
            self.runtime.start_daily(today)
            self.assertEqual(today, self.runtime.resolve_target_date())

    def test_completed_yesterday_is_not_reopened_implicitly(self):
        class FixedDateTime(life_os.datetime):
            @classmethod
            def now(cls, tz=None):
                return cls(2026, 8, 7, 12, 0, tzinfo=tz)

        yesterday = date(2026, 8, 6)
        self.runtime.start_daily(yesterday)
        for index in range(1, 6):
            self.runtime.record(
                "answer", message_text=f"답 {index}", message_key=f"complete:{index}",
                target_date=yesterday,
            )
        with mock.patch.object(life_os, "datetime", FixedDateTime):
            self.assertEqual(date(2026, 8, 7), self.runtime.resolve_target_date())

    def test_runtime_and_environment_reject_non_kst_timezones_without_creating_state(self):
        direct_state = self.base / "direct-state"
        with self.assertRaises(life_os.LifeOSError):
            LifeOSRuntime(
                vault_root=self.vault,
                state_root=direct_state,
                timezone=ZoneInfo("UTC"),
            )
        self.assertFalse(direct_state.exists())

        environment_state = self.base / "environment-state"
        with mock.patch.dict(os.environ, {
            "DONGGU_LIFE_OS_VAULT_ROOT": str(self.vault),
            "DONGGU_LIFE_OS_STATE_ROOT": str(environment_state),
            "DONGGU_LIFE_OS_TIMEZONE": "UTC",
        }, clear=False):
            with self.assertRaises(life_os.LifeOSError):
                LifeOSRuntime.from_environment()
        self.assertFalse(environment_state.exists())

    def test_status_rejects_noncontiguous_active_and_paused_progress(self):
        day = date(2026, 8, 7)
        self.runtime.start_daily(day)
        path = self.runtime.daily_path(day)
        original = path.read_text(encoding="utf-8")
        state_match = life_os._STATE_PATTERN.search(original)
        self.assertIsNotNone(state_match)

        invalid_states = (
            {"status": "active", "next_question": 1, "answered": [2], "skipped": []},
            {"status": "paused", "next_question": 3, "answered": [1], "skipped": []},
            {"status": "active", "next_question": 3, "answered": [1, 2], "skipped": [2]},
        )
        for updates in invalid_states:
            with self.subTest(updates=updates):
                payload = json.loads(state_match.group(1))
                payload.update(updates)
                raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
                tampered = original[:state_match.start(1)] + raw + original[state_match.end(1):]
                path.write_text(tampered, encoding="utf-8")
                with self.assertRaises(life_os.LifeOSError):
                    self.runtime.status(day)
                path.write_text(original, encoding="utf-8")

    def test_status_rejects_boolean_follow_up_question_reference(self):
        day = date(2026, 8, 7)
        self.runtime.start_daily(day)
        self.runtime.record(
            "answer", message_text="첫 답", message_key="tamper:1",
            follow_up_question="꼬리질문?", target_date=day,
        )
        path = self.runtime.daily_path(day)
        original = path.read_text(encoding="utf-8")
        state_match = life_os._STATE_PATTERN.search(original)
        self.assertIsNotNone(state_match)
        payload = json.loads(state_match.group(1))
        payload["pending_follow_up"]["for_question"] = True
        raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        path.write_text(
            original[:state_match.start(1)] + raw + original[state_match.end(1):],
            encoding="utf-8",
        )
        with self.assertRaises(life_os.LifeOSError):
            self.runtime.status(day)

    def test_existing_state_root_requires_private_mode_and_current_owner_without_chmod(self):
        permissive = self.base / "permissive-state"
        permissive.mkdir(mode=0o755)
        os.chmod(permissive, 0o755)
        with self.assertRaises(life_os.LifeOSError):
            LifeOSRuntime(
                vault_root=self.vault,
                state_root=permissive,
                timezone=ZoneInfo("Asia/Seoul"),
            )
        self.assertEqual(0o755, permissive.stat().st_mode & 0o777)

        foreign = self.base / "foreign-state"
        foreign.mkdir(mode=0o700)
        os.chmod(foreign, 0o700)
        with mock.patch.object(life_os.os, "geteuid", return_value=os.geteuid() + 1):
            with self.assertRaises(life_os.LifeOSError):
                LifeOSRuntime(
                    vault_root=self.vault,
                    state_root=foreign,
                    timezone=ZoneInfo("Asia/Seoul"),
                )
        self.assertEqual(0o700, foreign.stat().st_mode & 0o777)

    def test_existing_private_state_root_is_accepted_unchanged(self):
        self.assertEqual(0o700, self.runtime.state_root.stat().st_mode & 0o777)
        private = self.base / "private-state"
        private.mkdir(mode=0o700)
        os.chmod(private, 0o700)
        runtime = LifeOSRuntime(
            vault_root=self.vault,
            state_root=private,
            timezone=ZoneInfo("Asia/Seoul"),
        )
        self.assertEqual(private, runtime.state_root)
        self.assertEqual(0o700, private.stat().st_mode & 0o777)

    def test_lock_uses_canonical_vault_digest_namespace_and_private_modes(self):
        expected_name = hashlib.sha256(
            os.path.realpath(self.vault).encode("utf-8")
        ).hexdigest()
        namespace = self.runtime.state_root / expected_name
        self.assertEqual(namespace, self.runtime.state_namespace)
        self.assertRegex(namespace.name, r"^[0-9a-f]{64}$")
        self.assertEqual(0o700, namespace.stat().st_mode & 0o777)

        self.runtime.status(date(2026, 8, 7))
        lock = namespace / "mutation.lock"
        self.assertEqual(0o600, lock.stat().st_mode & 0o777)
        self.assertEqual(b"", lock.read_bytes())
        self.assertNotIn(self.vault.name, str(lock.relative_to(self.runtime.state_root)))

    def test_shared_state_base_separates_vault_lock_namespaces(self):
        other_vault = self.base / "other-vault"
        template = other_vault / "Life OS/0. PeriodicNotes/Templates/Daily.md"
        template.parent.mkdir(parents=True)
        template.write_text("## Daily Record\n%%Your Record%%\n", encoding="utf-8")
        other = LifeOSRuntime(
            vault_root=other_vault,
            state_root=self.runtime.state_root,
            timezone=ZoneInfo("Asia/Seoul"),
        )

        self.assertNotEqual(self.runtime.state_namespace, other.state_namespace)
        self.assertEqual(self.runtime.state_root, other.state_root)
        self.assertTrue(self.runtime.state_namespace.is_dir())
        self.assertTrue(other.state_namespace.is_dir())

    def test_existing_lock_namespace_must_be_private_owned_directory(self):
        state_base = self.base / "namespace-state"
        state_base.mkdir(mode=0o700)
        os.chmod(state_base, 0o700)
        digest = hashlib.sha256(os.path.realpath(self.vault).encode("utf-8")).hexdigest()
        namespace = state_base / digest
        namespace.mkdir(mode=0o755)
        os.chmod(namespace, 0o755)

        with self.assertRaises(life_os.LifeOSError):
            LifeOSRuntime(
                vault_root=self.vault,
                state_root=state_base,
                timezone=ZoneInfo("Asia/Seoul"),
            )
        self.assertEqual(0o755, namespace.stat().st_mode & 0o777)

    def test_lock_namespace_rejects_symlink_and_foreign_owner(self):
        digest = hashlib.sha256(os.path.realpath(self.vault).encode("utf-8")).hexdigest()

        symlink_base = self.base / "symlink-namespace-state"
        symlink_base.mkdir(mode=0o700)
        os.chmod(symlink_base, 0o700)
        external = self.base / "external-namespace"
        external.mkdir(mode=0o700)
        (symlink_base / digest).symlink_to(external, target_is_directory=True)
        with self.assertRaises(life_os.LifeOSError):
            LifeOSRuntime(
                vault_root=self.vault,
                state_root=symlink_base,
                timezone=ZoneInfo("Asia/Seoul"),
            )

        foreign_base = self.base / "foreign-namespace-state"
        foreign_base.mkdir(mode=0o700)
        os.chmod(foreign_base, 0o700)
        foreign_namespace = foreign_base / digest
        foreign_namespace.mkdir(mode=0o700)
        os.chmod(foreign_namespace, 0o700)
        owner = os.geteuid()
        with mock.patch.object(life_os.os, "geteuid", side_effect=(owner, owner + 1)):
            with self.assertRaises(life_os.LifeOSError):
                LifeOSRuntime(
                    vault_root=self.vault,
                    state_root=foreign_base,
                    timezone=ZoneInfo("Asia/Seoul"),
                )

    def test_state_root_rejects_paths_canonically_nested_under_vault_without_creation(self):
        internal = self.vault / "Life OS/.state"
        with self.assertRaises(life_os.LifeOSError):
            LifeOSRuntime(
                vault_root=self.vault,
                state_root=internal,
                timezone=ZoneInfo("Asia/Seoul"),
            )
        self.assertFalse(internal.exists())

        alias = self.base / "vault-alias"
        alias.symlink_to(self.vault, target_is_directory=True)
        aliased_internal = alias / "Life OS/.aliased-state"
        with self.assertRaises(life_os.LifeOSError):
            LifeOSRuntime(
                vault_root=self.vault,
                state_root=aliased_internal,
                timezone=ZoneInfo("Asia/Seoul"),
            )
        self.assertFalse((self.vault / "Life OS/.aliased-state").exists())

    def test_state_root_rejects_canonical_vault_root_without_chmod(self):
        os.chmod(self.vault, 0o700)
        before_mode = self.vault.stat().st_mode & 0o777
        with self.assertRaises(life_os.LifeOSError):
            LifeOSRuntime(
                vault_root=self.vault,
                state_root=self.vault,
                timezone=ZoneInfo("Asia/Seoul"),
            )
        self.assertEqual(before_mode, self.vault.stat().st_mode & 0o777)

    def test_state_root_rejects_case_variant_vault_alias_without_creation(self):
        case_variant_vault = self.vault.with_name(self.vault.name.upper())
        try:
            same_vault = os.path.samefile(case_variant_vault, self.vault)
        except FileNotFoundError:
            same_vault = False
        if not same_vault:
            self.skipTest("temporary test filesystem is case-sensitive")

        internal = case_variant_vault / "Life OS/.case-alias-state"
        actual_internal = self.vault / "Life OS/.case-alias-state"
        self.assertFalse(actual_internal.exists())
        with self.assertRaises(life_os.LifeOSError):
            LifeOSRuntime(
                vault_root=self.vault,
                state_root=internal,
                timezone=ZoneInfo("Asia/Seoul"),
            )
        self.assertFalse(actual_internal.exists())

    def test_state_root_rejects_external_symlink_to_case_variant_inner_vault_without_creation(self):
        case_variant_vault = self.vault.with_name(self.vault.name.upper())
        try:
            same_vault = os.path.samefile(case_variant_vault, self.vault)
        except FileNotFoundError:
            same_vault = False
        if not same_vault:
            self.skipTest("temporary test filesystem is case-sensitive")

        alias = self.base / "case-inner-alias"
        alias.symlink_to(case_variant_vault / "Life OS", target_is_directory=True)
        requested = alias / ".state"
        actual_internal = self.vault / "Life OS/.state"
        self.assertFalse(actual_internal.exists())
        with self.assertRaises(life_os.LifeOSError):
            LifeOSRuntime(
                vault_root=self.vault,
                state_root=requested,
                timezone=ZoneInfo("Asia/Seoul"),
            )
        self.assertFalse(actual_internal.exists())


if __name__ == "__main__":
    unittest.main()
