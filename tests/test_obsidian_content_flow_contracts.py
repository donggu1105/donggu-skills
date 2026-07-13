from pathlib import Path
import json
import re
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
        self.assertIn(
            "`dry_run=true` 성공 응답은 절대 `published_posts`에 INSERT하지 않는다",
            publishing,
        )

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
        self.assertNotIn("weekly journal", decompose.lower())
        self.assertNotIn("주간 저널", decompose)

    def test_daily_health_reports_even_without_candidates(self):
        health = self.skills["health"]

        self.assertIn("후보가 없어도", health)
        report_format = health.split("## Report Format (standard)", 1)[1].split("```", 2)[1]
        for metric in (
            "recent Inbox count",
            "recent published count",
            "stalled Source count",
            "return-gap count",
            "link/schema candidate count",
        ):
            with self.subTest(metric=metric):
                self.assertRegex(report_format, rf"(?m)^- {re.escape(metric)}: [0N]$")

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

        for name in ("decompose", "health", "duplicates"):
            text = self.skills[name]
            self.assertIn("## Candidate handoff — mandatory STOP", text)
            handoff = text.split("## Candidate handoff — mandatory STOP", 1)[1]
            next_section = handoff.split("\n## ", 1)[0]
            for token in (
                "metadata-only",
                "candidate_code",
                "source_note_path",
                "source_sha256",
                "candidate_type",
                "proposed_changes",
                "CR-YYYYMMDD-NNNNNN",
                "core-review-approval",
                "STOP",
            ):
                with self.subTest(skill=name, token=token):
                    self.assertIn(token, next_section)

    def test_audited_candidate_skills_forbid_automatic_vault_mutation(self):
        required_guards = {
            "extract_core": ("자동 이동", "승인 전에 적용하지 않는다"),
            "decompose": ("Vault mutation은 수행하지 않는다", "후보 생성 뒤 종료"),
            "health": ("Vault mutation을 수행하지 않는다", "후보 생성 뒤 종료"),
            "duplicates": ("Vault mutation은 수행하지 않는다", "후보 생성 뒤 종료"),
        }
        forbidden = (
            "Create adopted atoms",
            "Wire bidirectionally",
            "recommend → STOP → create",
            "blanket approval covers",
            "act only on the user's per-item answer",
            "can be automated once adopted",
            "move to `99_Archive/`",
            "vault-wide find-replace",
            "actions can be automated",
        )
        approval_term = r"(?:approval|adoption|consent|adopted|user agrees|per-item answer)"
        mutation_term = r"(?:create|write|rewrite|modify|move|relocate|merge|archive|delete|replace|update|apply|wire|change)"
        contradictory_instruction = re.compile(
            rf"(?im)^\s*(?:after|once|upon|with|proceed)[^\n]*(?={approval_term})[^\n]*(?:{mutation_term})[^\n]*$"
        )
        for probe in (
            "After per-item consent, relocate the note and rewrite its status.",
            "After explicit adoption, archive the duplicate and rewrite all inbound citations.",
        ):
            self.assertRegex(probe, contradictory_instruction)
        for name, guards in required_guards.items():
            text = self.skills[name]
            for guard in guards:
                with self.subTest(skill=name, guard=guard):
                    self.assertIn(guard, text)
            if name != "extract_core":
                self.assertNotRegex(
                    text,
                    r"(?im)^##\s+(?:Action Rules(?:\s|\()|Remediation gates(?:\s|:))",
                )
                self.assertNotRegex(
                    text,
                    r"(?im)^\d+\.\s+\*\*(?:Create|Wire|Apply|Mutate|Remediate)\b",
                )
                for phrase in forbidden:
                    with self.subTest(skill=name, forbidden=phrase):
                        self.assertNotIn(phrase.lower(), text.lower())
                self.assertNotRegex(text, contradictory_instruction)

    def test_core_approval_conversation_gate_is_context_first_and_exact(self):
        approval = self.skills["approval"]
        gate = approval.split("## Conversation entry gate", 1)[1].split(
            "## Legacy entry gate", 1
        )[0]

        self.assertLess(
            approval.index("## Conversation entry gate"),
            approval.index("## Legacy entry gate"),
        )
        for command in ("수정안 보여줘", "적용해줘", "넘겨줘", "거절할게"):
            with self.subTest(command=command):
                self.assertIn(f"`{command}`", gate)
        for binding in (
            "validate-conversation.py",
            'SKILL_DIR="<absolute directory containing this loaded SKILL.md>"',
            "1526033497100390641",
            "736583402244931584",
            "get_core_review_conversation_by_thread",
            "exactly 1 row",
            "one thread = one candidate",
            "never from message text, nearby prose, memory, or a model guess",
        ):
            with self.subTest(binding=binding):
                self.assertIn(binding, gate)
        self.assertLess(
            gate.index("validate-conversation.py"),
            gate.index("get_core_review_conversation_by_thread"),
        )

    def test_core_approval_preview_is_native_bound_and_zero_write(self):
        approval = self.skills["approval"]
        preview = approval.split("### Preview — `수정안 보여줘`", 1)[1].split(
            "### Apply — `적용해줘`", 1
        )[0]
        ordered = (
            "`thread_open`",
            "recovery preflight",
            "`proposed`",
            "`source_sha256`",
            "`donggu_core_plan`",
            "`render-preview.py`",
            "`save_core_review_preview(...)`",
            "post only the returned `content`",
        )
        positions = [preview.index(token) for token in ordered]
        self.assertEqual(sorted(positions), positions)
        for contract in (
            "(`fix_link`, `replace`)",
            "(`link_existing`, `replace`)",
            "(`new_core`, `create_core_with_backlink`)",
            "exact 8-key envelope",
            "receipt_id",
            "preview_hash",
            "15 minutes",
            "Vault changes: 0",
        ):
            with self.subTest(contract=contract):
                self.assertIn(contract, preview)

    def test_core_approval_apply_claims_before_internal_approval_and_apply(self):
        approval = self.skills["approval"]
        apply = approval.split("### Apply — `적용해줘`", 1)[1].split(
            "### Hold and reject", 1
        )[0]
        ordered = (
            "`previewed`",
            "unexpired",
            "recovery preflight",
            "`claim_core_review_conversation_apply(...)`",
            "`previewed → applying`",
            "`proposed → processing`",
            'approval_text = f"{candidate_code} 승인"',
            "`donggu_core_apply(receipt_id)`",
            "after-hash read-back",
            "`complete_core_review_conversation(..., 'applied', ...)`",
            "`--ack-candidate`",
        )
        positions = [apply.index(token) for token in ordered]
        self.assertEqual(sorted(positions), positions)
        for contract in (
            "source_sha256",
            "preview_hash",
            "exactly 1 row",
            "duplicate apply",
            "never synthesize it from arbitrary natural language",
            "exit 70",
            "exit 4",
            "exit 5",
            "exit 6",
            "never retry apply blindly",
        ):
            with self.subTest(contract=contract):
                self.assertIn(contract, apply)

    def test_core_approval_terminal_and_legacy_paths_cannot_bypass_thread_state(self):
        approval = self.skills["approval"]
        terminal = approval.split("### Hold and reject", 1)[1].split(
            "## Legacy entry gate", 1
        )[0]
        for contract in (
            "hold_core_review_conversation(...) only",
            "reject_core_review_conversation(...) only",
            "terminal",
            "Vault changes: 0",
        ):
            with self.subTest(contract=contract):
                self.assertIn(contract, terminal)
        self.assertIn(
            "A candidate bound to a conversation thread may never use this legacy path",
            approval,
        )
        self.assertIn("blanket or multi-candidate approval is forbidden", approval)
        self.assertIn("Never expose candidate code, receipt_id", approval)
        self.assertIn("Never mutate Vault files directly", approval)

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
