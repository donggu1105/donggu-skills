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


if __name__ == "__main__":
    unittest.main()
