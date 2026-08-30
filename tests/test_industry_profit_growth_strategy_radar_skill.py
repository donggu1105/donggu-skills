#!/usr/bin/env python3
import json
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "donggu-research"
SKILL = PLUGIN / "skills" / "industry-profit-growth-strategy-radar" / "SKILL.md"
OLD_SKILL = PLUGIN / "skills" / "ai-consulting-practice-radar"
PLUGIN_MANIFEST = PLUGIN / ".claude-plugin" / "plugin.json"
MARKETPLACE = ROOT / ".claude-plugin" / "marketplace.json"
ROOT_README = ROOT / "README.md"
PLUGIN_README = PLUGIN / "README.md"


class IndustryProfitGrowthStrategyRadarSkillTests(unittest.TestCase):
    def test_plugin_manifest_matches_marketplace_release(self):
        plugin = json.loads(PLUGIN_MANIFEST.read_text(encoding="utf-8"))
        marketplace = json.loads(MARKETPLACE.read_text(encoding="utf-8"))
        entry = next(item for item in marketplace["plugins"] if item["name"] == "donggu-research")

        self.assertEqual("donggu-research", plugin["name"])
        self.assertEqual("1.3.0", plugin["version"])
        self.assertEqual(plugin["version"], entry["version"])
        self.assertEqual("./donggu-research", entry["source"])

    def test_skill_replaces_ai_consulting_practice_radar(self):
        self.assertFalse(OLD_SKILL.exists())
        text = SKILL.read_text(encoding="utf-8")
        self.assertTrue(text.startswith("---\n"))
        self.assertRegex(text, r"(?m)^name: industry-profit-growth-strategy-radar$")
        match = re.search(r"(?m)^description:\s*[\"']?(.*?)[\"']?$", text)
        self.assertIsNotNone(match)
        description = match.group(1) if match is not None else ""
        self.assertTrue(description.startswith("Use when learning how AI/AX changes real industries"))
        for cue in ("AI/AX", "P&L", "beginner-friendly Korean", "AX로 산업이 어떻게 바뀌고 이익을 늘리는가"):
            self.assertIn(cue, description)
        self.assertLessEqual(len(description), 1024)

    def test_teaches_a_repeatable_four_week_strategy_curriculum(self):
        text = SKILL.read_text(encoding="utf-8")
        for week in (
            "1주차 — 산업 구조와 profit pool",
            "2주차 — 기업 P&L과 driver tree",
            "3주차 — 실제 성장전략과 결과",
            "4주차 — 1페이지 전략 메모",
        ):
            with self.subTest(week=week):
                self.assertIn(week, text)

        for concept in (
            "가치사슬",
            "profit pool",
            "매출 성장률",
            "매출총이익률",
            "영업이익률",
            "고객 수",
            "객단가",
            "구매 빈도",
            "가격·상품 Mix",
            "반복 매출",
            "수주잔고",
        ):
            with self.subTest(concept=concept):
                self.assertIn(concept, text)

    def test_focuses_on_profit_growth_options_not_cost_only(self):
        text = SKILL.read_text(encoding="utf-8")
        for option in (
            "기존 시장 침투",
            "가격·Mix 개선",
            "신규 고객·채널·지역 확장",
            "인접 제품·신사업",
            "반복 매출화",
        ):
            with self.subTest(option=option):
                self.assertIn(option, text)
        self.assertIn("Revenue = 고객 수 × 구매 빈도 × 가격·상품 Mix", text)
        self.assertIn("Profit = Revenue - Cost", text)
        self.assertIn("비용 절감만으로 끝내지 않는다", text)

    def test_uses_last30days_plus_financial_primary_sources(self):
        text = SKILL.read_text(encoding="utf-8")
        for required in (
            "last30days.py",
            "--plan",
            "Python 3.12+",
            "DART",
            "사업보고서",
            "분기 실적",
            "IR 자료",
            "earnings call",
            "정부·협회 산업통계",
            "grounded-citations",
        ):
            with self.subTest(required=required):
                self.assertIn(required, text)
        self.assertIn("last30days는 최신 신호 탐지", text)
        self.assertIn("숫자의 정본", text)

    def test_targets_industries_changed_by_ax_not_only_ax_suppliers(self):
        text = SKILL.read_text(encoding="utf-8")
        self.assertIn("AX 공급업체 시장이 아니다", text)
        for industry in (
            "제조",
            "금융",
            "유통·커머스",
            "물류",
            "헬스케어",
            "전문서비스",
            "콘텐츠·미디어",
            "공공",
        ):
            with self.subTest(industry=industry):
                self.assertIn(industry, text)
        self.assertIn("industry_index", text)
        self.assertIn("제조 → 금융 → 유통·커머스 → 물류", text)

    def test_output_is_beginner_friendly_and_business_model_first(self):
        text = SKILL.read_text(encoding="utf-8")
        for required in (
            "사업전략을 처음 체계적으로 배우는 AI/FDE 실무자",
            "이번 주 산업 하나",
            "기업 하나",
            "숫자는 최대 3개",
            "새 용어는 최대 3개",
            "초등학생도 이해할 수 있는 한국어",
            "누가 왜 돈을 내는가",
            "돈이 들어오고 비용이 나가는 흐름",
            "AI 전에는",
            "AI 이후에는",
        ):
            with self.subTest(required=required):
                self.assertIn(required, text)

        for section in (
            "이번 주 한 문장",
            "이 산업은 원래 어떻게 돈을 버나",
            "AI 때문에 무엇이 바뀌나",
            "기업 하나로 보기",
            "숫자 3개만 보기",
            "용어 3개만 배우기",
            "이익을 늘릴 선택지",
            "동구님이 답해볼 질문",
        ):
            with self.subTest(section=section):
                self.assertIn(section, text)

    def test_default_industry_and_output_are_learning_oriented(self):
        text = SKILL.read_text(encoding="utf-8")
        self.assertIn("제조업", text)
        self.assertIn("1페이지 전략 메모", text)
        self.assertIn("90일 검증", text)

    def test_rejects_irrelevant_community_evidence_from_public_brief(self):
        text = SKILL.read_text(encoding="utf-8")
        for required in (
            "돈 버는 구조와 직접 연결되지 않은 커뮤니티 반응은 제외",
            "제품 불만·사고·수리 경험",
            "Reddit·커뮤니티 댓글은 핵심 근거로 쓰지 않는다",
            "업무·고객·매출·비용 중 하나를 바꾼다는 인과",
        ):
            with self.subTest(required=required):
                self.assertIn(required, text)

    def test_weekly_cron_rotates_learning_stage_and_dedupes(self):
        text = SKILL.read_text(encoding="utf-8")
        for required in (
            "0 8 * * 1",
            "📣-AX-산업변화",
            "fetch_messages(channel_id, limit=100)",
            "최근 120일",
            "material learning delta",
            "[SILENT]",
            "week_index",
        ):
            with self.subTest(required=required):
                self.assertIn(required, text)

    def test_docs_expose_only_the_new_research_skill(self):
        root = ROOT_README.read_text(encoding="utf-8")
        plugin = PLUGIN_README.read_text(encoding="utf-8")
        for text in (root, plugin):
            self.assertIn("industry-profit-growth-strategy-radar", text)
            self.assertIn("last30days", text)
            self.assertNotIn("ai-consulting-practice-radar", text)
        self.assertIn("plugins-6", root)
        self.assertIn("skills-10", root)


if __name__ == "__main__":
    unittest.main()
