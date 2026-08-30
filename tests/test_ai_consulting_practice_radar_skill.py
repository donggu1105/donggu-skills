#!/usr/bin/env python3
import json
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "donggu-research"
SKILL = PLUGIN / "skills" / "ai-consulting-practice-radar" / "SKILL.md"
OLD_SKILL = PLUGIN / "skills" / "consulting-event-radar"
PLUGIN_MANIFEST = PLUGIN / ".claude-plugin" / "plugin.json"
MARKETPLACE = ROOT / ".claude-plugin" / "marketplace.json"
ROOT_README = ROOT / "README.md"
PLUGIN_README = PLUGIN / "README.md"


class AIConsultingPracticeRadarSkillTests(unittest.TestCase):
    def test_plugin_manifest_matches_marketplace_release(self):
        plugin = json.loads(PLUGIN_MANIFEST.read_text(encoding="utf-8"))
        marketplace = json.loads(MARKETPLACE.read_text(encoding="utf-8"))
        entry = next(item for item in marketplace["plugins"] if item["name"] == "donggu-research")

        self.assertEqual("donggu-research", plugin["name"])
        self.assertEqual("1.1.0", plugin["version"])
        self.assertEqual(plugin["version"], entry["version"])
        self.assertEqual("./donggu-research", entry["source"])

    def test_skill_replaces_event_listing_with_practice_learning(self):
        self.assertFalse(OLD_SKILL.exists())
        text = SKILL.read_text(encoding="utf-8")
        self.assertTrue(text.startswith("---\n"))
        self.assertRegex(text, r"(?m)^name: ai-consulting-practice-radar$")
        match = re.search(r"(?m)^description:\s*[\"']?(.*?)[\"']?$", text)
        self.assertIsNotNone(match)
        description = match.group(1) if match is not None else ""
        self.assertTrue(description.startswith("Use when learning how strategy consulting firms"))
        for cue in ("AI", "AX", "전략컨설팅", "실제 하는 일"):
            self.assertIn(cue, description)
        self.assertLessEqual(len(description), 1024)

    def test_last30days_is_the_required_discovery_engine(self):
        text = SKILL.read_text(encoding="utf-8")
        for required in (
            "last30days",
            "last30days.py",
            "--plan",
            "Python 3.12+",
            "source outcome",
            "일반 웹검색으로 대체하지 않는다",
            "grounded-citations",
        ):
            with self.subTest(required=required):
                self.assertIn(required, text)

    def test_researches_real_ai_consulting_work_not_event_calendar(self):
        text = SKILL.read_text(encoding="utf-8")
        for firm in (
            "McKinsey / QuantumBlack",
            "BCG / BCG X",
            "Bain",
            "Deloitte / Monitor Deloitte",
            "EY / EY-Parthenon",
            "PwC / Strategy&",
            "KPMG",
            "Accenture",
        ):
            with self.subTest(firm=firm):
                self.assertIn(firm, text)

        for practice in (
            "CEO agenda",
            "operating model",
            "workflow redesign",
            "data and platform",
            "governance",
            "change management",
            "value realization",
        ):
            with self.subTest(practice=practice):
                self.assertIn(practice, text)

        for stage in (
            "문제 정의",
            "진단",
            "로드맵",
            "PoC",
            "production",
            "adoption",
            "ROI",
        ):
            with self.subTest(stage=stage):
                self.assertIn(stage, text)

    def test_output_is_a_learning_brief_with_transfer_to_current_work(self):
        text = SKILL.read_text(encoding="utf-8")
        for section in (
            "이번 주 핵심 판단",
            "컨설팅펌이 실제로 한 일",
            "산출물과 개입 방식",
            "동구님 업무와 비교",
            "이번 주 따라 해볼 것",
            "더 파볼 질문",
        ):
            with self.subTest(section=section):
                self.assertIn(section, text)
        self.assertIn("FDE", text)
        self.assertIn("DA", text)
        self.assertIn("Wishket AIDP", text)
        self.assertIn("출처를 일반화하지 않는다", text)

    def test_weekly_cron_contract_is_explicit_and_quiet(self):
        text = SKILL.read_text(encoding="utf-8")
        for required in (
            "0 8 * * 1",
            "🧠-AI-전략컨설팅-리서치",
            "fetch_messages(channel_id, limit=100)",
            "last_status=ok",
            "[SILENT]",
            "material learning delta",
            "최근 90일",
        ):
            with self.subTest(required=required):
                self.assertIn(required, text)

    def test_docs_expose_only_the_new_research_skill(self):
        root = ROOT_README.read_text(encoding="utf-8")
        plugin = PLUGIN_README.read_text(encoding="utf-8")
        for text in (root, plugin):
            self.assertIn("ai-consulting-practice-radar", text)
            self.assertIn("last30days", text)
            self.assertNotIn("consulting-event-radar", text)
        self.assertIn("plugins-6", root)
        self.assertIn("skills-10", root)


if __name__ == "__main__":
    unittest.main()
