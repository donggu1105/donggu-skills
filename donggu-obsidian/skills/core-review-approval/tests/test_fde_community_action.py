#!/usr/bin/env python3
"""Native FDE Community separation helper contract tests."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


HERE = Path(__file__).resolve().parent
SCRIPT = HERE.parent / "scripts" / "fde-community-action.py"
LEGACY = (
    "Personal Branding/60_Projects/PROJECT - FDE Community.md",
    "Personal Branding/60_Projects/FDE Community/_INDEX - FDE 커뮤니티.md",
    "Personal Branding/60_Projects/FDE Community/FDE 커뮤니티 전략.md",
    "Personal Branding/60_Projects/FDE Community/FDE_COMMUNITY_MEDIA_DESIGN.md",
    "Personal Branding/60_Projects/FDE Community/FDE_COMMUNITY_MEDIA_IMPLEMENTATION.md",
)
NEW = (
    "FDE Community/AGENTS.md",
    "FDE Community/HOME.md",
    "FDE Community/ONTOLOGY.md",
    "FDE Community/Events/INDEX - Events.md",
    "FDE Community/Meetings/INDEX - Meetings.md",
    "FDE Community/Recordings/INDEX - Recordings.md",
    "FDE Community/Cases/INDEX - Cases.md",
    "FDE Community/Operations/INDEX - Operations.md",
)
ALL_PATHS = sorted(LEGACY + NEW)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class FDECommunityActionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        for rel in LEGACY:
            path = self.root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(("---\ntype: fixture\n---\n\n" + rel + "\n").encode())
        self.source_rel = LEGACY[0]

    def envelope(self, **updates):
        before_hashes: dict[str, str | None] = {
            rel: sha((self.root / rel).read_bytes()) for rel in LEGACY
        }
        before_hashes.update({rel: None for rel in NEW})
        value = {
            "schema_version": 1,
            "candidate_code": "CR-20260816-000001",
            "candidate_type": "fde_community_separation",
            "source_note_path": self.source_rel,
            "source_sha256": sha((self.root / self.source_rel).read_bytes()),
            "claim": "FDE Community 운영 정본을 독립 영역으로 분리",
            "target_note_paths": ALL_PATHS,
            "action": {
                "op": "create_fde_community_structure",
                "schema_version": 1,
                "template_version": 1,
                "manifest_id": "fde-community-separation.v1",
                "manifest_sha256": "86a4c29e2e70a9083838ca76065c4b64886db579a0fe2dc3576be536b97dce7b",
                "before_hashes": before_hashes,
            },
        }
        value.update(updates)
        return value

    def run_helper(self, envelope, *args):
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--vault-root", str(self.root), *args],
            input=json.dumps(envelope, ensure_ascii=False).encode("utf-8"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

    def ack_args(self, envelope):
        status = self.run_helper(envelope, "--recovery-status")
        self.assertEqual(0, status.returncode, status.stderr)
        transaction = json.loads(status.stdout)["transaction_sha256"]
        return "--ack-candidate", envelope["candidate_code"], "--ack-transaction", transaction

    def snapshot(self):
        result = {}
        for path in self.root.rglob("*"):
            if path.is_file() or path.is_symlink():
                result[str(path.relative_to(self.root))] = path.read_bytes() if path.is_file() else None
        return result

    @staticmethod
    def load_helper():
        spec = importlib.util.spec_from_file_location(
            "fde_community_action_test_instance", SCRIPT,
        )
        if spec is None or spec.loader is None:
            raise AssertionError("helper module unavailable")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_fde_manifest_dry_run_is_zero_write_and_returns_all_thirteen_paths(self):
        before = self.snapshot()
        proc = self.run_helper(self.envelope(), "--dry-run")
        self.assertEqual(0, proc.returncode, proc.stderr)
        result = json.loads(proc.stdout)
        self.assertEqual("planned", result["status"])
        self.assertEqual(ALL_PATHS, result["paths"])
        self.assertEqual(set(ALL_PATHS), set(result["hashes"]))
        self.assertEqual(before, self.snapshot())

    def test_fde_manifest_rejects_tampered_manifest_id_and_before_hash(self):
        bad_id = self.envelope()
        bad_id["action"]["manifest_id"] = "fde-community-separation.tampered"
        proc = self.run_helper(bad_id, "--dry-run")
        self.assertEqual(2, proc.returncode)
        bad_hash = self.envelope()
        bad_hash["action"]["before_hashes"][LEGACY[0]] = "0" * 64
        proc = self.run_helper(bad_hash, "--dry-run")
        self.assertEqual(2, proc.returncode)

    def test_apply_commits_all_files_and_ack_cleans_journal_artifacts(self):
        env = self.envelope()
        proc = self.run_helper(env)
        self.assertEqual(0, proc.returncode, proc.stderr)
        result = json.loads(proc.stdout)
        self.assertEqual("applied", result["status"])
        self.assertEqual(ALL_PATHS, result["paths"])
        helper = self.load_helper()
        for rel in ALL_PATHS:
            self.assertEqual(
                helper.MANIFEST[rel].encode("utf-8"),
                (self.root / rel).read_bytes(),
            )
        status = self.run_helper(env, "--recovery-status")
        self.assertEqual(0, status.returncode, status.stderr)
        self.assertEqual("committed", json.loads(status.stdout)["state"])
        ack = self.run_helper(env, *self.ack_args(env))
        self.assertEqual(0, ack.returncode, ack.stderr)
        status = self.run_helper(env, "--recovery-status")
        self.assertEqual("no_transaction", json.loads(status.stdout)["state"])
        artifacts = [
            path.name for path in self.root.rglob("*")
            if path.name.startswith(".fde-community-")
        ]
        self.assertEqual([], artifacts)

    def test_failure_installing_new_tree_rolls_back_legacy_files(self):
        helper = self.load_helper()
        env = self.envelope()
        before = self.snapshot()
        plan = helper.prepare(self.root, env)
        original = helper._core.atomic_exclusive_at

        def fail_target_install(parent_fd, source, target):
            if target == helper.TARGET_ROOT:
                raise OSError("injected target install failure")
            return original(parent_fd, source, target)

        helper._core.atomic_exclusive_at = fail_target_install
        try:
            code = helper._apply(plan, env["candidate_code"])
        finally:
            helper._core.atomic_exclusive_at = original
        self.assertEqual(3, code)
        self.assertEqual(before, self.snapshot())
        self.assertFalse((self.root / "FDE Community").exists())

    def test_recover_only_rolls_back_partially_swapped_prepared_transaction(self):
        helper = self.load_helper()
        env = self.envelope()
        before = self.snapshot()
        plan = helper.prepare(self.root, env)
        token = "1" * 24
        tree_stage = helper._stage_tree(self.root, plan["new_files"], token)
        stages, backups = helper._legacy_stage_and_backup(plan, token)
        payload = helper._journal_payload(
            env["candidate_code"], token, "prepared", plan,
            stages, backups, tree_stage, False,
        )
        helper._write_journal(self.root, payload, install=True)
        rel = sorted(LEGACY)[0]
        ref = plan["legacy_refs"][rel]
        helper._core.atomic_swap_at(ref.parent_fd, stages[rel], ref.name)
        helper._core.fsync_fd(ref.parent_fd)
        recovered = self.run_helper(env, "--recover-only")
        self.assertEqual(0, recovered.returncode, recovered.stderr)
        self.assertEqual("recovered", json.loads(recovered.stdout)["status"])
        self.assertEqual(before, self.snapshot())
        self.assertFalse((self.root / "FDE Community").exists())

    def test_existing_fde_community_root_fails_closed_without_writes(self):
        (self.root / "FDE Community").mkdir()
        before = self.snapshot()
        proc = self.run_helper(self.envelope(), "--dry-run")
        self.assertEqual(2, proc.returncode)
        self.assertEqual(before, self.snapshot())

    def test_ack_rejects_extra_tree_file_without_deleting_it(self):
        env = self.envelope()
        applied = self.run_helper(env)
        self.assertEqual(0, applied.returncode, applied.stderr)
        foreign = self.root / "FDE Community" / "foreign.md"
        foreign.write_text("do not delete\n", encoding="utf-8")
        ack = self.run_helper(env, *self.ack_args(env))
        self.assertEqual(4, ack.returncode)
        self.assertEqual("do not delete\n", foreign.read_text(encoding="utf-8"))
        status = self.run_helper(env, "--recovery-status")
        self.assertEqual("committed", json.loads(status.stdout)["state"])

    def test_ack_rejects_foreign_stage_artifact_without_deleting_it(self):
        env = self.envelope()
        applied = self.run_helper(env)
        self.assertEqual(0, applied.returncode, applied.stderr)
        stage = next(self.root.rglob(".fde-community-stage-*"))
        stage.write_text("foreign stage\n", encoding="utf-8")
        ack = self.run_helper(env, *self.ack_args(env))
        self.assertEqual(6, ack.returncode)
        self.assertEqual("foreign stage\n", stage.read_text(encoding="utf-8"))

    def test_ack_requires_matching_transaction_fingerprint(self):
        env = self.envelope()
        applied = self.run_helper(env)
        self.assertEqual(0, applied.returncode, applied.stderr)
        ack = self.run_helper(
            env,
            "--ack-candidate", env["candidate_code"],
            "--ack-transaction", "0" * 64,
        )
        self.assertEqual(4, ack.returncode)
        status = self.run_helper(env, "--recovery-status")
        self.assertEqual("committed", json.loads(status.stdout)["state"])

    def test_recovery_rejects_exact_foreign_tree_with_different_identity(self):
        helper = self.load_helper()
        env = self.envelope()
        plan = helper.prepare(self.root, env)
        token = "2" * 24
        tree_stage = helper._stage_tree(self.root, plan["new_files"], token)
        stages, backups = helper._legacy_stage_and_backup(plan, token)
        payload = helper._journal_payload(
            env["candidate_code"], token, "prepared", plan,
            stages, backups, tree_stage, False,
        )
        helper._write_journal(self.root, payload, install=True)
        root_fd = helper._core.open_root(self.root)
        try:
            helper._core.atomic_exclusive_at(root_fd, tree_stage, helper.TARGET_ROOT)
        finally:
            os.close(root_fd)
        shutil.rmtree(self.root / helper.TARGET_ROOT)
        for rel in NEW:
            path = self.root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(helper.MANIFEST[rel], encoding="utf-8")
        recovered = self.run_helper(env, "--recover-only")
        self.assertEqual(4, recovered.returncode)
        self.assertTrue((self.root / helper.JOURNAL).is_file())
        self.assertTrue((self.root / helper.TARGET_ROOT).is_dir())

    def test_manifest_sha256_is_bound_to_the_package_manifest(self):
        env = self.envelope()
        env["action"]["manifest_sha256"] = "0" * 64
        proc = self.run_helper(env, "--dry-run")
        self.assertEqual(2, proc.returncode)

    def test_tree_collision_is_rejected_before_legacy_swaps(self):
        helper = self.load_helper()
        env = self.envelope()
        plan = helper.prepare(self.root, env)
        before = self.snapshot()
        original_exclusive = helper._core.atomic_exclusive_at
        original_swap = helper._core.atomic_swap_at
        install_attempted = False
        forward_swaps = []

        def collide(parent_fd, source, target):
            nonlocal install_attempted
            if target == helper.TARGET_ROOT:
                install_attempted = True
                os.mkdir(target, dir_fd=parent_fd)
            return original_exclusive(parent_fd, source, target)

        def count_forward(parent_fd, source, target):
            if not install_attempted and source.startswith(".fde-community-stage-"):
                forward_swaps.append(target)
            return original_swap(parent_fd, source, target)

        helper._core.atomic_exclusive_at = collide
        helper._core.atomic_swap_at = count_forward
        try:
            code = helper._apply(plan, env["candidate_code"])
        finally:
            helper._core.atomic_exclusive_at = original_exclusive
            helper._core.atomic_swap_at = original_swap
        self.assertEqual(3, code)
        self.assertEqual([], forward_swaps)
        self.assertEqual(before, self.snapshot())

    def test_foreign_stage_is_not_swapped_or_cleaned_and_journal_remains(self):
        helper = self.load_helper()
        env = self.envelope()
        plan = helper.prepare(self.root, env)
        before = self.snapshot()
        original_unchanged = helper._legacy_unchanged
        tampered = False

        def tamper_once(current_plan):
            nonlocal tampered
            result = original_unchanged(current_plan)
            if not tampered:
                rel = sorted(helper.LEGACY_PATHS)[0]
                ref = current_plan["legacy_refs"][rel]
                stage_name = next(
                    name for name in os.listdir(ref.parent_fd)
                    if name.startswith(".fde-community-stage-")
                )
                stage_fd = os.open(stage_name, os.O_WRONLY | os.O_TRUNC, dir_fd=ref.parent_fd)
                os.write(stage_fd, b"foreign stage\n")
                os.close(stage_fd)
                tampered = True
            return result

        setattr(helper, "_legacy_unchanged", tamper_once)
        try:
            code = helper._apply(plan, env["candidate_code"])
        finally:
            setattr(helper, "_legacy_unchanged", original_unchanged)
        self.assertEqual(4, code)
        for rel in helper.LEGACY_PATHS:
            self.assertEqual(before[rel], (self.root / rel).read_bytes())
        self.assertTrue((self.root / helper.JOURNAL).is_file())

    def test_published_tree_is_atomically_captured_when_legacy_swap_fails(self):
        helper = self.load_helper()
        env = self.envelope()
        plan = helper.prepare(self.root, env)
        before = self.snapshot()
        original_swap_legacy = helper._swap_legacy
        setattr(helper, "_swap_legacy", lambda _plan, _stages: False)
        try:
            code = helper._apply(plan, env["candidate_code"])
        finally:
            setattr(helper, "_swap_legacy", original_swap_legacy)
        self.assertEqual(3, code)
        self.assertEqual(before, self.snapshot())
        self.assertFalse((self.root / helper.TARGET_ROOT).exists())
        self.assertFalse((self.root / helper.JOURNAL).exists())


if __name__ == "__main__":
    unittest.main()
