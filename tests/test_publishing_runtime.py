#!/usr/bin/env python3
import importlib.util
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import threading
import unittest
from unittest import mock
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "donggu-sns" / "runtime" / "publishing.py"


def load_module():
    spec = importlib.util.spec_from_file_location("donggu_publishing_runtime", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class FakeApiHandler(BaseHTTPRequestHandler):
    requests = []
    fail_ledger_insert = False
    empty_ledger_write = False
    redirect_webhook = False
    incomplete_webhook_response = False
    duplicate_active_posts = False
    active_post = {"id": 41, "post_id": "existing-post", "url": "https://example.test/existing", "note_path": "note.md"}

    def log_message(self, format, *args):
        pass

    def _body(self):
        size = int(self.headers.get("Content-Length", "0"))
        return json.loads(self.rfile.read(size) or b"{}")

    def _send(self, status, payload, *, location=None):
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        if location:
            self.send_header("Location", location)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        parsed = urlparse(self.path)
        type(self).requests.append(("GET", parsed.path, dict(self.headers), None, parsed.query))
        if parsed.path == "/rest/v1/published_posts":
            rows = [dict(type(self).active_post)]
            if type(self).duplicate_active_posts:
                rows.append({**type(self).active_post, "id": 42})
            self._send(200, rows)
            return
        if parsed.path == "/redirect-target":
            self._send(200, {"success": True, "url": "https://leak.test/post", "post_id": "leaked"})
            return
        self._send(404, {"error": "not found"})

    def do_POST(self):
        parsed = urlparse(self.path)
        body = self._body()
        type(self).requests.append(("POST", parsed.path, dict(self.headers), body, parsed.query))
        if parsed.path == "/webhook/sns-pub-threads":
            if type(self).redirect_webhook:
                self._send(302, {}, location="/redirect-target")
            elif type(self).incomplete_webhook_response:
                self._send(200, {"success": True})
            else:
                self._send(200, {"success": True, "url": "https://threads.test/post/1", "post_id": "thread-1"})
            return
        if parsed.path == "/webhook/sns-pub-maily":
            self._send(200, {"success": True, "url": "https://maily.test/post/1", "post_id": None})
            return
        if parsed.path == "/webhook/sns-del-threads":
            self._send(200, {"success": True})
            return
        if parsed.path == "/rest/v1/published_posts":
            if type(self).fail_ledger_insert:
                self._send(500, {"error": "ledger unavailable"})
            elif type(self).empty_ledger_write:
                self._send(201, [])
            else:
                self._send(201, [body])
            return
        self._send(404, {"error": "not found"})

    def do_PATCH(self):
        parsed = urlparse(self.path)
        body = self._body()
        type(self).requests.append(("PATCH", parsed.path, dict(self.headers), body, parsed.query))
        if parsed.path == "/rest/v1/published_posts":
            if type(self).empty_ledger_write:
                self._send(200, [])
            else:
                self._send(200, [{**type(self).active_post, **body}])
            return
        self._send(404, {"error": "not found"})


class PublishingRuntimeTests(unittest.TestCase):
    SESSION_ID = "session-1"
    PREVIEW_TURN = "turn-preview"
    APPROVAL_TURN = "turn-approval"
    CONFIRM_TURN = "turn-confirm"
    PREVIEW_MESSAGE_ID = 1
    APPROVAL_MESSAGE_ID = 2
    CONFIRM_MESSAGE_ID = 3

    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), FakeApiHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.thread.join(timeout=5)
        cls.server.server_close()

    def setUp(self):
        self.module = load_module()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        FakeApiHandler.requests = []
        FakeApiHandler.fail_ledger_insert = False
        FakeApiHandler.empty_ledger_write = False
        FakeApiHandler.redirect_webhook = False
        FakeApiHandler.incomplete_webhook_response = False
        FakeApiHandler.duplicate_active_posts = False
        ledger = self.module.SupabaseLedger(base_url=self.base, service_key="service-secret", allow_test_origins=True)
        self.runtime = self.module.PublishingRuntime(
            receipt_root=Path(self.tmp.name) / "receipts",
            webhook_base_url=f"{self.base}/webhook",
            webhook_token="webhook-secret",
            ledger=ledger,
            receipt_ttl_seconds=900,
            allow_test_origins=True,
        )

    def preview_threads(self):
        return self.runtime.preview(
            channel="threads",
            operation="publish",
            payload={"content": "hello", "image_urls": ["https://img.test/1.png"]},
            topic="demo",
            note_path="50_Channel_Packs/1_SNS/Threads/Threads - demo.md",
            session_id=self.SESSION_ID,
            turn_id=self.PREVIEW_TURN, user_message_id=self.PREVIEW_MESSAGE_ID,
        )

    def approve_and_dispatch(self, plan, text="올려줘"):
        approved = self.runtime.approve(
            plan["receipt_id"], approval_text=text,
            session_id=self.SESSION_ID, turn_id=self.APPROVAL_TURN, user_message_id=self.APPROVAL_MESSAGE_ID,
        )
        self.assertEqual("approved", approved["status"])
        return self.runtime.dispatch(plan["receipt_id"], session_id=self.SESSION_ID)

    def test_preview_issues_bound_receipt_without_network(self):
        result = self.preview_threads()
        self.assertEqual("planned", result["status"])
        self.assertEqual(1, result["preview"]["image_count"])
        self.assertEqual([], FakeApiHandler.requests)
        receipt = Path(self.tmp.name) / "receipts" / f"{result['receipt_id']}.json"
        self.assertEqual(0o600, stat.S_IMODE(receipt.stat().st_mode))
        stored = json.loads(receipt.read_text(encoding="utf-8"))
        self.assertEqual(result["payload_sha256"], stored["payload_sha256"])
        self.assertNotIn("webhook-secret", json.dumps(result))
        self.assertNotIn("service-secret", json.dumps(result))

    def test_stateless_preview_does_not_issue_a_receipt(self):
        result = self.runtime.preview(
            channel="threads", operation="publish", payload={"content": "hello"},
            topic="stateless", note_path="note.md", session_id="claude-preview-only",
            turn_id="stateless-turn", issue_receipt=False,
        )
        self.assertEqual("preview", result["status"])
        self.assertNotIn("receipt_id", result)
        self.assertEqual([], list((Path(self.tmp.name) / "receipts").glob("*.json")))

    def test_receipt_hmac_key_is_process_local_and_not_written_to_disk(self):
        plan = self.preview_threads()
        other = self.module.PublishingRuntime(
            receipt_root=Path(self.tmp.name) / "receipts",
            webhook_base_url=f"{self.base}/webhook",
            webhook_token="webhook-secret",
            ledger=self.runtime.ledger,
            receipt_ttl_seconds=900,
            allow_test_origins=True,
        )
        with self.assertRaises(self.module.ReceiptError):
            other.receipt_status(plan["receipt_id"])
        self.assertFalse((Path(self.tmp.name) / "receipt-signing.key").exists())

    def test_approval_and_dispatch_are_separate_state_transitions(self):
        plan = self.preview_threads()
        with self.assertRaises(self.module.ReceiptError):
            self.runtime.dispatch(plan["receipt_id"], session_id=self.SESSION_ID)
        with self.assertRaises(self.module.ApprovalError):
            self.runtime.approve(
                plan["receipt_id"], approval_text=" ",
                session_id=self.SESSION_ID, turn_id=self.APPROVAL_TURN, user_message_id=self.APPROVAL_MESSAGE_ID,
            )
        result = self.approve_and_dispatch(plan)
        self.assertEqual("completed", result["status"])
        webhook = [r for r in FakeApiHandler.requests if r[1] == "/webhook/sns-pub-threads"]
        inserts = [r for r in FakeApiHandler.requests if r[0] == "POST" and r[1] == "/rest/v1/published_posts"]
        self.assertEqual(1, len(webhook))
        self.assertEqual(1, len(inserts))
        headers = {key.lower(): value for key, value in webhook[0][2].items()}
        self.assertEqual("webhook-secret", headers["x-sns-token"])
        self.assertEqual(plan["receipt_id"], headers["x-idempotency-key"])
        with self.assertRaises(self.module.ReceiptError):
            self.runtime.dispatch(plan["receipt_id"], session_id=self.SESSION_ID)

    def test_approval_requires_same_session_and_later_trusted_turn(self):
        plan = self.preview_threads()
        with self.assertRaises(self.module.ApprovalError):
            self.runtime.approve(
                plan["receipt_id"], approval_text="올려줘",
                session_id=self.SESSION_ID, turn_id=self.PREVIEW_TURN, user_message_id=self.PREVIEW_MESSAGE_ID,
            )
        with self.assertRaises(self.module.ApprovalError):
            self.runtime.approve(
                plan["receipt_id"], approval_text="올려줘",
                session_id="other-session", turn_id=self.APPROVAL_TURN, user_message_id=self.APPROVAL_MESSAGE_ID,
            )
        with self.assertRaises(self.module.ApprovalError):
            self.runtime.approve(
                plan["receipt_id"], approval_text="오늘 날씨 알려줘",
                session_id=self.SESSION_ID, turn_id=self.APPROVAL_TURN, user_message_id=self.APPROVAL_MESSAGE_ID,
            )
        with self.assertRaises(self.module.ApprovalError):
            self.runtime.approve(
                plan["receipt_id"], approval_text="발행하지 마",
                session_id=self.SESSION_ID, turn_id=self.APPROVAL_TURN, user_message_id=self.APPROVAL_MESSAGE_ID,
            )
        with self.assertRaises(self.module.ApprovalError):
            self.runtime.approve(
                plan["receipt_id"], approval_text="올려줘",
                session_id=self.SESSION_ID, turn_id=self.APPROVAL_TURN,
                user_message_id=self.PREVIEW_MESSAGE_ID,
            )
        approved = self.runtime.approve(
            plan["receipt_id"], approval_text="올려줘",
            session_id=self.SESSION_ID, turn_id=self.APPROVAL_TURN, user_message_id=self.APPROVAL_MESSAGE_ID,
        )
        self.assertEqual("approved", approved["status"])
        with self.assertRaises(self.module.ApprovalError):
            self.runtime.dispatch(plan["receipt_id"], session_id="other-session")

    def test_approved_receipt_expires_before_dispatch(self):
        runtime = self.module.PublishingRuntime(
            receipt_root=Path(self.tmp.name) / "expiring",
            webhook_base_url=f"{self.base}/webhook",
            webhook_token="webhook-secret",
            ledger=self.runtime.ledger,
            receipt_ttl_seconds=1,
            allow_test_origins=True,
        )
        with mock.patch.object(self.module.time, "time", return_value=100.0):
            plan = runtime.preview(
                channel="threads", operation="publish", payload={"content": "hello"},
                topic="expiry", note_path="note.md",
                session_id=self.SESSION_ID, turn_id=self.PREVIEW_TURN, user_message_id=self.PREVIEW_MESSAGE_ID,
            )
            runtime.approve(
                plan["receipt_id"], approval_text="올려줘",
                session_id=self.SESSION_ID, turn_id=self.APPROVAL_TURN, user_message_id=self.APPROVAL_MESSAGE_ID,
            )
        with mock.patch.object(self.module.time, "time", return_value=102.0):
            with self.assertRaises(self.module.ReceiptError):
                runtime.dispatch(plan["receipt_id"], session_id=self.SESSION_ID)
        self.assertEqual([], FakeApiHandler.requests)

    def test_one_persisted_authorization_cannot_approve_multiple_receipts(self):
        first = self.preview_threads()
        second = self.runtime.preview(
            channel="threads", operation="publish",
            payload={"content": "different", "image_urls": ["https://img.test/2.png"]},
            topic="demo-2", note_path="50_Channel_Packs/1_SNS/Threads/Threads - demo-2.md",
            session_id=self.SESSION_ID, turn_id=self.PREVIEW_TURN,
            user_message_id=self.PREVIEW_MESSAGE_ID,
        )
        plans = [first, second]

        def approve(index):
            try:
                self.runtime.approve(
                    plans[index]["receipt_id"], approval_text="승인",
                    session_id=self.SESSION_ID, turn_id=self.APPROVAL_TURN,
                    user_message_id=self.APPROVAL_MESSAGE_ID,
                )
                return "won"
            except self.module.ApprovalError:
                return "lost"

        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(approve, (0, 1)))
        self.assertEqual(1, outcomes.count("won"))
        self.assertEqual(1, outcomes.count("lost"))
        states = [self.runtime.receipt_status(plan["receipt_id"])["state"] for plan in plans]
        self.assertEqual(["approved", "planned"], sorted(states))

    def test_one_persisted_authorization_cannot_confirm_multiple_maily_receipts(self):
        plans = []
        for index in (1, 2):
            plan = self.runtime.preview(
                channel="maily", operation="publish",
                payload={"title": f"Title {index}", "subtitle": "Subtitle", "content": "Body", "dry_run": False},
                topic=f"mail-{index}", note_path=f"50_Channel_Packs/1_SNS/Maily/Maily - mail-{index}.md",
                session_id=self.SESSION_ID, turn_id=self.PREVIEW_TURN,
                user_message_id=self.PREVIEW_MESSAGE_ID,
            )
            self.runtime.approve(
                plan["receipt_id"], approval_text="발행해줘",
                session_id=self.SESSION_ID, turn_id=f"approval-{index}",
                user_message_id=10 + index,
            )
            plans.append(plan)
        self.runtime.confirm_irreversible(
            plans[0]["receipt_id"], confirmation_text="메일 최종 발송 확인",
            session_id=self.SESSION_ID, turn_id="confirm-final", user_message_id=20,
        )
        with self.assertRaises(self.module.ApprovalError):
            self.runtime.confirm_irreversible(
                plans[1]["receipt_id"], confirmation_text="메일 최종 발송 확인",
                session_id=self.SESSION_ID, turn_id="confirm-final", user_message_id=20,
            )
        self.assertEqual("approved", self.runtime.receipt_status(plans[1]["receipt_id"])["state"])

    def test_maily_real_send_requires_separate_irreversible_confirmation(self):
        plan = self.runtime.preview(
            channel="maily", operation="publish",
            payload={"title": "Title", "subtitle": "Subtitle", "content": "Body", "dry_run": False},
            topic="mail", note_path="50_Channel_Packs/1_SNS/Maily/Maily - mail.md",
            session_id=self.SESSION_ID, turn_id=self.PREVIEW_TURN, user_message_id=self.PREVIEW_MESSAGE_ID,
        )
        self.runtime.approve(
            plan["receipt_id"], approval_text="발행해줘",
            session_id=self.SESSION_ID, turn_id=self.APPROVAL_TURN, user_message_id=self.APPROVAL_MESSAGE_ID,
        )
        with self.assertRaises(self.module.ReceiptError):
            self.runtime.dispatch(plan["receipt_id"], session_id=self.SESSION_ID)
        with self.assertRaises(self.module.ApprovalError):
            self.runtime.confirm_irreversible(
                plan["receipt_id"], confirmation_text="메일 최종 발송 확인",
                session_id=self.SESSION_ID, turn_id=self.APPROVAL_TURN, user_message_id=self.APPROVAL_MESSAGE_ID,
            )
        with self.assertRaises(self.module.ApprovalError):
            self.runtime.confirm_irreversible(
                plan["receipt_id"], confirmation_text="오늘 날씨 알려줘",
                session_id=self.SESSION_ID, turn_id=self.CONFIRM_TURN, user_message_id=self.CONFIRM_MESSAGE_ID,
            )
        with self.assertRaises(self.module.ApprovalError):
            self.runtime.confirm_irreversible(
                plan["receipt_id"], confirmation_text="메일 발송 확인",
                session_id=self.SESSION_ID, turn_id=self.CONFIRM_TURN, user_message_id=self.CONFIRM_MESSAGE_ID,
            )
        with self.assertRaises(self.module.ApprovalError):
            self.runtime.confirm_irreversible(
                plan["receipt_id"], confirmation_text="메일 최종 발송 확인",
                session_id=self.SESSION_ID, turn_id=self.CONFIRM_TURN,
                user_message_id=self.APPROVAL_MESSAGE_ID,
            )
        confirmed = self.runtime.confirm_irreversible(
            plan["receipt_id"], confirmation_text="메일 최종 발송 확인",
            session_id=self.SESSION_ID, turn_id=self.CONFIRM_TURN, user_message_id=self.CONFIRM_MESSAGE_ID,
        )
        self.assertEqual("confirmed", confirmed["status"])
        self.assertEqual("completed", self.runtime.dispatch(plan["receipt_id"], session_id=self.SESSION_ID)["status"])

    def test_maily_dry_run_does_not_write_published_ledger(self):
        plan = self.runtime.preview(
            channel="maily", operation="publish",
            payload={"title": "Title", "subtitle": "Subtitle", "content": "Body", "dry_run": True},
            topic="mail-draft", note_path="50_Channel_Packs/1_SNS/Maily/Maily - mail.md",
            session_id=self.SESSION_ID, turn_id=self.PREVIEW_TURN, user_message_id=self.PREVIEW_MESSAGE_ID,
        )
        result = self.approve_and_dispatch(plan)
        self.assertEqual("completed_draft", result["status"])
        inserts = [r for r in FakeApiHandler.requests if r[0] == "POST" and r[1] == "/rest/v1/published_posts"]
        self.assertEqual([], inserts)

    def test_receipt_payload_tampering_is_rejected_before_network(self):
        plan = self.preview_threads()
        path = Path(self.tmp.name) / "receipts" / f"{plan['receipt_id']}.json"
        stored = json.loads(path.read_text(encoding="utf-8"))
        stored["payload"]["content"] = "TAMPERED"
        path.write_text(json.dumps(stored), encoding="utf-8")
        with self.assertRaises(self.module.ReceiptError):
            self.runtime.approve(
                plan["receipt_id"], approval_text="올려줘",
                session_id=self.SESSION_ID, turn_id=self.APPROVAL_TURN, user_message_id=self.APPROVAL_MESSAGE_ID,
            )
        self.assertEqual([], FakeApiHandler.requests)

    def test_recomputed_hash_and_approval_state_forgery_is_rejected(self):
        plan = self.preview_threads()
        path = Path(self.tmp.name) / "receipts" / f"{plan['receipt_id']}.json"
        stored = json.loads(path.read_text(encoding="utf-8"))
        stored["payload"]["content"] = "TAMPERED"
        binding = {
            "channel": stored["channel"], "operation": stored["operation"],
            "payload": stored["payload"], "topic": stored["topic"],
            "note_path": stored["note_path"], "resolved": stored["resolved"],
        }
        stored["payload_sha256"] = self.module._sha256(binding)
        stored["state"] = "approved"
        path.write_text(json.dumps(stored), encoding="utf-8")
        with self.assertRaises(self.module.ReceiptError):
            self.runtime.dispatch(plan["receipt_id"], session_id=self.SESSION_ID)
        self.assertEqual([], FakeApiHandler.requests)

    def test_webhook_redirect_is_not_followed_and_is_definitive_failure(self):
        FakeApiHandler.redirect_webhook = True
        plan = self.preview_threads()
        result = self.approve_and_dispatch(plan)
        self.assertEqual("failed", result["status"])
        self.assertFalse(any(r[1] == "/redirect-target" for r in FakeApiHandler.requests))

    def test_invalid_production_origins_are_rejected(self):
        with self.assertRaises(self.module.ValidationError):
            self.module.SupabaseLedger(base_url="http://attacker.invalid", service_key="secret")
        with self.assertRaises(self.module.ValidationError):
            self.module.PublishingRuntime(
                receipt_root=Path(self.tmp.name) / "bad", webhook_base_url="https://attacker.invalid/webhook",
                webhook_token="secret", ledger=self.runtime.ledger,
            )

    def test_private_literal_image_url_is_rejected(self):
        with self.assertRaises(self.module.ValidationError):
            self.runtime.preview(
                channel="threads", operation="publish",
                payload={"content": "hello", "image_urls": ["https://127.0.0.1/admin"]},
                topic="demo", note_path="note.md",
                session_id=self.SESSION_ID, turn_id=self.PREVIEW_TURN, user_message_id=self.PREVIEW_MESSAGE_ID,
            )

    def test_allowlisted_image_hostname_resolving_private_is_rejected(self):
        private_answer = [
            (2, 1, 6, "", ("169.254.169.254", 443)),
        ]
        with mock.patch.object(self.module.socket, "getaddrinfo", return_value=private_answer):
            with self.assertRaises(self.module.ValidationError):
                self.module._validate_image_url(
                    "https://cdn.example.com/latest/meta-data",
                    allowed_hosts={"cdn.example.com"},
                )

    def test_empty_ledger_representation_requires_reconciliation(self):
        FakeApiHandler.empty_ledger_write = True
        result = self.approve_and_dispatch(self.preview_threads())
        self.assertEqual("reconciliation_required", result["status"])

    def test_incomplete_publisher_success_requires_reconciliation(self):
        FakeApiHandler.incomplete_webhook_response = True
        result = self.approve_and_dispatch(self.preview_threads())
        self.assertEqual("reconciliation_required", result["status"])
        self.assertFalse(any(r[1] == "/rest/v1/published_posts" for r in FakeApiHandler.requests))

    def test_delete_resolves_post_and_updates_exactly_one_active_row(self):
        plan = self.runtime.preview(
            channel="threads", operation="delete", payload={}, topic="demo", note_path="",
            session_id=self.SESSION_ID, turn_id=self.PREVIEW_TURN, user_message_id=self.PREVIEW_MESSAGE_ID,
        )
        result = self.approve_and_dispatch(plan, "내려줘")
        self.assertEqual("completed", result["status"])
        patches = [r for r in FakeApiHandler.requests if r[0] == "PATCH"]
        self.assertEqual(1, len(patches))
        self.assertIn("deleted_at=is.null", patches[0][4])
        self.assertIn("post_id=eq.existing-post", patches[0][4])
        self.assertIn("id=eq.41", patches[0][4])

    def test_delete_rejects_duplicate_active_rows_before_mutation(self):
        FakeApiHandler.duplicate_active_posts = True
        with self.assertRaises(self.module.ValidationError):
            self.runtime.preview(
                channel="threads", operation="delete", payload={}, topic="demo", note_path="",
                session_id=self.SESSION_ID, turn_id=self.PREVIEW_TURN, user_message_id=self.PREVIEW_MESSAGE_ID,
            )
        self.assertFalse(any(request[0] in {"PATCH", "POST"} for request in FakeApiHandler.requests))

    def test_external_success_and_ledger_failure_requires_reconciliation(self):
        FakeApiHandler.fail_ledger_insert = True
        result = self.approve_and_dispatch(self.preview_threads())
        self.assertEqual("reconciliation_required", result["status"])
        self.assertNotIn("service-secret", json.dumps(result))

    def test_unknown_fields_and_operations_are_rejected(self):
        with self.assertRaises(self.module.ValidationError):
            self.runtime.preview(
                channel="threads", operation="publish",
                payload={"content": "hello", "endpoint": "https://evil.test"}, topic="demo", note_path="note.md",
                session_id=self.SESSION_ID, turn_id=self.PREVIEW_TURN, user_message_id=self.PREVIEW_MESSAGE_ID,
            )
        with self.assertRaises(self.module.ValidationError):
            self.runtime.preview(
                channel="instagram", operation="delete", payload={}, topic="demo", note_path="note.md",
                session_id=self.SESSION_ID, turn_id=self.PREVIEW_TURN, user_message_id=self.PREVIEW_MESSAGE_ID,
            )

    def test_receipt_claim_allows_exactly_one_concurrent_winner(self):
        plan = self.preview_threads()

        def claim_once():
            try:
                self.runtime.store.claim(plan["receipt_id"], "planned", "approved")
                return "won"
            except self.module.ReceiptError:
                return "lost"

        with ThreadPoolExecutor(max_workers=8) as pool:
            outcomes = list(pool.map(lambda _index: claim_once(), range(8)))
        self.assertEqual(1, outcomes.count("won"))
        self.assertEqual(7, outcomes.count("lost"))


if __name__ == "__main__":
    unittest.main()
