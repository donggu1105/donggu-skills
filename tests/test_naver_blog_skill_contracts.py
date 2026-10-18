"""Offline contracts for the Naver authoring/publishing documentation."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1] / "donggu-sns" / "skills"


class NaverBlogSkillContractsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.writing = (ROOT / "writing-social-content" / "SKILL.md").read_text()
        cls.author = (ROOT / "writing-social-content" / "references" / "naver-blog.md").read_text()
        cls.publishing = (ROOT / "publish-sns" / "SKILL.md").read_text()
        cls.handoff = (ROOT / "publish-sns" / "references" / "naver-blog-vault.md").read_text()

    def test_naver_is_blog_branch_not_external_voice_dependency(self):
        self.assertIn("Blog (Naver Blog / 네이버 / naver_blog)", self.writing)
        self.assertIn("references/naver-blog.md", self.writing)
        self.assertIn("외부 보이스 의존성을 만들지 않는다", self.writing)

    def test_authoring_does_not_claim_publish_capability(self):
        self.assertIn("집필 형식", self.author)
        self.assertIn("저장·이미지 작업·편집기 입력·게시를 수행하지 않는다", self.author)
        self.assertIn("검색량을 조회하지 않았다면", self.author)

    def test_no_search_rank_guarantee(self):
        self.assertIn("노출 요건이 아니다", self.author)
        self.assertIn("순위 공식처럼 제시하지 않는다", self.author)
        self.assertIn("무조건 검색 제재", self.author)

    def test_folder_and_channel_identity_stay_distinct(self):
        self.assertIn("NaverBlog→naver_blog (locked)", self.publishing)
        self.assertIn("`Blog/` and `channel: blog` remain Tistory", self.handoff)
        self.assertIn("do not inherit approval, receipt, or publication status", self.handoff)

    def test_note_boundary_excludes_private_working_notes(self):
        self.assertIn("exactly one top-level `# 발행 원고`", self.handoff)
        self.assertIn("exactly one `# 편집 메모`", self.handoff)
        self.assertIn("ignore headings inside fenced code", self.handoff)
        self.assertIn("Missing, reversed, duplicated, or unexpected H1 boundaries fail closed", self.handoff)
        self.assertIn("First nonblank line", self.handoff)
        self.assertIn("Never include frontmatter", self.handoff)

    def test_private_and_public_tags_are_not_mixed(self):
        self.assertIn("`topics` are internal classification", self.handoff)
        self.assertIn("Only `public_tags` are public tag candidates", self.handoff)
        self.assertIn("Never auto-copy the legacy fixed TAG_GUIDE", self.handoff)

    def test_activation_and_unsupported_assets_fail_closed(self):
        self.assertIn("Every Tistory publish or update", self.publishing)
        self.assertIn("NAVER_BLOG_ENABLED=false", self.handoff)
        self.assertIn("Current backend rejects images, cover, and rich Markdown", self.handoff)
        self.assertIn("Unsupported content is a blocker", self.handoff)
        self.assertIn("Never call a direct endpoint", self.handoff)

    def test_public_result_and_ledger_both_required(self):
        self.assertIn("public content and adapter ledger write must both be verified", self.handoff)
        self.assertIn("only this Naver note", self.handoff)
        self.assertIn("reconciliation leaves it draft", self.handoff)
        self.assertIn("Post IDs/URLs remain owned by `published_posts`", self.handoff)


if __name__ == "__main__":
    unittest.main()
