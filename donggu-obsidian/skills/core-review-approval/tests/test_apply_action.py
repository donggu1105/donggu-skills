#!/usr/bin/env python3
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
SCRIPT = HERE.parent / "scripts" / "apply-action.py"


def sha(data):
    return hashlib.sha256(data).hexdigest()


class ApplyActionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        for name in ("10_Sources", "20_Core", "50_Channel_Packs", "60_MOCs"):
            (self.root / name).mkdir()
        self.source_rel = "10_Sources/source.md"
        self.source = self.root / self.source_rel
        self.source_bytes = b"---\ntype: source\nextracted_to: []\n---\n\n[[Broken]]\n"
        self.source.write_bytes(self.source_bytes)
        self.target_rel = "20_Core/Target.md"
        (self.root / self.target_rel).write_bytes(b"target\n")

    def replace_envelope(self, **updates):
        value = {
            "schema_version": 1,
            "candidate_code": "CR-20260712-000001",
            "candidate_type": "fix_link",
            "source_note_path": self.source_rel,
            "source_sha256": sha(self.source_bytes),
            "claim": "A claim",
            "target_note_paths": [self.target_rel],
            "action": {"op": "replace", "schema_version": 1, "old": "[[Broken]]", "new": "[[20_Core/Target]]"},
        }
        value.update(updates)
        return value

    def core_envelope(self, source_rel=None, source_bytes=None, **updates):
        source_rel = source_rel or self.source_rel
        source_bytes = source_bytes or (self.root / source_rel).read_bytes()
        action = {
            "op": "create_core_with_backlink",
            "schema_version": 1,
            "template_version": 1,
            "core_path": "20_Core/CORE - A claim.md",
            "moc_path": "60_MOCs/MOC - Topic.md",
            "moc_sha256": "",
            "trace_field": "extracted_to",
        }
        moc = self.root / action["moc_path"]
        if not moc.exists():
            moc.write_bytes(b"---\ntype: moc\n---\n\n# Topic\n")
        action["moc_sha256"] = sha(moc.read_bytes())
        value = {
            "schema_version": 1,
            "candidate_code": "CR-20260712-000002",
            "candidate_type": "new_core",
            "source_note_path": source_rel,
            "source_sha256": sha(source_bytes),
            "claim": "A claim",
            "target_note_paths": sorted([action["core_path"], action["moc_path"]]),
            "action": action,
        }
        value.update(updates)
        return value

    def run_helper(self, envelope=None, raw=None, *args):
        payload = raw if raw is not None else json.dumps(envelope, ensure_ascii=False)
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--vault-root", str(self.root), *args],
            input=payload.encode("utf-8"), stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
        )

    def run_with_closed_stdout(self, envelope=None, *args):
        payload = json.dumps(envelope).encode("utf-8") if envelope is not None else b""
        proc = subprocess.Popen(
            [sys.executable, str(SCRIPT), "--vault-root", str(self.root), *args],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        proc.stdout.close()
        _, stderr = proc.communicate(payload)
        return proc.returncode, stderr

    def snapshot(self):
        result = {}
        for path in self.root.rglob("*"):
            if path.is_file() or path.is_symlink():
                stat = path.lstat()
                result[str(path.relative_to(self.root))] = (stat.st_mtime_ns, path.read_bytes() if path.is_file() else None)
        return result

    def assert_validation(self, proc):
        self.assertEqual(2, proc.returncode, proc.stdout)
        self.assertEqual(b"", proc.stdout)
        self.assertEqual(b"validation failed\n", proc.stderr)

    def test_malformed_json_and_schema_and_exact_keys_are_rejected(self):
        self.assert_validation(self.run_helper(raw="{"))
        bad_schema = self.replace_envelope(schema_version=2)
        self.assert_validation(self.run_helper(bad_schema))
        extra = self.replace_envelope()
        extra["secret"] = "do-not-print"
        proc = self.run_helper(extra)
        self.assert_validation(proc)
        self.assertNotIn(b"do-not-print", proc.stdout + proc.stderr)

    def test_versions_reject_bool_and_claim_rules_are_op_specific(self):
        self.assert_validation(self.run_helper(self.replace_envelope(schema_version=True)))
        env = self.replace_envelope(claim=None)
        proc = self.run_helper(env, None, "--dry-run")
        self.assertEqual(0, proc.returncode, proc.stderr)
        env = self.core_envelope()
        env["action"]["schema_version"] = True
        self.assert_validation(self.run_helper(env))
        env = self.core_envelope()
        env["action"]["template_version"] = True
        self.assert_validation(self.run_helper(env))
        self.assert_validation(self.run_helper(self.core_envelope(claim=None)))

    def test_unsafe_paths_inbox_symlink_binary_and_oversize_are_rejected(self):
        for path in ("/tmp/a.md", "10_Sources/../source.md", "00_Inbox/a.md", "10_Sources/00_Inbox/a.md"):
            env = self.replace_envelope(source_note_path=path, target_note_paths=[path])
            self.assert_validation(self.run_helper(env))
        outside = self.root / "outside.md"
        outside.write_text("old text", encoding="utf-8")
        link = self.root / "10_Sources/link.md"
        link.symlink_to(outside)
        env = self.replace_envelope(source_note_path="10_Sources/link.md", target_note_paths=["10_Sources/link.md"], source_sha256=sha(b"old text"))
        self.assert_validation(self.run_helper(env))
        self.source.write_bytes(b"\xffold text")
        env = self.replace_envelope(source_sha256=sha(self.source.read_bytes()))
        self.assert_validation(self.run_helper(env))
        self.assert_validation(self.run_helper(raw=" " * (1024 * 1024 + 1)))

    def test_replace_hash_occurrence_and_action_shape_validation(self):
        self.assert_validation(self.run_helper(self.replace_envelope(source_sha256="A" * 64)))
        self.assert_validation(self.run_helper(self.replace_envelope(action={"op": "replace"})))
        for old in ("[[Missing]]", "[[Broken]]"):
            env = self.replace_envelope(action={"op": "replace", "schema_version": 1, "old": old, "new": "[[20_Core/Target]]"})
            if old == "[[Broken]]":
                self.source.write_bytes(self.source_bytes + b"[[Broken]]\n")
                env["source_sha256"] = sha(self.source.read_bytes())
            self.assert_validation(self.run_helper(env))

    def test_replace_preserves_crlf_and_applies_exactly_once(self):
        data = b"---\r\ntype: source\r\nextracted_to: []\r\n---\r\n\r\n[[Broken]]\r\n"
        self.source.write_bytes(data)
        env = self.replace_envelope(source_sha256=sha(data))
        proc = self.run_helper(env)
        self.assertEqual(0, proc.returncode, proc.stderr)
        self.assertEqual(data.replace(b"[[Broken]]", b"[[20_Core/Target]]"), self.source.read_bytes())
        result = json.loads(proc.stdout)
        self.assertEqual("applied", result["status"])
        self.assertEqual([self.source_rel], result["paths"])
        self.assertNotIn(str(self.root), proc.stdout.decode())
        self.assertNotIn("new text", proc.stdout.decode())

    def test_replace_supports_core_source_and_reference_targets(self):
        core_source_rel = "20_Core/source.md"
        core_source = self.root / core_source_rel
        core_bytes = b"---\ntype: core\n---\n\n[[Broken]]\n"
        core_source.write_bytes(core_bytes)
        target_rel = "20_Core/Target.md"
        (self.root / target_rel).write_text("target", encoding="utf-8")
        env = self.replace_envelope(
            source_note_path=core_source_rel,
            source_sha256=sha(core_bytes),
            claim=None,
            target_note_paths=[target_rel],
            action={"op": "replace", "schema_version": 1, "old": "[[Broken]]", "new": "[[20_Core/Target]]"},
        )
        proc = self.run_helper(env)
        self.assertEqual(0, proc.returncode, proc.stderr)
        self.assertIn("[[20_Core/Target]]", core_source.read_text(encoding="utf-8"))

    def test_replace_dry_run_has_zero_writes_or_mtime_changes(self):
        before = self.snapshot()
        proc = self.run_helper(self.replace_envelope(), None, "--dry-run")
        self.assertEqual(0, proc.returncode, proc.stderr)
        self.assertEqual(before, self.snapshot())
        self.assertEqual("planned", json.loads(proc.stdout)["status"])

    def test_create_rejects_op_only_wrong_hash_targets_trace_existing_and_duplicates(self):
        self.assert_validation(self.run_helper(self.core_envelope(action={"op": "create_core_with_backlink"})))
        env = self.core_envelope()
        env["action"]["moc_sha256"] = "0" * 64
        self.assert_validation(self.run_helper(env))
        env = self.core_envelope(target_note_paths=["20_Core/CORE - A claim.md"])
        self.assert_validation(self.run_helper(env))
        env = self.core_envelope()
        env["action"]["trace_field"] = "decomposed_to"
        self.assert_validation(self.run_helper(env))
        core = self.root / env["action"]["core_path"]
        core.write_text("occupied", encoding="utf-8")
        self.assert_validation(self.run_helper(env))
        core.unlink()
        link = "[[20_Core/CORE - A claim]]"
        self.source.write_text(self.source.read_text(encoding="utf-8").replace("[]", '["%s"]' % link), encoding="utf-8")
        env = self.core_envelope(source_bytes=self.source.read_bytes())
        self.assert_validation(self.run_helper(env))

    def test_create_requires_new_core_and_fixed_root_trace_mapping(self):
        self.assert_validation(self.run_helper(self.core_envelope(candidate_type="fix_link")))
        pack_rel = "50_Channel_Packs/post.md"
        pack = self.root / pack_rel
        pack_bytes = b"---\ntype: channel_pack\ndecomposed_to: []\n---\n\nPost\n"
        pack.write_bytes(pack_bytes)
        env = self.core_envelope(source_rel=pack_rel, source_bytes=pack_bytes)
        env["source_note_path"] = pack_rel
        env["source_sha256"] = sha(pack_bytes)
        env["action"]["trace_field"] = "decomposed_to"
        proc = self.run_helper(env, None, "--dry-run")
        self.assertEqual(0, proc.returncode, proc.stderr)

    def test_create_happy_path_builds_template_and_bidirectional_links(self):
        env = self.core_envelope()
        proc = self.run_helper(env)
        self.assertEqual(0, proc.returncode, proc.stderr)
        core = self.root / env["action"]["core_path"]
        text = core.read_text(encoding="utf-8")
        self.assertIn("template_version: 1", text)
        self.assertIn("A claim", text)
        self.assertIn("[[10_Sources/source]]", text)
        self.assertIn("[[60_MOCs/MOC - Topic]]", text)
        self.assertIn("[[20_Core/CORE - A claim]]", self.source.read_text(encoding="utf-8"))
        moc_text = (self.root / env["action"]["moc_path"]).read_text(encoding="utf-8")
        self.assertIn("## 연결된 CORE", moc_text)
        self.assertIn("- [[20_Core/CORE - A claim]]", moc_text)
        result = json.loads(proc.stdout)
        self.assertEqual("applied", result["status"])
        self.assertEqual(sorted([self.source_rel, env["action"]["core_path"], env["action"]["moc_path"]]), result["paths"])

    def test_create_appends_to_existing_moc_section_and_frontmatter_block_list(self):
        self.source.write_bytes(b"---\ntype: source\nextracted_to:\n  - \"[[20_Core/old]]\"\n---\nBody\n")
        moc = self.root / "60_MOCs/MOC - Topic.md"
        moc.write_bytes("# Topic\n\n## 연결된 CORE\n\n- [[20_Core/old]]\n\n## Other\nText\n".encode("utf-8"))
        env = self.core_envelope(source_bytes=self.source.read_bytes())
        env["action"]["moc_sha256"] = sha(moc.read_bytes())
        proc = self.run_helper(env)
        self.assertEqual(0, proc.returncode, proc.stderr)
        self.assertIn('  - "[[20_Core/CORE - A claim]]"', self.source.read_text(encoding="utf-8"))
        text = moc.read_text(encoding="utf-8")
        self.assertLess(text.index("CORE - A claim"), text.index("## Other"))

    def test_create_supports_vault_style_unindented_frontmatter_list(self):
        self.source.write_bytes(
            b'---\ntype: source\nextracted_to:\n- "[[20_Core/old]]"\ntags:\n- test\n---\nBody\n'
        )
        env = self.core_envelope(source_bytes=self.source.read_bytes())
        proc = self.run_helper(env)
        self.assertEqual(0, proc.returncode, proc.stderr)
        text = self.source.read_text(encoding="utf-8")
        self.assertIn('- "[[20_Core/old]]"', text)
        self.assertIn('- "[[20_Core/CORE - A claim]]"', text)
        self.assertLess(text.index('CORE - A claim'), text.index('tags:'))

    def test_create_dry_run_has_zero_writes_or_mtime_changes(self):
        env = self.core_envelope()
        before = self.snapshot()
        proc = self.run_helper(env, None, "--dry-run")
        self.assertEqual(0, proc.returncode, proc.stderr)
        self.assertEqual(before, self.snapshot())
        self.assertFalse((self.root / env["action"]["core_path"]).exists())

    def test_commit_failure_rolls_back_replace_and_create(self):
        spec = importlib.util.spec_from_file_location("apply_action", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        def invoke(env, fail_at):
            stdin = io.StringIO(json.dumps(env))
            stdout, stderr = io.StringIO(), io.StringIO()
            real_cas = module.cas_install
            count = {"n": 0}
            def failing_cas(*args, **kwargs):
                result = real_cas(*args, **kwargs)
                count["n"] += 1
                if count["n"] == fail_at:
                    raise OSError("injected secret failure")
                return result
            with mock.patch.object(module, "cas_install", side_effect=failing_cas):
                code = module.run(["--vault-root", str(self.root)], stdin, stdout, stderr)
            return code, stdout.getvalue(), stderr.getvalue()

        before = self.source.read_bytes()
        code, out, err = invoke(self.replace_envelope(), 1)
        self.assertEqual(3, code)
        self.assertEqual(before, self.source.read_bytes())
        self.assertNotIn("secret", out + err)

        env = self.core_envelope()
        moc = self.root / env["action"]["moc_path"]
        source_before, moc_before = self.source.read_bytes(), moc.read_bytes()
        code, out, err = invoke(env, 2)
        self.assertEqual(3, code)
        self.assertEqual(source_before, self.source.read_bytes())
        self.assertEqual(moc_before, moc.read_bytes())
        self.assertFalse((self.root / env["action"]["core_path"]).exists())
    def test_duplicate_json_keys_candidate_enum_and_op_type_are_rejected(self):
        raw = json.dumps(self.replace_envelope())
        raw = raw.replace('"candidate_type": "fix_link"', '"candidate_type":"fix_link","candidate_type":"new_core"')
        self.assert_validation(self.run_helper(raw=raw))
        for candidate_type in ("merge", "new_core", "unknown", "FIX_LINK"):
            self.assert_validation(self.run_helper(self.replace_envelope(candidate_type=candidate_type)))
        for candidate_type in ("fix_link", "link_existing"):
            proc = self.run_helper(self.replace_envelope(candidate_type=candidate_type), None, "--dry-run")
            self.assertEqual(0, proc.returncode, proc.stderr)

    def test_replace_targets_are_bounded_and_exactly_match_canonical_new_links(self):
        for targets in ([], [self.target_rel] * 21, [self.source_rel], [self.target_rel, self.source_rel]):
            self.assert_validation(self.run_helper(self.replace_envelope(target_note_paths=targets)))
        env = self.replace_envelope(action={"op": "replace", "schema_version": 1,
            "old": "[[Broken]]", "new": "[[20_Core/Target|별칭]] and [[20_Core/Target#부분]]"})
        self.assert_validation(self.run_helper(env))

    def test_reference_target_snapshot_change_blocks_apply(self):
        module = self.load_module()
        env = self.replace_envelope()
        paths, originals, desired = module.prepare(self.root, env)
        (self.root / self.target_rel).unlink()
        code = module.apply_changes("CR-20260712-000001", paths, originals, desired)
        self.assertEqual(3, code)
        self.assertEqual(self.source_bytes, self.source.read_bytes())

    def test_edit_at_leaf_cas_boundary_is_not_overwritten(self):
        module = self.load_module()
        foreign = b"foreign concurrent edit\n"
        real_swap = module.atomic_swap_at
        injected = {"done": False}

        def edit_then_swap(parent_fd, left, right):
            if not injected["done"] and left.startswith(".core-review-stage-") and right == self.source.name:
                injected["done"] = True
                self.source.write_bytes(foreign)
            return real_swap(parent_fd, left, right)

        with mock.patch.object(module, "atomic_swap_at", side_effect=edit_then_swap):
            code = module.run(
                ["--vault-root", str(self.root)],
                io.StringIO(json.dumps(self.replace_envelope())), io.StringIO(), io.StringIO(),
            )
        self.assertEqual(4, code)
        self.assertEqual(foreign, self.source.read_bytes())
        self.assertTrue((self.root / ".core-review-journal.json").exists())

    def test_control_characters_and_oversize_desired_are_rejected_before_stage(self):
        bad = self.source_bytes + b"\x01"
        self.source.write_bytes(bad)
        self.assert_validation(self.run_helper(self.replace_envelope(source_sha256=sha(bad))))
        huge = b"[[Broken]]" + b"x" * (8 * 1024 * 1024 - len(b"[[Broken]]"))
        self.source.write_bytes(huge)
        env = self.replace_envelope(source_sha256=sha(huge), action={"op": "replace", "schema_version": 1,
            "old": "[[Broken]]", "new": "[[20_Core/Target]]"})
        before = self.snapshot()
        self.assert_validation(self.run_helper(env))
        self.assertEqual(before, self.snapshot())

    def test_missing_trace_field_is_created_before_frontmatter_close(self):
        self.source_bytes = b"---\ntype: source\n---\nBody\n"
        self.source.write_bytes(self.source_bytes)
        env = self.core_envelope(source_bytes=self.source_bytes)
        proc = self.run_helper(env)
        self.assertEqual(0, proc.returncode, proc.stderr)
        text = self.source.read_text(encoding="utf-8")
        self.assertLess(text.index("extracted_to:"), text.index("---", 4))

    def test_moc_heading_alias_and_canonical_link_duplicates(self):
        moc = self.root / "60_MOCs/MOC - Topic.md"
        moc.write_text("# Topic\n\n## 💡 Core 연결\n\n- [[20_Core/old]]\n", encoding="utf-8")
        env = self.core_envelope()
        env["action"]["moc_sha256"] = sha(moc.read_bytes())
        proc = self.run_helper(env)
        self.assertEqual(0, proc.returncode, proc.stderr)
        self.assertNotIn("## 연결된 CORE", moc.read_text(encoding="utf-8"))
        self.assertEqual(0, self.run_helper(None, "", "--ack-candidate", env["candidate_code"]).returncode)

        self.setUp_duplicate_fixture()
        link = "[[20_Core/CORE - A claim|alias]]"
        self.source.write_text(self.source.read_text(encoding="utf-8").replace("[]", '["%s"]' % link), encoding="utf-8")
        env = self.core_envelope(source_bytes=self.source.read_bytes())
        self.assert_validation(self.run_helper(env))

    def test_post_commit_stdout_failure_is_exit_5_and_never_70(self):
        module = self.load_module()
        class BrokenOutput(io.StringIO):
            def write(self, value):
                raise BrokenPipeError()
        code = module.run(["--vault-root", str(self.root)], io.StringIO(json.dumps(self.replace_envelope())), BrokenOutput(), io.StringIO())
        self.assertEqual(5, code)
        self.assertIn(b"[[20_Core/Target]]", self.source.read_bytes())

    def test_real_closed_pipe_is_70_before_mutation_and_5_after_mutation(self):
        before = self.snapshot()
        code, _ = self.run_with_closed_stdout(self.replace_envelope(), "--dry-run")
        self.assertEqual(70, code)
        self.assertEqual(before, self.snapshot())
        code, stderr = self.run_with_closed_stdout(self.replace_envelope())
        self.assertEqual(5, code, stderr)
        self.assertNotEqual(120, code)
        self.assertIn(b"[[20_Core/Target]]", self.source.read_bytes())
        self.assertTrue((self.root / ".core-review-journal.json").exists())

    def test_real_closed_pipe_is_exit_5_after_recovery_and_ack_mutations(self):
        module = self.load_module()
        self.interrupt_after_first_cas(module, self.replace_envelope())
        code, stderr = self.run_with_closed_stdout(None, "--recover-only")
        self.assertEqual(5, code, stderr)
        self.assertNotEqual(120, code)
        self.assertEqual(self.source_bytes, self.source.read_bytes())

        env = self.replace_envelope()
        self.assertEqual(0, self.run_helper(env).returncode)
        code, stderr = self.run_with_closed_stdout(None, "--ack-candidate", env["candidate_code"])
        self.assertEqual(5, code, stderr)
        self.assertNotEqual(120, code)
        self.assertFalse((self.root / ".core-review-journal.json").exists())

    def test_successful_apply_retains_committed_journal_until_matching_ack(self):
        env = self.replace_envelope()
        proc = self.run_helper(env)
        self.assertEqual(0, proc.returncode, proc.stderr)
        result = json.loads(proc.stdout)
        self.assertEqual("applied", result["status"])
        self.assertEqual(env["candidate_code"], result["candidate_code"])
        self.assertEqual("committed", result["state"])
        self.assertEqual(sha(self.source.read_bytes()), result["hashes"][self.source_rel]["after"])
        journal = self.root / ".core-review-journal.json"
        self.assertTrue(journal.exists())
        self.assertEqual("committed", json.loads(journal.read_text())["state"])
        self.assertTrue(any("backup" in p.name for p in self.root.rglob(".*")))
        status = self.run_helper(None, "", "--recovery-status")
        self.assertEqual({"state": "committed", "candidate_code": env["candidate_code"]}, json.loads(status.stdout))
        before = self.snapshot()
        recovery = self.run_helper(None, "", "--recover-only")
        self.assertEqual(0, recovery.returncode, recovery.stderr)
        self.assertEqual("reconciliation_required", json.loads(recovery.stdout)["status"])
        self.assertEqual(before, self.snapshot())
        wrong = self.run_helper(None, "", "--ack-candidate", "CR-20260712-999999")
        self.assertEqual(4, wrong.returncode)
        self.assertTrue(journal.exists())
        ack = self.run_helper(None, "", "--ack-candidate", env["candidate_code"])
        self.assertEqual(0, ack.returncode, ack.stderr)
        self.assertEqual("acknowledged", json.loads(ack.stdout)["status"])
        self.assertFalse(journal.exists())
        self.assertFalse(any("backup" in p.name or "stage" in p.name for p in self.root.rglob(".*")))

    def test_ack_rejects_foreign_after_hash_without_cleanup(self):
        env = self.replace_envelope()
        self.assertEqual(0, self.run_helper(env).returncode)
        self.source.write_bytes(b"foreign after db completion\n")
        before = self.snapshot()
        ack = self.run_helper(None, "", "--ack-candidate", env["candidate_code"])
        self.assertEqual(4, ack.returncode)
        self.assertEqual(before, self.snapshot())

    def test_ack_nonregular_leaf_is_integrity_exit_4(self):
        env = self.replace_envelope()
        self.assertEqual(0, self.run_helper(env).returncode)
        self.source.unlink()
        self.source.mkdir()
        ack = self.run_helper(None, "", "--ack-candidate", env["candidate_code"])
        self.assertEqual(4, ack.returncode)
        self.assertTrue((self.root / ".core-review-journal.json").exists())

    def test_ack_cleanup_failure_is_retryable_exit_6_and_keeps_committed_journal(self):
        module = self.load_module()
        env = self.replace_envelope()
        self.assertEqual(0, module.run(["--vault-root", str(self.root)], io.StringIO(json.dumps(env)), io.StringIO(), io.StringIO()))
        with mock.patch.object(module, "cleanup_artifacts", return_value=False):
            code = module.run(["--vault-root", str(self.root), "--ack-candidate", env["candidate_code"]], io.StringIO(), io.StringIO(), io.StringIO())
        self.assertEqual(6, code)
        self.assertEqual("committed", json.loads((self.root / ".core-review-journal.json").read_text())["state"])
        retry = self.run_helper(None, "", "--ack-candidate", env["candidate_code"])
        self.assertEqual(0, retry.returncode, retry.stderr)

    def test_ack_unlink_success_with_directory_fsync_failure_is_completed(self):
        module = self.load_module()
        env = self.replace_envelope()
        self.assertEqual(0, module.run(["--vault-root", str(self.root)], io.StringIO(json.dumps(env)), io.StringIO(), io.StringIO()))
        real_fsync = module.fsync_fd
        journal = self.root / ".core-review-journal.json"
        def fail_only_after_journal_unlink(fd):
            if not journal.exists():
                raise OSError("post-unlink directory fsync failure")
            return real_fsync(fd)
        with mock.patch.object(module, "fsync_fd", side_effect=fail_only_after_journal_unlink):
            code = module.run(["--vault-root", str(self.root), "--ack-candidate", env["candidate_code"]], io.StringIO(), io.StringIO(), io.StringIO())
        self.assertEqual(0, code)
        self.assertFalse(journal.exists())
        self.assertEqual("no_transaction", json.loads(self.run_helper(None, "", "--recovery-status").stdout)["state"])

    def test_ack_partial_cleanup_crash_is_idempotently_retryable(self):
        module = self.load_module()
        env = self.replace_envelope()
        self.assertEqual(0, module.run(["--vault-root", str(self.root)], io.StringIO(json.dumps(env)), io.StringIO(), io.StringIO()))
        real_unlink = module.unlink_at
        failed = {"done": False}
        def remove_backup_then_fail_stage(parent_fd, name):
            if name.startswith(".core-review-stage-") and not failed["done"]:
                failed["done"] = True
                raise OSError("injected cleanup crash")
            return real_unlink(parent_fd, name)
        with mock.patch.object(module, "unlink_at", side_effect=remove_backup_then_fail_stage):
            code = module.run(["--vault-root", str(self.root), "--ack-candidate", env["candidate_code"]], io.StringIO(), io.StringIO(), io.StringIO())
        self.assertEqual(6, code)
        self.assertTrue((self.root / ".core-review-journal.json").exists())
        self.assertEqual(0, self.run_helper(None, "", "--ack-candidate", env["candidate_code"]).returncode)

    def test_crash_after_committed_journal_rewrite_retains_reconciliation_record(self):
        module = self.load_module()
        env = self.replace_envelope()
        real_rewrite = module.rewrite_journal
        def rewrite_then_interrupt(*args):
            result = real_rewrite(*args)
            raise KeyboardInterrupt()
        with mock.patch.object(module, "rewrite_journal", side_effect=rewrite_then_interrupt):
            with self.assertRaises(KeyboardInterrupt):
                module.run(["--vault-root", str(self.root)], io.StringIO(json.dumps(env)), io.StringIO(), io.StringIO())
        status = self.run_helper(None, "", "--recovery-status")
        self.assertEqual({"state": "committed", "candidate_code": env["candidate_code"]}, json.loads(status.stdout))
        self.assertIn(b"[[20_Core/Target]]", self.source.read_bytes())

    def test_prepared_recovery_validates_foreign_stage_before_any_leaf_swap(self):
        module = self.load_module()
        self.interrupt_after_first_cas(module, self.replace_envelope())
        journal = json.loads((self.root / ".core-review-journal.json").read_text())
        entry = journal["entries"][0]
        stage = self.source.parent / entry["stage"]
        stage.write_bytes(b"FOREIGN STAGE SENTINEL\n")
        leaf_before = self.source.read_bytes()
        recovery = self.run_helper(None, "", "--recover-only")
        self.assertEqual(4, recovery.returncode)
        self.assertEqual(leaf_before, self.source.read_bytes())
        self.assertEqual(b"FOREIGN STAGE SENTINEL\n", stage.read_bytes())

    def test_malformed_regular_journals_are_all_integrity_exit_4(self):
        journal = self.root / ".core-review-journal.json"
        malformed = [
            b"{",
            json.dumps({"version": 2, "candidate_code": "CR-20260712-000001", "token": "a" * 24,
                        "state": "prepared", "entries": [], "extra": True}).encode(),
            json.dumps({"version": 2, "candidate_code": "CR-20260712-000001", "token": "a" * 24,
                        "state": "prepared", "entries": [{"path": [], "existed": True, "backup": "x",
                        "stage": "x", "before": "x", "after": "x", "mode": 420}]}).encode(),
        ]
        for data in malformed:
            with self.subTest(data=data):
                journal.write_bytes(data)
                status = self.run_helper(None, "", "--recovery-status")
                self.assertEqual(4, status.returncode)
                self.assertEqual(b"recovery failed\n", status.stderr)

    def test_directory_swap_during_rename_never_writes_through_symlink(self):
        module = self.load_module()
        outside = self.root / "outside"
        outside.mkdir()
        outside_source = outside / "source.md"
        outside_source.write_bytes(self.source_bytes)
        moved = self.root / "moved-sources"
        real_swap = module.atomic_swap_at
        swapped = {"done": False}
        def swapping_replace(parent_fd, left, right):
            if not swapped["done"] and left.startswith(".core-review-stage-"):
                swapped["done"] = True
                (self.root / "10_Sources").rename(moved)
                (self.root / "10_Sources").symlink_to(outside, target_is_directory=True)
            return real_swap(parent_fd, left, right)
        with mock.patch.object(module, "atomic_swap_at", side_effect=swapping_replace):
            code = module.run(["--vault-root", str(self.root)], io.StringIO(json.dumps(self.replace_envelope())), io.StringIO(), io.StringIO())
        self.assertIn(code, (3, 4))
        self.assertEqual(self.source_bytes, outside_source.read_bytes())
        self.assertEqual(self.source_bytes, (moved / "source.md").read_bytes())

    def interrupt_after_first_cas(self, module, envelope):
        real_cas = module.cas_install
        def interrupting_cas(*args, **kwargs):
            result = real_cas(*args, **kwargs)
            raise KeyboardInterrupt()
        with mock.patch.object(module, "cas_install", side_effect=interrupting_cas):
            with self.assertRaises(KeyboardInterrupt):
                module.run(["--vault-root", str(self.root)], io.StringIO(json.dumps(envelope)), io.StringIO(), io.StringIO())

    def test_interrupted_transaction_is_recovered_on_next_invocation(self):
        module = self.load_module()
        self.interrupt_after_first_cas(module, self.replace_envelope())
        self.assertNotEqual(self.source_bytes, self.source.read_bytes())
        proc = self.run_helper(None, "", "--recover-only")
        self.assertEqual(0, proc.returncode)
        self.assertEqual("recovered", json.loads(proc.stdout)["status"])
        self.assertEqual("prepared", json.loads(proc.stdout)["state"])
        self.assertEqual("CR-20260712-000001", json.loads(proc.stdout)["candidate_code"])
        self.assertEqual(self.source_bytes, self.source.read_bytes())
        self.assertFalse(any("journal" in p.name or "backup" in p.name for p in self.root.rglob(".*")))

    def test_dry_run_never_recovers_or_writes_an_interrupted_transaction(self):
        module = self.load_module()
        self.interrupt_after_first_cas(module, self.replace_envelope())
        before = self.snapshot()
        proc = self.run_helper(self.replace_envelope(source_sha256=sha(self.source.read_bytes())), None, "--dry-run")
        self.assertEqual(4, proc.returncode)
        self.assertEqual(before, self.snapshot())

    def test_recovery_does_not_delete_foreign_content_at_new_core_path(self):
        module = self.load_module()
        env = self.core_envelope()
        core = self.root / env["action"]["core_path"]
        self.interrupt_after_first_cas(module, env)
        core.write_bytes(b"foreign content\n")
        proc = self.run_helper(None, "", "--recover-only")
        self.assertEqual(4, proc.returncode)
        self.assertEqual(b"foreign content\n", core.read_bytes())
        self.assertTrue((self.root / ".core-review-journal.json").exists())

    def test_recovery_preserves_foreign_edit_or_missing_existing_leaf(self):
        for replacement in (b"foreign post-crash edit\n", None):
            with self.subTest(replacement=replacement):
                module = self.load_module()
                self.interrupt_after_first_cas(module, self.replace_envelope())
                if replacement is None:
                    self.source.unlink()
                else:
                    self.source.write_bytes(replacement)
                before = self.snapshot()
                proc = self.run_helper(None, "", "--recover-only")
                self.assertEqual(4, proc.returncode)
                self.assertEqual(before, self.snapshot())
                self.assertTrue((self.root / ".core-review-journal.json").exists())
                self.setUp_duplicate_fixture()
                (self.root / ".core-review-journal.json").unlink()

    def test_new_core_create_is_exclusive_at_cas_boundary(self):
        module = self.load_module()
        env = self.core_envelope()
        core = self.root / env["action"]["core_path"]
        real_exclusive = module.atomic_exclusive_at
        injected = {"done": False}
        def occupy_then_rename(parent_fd, source, target):
            if not injected["done"] and source.startswith(".core-review-stage-") and target == core.name:
                injected["done"] = True
                core.write_bytes(b"foreign at create boundary\n")
            return real_exclusive(parent_fd, source, target)
        with mock.patch.object(module, "atomic_exclusive_at", side_effect=occupy_then_rename):
            code = module.run(["--vault-root", str(self.root)], io.StringIO(json.dumps(env)), io.StringIO(), io.StringIO())
        self.assertEqual(4, code)
        self.assertEqual(b"foreign at create boundary\n", core.read_bytes())
        self.assertTrue((self.root / ".core-review-journal.json").exists())

    def test_any_nonregular_journal_entry_blocks_normal_and_recovery(self):
        journal = self.root / ".core-review-journal.json"
        outside = self.root / "outside-journal"
        outside.write_text("{}", encoding="utf-8")
        makers = (
            lambda: journal.symlink_to(outside),
            lambda: os.mkfifo(journal),
            lambda: journal.mkdir(),
        )
        for maker in makers:
            with self.subTest(maker=maker):
                maker()
                before = self.snapshot()
                proc = self.run_helper(self.replace_envelope(), None, "--dry-run")
                self.assertEqual(4, proc.returncode)
                self.assertEqual(before, self.snapshot())
                recover = self.run_helper(None, "", "--recover-only")
                self.assertEqual(4, recover.returncode)
                self.assertEqual(before, self.snapshot())
                if journal.is_dir() and not journal.is_symlink():
                    journal.rmdir()
                else:
                    journal.unlink()

    def test_recovery_status_is_read_only_and_reports_prepared(self):
        no_tx = self.run_helper(None, "", "--recovery-status")
        self.assertEqual({"state": "no_transaction", "candidate_code": None}, json.loads(no_tx.stdout))
        module = self.load_module()
        self.interrupt_after_first_cas(module, self.replace_envelope())
        before = self.snapshot()
        status = self.run_helper(None, "", "--recovery-status")
        self.assertEqual(0, status.returncode)
        self.assertEqual("prepared", json.loads(status.stdout)["state"])
        self.assertEqual("CR-20260712-000001", json.loads(status.stdout)["candidate_code"])
        self.assertEqual(before, self.snapshot())

    def test_committed_cleanup_failure_keeps_recoverable_journal(self):
        module = self.load_module()
        env = self.replace_envelope()
        code = module.run(["--vault-root", str(self.root)], io.StringIO(json.dumps(env)), io.StringIO(), io.StringIO())
        self.assertEqual(0, code)
        status = self.run_helper(None, "", "--recovery-status")
        self.assertEqual("committed", json.loads(status.stdout)["state"])
        self.assertIn(b"[[20_Core/Target]]", self.source.read_bytes())
        recovered = self.run_helper(None, "", "--recover-only")
        self.assertEqual(0, recovered.returncode, recovered.stderr)
        self.assertEqual("committed", json.loads(recovered.stdout)["state"])
        self.assertIn(b"[[20_Core/Target]]", self.source.read_bytes())
        self.assertTrue((self.root / ".core-review-journal.json").exists())
        ack = self.run_helper(None, "", "--ack-candidate", env["candidate_code"])
        self.assertEqual(0, ack.returncode, ack.stderr)
        self.assertFalse((self.root / ".core-review-journal.json").exists())

    def test_recovery_stdout_failure_identifies_preflight_candidate_and_state(self):
        module = self.load_module()
        self.interrupt_after_first_cas(module, self.replace_envelope())
        class BrokenOutput(io.StringIO):
            def write(self, value):
                raise BrokenPipeError()
        stderr = io.StringIO()
        code = module.run(["--vault-root", str(self.root), "--recover-only"], io.StringIO(), BrokenOutput(), stderr)
        self.assertEqual(5, code)
        self.assertIn("candidate_code=CR-20260712-000001", stderr.getvalue())
        self.assertIn("state=prepared", stderr.getvalue())
        self.assertEqual(self.source_bytes, self.source.read_bytes())

    def test_prepared_recovery_cleanup_failure_keeps_journal_for_retry(self):
        module = self.load_module()
        self.interrupt_after_first_cas(module, self.replace_envelope())
        with mock.patch.object(module, "cleanup_artifacts", return_value=False):
            code = module.run(["--vault-root", str(self.root), "--recover-only"], io.StringIO(), io.StringIO(), io.StringIO())
        self.assertEqual(6, code)
        self.assertEqual(self.source_bytes, self.source.read_bytes())
        self.assertTrue((self.root / ".core-review-journal.json").exists())
        self.assertEqual("rolled_back", json.loads((self.root / ".core-review-journal.json").read_text())["state"])
        retry = self.run_helper(None, "", "--recover-only")
        self.assertEqual(0, retry.returncode, retry.stderr)
        self.assertEqual("prepared", json.loads(retry.stdout)["state"])

    def test_committed_recovery_rejects_foreign_after_edit(self):
        module = self.load_module()
        code = module.run(["--vault-root", str(self.root)], io.StringIO(json.dumps(self.replace_envelope())), io.StringIO(), io.StringIO())
        self.assertEqual(0, code)
        foreign = b"foreign after committed apply\n"
        self.source.write_bytes(foreign)
        before = self.snapshot()
        recover = self.run_helper(None, "", "--recover-only")
        self.assertEqual(4, recover.returncode)
        self.assertEqual(before, self.snapshot())
        self.assertEqual(foreign, self.source.read_bytes())

    def test_skill_requires_recovery_preflight_before_claim_and_never_guesses_exit5(self):
        text = (HERE.parent / "SKILL.md").read_text(encoding="utf-8")
        approval = text[text.index("## Approval procedure"):]
        self.assertLess(approval.index("--recovery-status"), approval.index("claim_core_review_candidate"))
        self.assertIn("state=prepared|rolled_back", approval)
        self.assertIn("state=committed", approval)
        self.assertIn("--ack-candidate", approval)
        self.assertIn("stdout이나 현재 메시지 후보로 추측하지 않는다", approval)

    def test_apply_fails_closed_without_renameatx_np(self):
        module = self.load_module()
        with mock.patch.object(module, "RENAMEATX_NP", None):
            code = module.run(["--vault-root", str(self.root)], io.StringIO(json.dumps(self.replace_envelope())), io.StringIO(), io.StringIO())
        self.assertEqual(3, code)
        self.assertEqual(self.source_bytes, self.source.read_bytes())

    def load_module(self):
        spec = importlib.util.spec_from_file_location("apply_action_%s" % id(self), SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def setUp_duplicate_fixture(self):
        for child in list(self.root.iterdir()):
            if child.is_dir() and not child.is_symlink():
                for item in child.iterdir():
                    if item.is_file() or item.is_symlink():
                        item.unlink()
        self.source_bytes = b"---\ntype: source\nextracted_to: []\n---\n\n[[Broken]]\n"
        self.source.write_bytes(self.source_bytes)
        (self.root / self.target_rel).write_bytes(b"target\n")


if __name__ == "__main__":
    unittest.main()
