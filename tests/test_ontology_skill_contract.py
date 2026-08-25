import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
PLUGIN = ROOT / "donggu-obsidian"
SKILLS = PLUGIN / "skills"
RETIRED_NAME = "ontology"


class RetiredOntologySurfaceContractTests(unittest.TestCase):
    def test_ontology_prompt_skill_is_absent_from_package(self):
        self.assertFalse((SKILLS / RETIRED_NAME).exists())
        self.assertFalse((SKILLS / RETIRED_NAME / "SKILL.md").exists())

    def test_plugin_registers_only_life_os_as_a_user_facing_skill(self):
        init_text = (PLUGIN / "__init__.py").read_text(encoding="utf-8")
        registered = re.findall(r'ctx\.register_skill\(\s*name="([^"]+)"', init_text)
        self.assertEqual(["life-os"], registered)
        self.assertNotIn('"skills" / "ontology"', init_text)

    def test_public_docs_and_manifests_do_not_advertise_ontology(self):
        surfaces = [
            ROOT / "README.md",
            PLUGIN / "README.md",
            PLUGIN / "plugin.yaml",
            PLUGIN / ".claude-plugin" / "plugin.json",
            ROOT / ".claude-plugin" / "marketplace.json",
        ]
        for path in surfaces:
            text = path.read_text(encoding="utf-8")
            with self.subTest(path=path):
                self.assertNotIn("donggu-obsidian:ontology", text)
                self.assertNotRegex(text, r"(?i)\bontology skill\b")

    def test_package_keeps_life_os_and_native_tool_runtime(self):
        self.assertTrue((SKILLS / "life-os" / "SKILL.md").is_file())
        init_text = (PLUGIN / "__init__.py").read_text(encoding="utf-8")
        for tool in (
            "donggu_core_plan",
            "donggu_fde_daily_capture_upsert",
            "donggu_life_os_start_daily",
        ):
            self.assertIn(tool, init_text)

        claude = json.loads(
            (PLUGIN / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
        )
        self.assertEqual("2.4.0", claude["version"])
        manifest = (PLUGIN / "plugin.yaml").read_text(encoding="utf-8")
        self.assertRegex(manifest, r'(?m)^version: "2\.4\.0"$')


if __name__ == "__main__":
    unittest.main()
