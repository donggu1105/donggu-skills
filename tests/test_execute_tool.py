"""통합 실행 도구 — 승인과 실행 사이의 틈 제거.

회귀 근거(2026-08-24): 발행 한 건에 `preview → approve → dispatch` 3회 호출이 필요했고,
`approve`와 `dispatch` 사이에서 모델이 멈추거나 다른 작업을 끼워 넣을 수 있었다. 승인은
이미 소모됐는데 dispatch 전에 실행 창이 지나가는 일이 반복됐다.

승인 이후는 사용자가 개입할 지점이 아니다. 승인 결속 → 실행을 한 번의 도구 호출로
원자화해서, 모델이 중간에 이탈할 수 있는 표면 자체를 없앤다.

안전장치는 그대로다 — later-turn 승인, 동사 일치, 일회용 소비, Maily 2차 확인.
"""
import unittest

from tests.test_publishing_runtime import PublishingRuntimeTests


class ExecuteToolTest(PublishingRuntimeTests):
    """`execute`는 approve + dispatch를 하나의 원자적 호출로 수행한다."""

    def test_execute_publishes_in_one_call(self):
        plan = self.preview_threads()
        result = self.runtime.execute(
            plan["receipt_id"],
            approval_text="올려줘",
            session_id=self.SESSION_ID,
            turn_id=self.APPROVAL_TURN,
            user_message_id=self.APPROVAL_MESSAGE_ID,
        )
        self.assertEqual("completed", result["status"])

    def test_execute_rejects_preview_turn(self):
        """프리뷰와 같은 턴으로는 실행할 수 없다 — later-turn 규율 유지."""
        plan = self.preview_threads()
        with self.assertRaises(self.module.ApprovalError):
            self.runtime.execute(
                plan["receipt_id"],
                approval_text="올려줘",
                session_id=self.SESSION_ID,
                turn_id=self.PREVIEW_TURN,
                user_message_id=self.PREVIEW_MESSAGE_ID,
            )

    def test_execute_rejects_other_session(self):
        plan = self.preview_threads()
        with self.assertRaises(self.module.ApprovalError):
            self.runtime.execute(
                plan["receipt_id"],
                approval_text="올려줘",
                session_id="other-session",
                turn_id=self.APPROVAL_TURN,
                user_message_id=self.APPROVAL_MESSAGE_ID,
            )

    def test_execute_rejects_wrong_operation_verb(self):
        """publish 영수증을 delete 동사로 실행할 수 없다."""
        plan = self.preview_threads()
        with self.assertRaises(self.module.ApprovalError):
            self.runtime.execute(
                plan["receipt_id"],
                approval_text="삭제해줘",
                session_id=self.SESSION_ID,
                turn_id=self.APPROVAL_TURN,
                user_message_id=self.APPROVAL_MESSAGE_ID,
            )

    def test_execute_rejects_non_final_and_negated_intent(self):
        plan = self.preview_threads()
        for text in ("올려줘 볼까?", "나중에 올려줘", "올려주지 마"):
            with self.subTest(text=text):
                with self.assertRaises(self.module.ApprovalError):
                    self.runtime.execute(
                        plan["receipt_id"],
                        approval_text=text,
                        session_id=self.SESSION_ID,
                        turn_id=self.APPROVAL_TURN,
                        user_message_id=self.APPROVAL_MESSAGE_ID,
                    )

    def test_execute_is_one_shot(self):
        plan = self.preview_threads()
        kwargs = dict(
            approval_text="올려줘",
            session_id=self.SESSION_ID,
            turn_id=self.APPROVAL_TURN,
            user_message_id=self.APPROVAL_MESSAGE_ID,
        )
        self.runtime.execute(plan["receipt_id"], **kwargs)
        with self.assertRaises(self.module.PublishingError):
            self.runtime.execute(plan["receipt_id"], **kwargs)

    def test_execute_blocks_maily_real_send_without_confirmation(self):
        """Maily 실발송은 execute 한 번으로 나가지 않는다 — 2차 확인 유지."""
        plan = self.runtime.preview(
            channel="maily",
            operation="publish",
            payload={
                "title": "Title", "subtitle": "Subtitle",
                "content": "Body", "dry_run": False,
            },
            topic="maily-exec",
            note_path="note.md",
            session_id=self.SESSION_ID,
            turn_id=self.PREVIEW_TURN,
            user_message_id=self.PREVIEW_MESSAGE_ID,
        )
        with self.assertRaises(self.module.PublishingError):
            self.runtime.execute(
                plan["receipt_id"],
                approval_text="발행해",
                session_id=self.SESSION_ID,
                turn_id=self.APPROVAL_TURN,
                user_message_id=self.APPROVAL_MESSAGE_ID,
            )

    def test_legacy_approve_then_dispatch_still_works(self):
        """기존 2단계 경로를 깨지 않는다."""
        plan = self.preview_threads()
        result = self.approve_and_dispatch(plan)
        self.assertEqual("completed", result["status"])


if __name__ == "__main__":
    unittest.main()
