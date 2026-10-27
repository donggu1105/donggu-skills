"""Repo layout contract — flat Agent Skills tree, no plugin/marketplace layer (2026-10-27)."""

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "skills"
SPEC_FIELDS = {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}
# Pre-existing non-spec keys some skills carry; every runtime ignores unknown keys, so they are
# tolerated but frozen — new skills must stay spec-clean.
TOLERATED_LEGACY = {"type", "channel", "topics", "status", "format", "created", "version", "url", "author"}


def frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), path
    block = text.split("\n---", 1)[0][4:]
    out = {}
    for line in block.splitlines():
        if line and not line.startswith((" ", "\t", "-")) and ":" in line:
            key, _, value = line.partition(":")
            out[key.strip()] = value.strip()
    return out


class FlatLayoutTest(unittest.TestCase):
    def test_every_skill_is_a_folder_with_spec_frontmatter(self):
        dirs = sorted(p for p in SKILLS.iterdir() if p.is_dir() and not p.name.startswith((".", "_")))
        self.assertEqual(12, len(dirs), [d.name for d in dirs])
        for d in dirs:
            with self.subTest(skill=d.name):
                fm = frontmatter(d / "SKILL.md")
                self.assertEqual(d.name, fm.get("name"))
                self.assertRegex(d.name, r"^[a-z0-9]+(-[a-z0-9]+)*$")
                self.assertTrue(fm.get("description"))
                self.assertLessEqual(len(fm["description"]), 1024)
                self.assertFalse(set(fm) - SPEC_FIELDS - TOLERATED_LEGACY, set(fm) - SPEC_FIELDS)

    def test_no_plugin_or_marketplace_layer(self):
        for legacy in (".claude-plugin", ".agents/plugins", "donggu-sns", "donggu-ppt", "donggu-docs",
                       "donggu-research", "donggu-media", "donggu-apply", "donggu-obsidian"):
            self.assertFalse((ROOT / legacy).exists(), legacy)
        for stray in ROOT.rglob("plugin.json"):
            if ".git" in stray.parts or ".worktrees" in stray.parts:
                continue
            self.fail(f"plugin manifest reintroduced: {stray.relative_to(ROOT)}")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("npx skills add donggu1105/donggu-skills", readme)
        self.assertNotIn("/plugin install donggu-sns@", readme)  # the old per-plugin install line is gone
        for d in SKILLS.iterdir():
            for md in d.rglob("*.md"):
                with self.subTest(path=md.relative_to(ROOT)):
                    self.assertIsNone(re.search(r"donggu-(sns|ppt|docs|research|media|apply):", md.read_text(encoding="utf-8")))

    def test_hermes_native_publisher_stays_a_plugin_dir(self):
        plugin = ROOT / "hermes" / "donggu-sns"
        for required in ("plugin.yaml", "tools.py", "__init__.py", "runtime"):
            self.assertTrue((plugin / required).exists(), required)
        manifest = (plugin / "plugin.yaml").read_text(encoding="utf-8")
        self.assertIn("name: donggu-sns", manifest)
        self.assertIn("provides_tools:", manifest)
        self.assertFalse((plugin / "skills").exists(), "skills live in /skills, not inside the plugin")


if __name__ == "__main__":
    unittest.main()
