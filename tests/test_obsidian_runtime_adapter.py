#!/usr/bin/env python3
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import sqlite3
import subprocess
import sys
import tempfile
import unittest
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

    def plan(self, vault_root, envelope, *, user_message_id=1):
        return self.runtime.plan(
            vault_root, envelope,
            session_id="session-1", turn_id="turn-plan", user_message_id=user_message_id,
        )

    def apply(self, receipt_id, *, approval_text, session_id="session-1", user_message_id=2):
        return self.runtime.apply(
            receipt_id,
            approval_text=approval_text,
            session_id=session_id,
            turn_id="turn-apply",
            user_message_id=user_message_id,
        )

    def test_plan_runs_real_helper_dry_run_and_binds_receipt(self):
        before = self.source.read_bytes()
        result = self.plan(self.vault, self.envelope)
        self.assertEqual("planned", result["status"])
        self.assertEqual([self.source_rel], result["paths"])
        self.assertEqual(sha(self.source_bytes), result["hashes"][self.source_rel]["before"])
        self.assertEqual(before, self.source.read_bytes())
        receipt = json.loads((self.base / "receipts" / f"{result['receipt_id']}.json").read_text(encoding="utf-8"))
        self.assertEqual(os.path.realpath(str(self.vault)), receipt["vault_root"])
        self.assertEqual(result["envelope_sha256"], receipt["envelope_sha256"])

    def test_apply_commits_vault_and_requires_db_reconciliation(self):
        plan = self.plan(self.vault, self.envelope)
        result = self.apply(plan["receipt_id"], approval_text="CR-20260713-000001 승인")
        self.assertEqual("vault_committed_reconciliation_required", result["status"])
        self.assertEqual("applied", result["helper_status"])
        self.assertEqual("committed", result["journal_state"])
        self.assertIn("[[20_Core/Target]]", self.source.read_text(encoding="utf-8"))
        self.assertEqual(sha(self.source.read_bytes()), result["hashes"][self.source_rel]["after"])
        status = self.runtime.recovery_status(self.vault)
        self.assertEqual("committed", status["state"])
        self.assertEqual("CR-20260713-000001", status["candidate_code"])
        with self.assertRaises(self.module.CoreReceiptError):
            self.apply(plan["receipt_id"], approval_text="CR-20260713-000001 승인")

    def test_apply_rejects_empty_approval_without_mutation(self):
        plan = self.plan(self.vault, self.envelope)
        with self.assertRaises(self.module.CoreApprovalError):
            self.apply(plan["receipt_id"], approval_text=" ")
        self.assertEqual(self.source_bytes, self.source.read_bytes())

    def test_apply_binds_trusted_session_and_persisted_message_order(self):
        plan = self.plan(self.vault, self.envelope, user_message_id=2)
        with self.assertRaises(self.module.CoreApprovalError):
            self.apply(
                plan["receipt_id"], approval_text="CR-20260713-000001 승인",
                session_id="other-session", user_message_id=3,
            )
        with self.assertRaises(self.module.CoreApprovalError):
            self.apply(
                plan["receipt_id"], approval_text="CR-20260713-000001 승인",
                user_message_id=1,
            )
        self.assertEqual(self.source_bytes, self.source.read_bytes())

    def test_apply_binds_exact_approval_decision_and_candidate(self):
        for text in ("거절", "보류", "일단 해줘", "CR-20260713-000001 거절", "CR-20260713-999999 승인"):
            plan = self.plan(self.vault, self.envelope)
            with self.assertRaises(self.module.CoreApprovalError):
                self.apply(plan["receipt_id"], approval_text=text)
            self.assertEqual(self.source_bytes, self.source.read_bytes())
            self.assertEqual("planned", self.runtime.store.load(plan["receipt_id"])["state"])

    def test_receipt_hash_tampering_is_rejected_before_vault_mutation(self):
        plan = self.plan(self.vault, self.envelope)
        path = self.base / "receipts" / f"{plan['receipt_id']}.json"
        receipt = json.loads(path.read_text(encoding="utf-8"))
        receipt["hashes"][self.source_rel]["after"] = "0" * 64
        path.write_text(json.dumps(receipt), encoding="utf-8")
        with self.assertRaises(self.module.CoreReceiptError):
            self.apply(plan["receipt_id"], approval_text="CR-20260713-000001 승인")
        self.assertEqual(self.source_bytes, self.source.read_bytes())
        with self.assertRaises(self.module.CoreReceiptError):
            self.runtime.store.load(plan["receipt_id"])

    def test_recomputed_receipt_hash_tampering_is_rejected_before_vault_mutation(self):
        plan = self.plan(self.vault, self.envelope)
        path = self.base / "receipts" / f"{plan['receipt_id']}.json"
        receipt = json.loads(path.read_text(encoding="utf-8"))
        receipt["hashes"][self.source_rel]["after"] = "0" * 64
        receipt["receipt_sha256"] = self.module._receipt_binding_sha256(receipt)
        path.write_text(json.dumps(receipt), encoding="utf-8")
        with self.assertRaises(self.module.CoreReceiptError):
            self.apply(plan["receipt_id"], approval_text="CR-20260713-000001 승인")
        self.assertEqual(self.source_bytes, self.source.read_bytes())

    def test_vault_root_symlink_is_rejected(self):
        link = self.base / "vault-link"
        link.symlink_to(self.vault, target_is_directory=True)
        with self.assertRaises(self.module.CoreHelperError):
            self.plan(link, self.envelope)

    def test_vault_root_with_symlinked_ancestor_is_rejected(self):
        alias = self.base / "alias"
        alias.symlink_to(self.base, target_is_directory=True)
        with self.assertRaises(self.module.CoreHelperError):
            self.plan(alias / "vault", self.envelope)

    def test_recovery_status_is_read_only(self):
        before = self.source.read_bytes()
        result = self.runtime.recovery_status(self.vault)
        self.assertEqual("no_transaction", result["state"])
        self.assertIsNone(result["candidate_code"])
        self.assertEqual(before, self.source.read_bytes())

    def test_invalid_envelope_returns_bounded_error_without_content_leak(self):
        bad = dict(self.envelope)
        bad["secret"] = "private-envelope-value"
        with self.assertRaises(self.module.CoreHelperError) as caught:
            self.plan(self.vault, bad)
        self.assertNotIn("private-envelope-value", str(caught.exception))
        self.assertLess(len(str(caught.exception)), 200)

    def test_core_receipt_claim_allows_exactly_one_concurrent_winner(self):
        plan = self.plan(self.vault, self.envelope)

        def claim_once():
            try:
                self.runtime.store.claim(plan["receipt_id"], "planned", "applying")
                return "won"
            except self.module.CoreReceiptError:
                return "lost"

        with ThreadPoolExecutor(max_workers=8) as pool:
            outcomes = list(pool.map(lambda _index: claim_once(), range(8)))
        self.assertEqual(1, outcomes.count("won"))
        self.assertEqual(7, outcomes.count("lost"))

    def test_one_persisted_authorization_cannot_apply_multiple_core_receipts(self):
        first = self.plan(self.vault, self.envelope)
        second = self.plan(self.vault, self.envelope)
        result = self.apply(
            first["receipt_id"], approval_text="CR-20260713-000001 승인", user_message_id=2,
        )
        self.assertEqual("vault_committed_reconciliation_required", result["status"])
        with self.assertRaises(self.module.CoreApprovalError):
            self.apply(
                second["receipt_id"], approval_text="CR-20260713-000001 승인", user_message_id=2,
            )
        self.assertEqual("planned", self.runtime.store.load(second["receipt_id"])["state"])

    def test_failed_approval_validation_does_not_consume_durable_row(self):
        plan = self.plan(self.vault, self.envelope)
        with self.assertRaises(self.module.CoreApprovalError):
            self.apply(plan["receipt_id"], approval_text="CR-20260713-000001 거절", user_message_id=2)
        result = self.apply(
            plan["receipt_id"], approval_text="CR-20260713-000001 승인", user_message_id=2,
        )
        self.assertEqual("vault_committed_reconciliation_required", result["status"])

    def test_durable_authorization_has_one_winner_across_runtime_instances(self):
        def make_vault(name):
            vault = self.base / name
            (vault / "10_Sources").mkdir(parents=True)
            (vault / "20_Core").mkdir(parents=True)
            (vault / "50_Channel_Packs").mkdir(parents=True)
            (vault / "60_MOCs").mkdir(parents=True)
            (vault / self.source_rel).write_bytes(self.source_bytes)
            (vault / self.target_rel).write_text("target\n", encoding="utf-8")
            return vault

        shared_authorization = self.base / "shared-authorization.sqlite3"
        runtimes = [
            self.module.CoreActionRuntime(
                receipt_root=self.base / f"receipts-{index}",
                helper_path=HELPER,
                authorization_store_path=shared_authorization,
            )
            for index in (1, 2)
        ]
        vaults = [make_vault("vault-a"), make_vault("vault-b")]
        plans = [
            runtime.plan(
                vault, self.envelope,
                session_id="session-shared", turn_id="plan", user_message_id=1,
            )
            for runtime, vault in zip(runtimes, vaults)
        ]

        def apply(index):
            try:
                runtimes[index].apply(
                    plans[index]["receipt_id"],
                    approval_text="CR-20260713-000001 승인",
                    session_id="session-shared", turn_id="apply", user_message_id=2,
                )
                return "won"
            except self.module.CoreApprovalError:
                return "lost"

        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(apply, (0, 1)))
        self.assertEqual(1, outcomes.count("won"))
        self.assertEqual(1, outcomes.count("lost"))
        changed = ["[[20_Core/Target]]" in (vault / self.source_rel).read_text(encoding="utf-8") for vault in vaults]
        self.assertEqual([False, True], sorted(changed))

    def test_authorization_commit_survives_crash_before_claim_returns(self):
        store_path = self.base / "crash-store" / "authorization.sqlite3"
        store = self.module.CoreAuthorizationStore(store_path)
        marker = self.base / "claim-side-effect"
        child_code = f'''\
import importlib.util
import os
from pathlib import Path
spec = importlib.util.spec_from_file_location("core_actions_crash_child", {str(MODULE_PATH)!r})
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
store = module.CoreAuthorizationStore(Path({str(store_path)!r}))
def crash_claim():
    Path({str(marker)!r}).write_text("started", encoding="utf-8")
    os._exit(99)
store.consume(
    session_digest="session-digest",
    user_message_id=77,
    receipt_id="first",
    claim=crash_claim,
)
'''
        child = subprocess.run([sys.executable, "-c", child_code], check=False)
        self.assertEqual(99, child.returncode)
        self.assertEqual("started", marker.read_text(encoding="utf-8"))
        with sqlite3.connect(store_path) as connection:
            rows = connection.execute(
                "SELECT session_sha256, message_id, receipt_id FROM consumed_authorizations"
            ).fetchall()
        self.assertEqual([("session-digest", 77, "first")], rows)
        with self.assertRaises(self.module.CoreApprovalError):
            self.module.CoreAuthorizationStore(store_path).consume(
                session_digest="session-digest",
                user_message_id=77,
                receipt_id="second",
                claim=lambda: {"receipt_id": "second"},
            )

    def test_authorization_store_repairs_insecure_modes_and_fails_if_fchmod_fails(self):
        store_path = self.base / "mode-store" / "authorization.sqlite3"
        self.module.CoreAuthorizationStore(store_path)
        os.chmod(store_path.parent, 0o777)
        os.chmod(store_path, 0o666)

        self.module.CoreAuthorizationStore(store_path)
        self.assertEqual(0o700, stat.S_IMODE(store_path.parent.stat().st_mode))
        self.assertEqual(0o600, stat.S_IMODE(store_path.stat().st_mode))

        os.chmod(store_path.parent, 0o777)
        os.chmod(store_path, 0o666)
        with mock.patch.object(self.module.os, "fchmod", side_effect=PermissionError("denied")):
            with self.assertRaises(self.module.CoreApprovalError):
                self.module.CoreAuthorizationStore(store_path)

    def test_apply_fails_before_claim_when_store_permissions_cannot_be_resecured(self):
        plan = self.plan(self.vault, self.envelope)
        store_path = self.base / "authorization.sqlite3"
        os.chmod(store_path.parent, 0o777)
        os.chmod(store_path, 0o666)
        with mock.patch.object(self.module.os, "fchmod", side_effect=PermissionError("denied")):
            with self.assertRaises(self.module.CoreApprovalError):
                self.apply(
                    plan["receipt_id"],
                    approval_text="CR-20260713-000001 승인",
                    user_message_id=2,
                )
        self.assertEqual("planned", self.runtime.store.load(plan["receipt_id"])["state"])
        self.assertEqual(self.source_bytes, (self.vault / self.source_rel).read_bytes())

    def test_authorization_store_symlink_is_rejected(self):
        outside = self.base / "outside-authorization.sqlite3"
        outside.write_bytes(b"foreign")
        link = self.base / "authorization-link.sqlite3"
        link.symlink_to(outside)
        with self.assertRaises(self.module.CoreApprovalError):
            self.module.CoreActionRuntime(
                receipt_root=self.base / "other-receipts",
                helper_path=HELPER,
                authorization_store_path=link,
            )
        self.assertEqual(b"foreign", outside.read_bytes())

    def test_restart_requires_new_persisted_approval_after_replan(self):
        first = self.plan(self.vault, self.envelope, user_message_id=1)
        result = self.apply(
            first["receipt_id"], approval_text="CR-20260713-000001 승인", user_message_id=2,
        )
        self.assertEqual("vault_committed_reconciliation_required", result["status"])
        authorization_db = self.base / "authorization.sqlite3"
        self.assertEqual(0o600, stat.S_IMODE(authorization_db.stat().st_mode))
        self.assertNotIn("승인".encode("utf-8"), authorization_db.read_bytes())

        second_vault = self.base / "vault-after-restart"
        (second_vault / "10_Sources").mkdir(parents=True)
        (second_vault / "20_Core").mkdir(parents=True)
        (second_vault / "50_Channel_Packs").mkdir(parents=True)
        (second_vault / "60_MOCs").mkdir(parents=True)
        (second_vault / self.source_rel).write_bytes(self.source_bytes)
        (second_vault / self.target_rel).write_text("target\n", encoding="utf-8")
        restarted = self.module.CoreActionRuntime(
            receipt_root=self.base / "receipts",
            helper_path=HELPER,
            receipt_ttl_seconds=900,
        )
        second = restarted.plan(
            second_vault, self.envelope,
            session_id="session-1", turn_id="turn-replan", user_message_id=2,
        )
        with self.assertRaises(self.module.CoreApprovalError):
            restarted.apply(
                second["receipt_id"],
                approval_text="CR-20260713-000001 승인",
                session_id="session-1", turn_id="turn-reapply", user_message_id=2,
            )
        self.assertEqual(self.source_bytes, (second_vault / self.source_rel).read_bytes())

    def test_foreign_candidate_journal_is_not_attributed_to_receipt(self):
        original_plan = self.plan(self.vault, self.envelope)
        foreign = dict(self.envelope)
        foreign["candidate_code"] = "CR-20260713-000002"
        foreign_plan = self.plan(self.vault, foreign)
        foreign_result = self.apply(
            foreign_plan["receipt_id"], approval_text="CR-20260713-000002 승인",
            user_message_id=2,
        )
        self.assertEqual("vault_committed_reconciliation_required", foreign_result["status"])

        result = self.apply(
            original_plan["receipt_id"], approval_text="CR-20260713-000001 승인",
            user_message_id=3,
        )
        self.assertEqual("outcome_unknown", result["status"])
        self.assertEqual("CR-20260713-000002", result["journal_candidate_code"])
        self.assertNotIn("hashes", result)

    def test_same_candidate_different_transaction_journal_is_not_attributed(self):
        original_plan = self.plan(self.vault, self.envelope)
        other_rel = "20_Core/Other.md"
        (self.vault / other_rel).write_text("other\n", encoding="utf-8")
        foreign = json.loads(json.dumps(self.envelope))
        foreign["target_note_paths"] = [other_rel]
        foreign["action"]["new"] = "[[20_Core/Other]]"
        foreign_plan = self.plan(self.vault, foreign)
        foreign_result = self.apply(
            foreign_plan["receipt_id"], approval_text="CR-20260713-000001 승인",
            user_message_id=2,
        )
        self.assertEqual("vault_committed_reconciliation_required", foreign_result["status"])

        result = self.apply(
            original_plan["receipt_id"], approval_text="CR-20260713-000001 승인",
            user_message_id=3,
        )
        self.assertEqual("outcome_unknown", result["status"])
        self.assertEqual("CR-20260713-000001", result["journal_candidate_code"])
        self.assertNotEqual(
            self.runtime.store.load(original_plan["receipt_id"])["transaction_sha256"],
            result["journal_transaction_sha256"],
        )
        self.assertNotIn("hashes", result)

    def test_helper_timeout_preserves_receipt_as_outcome_unknown(self):
        plan = self.plan(self.vault, self.envelope)
        sleeper = self.base / "sleep-helper.py"
        sleeper.write_text("import time\ntime.sleep(2)\n", encoding="utf-8")
        self.runtime.helper_path = sleeper
        self.runtime.timeout = 0.05
        result = self.apply(plan["receipt_id"], approval_text="CR-20260713-000001 승인")
        self.assertEqual("outcome_unknown", result["status"])
        self.assertFalse(result["operation_completed"])
        stored = self.runtime.store.load(plan["receipt_id"])
        self.assertIsInstance(stored.get("envelope"), dict)


if __name__ == "__main__":
    unittest.main()
