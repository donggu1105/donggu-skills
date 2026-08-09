import re
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
PLUGIN = ROOT / "donggu-obsidian"
SKILLS = PLUGIN / "skills"
ONTOLOGY = SKILLS / "ontology"
LEGACY_USER_SKILLS = (
    "extract-core",
    "decompose-canon",
    "finding-duplicate-notes",
    "checking-vault-health",
)
REFERENCES = (
    "routing.md",
    "personal-branding.md",
    "fde-projects.md",
    "maintenance.md",
    "mutation.md",
)


class OntologySkillContractTests(unittest.TestCase):
    def test_one_user_facing_ontology_skill_replaces_legacy_surface(self):
        self.assertTrue((ONTOLOGY / "SKILL.md").is_file())
        for name in LEGACY_USER_SKILLS:
            self.assertFalse((SKILLS / name / "SKILL.md").exists(), name)

        # The proven transaction helpers remain available to the native runtime,
        # but the protocol is no longer exposed as a user-facing prompt skill.
        approval = SKILLS / "core-review-approval"
        self.assertFalse((approval / "SKILL.md").exists())
        for helper in (
            "apply-action.py",
            "render-preview.py",
            "validate-conversation.py",
            "validate-approval.py",
        ):
            self.assertTrue((approval / "scripts" / helper).is_file(), helper)

    def test_frontmatter_is_minimal_and_progressive_references_exist(self):
        text = (ONTOLOGY / "SKILL.md").read_text(encoding="utf-8")
        self.assertTrue(text.startswith("---\n"))
        frontmatter = text.split("---", 2)[1]
        keys = [
            line.split(":", 1)[0]
            for line in frontmatter.splitlines()
            if ":" in line
        ]
        self.assertEqual(["name", "description"], keys)
        self.assertRegex(frontmatter, r"(?m)^name: ontology$")
        self.assertRegex(frontmatter, r"(?m)^description: Use when ")
        self.assertLess(len(text), 6500)

        for filename in REFERENCES:
            path = ONTOLOGY / "references" / filename
            self.assertTrue(path.is_file(), filename)
            self.assertIn(f"references/{filename}", text)

    def test_contract_follows_real_vault_boundaries_and_pipeline(self):
        corpus = "\n".join(
            (ONTOLOGY / relative).read_text(encoding="utf-8")
            for relative in ("SKILL.md",) + tuple(
                f"references/{filename}" for filename in REFERENCES
            )
        )
        for phrase in (
            "AGENTS.md",
            "Personal Branding",
            "FDE Projects",
            "Life OS",
            "Inbox",
            "발행",
            "CORE",
            "Snippet",
            "MOC",
            "Ontology Lens",
            "출처 포인터",
        ):
            self.assertIn(phrase, corpus)

        # Inbox selection feeds publication; CORE integration starts only after publication.
        self.assertIn("Inbox selection is publication input only", corpus)
        self.assertIn("completed and approved publication only", corpus)
        self.assertRegex(corpus, r"선택.+추출.+통합")
        self.assertIn("기존 CORE", corpus)
        self.assertIn("새 CORE", corpus)
        self.assertIn("후보 하나", corpus)

    def test_mutation_and_maintenance_are_quiet_and_candidate_scoped(self):
        mutation = (ONTOLOGY / "references" / "mutation.md").read_text(
            encoding="utf-8"
        )
        for phrase in (
            "실제 diff",
            "변경 0건",
            "exact `수정안 보여줘`",
            "별도 메시지",
            "later persisted user message",
            "적용해줘",
            "proposal-only",
            "read-back",
            "rollback",
        ):
            self.assertIn(phrase, mutation)
        self.assertNotIn("button", mutation.lower())
        self.assertNotIn("filesystem patch", mutation.lower())

        maintenance = (ONTOLOGY / "references" / "maintenance.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("매일 전체 Vault를 스캔하지 않는다", maintenance)
        self.assertIn("정상 결과는 알리지 않는다", maintenance)
        self.assertIn("발행 이벤트", maintenance)
        self.assertIn("최대 3개", maintenance)

    def test_prompt_surface_does_not_leak_legacy_machine_protocol(self):
        corpus = "\n".join(
            path.read_text(encoding="utf-8")
            for path in [ONTOLOGY / "SKILL.md", *(ONTOLOGY / "references").glob("*.md")]
        )
        for forbidden in (
            "CR-YYYYMMDD",
            "10점",
            "05:40",
            "PARA",
            "LYT",
            "status_cleanup",
            "skill_drift",
            "Documents/obsidian",
        ):
            self.assertNotIn(forbidden, corpus)

    def test_plugin_registers_ontology_as_a_native_skill(self):
        init_text = (PLUGIN / "__init__.py").read_text(encoding="utf-8")
        self.assertRegex(
            init_text,
            r'ctx\.register_skill\(\s*name="ontology"',
        )
        self.assertIn('"skills" / "ontology" / "SKILL.md"', init_text)

        manifest = (PLUGIN / "plugin.yaml").read_text(encoding="utf-8")
        self.assertIn("Ontology-aware Obsidian operations", manifest)

        readme = (PLUGIN / "README.md").read_text(encoding="utf-8")
        self.assertIn("`donggu-obsidian:ontology`", readme)


if __name__ == "__main__":
    unittest.main()
