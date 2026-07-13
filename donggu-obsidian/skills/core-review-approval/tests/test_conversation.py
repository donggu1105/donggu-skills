#!/usr/bin/env python3
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
VALIDATOR = HERE.parent / "scripts" / "validate-conversation.py"
RENDERER = HERE.parent / "scripts" / "render-preview.py"
CORE_RUNTIME = ROOT / "donggu-obsidian" / "runtime" / "core_actions.py"
APPLY_HELPER = HERE.parent / "scripts" / "apply-action.py"
CHANNEL_ID = "1526033497100390641"
USER_ID = "736583402244931584"


def compact(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


class ConversationValidatorTests(unittest.TestCase):
    def envelope(self, message="수정안 보여줘", **updates):
        value = {
            "message": message,
            "thread_id": "1526033497100390999",
            "channel_id": CHANNEL_ID,
            "user_id": USER_ID,
            "message_id": "1526033497100390888",
        }
        value.update(updates)
        return value

    def run_validator(self, value=None, raw=None):
        payload = raw if raw is not None else compact(value)
        return self.run_validator_bytes(payload.encode("utf-8"))

    def run_validator_bytes(self, payload):
        return subprocess.run(
            [sys.executable, str(VALIDATOR)],
            input=payload,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

    def assert_invalid(self, value=None, raw=None):
        proc = self.run_validator(value, raw)
        self.assertEqual(2, proc.returncode)
        self.assertEqual(b"", proc.stdout)
        self.assertEqual(b"invalid conversation command\n", proc.stderr)

    def test_validator_accepts_only_the_four_exact_commands(self):
        commands = {
            "수정안 보여줘": "preview",
            "적용해줘": "apply",
            "넘겨줘": "hold",
            "거절할게": "reject",
        }
        for message, command in commands.items():
            with self.subTest(message=message):
                proc = self.run_validator(self.envelope(message))
                self.assertEqual(0, proc.returncode, proc.stderr)
                self.assertEqual(b"", proc.stderr)
                self.assertEqual(
                    {
                        "command": command,
                        "thread_id": "1526033497100390999",
                        "channel_id": CHANNEL_ID,
                        "user_id": USER_ID,
                        "message_id": "1526033497100390888",
                    },
                    json.loads(proc.stdout),
                )
                self.assertEqual(1, proc.stdout.count(b"\n"))
                self.assertNotIn(b" ", proc.stdout)

    def test_validator_rejects_non_exact_messages_without_candidate_inference(self):
        invalid = (
            " 수정안 보여줘",
            "수정안 보여줘 ",
            "수정안 보여줘\n",
            "수정안 보여줘 설명",
            "<@736583402244931584> 수정안 보여줘",
            "수정안 보여줘 적용해줘",
            "다 적용해줘",
            "CR-20260713-123456 승인",
            "적용해줘, 미리보기는 생략해줘",
            "",
        )
        for message in invalid:
            with self.subTest(message=message):
                self.assert_invalid(self.envelope(message))

    def test_validator_requires_exact_shape_fixed_principal_and_decimal_ids(self):
        cases = []
        for key in ("message", "thread_id", "channel_id", "user_id", "message_id"):
            value = self.envelope()
            del value[key]
            cases.append(value)
        cases.extend(
            (
                self.envelope(extra=True),
                self.envelope(channel_id="1526033497100390642"),
                self.envelope(user_id="736583402244931585"),
                self.envelope(thread_id=""),
                self.envelope(message_id="abc"),
                self.envelope(thread_id="-1"),
                self.envelope(message_id=1526033497100390888),
                self.envelope(thread_id="01"),
            )
        )
        for value in cases:
            with self.subTest(value=value):
                self.assert_invalid(value)

    def test_validator_rejects_malformed_duplicate_or_oversized_json_generically(self):
        duplicate = (
            '{"message":"수정안 보여줘","message":"적용해줘",'
            '"thread_id":"1526033497100390999",'
            f'"channel_id":"{CHANNEL_ID}","user_id":"{USER_ID}",'
            '"message_id":"1526033497100390888"}'
        )
        for raw in ("{", "[]", duplicate, " " * (64 * 1024 + 1)):
            with self.subTest(raw=raw[:30]):
                self.assert_invalid(raw=raw)
        proc = self.run_validator_bytes(b"\xff")
        self.assertEqual(
            (2, b"", b"invalid conversation command\n"),
            (proc.returncode, proc.stdout, proc.stderr),
        )


class PreviewRendererTests(unittest.TestCase):
    def load_core_runtime(self):
        spec = importlib.util.spec_from_file_location(
            "donggu_core_runtime_preview_tests", CORE_RUNTIME
        )
        if spec is None or spec.loader is None:
            raise ImportError(f"cannot load {CORE_RUNTIME}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module

    def replace_candidate(self, **updates):
        value = {
            "candidate_code": "CR-20260713-000001",
            "candidate_type": "fix_link",
            "source_note_path": "10_Sources/대화형 승인.md",
            "source_sha256": "0" * 64,
            "target_note_paths": ["20_Core/정확한 대상.md"],
            "claim": "표시하지 않는 모델 제안",
            "relationship": "complement",
            "rationale": "표시하지 않는 모델 근거",
            "proposed_changes": [{
                "op": "replace",
                "schema_version": 1,
                "old": "[[깨진 링크]]",
                "new": "[[20_Core/정확한 대상|깨진 링크]]",
            }],
            "risk": "low",
        }
        value.update(updates)
        return value

    def create_candidate(self, **updates):
        action = {
            "op": "create_core_with_backlink",
            "schema_version": 1,
            "template_version": 1,
            "core_path": "20_Core/CORE - 검증은 실행의 일부다.md",
            "moc_path": "60_MOCs/MOC - 검증.md",
            "moc_sha256": "a" * 64,
            "trace_field": "extracted_to",
        }
        value = {
            "candidate_code": "CR-20260713-000002",
            "candidate_type": "new_core",
            "source_note_path": "10_Sources/대화형 승인.md",
            "source_sha256": "0" * 64,
            "target_note_paths": sorted([action["core_path"], action["moc_path"]]),
            "claim": "검증은 실행의 일부다",
            "relationship": "new",
            "rationale": "표시하지 않는 모델 근거",
            "proposed_changes": [action],
            "risk": "low",
        }
        value.update(updates)
        return value

    def plan(self, candidate, **updates):
        action = candidate["proposed_changes"][0]
        source = candidate["source_note_path"]
        if action["op"] == "replace":
            paths = [source]
            hashes = {source: {"before": candidate["source_sha256"], "after": "1" * 64}}
        else:
            core = action["core_path"]
            moc = action["moc_path"]
            paths = sorted([source, core, moc])
            hashes = {
                source: {"before": candidate["source_sha256"], "after": "1" * 64},
                core: {"before": None, "after": "2" * 64},
                moc: {"before": action["moc_sha256"], "after": "3" * 64},
            }
        envelope = {
            "schema_version": 1,
            "candidate_code": candidate["candidate_code"],
            "candidate_type": candidate["candidate_type"],
            "source_note_path": candidate["source_note_path"],
            "source_sha256": candidate["source_sha256"],
            "claim": candidate["claim"],
            "target_note_paths": candidate["target_note_paths"],
            "action": action,
        }
        envelope_sha256 = hashlib.sha256(
            json.dumps(
                envelope, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            ).encode("utf-8")
        ).hexdigest()
        value = {
            "status": "planned",
            "receipt_id": "privateReceiptCapability_1234567890",
            "expires_at": 2000000000,
            "candidate_code": candidate["candidate_code"],
            "envelope_sha256": envelope_sha256,
            "paths": paths,
            "hashes": hashes,
        }
        value.update(updates)
        return value

    def runtime_envelope(self, candidate):
        action = candidate["proposed_changes"][0]
        return {
            "schema_version": 1,
            "candidate_code": candidate["candidate_code"],
            "candidate_type": candidate["candidate_type"],
            "source_note_path": candidate["source_note_path"],
            "source_sha256": candidate["source_sha256"],
            "claim": candidate["claim"],
            "target_note_paths": candidate["target_note_paths"],
            "action": action,
        }

    def run_renderer(self, candidate=None, plan=None, raw=None):
        payload = raw if raw is not None else compact({"candidate": candidate, "plan": plan})
        return self.run_renderer_bytes(payload.encode("utf-8"))

    def run_renderer_bytes(self, payload):
        return subprocess.run(
            [sys.executable, str(RENDERER)],
            input=payload,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

    def assert_render_invalid(self, candidate=None, plan=None, raw=None):
        proc = self.run_renderer(candidate, plan, raw)
        self.assertEqual(2, proc.returncode)
        self.assertEqual(b"", proc.stdout)
        self.assertEqual(b"preview rendering failed\n", proc.stderr)

    def render(self, candidate):
        proc = self.run_renderer(candidate, self.plan(candidate))
        self.assertEqual(0, proc.returncode, proc.stderr)
        self.assertEqual(b"", proc.stderr)
        self.assertEqual(1, proc.stdout.count(b"\n"))
        return json.loads(proc.stdout)

    def expected_preview_hash(self, candidate, plan):
        binding = {
            "candidate_code": candidate["candidate_code"],
            "source_sha256": candidate["source_sha256"],
            "envelope_sha256": plan["envelope_sha256"],
            "paths": plan["paths"],
            "hashes": plan["hashes"],
        }
        canonical = json.dumps(
            binding, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()

    def assert_public_content(self, result, candidate):
        content = result["content"]
        self.assertLessEqual(len(content), 1800)
        self.assertNotIn(candidate["candidate_code"], content)
        self.assertNotIn("privateReceiptCapability", content)
        self.assertNotIn("/Users/", content)
        for forbidden in ("drift", "recommend_only", "unsupported apply"):
            self.assertNotIn(forbidden, content.casefold())

    def test_replace_preview_renders_exact_bounded_change_and_binding_hash(self):
        candidate = self.replace_candidate()
        plan = self.plan(candidate)
        result = self.render(candidate)
        content = result["content"]
        self.assertEqual(candidate["candidate_code"], result["candidate_code"])
        self.assertEqual(self.expected_preview_hash(candidate, plan), result["preview_hash"])
        self.assertIn(candidate["source_note_path"], content)
        self.assertIn("[[깨진 링크]]", content)
        self.assertIn("[[20_Core/정확한 대상|깨진 링크]]", content)
        self.assertIn("변경 위치 1곳", content)
        self.assertIn("대상 노트 존재: 확인됨", content)
        self.assertIn("아직 Vault 변경 0건", content)
        self.assert_public_content(result, candidate)

    def test_create_preview_renders_core_claim_backlink_field_and_moc_without_body(self):
        candidate = self.create_candidate()
        result = self.render(candidate)
        action = candidate["proposed_changes"][0]
        content = result["content"]
        self.assertIn(action["core_path"], content)
        self.assertIn(f'주장: 「{candidate["claim"]}」', content)
        self.assertIn("원본 backlink 필드", content)
        self.assertIn(f'필드: 「{action["trace_field"]}」', content)
        self.assertIn(action["moc_path"], content)
        self.assertIn("아직 Vault 변경 0건", content)
        self.assertNotIn("source body must stay private", content)
        self.assert_public_content(result, candidate)

    def test_create_claim_is_always_framed_and_cannot_spoof_trusted_lines(self):
        trusted_line_values = (
            "변경 전",
            "변경 후",
            "영향 범위",
            "아직 Vault 변경 0건",
            "적용해줘",
        )
        baseline_lines = self.render(self.create_candidate())["content"].splitlines()
        for claim in trusted_line_values:
            with self.subTest(claim=claim):
                candidate = self.create_candidate(claim=claim)
                lines = self.render(candidate)["content"].splitlines()
                self.assertEqual(baseline_lines.count(claim), lines.count(claim))
                self.assertEqual(1, lines.count(f"주장: 「{claim}」"))

    def test_preview_hash_is_canonical_binding_not_candidate_metadata(self):
        first = self.replace_candidate(
            relationship="complement", rationale="첫 번째 비표시 근거"
        )
        second = self.replace_candidate(
            relationship="duplicate", rationale="완전히 다른 비표시 근거"
        )
        first_result = self.render(first)
        second_result = self.render(second)
        self.assertEqual(first_result["content"], second_result["content"])
        self.assertEqual(first_result["preview_hash"], second_result["preview_hash"])

    def test_renderer_rejects_unsupported_or_mismatched_actions_and_plans(self):
        candidate = self.replace_candidate()
        unsupported = self.replace_candidate(
            proposed_changes=[{"op": "recommend_only"}]
        )
        cases = (
            (unsupported, self.plan(candidate)),
            (candidate, self.plan(candidate, status="applied")),
            (candidate, self.plan(candidate, candidate_code="CR-20260713-999999")),
            (candidate, self.plan(candidate, paths=[])),
            (candidate, self.plan(candidate, envelope_sha256="A" * 64)),
        )
        for bad_candidate, bad_plan in cases:
            with self.subTest(candidate=bad_candidate, plan=bad_plan):
                self.assert_render_invalid(bad_candidate, bad_plan)

    def test_renderer_rejects_private_control_oversized_or_source_body_data(self):
        private_cases = (
            self.replace_candidate(source_note_path="/Users/joey/Vault/private.md"),
            self.replace_candidate(proposed_changes=[{
                "op": "replace", "schema_version": 1,
                "old": "user@example.com", "new": "[[20_Core/정확한 대상]]",
            }]),
            self.replace_candidate(proposed_changes=[{
                "op": "replace", "schema_version": 1,
                "old": "[[깨진 링크]]", "new": "Bearer abc.def.secret",
            }]),
            self.create_candidate(claim="비밀\x01본문"),
            self.create_candidate(claim="가" * 501),
            {**self.create_candidate(), "source_body": "source body must stay private"},
            self.create_candidate(claim="recommend_only 내부 상태"),
        )
        for candidate in private_cases:
            with self.subTest(candidate=candidate):
                plan_candidate = self.create_candidate() if candidate.get("candidate_type") == "new_core" else self.replace_candidate()
                self.assert_render_invalid(candidate, self.plan(plan_candidate))

    def test_renderer_rejects_structurally_unsafe_relative_paths(self):
        bad_paths = (
            "/Volumes/PrivateVault/secret.md",
            "/opt/private/secret.md",
            "~/Vault/secret.md",
            "C:/Vault/secret.md",
            "\\\\server\\share\\secret.md",
            "file:10_Sources/secret.md",
            "https://example.com/secret.md",
            "urn:private:secret.md",
            "10_Sources/../secret.md",
            "10_Sources/./secret.md",
            "10_Sources\\secret.md",
            "10_Sources/e\u0301.md",
            "10_Sources/safe\u202Egnidnep.md",
            "10_Sources/private\ue000.md",
            "10_Sources/unassigned\u0378.md",
        )
        for path in bad_paths:
            with self.subTest(path=path):
                candidate = self.replace_candidate(source_note_path=path)
                self.assert_render_invalid(candidate, self.plan(candidate))

    def test_renderer_checks_path_entropy_per_token_not_across_descriptive_paths(self):
        safe_paths = (
            "10_Sources/source-create.md",
            "10_Sources/research_notes/source-create-review-notes.md",
            "10_Sources/product-launch-notes/source-create-review-2026.md",
        )
        for path in safe_paths:
            with self.subTest(path=path):
                candidate = self.replace_candidate(source_note_path=path)
                result = self.render(candidate)
                self.assertIn(path, result["content"])

        safe_target = "20_Core/research_notes/CORE-source-create-review-notes.md"
        candidate = self.replace_candidate(
            target_note_paths=[safe_target],
            proposed_changes=[{
                "op": "replace",
                "schema_version": 1,
                "old": "[[깨진 링크]]",
                "new": f"[[{safe_target[:-3]}|깨진 링크]]",
            }],
        )
        result = self.render(candidate)
        self.assertIn(candidate["proposed_changes"][0]["new"], result["content"])

        malicious_segment = "aB3dE5fG7hJ9kL2mN4pQ6rS8tV0xY1zC"
        candidate = self.replace_candidate(
            source_note_path=f"10_Sources/{malicious_segment}/safe-note.md"
        )
        self.assert_render_invalid(candidate, self.plan(candidate))

    def test_renderer_requires_exact_bounded_wikilinks_and_claim_display_grammar(self):
        malformed_links = (
            ("prefix [[깨진 링크]]", "[[20_Core/정확한 대상|깨진 링크]]"),
            ("[[깨진 링크]] suffix", "[[20_Core/정확한 대상|깨진 링크]]"),
            ("[[깨진 링크]]", "**[[20_Core/정확한 대상|깨진 링크]]**"),
            ("[[깨진 링크]]", "`[[20_Core/정확한 대상|깨진 링크]]`"),
        )
        for old, new in malformed_links:
            with self.subTest(old=old, new=new):
                candidate = self.replace_candidate(proposed_changes=[{
                    "op": "replace", "schema_version": 1, "old": old, "new": new,
                }])
                self.assert_render_invalid(candidate, self.plan(candidate))

        bad_claims = (
            "claim/with/slash",
            "claim\\with\\backslash",
            "**강조 주장**",
            "`코드 주장`",
            "# 제목 주장",
            "@everyone 알림",
            "safe\u202Egnidnep",
            "line\u2028separator",
            "paragraph\u2029separator",
            "private\ue000value",
            "unassigned\u0378value",
        )
        for claim in bad_claims:
            with self.subTest(claim=claim):
                candidate = self.create_candidate(claim=claim)
                self.assert_render_invalid(candidate, self.plan(candidate))
        surrogate_candidate = self.create_candidate(claim="\ud800")
        surrogate_raw = json.dumps(
            {"candidate": surrogate_candidate, "plan": {}},
            ensure_ascii=True,
            separators=(",", ":"),
        )
        self.assert_render_invalid(raw=surrogate_raw)

    def test_renderer_rejects_actual_receipt_id_anywhere_in_public_content(self):
        receipt_id = "ReceiptCapabilityAllLettersOnly"
        candidate = self.replace_candidate(proposed_changes=[{
            "op": "replace",
            "schema_version": 1,
            "old": f"[[{receipt_id}]]",
            "new": "[[20_Core/정확한 대상|깨진 링크]]",
        }])
        self.assert_render_invalid(candidate, self.plan(candidate, receipt_id=receipt_id))

    def test_real_runtime_plan_renders_safely_without_source_bytes_or_mtime_changes(self):
        module = self.load_core_runtime()
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            vault = base / "vault"
            for root in ("10_Sources", "20_Core", "40_Snippets", "50_Channel_Packs", "60_MOCs"):
                (vault / root).mkdir(parents=True)
            candidate = self.replace_candidate(
                source_note_path="10_Sources/source.md",
                target_note_paths=["20_Core/Target.md"],
                proposed_changes=[{
                    "op": "replace",
                    "schema_version": 1,
                    "old": "[[Broken]]",
                    "new": "[[20_Core/Target|Broken]]",
                }],
            )
            source = vault / candidate["source_note_path"]
            source_bytes = b"---\ntype: source\n---\n\n[[Broken]]\n"
            source.write_bytes(source_bytes)
            (vault / "20_Core/Target.md").write_text("target\n", encoding="utf-8")
            candidate["source_sha256"] = hashlib.sha256(source_bytes).hexdigest()
            before = (source.read_bytes(), source.stat().st_mtime_ns)
            runtime = module.CoreActionRuntime(
                receipt_root=base / "receipts",
                helper_path=APPLY_HELPER,
            )

            plan = runtime.plan(
                vault,
                self.runtime_envelope(candidate),
                session_id="preview-session",
                turn_id="preview-turn",
                user_message_id=1,
            )
            self.assertEqual(
                {"status", "receipt_id", "expires_at", "candidate_code", "envelope_sha256", "paths", "hashes"},
                set(plan),
            )
            proc = self.run_renderer(candidate, plan)
            self.assertEqual(0, proc.returncode, proc.stderr)
            result = json.loads(proc.stdout)
            self.assertEqual(self.expected_preview_hash(candidate, plan), result["preview_hash"])
            self.assertNotIn(plan["receipt_id"], result["content"])
            self.assertEqual(before, (source.read_bytes(), source.stat().st_mtime_ns))

    def test_real_runtime_create_plan_renders_descriptive_source_without_vault_changes(self):
        module = self.load_core_runtime()
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            vault = base / "vault"
            for root in ("10_Sources", "20_Core", "40_Snippets", "50_Channel_Packs", "60_MOCs"):
                (vault / root).mkdir(parents=True)

            source_rel = "10_Sources/source-create.md"
            source = vault / source_rel
            source_bytes = b"---\ntype: source\nextracted_to: []\n---\n\nCreate source body.\n"
            source.write_bytes(source_bytes)
            moc_rel = "60_MOCs/MOC - Creation.md"
            moc = vault / moc_rel
            moc_bytes = b"---\ntype: moc\n---\n\n# Creation\n"
            moc.write_bytes(moc_bytes)
            core_rel = "20_Core/CORE - Creation requires verification.md"
            core = vault / core_rel
            action = {
                "op": "create_core_with_backlink",
                "schema_version": 1,
                "template_version": 1,
                "core_path": core_rel,
                "moc_path": moc_rel,
                "moc_sha256": hashlib.sha256(moc_bytes).hexdigest(),
                "trace_field": "extracted_to",
            }
            candidate = self.create_candidate(
                source_note_path=source_rel,
                source_sha256=hashlib.sha256(source_bytes).hexdigest(),
                target_note_paths=sorted([core_rel, moc_rel]),
                claim="Creation requires verification",
                proposed_changes=[action],
            )
            before = {
                source_rel: (source.read_bytes(), source.stat().st_mtime_ns),
                moc_rel: (moc.read_bytes(), moc.stat().st_mtime_ns),
            }
            self.assertFalse(core.exists())
            runtime = module.CoreActionRuntime(
                receipt_root=base / "receipts",
                helper_path=APPLY_HELPER,
            )

            plan = runtime.plan(
                vault,
                self.runtime_envelope(candidate),
                session_id="create-preview-session",
                turn_id="create-preview-turn",
                user_message_id=1,
            )
            self.assertEqual(
                {"status", "receipt_id", "expires_at", "candidate_code", "envelope_sha256", "paths", "hashes"},
                set(plan),
            )
            proc = self.run_renderer(candidate, plan)
            self.assertEqual(0, proc.returncode, proc.stderr)
            result = json.loads(proc.stdout)
            self.assertEqual(self.expected_preview_hash(candidate, plan), result["preview_hash"])
            self.assertIn("주장: 「Creation requires verification」", result["content"])
            self.assert_public_content(result, candidate)
            self.assertEqual(
                before,
                {
                    source_rel: (source.read_bytes(), source.stat().st_mtime_ns),
                    moc_rel: (moc.read_bytes(), moc.stat().st_mtime_ns),
                },
            )
            self.assertFalse(core.exists())

    def test_real_runtime_bound_malicious_visible_fields_are_rejected_without_leak(self):
        module = self.load_core_runtime()
        malicious_values = (
            "/Volumes/PrivateVault/secret.md",
            "/opt/private/secret.md",
            "-----BEGIN PRIVATE KEY-----",
            "AKIAIOSFODNN7EXAMPLE",
            "sk-proj-AbCdEf0123456789AbCdEf0123456789",
            "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.signature",
            "eyJhbGciOiJub25lIn0.eyJzdWIiOiIxIn0.",
            "aB3dE5fG7hJ9kL2mN4pQ6rS8tV0xY1zC",
            "api key",
            "access key",
            "credential",
            "token",
            "password",
            "private key",
            "@everyone",
            "@here",
            "hello@world",
            "<@123456>",
            "<@&123456>",
            "<#123456>",
            "**markdown**",
            "`inline code`",
            "# heading",
            "safe\u202Egnidnep",
            "line\u2028separator",
            "paragraph\u2029separator",
        )
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            vault = base / "vault"
            for root in ("10_Sources", "20_Core", "40_Snippets", "50_Channel_Packs", "60_MOCs"):
                (vault / root).mkdir(parents=True)
            (vault / "20_Core/Target.md").write_text("target\n", encoding="utf-8")
            runtime = module.CoreActionRuntime(
                receipt_root=base / "receipts",
                helper_path=APPLY_HELPER,
            )
            for index, malicious in enumerate(malicious_values):
                with self.subTest(malicious=malicious):
                    source_rel = f"10_Sources/source-{index}.md"
                    source = vault / source_rel
                    old = f"[[20_Core/Target|{malicious}]]"
                    source_bytes = f"---\ntype: source\n---\n\n{old}\n".encode("utf-8")
                    source.write_bytes(source_bytes)
                    candidate = self.replace_candidate(
                        candidate_code=f"CR-20260713-{index + 100:06d}",
                        source_note_path=source_rel,
                        source_sha256=hashlib.sha256(source_bytes).hexdigest(),
                        target_note_paths=["20_Core/Target.md"],
                        proposed_changes=[{
                            "op": "replace",
                            "schema_version": 1,
                            "old": old,
                            "new": "[[20_Core/Target]]",
                        }],
                    )
                    before = (source.read_bytes(), source.stat().st_mtime_ns)
                    plan = runtime.plan(
                        vault,
                        self.runtime_envelope(candidate),
                        session_id="preview-session",
                        turn_id=f"preview-turn-{index}",
                        user_message_id=index + 1,
                    )
                    self.assertEqual(
                        {"status", "receipt_id", "expires_at", "candidate_code", "envelope_sha256", "paths", "hashes"},
                        set(plan),
                    )
                    proc = self.run_renderer(candidate, plan)
                    self.assertEqual(2, proc.returncode)
                    self.assertEqual(b"", proc.stdout)
                    self.assertEqual(b"preview rendering failed\n", proc.stderr)
                    self.assertNotIn(malicious, (proc.stdout + proc.stderr).decode("utf-8"))
                    self.assertEqual(before, (source.read_bytes(), source.stat().st_mtime_ns))

    def test_renderer_rejects_extra_duplicate_malformed_and_deep_json_generically(self):
        candidate = self.replace_candidate()
        plan = self.plan(candidate)
        extra = compact({"candidate": candidate, "plan": plan, "extra": True})
        duplicate = (
            '{"candidate":' + compact(candidate) + ',"candidate":' + compact(candidate)
            + ',"plan":' + compact(plan) + '}'
        )
        deep = '{"candidate":' + ('[' * 1500) + ('0' + ']' * 1500) + ',"plan":{}}'
        for raw in ("{", extra, duplicate, deep, " " * (1024 * 1024 + 1)):
            with self.subTest(raw=raw[:40]):
                self.assert_render_invalid(raw=raw)
        proc = self.run_renderer_bytes(b"\xff")
        self.assertEqual(
            (2, b"", b"preview rendering failed\n"),
            (proc.returncode, proc.stdout, proc.stderr),
        )


if __name__ == "__main__":
    unittest.main()
