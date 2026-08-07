#!/usr/bin/env python3
import importlib.util
from datetime import date
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
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

    def test_new_note_publish_uses_exclusive_rename_without_unlink(self):
        directory = self.base / "publish-order"
        directory.mkdir()
        directory_fd = os.open(directory, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        self.addCleanup(os.close, directory_fd)
        events = []
        real_rename = life_os._exclusive_rename_at
        real_unlink = life_os.os.unlink
        real_fsync = life_os.os.fsync

        def tracked_rename(*args, **kwargs):
            result = real_rename(*args, **kwargs)
            events.append("exclusive-rename")
            return result

        def tracked_unlink(*args, **kwargs):
            events.append("unlink")
            return real_unlink(*args, **kwargs)

        def tracked_fsync(descriptor):
            if descriptor == directory_fd:
                events.append("fsync-directory")
            return real_fsync(descriptor)

        with mock.patch.object(life_os, "_exclusive_rename_at", side_effect=tracked_rename), \
             mock.patch.object(life_os.os, "unlink", side_effect=tracked_unlink), \
             mock.patch.object(life_os.os, "fsync", side_effect=tracked_fsync):
            self.runtime._atomic_publish_note_at(directory_fd, "note.md", "bytes\n", None)

        self.assertEqual(["exclusive-rename", "fsync-directory"], events)

    def test_new_daily_hard_death_after_exclusive_rename_is_idempotent_on_retry(self):
        day = date(2026, 8, 7)
        child = (
            "import importlib.util, os, pathlib, sys\n"
            "module_path, vault, state = map(pathlib.Path, sys.argv[1:])\n"
            "spec = importlib.util.spec_from_file_location('child_daily_crash', module_path)\n"
            "module = importlib.util.module_from_spec(spec)\n"
            "sys.modules[spec.name] = module\n"
            "spec.loader.exec_module(module)\n"
            "runtime = module.LifeOSRuntime(vault_root=vault, state_root=state, "
            "timezone=module.ZoneInfo('Asia/Seoul'), cache_roots=(), "
            "max_attachment_bytes=1024)\n"
            "real_rename = module._exclusive_rename_at\n"
            "def die_after_rename(*args, **kwargs):\n"
            "    real_rename(*args, **kwargs)\n"
            "    os._exit(74)\n"
            "module._exclusive_rename_at = die_after_rename\n"
            "runtime.start_daily(module.date(2026, 8, 7))\n"
        )
        proc = subprocess.run(
            [
                sys.executable, "-c", child, str(MODULE_PATH), str(self.vault),
                str(self.base / "state"),
            ],
            text=True, capture_output=True, check=False,
        )
        self.assertEqual(74, proc.returncode, proc.stderr)
        path = self.runtime.daily_path(day)
        self.assertIn("- [ ] Breakfast", path.read_text(encoding="utf-8"))
        self.assertFalse(any(name.startswith(f".{path.name}.life-os-") for name in os.listdir(path.parent)))

        result = self.runtime.start_daily(day)

        text = Path(result["path"]).read_text(encoding="utf-8")
        self.assertIn("- [ ] Breakfast", text)
        self.assertEqual(1, text.count("<!-- life-os:record:start -->"))
        self.assertFalse(any(name.startswith(f".{path.name}.life-os-") for name in os.listdir(path.parent)))

    def test_concurrent_new_daily_creation_is_never_replaced(self):
        day = date(2026, 8, 7)
        path = self.runtime.daily_path(day)
        competing = "## Daily Record\n외부에서 먼저 만든 Daily\n"
        real_rename = life_os._exclusive_rename_at
        injected = False

        def occupy_before_rename(directory_fd, source, destination):
            nonlocal injected
            if not injected and destination == path.name:
                injected = True
                path.write_text(competing, encoding="utf-8")
            return real_rename(directory_fd, source, destination)

        with mock.patch.object(
            life_os, "_exclusive_rename_at", side_effect=occupy_before_rename,
        ):
            with self.assertRaisesRegex(life_os.LifeOSError, "temporary note"):
                self.runtime.start_daily(day)

        text = path.read_text(encoding="utf-8")
        self.assertTrue(injected)
        self.assertIn("외부에서 먼저 만든 Daily", text)
        self.assertTrue(any(name.startswith(f".{path.name}.life-os-") for name in os.listdir(path.parent)))

    def test_external_daily_edit_before_commit_is_replayed_on_newest_document(self):
        day = date(2026, 8, 7)
        path = self.runtime.daily_path(day)
        self.runtime.start_daily(day)
        outside = "\n외부 편집: 회의 메모\n"
        real_snapshot = life_os.LifeOSRuntime._read_text_snapshot_at
        injected = False
        reads = 0

        def edit_before_validation(directory_fd, name, **kwargs):
            nonlocal injected, reads
            if name == path.name:
                reads += 1
            if not injected and name == path.name and reads == 2:
                injected = True
                path.write_text(path.read_text(encoding="utf-8") + outside, encoding="utf-8")
            return real_snapshot(directory_fd, name, **kwargs)

        with mock.patch.object(
            life_os.LifeOSRuntime, "_read_text_snapshot_at", side_effect=edit_before_validation,
        ):
            result = self.runtime.record(
                "answer", message_text="산책했다", message_key="race:daily", target_date=day,
            )

        text = Path(result["path"]).read_text(encoding="utf-8")
        self.assertTrue(injected)
        self.assertIn(outside.strip(), text)
        self.assertEqual(1, text.count("%% life-os-message: race:daily %%"))

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

    def test_sensitive_message_policy_rejects_daily_and_capture_without_mutation(self):
        day = date(2026, 8, 7)
        self.runtime.start_daily(day)
        daily = self.runtime.daily_path(day)
        original = daily.read_bytes()
        capture = self.runtime.capture_path(day)
        sensitive = (
            "<@" + "123456789" + "012345678>",
            "123456789" + "012345678",
            "https://media." + "discordapp.net/attachments/file.txt",
            "/tmp/profile/.hermes/" + "cache/audio/file.ogg",
            "/Users/" + "example/private.txt",
            "/home/" + "example/private.txt",
            "C:\\" + "Users\\example\\private.txt",
            "sk-" + "a" * 32,
            "ghp_" + "b" * 36,
            "AKIA" + "C" * 16,
            "Bearer " + "d" * 32,
            "password=" + "e" * 32,
            "DISCORD_BOT_" + "TOKEN=" + "f" * 32,
            "-----BEGIN " + "OPENSSH PRIVATE KEY-----",
        )

        for index, value in enumerate(sensitive):
            with self.subTest(surface="daily", value=value):
                with self.assertRaisesRegex(life_os.LifeOSError, "sensitive"):
                    self.runtime.record(
                        "free_record", message_text="내 답 " + value,
                        message_key=f"sensitive:daily:{index}", target_date=day,
                    )
                self.assertEqual(original, daily.read_bytes())
            with self.subTest(surface="capture", value=value):
                with self.assertRaisesRegex(life_os.LifeOSError, "sensitive"):
                    self.runtime.record(
                        "capture", message_text="내 답 " + value,
                        message_key=f"sensitive:capture:{index}", target_date=day,
                    )
                self.assertFalse(capture.exists())

    def test_message_policy_allows_ordinary_numbers_and_non_discord_urls(self):
        day = date(2026, 8, 7)
        self.runtime.start_daily(day)
        text = "자연수 123456과 https://example.com/report를 기록"
        result = self.runtime.record(
            "free_record", message_text=text, message_key="ordinary:1", target_date=day,
        )
        self.assertIn(text, Path(result["path"]).read_text(encoding="utf-8"))

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

    def test_resume_is_explicitly_idempotent_while_already_active(self):
        day = date(2026, 8, 7)
        self.runtime.start_daily(day)
        first = self.runtime.record(
            "resume", message_text="이어서 하자", message_key="resume:active", target_date=day,
        )
        second = self.runtime.record(
            "resume", message_text="이어서 하자", message_key="resume:active", target_date=day,
        )
        self.assertEqual("active", first["status"])
        self.assertTrue(second["duplicate"])
        text = self.runtime.daily_path(day).read_text(encoding="utf-8")
        self.assertEqual(1, text.count("%% life-os-message: resume:active %%"))

    def test_explicit_start_resumes_paused_daily_without_resetting_progress(self):
        day = date(2026, 8, 7)
        self.runtime.start_daily(day)
        self.runtime.record(
            "answer", message_text="첫 답", message_key="start-resume:answer", target_date=day,
        )
        self.runtime.record(
            "pause", message_text="그만", message_key="start-resume:pause", target_date=day,
        )
        resumed = self.runtime.start_daily(day, resume=True)
        self.assertEqual("active", resumed["status"])
        self.assertEqual(2, resumed["next_question"])

    def test_question_five_follow_up_keeps_active_until_follow_up_is_committed(self):
        day = date(2026, 8, 7)
        self.runtime.start_daily(day)
        for index in range(1, 5):
            self.runtime.record(
                "answer", message_text=f"답변 {index}", message_key=f"q5:{index}",
                target_date=day,
            )
        fifth = self.runtime.record(
            "answer", message_text="내일은 마무리", message_key="q5:5",
            follow_up_question="첫 행동은 무엇인가?", target_date=day,
        )
        self.assertEqual("active", fifth["status"])
        self.assertEqual("첫 행동은 무엇인가?", fifth["question"])
        self.assertIsNotNone(fifth["pending_follow_up"])

        completed = self.runtime.record(
            "answer", message_text="문서를 연다", message_key="q5:follow", target_date=day,
        )
        self.assertEqual("completed", completed["status"])
        self.assertIsNone(completed["pending_follow_up"])
        self.assertIsNone(completed["question"])
        text = self.runtime.daily_path(day).read_text(encoding="utf-8")
        self.assertEqual(1, text.count("문서를 연다"))

    def test_capture_appends_timestamped_entry_without_starting_daily(self):
        result = self.runtime.record(
            "capture", message_text="책 아이디어", message_key="s2:1",
            target_date=date(2026, 8, 7),
        )
        text = Path(result["path"]).read_text(encoding="utf-8")
        self.assertIn("# Capture — 2026-08-07", text)
        self.assertIn("책 아이디어", text)
        self.assertFalse(self.runtime.daily_path(date(2026, 8, 7)).exists())

    def test_new_capture_hard_death_after_exclusive_rename_is_idempotent_on_retry(self):
        day = date(2026, 8, 7)
        child = (
            "import importlib.util, os, pathlib, sys\n"
            "module_path, vault, state = map(pathlib.Path, sys.argv[1:])\n"
            "spec = importlib.util.spec_from_file_location('child_capture_crash', module_path)\n"
            "module = importlib.util.module_from_spec(spec)\n"
            "sys.modules[spec.name] = module\n"
            "spec.loader.exec_module(module)\n"
            "runtime = module.LifeOSRuntime(vault_root=vault, state_root=state, "
            "timezone=module.ZoneInfo('Asia/Seoul'), cache_roots=(), "
            "max_attachment_bytes=1024)\n"
            "real_rename = module._exclusive_rename_at\n"
            "def die_after_rename(*args, **kwargs):\n"
            "    real_rename(*args, **kwargs)\n"
            "    os._exit(75)\n"
            "module._exclusive_rename_at = die_after_rename\n"
            "runtime.record('capture', message_text='충돌 뒤에도 남을 캡처', "
            "message_key='crash:capture-note', target_date=module.date(2026, 8, 7))\n"
        )
        proc = subprocess.run(
            [
                sys.executable, "-c", child, str(MODULE_PATH), str(self.vault),
                str(self.base / "state"),
            ],
            text=True, capture_output=True, check=False,
        )
        self.assertEqual(75, proc.returncode, proc.stderr)
        path = self.runtime.capture_path(day)
        self.assertIn("충돌 뒤에도 남을 캡처", path.read_text(encoding="utf-8"))
        self.assertFalse(any(name.startswith(f".{path.name}.life-os-") for name in os.listdir(path.parent)))

        result = self.runtime.record(
            "capture", message_text="충돌 뒤에도 남을 캡처",
            message_key="crash:capture-note", target_date=day,
        )

        text = Path(result["path"]).read_text(encoding="utf-8")
        self.assertIn("충돌 뒤에도 남을 캡처", text)
        self.assertEqual(1, text.count("%% life-os-message: crash:capture-note %%"))
        self.assertFalse(any(name.startswith(f".{path.name}.life-os-") for name in os.listdir(path.parent)))

    def test_note_temp_reconciliation_fails_closed_on_unlinked_temp(self):
        day = date(2026, 8, 7)
        directory = self.runtime.daily_path(day).parent
        directory.mkdir(parents=True)
        temp = directory / f".{day.isoformat()}.md.life-os-{'a' * 16}"
        temp.write_text("arbitrary user bytes\n", encoding="utf-8")
        temp.chmod(0o600)

        with self.assertRaisesRegex(life_os.LifeOSError, "temporary note"):
            self.runtime.status(day)

        self.assertEqual("arbitrary user bytes\n", temp.read_text(encoding="utf-8"))

    def test_linked_note_temp_is_retained_for_manual_recovery(self):
        day = date(2026, 8, 7)
        path = self.runtime.daily_path(day)
        path.parent.mkdir(parents=True)
        path.write_text("## Daily Record\ncanonical user bytes\n", encoding="utf-8")
        path.chmod(0o600)
        temp = path.parent / f".{path.name}.life-os-{'b' * 16}"
        os.link(path, temp)
        with self.assertRaisesRegex(life_os.LifeOSError, "temporary note"):
            self.runtime.status(day)

        self.assertEqual("## Daily Record\ncanonical user bytes\n", path.read_text(encoding="utf-8"))
        self.assertEqual("## Daily Record\ncanonical user bytes\n", temp.read_text(encoding="utf-8"))

    def test_status_and_date_resolution_normalize_repeated_concurrent_reads(self):
        day = date(2026, 8, 7)
        self.runtime.start_daily(day)
        for operation in (
            lambda: self.runtime.status(day),
            self.runtime.resolve_target_date,
        ):
            with self.subTest(operation=operation):
                with mock.patch.object(
                    self.runtime, "_read_daily_snapshot",
                    side_effect=life_os._ConcurrentMutation(),
                ):
                    with self.assertRaisesRegex(life_os.LifeOSError, "changed concurrently"):
                        operation()

    def test_concurrent_new_capture_creation_is_never_replaced(self):
        day = date(2026, 8, 7)
        path = self.runtime.capture_path(day)
        competing = f"# Capture — {day.isoformat()}\n\n외부 선행 캡처\n"
        real_rename = life_os._exclusive_rename_at
        injected = False

        def occupy_before_rename(directory_fd, source, destination):
            nonlocal injected
            if not injected and destination == path.name:
                injected = True
                path.write_text(competing, encoding="utf-8")
            return real_rename(directory_fd, source, destination)

        with mock.patch.object(
            life_os, "_exclusive_rename_at", side_effect=occupy_before_rename,
        ):
            with self.assertRaisesRegex(life_os.LifeOSError, "temporary note"):
                self.runtime.record(
                    "capture", message_text="내 캡처", message_key="race:capture:new", target_date=day,
                )

        text = path.read_text(encoding="utf-8")
        self.assertTrue(injected)
        self.assertIn("외부 선행 캡처", text)
        self.assertTrue(any(name.startswith(f".{path.name}.life-os-") for name in os.listdir(path.parent)))

    def test_external_capture_append_before_commit_is_replayed_on_newest_document(self):
        day = date(2026, 8, 7)
        first = self.runtime.record(
            "capture", message_text="첫 캡처", message_key="race:capture:first", target_date=day,
        )
        path = Path(first["path"])
        outside = "외부에서 추가한 캡처\n"
        real_snapshot = life_os.LifeOSRuntime._read_text_snapshot_at
        injected = False
        reads = 0

        def edit_before_validation(directory_fd, name, **kwargs):
            nonlocal injected, reads
            if name == path.name:
                reads += 1
            if not injected and name == path.name and reads == 2:
                injected = True
                path.write_text(path.read_text(encoding="utf-8") + outside, encoding="utf-8")
            return real_snapshot(directory_fd, name, **kwargs)

        with mock.patch.object(
            life_os.LifeOSRuntime, "_read_text_snapshot_at", side_effect=edit_before_validation,
        ):
            result = self.runtime.record(
                "capture", message_text="둘째 캡처", message_key="race:capture:second", target_date=day,
            )

        text = Path(result["path"]).read_text(encoding="utf-8")
        self.assertTrue(injected)
        self.assertIn(outside.strip(), text)
        self.assertEqual(1, text.count("%% life-os-message: race:capture:second %%"))

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
        real_rename = life_os._exclusive_rename_at

        def occupy_then_rename(directory_fd, source_name, destination_name):
            destination.parent.mkdir(exist_ok=True)
            destination.write_bytes(b"racing bytes")
            return real_rename(directory_fd, source_name, destination_name)

        with mock.patch.object(
            life_os, "_exclusive_rename_at", side_effect=occupy_then_rename,
        ):
            with self.assertRaises(life_os.LifeOSError):
                self.runtime.record(
                    "answer", message_text="conflict", message_key="conflict:race",
                    attachment_paths=[source], target_date=day,
                )

        self.assertEqual(b"racing bytes", destination.read_bytes())
        self.assertEqual(1, self.runtime.status(day)["next_question"])

    def test_attachment_publish_uses_exclusive_rename_without_unlink(self):
        source = self.base / "attachment-order.bin"
        source.write_bytes(b"attachment order")
        descriptor = os.open(source, os.O_RDONLY)
        self.addCleanup(os.close, descriptor)
        destination = self.runtime.attachments_root / "A001 - order.bin"
        events = []
        directory_fd = None
        real_rename = life_os._exclusive_rename_at
        real_unlink = life_os.os.unlink
        real_fsync = life_os.os.fsync

        def tracked_rename(*args, **kwargs):
            nonlocal directory_fd
            result = real_rename(*args, **kwargs)
            directory_fd = args[0]
            events.append("exclusive-rename")
            return result

        def tracked_unlink(*args, **kwargs):
            events.append("unlink")
            return real_unlink(*args, **kwargs)

        def tracked_fsync(value):
            if directory_fd is not None and value == directory_fd:
                events.append("fsync-directory")
            return real_fsync(value)

        with mock.patch.object(life_os, "_exclusive_rename_at", side_effect=tracked_rename), \
             mock.patch.object(life_os.os, "unlink", side_effect=tracked_unlink), \
             mock.patch.object(life_os.os, "fsync", side_effect=tracked_fsync):
            self.runtime._atomic_copy_verified(
                descriptor, destination, hashlib.sha256(b"attachment order").hexdigest(),
            )

        self.assertEqual(["exclusive-rename", "fsync-directory"], events)

    def test_attachment_post_rename_fsync_failure_has_no_residual_temp(self):
        source = self.base / "attachment-fsync-failure.bin"
        source.write_bytes(b"recover after directory fsync failure")
        descriptor = os.open(source, os.O_RDONLY)
        self.addCleanup(os.close, descriptor)
        destination = self.runtime.attachments_root / "A001 - recover.bin"
        directory_fd = None
        real_rename = life_os._exclusive_rename_at
        real_fsync = life_os.os.fsync

        def tracked_rename(*args, **kwargs):
            nonlocal directory_fd
            result = real_rename(*args, **kwargs)
            directory_fd = args[0]
            return result

        def fail_first_directory_fsync(value):
            if directory_fd is not None and value == directory_fd:
                raise OSError("injected directory fsync failure")
            return real_fsync(value)

        with mock.patch.object(life_os, "_exclusive_rename_at", side_effect=tracked_rename), \
             mock.patch.object(life_os.os, "fsync", side_effect=fail_first_directory_fsync):
            with self.assertRaises(life_os.LifeOSError):
                self.runtime._atomic_copy_verified(
                    descriptor,
                    destination,
                    hashlib.sha256(b"recover after directory fsync failure").hexdigest(),
                )

        self.assertEqual([destination.name], [path.name for path in self.runtime.attachments_root.iterdir()])
        self.assertEqual(b"recover after directory fsync failure", destination.read_bytes())

    def test_unlinked_attachment_temp_is_retained_for_manual_recovery(self):
        attachments = self.runtime.attachments_root
        attachments.mkdir()
        temp = attachments / (".life-os-attachment-" + "d" * 16)
        temp.write_bytes(b"arbitrary attachment bytes")
        temp.chmod(0o600)

        with self.assertRaisesRegex(life_os.LifeOSError, "temporary attachment"):
            self.runtime._reconcile_attachment_temps()

        self.assertEqual(b"arbitrary attachment bytes", temp.read_bytes())

    def test_linked_attachment_temp_is_retained_for_manual_recovery(self):
        attachments = self.runtime.attachments_root
        attachments.mkdir()
        canonical = attachments / "A001 - canonical.bin"
        canonical.write_bytes(b"canonical attachment bytes")
        canonical.chmod(0o600)
        temp = attachments / (".life-os-attachment-" + "e" * 16)
        os.link(canonical, temp)
        with self.assertRaisesRegex(life_os.LifeOSError, "temporary attachment"):
            self.runtime._reconcile_attachment_temps()

        self.assertEqual(b"canonical attachment bytes", canonical.read_bytes())
        self.assertEqual(b"canonical attachment bytes", temp.read_bytes())

    def test_attachment_recovery_path_replacement_is_never_automatically_unlinked(self):
        attachments = self.runtime.attachments_root
        attachments.mkdir()
        canonical = attachments / "A001 - canonical.bin"
        canonical.write_bytes(b"canonical attachment bytes")
        canonical.chmod(0o600)
        temp = attachments / (".life-os-attachment-" + "e" * 16)
        os.link(canonical, temp)
        unrelated = b"unrelated attachment replacement"
        real_unlink = life_os.os.unlink
        replaced = False

        def replace_at_final_unlink(name, *args, **kwargs):
            nonlocal replaced
            if str(name).startswith(".life-os-recovery-") and not replaced:
                replaced = True
                real_unlink(name, *args, **kwargs)
                (attachments / str(name)).write_bytes(unrelated)
                (attachments / str(name)).chmod(0o600)
            return real_unlink(name, *args, **kwargs)

        with mock.patch.object(life_os.os, "unlink", side_effect=replace_at_final_unlink):
            with self.assertRaisesRegex(life_os.LifeOSError, "temporary attachment"):
                self.runtime._reconcile_attachment_temps()

        residuals = [
            path for path in attachments.iterdir()
            if path.name.startswith((".life-os-attachment-", ".life-os-recovery-"))
        ]
        self.assertTrue(residuals)
        if replaced:
            self.assertTrue(any(path.read_bytes() == unrelated for path in residuals))

    def test_recovery_temp_is_retained_for_manual_recovery(self):
        attachments = self.runtime.attachments_root
        attachments.mkdir()
        recovery = attachments / (".life-os-recovery-" + "f" * 16)
        recovery.write_bytes(b"manual recovery bytes")
        recovery.chmod(0o600)

        with self.assertRaisesRegex(life_os.LifeOSError, "temporary attachment"):
            self.runtime._reconcile_attachment_temps()

        self.assertEqual(b"manual recovery bytes", recovery.read_bytes())

    def test_attachment_rename_crash_is_recovered_by_hash_on_retry(self):
        cache = self.base / "cache/documents"
        cache.mkdir(parents=True)
        source = cache / "uuid-crash.pdf"
        source.write_bytes(b"recover me")
        day = date(2026, 8, 7)
        self.runtime.start_daily(day)
        failed = False

        def fail_after_attachment_rename(directory_fd, source_path, destination_path):
            nonlocal failed
            result = real_rename(directory_fd, source_path, destination_path)
            if not failed:
                failed = True
                raise OSError("injected post-attachment-rename crash")
            return result

        real_rename = life_os._exclusive_rename_at
        with mock.patch.object(
            life_os, "_exclusive_rename_at", side_effect=fail_after_attachment_rename,
        ):
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

    def test_attachment_hard_process_death_after_exclusive_rename_is_idempotent_on_retry(self):
        cache = self.base / "cache/documents"
        cache.mkdir(parents=True)
        source = cache / "uuid-hard-crash.pdf"
        source.write_bytes(b"hard crash recovery")
        day = date(2026, 8, 7)
        self.runtime.start_daily(day)
        child = (
            "import importlib.util, os, pathlib, sys\n"
            "module_path, vault, state, cache, source = map(pathlib.Path, sys.argv[1:])\n"
            "spec = importlib.util.spec_from_file_location('child_life_os', module_path)\n"
            "module = importlib.util.module_from_spec(spec)\n"
            "sys.modules[spec.name] = module\n"
            "spec.loader.exec_module(module)\n"
            "runtime = module.LifeOSRuntime(vault_root=vault, state_root=state, "
            "timezone=module.ZoneInfo('Asia/Seoul'), cache_roots=(cache,), "
            "max_attachment_bytes=32 * 1024 * 1024)\n"
            "real_rename = module._exclusive_rename_at\n"
            "def die_after_rename(*args, **kwargs):\n"
            "    real_rename(*args, **kwargs)\n"
            "    os._exit(73)\n"
            "module._exclusive_rename_at = die_after_rename\n"
            "runtime.record('answer', message_text='first try', "
            "message_key='crash:hard-process', attachment_paths=(source,), "
            "target_date=module.date(2026, 8, 7))\n"
        )
        proc = subprocess.run(
            [
                sys.executable, "-c", child, str(MODULE_PATH), str(self.vault),
                str(self.base / "state"), str(cache), str(source),
            ],
            text=True, capture_output=True, check=False,
        )
        self.assertEqual(73, proc.returncode, proc.stderr)
        names_after_death = sorted(path.name for path in self.runtime.attachments_root.iterdir())
        self.assertEqual(["A001 - hard-crash.pdf"], names_after_death)

        result = self.runtime.record(
            "answer", message_text="first try", message_key="crash:hard-process",
            attachment_paths=(source,), target_date=day,
        )
        self.assertEqual(
            ["A001 - hard-crash.pdf"],
            [path.name for path in self.runtime.attachments_root.iterdir()],
        )
        text = Path(result["path"]).read_text(encoding="utf-8")
        self.assertEqual(1, text.count("[[Life OS/Attachments/A001 - hard-crash.pdf]]"))

    def test_attachment_temp_reconciliation_rejects_symlink_and_nonregular_entries(self):
        attachments = self.runtime.attachments_root
        attachments.mkdir()
        target = self.base / "outside-temp"
        target.write_bytes(b"outside")
        symlink = attachments / (".life-os-attachment-" + "a" * 16)
        symlink.symlink_to(target)
        with self.assertRaisesRegex(life_os.LifeOSError, "temporary attachment"):
            self.runtime._reconcile_attachment_temps()
        symlink.unlink()
        fifo = attachments / (".life-os-attachment-" + "b" * 16)
        os.mkfifo(fifo)
        with self.assertRaisesRegex(life_os.LifeOSError, "temporary attachment"):
            self.runtime._reconcile_attachment_temps()

    def test_attachment_temp_reconciliation_rejects_foreign_owner(self):
        attachments = self.runtime.attachments_root
        attachments.mkdir()
        temp_name = ".life-os-attachment-" + "c" * 16
        (attachments / temp_name).write_bytes(b"stale")
        real_stat = life_os.os.stat

        def foreign_temp(path, *args, **kwargs):
            info = real_stat(path, *args, **kwargs)
            if path == temp_name and kwargs.get("follow_symlinks") is False:
                values = list(info)
                values[4] = info.st_uid + 1
                return os.stat_result(values)
            return info

        with mock.patch.object(life_os.os, "stat", side_effect=foreign_temp):
            with self.assertRaisesRegex(life_os.LifeOSError, "temporary attachment"):
                self.runtime._reconcile_attachment_temps()

    def test_failed_note_replace_retains_temp_for_manual_recovery(self):
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

        with self.assertRaisesRegex(life_os.LifeOSError, "temporary note"):
            self.runtime.record(
                "answer", message_text="note try", message_key="crash:note",
                attachment_paths=[source], target_date=day,
            )
        self.assertEqual(["A001 - note-crash.pdf"], [path.name for path in self.runtime.attachments_root.iterdir()])
        self.assertEqual(original, note_path.read_text(encoding="utf-8"))
        self.assertTrue(any(
            name.startswith(f".{note_path.name}.life-os-") for name in os.listdir(note_path.parent)
        ))

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

    def test_lock_uses_filesystem_identity_digest_namespace_and_private_modes(self):
        vault_info = self.vault.stat()
        identity = json.dumps(
            {"st_dev": vault_info.st_dev, "st_ino": vault_info.st_ino},
            separators=(",", ":"), sort_keys=True,
        )
        expected_name = hashlib.sha256(identity.encode("utf-8")).hexdigest()
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
        info = self.vault.stat()
        identity = json.dumps({"st_dev": info.st_dev, "st_ino": info.st_ino}, separators=(",", ":"), sort_keys=True)
        digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()
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
        info = self.vault.stat()
        identity = json.dumps({"st_dev": info.st_dev, "st_ino": info.st_ino}, separators=(",", ":"), sort_keys=True)
        digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()

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

    def test_lock_namespace_rejects_post_construction_symlink_replacement(self):
        namespace = self.runtime.state_namespace
        moved = namespace.with_name(namespace.name + "-original")
        external = self.base / "external-state-namespace"
        external.mkdir(mode=0o700)
        namespace.rename(moved)
        namespace.symlink_to(external, target_is_directory=True)

        with self.assertRaises(life_os.LifeOSError):
            self.runtime.record(
                "free_record", message_text="must not mutate", message_key="namespace:swap",
                target_date=date(2026, 8, 7),
            )
        self.assertFalse(self.runtime.daily_path(date(2026, 8, 7)).exists())
        self.assertFalse((external / "mutation.lock").exists())

    def test_case_alias_of_same_vault_uses_same_lock_namespace(self):
        case_alias = self.vault.with_name(self.vault.name.upper())
        try:
            same = os.path.samefile(case_alias, self.vault)
        except FileNotFoundError:
            same = False
        if not same:
            self.skipTest("temporary test filesystem is case-sensitive")
        aliased = LifeOSRuntime(
            vault_root=case_alias,
            state_root=self.runtime.state_root,
            timezone=ZoneInfo("Asia/Seoul"),
        )
        self.assertEqual(self.runtime.state_namespace, aliased.state_namespace)

    def test_global_message_claim_prevents_cross_date_and_cross_surface_replay(self):
        yesterday = date(2026, 8, 6)
        today = date(2026, 8, 7)
        first = self.runtime.record(
            "free_record", message_text="한 번만", message_key="global:date",
            target_date=yesterday,
        )
        replay = self.runtime.record(
            "free_record", message_text="한 번만", message_key="global:date",
            target_date=today,
        )
        self.assertFalse(first.get("duplicate", False))
        self.assertTrue(replay["duplicate"])
        self.assertEqual(first["path"], replay["path"])
        self.assertFalse(self.runtime.daily_path(today).exists())

        captured = self.runtime.record(
            "capture", message_text="캡처", message_key="global:surface",
            target_date=today,
        )
        daily_replay = self.runtime.record(
            "free_record", message_text="캡처", message_key="global:surface",
            target_date=today,
        )
        self.assertTrue(daily_replay["duplicate"])
        self.assertEqual(captured["path"], daily_replay["path"])

        daily = self.runtime.record(
            "free_record", message_text="데일리", message_key="global:reverse",
            target_date=today,
        )
        capture_replay = self.runtime.record(
            "capture", message_text="데일리", message_key="global:reverse",
            target_date=today,
        )
        self.assertTrue(capture_replay["duplicate"])
        self.assertEqual(daily["path"], capture_replay["path"])

    def test_global_claim_survives_restart_and_pending_claim_recovers_without_suppression(self):
        day = date(2026, 8, 7)
        original_commit = self.runtime._commit_global_claim
        with mock.patch.object(self.runtime, "_commit_global_claim", side_effect=OSError("crash")):
            with self.assertRaises(OSError):
                self.runtime.record(
                    "free_record", message_text="committed before crash", message_key="claim:crash",
                    target_date=day,
                )
        restarted = LifeOSRuntime(
            vault_root=self.vault,
            state_root=self.runtime.state_root,
            timezone=ZoneInfo("Asia/Seoul"),
            cache_roots=self.runtime.cache_roots,
            max_attachment_bytes=32 * 1024 * 1024,
        )
        result = restarted.record(
            "free_record", message_text="committed before crash", message_key="claim:crash",
            target_date=day,
        )
        self.assertTrue(result["duplicate"])
        self.assertEqual(1, self.runtime.daily_path(day).read_text(encoding="utf-8").count("committed before crash"))
        self.assertTrue(callable(original_commit))

    def test_implicit_record_and_start_are_linearized_under_one_lock(self):
        yesterday = date(2026, 8, 6)
        today = date(2026, 8, 7)
        self.runtime.start_daily(yesterday)

        class FixedDateTime(life_os.datetime):
            @classmethod
            def now(cls, tz=None):
                return cls(2026, 8, 7, 12, 0, tzinfo=tz)

        entered = threading.Event()
        release = threading.Event()
        original_resolve = self.runtime._resolve_target_date_unlocked

        def blocked_resolve(command=None):
            entered.set()
            release.wait(1)
            return original_resolve(command)

        outcomes = []
        with mock.patch.object(life_os, "datetime", FixedDateTime), mock.patch.object(
            self.runtime, "_resolve_target_date_unlocked", side_effect=blocked_resolve,
        ):
            record_thread = threading.Thread(target=lambda: outcomes.append(self.runtime.record(
                "answer", message_text="어제 답", message_key="linearized:1",
            )))
            start_thread = threading.Thread(target=lambda: outcomes.append(self.runtime.start_daily(today)))
            record_thread.start()
            self.assertTrue(entered.wait(1))
            start_thread.start()
            release.set()
            record_thread.join(2)
            start_thread.join(2)
        self.assertIn("어제 답", self.runtime.daily_path(yesterday).read_text(encoding="utf-8"))
        self.assertNotIn("어제 답", self.runtime.daily_path(today).read_text(encoding="utf-8"))

    def test_default_attachment_limit_uses_active_yaml_then_env_and_refreshes(self):
        cache_root = self.base / "cache/dynamic-documents"
        cache_root.mkdir(parents=True)
        source = cache_root / "limit.txt"
        source.write_bytes(b"fifteen-bytes!!")
        runtime = LifeOSRuntime(
            vault_root=self.vault,
            state_root=self.base / "dynamic-limit-state",
            timezone=ZoneInfo("Asia/Seoul"),
            cache_roots=(cache_root,),
        )
        config = {"discord": {"max_attachment_bytes": 11}}
        fake_config = types.SimpleNamespace(load_config_readonly=lambda: config)
        with mock.patch.dict(sys.modules, {
            "hermes_cli": types.ModuleType("hermes_cli"),
            "hermes_cli.config": fake_config,
        }), mock.patch.dict(os.environ, {"DISCORD_MAX_ATTACHMENT_BYTES": "22"}, clear=False):
            self.assertEqual(11, runtime.max_attachment_bytes)
            with self.assertRaisesRegex(life_os.LifeOSError, "configured size limit"):
                runtime.record(
                    "free_record", message_text="limit", message_key="dynamic-limit:1",
                    attachment_paths=(source,), target_date=date(2026, 8, 7),
                )
            config["discord"] = {}
            self.assertEqual(22, runtime.max_attachment_bytes)
            config["discord"]["max_attachment_bytes"] = 33
            self.assertEqual(33, runtime.max_attachment_bytes)
            recorded = runtime.record(
                "free_record", message_text="limit", message_key="dynamic-limit:1",
                attachment_paths=(source,), target_date=date(2026, 8, 7),
            )
            self.assertFalse(recorded.get("duplicate", False))

    def test_default_attachment_limit_fails_closed_on_unsafe_value(self):
        runtime = LifeOSRuntime(
            vault_root=self.vault,
            state_root=self.base / "unsafe-limit-state",
            timezone=ZoneInfo("Asia/Seoul"),
            cache_roots=(self.base / "cache/documents",),
        )
        fake_config = types.SimpleNamespace(
            load_config_readonly=lambda: {"discord": {"max_attachment_bytes": -1}},
        )
        with mock.patch.dict(sys.modules, {
            "hermes_cli": types.ModuleType("hermes_cli"),
            "hermes_cli.config": fake_config,
        }):
            with self.assertRaises(life_os.LifeOSError):
                _ = runtime.max_attachment_bytes

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
