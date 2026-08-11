from pathlib import Path
import hashlib
import json
import re
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]


SKILL_PATHS = {
    "writing": REPO_ROOT / "donggu-sns" / "skills" / "writing-social-content" / "SKILL.md",
    "publishing": REPO_ROOT / "donggu-sns" / "skills" / "publish-sns" / "SKILL.md",
    "ontology": REPO_ROOT / "donggu-obsidian" / "skills" / "ontology" / "SKILL.md",
}

WRITING_REFERENCE_PATHS = {
    "personas": REPO_ROOT / "donggu-sns" / "skills" / "writing-social-content" / "references" / "personas.md",
    "common": REPO_ROOT / "donggu-sns" / "skills" / "writing-social-content" / "references" / "common-voice.md",
    "blog": REPO_ROOT / "donggu-sns" / "skills" / "writing-social-content" / "references" / "blog.md",
    "linkedin": REPO_ROOT / "donggu-sns" / "skills" / "writing-social-content" / "references" / "linkedin.md",
    "threads": REPO_ROOT / "donggu-sns" / "skills" / "writing-social-content" / "references" / "threads.md",
    "maily": REPO_ROOT / "donggu-sns" / "skills" / "writing-social-content" / "references" / "maily.md",
    "examples_blog": REPO_ROOT / "donggu-sns" / "skills" / "writing-social-content" / "references" / "examples-blog.md",
    "examples_linkedin": REPO_ROOT / "donggu-sns" / "skills" / "writing-social-content" / "references" / "examples-linkedin.md",
    "examples_threads": REPO_ROOT / "donggu-sns" / "skills" / "writing-social-content" / "references" / "examples-threads.md",
    "examples_maily": REPO_ROOT / "donggu-sns" / "skills" / "writing-social-content" / "references" / "examples-maily.md",
}


class ObsidianContentFlowContractsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.skills = {
            name: path.read_text(encoding="utf-8")
            for name, path in SKILL_PATHS.items()
        }
        cls.writing_references = {
            name: path.read_text(encoding="utf-8")
            for name, path in WRITING_REFERENCE_PATHS.items()
        }

    def test_writing_is_portable_authoring_router(self):
        writing = self.skills["writing"]

        self.assertIn("origin", writing)
        self.assertIn("adapt", writing)
        for reference in (
            "references/common-voice.md",
            "references/blog.md",
            "references/linkedin.md",
            "references/threads.md",
            "references/maily.md",
            "references/examples-blog.md",
            "references/examples-linkedin.md",
            "references/examples-threads.md",
            "references/examples-maily.md",
        ):
            with self.subTest(reference=reference):
                self.assertIn(reference, writing)
        self.assertNotIn("type: channel_pack", writing)
        self.assertNotIn("derived_from", writing)
        self.assertNotIn("type: content", writing)
        self.assertNotIn("Personal Branding/", writing)
        self.assertNotIn("VOICE -", writing)
        self.assertNotIn("canon:", writing)

    def test_writing_resolves_one_persona_before_source_lock(self):
        writing = self.skills["writing"]

        self.assertIn("references/personas.md", writing)
        self.assertIn("### 0. 발신 페르소나와 오디언스 잠금", writing)
        self.assertLess(
            writing.index("### 0. 발신 페르소나와 오디언스 잠금"),
            writing.index("### 1. 범위와 source 잠금"),
        )
        self.assertIn("명시했으면 다시 묻지 않는다", writing)
        self.assertIn("정확히 하나", writing)
        self.assertIn("오디언스", writing)
        self.assertIn("채널에 고정하지 않는다", writing)

    def test_writing_persona_reference_has_exact_public_choices(self):
        personas = self.writing_references["personas"]

        self.assertIn("## FDE", personas)
        self.assertIn("## 1인 빌더", personas)
        self.assertIn("공개 페르소나 선택지는 정확히 두 개", personas)
        self.assertIn("DA는 위시켓 내부 역할", personas)
        self.assertIn("AX Engineer", personas)
        self.assertIn("세 번째 페르소나", personas)
        self.assertIn("모든 지원 채널", personas)
        self.assertIn("오디언스는 글마다", personas)

    def test_writing_persona_reference_preserves_evidence_boundaries(self):
        personas = self.writing_references["personas"]

        self.assertIn("고객·회사 식별정보", personas)
        self.assertIn("수익", personas)
        self.assertIn("출시", personas)
        self.assertIn("근거가 있을 때만", personas)
        self.assertIn("주 페르소나", personas)
        self.assertNotIn("Personal Branding/", personas)
        self.assertNotIn("/Users/", personas)
        self.assertNotIn("[[", personas)

    def test_writing_shared_signals_do_not_resolve_persona_without_context(self):
        personas = self.writing_references["personas"]

        for signal in ("직접 만들었다", "자동화", "AX"):
            with self.subTest(signal=signal):
                self.assertIn(signal, personas)
        self.assertIn("공통 신호만으로는 페르소나를 추론하지 않는다", personas)
        self.assertIn("고객·조직 맥락", personas)
        self.assertIn("자기 제품·시장 가설 맥락", personas)
        self.assertIn(
            "둘 다 없으면 `FDE`와 `1인 빌더` 중 하나를 한 번만 묻는다",
            personas,
        )

    def test_writing_references_own_channel_contracts(self):
        expected = {
            "common": ("## 사실 경계", "## 금지 표현과 장치"),
            "blog": ("2,000~2,500자", "`##` 소제목 3~6개"),
            "linkedin": ("800~1,400자", "1,200~1,400자", "약 210자", "3~5개"),
            "threads": ("500자 이하", "5~7개", "본문 해시태그: 0개"),
            "maily": ("1행: 제목", "2행: 부제목", "3행: 빈 줄", "해시태그는 붙이지 않는다"),
        }
        for channel, contracts in expected.items():
            text = self.writing_references[channel]
            for contract in contracts:
                with self.subTest(channel=channel, contract=contract):
                    self.assertIn(contract, text)

    def test_writing_references_have_no_vault_runtime_dependency(self):
        forbidden = (
            "/Users/",
            "Personal Branding",
            "40_Channel_Packs",
            "_anchors",
            "VOICE -",
            "canon:",
            "CORE",
            "[[",
        )
        for name, text in self.writing_references.items():
            for token in forbidden:
                with self.subTest(reference=name, token=token):
                    self.assertNotIn(token, text)

    def test_writing_examples_are_style_only_and_loaded_after_thesis_lock(self):
        writing = self.skills["writing"]
        self.assertLess(
            writing.index("### 4. 채널별 논지 잠금"),
            writing.index("### 5. 톤 캘리브레이션"),
        )
        self.assertIn("논지를 잠근 뒤 요청 채널", writing)
        self.assertIn("사실·숫자·사례·비유·결론·고유 표현", writing)
        step_2 = writing.split("### 2. 필수 reference 로드", 1)[1].split(
            "### 3. 근거 장부", 1
        )[0]
        step_5 = writing.split("### 5. 톤 캘리브레이션", 1)[1].split(
            "### 6. 작성", 1
        )[0]
        self.assertIn("`examples-*`는 여기서 읽지 않는다", step_2)
        self.assertIn("references/examples-*.md", step_5)

        expected_counts = {
            "examples_blog": 3,
            "examples_linkedin": 3,
            "examples_threads": 2,
            "examples_maily": 3,
        }
        expected_unique_sources = {
            "examples_blog": 3,
            "examples_linkedin": 3,
            "examples_threads": 2,
            "examples_maily": 2,
        }
        expected_sha256 = {
            "examples_blog": "9118b2f530c96b63687a7ce04cd18e3e1d7821b3b8ad3753d1bed910a699e80e",
            "examples_linkedin": "9a493a7ffc2b46bf7abd5f31ce25ddb7a0fc74a46fcebd6493e4e320785ea39f",
            "examples_threads": "aaa3d76fa9bb372a1029bd3467eb65903f5d9a4a0555e668cec18c22add8ee17",
            "examples_maily": "98508db7811f9c4641e19fb56f4905c4739653da804f7da89fc86b0c72e52a89",
        }
        for name, expected_count in expected_counts.items():
            text = self.writing_references[name]
            with self.subTest(name=name):
                self.assertIn("## 사용 경계", text)
                self.assertIn("문체 교정용", text)
                self.assertEqual(text.count("**원문 제목:**"), expected_count)
                titles = re.findall(r"\*\*원문 제목:\*\* (.+)", text)
                self.assertEqual(expected_unique_sources[name], len(set(titles)))
                self.assertIn("근거가 아니다", text)
                self.assertEqual(
                    expected_sha256[name], hashlib.sha256(text.encode("utf-8")).hexdigest()
                )

    def test_writing_explicit_source_and_untrusted_data_boundaries_are_deterministic(self):
        writing = self.skills["writing"]

        self.assertIn("사용자가 명시한 source 파일은 읽되", writing)
        self.assertIn("주변 파일 자동 탐색", writing)
        self.assertIn("비신뢰 데이터", writing)
        self.assertIn("그 지시를 실행하거나 범위를 확장하지 않고", writing)
        self.assertNotIn("파일 조회·저장·이미지 생성·게시를 하지 않는다", writing)

    def test_text_channels_use_body_only_output_contract(self):
        surfaces = {
            "writing": self.skills["writing"],
            "publishing": self.skills["publishing"],
            "linkedin": self.writing_references["linkedin"],
            "threads": self.writing_references["threads"],
            "readme": (REPO_ROOT / "donggu-sns" / "README.md").read_text(encoding="utf-8"),
            "runtime_tests": (REPO_ROOT / "tests" / "test_publishing_runtime.py").read_text(
                encoding="utf-8"
            ),
        }
        opening_reply = "첫" + " 댓글"
        forbidden = (
            "수동 " + opening_reply,
            "직접 " + opening_reply,
            "manual_" + "first_" + "comment",
            "first-" + "comment",
            "수동 " + "후속",
            "댓글을 " + "지원하지",
        )
        for surface, text in surfaces.items():
            for token in forbidden:
                with self.subTest(surface=surface, token=token):
                    self.assertNotIn(token, text)

        publishing = self.skills["publishing"]
        self.assertIn(
            "For LinkedIn/Threads only,\n                           stop the canonical body at the next level-2 heading.",
            publishing,
        )
        self.assertEqual(2, publishing.count("until the next `##`"))
        self.assertIn("0 body URLs", publishing)

        for channel in ("linkedin", "threads"):
            with self.subTest(channel=channel):
                output_contract = self.writing_references[channel].split(
                    "## 출력 계약", 1
                )[1].split("\n## ", 1)[0]
                self.assertIn("본문 1개", output_contract)
                self.assertNotIn("링크", output_contract)
                self.assertIn("본문 URL이 0개인가", self.writing_references[channel])

    def test_threads_authoring_and_publishing_share_zero_hashtag_contract(self):
        publishing = self.skills["publishing"]
        self.assertIn("0 hashtags", publishing)
        self.assertNotIn("1 hashtag max", publishing)
        self.assertIn("500자를 넘거나 해시태그·본문 URL", publishing)

    def test_writing_is_one_umbrella_skill_not_per_channel_copies(self):
        skills_root = REPO_ROOT / "donggu-sns" / "skills"

        self.assertTrue((skills_root / "writing-social-content" / "SKILL.md").is_file())
        for name in (
            "writing-blog",
            "writing-linkedin",
            "writing-threads",
            "writing-maily",
        ):
            with self.subTest(name=name):
                self.assertFalse((skills_root / name).exists())

    def test_writing_no_longer_owns_blog_image_paths_or_embedding(self):
        image_skill = (
            REPO_ROOT / "donggu-sns" / "skills" / "get-ai-image" / "SKILL.md"
        ).read_text(encoding="utf-8")
        image_adapter = (
            REPO_ROOT
            / "donggu-sns"
            / "skills"
            / "publish-sns"
            / "prepare_blog_images.py"
        ).read_text(encoding="utf-8")

        self.assertIn("`writing-social-content`는 이미지 배치나 경로를 소유하지 않는다", image_skill)
        self.assertNotIn("[[writing-social-content]]", image_skill)
        self.assertNotIn("writing-social-content는 이미지를", image_adapter)

    def test_publishing_owns_ledger_backed_review_event(self):
        publishing = self.skills["publishing"]

        self.assertIn("발행 완료 이벤트", publishing)
        self.assertIn("existing DB trigger", publishing)
        self.assertIn("dry-run", publishing.lower())
        self.assertIn("CORE/Snippet/MOC", publishing)
        self.assertIn(
            "`dry_run=true` 성공 응답은 절대 `published_posts`에 INSERT하지 않는다",
            publishing,
        )

    def test_ontology_separates_inbox_selection_from_post_publish_curation(self):
        ontology_root = REPO_ROOT / "donggu-obsidian" / "skills" / "ontology"
        corpus = self.skills["ontology"] + "\n" + "\n".join(
            path.read_text(encoding="utf-8")
            for path in sorted((ontology_root / "references").glob("*.md"))
        )
        self.assertIn("Inbox selection is publication input only", corpus)
        self.assertIn("completed and approved publication only", corpus)
        self.assertIn("선택 → 추출 → 통합", corpus)
        self.assertIn("기존 CORE", corpus)
        self.assertIn("새 CORE", corpus)
        self.assertIn("CORE / Snippet / MOC", corpus)
        self.assertIn("age, note count", corpus.lower())

    def test_ontology_preview_is_separate_scoped_and_quiet(self):
        ontology_root = REPO_ROOT / "donggu-obsidian" / "skills" / "ontology"
        mutation = (ontology_root / "references" / "mutation.md").read_text(
            encoding="utf-8"
        )
        maintenance = (ontology_root / "references" / "maintenance.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("현재 Vault 변경 0건", mutation)
        self.assertIn("exact `수정안 보여줘`", mutation)
        self.assertIn("별도 메시지", mutation)
        self.assertIn("later persisted user message", mutation)
        self.assertIn("적용해줘", mutation)
        self.assertIn("proposal-only", mutation)
        self.assertNotIn("button", mutation.lower())
        self.assertNotIn("filesystem patch", mutation.lower())
        self.assertIn("read-back", mutation)
        self.assertIn("매일 전체 Vault를 스캔하지 않는다", maintenance)
        self.assertIn("정상 결과는 알리지 않는다", maintenance)

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
