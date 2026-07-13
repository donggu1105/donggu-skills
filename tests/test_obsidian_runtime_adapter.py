#!/usr/bin/env python3
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
import uuid
from unittest import mock
from concurrent.futures import ThreadPoolExecutor

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "donggu-obsidian" / "runtime" / "core_actions.py"
HELPER = ROOT / "donggu-obsidian" / "skills" / "core-review-approval" / "scripts" / "apply-action.py"


def load_module():
    spec = importlib.util.spec_from_file_location("donggu_core_runtime", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class CoreActionRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.module = load_module()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.vault = self.base / "vault"
        for name in ("10_Sources", "20_Core", "50_Channel_Packs", "60_MOCs"):
            (self.vault / name).mkdir(parents=True)
        self.source_rel = "10_Sources/source.md"
        self.source = self.vault / self.source_rel
        self.source_bytes = b"---\ntype: source\nextracted_to: []\n---\n\n[[Broken]]\n"
        self.source.write_bytes(self.source_bytes)
        self.target_rel = "20_Core/Target.md"
        (self.vault / self.target_rel).write_text("target\n", encoding="utf-8")
        self.envelope = {
            "schema_version": 1,
            "candidate_code": "CR-20260713-000001",
            "candidate_type": "fix_link",
            "source_note_path": self.source_rel,
            "source_sha256": sha(self.source_bytes),
            "claim": "A claim",
            "target_note_paths": [self.target_rel],
            "action": {
                "op": "replace",
                "schema_version": 1,
                "old": "[[Broken]]",
                "new": "[[20_Core/Target]]",
            },
        }
        self.runtime = self.module.CoreActionRuntime(
            receipt_root=self.base / "receipts",
            helper_path=HELPER,
            receipt_ttl_seconds=900,
        )

    def plan(self):
        return self.runtime.plan(
            self.vault, self.envelope,
            session_id="session-a", plan_message_id=10,
            latest_user_text="수정안 보여줘",
        )

    def apply(self, receipt_id, text="적용해줘", *, session_id="session-a", message_id=11):
        return self.runtime.apply(
            receipt_id, latest_user_text=text,
            session_id=session_id, user_message_id=message_id,
            latest_user_reader=lambda: (message_id, text),
        )

    @staticmethod
    def nonce():
        return str(uuid.uuid4())

    def test_plan_runs_real_zero_write_helper_and_stores_absolute_expiry(self):
        before = self.source.read_bytes()
        with mock.patch.object(self.module.time, "time", return_value=1_000.9):
            result = self.plan()
        self.assertEqual("planned", result["status"])
        self.assertEqual(1900, result["expires_at"])
        self.assertEqual([self.source_rel], result["paths"])
        self.assertEqual(before, self.source.read_bytes())
        receipt = json.loads((self.base / "receipts" / f"{result['receipt_id']}.json").read_text(encoding="utf-8"))
        self.assertEqual(1900, receipt["expires_at"])
        self.assertEqual(result["envelope_sha256"], receipt["envelope_sha256"])
        self.assertEqual("session-a", receipt["session_id"])
        self.assertEqual(10, receipt["plan_message_id"])
        self.assertNotIn("receipt_hmac", receipt)

    def test_plan_requires_exact_latest_persisted_preview_command(self):
        for text in ("", " 수정안 보여줘", "수정안 보여줘\n", "적용해줘"):
            with self.assertRaises(self.module.CoreApprovalError):
                self.runtime.plan(
                    self.vault, self.envelope,
                    session_id="session-a", plan_message_id=10,
                    latest_user_text=text,
                )

    def test_receipt_write_error_never_closes_an_already_transferred_descriptor(self):
        receipt_id = "A" * 20
        original_mkstemp = self.module.tempfile.mkstemp
        captured = []

        def capture_mkstemp(*args, **kwargs):
            descriptor, name = original_mkstemp(*args, **kwargs)
            captured.append(descriptor)
            return descriptor, name

        original_close = self.module.os.close
        close_calls = []

        def capture_close(descriptor):
            close_calls.append(descriptor)
            return original_close(descriptor)

        with mock.patch.object(self.module.tempfile, "mkstemp", side_effect=capture_mkstemp), mock.patch.object(
            self.module.os, "replace", side_effect=OSError("replace failed")
        ), mock.patch.object(self.module.os, "close", side_effect=capture_close):
            with self.assertRaises(OSError):
                self.runtime.store._write({
                    "receipt_id": receipt_id, "state": "planned", "expires_at": 9999999999,
                })
        self.assertEqual(1, len(captured))
        self.assertNotIn(captured[0], close_calls)

    def test_apply_requires_exact_natural_text_and_derives_private_legacy_approval(self):
        plan = self.plan()
        original_validate = self.runtime._validate_approval
        captured = []

        def capture(text, candidate):
            captured.append((text, candidate))
            return original_validate(text, candidate)

        with mock.patch.object(self.runtime, "_validate_approval", side_effect=capture):
            result = self.apply(plan["receipt_id"])
        self.assertEqual("vault_committed_reconciliation_required", result["status"])
        self.assertEqual([("CR-20260713-000001 승인", "CR-20260713-000001")], captured)
        self.assertIn("[[20_Core/Target]]", self.source.read_text(encoding="utf-8"))
        self.assertEqual("reconciliation_required", self.runtime.store.load(plan["receipt_id"])["state"])

    def test_wrong_or_legacy_user_text_never_calls_mutating_helper(self):
        for text in ("", " 적용해줘", "적용해줘\n", "CR-20260713-000001 승인", "일단 적용해줘"):
            plan = self.plan()
            calls = []
            original_run = self.runtime._run

            def capture(root, envelope, *flags):
                calls.append((envelope, flags))
                return original_run(root, envelope, *flags)

            with mock.patch.object(self.runtime, "_run", side_effect=capture):
                with self.assertRaises(self.module.CoreApprovalError):
                    self.apply(plan["receipt_id"], text)
            self.assertFalse(any(envelope is not None and not flags for envelope, flags in calls))
            self.assertEqual(self.source_bytes, self.source.read_bytes())
            self.assertEqual("planned", self.runtime.store.load(plan["receipt_id"])["state"])

    def test_duplicate_apply_is_idempotent_and_never_reinvokes_helper(self):
        plan = self.plan()
        first = self.apply(plan["receipt_id"])
        with mock.patch.object(self.runtime, "_run", side_effect=AssertionError("helper replay")):
            second = self.apply(plan["receipt_id"])
        self.assertEqual(first, second)

    def test_apply_requires_same_session_and_strictly_later_message(self):
        plan = self.plan()
        for session_id, message_id in (("session-b", 11), ("session-a", 10), ("session-a", 9)):
            with mock.patch.object(self.runtime, "_run", side_effect=AssertionError("mutation helper called")):
                with self.assertRaises(self.module.CoreApprovalError):
                    self.apply(plan["receipt_id"], session_id=session_id, message_id=message_id)
        self.assertEqual("planned", self.runtime.store.load(plan["receipt_id"])["state"])

    def test_same_persisted_apply_message_cannot_authorize_two_receipts(self):
        first = self.plan()
        second = self.plan()
        self.apply(first["receipt_id"], message_id=11)
        with self.assertRaises(self.module.CoreApprovalError):
            self.apply(second["receipt_id"], message_id=11)
        self.assertEqual("planned", self.runtime.store.load(second["receipt_id"])["state"])

    def test_expired_receipt_is_rejected_without_helper_or_mutation(self):
        with mock.patch.object(self.module.time, "time", return_value=100):
            plan = self.plan()
        with mock.patch.object(self.module.time, "time", return_value=1001), mock.patch.object(
            self.runtime, "_run", side_effect=AssertionError("expired helper call")
        ):
            with self.assertRaises(self.module.CoreReceiptError):
                self.apply(plan["receipt_id"])
        self.assertEqual(self.source_bytes, self.source.read_bytes())

    def test_source_drift_is_terminal_revocation_and_not_retried(self):
        plan = self.plan()
        self.source.write_bytes(self.source_bytes + b"drift")
        result = self.apply(plan["receipt_id"])
        self.assertEqual("revoked", result["status"])
        self.assertEqual(2, result["exit_code"])
        with mock.patch.object(self.runtime, "_run", side_effect=AssertionError("apply retried")):
            self.assertEqual(result, self.apply(plan["receipt_id"]))
        self.assertEqual(self.source_bytes + b"drift", self.source.read_bytes())

    def test_exit_5_with_matching_committed_journal_requires_reconciliation(self):
        plan = self.plan()
        receipt = self.runtime.store.load(plan["receipt_id"])
        committed = {
            "state": "committed",
            "candidate_code": receipt["candidate_code"],
            "transaction_sha256": receipt["transaction_sha256"],
        }
        with mock.patch.object(self.runtime, "_run", return_value=(5, {})), mock.patch.object(
            self.runtime, "recovery_status", return_value=committed
        ):
            result = self.apply(plan["receipt_id"])
        self.assertEqual("vault_committed_reconciliation_required", result["status"])
        self.assertEqual(5, result["exit_code"])
        self.assertEqual("reconciliation_required", self.runtime.store.load(plan["receipt_id"])["state"])

    def test_exit_70_clean_revokes_but_matching_commit_requires_reconciliation(self):
        message_id = 20
        for matching, expected in ((False, "revoked"), (True, "reconciliation_required")):
            plan = self.plan()
            receipt = self.runtime.store.load(plan["receipt_id"])
            recovery = (
                {"state": "committed", "candidate_code": receipt["candidate_code"],
                 "transaction_sha256": receipt["transaction_sha256"]}
                if matching else
                {"state": "no_transaction", "candidate_code": None, "transaction_sha256": None}
            )
            with mock.patch.object(self.runtime, "_run", return_value=(70, {})), mock.patch.object(
                self.runtime, "recovery_status", return_value=recovery
            ):
                result = self.apply(plan["receipt_id"], message_id=message_id)
            message_id += 1
            self.assertEqual(expected, self.runtime.store.load(plan["receipt_id"])["state"])
            expected_status = "vault_committed_reconciliation_required" if matching else "revoked"
            self.assertEqual(expected_status, result["status"])

    def test_death_after_helper_commit_before_receipt_write_recovers_after_restart_with_newer_retry(self):
        plan = self.plan()
        original_transition = self.runtime.store.transition

        class SimulatedDeath(BaseException):
            pass

        def die_before_reconciliation(receipt, state, **updates):
            if state == "reconciliation_required":
                raise SimulatedDeath()
            return original_transition(receipt, state, **updates)

        with mock.patch.object(self.runtime.store, "transition", side_effect=die_before_reconciliation):
            with self.assertRaises(SimulatedDeath):
                self.apply(plan["receipt_id"])
        self.assertEqual("applying", self.runtime.store.load(plan["receipt_id"])["state"])
        self.assertIn("[[20_Core/Target]]", self.source.read_text(encoding="utf-8"))
        restarted = self.module.CoreActionRuntime(
            receipt_root=self.base / "receipts",
            helper_path=HELPER,
            receipt_ttl_seconds=900,
        )
        with mock.patch.object(restarted, "_run", wraps=restarted._run) as runner:
            result = restarted.apply(
                plan["receipt_id"], latest_user_text="적용해줘",
                session_id="session-a", user_message_id=12,
                latest_user_reader=lambda: (12, "적용해줘"),
            )
        self.assertEqual("vault_committed_reconciliation_required", result["status"])
        self.assertFalse(any(call.args[1] is not None and not call.args[2:] for call in runner.call_args_list))

    def test_readback_recovers_committed_applying_receipt_after_process_restart(self):
        plan = self.plan()
        original_transition = self.runtime.store.transition

        class SimulatedDeath(BaseException):
            pass

        def die_before_reconciliation(receipt, state, **updates):
            if state == "reconciliation_required":
                raise SimulatedDeath()
            return original_transition(receipt, state, **updates)

        with mock.patch.object(self.runtime.store, "transition", side_effect=die_before_reconciliation):
            with self.assertRaises(SimulatedDeath):
                self.apply(plan["receipt_id"])
        restarted = self.module.CoreActionRuntime(
            receipt_root=self.base / "receipts",
            helper_path=HELPER,
            receipt_ttl_seconds=900,
        )
        with mock.patch.object(restarted, "_run", wraps=restarted._run) as runner:
            result = restarted.readback(plan["receipt_id"])
        self.assertEqual("readback_verified", result["status"])
        self.assertEqual("reconciliation_required", restarted.store.load(plan["receipt_id"])["state"])
        self.assertFalse(any(call.args[1] is not None and not call.args[2:] for call in runner.call_args_list))

    def test_applying_with_clean_journal_is_revoked_and_foreign_journal_is_ambiguous(self):
        cases = (
            ({"state": "no_transaction", "candidate_code": None, "transaction_sha256": None}, "revoked"),
            ({"state": "committed", "candidate_code": "CR-foreign", "transaction_sha256": "a" * 64}, "ambiguous"),
        )
        for index, (journal, expected) in enumerate(cases, start=30):
            plan = self.plan()
            self.runtime.store.claim(
                plan["receipt_id"], "planned", "applying", approval_message_id=index,
            )
            with mock.patch.object(self.runtime, "recovery_status", return_value=journal), mock.patch.object(
                self.runtime, "_run", side_effect=AssertionError("apply helper replayed")
            ):
                result = self.apply(plan["receipt_id"], message_id=index)
            self.assertEqual(expected, result["status"])
            self.assertEqual(expected, self.runtime.store.load(plan["receipt_id"])["state"])

    def test_recover_matching_prepared_or_rolled_back_invokes_recover_only_once(self):
        for message_id, journal_state in enumerate(("prepared", "rolled_back"), start=35):
            with self.subTest(journal_state=journal_state):
                plan = self.plan()
                receipt = self.runtime.store.claim(
                    plan["receipt_id"], "planned", "applying", approval_message_id=message_id,
                )
                initial = {
                    "state": journal_state,
                    "candidate_code": receipt["candidate_code"],
                    "transaction_sha256": receipt["transaction_sha256"],
                }
                clean = {"state": "no_transaction", "candidate_code": None, "transaction_sha256": None}
                statuses = iter((initial, clean))
                calls = []

                def recover_only(root, envelope, *flags):
                    calls.append((root, envelope, flags))
                    return 0, {
                        "status": "recovered", "state": "prepared",
                        "candidate_code": receipt["candidate_code"],
                    }

                with mock.patch.object(
                    self.runtime, "recovery_status", side_effect=lambda _root: next(statuses)
                ), mock.patch.object(self.runtime, "_run", side_effect=recover_only):
                    result = self.runtime.recover(plan["receipt_id"])

                self.assertEqual("revoked", result["status"])
                self.assertEqual("revoked", self.runtime.store.load(plan["receipt_id"])["state"])
                self.assertEqual(1, len(calls))
                self.assertEqual(Path(receipt["vault_root"]), calls[0][0])
                self.assertEqual((None, ("--recover-only",)), calls[0][1:])

    def test_recover_classifies_committed_clean_and_foreign_without_helper_replay(self):
        cases = (
            ("committed", "vault_committed_reconciliation_required", "reconciliation_required"),
            ("clean", "revoked", "revoked"),
            ("foreign", "ambiguous", "ambiguous"),
        )
        for message_id, (case, expected_status, expected_state) in enumerate(cases, start=37):
            with self.subTest(case=case):
                plan = self.plan()
                receipt = self.runtime.store.claim(
                    plan["receipt_id"], "planned", "applying", approval_message_id=message_id,
                )
                if case == "committed":
                    journal = {
                        "state": "committed", "candidate_code": receipt["candidate_code"],
                        "transaction_sha256": receipt["transaction_sha256"],
                    }
                elif case == "clean":
                    journal = {"state": "no_transaction", "candidate_code": None, "transaction_sha256": None}
                else:
                    journal = {
                        "state": "prepared", "candidate_code": "CR-20260713-999999",
                        "transaction_sha256": "f" * 64,
                    }
                with mock.patch.object(self.runtime, "recovery_status", return_value=journal), mock.patch.object(
                    self.runtime, "_run", side_effect=AssertionError("recovery helper must not run")
                ):
                    result = self.runtime.recover(plan["receipt_id"])
                self.assertEqual(expected_status, result["status"])
                self.assertEqual(expected_state, self.runtime.store.load(plan["receipt_id"])["state"])

    def test_recover_exit_5_or_malformed_status_is_terminal_ambiguous_and_idempotent(self):
        plan = self.plan()
        receipt = self.runtime.store.claim(
            plan["receipt_id"], "planned", "applying", approval_message_id=40,
        )
        prepared = {
            "state": "prepared", "candidate_code": receipt["candidate_code"],
            "transaction_sha256": receipt["transaction_sha256"],
        }
        with mock.patch.object(self.runtime, "recovery_status", return_value=prepared), mock.patch.object(
            self.runtime, "_run", return_value=(5, {})
        ) as runner:
            result = self.runtime.recover(plan["receipt_id"])
        self.assertEqual("ambiguous", result["status"])
        self.assertEqual(1, runner.call_count)
        with mock.patch.object(self.runtime, "_run", side_effect=AssertionError("terminal recovery replay")):
            self.assertEqual(result, self.runtime.recover(plan["receipt_id"]))

        second = self.plan()
        self.runtime.store.claim(second["receipt_id"], "planned", "applying", approval_message_id=41)
        with mock.patch.object(
            self.runtime, "recovery_status", side_effect=self.module.CoreHelperError("malformed journal")
        ), mock.patch.object(self.runtime, "_run", side_effect=AssertionError("unknown recovery helper call")):
            malformed = self.runtime.recover(second["receipt_id"])
        self.assertEqual("ambiguous", malformed["status"])

    def test_recover_rejects_planned_receipt_without_approval_or_helper(self):
        plan = self.plan()
        with mock.patch.object(self.runtime, "_run", side_effect=AssertionError("helper called")):
            with self.assertRaises(self.module.CoreReceiptError):
                self.runtime.recover(plan["receipt_id"])

    def test_exit_4_matching_committed_still_preserves_local_ambiguous(self):
        plan = self.plan()
        receipt = self.runtime.store.load(plan["receipt_id"])
        committed = {
            "state": "committed", "candidate_code": receipt["candidate_code"],
            "transaction_sha256": receipt["transaction_sha256"],
        }
        with mock.patch.object(self.runtime, "_run", return_value=(4, {})), mock.patch.object(
            self.runtime, "recovery_status", return_value=committed
        ):
            result = self.apply(plan["receipt_id"], message_id=49)
        self.assertEqual("ambiguous", result["status"])
        self.assertEqual("ambiguous", self.runtime.store.load(plan["receipt_id"])["state"])

    def test_exit_4_and_unresolved_exit_5_are_ambiguous_and_never_reapplied(self):
        for message_id, exit_code in enumerate((4, 5), start=50):
            plan = self.plan()
            clean = {"state": "no_transaction", "candidate_code": None, "transaction_sha256": None}
            with mock.patch.object(self.runtime, "_run", return_value=(exit_code, {})), mock.patch.object(
                self.runtime, "recovery_status", return_value=clean
            ):
                result = self.apply(plan["receipt_id"], message_id=message_id)
            self.assertEqual("ambiguous", result["status"])
            with mock.patch.object(self.runtime, "_run", side_effect=AssertionError("ambiguous replay")):
                self.assertEqual(result, self.apply(plan["receipt_id"], message_id=message_id))

    def test_helper_transport_failure_with_clean_journal_requires_repreview(self):
        plan = self.plan()
        clean = {"state": "no_transaction", "candidate_code": None, "transaction_sha256": None}
        with mock.patch.object(
            self.runtime, "_run", side_effect=self.module.CoreHelperError("transport failed")
        ), mock.patch.object(self.runtime, "recovery_status", return_value=clean):
            result = self.apply(plan["receipt_id"], message_id=60)
        self.assertEqual("revoked", result["status"])
        self.assertEqual("revoked", self.runtime.store.load(plan["receipt_id"])["state"])

    def test_receipt_status_is_read_only_bounded_and_private_even_after_expiry(self):
        with mock.patch.object(self.module.time, "time", return_value=100):
            plan = self.plan()
        receipt_path = self.base / "receipts" / f"{plan['receipt_id']}.json"
        before = receipt_path.read_bytes()
        with mock.patch.object(self.module.time, "time", return_value=1001):
            status = self.runtime.receipt_status(plan["receipt_id"])
        self.assertEqual(
            {"state", "receipt_id", "candidate_code", "source_sha256", "envelope_sha256", "path_count", "expires_at"},
            set(status),
        )
        self.assertEqual("planned", status["state"])
        self.assertNotIn(str(self.vault), json.dumps(status))
        self.assertNotIn("envelope", status)
        self.assertNotIn("paths", status)
        self.assertNotIn("hashes", status)
        self.assertNotIn("receipt_hmac", status)
        self.assertLess(len(json.dumps(status)), 4096)
        self.assertEqual(before, receipt_path.read_bytes())

    def test_receipt_status_omits_unbounded_malformed_dynamic_strings(self):
        plan = self.plan()
        receipt_path = self.base / "receipts" / f"{plan['receipt_id']}.json"
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        receipt["candidate_code"] = "가" * 10_000
        receipt["source_sha256"] = "source" * 2_000
        receipt["envelope_sha256"] = "envelope" * 2_000
        receipt_path.write_text(json.dumps(receipt, ensure_ascii=False), encoding="utf-8")

        status = self.runtime.receipt_status(plan["receipt_id"])
        response = json.dumps({"success": True, **status}, ensure_ascii=False).encode("utf-8")

        self.assertLessEqual(len(response), self.module._MAX_STATUS_BYTES)
        self.assertNotIn("가", response.decode("utf-8"))
        self.assertIsNone(status["candidate_code"])
        self.assertIsNone(status["source_sha256"])
        self.assertIsNone(status["envelope_sha256"])

    def test_readback_verifies_actual_after_hashes_using_receipt_paths(self):
        plan = self.plan()
        self.apply(plan["receipt_id"])
        result = self.runtime.readback(plan["receipt_id"])
        self.assertEqual("readback_verified", result["status"])
        self.assertEqual(
            self.runtime.store.load(plan["receipt_id"])["hashes"], result["hashes"]
        )
        stored = self.runtime.store.load(plan["receipt_id"])
        self.assertTrue(stored["readback_verified"])

    def test_readback_mismatch_becomes_ambiguous_and_does_not_follow_symlink(self):
        plan = self.plan()
        self.apply(plan["receipt_id"])
        outside = self.base / "outside.md"
        outside.write_text("private outside bytes", encoding="utf-8")
        self.source.unlink()
        self.source.symlink_to(outside)
        with self.assertRaises(self.module.CoreReceiptError) as caught:
            self.runtime.readback(plan["receipt_id"])
        self.assertNotIn("private outside bytes", str(caught.exception))
        self.assertEqual("ambiguous", self.runtime.store.load(plan["receipt_id"])["state"])

    def test_revoke_only_planned_is_idempotent_and_never_calls_helper(self):
        plan = self.plan()
        with mock.patch.object(self.runtime, "_run", side_effect=AssertionError("revoke helper call")):
            first = self.runtime.revoke(plan["receipt_id"])
            second = self.runtime.revoke(plan["receipt_id"])
        self.assertEqual("revoked", first["status"])
        self.assertEqual(first, second)
        self.assertEqual(self.source_bytes, self.source.read_bytes())

    def test_revoke_rejects_reconciliation_required_receipt(self):
        plan = self.plan()
        self.apply(plan["receipt_id"])
        with mock.patch.object(self.runtime, "_run", side_effect=AssertionError("revoke helper call")):
            with self.assertRaises(self.module.CoreReceiptError):
                self.runtime.revoke(plan["receipt_id"])

    def test_ack_requires_local_readback_then_cleans_matching_committed_journal(self):
        plan = self.plan()
        self.apply(plan["receipt_id"])
        nonce = self.nonce()
        with self.assertRaises(self.module.CoreReceiptError):
            self.runtime.ack(plan["receipt_id"], completion_nonce=nonce)
        self.runtime.readback(plan["receipt_id"])
        result = self.runtime.ack(plan["receipt_id"], completion_nonce=nonce)
        self.assertEqual("completed", result["status"])
        self.assertTrue(result["operation_completed"])
        self.assertEqual(nonce, result["completion_nonce"])
        self.assertEqual("no_transaction", self.runtime.recovery_status(self.vault)["state"])
        with mock.patch.object(self.runtime, "_run", side_effect=AssertionError("ack replay")):
            self.assertEqual(result, self.runtime.ack(plan["receipt_id"], completion_nonce=nonce))

    def test_ack_rejects_noncanonical_or_changed_completion_nonce(self):
        plan = self.plan()
        self.apply(plan["receipt_id"])
        self.runtime.readback(plan["receipt_id"])
        for nonce in ("", "NOT-A-UUID", str(uuid.uuid4()).upper(), "{" + str(uuid.uuid4()) + "}"):
            with self.assertRaises(self.module.CoreReceiptError):
                self.runtime.ack(plan["receipt_id"], completion_nonce=nonce)
        nonce = self.nonce()
        self.runtime.ack(plan["receipt_id"], completion_nonce=nonce)
        with self.assertRaises(self.module.CoreReceiptError):
            self.runtime.ack(plan["receipt_id"], completion_nonce=self.nonce())

    def test_ack_exit_6_is_cleanup_only_retry_and_never_calls_apply(self):
        plan = self.plan()
        self.apply(plan["receipt_id"])
        self.runtime.readback(plan["receipt_id"])
        receipt = self.runtime.store.load(plan["receipt_id"])
        committed = {
            "state": "committed",
            "candidate_code": receipt["candidate_code"],
            "transaction_sha256": receipt["transaction_sha256"],
        }
        calls = []

        def cleanup_retry(root, envelope, *flags):
            calls.append((envelope, flags))
            return 6, {}

        with mock.patch.object(self.runtime, "recovery_status", return_value=committed), mock.patch.object(
            self.runtime, "_run", side_effect=cleanup_retry
        ):
            result = self.runtime.ack(plan["receipt_id"], completion_nonce=self.nonce())
        self.assertEqual("cleanup_retry_required", result["status"])
        self.assertEqual("acknowledging", self.runtime.store.load(plan["receipt_id"])["state"])
        self.assertEqual([(None, ("--ack-candidate", "CR-20260713-000001"))], calls)

    def test_ack_exit_5_reconciles_clean_as_completed_and_matching_as_retryable(self):
        for index, state in enumerate(("no_transaction", "committed"), start=40):
            plan = self.plan()
            self.apply(plan["receipt_id"], message_id=index)
            self.runtime.readback(plan["receipt_id"])
            receipt = self.runtime.store.load(plan["receipt_id"])
            committed = {
                "state": "committed", "candidate_code": receipt["candidate_code"],
                "transaction_sha256": receipt["transaction_sha256"],
            }
            after = (
                {"state": "no_transaction", "candidate_code": None, "transaction_sha256": None}
                if state == "no_transaction" else committed
            )
            statuses = iter((committed, after))
            nonce = self.nonce()
            with mock.patch.object(self.runtime, "recovery_status", side_effect=lambda _root: next(statuses)), mock.patch.object(
                self.runtime, "_run", return_value=(5, {})
            ):
                result = self.runtime.ack(plan["receipt_id"], completion_nonce=nonce)
            expected_status = "completed" if state == "no_transaction" else "ack_retry_required"
            expected_state = "completed" if state == "no_transaction" else "acknowledging"
            self.assertEqual(expected_status, result["status"])
            self.assertEqual(expected_state, self.runtime.store.load(plan["receipt_id"])["state"])
            cleanup_code, _cleanup_payload = self.runtime._run(
                self.vault, None, "--ack-candidate", str(receipt["candidate_code"]),
            )
            self.assertEqual(0, cleanup_code)
            self.source.write_bytes(self.source_bytes)

    def test_death_after_ack_cleanup_before_receipt_completion_converges_completed(self):
        plan = self.plan()
        self.apply(plan["receipt_id"])
        self.runtime.readback(plan["receipt_id"])
        nonce = self.nonce()
        original_transition = self.runtime.store.transition

        class SimulatedDeath(BaseException):
            pass

        def die_before_completed(receipt, state, **updates):
            if state == "completed":
                raise SimulatedDeath()
            return original_transition(receipt, state, **updates)

        with mock.patch.object(self.runtime.store, "transition", side_effect=die_before_completed):
            with self.assertRaises(SimulatedDeath):
                self.runtime.ack(plan["receipt_id"], completion_nonce=nonce)
        self.assertEqual("acknowledging", self.runtime.store.load(plan["receipt_id"])["state"])
        self.assertEqual("no_transaction", self.runtime.recovery_status(self.vault)["state"])
        with mock.patch.object(self.runtime, "_run", wraps=self.runtime._run) as runner:
            result = self.runtime.ack(plan["receipt_id"], completion_nonce=nonce)
        self.assertEqual("completed", result["status"])
        self.assertFalse(any("--ack-candidate" in call.args[2:] for call in runner.call_args_list))

    def test_concurrent_ack_invokes_helper_once(self):
        plan = self.plan()
        self.apply(plan["receipt_id"])
        self.runtime.readback(plan["receipt_id"])
        nonce = self.nonce()
        original_run = self.runtime._run
        ack_calls = 0

        def count_ack(root, envelope, *flags):
            nonlocal ack_calls
            if "--ack-candidate" in flags:
                ack_calls += 1
            return original_run(root, envelope, *flags)

        with mock.patch.object(self.runtime, "_run", side_effect=count_ack):
            with ThreadPoolExecutor(max_workers=8) as pool:
                results = list(pool.map(
                    lambda _index: self.runtime.ack(plan["receipt_id"], completion_nonce=nonce), range(8)
                ))
        self.assertEqual(1, ack_calls)
        self.assertTrue(all(result["status"] == "completed" for result in results))

    def test_core_receipt_claim_allows_exactly_one_concurrent_winner(self):
        plan = self.plan()

        def claim_once(_index):
            try:
                self.runtime.store.claim(plan["receipt_id"], "planned", "applying")
                return "won"
            except self.module.CoreReceiptError:
                return "lost"

        with ThreadPoolExecutor(max_workers=8) as pool:
            outcomes = list(pool.map(claim_once, range(8)))
        self.assertEqual(1, outcomes.count("won"))
        self.assertEqual(7, outcomes.count("lost"))

    def test_recovery_status_is_read_only(self):
        before = self.source.read_bytes()
        result = self.runtime.recovery_status(self.vault)
        self.assertEqual({"state": "no_transaction", "candidate_code": None, "transaction_sha256": None}, result)
        self.assertEqual(before, self.source.read_bytes())

    def test_vault_root_symlink_is_rejected(self):
        link = self.base / "vault-link"
        link.symlink_to(self.vault, target_is_directory=True)
        with self.assertRaises(self.module.CoreHelperError):
            self.runtime.plan(
                link, self.envelope, session_id="session-a", plan_message_id=10,
                latest_user_text="수정안 보여줘",
            )


if __name__ == "__main__":
    unittest.main()
