"""Contracts for donggu-ppt:donggu-deck — the deck skill moved here from wishket-tools:decks (2026-10-26)."""

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "donggu-ppt"
SKILL = PLUGIN / "skills" / "donggu-deck"


class DongguPptPackagingTest(unittest.TestCase):
    def test_manifest_matches_marketplace_and_ships_exactly_one_skill(self):
        plugin = json.loads((PLUGIN / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
        marketplace = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
        entry = next(item for item in marketplace["plugins"] if item["name"] == "donggu-ppt")
        self.assertEqual("donggu-ppt", plugin["name"])
        self.assertEqual("./donggu-ppt", entry["source"])
        self.assertEqual(plugin["version"], entry["version"])
        codex = json.loads((PLUGIN / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
        codex_catalog = json.loads((ROOT / ".agents" / "plugins" / "marketplace.json").read_text(encoding="utf-8"))
        codex_entry = next(item for item in codex_catalog["plugins"] if item["name"] == "donggu-ppt")
        self.assertEqual("./skills/", codex["skills"])
        self.assertEqual(plugin["version"], codex["version"])
        self.assertEqual(plugin["version"], codex_entry["version"])
        self.assertEqual({"source": "local", "path": "./donggu-ppt"}, codex_entry["source"])
        self.assertEqual(["donggu-deck"], sorted(p.parent.name for p in (PLUGIN / "skills").glob("*/SKILL.md")))
        root_readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("donggu-ppt:donggu-deck", root_readme)
        self.assertIn(f"v{plugin['version']}", root_readme)
        self.assertIn("skills-1", (PLUGIN / "README.md").read_text(encoding="utf-8"))

    def test_skill_files_and_runtime_neutral_wording(self):
        text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        self.assertTrue(text.startswith("---\nname: donggu-deck\n"))
        for banned in ("AskUserQuestion", "skill_view(", "MEDIA:", "~/.hermes/profiles", "make-ppt"):
            with self.subTest(banned=banned):
                self.assertNotIn(banned, text)
        for required in (
            SKILL / "template.html",
            SKILL / "components.html",
            SKILL / "references" / "tokens.md",
            SKILL / "references" / "qa-headless.md",
            SKILL / "assets" / "PretendardVariable.woff2",
        ):
            with self.subTest(path=required.relative_to(ROOT)):
                self.assertTrue(required.is_file())

    def test_public_copy_carries_no_client_names(self):
        # The skill was distilled from a client workshop; the public repo keeps the lessons, not the client.
        for path in SKILL.rglob("*"):
            if path.suffix not in {".md", ".html", ".yaml", ".yml", ".json"}:
                continue
            with self.subTest(path=path.relative_to(ROOT)):
                self.assertIsNone(re.search(r"맨텍|mantech|wishket|위시켓", path.read_text(encoding="utf-8"), re.I))

    def test_template_does_not_advance_on_click(self):
        # Host rule: slides move by keys/arrow buttons only ("클릭으로 넘어가진 않게").
        html = (SKILL / "template.html").read_text(encoding="utf-8")
        self.assertNotIn("addEventListener('click'", html)
        self.assertNotIn("클릭으로 진행", html)
        self.assertIn("클릭 진행 금지", (SKILL / "SKILL.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
