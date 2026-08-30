#!/usr/bin/env python3
import json
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "donggu-research"
SKILL = PLUGIN / "skills" / "consulting-event-radar" / "SKILL.md"
PLUGIN_MANIFEST = PLUGIN / ".claude-plugin" / "plugin.json"
MARKETPLACE = ROOT / ".claude-plugin" / "marketplace.json"
ROOT_README = ROOT / "README.md"


class ConsultingEventRadarSkillTests(unittest.TestCase):
    def test_plugin_manifest_matches_marketplace(self):
        plugin = json.loads(PLUGIN_MANIFEST.read_text(encoding="utf-8"))
        marketplace = json.loads(MARKETPLACE.read_text(encoding="utf-8"))
        entry = next(item for item in marketplace["plugins"] if item["name"] == "donggu-research")

        self.assertEqual("donggu-research", plugin["name"])
        self.assertEqual("1.0.0", plugin["version"])
        self.assertEqual(plugin["version"], entry["version"])
        self.assertEqual("./donggu-research", entry["source"])

    def test_skill_frontmatter_and_trigger_are_portable(self):
        text = SKILL.read_text(encoding="utf-8")
        self.assertTrue(text.startswith("---\n"))
        self.assertRegex(text, r"(?m)^name: consulting-event-radar$")
        match = re.search(r"(?m)^description:\s*[\"']?(.*?)[\"']?$", text)
        self.assertIsNotNone(match)
        description = match.group(1) if match is not None else ""
        self.assertTrue(description.startswith("Use when finding upcoming strategy consulting"))
        self.assertLessEqual(len(description), 1024)
        self.assertNotIn("/Users/joeykang", text)
        self.assertNotIn("~/.hermes", text)

    def test_skill_enforces_grounded_future_event_verification(self):
        text = SKILL.read_text(encoding="utf-8")
        for required in (
            "current KST",
            "official source",
            "search snippet",
            "registration status",
            "canonical URL",
            "MBB",
            "Big4",
            "event identity",
            "last30days",
            "last30days.py",
            "grounded-citations",
        ):
            with self.subTest(required=required):
                self.assertIn(required, text)

        self.assertIn("actor + event + date", text)
        self.assertIn("closed", text)
        self.assertIn("full", text)
        self.assertIn("cancelled", text)

    def test_skill_defines_concise_chat_and_quiet_cron_contracts(self):
        text = SKILL.read_text(encoding="utf-8")
        for required in (
            "추천 1순위",
            "컨설팅펌 직접 주최",
            "인접 행사",
            "최근 목적지 메시지",
            "[SILENT]",
            "45 days",
        ):
            with self.subTest(required=required):
                self.assertIn(required, text)

    def test_root_readme_exposes_the_new_plugin_and_skill(self):
        readme = ROOT_README.read_text(encoding="utf-8")
        self.assertIn("plugins-6", readme)
        self.assertIn("skills-10", readme)
        self.assertIn("donggu-research", readme)
        self.assertIn("consulting-event-radar", readme)


if __name__ == "__main__":
    unittest.main()
