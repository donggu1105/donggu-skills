#!/usr/bin/env python3
"""Behavioral contract for the deterministic minimal approval workflow.

The database ledger and Discord transport are fakes.  The registered Hermes
handlers, SessionDB-shaped rows, portable helper, receipt store, and Vault are
real so the successful path proves the natural command reaches one mutation.
"""
from __future__ import annotations

import hashlib
import importlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
import uuid
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "donggu-obsidian"
HELPER = PACKAGE / "skills" / "core-review-approval" / "scripts" / "apply-action.py"
RENDERER = PACKAGE / "skills" / "core-review-approval" / "scripts" / "render-preview.py"
CHANNEL_ID = "1526033497100390641"
USER_ID = "736583402244931584"
THREAD_ID = "1526033497100390999"


def load_package(module_name: str):
    spec = importlib.util.spec_from_file_location(
        module_name,
        PACKAGE / "__init__.py",
        submodule_search_locations=[str(PACKAGE)],
    )
    if spec is None or spec.loader is None:
        raise ImportError("cannot load donggu-obsidian package")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def canonical_sha(value) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class FakeContext:
    def __init__(self):
        self.tools = []

    def register_tool(self, **kwargs):
        self.tools.append(kwargs)


class LedgerOrderError(RuntimeError):
    pass


class FakeDeterministicLedger:
    """Small in-memory model of the checked-in PostgreSQL state machine."""

    def __init__(self, candidate: dict):
        self.candidate = candidate
        self.candidate_state = "proposed"
        self.state = "thread_open"
        self.delivery = None
        self.preview_message_id = None
        self.decision_message_id = None
        self.receipt_id = None
        self.receipt_expires_at = None
        self.preview_hash = None
        self.envelope_hash = None
        self.after_hashes_sha256 = None
        self.completion_nonce = None
        self.completion_state = None
        self.events = []

    def prepare(self, *, receipt_id, expires_at, preview_hash, envelope_hash):
        if self.state != "thread_open" or self.candidate_state != "proposed":
            raise LedgerOrderError("preview prepare requires an open proposed row")
        if self.preview_message_id is not None:
            raise LedgerOrderError("prepare cannot store a pre-send message id")
        self.state = "previewed"
        self.delivery = "prepared"
        self.receipt_id = receipt_id
        self.receipt_expires_at = expires_at
        self.preview_hash = preview_hash
        self.envelope_hash = envelope_hash
        self.events.append("db_prepare")

    def finalize_sent(self, actual_message_id: str):
        if self.state != "previewed" or self.delivery != "prepared":
            raise LedgerOrderError("sent finalize requires prepared")
        if not actual_message_id:
            raise LedgerOrderError("actual Discord message id is required")
        self.delivery = "sent"
        self.preview_message_id = actual_message_id
        self.events.append("db_sent_finalize")

    def mark_delivery_ambiguous(self):
        if self.state != "previewed" or self.delivery != "prepared":
            raise LedgerOrderError("delivery ambiguity requires prepared")
        self.delivery = "ambiguous"
        self.events.append("db_delivery_ambiguous")

    def claim_apply(self, *, receipt_id, decision_message_id, preview_hash, envelope_hash):
        if self.state != "previewed" or self.delivery != "sent":
            raise LedgerOrderError("atomic claim requires a sent preview")
        if (
            receipt_id != self.receipt_id
            or preview_hash != self.preview_hash
            or envelope_hash != self.envelope_hash
        ):
            raise LedgerOrderError("atomic claim binding mismatch")
        self.state = "applying"
        self.candidate_state = "processing"
        self.decision_message_id = decision_message_id
        self.events.append("db_atomic_claim")
        return {"receipt_id": self.receipt_id}

    def require_claimed(self, receipt_id: str):
        if (
            self.state != "applying"
            or self.candidate_state != "processing"
            or receipt_id != self.receipt_id
        ):
            raise LedgerOrderError("native apply is outside the mapped claimed workflow")

    def release(self, *, receipt_id):
        self.require_claimed(receipt_id)
        self.state = "previewed"
        self.candidate_state = "proposed"
        self.events.append("db_release")

    def complete(self, *, receipt_id, after_hashes_sha256, completion_nonce):
        if self.state != "applying" or self.candidate_state != "processing":
            raise LedgerOrderError("DB complete requires applying/processing")
        if receipt_id != self.receipt_id:
            raise LedgerOrderError("DB complete receipt mismatch")
        if str(uuid.UUID(completion_nonce)) != completion_nonce:
            raise LedgerOrderError("completion nonce must be canonical")
        self.state = "applied"
        self.candidate_state = "applied"
        self.after_hashes_sha256 = after_hashes_sha256
        self.completion_nonce = completion_nonce
        self.completion_state = "readback_complete_ack_pending"
        self.events.append("db_complete")
        return {"completion_nonce": completion_nonce}

    def require_ack_binding(self, *, receipt_id, completion_nonce):
        if (
            self.state != "applied"
            or self.completion_state != "readback_complete_ack_pending"
            or receipt_id != self.receipt_id
        ):
            raise LedgerOrderError("native ack is outside the mapped completed workflow")
        if completion_nonce != self.completion_nonce:
            raise LedgerOrderError("completion nonce mismatch")

    def confirm_ack(self, *, receipt_id, completion_nonce, after_hashes_sha256):
        self.require_ack_binding(
            receipt_id=receipt_id, completion_nonce=completion_nonce
        )
        if after_hashes_sha256 != self.after_hashes_sha256:
            raise LedgerOrderError("DB ack digest mismatch")
        self.completion_state = "native_ack_complete"
        self.events.append("db_ack_confirm")


class MinimalApprovalBehavioralTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.vault = self.base / "vault"
        for name in ("10_Sources", "20_Core", "40_Snippets", "50_Channel_Packs", "60_MOCs"):
            (self.vault / name).mkdir(parents=True)
        self.source_rel = "10_Sources/source.md"
        self.source_bytes = b"---\ntype: source\n---\n\n[[Broken]]\n"
        (self.vault / self.source_rel).write_bytes(self.source_bytes)
        self.target_rel = "20_Core/Target.md"
        (self.vault / self.target_rel).write_text("target\n", encoding="utf-8")
        self.envelope = {
            "schema_version": 1,
            "candidate_code": "CR-20260714-000001",
            "candidate_type": "fix_link",
            "source_note_path": self.source_rel,
            "source_sha256": hashlib.sha256(self.source_bytes).hexdigest(),
            "claim": "A claim",
            "target_note_paths": [self.target_rel],
            "action": {
                "op": "replace",
                "schema_version": 1,
                "old": "[[Broken]]",
                "new": "[[20_Core/Target]]",
            },
        }
        self.candidate = {
            "candidate_code": self.envelope["candidate_code"],
            "candidate_type": self.envelope["candidate_type"],
            "source_note_path": self.envelope["source_note_path"],
            "source_sha256": self.envelope["source_sha256"],
            "target_note_paths": self.envelope["target_note_paths"],
            "claim": self.envelope["claim"],
            "relationship": "complement",
            "rationale": "private rationale",
            "proposed_changes": [self.envelope["action"]],
            "risk": "low",
        }
        module_name = f"donggu_obsidian_behavioral_{id(self)}"
        self.package = load_package(module_name)
        self.tools = importlib.import_module(module_name + ".tools")
        runtime_module = importlib.import_module(module_name + ".runtime")
        self.runtime = runtime_module.CoreActionRuntime(
            receipt_root=self.base / "receipts", helper_path=HELPER
        )
        setattr(self.tools, "_RUNTIME", self.runtime)
        context = FakeContext()
        self.package.register(context)
        self.handlers = {item["name"]: item["handler"] for item in context.tools}
        self.rows = [{"id": 1, "role": "user", "content": "수정안 보여줘"}]
        rows = self.rows

        class FakeSessionDB:
            def get_messages(self, session_id, limit=None):
                if session_id != "approval-session":
                    return []
                return list(rows)

            def close(self):
                return None

        self.hermes_state = types.ModuleType("hermes_state")
        setattr(self.hermes_state, "SessionDB", FakeSessionDB)
        self.ledger = FakeDeterministicLedger(self.candidate)

    def call(self, name: str, args: dict):
        with mock.patch.dict(sys.modules, {"hermes_state": self.hermes_state}):
            return json.loads(
                self.handlers[name](args, session_id="approval-session")
            )

    def load_helper_module(self):
        name = f"donggu_recovery_helper_{id(self)}"
        spec = importlib.util.spec_from_file_location(name, HELPER)
        if spec is None or spec.loader is None:
            raise ImportError("cannot load CORE helper")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def leave_prepared_journal(self):
        module = self.load_helper_module()
        real_cas = module.cas_install

        class SimulatedDeath(BaseException):
            pass

        def install_then_die(*args, **kwargs):
            result = real_cas(*args, **kwargs)
            raise SimulatedDeath()

        with mock.patch.object(module, "cas_install", side_effect=install_then_die):
            with self.assertRaises(SimulatedDeath):
                module.run(
                    ["--vault-root", str(self.vault)],
                    io.StringIO(json.dumps(self.envelope)), io.StringIO(), io.StringIO(),
                )
        status = self.runtime.recovery_status(self.vault)
        self.assertEqual("prepared", status["state"])

    def preview_to_prepared(self):
        recovery = self.call(
            "donggu_core_recovery_status", {"vault_root": str(self.vault)}
        )
        self.assertTrue(recovery["success"])
        self.assertEqual("no_transaction", recovery["state"])
        self.ledger.events.append("recovery_clean")

        plan = self.call(
            "donggu_core_plan",
            {"vault_root": str(self.vault), "envelope": self.envelope},
        )
        self.assertTrue(plan["success"])
        self.ledger.events.append("native_plan")
        private_plan = {key: value for key, value in plan.items() if key != "success"}
        rendered = subprocess.run(
            [sys.executable, str(RENDERER)],
            input=json.dumps(
                {"candidate": self.candidate, "plan": private_plan},
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode("utf-8"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(0, rendered.returncode, rendered.stderr)
        preview = json.loads(rendered.stdout)
        self.ledger.prepare(
            receipt_id=plan["receipt_id"],
            expires_at=plan["expires_at"],
            preview_hash=preview["preview_hash"],
            envelope_hash=plan["envelope_sha256"],
        )
        return plan, preview

    def finalize_preview(self):
        plan, preview = self.preview_to_prepared()
        public = preview["content"]
        self.assertLessEqual(len(public), 1800)
        for private in (
            self.envelope["candidate_code"],
            plan["receipt_id"],
            plan["envelope_sha256"],
            str(self.vault),
        ):
            self.assertNotIn(private, public)
        self.ledger.events.append("discord_send")
        self.ledger.finalize_sent("170000000000000001")
        return plan, preview

    def claim_without_native_apply(self, plan, preview):
        claim = self.ledger.claim_apply(
            receipt_id=plan["receipt_id"],
            decision_message_id="170000000000000002",
            preview_hash=preview["preview_hash"],
            envelope_hash=plan["envelope_sha256"],
        )
        receipt_id = claim["receipt_id"]
        self.runtime.store.claim(
            receipt_id, "planned", "applying", approval_message_id=2,
        )
        return receipt_id

    def mapped_apply(self, plan, preview, *, completion_nonce=None):
        claim = self.ledger.claim_apply(
            receipt_id=plan["receipt_id"],
            decision_message_id="170000000000000002",
            preview_hash=preview["preview_hash"],
            envelope_hash=plan["envelope_sha256"],
        )
        claim_receipt = claim.get("receipt_id")
        if not isinstance(claim_receipt, str):
            raise AssertionError("fake DB claim did not return a receipt")
        self.ledger.require_claimed(claim_receipt)
        applied = self.call(
            "donggu_core_apply", {"receipt_id": claim_receipt}
        )
        self.ledger.events.append("native_apply")
        if not applied.get("success"):
            return applied
        readback = self.call(
            "donggu_core_readback", {"receipt_id": claim_receipt}
        )
        self.ledger.events.append("native_readback")
        self.assertTrue(readback["success"])
        after_digest = canonical_sha(readback["hashes"])
        nonce = completion_nonce or str(uuid.uuid4())
        completed = self.ledger.complete(
            receipt_id=claim_receipt,
            after_hashes_sha256=after_digest,
            completion_nonce=nonce,
        )
        ack = self.call(
            "donggu_core_ack",
            {
                "receipt_id": claim_receipt,
                "completion_nonce": completed["completion_nonce"],
            },
        )
        self.ledger.events.append("native_ack")
        self.assertTrue(ack["success"])
        self.ledger.confirm_ack(
            receipt_id=claim_receipt,
            completion_nonce=completed["completion_nonce"],
            after_hashes_sha256=after_digest,
        )
        return applied, readback, ack

    def test_exact_natural_preview_then_apply_reaches_registered_real_helper_once(self):
        plan, preview = self.finalize_preview()
        self.assertEqual(self.source_bytes, (self.vault / self.source_rel).read_bytes())
        self.rows.append({"id": 2, "role": "user", "content": "적용해줘"})
        original_run = self.runtime._run
        mutation_calls = []

        def capture(root, envelope, *flags):
            if envelope is not None and not flags:
                mutation_calls.append(envelope["candidate_code"])
            return original_run(root, envelope, *flags)

        with mock.patch.object(self.runtime, "_run", side_effect=capture):
            applied, readback, ack = self.mapped_apply(plan, preview)
            final_status = self.call(
                "donggu_core_receipt_status", {"receipt_id": plan["receipt_id"]}
            )
            recovery = self.call(
                "donggu_core_recovery_status", {"vault_root": str(self.vault)}
            )

        self.assertTrue(applied["success"])
        self.assertEqual("vault_committed_reconciliation_required", applied["status"])
        self.assertEqual("readback_verified", readback["status"])
        self.assertEqual("completed", ack["status"])
        self.assertEqual("completed", final_status["state"])
        self.assertEqual("no_transaction", recovery["state"])
        self.assertEqual("native_ack_complete", self.ledger.completion_state)
        self.assertEqual([self.envelope["candidate_code"]], mutation_calls)
        self.assertIn(
            "[[20_Core/Target]]",
            (self.vault / self.source_rel).read_text(encoding="utf-8"),
        )
        self.assertEqual(
            [
                "recovery_clean",
                "native_plan",
                "db_prepare",
                "discord_send",
                "db_sent_finalize",
                "db_atomic_claim",
                "native_apply",
                "native_readback",
                "db_complete",
                "native_ack",
                "db_ack_confirm",
            ],
            self.ledger.events,
        )
        public_result = "적용이 완료됐어요."
        self.assertLessEqual(len(public_result), 200)
        for private in (plan["receipt_id"], self.envelope["candidate_code"], str(self.vault)):
            self.assertNotIn(private, public_result)

    def test_prepared_recovery_uses_registered_recover_only_once_then_releases_db(self):
        plan, preview = self.finalize_preview()
        receipt_id = self.claim_without_native_apply(plan, preview)
        self.leave_prepared_journal()
        recover_only_calls = []
        original_run = self.runtime._run

        def capture(root, envelope, *flags):
            if flags == ("--recover-only",):
                recover_only_calls.append((envelope, flags))
            return original_run(root, envelope, *flags)

        with mock.patch.object(self.runtime, "_run", side_effect=capture):
            recovered = self.call("donggu_core_recover", {"receipt_id": receipt_id})
        self.assertTrue(recovered["success"])
        self.assertEqual("revoked", recovered["status"])
        self.assertEqual([(None, ("--recover-only",))], recover_only_calls)
        self.ledger.release(receipt_id=receipt_id)
        self.assertEqual(self.source_bytes, (self.vault / self.source_rel).read_bytes())
        self.assertEqual("no_transaction", self.runtime.recovery_status(self.vault)["state"])
        self.assertEqual("previewed", self.ledger.state)
        self.assertEqual("proposed", self.ledger.candidate_state)

    def test_clean_recovery_revokes_without_helper_then_releases_db(self):
        plan, preview = self.finalize_preview()
        receipt_id = self.claim_without_native_apply(plan, preview)
        with mock.patch.object(self.runtime, "_run", wraps=self.runtime._run) as runner:
            recovered = self.call("donggu_core_recover", {"receipt_id": receipt_id})
        self.assertTrue(recovered["success"])
        self.assertEqual("revoked", recovered["status"])
        self.assertFalse(any(call.args[2:] == ("--recover-only",) for call in runner.call_args_list))
        self.ledger.release(receipt_id=receipt_id)
        self.assertEqual(self.source_bytes, (self.vault / self.source_rel).read_bytes())

    def test_committed_recovery_skips_forward_and_recover_only_then_completes_ack(self):
        plan, preview = self.finalize_preview()
        receipt_id = self.claim_without_native_apply(plan, preview)
        code, payload = self.runtime._run(self.vault, self.envelope)
        self.assertEqual(0, code)
        self.assertEqual("applied", payload["status"])

        with mock.patch.object(self.runtime, "_run", wraps=self.runtime._run) as runner:
            recovered = self.call("donggu_core_recover", {"receipt_id": receipt_id})
        self.assertTrue(recovered["success"])
        self.assertEqual("vault_committed_reconciliation_required", recovered["status"])
        self.assertFalse(any(call.args[1] is not None for call in runner.call_args_list))
        self.assertFalse(any(call.args[2:] == ("--recover-only",) for call in runner.call_args_list))

        readback = self.call("donggu_core_readback", {"receipt_id": receipt_id})
        after_digest = canonical_sha(readback["hashes"])
        nonce = str(uuid.uuid4())
        self.ledger.complete(
            receipt_id=receipt_id, after_hashes_sha256=after_digest,
            completion_nonce=nonce,
        )
        ack = self.call(
            "donggu_core_ack", {"receipt_id": receipt_id, "completion_nonce": nonce},
        )
        self.assertEqual("completed", ack["status"])
        self.ledger.confirm_ack(
            receipt_id=receipt_id, completion_nonce=nonce,
            after_hashes_sha256=after_digest,
        )
        self.assertEqual("native_ack_complete", self.ledger.completion_state)
        self.assertEqual("no_transaction", self.runtime.recovery_status(self.vault)["state"])

    def test_wrong_order_is_blocked_before_registered_apply_and_vault_mutation(self):
        plan, _preview = self.finalize_preview()
        self.rows.append({"id": 2, "role": "user", "content": "적용해줘"})
        with self.assertRaises(LedgerOrderError):
            self.ledger.require_claimed(plan["receipt_id"])
        self.assertEqual(self.source_bytes, (self.vault / self.source_rel).read_bytes())
        self.assertEqual("planned", self.runtime.store.load(plan["receipt_id"])["state"])

    def test_prepared_but_not_sent_cannot_claim_or_mutate(self):
        plan, preview = self.preview_to_prepared()
        self.rows.append({"id": 2, "role": "user", "content": "적용해줘"})
        with self.assertRaises(LedgerOrderError):
            self.ledger.claim_apply(
                receipt_id=plan["receipt_id"],
                decision_message_id="170000000000000002",
                preview_hash=preview["preview_hash"],
                envelope_hash=plan["envelope_sha256"],
            )
        self.assertEqual(self.source_bytes, (self.vault / self.source_rel).read_bytes())
        self.assertEqual("planned", self.runtime.store.load(plan["receipt_id"])["state"])

    def test_wrong_completion_nonce_is_blocked_by_db_binding_without_vault_mutation(self):
        plan, _preview = self.finalize_preview()
        stored_nonce = str(uuid.uuid4())
        self.ledger.state = "applied"
        self.ledger.candidate_state = "applied"
        self.ledger.completion_state = "readback_complete_ack_pending"
        self.ledger.completion_nonce = stored_nonce
        self.ledger.after_hashes_sha256 = "a" * 64
        with self.assertRaisesRegex(LedgerOrderError, "completion nonce mismatch"):
            self.ledger.require_ack_binding(
                receipt_id=plan["receipt_id"], completion_nonce=str(uuid.uuid4())
            )
        self.assertEqual(self.source_bytes, (self.vault / self.source_rel).read_bytes())
        self.assertEqual("planned", self.runtime.store.load(plan["receipt_id"])["state"])


if __name__ == "__main__":
    unittest.main()
