#!/usr/bin/env python3
import importlib.util
from datetime import date
from pathlib import Path
import sys
import tempfile
import unittest
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


if __name__ == "__main__":
    unittest.main()
