#!/usr/bin/env python3
"""Native FDE Community separation helper contract tests."""

from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import stat
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

    def prepare(self, helper, envelope):
        plan = helper.prepare(self.root, envelope)
        self.addCleanup(helper._close_legacy_refs, plan["legacy_refs"])
        return plan

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

    def test_ack_retain_journal_leaves_evidence_for_receipt_completion(self):
        env = self.envelope()
        applied = self.run_helper(env)
        self.assertEqual(0, applied.returncode, applied.stderr)
        args = self.ack_args(env)
        retained = self.run_helper(env, *args, "--ack-retain-journal")
        self.assertEqual(0, retained.returncode, retained.stderr)
        self.assertEqual("committed", json.loads(self.run_helper(env, "--recovery-status").stdout)["state"])
        cleaned = self.run_helper(env, *args)
        self.assertEqual(0, cleaned.returncode, cleaned.stderr)
        self.assertEqual("no_transaction", json.loads(self.run_helper(env, "--recovery-status").stdout)["state"])

    def test_failure_installing_new_tree_rolls_back_legacy_files(self):
        helper = self.load_helper()
        env = self.envelope()
        before = self.snapshot()
        plan = self.prepare(helper, env)
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

    def test_stage_creation_failure_does_not_unlink_replaced_foreign_artifact(self):
        helper = self.load_helper()
        plan = self.prepare(helper, self.envelope())
        original = helper._core.write_temp
        calls = 0
        foreign_stage = None

        def fail_on_second_stage(parent_fd, prefix, data, mode):
            nonlocal calls, foreign_stage
            calls += 1
            if calls == 3:
                foreign_stage = next(self.root.rglob(".fde-community-stage-*"))
                foreign_stage.unlink()
                foreign_stage.write_bytes(b"FOREIGN-STAGE-CREATION-RACE\n")
                raise OSError("injected stage creation failure")
            return original(parent_fd, prefix, data, mode)

        helper._core.write_temp = fail_on_second_stage
        try:
            with self.assertRaises(OSError):
                helper._legacy_stage_and_backup(plan, "4" * 24)
        finally:
            helper._core.write_temp = original

        self.assertIsNotNone(foreign_stage)
        assert foreign_stage is not None
        self.assertEqual(b"FOREIGN-STAGE-CREATION-RACE\n", foreign_stage.read_bytes())

    def test_prejournal_cleanup_never_deletes_original_inode_moved_to_stage_name(self):
        helper = self.load_helper()
        plan = self.prepare(helper, self.envelope())
        token = "5" * 24
        stages, backups = helper._legacy_stage_and_backup(plan, token)
        rel = sorted(LEGACY)[0]
        ref = plan["legacy_refs"][rel]
        original = (self.root / rel).read_bytes()
        os.unlink(stages[rel], dir_fd=ref.parent_fd)
        helper._core.atomic_exclusive_at(ref.parent_fd, ref.name, stages[rel])
        helper._core.fsync_fd(ref.parent_fd)

        cleaned = helper._cleanup_legacy(plan, stages, backups)

        self.assertFalse(cleaned)
        self.assertEqual(original, helper._core.read_at(ref.parent_fd, stages[rel], text=False))

    def test_swap_rejects_same_content_foreign_stage_inode_at_cas_boundary(self):
        helper = self.load_helper()
        plan = self.prepare(helper, self.envelope())
        stages, backups = helper._legacy_stage_and_backup(plan, "6" * 24)
        rel = sorted(LEGACY)[0]
        ref = plan["legacy_refs"][rel]
        original_cas = helper._core.cas_install
        replaced = False

        def replace_stage_before_cas(cas_ref, original, desired, stage):
            nonlocal replaced
            if not replaced and stage == stages[rel]:
                replaced = True
                data = helper._core.read_at(cas_ref.parent_fd, stage, text=False)
                os.unlink(stage, dir_fd=cas_ref.parent_fd)
                fd = os.open(stage, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644, dir_fd=cas_ref.parent_fd)
                try:
                    os.write(fd, data)
                finally:
                    os.close(fd)
            return original_cas(cas_ref, original, desired, stage)

        setattr(helper._core, "cas_install", replace_stage_before_cas)
        try:
            swapped = helper._swap_legacy(plan, stages)
        finally:
            setattr(helper._core, "cas_install", original_cas)

        self.assertTrue(replaced)
        self.assertFalse(swapped)
        self.assertNotEqual(
            helper._artifact_identity(ref, ref.name),
            plan["stage_identities"][rel],
        )

    def test_recover_only_rolls_back_partially_swapped_prepared_transaction(self):
        helper = self.load_helper()
        env = self.envelope()
        before = self.snapshot()
        plan = self.prepare(helper, env)
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

    def test_prepared_recovery_rejects_mode_change_after_restore_cas(self):
        helper = self.load_helper()
        env = self.envelope()
        rel = sorted(LEGACY)[0]
        target = self.root / rel
        target.chmod(0o600)
        plan = self.prepare(helper, env)
        token = "3" * 24
        tree_stage = helper._stage_tree(self.root, plan["new_files"], token)
        stages, backups = helper._legacy_stage_and_backup(plan, token)
        payload = helper._journal_payload(
            env["candidate_code"], token, "prepared", plan,
            stages, backups, tree_stage, False,
        )
        helper._write_journal(self.root, payload, install=True)
        ref = plan["legacy_refs"][rel]
        helper._core.atomic_swap_at(ref.parent_fd, stages[rel], ref.name)
        helper._core.fsync_fd(ref.parent_fd)

        original = helper._core.cas_install

        def chmod_after_restore(*args, **kwargs):
            restored = original(*args, **kwargs)
            if restored:
                target.chmod(0o644)
            return restored

        helper._core.cas_install = chmod_after_restore
        try:
            with self.assertRaises(helper.ApplyError):
                helper._recover_prepared(self.root, payload)
        finally:
            helper._core.cas_install = original

        self.assertEqual(0o644, stat.S_IMODE(target.stat().st_mode))
        self.assertTrue((self.root / helper.JOURNAL).is_file())
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
        self.assertEqual(4, ack.returncode)
        self.assertEqual("foreign stage\n", stage.read_text(encoding="utf-8"))

    def test_ack_rejects_same_content_foreign_stage_inode_without_deleting_it(self):
        helper = self.load_helper()
        env = self.envelope()
        applied = self.run_helper(env)
        self.assertEqual(0, applied.returncode, applied.stderr)
        stage = next(self.root.rglob(".fde-community-stage-*"))
        replacement = self.root / ".same-content-stage"
        replacement.write_bytes(stage.read_bytes())
        stage.unlink()
        os.rename(replacement, stage)

        ack = self.run_helper(env, *self.ack_args(env))

        self.assertEqual(4, ack.returncode)
        self.assertTrue(stage.is_file())
        self.assertTrue((self.root / helper.JOURNAL).is_file())

    def test_ack_cleanup_never_unlinks_artifact_replaced_after_identity_check(self):
        helper = self.load_helper()
        env = self.envelope()
        applied = self.run_helper(env)
        self.assertEqual(0, applied.returncode, applied.stderr)
        stage = next(self.root.rglob(".fde-community-stage-*"))
        journal = helper._read_journal(self.root)
        self.assertIsNotNone(journal)
        transaction = helper.transaction_sha256(journal["candidate_code"], journal["entries"])
        original_move = helper._move_exclusive_for_cleanup
        injected = False

        def replace_before_capture(parent_fd, source, prefix):
            nonlocal injected
            if not injected and source == stage.name and prefix == ".fde-community-cleanup-file-":
                injected = True
                os.unlink(source, dir_fd=parent_fd)
                descriptor = os.open(
                    source, os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                    0o600, dir_fd=parent_fd,
                )
                try:
                    os.write(descriptor, b"FOREIGN-RACE-ARTIFACT\n")
                    os.fsync(descriptor)
                finally:
                    os.close(descriptor)
                helper._core.fsync_fd(parent_fd)
            return original_move(parent_fd, source, prefix)

        setattr(helper, "_move_exclusive_for_cleanup", replace_before_capture)
        try:
            with self.assertRaises(helper.CleanupRetryError):
                helper._ack(self.root, env["candidate_code"], transaction)
        finally:
            setattr(helper, "_move_exclusive_for_cleanup", original_move)

        self.assertTrue(injected)
        self.assertEqual(b"FOREIGN-RACE-ARTIFACT\n", stage.read_bytes())
        self.assertTrue((self.root / helper.JOURNAL).is_file())

    def test_journal_update_preserves_foreign_old_journal_temp(self):
        helper = self.load_helper()
        env = self.envelope()
        applied = self.run_helper(env)
        self.assertEqual(0, applied.returncode, applied.stderr)
        journal = helper._read_journal(self.root)
        self.assertIsNotNone(journal)
        original_cleanup = helper._cleanup_one_artifact
        injected = False

        def replace_old_journal(ref, name, expected_identities, allowed_hashes):
            nonlocal injected
            if not injected and name.startswith(".fde-community-journal-"):
                injected = True
                os.unlink(name, dir_fd=ref.parent_fd)
                descriptor = os.open(name, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600, dir_fd=ref.parent_fd)
                try:
                    os.write(descriptor, b"FOREIGN-JOURNAL-TEMP\n")
                    os.fsync(descriptor)
                finally:
                    os.close(descriptor)
            return original_cleanup(ref, name, expected_identities, allowed_hashes)

        setattr(helper, "_cleanup_one_artifact", replace_old_journal)
        try:
            with self.assertRaises(helper.CleanupRetryError):
                helper._write_journal(self.root, journal, install=False)
        finally:
            setattr(helper, "_cleanup_one_artifact", original_cleanup)
        self.assertTrue(injected)
        self.assertEqual(b"FOREIGN-JOURNAL-TEMP\n", next(self.root.glob(".fde-community-journal-*")).read_bytes())
        self.assertTrue((self.root / helper.JOURNAL).is_file())

    def test_remove_journal_preserves_foreign_replacement(self):
        helper = self.load_helper()
        env = self.envelope()
        applied = self.run_helper(env)
        self.assertEqual(0, applied.returncode, applied.stderr)
        original_cleanup = helper._cleanup_one_artifact
        injected = False

        def replace_journal(ref, name, expected_identities, allowed_hashes):
            nonlocal injected
            if not injected and name == helper.JOURNAL:
                injected = True
                os.unlink(name, dir_fd=ref.parent_fd)
                descriptor = os.open(name, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600, dir_fd=ref.parent_fd)
                try:
                    os.write(descriptor, b"FOREIGN-JOURNAL\n")
                    os.fsync(descriptor)
                finally:
                    os.close(descriptor)
            return original_cleanup(ref, name, expected_identities, allowed_hashes)

        setattr(helper, "_cleanup_one_artifact", replace_journal)
        try:
            with self.assertRaises(helper.CleanupRetryError):
                helper._remove_journal(self.root)
        finally:
            setattr(helper, "_cleanup_one_artifact", original_cleanup)
        self.assertTrue(injected)
        self.assertEqual(b"FOREIGN-JOURNAL\n", (self.root / helper.JOURNAL).read_bytes())

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
        plan = self.prepare(helper, env)
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

    def test_journal_rejects_boolean_legacy_mode(self):
        helper = self.load_helper()
        env = self.envelope()
        applied = self.run_helper(env)
        self.assertEqual(0, applied.returncode, applied.stderr)
        journal_path = self.root / helper.JOURNAL
        journal = json.loads(journal_path.read_text(encoding="utf-8"))
        journal["legacy_entries"][0]["mode"] = True
        journal_path.write_text(json.dumps(journal, separators=(",", ":")), encoding="utf-8")

        status = self.run_helper(env, "--recovery-status")

        self.assertEqual(4, status.returncode)

    def test_tree_collision_is_rejected_before_legacy_swaps(self):
        helper = self.load_helper()
        env = self.envelope()
        plan = self.prepare(helper, env)
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
        plan = self.prepare(helper, env)
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
        self.assertFalse((self.root / helper.JOURNAL).is_file())
        self.assertTrue(
            any(
                path.name.startswith(".fde-community-stage-") and path.read_bytes() == b"foreign stage\n"
                for path in self.root.rglob(".fde-community-stage-*")
            )
        )

    def test_published_tree_is_atomically_captured_when_legacy_swap_fails(self):
        helper = self.load_helper()
        env = self.envelope()
        plan = self.prepare(helper, env)
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

    def test_legacy_swap_is_fail_closed_when_target_changes_at_swap_boundary(self):
        helper = self.load_helper()
        env = self.envelope()
        plan = self.prepare(helper, env)
        rel = sorted(helper.LEGACY_PATHS)[0]
        ref = plan["legacy_refs"][rel]
        foreign = b"concurrent foreign edit\n"
        original_swap = helper._core.atomic_swap_at
        injected = False

        def race(parent_fd, source, target):
            nonlocal injected
            if not injected and target == ref.name and source.startswith(".fde-community-stage-"):
                fd = os.open(ref.name, os.O_WRONLY | os.O_TRUNC, dir_fd=parent_fd)
                try:
                    os.write(fd, foreign)
                finally:
                    os.close(fd)
                injected = True
            return original_swap(parent_fd, source, target)

        helper._core.atomic_swap_at = race
        try:
            code = helper._apply(plan, env["candidate_code"])
        finally:
            helper._core.atomic_swap_at = original_swap

        self.assertTrue(injected)
        self.assertEqual(4, code)
        self.assertEqual(foreign, (self.root / rel).read_bytes())
        self.assertTrue((self.root / helper.JOURNAL).is_file())

    def test_crash_after_legacy_swap_recovers_from_captured_side_journal(self):
        helper = self.load_helper()
        env = self.envelope()
        rel = sorted(helper.LEGACY_PATHS)[0]
        os.chmod(self.root / rel, 0o600)
        before = self.snapshot()
        plan = self.prepare(helper, env)
        ref = plan["legacy_refs"][rel]
        original_swap = helper._core.atomic_swap_at
        crashed = False

        def crash_after_swap(parent_fd, source, target):
            nonlocal crashed
            result = original_swap(parent_fd, source, target)
            if not crashed and target == ref.name and source.startswith(".fde-community-stage-"):
                crashed = True
                raise SystemExit("injected process death after rename-swap")
            return result

        helper._core.atomic_swap_at = crash_after_swap
        try:
            with self.assertRaises(SystemExit):
                helper._apply(plan, env["candidate_code"])
        finally:
            helper._core.atomic_swap_at = original_swap

        self.assertTrue(crashed)
        self.assertTrue((self.root / helper.JOURNAL).is_file())
        recovered = self.run_helper(env, "--recover-only")
        self.assertEqual(0, recovered.returncode, recovered.stderr)
        self.assertEqual(before, self.snapshot())
        self.assertEqual(0o600, stat.S_IMODE((self.root / rel).stat().st_mode))
        self.assertFalse((self.root / helper.JOURNAL).exists())

    def test_apply_preserves_each_legacy_file_mode(self):
        modes = dict(zip(sorted(LEGACY), (0o600, 0o640, 0o644, 0o660, 0o700)))
        for rel, mode in modes.items():
            os.chmod(self.root / rel, mode)

        proc = self.run_helper(self.envelope())

        self.assertEqual(0, proc.returncode, proc.stderr)
        for rel, mode in modes.items():
            self.assertEqual(mode, stat.S_IMODE((self.root / rel).stat().st_mode))

    def test_committed_recovery_rejects_same_content_tree_with_different_identity(self):
        helper = self.load_helper()
        env = self.envelope()
        applied = self.run_helper(env)
        self.assertEqual(0, applied.returncode, applied.stderr)

        replacement = self.root / ".foreign-tree"
        shutil.copytree(self.root / helper.TARGET_ROOT, replacement)
        shutil.rmtree(self.root / helper.TARGET_ROOT)
        os.rename(replacement, self.root / helper.TARGET_ROOT)

        recovered = self.run_helper(env, "--recover-only")

        self.assertEqual(4, recovered.returncode, recovered.stderr)
        self.assertTrue((self.root / helper.TARGET_ROOT).is_dir())
        self.assertTrue((self.root / helper.JOURNAL).is_file())

    def test_rollback_cleanup_never_deletes_tree_replaced_after_identity_capture(self):
        helper = self.load_helper()
        tree_files = {rel: str(helper.MANIFEST[rel]).encode("utf-8") for rel in helper.NEW_PATHS}
        tree_name = helper._stage_tree(self.root, tree_files, "a" * 24)
        expected_identity = helper._tree_identity(self.root, tree_name)
        foreign_copy = self.root / ".foreign-tree-copy"
        shutil.copytree(self.root / tree_name, foreign_copy)
        original_remove = helper._remove_tree_at
        injected = False

        def race(parent_fd, name, expected=None):
            nonlocal injected
            if name.startswith(".fde-community-cleanup-") and not injected:
                shutil.rmtree(self.root / tree_name)
                shutil.copytree(foreign_copy, self.root / tree_name)
                injected = True
            return original_remove(parent_fd, name, expected)

        helper._remove_tree_at = race
        try:
            cleaned = helper._cleanup_owned_tree(self.root, tree_name, expected_identity, tree_files)
        finally:
            helper._remove_tree_at = original_remove

        self.assertTrue(injected)
        self.assertFalse(cleaned)
        self.assertTrue((self.root / tree_name).is_dir())
        self.assertEqual(
            sorted(path.relative_to(foreign_copy) for path in foreign_copy.rglob("*")),
            sorted(path.relative_to(self.root / tree_name) for path in (self.root / tree_name).rglob("*")),
        )

    def test_artifact_cleanup_preserves_foreign_tombstone_replaced_after_final_hash(self):
        helper = self.load_helper()
        env = self.envelope()
        applied = self.run_helper(env)
        self.assertEqual(0, applied.returncode, applied.stderr)
        journal = helper._read_journal(self.root)
        self.assertIsNotNone(journal)
        entry = journal["legacy_entries"][0]
        refs = helper._journal_legacy_refs(self.root, journal)
        ref = refs[entry["path"]]
        original_hash = helper._artifact_hash
        injected = False

        def replace_after_tombstone_hash(hash_ref, name):
            nonlocal injected
            value = original_hash(hash_ref, name)
            if not injected and name.startswith(".fde-community-delete-file-"):
                injected = True
                os.unlink(name, dir_fd=hash_ref.parent_fd)
                descriptor = os.open(name, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600, dir_fd=hash_ref.parent_fd)
                try:
                    os.write(descriptor, b"FOREIGN-TOMBSTONE\n")
                    os.fsync(descriptor)
                finally:
                    os.close(descriptor)
            return value

        setattr(helper, "_artifact_hash", replace_after_tombstone_hash)
        try:
            cleaned = helper._cleanup_one_artifact(
                ref,
                entry["stage"],
                [entry["stage_identity"], entry["before_identity"]],
                {entry["before"], entry["after"]},
            )
        finally:
            setattr(helper, "_artifact_hash", original_hash)
            helper._close_legacy_refs(refs)

        self.assertTrue(injected)
        self.assertFalse(cleaned)
        self.assertIn(
            b"FOREIGN-TOMBSTONE\n",
            [path.read_bytes() for path in self.root.rglob(".fde-community-delete-file-*")],
        )

    def test_artifact_cleanup_preserves_foreign_final_capture_replaced_after_identity(self):
        helper = self.load_helper()
        env = self.envelope()
        applied = self.run_helper(env)
        self.assertEqual(0, applied.returncode, applied.stderr)
        journal = helper._read_journal(self.root)
        self.assertIsNotNone(journal)
        transaction = helper.transaction_sha256(journal["candidate_code"], journal["entries"])
        original_identity = helper._artifact_identity
        injected = False
        foreign_name = None

        def replace_after_final_identity(ref, name):
            nonlocal injected, foreign_name
            value = original_identity(ref, name)
            if not injected and name.startswith(".fde-community-final-delete-"):
                injected = True
                foreign_name = name
                os.unlink(name, dir_fd=ref.parent_fd)
                descriptor = os.open(
                    name,
                    os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                    0o600,
                    dir_fd=ref.parent_fd,
                )
                try:
                    os.write(descriptor, b"FOREIGN-FINAL-CAPTURE\n")
                    os.fsync(descriptor)
                finally:
                    os.close(descriptor)
            return value

        helper._artifact_identity = replace_after_final_identity
        try:
            with self.assertRaises(helper.CleanupRetryError):
                helper._ack(self.root, env["candidate_code"], transaction)
        finally:
            helper._artifact_identity = original_identity

        self.assertTrue(injected)
        self.assertIsNotNone(foreign_name)
        self.assertEqual(
            b"FOREIGN-FINAL-CAPTURE\n",
            next(self.root.rglob(foreign_name)).read_bytes(),
        )
        self.assertTrue((self.root / helper.JOURNAL).is_file())

    def test_tree_cleanup_preserves_foreign_capture_replaced_after_identity(self):
        helper = self.load_helper()
        tree_name = ".tree-under-test"
        root_fd_for_setup = helper._core.open_root(self.root)
        try:
            os.mkdir(tree_name, 0o700, dir_fd=root_fd_for_setup)
            helper._core.fsync_fd(root_fd_for_setup)
        finally:
            os.close(root_fd_for_setup)
        expected_identity = helper._tree_identity(self.root, tree_name)
        original_identity = helper._identity_at
        injected = False
        foreign_name = None

        def replace_after_capture_identity(parent_fd, name):
            nonlocal injected, foreign_name
            value = original_identity(parent_fd, name)
            if not injected and name.startswith(".fde-community-tree-cleanup-"):
                injected = True
                foreign_name = name
                os.rmdir(name, dir_fd=parent_fd)
                os.mkdir(name, 0o700, dir_fd=parent_fd)
                helper._core.fsync_fd(parent_fd)
            return value

        helper._identity_at = replace_after_capture_identity
        root_fd = helper._core.open_root(self.root)
        try:
            with self.assertRaises(helper.ApplyError):
                helper._remove_tree_at(root_fd, tree_name, expected_identity)
        finally:
            helper._identity_at = original_identity
            os.close(root_fd)

        self.assertTrue(injected)
        self.assertIsNotNone(foreign_name)
        self.assertTrue((self.root / foreign_name).is_dir())

    def test_recursive_tree_cleanup_preserves_foreign_child_after_identity(self):
        helper = self.load_helper()
        tree_name = ".tree-with-child"
        root_fd_for_setup = helper._core.open_root(self.root)
        try:
            os.mkdir(tree_name, 0o700, dir_fd=root_fd_for_setup)
            tree_fd = os.open(tree_name, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0), dir_fd=root_fd_for_setup)
            try:
                child_fd = os.open("child.md", os.O_CREAT | os.O_WRONLY, 0o600, dir_fd=tree_fd)
                try:
                    os.write(child_fd, b"ORIGINAL-CHILD\n")
                    os.fsync(child_fd)
                finally:
                    os.close(child_fd)
            finally:
                os.close(tree_fd)
            helper._core.fsync_fd(root_fd_for_setup)
        finally:
            os.close(root_fd_for_setup)
        expected_identity = helper._tree_identity(self.root, tree_name)
        original_identity = helper._identity_at_file
        injected = False

        def replace_after_child_identity(parent_fd, name):
            nonlocal injected
            value = original_identity(parent_fd, name)
            if not injected and name.startswith(".fde-community-tree-delete-"):
                injected = True
                os.unlink(name, dir_fd=parent_fd)
                descriptor = os.open(name, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600, dir_fd=parent_fd)
                try:
                    os.write(descriptor, b"FOREIGN-CHILD\n")
                    os.fsync(descriptor)
                finally:
                    os.close(descriptor)
            return value

        helper._identity_at_file = replace_after_child_identity
        root_fd = helper._core.open_root(self.root)
        try:
            with self.assertRaises(helper.ApplyError):
                helper._remove_tree_at(root_fd, tree_name, expected_identity)
        finally:
            helper._identity_at_file = original_identity
            os.close(root_fd)

        self.assertTrue(injected)
        self.assertIn(
            b"FOREIGN-CHILD\n",
            [path.read_bytes() for path in self.root.rglob("*") if path.is_file()],
        )

    def test_in_process_dry_run_closes_path_refs(self):
        helper = self.load_helper()
        env = self.envelope()

        def fd_count():
            return len(os.listdir("/dev/fd"))

        before = fd_count()
        for _ in range(10):
            stdout = io.StringIO()
            stderr = io.StringIO()
            code = helper.run(
                ["--vault-root", str(self.root), "--dry-run"],
                stdin=io.StringIO(json.dumps(env, ensure_ascii=False)),
                stdout=stdout,
                stderr=stderr,
            )
            self.assertEqual(0, code, stderr.getvalue())
        after = fd_count()
        self.assertLessEqual(after - before, 1)

    def test_prepare_validation_failure_closes_partial_path_refs(self):
        helper = self.load_helper()
        env = self.envelope()
        env["action"]["before_hashes"][sorted(LEGACY)[-1]] = "0" * 64

        def fd_count():
            return len(os.listdir("/dev/fd"))

        before = fd_count()
        with self.assertRaises(helper.ValidationError):
            helper.prepare(self.root, env)
        after = fd_count()
        self.assertLessEqual(after - before, 1)

    def test_pathref_constructor_closes_parent_fd_when_post_open_validation_fails(self):
        helper = self.load_helper()
        original_exists = helper._core.PathRef.exists

        def fail_after_parent_open(_self):
            raise helper.ValidationError()

        helper._core.PathRef.exists = fail_after_parent_open
        try:
            before = len(os.listdir("/dev/fd"))
            with self.assertRaises(helper.ValidationError):
                helper._core.PathRef(
                    self.root,
                    helper.PurePosixPath(sorted(helper.LEGACY_PATHS)[0]),
                    True,
                )
            after = len(os.listdir("/dev/fd"))
        finally:
            helper._core.PathRef.exists = original_exists

        self.assertLessEqual(after - before, 1)

    def test_rollback_final_visible_identity_race_preserves_foreign_leaf_and_journal(self):
        helper = self.load_helper()
        env = self.envelope()
        plan = self.prepare(helper, env)
        original_exclusive = helper._core.atomic_exclusive_at
        original_modes = helper._legacy_modes_match
        rel = sorted(helper.LEGACY_PATHS)[0]
        injected = False

        def fail_target_install(parent_fd, source, target):
            if target == helper.TARGET_ROOT:
                raise OSError("injected target install failure")
            return original_exclusive(parent_fd, source, target)

        def replace_after_final_mode_check(refs, entries):
            nonlocal injected
            value = original_modes(refs, entries)
            if not injected:
                replacement = self.root / ".foreign-visible-legacy"
                replacement.write_bytes(b"FOREIGN-VISIBLE-LEGACY\n")
                os.replace(replacement, self.root / rel)
                injected = True
            return value

        helper._core.atomic_exclusive_at = fail_target_install
        helper._legacy_modes_match = replace_after_final_mode_check
        try:
            code = helper._apply(plan, env["candidate_code"])
        finally:
            helper._core.atomic_exclusive_at = original_exclusive
            helper._legacy_modes_match = original_modes

        self.assertTrue(injected)
        self.assertEqual(4, code)
        self.assertEqual(b"FOREIGN-VISIBLE-LEGACY\n", (self.root / rel).read_bytes())
        self.assertTrue((self.root / helper.JOURNAL).is_file())

    def test_orphan_journal_temp_blocks_false_no_transaction_status(self):
        helper = self.load_helper()
        child = """
import importlib.util
import os
import sys
from pathlib import Path

spec = importlib.util.spec_from_file_location("fde_child", sys.argv[1])
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
original = module._core.write_temp

def crash_after_temp(parent_fd, prefix, data, mode):
    name = original(parent_fd, prefix, data, mode)
    os._exit(97)

module._core.write_temp = crash_after_temp
module._write_journal(Path(sys.argv[2]), {}, install=True)
"""
        child_result = subprocess.run(
            [sys.executable, "-c", child, str(SCRIPT), str(self.root)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(97, child_result.returncode)
        self.assertTrue(list(self.root.glob(".fde-community-journal-*")))
        status = self.run_helper(self.envelope(), "--recovery-status")
        self.assertEqual(4, status.returncode)
        self.assertTrue(list(self.root.glob(".fde-community-journal-*")))


if __name__ == "__main__":
    unittest.main()
