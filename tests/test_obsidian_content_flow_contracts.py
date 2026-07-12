from pathlib import Path
import json
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]


SKILL_PATHS = {
    "writing": REPO_ROOT / "donggu-sns" / "skills" / "writing-social-content" / "SKILL.md",
    "publishing": REPO_ROOT / "donggu-sns" / "skills" / "publish-sns" / "SKILL.md",
    "extract_core": REPO_ROOT / "donggu-obsidian" / "skills" / "extract-core" / "SKILL.md",
    "decompose": REPO_ROOT / "donggu-obsidian" / "skills" / "decompose-canon" / "SKILL.md",
    "health": REPO_ROOT / "donggu-obsidian" / "skills" / "checking-vault-health" / "SKILL.md",
    "duplicates": REPO_ROOT / "donggu-obsidian" / "skills" / "finding-duplicate-notes" / "SKILL.md",
    "approval": REPO_ROOT / "donggu-obsidian" / "skills" / "core-review-approval" / "SKILL.md",
}


class ObsidianContentFlowContractsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.skills = {
            name: path.read_text(encoding="utf-8")
            for name, path in SKILL_PATHS.items()
        }

    def test_writing_owns_origin_and_adapt_lineage(self):
        writing = self.skills["writing"]

        self.assertIn("origin", writing)
        self.assertIn("adapt", writing)
        self.assertIn("type: channel_pack", writing)
        self.assertIn("derived_from", writing)
        self.assertNotIn("type: content", writing)

    def test_publishing_owns_ledger_backed_review_event(self):
        publishing = self.skills["publishing"]

        self.assertIn("발행 완료 이벤트", publishing)
        self.assertIn("existing DB trigger", publishing)
        self.assertIn("dry-run", publishing.lower())
        self.assertIn("CORE/Snippet/MOC", publishing)

    def test_extract_core_is_routine_first(self):
        extract_core = self.skills["extract_core"]

        self.assertIn("routine", extract_core.lower())
        self.assertIn("newly published Channel Pack", extract_core)
        self.assertIn("curated `10_Sources` note", extract_core)
        self.assertIn("explicit Inbox recommendation-only request", extract_core)
        for outcome in ("LINK", "NEW", "MERGE", "HOLD"):
            with self.subTest(outcome=outcome):
                self.assertIn(outcome, extract_core)

    def test_decompose_is_reserved_for_explicit_canon_selection(self):
        decompose = self.skills["decompose"]

        self.assertIn("canon", decompose.lower())
        self.assertIn("explicit canon selection", decompose.lower())
        self.assertIn("routine", decompose.lower())
        self.assertIn("extract-core", decompose)

    def test_daily_health_reports_even_without_candidates(self):
        health = self.skills["health"]

        self.assertIn("후보가 없어도", health)
        for metric in (
            "recent Inbox count",
            "recent published count",
            "stalled Source count",
            "return-gap count",
            "link/schema candidate count",
        ):
            with self.subTest(metric=metric):
                self.assertIn(metric, health)

    def test_daily_health_preserves_inbox_boundary(self):
        health = self.skills["health"]

        self.assertIn("00_Inbox", health)
        self.assertIn("자동 이동", health)
        self.assertIn("age/count alone", health)
        self.assertIn("recommendation-only", health)

    def test_duplicate_full_audit_is_monthly_or_on_demand(self):
        duplicates = self.skills["duplicates"]

        self.assertIn("monthly", duplicates.lower())
        self.assertIn("on-demand", duplicates.lower())
        self.assertIn("daily", duplicates.lower())
        self.assertIn("threshold signal", duplicates.lower())

    def test_only_core_review_approval_applies_candidates(self):
        self.assertIn("apply-action.py", self.skills["approval"])
        for name in ("extract_core", "decompose", "health", "duplicates"):
            with self.subTest(skill=name):
                self.assertNotIn("apply-action.py", self.skills[name])

    def test_audited_candidate_skills_forbid_automatic_vault_mutation(self):
        required_guards = {
            "extract_core": ("자동 이동", "승인 전에 적용하지 않는다"),
            "decompose": ("자동 생성 금지", "recommend → STOP → create"),
            "health": ("Auto-promoting inbox notes", "per-item approval"),
            "duplicates": ("No auto-merge", "No automation"),
        }
        for name, guards in required_guards.items():
            text = self.skills[name]
            for guard in guards:
                with self.subTest(skill=name, guard=guard):
                    self.assertIn(guard, text)

    def test_changed_plugin_versions_match_marketplace(self):
        marketplace = json.loads(
            (REPO_ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8")
        )
        marketplace_versions = {
            plugin["name"]: plugin["version"] for plugin in marketplace["plugins"]
        }
        for plugin_name in ("donggu-sns", "donggu-obsidian"):
            manifest = json.loads(
                (REPO_ROOT / plugin_name / ".claude-plugin" / "plugin.json").read_text(
                    encoding="utf-8"
                )
            )
            with self.subTest(plugin=plugin_name):
                self.assertEqual(manifest["version"], marketplace_versions[plugin_name])


if __name__ == "__main__":
    unittest.main()
