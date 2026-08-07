#!/usr/bin/env python3
import importlib.util
from datetime import date
import json
import os
from pathlib import Path
import sys
import tempfile
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
        )

    def test_start_daily_renders_known_snapshot_and_preserves_template_blocks(self):
        result = self.runtime.start_daily(date(2026, 8, 7))
        text = Path(result["path"]).read_text(encoding="utf-8")
        self.assertNotIn("<%", text)
        self.assertIn("- [ ] Breakfast", text)
        self.assertIn("```LifeOS\nTaskDoneListByTime\n```", text)
        self.assertIn("<!-- life-os:record:start -->", text)
        self.assertEqual(1, result["next_question"])

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
