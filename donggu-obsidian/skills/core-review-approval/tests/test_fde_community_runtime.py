#!/usr/bin/env python3
"""Receipt and exact-approval tests for the FDE Community native runtime."""
from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
import uuid

HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parents[2]
HELPER = HERE.parent / "scripts" / "fde-community-action.py"
VALIDATOR = HERE.parent / "scripts" / "validate-approval.py"
LEGACY = (
    "Personal Branding/60_Projects/PROJECT - FDE Community.md",
    "Personal Branding/60_Projects/FDE Community/_INDEX - FDE 커뮤니티.md",
    "Personal Branding/60_Projects/FDE Community/FDE 커뮤니티 전략.md",
    "Personal Branding/60_Projects/FDE Community/FDE_COMMUNITY_MEDIA_DESIGN.md",
    "Personal Branding/60_Projects/FDE Community/FDE_COMMUNITY_MEDIA_IMPLEMENTATION.md",
)


def _load_runtime_module():
    # The plugin directory has a hyphen, so tests load it under the same
    # temporary package convention used by the existing suite.
    import importlib.util
    import sys
    import types

    package_name = "donggu_obsidian_fde_test"
    if package_name not in sys.modules:
        package = types.ModuleType(package_name)
        package.__path__ = [str(PACKAGE)]
        sys.modules[package_name] = package
    runtime_name = package_name + ".runtime"
    if runtime_name not in sys.modules:
        spec = importlib.util.spec_from_file_location(
            runtime_name,
            PACKAGE / "runtime" / "__init__.py",
            submodule_search_locations=[str(PACKAGE / "runtime")],
        )
        if spec is None or spec.loader is None:
            raise AssertionError("runtime package unavailable")
        module = importlib.util.module_from_spec(spec)
        sys.modules[runtime_name] = module
        spec.loader.exec_module(module)
    return sys.modules[runtime_name]


class FDECommunityRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.vault = self.base / "vault"
        self.vault.mkdir()
        for index, rel in enumerate(LEGACY):
            path = self.vault / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"legacy-{index}\n", encoding="utf-8")
        runtime_module = _load_runtime_module()
        self.approval_error = runtime_module.CoreApprovalError
        self.runtime_error = runtime_module.CoreRuntimeError
        self.runtime = runtime_module.FDECommunityActionRuntime(
            receipt_root=self.base / "receipts",
            helper_path=HELPER,
            validator_path=VALIDATOR,
            receipt_ttl_seconds=300,
        )

    def snapshot(self):
        result = {}
        for path in sorted(self.vault.rglob("*")):
            if path.is_file() or path.is_symlink():
                result[str(path.relative_to(self.vault))] = (
                    path.read_bytes() if path.is_file() else None
                )
        return result

    def test_plan_requires_exact_preview_text_and_is_zero_write(self):
        before = self.snapshot()
        with self.assertRaises(self.approval_error):
            self.runtime.plan_fde_community(
                self.vault,
                session_id="session-1",
                plan_message_id=10,
                latest_user_text="수정안 보여 줘",
            )
        self.assertEqual(before, self.snapshot())
        result = self.runtime.plan_fde_community(
            self.vault,
            session_id="session-1",
            plan_message_id=11,
            latest_user_text="수정안 보여줘",
        )
        self.assertEqual("planned", result["status"])
        self.assertEqual(13, len(result["paths"]))
        self.assertEqual(8, result["created"])
        self.assertEqual(5, result["modified"])
        self.assertEqual(before, self.snapshot())

    def test_apply_requires_later_exact_message_then_readback_and_ack(self):
        plan = self.runtime.plan_fde_community(
            self.vault,
            session_id="session-2",
            plan_message_id=20,
            latest_user_text="수정안 보여줘",
        )
        before = self.snapshot()
        with self.assertRaises(self.approval_error):
            self.runtime.apply(
                plan["receipt_id"],
                latest_user_text="적용해 줘",
                session_id="session-2",
                user_message_id=21,
                latest_user_reader=lambda: (21, "적용해 줘"),
            )
        self.assertEqual(before, self.snapshot())
        result = self.runtime.apply(
            plan["receipt_id"],
            latest_user_text="적용해줘",
            session_id="session-2",
            user_message_id=22,
            latest_user_reader=lambda: (22, "적용해줘"),
        )
        self.assertEqual("vault_committed_reconciliation_required", result["status"])
        self.assertTrue((self.vault / "FDE Community/HOME.md").is_file())
        readback = self.runtime.readback(plan["receipt_id"])
        self.assertEqual("readback_verified", readback["status"])
        self.assertEqual(13, len(readback["hashes"]))
        completed = self.runtime.ack(
            plan["receipt_id"], completion_nonce=str(uuid.uuid4()),
        )
        self.assertEqual("completed", completed["status"])
        recovery = self.runtime.recovery_status(self.vault)
        self.assertEqual("no_transaction", recovery["state"])

    def test_fde_path_validation_does_not_widen_generic_core_contract(self):
        import importlib

        _load_runtime_module()
        core = importlib.import_module("donggu_obsidian_fde_test.runtime.core_actions")
        paths = sorted((*LEGACY, "FDE Community/HOME.md"))
        result = {
            "paths": paths,
            "hashes": {
                path: {"before": None, "after": "0" * 64}
                for path in paths
            },
        }
        with self.assertRaises(core.CoreHelperError):
            core._validated_hashes(result)
        self.assertEqual(
            {"10_Sources", "20_Core", "40_Channel_Packs", "50_MOCs"},
            core._ALLOWED_VAULT_ROOTS,
        )

    def test_readback_rejects_same_content_tree_with_different_identity(self):
        import shutil
        import os

        plan = self.runtime.plan_fde_community(
            self.vault,
            session_id="session-identity",
            plan_message_id=30,
            latest_user_text="수정안 보여줘",
        )
        applied = self.runtime.apply(
            plan["receipt_id"],
            latest_user_text="적용해줘",
            session_id="session-identity",
            user_message_id=31,
            latest_user_reader=lambda: (31, "적용해줘"),
        )
        self.assertEqual("vault_committed_reconciliation_required", applied["status"])

        replacement = self.vault / ".foreign-tree"
        shutil.copytree(self.vault / "FDE Community", replacement)
        shutil.rmtree(self.vault / "FDE Community")
        os.rename(replacement, self.vault / "FDE Community")

        with self.assertRaises(self.runtime_error):
            self.runtime.readback(plan["receipt_id"])
        self.assertEqual("ambiguous", self.runtime.store.load(plan["receipt_id"])["state"])

    def test_readback_rechecks_tree_identity_inside_receipt_commit_lock(self):
        import os
        import shutil

        plan = self.runtime.plan_fde_community(
            self.vault,
            session_id="session-readback-race",
            plan_message_id=40,
            latest_user_text="수정안 보여줘",
        )
        self.runtime.apply(
            plan["receipt_id"],
            latest_user_text="적용해줘",
            session_id="session-readback-race",
            user_message_id=41,
            latest_user_reader=lambda: (41, "적용해줘"),
        )
        original = self.runtime._validate_readback_context_after_hashes
        calls = 0

        def replace_after_first_check(receipt):
            nonlocal calls
            calls += 1
            original(receipt)
            if calls == 1:
                replacement = self.vault / ".foreign-readback-tree"
                shutil.copytree(self.vault / "FDE Community", replacement)
                shutil.rmtree(self.vault / "FDE Community")
                os.rename(replacement, self.vault / "FDE Community")

        setattr(self.runtime, "_validate_readback_context_after_hashes", replace_after_first_check)
        try:
            with self.assertRaises(self.runtime_error):
                self.runtime.readback(plan["receipt_id"])
        finally:
            setattr(self.runtime, "_validate_readback_context_after_hashes", original)

        self.assertGreaterEqual(calls, 2)
        self.assertEqual("ambiguous", self.runtime.store.load(plan["receipt_id"])["state"])

    def test_ack_rechecks_live_tree_after_helper_cleanup_before_receipt_completion(self):
        import os
        import shutil

        plan = self.runtime.plan_fde_community(
            self.vault,
            session_id="session-ack-race",
            plan_message_id=50,
            latest_user_text="수정안 보여줘",
        )
        self.runtime.apply(
            plan["receipt_id"],
            latest_user_text="적용해줘",
            session_id="session-ack-race",
            user_message_id=51,
            latest_user_reader=lambda: (51, "적용해줘"),
        )
        self.runtime.readback(plan["receipt_id"])
        original_run = self.runtime._run
        injected = False

        def replace_after_helper_ack(vault_root, envelope, *flags):
            nonlocal injected
            result = original_run(vault_root, envelope, *flags)
            if "--ack-candidate" in flags:
                replacement = self.vault / ".foreign-ack-tree"
                shutil.copytree(self.vault / "FDE Community", replacement)
                shutil.rmtree(self.vault / "FDE Community")
                os.rename(replacement, self.vault / "FDE Community")
                injected = True
            return result

        setattr(self.runtime, "_run", replace_after_helper_ack)
        try:
            result = self.runtime.ack(
                plan["receipt_id"], completion_nonce=str(uuid.uuid4()),
            )
        finally:
            setattr(self.runtime, "_run", original_run)

        self.assertTrue(injected)
        self.assertEqual("ambiguous", result["status"])
        self.assertEqual("ack_context_changed", result["reason"])
        self.assertEqual("ambiguous", self.runtime.store.load(plan["receipt_id"])["state"])

    def test_readback_transition_boundary_is_fenced(self):
        import os
        import shutil

        plan = self.runtime.plan_fde_community(
            self.vault,
            session_id="session-readback-transition-boundary",
            plan_message_id=60,
            latest_user_text="수정안 보여줘",
        )
        self.runtime.apply(
            plan["receipt_id"],
            latest_user_text="적용해줘",
            session_id="session-readback-transition-boundary",
            user_message_id=61,
            latest_user_reader=lambda: (61, "적용해줘"),
        )
        original_transition = self.runtime.store.transition
        injected = False

        def replace_before_readback_receipt_write(receipt, state, **updates):
            nonlocal injected
            if not injected and state == "reconciliation_required" and updates.get("readback_verified") is True:
                replacement = self.vault / ".foreign-readback-transition-tree"
                shutil.copytree(self.vault / "FDE Community", replacement)
                shutil.rmtree(self.vault / "FDE Community")
                os.rename(replacement, self.vault / "FDE Community")
                injected = True
            return original_transition(receipt, state, **updates)

        setattr(self.runtime.store, "transition", replace_before_readback_receipt_write)
        try:
            with self.assertRaises(self.runtime_error):
                self.runtime.readback(plan["receipt_id"])
        finally:
            setattr(self.runtime.store, "transition", original_transition)

        self.assertTrue(injected)
        self.assertEqual("ambiguous", self.runtime.store.load(plan["receipt_id"])["state"])

    def test_ack_transition_boundary_is_fenced(self):
        import os
        import shutil

        plan = self.runtime.plan_fde_community(
            self.vault,
            session_id="session-ack-transition-boundary",
            plan_message_id=70,
            latest_user_text="수정안 보여줘",
        )
        self.runtime.apply(
            plan["receipt_id"],
            latest_user_text="적용해줘",
            session_id="session-ack-transition-boundary",
            user_message_id=71,
            latest_user_reader=lambda: (71, "적용해줘"),
        )
        self.runtime.readback(plan["receipt_id"])
        original_transition = self.runtime.store.transition
        injected = False

        def replace_before_completed_receipt_write(receipt, state, **updates):
            nonlocal injected
            if not injected and state == "completed":
                replacement = self.vault / ".foreign-ack-transition-tree"
                shutil.copytree(self.vault / "FDE Community", replacement)
                shutil.rmtree(self.vault / "FDE Community")
                os.rename(replacement, self.vault / "FDE Community")
                injected = True
            return original_transition(receipt, state, **updates)

        setattr(self.runtime.store, "transition", replace_before_completed_receipt_write)
        try:
            result = self.runtime.ack(
                plan["receipt_id"], completion_nonce=str(uuid.uuid4()),
            )
        finally:
            setattr(self.runtime.store, "transition", original_transition)

        self.assertTrue(injected)
        self.assertEqual("ambiguous", result["status"])
        self.assertEqual("ambiguous", self.runtime.store.load(plan["receipt_id"])["state"])
        self.assertTrue((self.vault / ".fde-community-review-journal.json").exists())

    def test_ack_cleanup_boundary_converges_to_ambiguous_after_completion_write(self):
        import os
        import shutil

        plan = self.runtime.plan_fde_community(
            self.vault,
            session_id="session-ack-cleanup-boundary",
            plan_message_id=80,
            latest_user_text="수정안 보여줘",
        )
        self.runtime.apply(
            plan["receipt_id"],
            latest_user_text="적용해줘",
            session_id="session-ack-cleanup-boundary",
            user_message_id=81,
            latest_user_reader=lambda: (81, "적용해줘"),
        )
        self.runtime.readback(plan["receipt_id"])
        original_run = self.runtime._run
        cleanup_calls = 0

        def replace_after_cleanup(vault_root, envelope, *flags):
            nonlocal cleanup_calls
            result = original_run(vault_root, envelope, *flags)
            if "--ack-candidate" in flags and "--ack-retain-journal" not in flags:
                cleanup_calls += 1
                replacement = self.vault / ".foreign-ack-cleanup-tree"
                shutil.copytree(self.vault / "FDE Community", replacement)
                shutil.rmtree(self.vault / "FDE Community")
                os.rename(replacement, self.vault / "FDE Community")
            return result

        setattr(self.runtime, "_run", replace_after_cleanup)
        try:
            result = self.runtime.ack(
                plan["receipt_id"], completion_nonce=str(uuid.uuid4()),
            )
        finally:
            setattr(self.runtime, "_run", original_run)

        self.assertEqual(1, cleanup_calls)
        self.assertEqual("ambiguous", result["status"])
        self.assertEqual("ack_cleanup_or_context_changed", result["reason"])
        self.assertEqual("ambiguous", self.runtime.store.load(plan["receipt_id"])["state"])

    def test_ack_final_validation_fence_cannot_return_completed_after_tree_replacement(self):
        import os
        import shutil

        plan = self.runtime.plan_fde_community(
            self.vault,
            session_id="session-ack-final-fence",
            plan_message_id=90,
            latest_user_text="수정안 보여줘",
        )
        self.runtime.apply(
            plan["receipt_id"],
            latest_user_text="적용해줘",
            session_id="session-ack-final-fence",
            user_message_id=91,
            latest_user_reader=lambda: (91, "적용해줘"),
        )
        self.runtime.readback(plan["receipt_id"])
        original_validate = self.runtime._validate_ack_context_before_completion
        calls = 0
        injected = False

        def replace_after_final_validation(receipt):
            nonlocal calls, injected
            result = original_validate(receipt)
            calls += 1
            if calls == 3 and not injected:
                replacement = self.vault / ".foreign-ack-final-fence-tree"
                shutil.copytree(self.vault / "FDE Community", replacement)
                shutil.rmtree(self.vault / "FDE Community")
                os.rename(replacement, self.vault / "FDE Community")
                injected = True
            return result

        setattr(self.runtime, "_validate_ack_context_before_completion", replace_after_final_validation)
        try:
            result = self.runtime.ack(
                plan["receipt_id"], completion_nonce=str(uuid.uuid4()),
            )
        finally:
            setattr(self.runtime, "_validate_ack_context_before_completion", original_validate)

        self.assertTrue(injected)
        self.assertGreaterEqual(calls, 3)
        self.assertNotEqual("completed", result["status"])
        self.assertEqual("ambiguous", self.runtime.store.load(plan["receipt_id"])["state"])

    def test_apply_transition_boundary_converges_to_ambiguous_after_tree_replacement(self):
        import os
        import shutil

        plan = self.runtime.plan_fde_community(
            self.vault,
            session_id="session-apply-transition-boundary",
            plan_message_id=100,
            latest_user_text="수정안 보여줘",
        )
        original_status = self.runtime.recovery_status
        calls = 0
        injected = False

        def replace_after_first_status(vault_root):
            nonlocal calls, injected
            result = original_status(vault_root)
            calls += 1
            if not injected and result.get("state") == "committed":
                replacement = self.vault / ".foreign-apply-transition-tree"
                shutil.copytree(self.vault / "FDE Community", replacement)
                shutil.rmtree(self.vault / "FDE Community")
                os.rename(replacement, self.vault / "FDE Community")
                injected = True
            return result

        self.runtime.recovery_status = replace_after_first_status
        try:
            result = self.runtime.apply(
                plan["receipt_id"],
                latest_user_text="적용해줘",
                session_id="session-apply-transition-boundary",
                user_message_id=101,
                latest_user_reader=lambda: (101, "적용해줘"),
            )
        finally:
            self.runtime.recovery_status = original_status

        self.assertTrue(injected)
        self.assertGreaterEqual(calls, 2)
        self.assertEqual("ambiguous", result["status"])
        self.assertEqual("ambiguous", self.runtime.store.load(plan["receipt_id"])["state"])

    def test_malformed_applied_helper_result_does_not_leave_receipt_applying(self):
        plan = self.runtime.plan_fde_community(
            self.vault,
            session_id="session-malformed-helper-result",
            plan_message_id=110,
            latest_user_text="수정안 보여줘",
        )
        original_run = self.runtime._run
        malformed = {
            "status": "applied",
            "state": "committed",
            "candidate_code": plan["candidate_code"],
            "paths": list(plan["paths"]),
            "hashes": dict(plan["hashes"]),
            # Deliberately omit tree_identity.
        }
        self.runtime._run = lambda *args, **kwargs: (0, malformed)
        try:
            result = self.runtime.apply(
                plan["receipt_id"],
                latest_user_text="적용해줘",
                session_id="session-malformed-helper-result",
                user_message_id=111,
                latest_user_reader=lambda: (111, "적용해줘"),
            )
        finally:
            self.runtime._run = original_run

        self.assertNotEqual("applying", self.runtime.store.load(plan["receipt_id"])["state"])
        self.assertIn(result["status"], {"revoked", "ambiguous"})


if __name__ == "__main__":
    unittest.main()
