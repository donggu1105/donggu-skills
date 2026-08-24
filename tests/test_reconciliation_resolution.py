"""Reconciliation 해소 도구 — 사용자 승인 기반, 손수정 제거.

회귀 근거(2026-08-24): `image_validation_failed`가 발행 전 실패인데도
`reconciliation_required`로 기록되어 같은 채널+토픽의 후속 발행이 영구 차단됐다.
해소 경로가 코드에 없어서 운영자가 영수증 JSON 파일을 직접 열어 state를 고쳐야
복구됐다. 안전장치를 우회하는 수작업이 유일한 복구 수단인 것 자체가 결함이다.

설계 원칙:
  - 해소는 mutation이다. 프리뷰 → 사용자 승인(later turn) → 실행을 그대로 따른다.
  - 어떤 상태로 종결할지 사용자가 고른다: 외부 변경 없음(재발행 가능) /
    외부 변경 있음(장부 기록 후 종결).
  - 조회는 승인 없이 가능해야 한다. 무엇이 막고 있는지 봐야 판단할 수 있다.
"""
import json
import time
import unittest
from unittest import mock

from tests.test_publishing_runtime import PublishingRuntimeTests


class ReconciliationResolutionTest(PublishingRuntimeTests):

    def _make_stuck_receipt(self, *, channel="tistory", topic="stuck-topic"):
        """reconciliation_required 상태의 영수증을 하나 만든다."""
        store = self.runtime.store
        receipt = store.issue({
            "channel": channel,
            "operation": "publish",
            "topic": topic,
            "note_path": "note.md",
            "payload": {"title": "t", "content": "c"},
            "payload_sha256": "0" * 64,
            "session_sha256": "1" * 64,
            "preview_turn_sha256": "2" * 64,
            "preview_message_id": 1,
        })
        store.transition(
            receipt,
            "reconciliation_required",
            result={"url": None, "post_id": None, "job_id": None,
                    "error": "image_validation_failed: test"},
        )
        return receipt["receipt_id"]

    # --- 조회: 승인 없이 가능 ---

    def test_list_blocking_receipts_needs_no_approval(self):
        receipt_id = self._make_stuck_receipt()
        blocking = self.runtime.list_reconciliations()
        ids = [item["receipt_id"] for item in blocking]
        self.assertIn(receipt_id, ids)
        entry = next(i for i in blocking if i["receipt_id"] == receipt_id)
        self.assertEqual("tistory", entry["channel"])
        self.assertEqual("stuck-topic", entry["topic"])
        self.assertIn("image_validation_failed", str(entry.get("error")))

    def test_list_excludes_non_reconciliation_receipts(self):
        self.runtime.store.issue({
            "channel": "tistory", "operation": "publish", "topic": "clean",
            "note_path": "n.md", "payload": {}, "payload_sha256": "0" * 64,
            "session_sha256": "1" * 64, "preview_turn_sha256": "2" * 64,
            "preview_message_id": 1,
        })
        topics = [i["topic"] for i in self.runtime.list_reconciliations()]
        self.assertNotIn("clean", topics)

    # --- 해소: 사용자 승인 필요 ---

    def test_resolve_requires_later_turn_approval(self):
        receipt_id = self._make_stuck_receipt()
        with self.assertRaises(self.module.PublishingError):
            self.runtime.resolve_reconciliation(
                receipt_id,
                resolution="no_external_change",
                approval_text="",                 # 빈 승인 = 거부
                session_id=self.SESSION_ID,
                turn_id="turn-x",
                user_message_id=999,
            )

    def test_resolve_rejects_wrong_approval_verb(self):
        receipt_id = self._make_stuck_receipt()
        with self.assertRaises(self.module.PublishingError):
            self.runtime.resolve_reconciliation(
                receipt_id,
                resolution="no_external_change",
                approval_text="발행해",            # 해소 동사가 아님
                session_id=self.SESSION_ID,
                turn_id="turn-x",
                user_message_id=999,
            )

    def test_resolve_no_external_change_unblocks_channel(self):
        receipt_id = self._make_stuck_receipt()
        result = self.runtime.resolve_reconciliation(
            receipt_id,
            resolution="no_external_change",
            approval_text="재조정 해소해줘",
            session_id=self.SESSION_ID,
            turn_id="turn-x",
            user_message_id=999,
        )
        self.assertEqual("resolved_no_external_change", result["state"])
        # 해소 후에는 같은 채널+토픽으로 새 영수증이 발급되어야 한다.
        self.runtime.store.assert_no_reconciliation(
            channel="tistory", topic="stuck-topic",
        )

    def test_resolve_records_evidence(self):
        receipt_id = self._make_stuck_receipt()
        self.runtime.resolve_reconciliation(
            receipt_id,
            resolution="no_external_change",
            approval_text="재조정 해소해줘",
            evidence="티스토리 /307, /308 모두 404. 장부 무기록.",
            session_id=self.SESSION_ID,
            turn_id="turn-x",
            user_message_id=999,
        )
        status = self.runtime.receipt_status(receipt_id)
        self.assertIn("404", json.dumps(status, ensure_ascii=False))

    def test_resolve_is_one_shot(self):
        receipt_id = self._make_stuck_receipt()
        kwargs = dict(
            resolution="no_external_change",
            approval_text="재조정 해소해줘",
            session_id=self.SESSION_ID,
            turn_id="turn-x",
            user_message_id=999,
        )
        self.runtime.resolve_reconciliation(receipt_id, **kwargs)
        with self.assertRaises(self.module.PublishingError):
            self.runtime.resolve_reconciliation(receipt_id, **kwargs)

    def test_resolve_rejects_unknown_resolution(self):
        receipt_id = self._make_stuck_receipt()
        with self.assertRaises(self.module.PublishingError):
            self.runtime.resolve_reconciliation(
                receipt_id,
                resolution="whatever",
                approval_text="재조정 해소해줘",
                session_id=self.SESSION_ID,
                turn_id="turn-x",
                user_message_id=999,
            )

    def test_resolve_rejects_non_reconciliation_receipt(self):
        receipt = self.runtime.store.issue({
            "channel": "tistory", "operation": "publish", "topic": "fresh",
            "note_path": "n.md", "payload": {}, "payload_sha256": "0" * 64,
            "session_sha256": "1" * 64, "preview_turn_sha256": "2" * 64,
            "preview_message_id": 1,
        })
        with self.assertRaises(self.module.PublishingError):
            self.runtime.resolve_reconciliation(
                receipt["receipt_id"],
                resolution="no_external_change",
                approval_text="재조정 해소해줘",
                session_id=self.SESSION_ID,
                turn_id="turn-x",
                user_message_id=999,
            )

    def test_resolve_external_change_keeps_channel_blocked_until_ledger(self):
        """외부 변경이 있었다면 장부 기록 없이 종결하지 않는다."""
        receipt_id = self._make_stuck_receipt()
        with self.assertRaises(self.module.PublishingError):
            self.runtime.resolve_reconciliation(
                receipt_id,
                resolution="external_change_recorded",
                approval_text="재조정 해소해줘",
                # url/post_id 없이 외부변경 종결 시도 → 거부
                session_id=self.SESSION_ID,
                turn_id="turn-x",
                user_message_id=999,
            )


if __name__ == "__main__":
    unittest.main()
