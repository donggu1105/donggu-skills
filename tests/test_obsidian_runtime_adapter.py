#!/usr/bin/env python3
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
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

    def test_plan_runs_real_helper_dry_run_and_binds_receipt(self):
        before = self.source.read_bytes()
        result = self.runtime.plan(self.vault, self.envelope)
        self.assertEqual("planned", result["status"])
        self.assertEqual([self.source_rel], result["paths"])
        self.assertEqual(sha(self.source_bytes), result["hashes"][self.source_rel]["before"])
        self.assertEqual(before, self.source.read_bytes())
        receipt = json.loads((self.base / "receipts" / f"{result['receipt_id']}.json").read_text(encoding="utf-8"))
        self.assertEqual(os.path.abspath(str(self.vault)), receipt["vault_root"])
        self.assertEqual(result["envelope_sha256"], receipt["envelope_sha256"])

    def test_apply_commits_vault_and_requires_db_reconciliation(self):
        plan = self.runtime.plan(self.vault, self.envelope)
        result = self.runtime.apply(plan["receipt_id"], approval_text="CR-20260713-000001 승인")
        self.assertEqual("vault_committed_reconciliation_required", result["status"])
        self.assertEqual("applied", result["helper_status"])
        self.assertEqual("committed", result["journal_state"])
        self.assertIn("[[20_Core/Target]]", self.source.read_text(encoding="utf-8"))
        self.assertEqual(sha(self.source.read_bytes()), result["hashes"][self.source_rel]["after"])
        status = self.runtime.recovery_status(self.vault)
        self.assertEqual("committed", status["state"])
        self.assertEqual("CR-20260713-000001", status["candidate_code"])
        with self.assertRaises(self.module.CoreReceiptError):
            self.runtime.apply(plan["receipt_id"], approval_text="CR-20260713-000001 승인")

    def test_apply_rejects_empty_approval_without_mutation(self):
        plan = self.runtime.plan(self.vault, self.envelope)
        with self.assertRaises(self.module.CoreApprovalError):
            self.runtime.apply(plan["receipt_id"], approval_text=" ")
        self.assertEqual(self.source_bytes, self.source.read_bytes())

    def test_apply_binds_exact_approval_decision_and_candidate(self):
        for text in ("거절", "보류", "일단 해줘", "CR-20260713-000001 거절", "CR-20260713-999999 승인"):
            plan = self.runtime.plan(self.vault, self.envelope)
            with self.assertRaises(self.module.CoreApprovalError):
                self.runtime.apply(plan["receipt_id"], approval_text=text)
            self.assertEqual(self.source_bytes, self.source.read_bytes())
            self.assertEqual("planned", self.runtime.store.load(plan["receipt_id"])["state"])

    def test_receipt_hash_tampering_is_rejected_before_vault_mutation(self):
        plan = self.runtime.plan(self.vault, self.envelope)
        path = self.base / "receipts" / f"{plan['receipt_id']}.json"
        receipt = json.loads(path.read_text(encoding="utf-8"))
        receipt["hashes"][self.source_rel]["after"] = "0" * 64
        path.write_text(json.dumps(receipt), encoding="utf-8")
        with self.assertRaises(self.module.CoreReceiptError):
            self.runtime.apply(plan["receipt_id"], approval_text="CR-20260713-000001 승인")
        self.assertEqual(self.source_bytes, self.source.read_bytes())
        self.assertEqual("planned", self.runtime.store.load(plan["receipt_id"])["state"])

    def test_vault_root_symlink_is_rejected(self):
        link = self.base / "vault-link"
        link.symlink_to(self.vault, target_is_directory=True)
        with self.assertRaises(self.module.CoreHelperError):
            self.runtime.plan(link, self.envelope)

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
            self.runtime.plan(self.vault, bad)
        self.assertNotIn("private-envelope-value", str(caught.exception))
        self.assertLess(len(str(caught.exception)), 200)

    def test_core_receipt_claim_allows_exactly_one_concurrent_winner(self):
        plan = self.runtime.plan(self.vault, self.envelope)

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

    def test_helper_timeout_preserves_receipt_as_outcome_unknown(self):
        plan = self.runtime.plan(self.vault, self.envelope)
        sleeper = self.base / "sleep-helper.py"
        sleeper.write_text("import time\ntime.sleep(2)\n", encoding="utf-8")
        self.runtime.helper_path = sleeper
        self.runtime.timeout = 0.05
        result = self.runtime.apply(plan["receipt_id"], approval_text="CR-20260713-000001 승인")
        self.assertEqual("outcome_unknown", result["status"])
        self.assertFalse(result["operation_completed"])
        stored = self.runtime.store.load(plan["receipt_id"])
        self.assertIsInstance(stored.get("envelope"), dict)


if __name__ == "__main__":
    unittest.main()
