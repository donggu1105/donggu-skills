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


if __name__ == "__main__":
    unittest.main()
