from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL = REPO_ROOT / "donggu-docs" / "skills" / "make-ppt" / "SKILL.md"


class MakePptPortabilityTest(unittest.TestCase):
    def test_skill_uses_runtime_neutral_interaction_and_paths(self):
        text = SKILL.read_text(encoding="utf-8")

        banned = (
            "AskUserQuestion",
            "Read tool (Claude is multimodal)",
            ".claude-design/slide-previews/",
        )
        for marker in banned:
            with self.subTest(marker=marker):
                self.assertNotIn(marker, text)

        self.assertIn("current runtime's user-interaction mechanism", text)
        self.assertIn("current runtime's image/vision capability", text)
        self.assertIn(".presentation-previews/", text)


if __name__ == "__main__":
    unittest.main()
