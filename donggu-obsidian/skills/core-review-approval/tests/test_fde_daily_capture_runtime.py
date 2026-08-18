#!/usr/bin/env python3
"""Behavior tests for the bounded FDE Community daily Capture writer."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock


HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parents[2]


def _load_runtime_module():
    import importlib.util
    import sys
    import types

    package_name = "donggu_obsidian_fde_daily_capture_test"
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


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class FDEDailyCaptureRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.vault = self.base / "vault"
        inbox = self.vault / "FDE Community" / "Inbox"
        inbox.mkdir(parents=True)
        runtime_module = _load_runtime_module()
        self.error = runtime_module.FDEDailyCaptureError
        self.runtime = runtime_module.FDEDailyCaptureRuntime(
            vault_root=self.vault,
            lock_root=self.base / "locks",
        )
        self.sections = {
            "coverage": "확인 가능한 최근 구간 · 읽기 전용 · 카카오 발송 0건",
            "situation": ["현장 질문 한 건이 확인됐다."],
            "problems": ["운영 전환 기준이 불명확하다."],
            "insights": ["사실 → 해석을 분리해야 한다."],
            "participant_map": ["실무자 역할군 — 구체 질문 1건"],
            "actions": ["지금 — 사례 질문을 한 줄로 좁힌다."],
            "judgment_holds": ["추가 사례 전에는 일반화하지 않는다."],
            "wiki_candidates": ["운영 전환 판단 기준 — 추가 관찰"],
        }

    def write(self, *, room_kind="public", date="2026-08-17", expected=None, sections=None):
        return self.runtime.upsert(
            room_kind=room_kind,
            analysis_date=date,
            expected_before_sha256=expected,
            sections=self.sections if sections is None else sections,
            cron_job_id=("fdc11961e59f" if room_kind == "public" else "28e24dbebacd"),
        )

    def test_creates_public_capture_with_fixed_path_and_readback(self):
        result = self.write()
        target = self.vault / result["path"]
        self.assertTrue(target.is_file())
        self.assertEqual("created", result["status"])
        self.assertEqual(_sha256(target), result["after_sha256"])
        text = target.read_text(encoding="utf-8")
        self.assertIn("type: capture", text)
        self.assertIn("source: kakao", text)
        self.assertIn("# 오픈카톡 일일 분석 — 2026-08-17", text)
        self.assertIn("## 참여자 지형", text)
        self.assertNotIn("member_", text)

    def test_creates_operator_capture_in_separate_fixed_file(self):
        result = self.write(room_kind="operators")
        self.assertEqual(
            "FDE Community/Inbox/CAPTURE - 2026-08-17 - 운영진방 일일 분석.md",
            result["path"],
        )
        text = (self.vault / result["path"]).read_text(encoding="utf-8")
        self.assertIn("operations", text)
        self.assertIn("# 운영진방 일일 분석 — 2026-08-17", text)

    def test_same_bytes_are_idempotent(self):
        first = self.write()
        second = self.write(expected=first["after_sha256"])
        self.assertEqual("unchanged", second["status"])
        self.assertEqual(first["after_sha256"], second["after_sha256"])

    def test_changed_existing_capture_requires_matching_before_hash(self):
        first = self.write()
        changed = {**self.sections, "situation": ["바뀐 상황"]}
        with self.assertRaises(self.error):
            self.write(expected="0" * 64, sections=changed)
        target = self.vault / first["path"]
        self.assertEqual(first["after_sha256"], _sha256(target))
        updated = self.write(expected=first["after_sha256"], sections=changed)
        self.assertEqual("updated", updated["status"])
        self.assertIn("바뀐 상황", target.read_text(encoding="utf-8"))

    def test_existing_target_without_expected_hash_is_not_overwritten(self):
        first = self.write()
        changed = {**self.sections, "situation": ["무단 덮어쓰기 시도"]}
        with self.assertRaises(self.error):
            self.write(sections=changed)
        target = self.vault / first["path"]
        self.assertEqual(first["after_sha256"], _sha256(target))

    def test_rejects_wrong_job_for_room_kind(self):
        with self.assertRaises(self.error):
            self.runtime.upsert(
                room_kind="public",
                analysis_date="2026-08-17",
                expected_before_sha256=None,
                sections=self.sections,
                cron_job_id="28e24dbebacd",
            )

    def test_rejects_empty_or_sensitive_sections_before_write(self):
        for sections in (
            {**self.sections, "situation": []},
            {**self.sections, "situation": ["연락처 010-1234-5678"]},
            {**self.sections, "situation": ["user@example.com"]},
            {**self.sections, "situation": ["member_abcd1234"]},
        ):
            with self.subTest(sections=sections["situation"]):
                with self.assertRaises(self.error):
                    self.write(sections=sections)
        self.assertEqual([], list((self.vault / "FDE Community/Inbox").glob("CAPTURE - *.md")))

    def test_rejects_invalid_date_and_symlink_target(self):
        with self.assertRaises(self.error):
            self.write(date="2026-W34")
        outside = self.base / "outside.md"
        outside.write_text("foreign\n", encoding="utf-8")
        target = self.vault / "FDE Community/Inbox/CAPTURE - 2026-08-17 - 오픈카톡 일일 분석.md"
        target.symlink_to(outside)
        with self.assertRaises(self.error):
            self.write()
        self.assertEqual("foreign\n", outside.read_text(encoding="utf-8"))

    def test_concurrent_edit_at_commit_boundary_is_preserved(self):
        first = self.write()
        target = self.vault / first["path"]
        changed = {**self.sections, "situation": ["승인된 새 내용"]}

        def mutate_before_commit(_target: Path) -> None:
            _target.write_text("foreign concurrent edit\n", encoding="utf-8")

        self.runtime.before_commit_hook = mutate_before_commit
        with self.assertRaises(self.error):
            self.write(expected=first["after_sha256"], sections=changed)
        self.assertEqual("foreign concurrent edit\n", target.read_text(encoding="utf-8"))
        self.assertFalse(any(target.parent.glob(".fde-daily-capture-*")))

    def test_frontmatter_and_content_are_bounded(self):
        oversized = {**self.sections, "situation": ["x" * 5001]}
        with self.assertRaises(self.error):
            self.write(sections=oversized)

    def test_unavailable_atomic_primitives_fail_without_write(self):
        module = __import__(
            "donggu_obsidian_fde_daily_capture_test.runtime.fde_daily_capture",
            fromlist=["fde_daily_capture"],
        )
        with mock.patch.object(module, "_EXCLUSIVE_RENAME", None):
            with self.assertRaises(self.error):
                self.write()
        self.assertEqual([], list((self.vault / "FDE Community/Inbox").glob("CAPTURE - *.md")))

    def test_created_target_readback_failure_is_removed(self):
        module = __import__(
            "donggu_obsidian_fde_daily_capture_test.runtime.fde_daily_capture",
            fromlist=["fde_daily_capture"],
        )
        original = module._read_leaf
        calls = 0

        def fail_second_read(directory_fd, name):
            nonlocal calls
            calls += 1
            if calls == 2:
                return b"corrupt", None
            return original(directory_fd, name)

        with mock.patch.object(module, "_read_leaf", side_effect=fail_second_read):
            with self.assertRaises(self.error):
                self.write()
        self.assertEqual([], list((self.vault / "FDE Community/Inbox").glob("CAPTURE - *.md")))
        self.assertFalse(any((self.vault / "FDE Community/Inbox").glob(".fde-daily-capture-*")))


if __name__ == "__main__":
    unittest.main()
