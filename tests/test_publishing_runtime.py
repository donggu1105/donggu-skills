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
    publisher_failure_with_identifiers = False
    pre_mutation_failure_with_url = False
    publisher_uncertain_without_identifiers = False
    publisher_uncertain_delete = False
    drop_webhook_connection = False
    forced_update_response: object = None
    active_posts_enabled = False
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
            rows = [dict(type(self).active_post)] if type(self).active_posts_enabled else []
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
            if type(self).drop_webhook_connection:
                self.close_connection = True
                return
            if type(self).redirect_webhook:
                self._send(302, {}, location="/redirect-target")
            elif type(self).pre_mutation_failure_with_url:
                self._send(200, {
                    "success": False,
                    "url": "https://threads.test/editor/preview",
                    "post_id": "thread-draft",
                    "error": "validation_failed_before_submit",
                })
            elif type(self).publisher_failure_with_identifiers:
                self._send(200, {
                    "success": False,
                    "url": "https://threads.test/post/1",
                    "post_id": "thread-1",
                    "error": "published_tags_mismatch: expected tags were not visible",
                    "external_mutation_possible": True,
                })
            elif type(self).publisher_uncertain_without_identifiers:
                self._send(200, {
                    "success": False,
                    "url": None,
                    "post_id": None,
                    "error": "published_identifiers_missing_after_submit",
                    "external_mutation_possible": True,
                })
            elif type(self).incomplete_webhook_response:
                self._send(200, {"success": True})
            else:
                self._send(200, {"success": True, "url": "https://threads.test/post/1", "post_id": "thread-1"})
            return
        if parsed.path == "/webhook/sns-pub-maily":
            self._send(200, {"success": True, "url": "https://maily.test/post/1", "post_id": None})
            return
        if parsed.path == "/publish-sync/tistory":
            if type(self).publisher_uncertain_without_identifiers:
                self._send(200, {
                    "success": False,
                    "url": None,
                    "post_id": None,
                    "error": "published_identifiers_missing_after_submit",
                    "external_mutation_possible": True,
                })
            else:
                self._send(200, {
                    "success": True,
                    "url": "https://donggu1105.tistory.com/307",
                    "post_id": "307",
                })
            return
        if parsed.path == "/update-sync/tistory":
            response = type(self).forced_update_response or {
                "success": True,
                "url": "https://donggu1105.tistory.com/306",
                "post_id": "306",
            }
            self._send(200, response)
            return
        if parsed.path == "/unpublish-sync/tistory":
            self._send(200, {"success": True})
            return
        if parsed.path == "/publish-sync/maily":
            self._send(200, {
                "success": True,
                "url": "https://maily.so/example/posts/post123",
                "post_id": None,
            })
            return
        if parsed.path == "/webhook/sns-update-tistory":
            response = type(self).forced_update_response or {
                "success": True,
                "url": "https://donggu1105.tistory.com/306",
                "post_id": "306",
            }
            self._send(200, response)
            return
        if parsed.path == "/webhook/sns-del-threads":
            if type(self).publisher_uncertain_delete:
                self._send(200, {
                    "success": False,
                    "error": "publisher response lost after delete",
                    "external_mutation_possible": True,
                })
            else:
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
        FakeApiHandler.publisher_failure_with_identifiers = False
        FakeApiHandler.pre_mutation_failure_with_url = False
        FakeApiHandler.publisher_uncertain_without_identifiers = False
        FakeApiHandler.publisher_uncertain_delete = False
        FakeApiHandler.drop_webhook_connection = False
        FakeApiHandler.forced_update_response = None
        FakeApiHandler.active_posts_enabled = False
        FakeApiHandler.active_post = {
            "id": 41,
            "post_id": "existing-post",
            "url": "https://example.test/existing",
            "note_path": "note.md",
        }
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
            note_path="40_Channel_Packs/Threads/Threads - demo.md",
            session_id=self.SESSION_ID,
            turn_id=self.PREVIEW_TURN, user_message_id=self.PREVIEW_MESSAGE_ID,
        )

    def direct_runtime(self):
        return self.module.PublishingRuntime(
            receipt_root=Path(self.tmp.name) / "direct-receipts",
            webhook_base_url=f"{self.base}/webhook",
            webhook_token="webhook-secret",
            publisher_api_base_url=self.base,
            publisher_api_token="publisher-secret",
            ledger=self.runtime.ledger,
            receipt_ttl_seconds=900,
            allow_test_origins=True,
        )

    def preview_tistory_update(
        self, *, preview_turn=None, preview_message_id=None,
    ):
        FakeApiHandler.active_posts_enabled = True
        FakeApiHandler.active_post = {
            "id": 28,
            "post_id": "306",
            "url": "https://donggu1105.tistory.com/306",
            "note_path": "Blog/demo.md",
        }
        return self.runtime.preview(
            channel="tistory",
            operation="update",
            payload={
                "title": "Demo",
                "content": (
                    "![](https://img.test/hero.png)\n"
                    "## One\nText\n![](https://img.test/one.png)\n"
                    "## Two\nText\n![](https://img.test/two.png)"
                ),
                "tags": ["FDE", "고객인터뷰", "현장관찰", "업무분석"],
                "cover_image": "https://img.test/hero.png",
            },
            topic="demo",
            note_path="Blog/demo.md",
            session_id=self.SESSION_ID,
            turn_id=preview_turn or self.PREVIEW_TURN,
            user_message_id=(
                self.PREVIEW_MESSAGE_ID
                if preview_message_id is None else preview_message_id
            ),
        )

    def approve_and_dispatch(self, plan, text=None):
        if text is None:
            text = {
                "publish": "올려줘",
                "update": "업데이트 적용해줘",
                "delete": "삭제해줘",
            }[plan["operation"]]
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

    def test_receipt_write_fsyncs_file_and_directory(self):
        real_fsync = os.fsync
        synced_modes = []

        def tracked_fsync(fd):
            synced_modes.append(os.fstat(fd).st_mode)
            return real_fsync(fd)

        with mock.patch.object(self.module.os, "fsync", side_effect=tracked_fsync):
            self.preview_tistory_update(
                preview_turn="durable-preview", preview_message_id=40,
            )
        self.assertTrue(any(stat.S_ISREG(mode) for mode in synced_modes))
        self.assertTrue(any(stat.S_ISDIR(mode) for mode in synced_modes))

    def test_receipt_store_fails_closed_when_private_mode_cannot_be_set(self):
        root = Path(self.tmp.name) / "permissive-receipts"
        root.mkdir(mode=0o777)
        os.chmod(root, 0o777)
        with mock.patch.object(
            self.module.os, "chmod", side_effect=PermissionError("denied"),
        ):
            with self.assertRaises(self.module.ReceiptError):
                self.module.ReceiptStore(root)

    def test_tistory_markdown_images_are_counted_with_section_placements(self):
        content = (
            "![](https://img.test/hero.png)\n\n"
            "## First section\n\nBody\n\n"
            "![first](https://img.test/first.png)\n\n"
            "## Video\n\n"
            "[![](https://img.test/thumb.png)](https://video.test/watch)"
        )
        result = self.runtime.preview(
            channel="tistory",
            operation="publish",
            payload={
                "title": "Title",
                "content": content,
                "tags": ["FDE", "고객인터뷰", "도메인지식"],
                "cover_image": "https://img.test/hero.png",
            },
            topic="inline-images",
            note_path="40_Channel_Packs/Blog/Blog - inline-images.md",
            session_id=self.SESSION_ID,
            turn_id=self.PREVIEW_TURN,
            user_message_id=self.PREVIEW_MESSAGE_ID,
        )
        self.assertEqual(3, result["preview"]["image_count"])
        self.assertEqual(
            ["lead", "First section", "Video"],
            [item["section"] for item in result["preview"]["inline_images"]],
        )
        self.assertEqual("first", result["preview"]["inline_images"][1]["alt"])

    def test_tistory_markdown_images_reject_private_urls(self):
        with self.assertRaises(self.module.ValidationError):
            self.runtime.preview(
                channel="tistory",
                operation="publish",
                payload={
                    "title": "Title",
                    "content": "![](http://127.0.0.1/private.png)",
                    "tags": ["FDE", "고객인터뷰", "도메인지식"],
                },
                topic="private-inline-image",
                note_path="40_Channel_Packs/Blog/Blog - private-inline-image.md",
                session_id=self.SESSION_ID,
                turn_id=self.PREVIEW_TURN,
                user_message_id=self.PREVIEW_MESSAGE_ID,
            )

    def test_tistory_image_parser_accepts_title_and_ignores_fenced_code(self):
        content = (
            "```markdown\n"
            "![](http://127.0.0.1/not-rendered.png)\n"
            "```\n\n"
            "![hero](https://img.test/hero.png \"public title\")"
        )
        result = self.runtime.preview(
            channel="tistory",
            operation="publish",
            payload={
                "title": "Title",
                "content": content,
                "tags": ["FDE", "고객인터뷰", "도메인지식"],
                "cover_image": "https://img.test/hero.png",
            },
            topic="title-image",
            note_path="40_Channel_Packs/Blog/Blog - title-image.md",
            session_id=self.SESSION_ID,
            turn_id=self.PREVIEW_TURN,
            user_message_id=self.PREVIEW_MESSAGE_ID,
        )
        self.assertEqual(1, result["preview"]["image_count"])
        self.assertEqual("https://img.test/hero.png", result["preview"]["inline_images"][0]["url"])

    def test_tistory_rejects_raw_html_and_reference_images(self):
        unsafe_bodies = (
            "![](https://img.test/hero.png)\n<img src=\"http://127.0.0.1/private.png\">",
            "![](https://img.test/hero.png)\n![private][asset]\n[asset]: http://127.0.0.1/private.png",
            "![](https://img.test/hero.png)\n<div style=\"background:url(http://127.0.0.1/private.png)\"></div>",
            "![](https://img.test/hero.png)\n<img\n src=\"http://127.0.0.1/private.png\">",
            "![](https://img.test/hero.png)\n<img\n    src=\"http://127.0.0.1/private.png\">",
            "![](https://img.test/hero.png)\n\t```html\n<iframe src=\"http://127.0.0.1/private\"></iframe>\n\t```",
            "![](https://img.test/hero.png)\n```html`bad\n<iframe src=\"http://127.0.0.1/private\"></iframe>\n```",
            "![](https://img.test/hero.png)\n\f```html\n<iframe src=\"http://127.0.0.1/private\"></iframe>\n\f```",
            "![](https://img.test/hero.png)\n~~~html bad\n<iframe src=\"http://127.0.0.1/private\"></iframe>\n~~~",
            "![](https://img.test/hero.png)\n ```html\n<iframe src=\"http://127.0.0.1/private\"></iframe>\n ```",
            "![](https://img.test/hero.png)\n```html\n<iframe src=\"http://127.0.0.1/private\"></iframe>\n````",
            "![](https://img.test/hero.png)\n<iframe/src=\"http://127.0.0.1/private\">",
            "![](https://img.test/hero.png)\n<link/href=\"http://127.0.0.1/private.css\">",
            "![](https://img.test/hero.png)\n<object/data=\"http://127.0.0.1/private\">",
            "![](https://img.test/hero.png)\n<embed/src=\"http://127.0.0.1/private\">",
            "![](https://img.test/hero.png)\n<video/poster=\"http://127.0.0.1/private.jpg\">",
            "![](https://img.test/hero.png)\n<audio/src=\"http://127.0.0.1/private.mp3\">",
        )
        for content in unsafe_bodies:
            with self.subTest(content=content), self.assertRaises(self.module.ValidationError):
                self.runtime.preview(
                    channel="tistory",
                    operation="publish",
                    payload={
                        "title": "Title",
                        "content": content,
                        "tags": ["FDE", "고객인터뷰", "도메인지식"],
                        "cover_image": "https://img.test/hero.png",
                    },
                    topic="unsafe-image",
                    note_path="40_Channel_Packs/Blog/Blog - unsafe-image.md",
                    session_id=self.SESSION_ID,
                    turn_id=self.PREVIEW_TURN,
                    user_message_id=self.PREVIEW_MESSAGE_ID,
                )

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

    def test_bare_publish_imperative_is_explicit_approval(self):
        plan = self.preview_threads()
        approved = self.runtime.approve(
            plan["receipt_id"], approval_text="발행해",
            session_id=self.SESSION_ID, turn_id=self.APPROVAL_TURN,
            user_message_id=self.APPROVAL_MESSAGE_ID,
        )
        self.assertEqual("approved", approved["status"])

    def test_approval_must_name_the_receipt_operation(self):
        cases = {
            "publish": ("올려줘", "업데이트 적용해줘", "삭제해줘"),
            "update": ("업데이트 적용해줘", "올려줘", "삭제해줘"),
            "delete": ("삭제해줘", "올려줘", "업데이트 적용해줘"),
        }
        for operation, (accepted, *rejected) in cases.items():
            with self.subTest(operation=operation, text=accepted):
                self.assertEqual(
                    accepted,
                    self.module._require_operation_approval(accepted, operation),
                )
            for text in rejected:
                with self.subTest(operation=operation, text=text), self.assertRaises(
                    self.module.ApprovalError,
                ):
                    self.module._require_operation_approval(text, operation)

        plan = self.preview_threads()
        with self.assertRaises(self.module.ApprovalError):
            self.runtime.approve(
                plan["receipt_id"], approval_text="삭제해줘",
                session_id=self.SESSION_ID, turn_id=self.APPROVAL_TURN,
                user_message_id=self.APPROVAL_MESSAGE_ID,
            )
        self.assertEqual(
            "planned", self.runtime.receipt_status(plan["receipt_id"])["state"],
        )

    def test_approval_rejects_questions_and_negated_or_deferred_intent(self):
        rejected = (
            "발행해 볼까?",
            "발행해 보지 마",
            "발행해 두지 마",
            "발행해도 될까?",
            "일단 보류하고 나중에 발행해",
            "검토 후 발행해",
            "문제 없으면 발행해",
            "내일 발행해",
            "아직 확신은 없지만 발행해",
            "발행해도 될까? 승인",
            "발행하지 않아 승인",
            "발행하면 안 됩니다. 승인합니다",
            "발행하는 게 맞나요 승인",
            "모레 발행해",
            "일주일 뒤 발행해",
            "시간 되면 발행해",
            "아마 발행해",
            "지금은 곤란하지만 승인",
        )
        for text in rejected:
            with self.subTest(text=text), self.assertRaises(self.module.ApprovalError):
                self.module._require_explicit_approval(text)
        self.assertEqual(
            "블로그 업데이트 적용해줘",
            self.module._require_explicit_approval("블로그 업데이트 적용해줘"),
        )

    def test_image_url_rejects_browser_path_normalization_ambiguity(self):
        for path in (
            "/a/../private.png",
            "/a/%2e%2e/private.png",
            "/a/.%2E/private.png",
            r"/a\..\private.png",
            "/a/%5c..%5cprivate.png",
        ):
            with self.subTest(path=path), self.assertRaisesRegex(
                self.module.ValidationError, "browser-normalized path",
            ):
                self.module._validate_image_url(
                    f"https://img.test{path}",
                    allowed_hosts={"img.test"},
                    resolve_dns=False,
                )

        for unsafe in (
            " https://img.test/image.png",
            "https://img.test/image.png ",
        ):
            with self.subTest(unsafe=unsafe), self.assertRaisesRegex(
                self.module.ValidationError, "browser-normalized path",
            ):
                self.module._validate_image_url(
                    unsafe,
                    allowed_hosts={"img.test"},
                    resolve_dns=False,
                )

    def test_maily_confirmation_rejects_questions_and_uncertainty(self):
        for text in (
            "메일 최종 발송 승인해도 될까?",
            "메일 최종 발송 승인할지 모르겠어",
            "내일 메일 최종 발송 승인",
            "메일 최종 발송하지 않아 승인",
            "아마 메일 최종 발송 승인",
            "모레 메일 최종 발송 승인",
        ):
            with self.subTest(text=text), self.assertRaises(self.module.ApprovalError):
                self.module._require_maily_confirmation(text)
        self.assertEqual(
            "메일 최종 발송 확인",
            self.module._require_maily_confirmation("메일 최종 발송 확인"),
        )

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
            topic="demo-2", note_path="40_Channel_Packs/Threads/Threads - demo-2.md",
            session_id=self.SESSION_ID, turn_id=self.PREVIEW_TURN,
            user_message_id=self.PREVIEW_MESSAGE_ID,
        )
        plans = [first, second]

        def approve(index):
            try:
                self.runtime.approve(
                    plans[index]["receipt_id"], approval_text="발행 승인",
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

    def test_authoritative_message_is_revalidated_before_authorization_claim(self):
        plan = self.preview_threads()
        calls = []

        def reject_stale_message():
            calls.append("validated")
            raise self.module.ApprovalError("trusted user message changed before claim")

        with self.assertRaises(self.module.ApprovalError):
            self.runtime.approve(
                plan["receipt_id"], approval_text="올려줘",
                session_id=self.SESSION_ID, turn_id=self.APPROVAL_TURN,
                user_message_id=self.APPROVAL_MESSAGE_ID,
                authoritative_message_validator=reject_stale_message,
            )
        self.assertEqual(["validated"], calls)
        self.assertEqual("planned", self.runtime.receipt_status(plan["receipt_id"])["state"])
        self.assertEqual([], list((Path(self.tmp.name) / "receipts").glob("authorization-*.claim")))

    def test_authoritative_executor_wraps_the_durable_authorization_claim(self):
        plan = self.preview_threads()
        events = []

        def execute_while_latest_message_is_locked(action):
            events.append("lock-held-before")
            result = action()
            events.append("lock-held-after")
            return result

        result = self.runtime.approve(
            plan["receipt_id"], approval_text="올려줘",
            session_id=self.SESSION_ID, turn_id=self.APPROVAL_TURN,
            user_message_id=self.APPROVAL_MESSAGE_ID,
            authoritative_claim_executor=execute_while_latest_message_is_locked,
        )
        self.assertEqual("approved", result["status"])
        self.assertEqual(["lock-held-before", "lock-held-after"], events)
        self.assertEqual(1, len(list(
            (Path(self.tmp.name) / "receipts").glob("authorization-*.claim")
        )))

    def test_authorization_claim_is_durable_across_runtime_instances(self):
        other_runtime = self.module.PublishingRuntime(
            receipt_root=Path(self.tmp.name) / "receipts",
            webhook_base_url=f"{self.base}/webhook",
            webhook_token="webhook-secret",
            ledger=self.runtime.ledger,
            receipt_ttl_seconds=900,
            allow_test_origins=True,
        )
        runtimes = (self.runtime, other_runtime)
        plans = []
        for index, runtime in enumerate(runtimes, 1):
            plans.append(runtime.preview(
                channel="threads", operation="publish",
                payload={"content": f"body-{index}"},
                topic=f"cross-runtime-{index}", note_path=f"note-{index}.md",
                session_id=self.SESSION_ID, turn_id=self.PREVIEW_TURN,
                user_message_id=self.PREVIEW_MESSAGE_ID,
            ))

        def approve(index):
            try:
                runtimes[index].approve(
                    plans[index]["receipt_id"], approval_text="발행 승인",
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
        states = [
            runtimes[index].receipt_status(plans[index]["receipt_id"])["state"]
            for index in (0, 1)
        ]
        self.assertEqual(["approved", "planned"], sorted(states))
        claims = list((Path(self.tmp.name) / "receipts").glob("authorization-*.claim"))
        self.assertEqual(1, len(claims))
        self.assertEqual(0o600, stat.S_IMODE(claims[0].stat().st_mode))

    def test_one_persisted_authorization_cannot_confirm_multiple_maily_receipts(self):
        plans = []
        for index in (1, 2):
            plan = self.runtime.preview(
                channel="maily", operation="publish",
                payload={"title": f"Title {index}", "subtitle": "Subtitle", "content": "Body", "dry_run": False},
                topic=f"mail-{index}", note_path=f"40_Channel_Packs/Maily/Maily - mail-{index}.md",
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
            topic="mail", note_path="40_Channel_Packs/Maily/Maily - mail.md",
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
            topic="mail-draft", note_path="40_Channel_Packs/Maily/Maily - mail.md",
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

    def test_allowlisted_image_hostname_resolving_multicast_is_rejected(self):
        for address in ("224.0.0.1", "ff0e::1"):
            multicast_answer = [(2, 1, 6, "", (address, 443))]
            with self.subTest(address=address), mock.patch.object(
                self.module.socket, "getaddrinfo", return_value=multicast_answer,
            ):
                with self.assertRaisesRegex(
                    self.module.ValidationError, "public unicast",
                ):
                    self.module._validate_image_url(
                        "https://cdn.example.com/image.png",
                        allowed_hosts={"cdn.example.com"},
                    )

    def test_multicast_image_literal_is_rejected_even_if_allowlisted(self):
        for url, host in (
            ("https://224.0.0.1/image.png", "224.0.0.1"),
            ("https://[ff0e::1]/image.png", "ff0e::1"),
        ):
            with self.subTest(url=url), self.assertRaisesRegex(
                self.module.ValidationError, "public unicast",
            ):
                self.module._validate_image_url(
                    url, allowed_hosts={host}, resolve_dns=False,
                )

    def test_empty_ledger_representation_requires_reconciliation(self):
        FakeApiHandler.empty_ledger_write = True
        result = self.approve_and_dispatch(self.preview_threads())
        self.assertEqual("reconciliation_required", result["status"])

    def test_incomplete_publisher_success_requires_reconciliation_without_ledger_marker(self):
        FakeApiHandler.incomplete_webhook_response = True
        result = self.approve_and_dispatch(self.preview_threads())
        self.assertEqual("reconciliation_required", result["status"])
        inserts = [
            r for r in FakeApiHandler.requests
            if r[0] == "POST" and r[1] == "/rest/v1/published_posts"
        ]
        self.assertEqual([], inserts)

    def test_update_rejects_publisher_target_mismatch(self):
        FakeApiHandler.forced_update_response = {
            "success": True,
            "url": "https://donggu1105.tistory.com/999",
            "post_id": "999",
        }
        result = self.approve_and_dispatch(self.preview_tistory_update())
        self.assertEqual("reconciliation_required", result["status"])
        self.assertEqual("306", result["expected_post_id"])
        self.assertEqual("999", result["post_id"])
        self.assertFalse(any(
            request[0] == "POST" and request[1] == "/rest/v1/published_posts"
            for request in FakeApiHandler.requests
        ))

    def test_update_target_drift_is_blocked_before_webhook(self):
        plan = self.preview_tistory_update()
        approved = self.runtime.approve(
            plan["receipt_id"],
            approval_text="업데이트 적용해줘",
            session_id=self.SESSION_ID,
            turn_id=self.APPROVAL_TURN,
            user_message_id=self.APPROVAL_MESSAGE_ID,
        )
        self.assertEqual("approved", approved["status"])
        FakeApiHandler.active_post = {
            **FakeApiHandler.active_post,
            "post_id": "307",
            "url": "https://donggu1105.tistory.com/307",
        }
        result = self.runtime.dispatch(plan["receipt_id"], session_id=self.SESSION_ID)
        self.assertEqual("failed", result["status"])
        FakeApiHandler.active_post = {
            **FakeApiHandler.active_post,
            "post_id": "306",
            "url": "https://donggu1105.tistory.com/306",
        }
        with self.assertRaises(self.module.ReceiptError):
            self.runtime.dispatch(plan["receipt_id"], session_id=self.SESSION_ID)
        self.assertFalse(any(
            request[1] == "/webhook/sns-update-tistory"
            for request in FakeApiHandler.requests
        ))

    def test_update_preview_rejects_authoritative_ledger_without_valid_url(self):
        FakeApiHandler.active_posts_enabled = True
        FakeApiHandler.active_post = {
            "id": 28,
            "post_id": "306",
            "url": None,
            "note_path": "Blog/demo.md",
        }
        with self.assertRaises(self.module.ValidationError):
            self.runtime.preview(
                channel="tistory",
                operation="update",
                payload={
                    "title": "Demo",
                    "content": (
                        "![](https://img.test/hero.png)\n"
                        "## One\n![](https://img.test/one.png)\n"
                        "## Two\n![](https://img.test/two.png)"
                    ),
                    "tags": ["FDE", "고객인터뷰", "업무분석"],
                    "cover_image": "https://img.test/hero.png",
                },
                topic="demo",
                note_path="Blog/demo.md",
                session_id=self.SESSION_ID,
                turn_id=self.PREVIEW_TURN,
                user_message_id=self.PREVIEW_MESSAGE_ID,
            )
        self.assertFalse(any(
            request[1] == "/webhook/sns-update-tistory"
            for request in FakeApiHandler.requests
        ))

    def test_update_target_is_rechecked_after_receipt_claim(self):
        plan = self.preview_tistory_update()
        approved = self.runtime.approve(
            plan["receipt_id"],
            approval_text="업데이트 적용해줘",
            session_id=self.SESSION_ID,
            turn_id=self.APPROVAL_TURN,
            user_message_id=self.APPROVAL_MESSAGE_ID,
        )
        self.assertEqual("approved", approved["status"])
        original_verify = self.runtime._verify_current_target
        calls = []

        def verify_with_claim_race(receipt):
            calls.append(receipt.get("state"))
            if len(calls) == 2:
                raise self.module.ValidationError("target changed after claim")
            return original_verify(receipt)

        self.runtime._verify_current_target = verify_with_claim_race
        result = self.runtime.dispatch(plan["receipt_id"], session_id=self.SESSION_ID)
        self.assertEqual(["approved", "dispatching"], calls)
        self.assertEqual("failed", result["status"])
        self.assertIn("target changed", result["error"])
        self.assertFalse(any(
            request[1] == "/webhook/sns-update-tistory"
            for request in FakeApiHandler.requests
        ))

    def test_failure_identifiers_without_mutation_signal_requires_reconciliation(self):
        FakeApiHandler.pre_mutation_failure_with_url = True
        plan = self.preview_threads()
        result = self.approve_and_dispatch(plan)
        self.assertEqual("reconciliation_required", result["status"])
        self.assertIn("validation_failed_before_submit", result["error"])
        self.assertEqual("https://threads.test/editor/preview", result["url"])
        self.assertEqual("thread-draft", result["post_id"])
        self.assertFalse(any(
            request[0] == "POST" and request[1] == "/rest/v1/published_posts"
            for request in FakeApiHandler.requests
        ))

    def test_non_object_publisher_response_after_update_requires_reconciliation(self):
        FakeApiHandler.forced_update_response = ["unexpected"]
        result = self.approve_and_dispatch(self.preview_tistory_update())
        self.assertEqual("reconciliation_required", result["status"])
        self.assertEqual("306", result["post_id"])
        self.assertEqual("https://donggu1105.tistory.com/306", result["url"])

    def test_update_failure_preserves_valid_post_id_when_url_is_invalid(self):
        FakeApiHandler.forced_update_response = {
            "success": False,
            "error": "verification failed",
            "url": "not-a-url",
            "post_id": "999",
            "external_mutation_possible": True,
        }
        result = self.approve_and_dispatch(self.preview_tistory_update())
        self.assertEqual("reconciliation_required", result["status"])
        self.assertEqual("306", result["post_id"])
        self.assertEqual("999", result["observed_post_id"])

    def test_reconciliation_persists_worker_job_id(self):
        job_id = "sns-update:tistory:receipt123"
        FakeApiHandler.forced_update_response = {
            "success": False,
            "error": "worker result timed out",
            "job_id": job_id,
            "external_mutation_possible": True,
            "mutation_state": "reconciliation_required",
            "reconciliation_required": True,
        }
        plan = self.preview_tistory_update()
        result = self.approve_and_dispatch(plan)

        self.assertEqual("reconciliation_required", result["status"])
        self.assertEqual(job_id, result["job_id"])
        persisted = self.runtime.receipt_status(plan["receipt_id"])
        self.assertEqual(job_id, persisted["result"]["job_id"])

    def test_reconciliation_blocks_fresh_receipt_even_after_runtime_restart(self):
        FakeApiHandler.forced_update_response = ["unexpected"]
        result = self.approve_and_dispatch(self.preview_tistory_update())
        self.assertEqual("reconciliation_required", result["status"])

        restarted = self.module.PublishingRuntime(
            receipt_root=self.runtime.store.root,
            webhook_base_url=self.base + "/webhook",
            webhook_token="hook-secret",
            ledger=self.runtime.ledger,
            allow_test_origins=True,
        )
        with self.assertRaisesRegex(
            self.module.ReceiptError, "unresolved reconciliation",
        ):
            restarted.preview(
                channel="tistory",
                operation="update",
                payload={
                    "title": "Demo",
                    "content": (
                        "![](https://img.test/hero.png)\n"
                        "## One\n![](https://img.test/one.png)\n"
                        "## Two\n![](https://img.test/two.png)"
                    ),
                    "tags": ["FDE", "고객인터뷰", "업무분석"],
                    "cover_image": "https://img.test/hero.png",
                },
                topic="demo",
                note_path="Blog/demo.md",
                session_id=self.SESSION_ID,
                turn_id="restart-preview-turn",
                user_message_id=self.APPROVAL_MESSAGE_ID + 10,
            )
        self.assertFalse(any(
            request[0] == "POST" and request[1] == "/rest/v1/published_posts"
            for request in FakeApiHandler.requests
        ))

    def test_corrupt_receipt_store_fails_closed_for_new_mutation(self):
        plan = self.preview_tistory_update()
        receipt_path = self.runtime.store.root / f"{plan['receipt_id']}.json"
        receipt_path.write_text("{not-json", encoding="utf-8")
        os.chmod(receipt_path, 0o600)

        restarted = self.module.PublishingRuntime(
            receipt_root=self.runtime.store.root,
            webhook_base_url=self.base + "/webhook",
            webhook_token="hook-secret",
            ledger=self.runtime.ledger,
            allow_test_origins=True,
        )
        with self.assertRaisesRegex(
            self.module.ReceiptError, "invalid receipt file",
        ):
            restarted.preview(
                channel="tistory",
                operation="update",
                payload={
                    "title": "Demo",
                    "content": (
                        "![](https://img.test/hero.png)\n"
                        "## One\n![](https://img.test/one.png)\n"
                        "## Two\n![](https://img.test/two.png)"
                    ),
                    "tags": ["FDE", "고객인터뷰", "업무분석"],
                    "cover_image": "https://img.test/hero.png",
                },
                topic="demo",
                note_path="Blog/demo.md",
                session_id=self.SESSION_ID,
                turn_id="restart-corrupt-preview",
                user_message_id=self.APPROVAL_MESSAGE_ID + 30,
            )

    def test_dispatching_receipt_blocks_fresh_preview_after_restart(self):
        plan = self.preview_tistory_update()
        self.runtime.approve(
            plan["receipt_id"], approval_text="업데이트 적용해줘",
            session_id=self.SESSION_ID, turn_id=self.APPROVAL_TURN,
            user_message_id=self.APPROVAL_MESSAGE_ID,
        )
        self.runtime.store.claim(
            plan["receipt_id"], "approved", "dispatching",
        )

        restarted = self.module.PublishingRuntime(
            receipt_root=self.runtime.store.root,
            webhook_base_url=self.base + "/webhook",
            webhook_token="hook-secret",
            ledger=self.runtime.ledger,
            allow_test_origins=True,
        )
        with self.assertRaisesRegex(
            self.module.ReceiptError, "unresolved mutation",
        ):
            restarted.preview(
                channel="tistory",
                operation="update",
                payload={
                    "title": "Demo",
                    "content": (
                        "![](https://img.test/hero.png)\n"
                        "## One\n![](https://img.test/one.png)\n"
                        "## Two\n![](https://img.test/two.png)"
                    ),
                    "tags": ["FDE", "고객인터뷰", "업무분석"],
                    "cover_image": "https://img.test/hero.png",
                },
                topic="demo",
                note_path="Blog/demo.md",
                session_id=self.SESSION_ID,
                turn_id="restart-dispatching-preview",
                user_message_id=self.APPROVAL_MESSAGE_ID + 20,
            )

    def test_existing_approved_receipt_is_blocked_after_peer_reconciliation(self):
        first = self.preview_tistory_update(
            preview_turn="first-preview", preview_message_id=10,
        )
        self.runtime.approve(
            first["receipt_id"], approval_text="업데이트 적용해줘",
            session_id=self.SESSION_ID, turn_id="first-approval",
            user_message_id=11,
        )
        second = self.preview_tistory_update(
            preview_turn="second-preview", preview_message_id=20,
        )
        self.runtime.approve(
            second["receipt_id"], approval_text="업데이트 적용해줘",
            session_id=self.SESSION_ID, turn_id="second-approval",
            user_message_id=21,
        )
        FakeApiHandler.forced_update_response = ["unexpected"]
        result = self.runtime.dispatch(
            second["receipt_id"], session_id=self.SESSION_ID,
        )
        self.assertEqual("reconciliation_required", result["status"])
        webhook_count = sum(
            request[1] == "/webhook/sns-update-tistory"
            for request in FakeApiHandler.requests
        )
        with self.assertRaisesRegex(
            self.module.ReceiptError, "unresolved reconciliation",
        ):
            self.runtime.dispatch(
                first["receipt_id"], session_id=self.SESSION_ID,
            )
        self.assertEqual(
            webhook_count,
            sum(
                request[1] == "/webhook/sns-update-tistory"
                for request in FakeApiHandler.requests
            ),
        )

    def test_explicit_mutation_failure_preserves_identifiers_without_ledger_marker(self):
        FakeApiHandler.publisher_failure_with_identifiers = True
        plan = self.preview_threads()
        result = self.approve_and_dispatch(plan)
        self.assertEqual("reconciliation_required", result["status"])
        self.assertEqual("https://threads.test/post/1", result["url"])
        self.assertEqual("thread-1", result["post_id"])
        self.assertIn("published_tags_mismatch", result["error"])
        inserts = [
            request for request in FakeApiHandler.requests
            if request[0] == "POST" and request[1] == "/rest/v1/published_posts"
        ]
        self.assertEqual([], inserts)
        stored = self.runtime.receipt_status(plan["receipt_id"])
        self.assertEqual("reconciliation_required", stored["state"])
        self.assertEqual("thread-1", stored["result"]["post_id"])

    def test_publish_dispatch_blocks_an_existing_active_ledger_post(self):
        FakeApiHandler.active_posts_enabled = True
        plan = self.preview_threads()
        result = self.approve_and_dispatch(plan)
        self.assertEqual("reconciliation_required", result["status"])
        self.assertEqual("existing-post", result["post_id"])
        self.assertEqual("https://example.test/existing", result["url"])
        self.assertIn("use update", result["error"])
        webhook_calls = [
            request for request in FakeApiHandler.requests
            if request[1] == "/webhook/sns-pub-threads"
        ]
        self.assertEqual([], webhook_calls)

    def test_transport_response_loss_requires_reconciliation_without_ledger_write(self):
        FakeApiHandler.drop_webhook_connection = True
        plan = self.preview_threads()
        result = self.approve_and_dispatch(plan)
        self.assertEqual("reconciliation_required", result["status"])
        self.assertTrue(result["error"])
        self.assertFalse(any(
            request[0] == "POST" and request[1] == "/rest/v1/published_posts"
            for request in FakeApiHandler.requests
        ))
        self.assertEqual(
            "reconciliation_required",
            self.runtime.receipt_status(plan["receipt_id"])["state"],
        )

    def test_uncertain_publish_without_identifiers_uses_receipt_only(self):
        FakeApiHandler.publisher_uncertain_without_identifiers = True
        result = self.approve_and_dispatch(self.preview_threads())
        self.assertEqual("reconciliation_required", result["status"])
        self.assertIsNone(result["url"])
        self.assertIsNone(result["post_id"])
        inserts = [
            request for request in FakeApiHandler.requests
            if request[0] == "POST" and request[1] == "/rest/v1/published_posts"
        ]
        self.assertEqual([], inserts)

    def test_publish_dispatch_blocks_an_active_reconciliation_marker(self):
        FakeApiHandler.active_posts_enabled = True
        FakeApiHandler.active_post = {
            "id": 42,
            "post_id": None,
            "url": None,
            "note_path": "note.md",
        }
        result = self.approve_and_dispatch(self.preview_threads())
        self.assertEqual("reconciliation_required", result["status"])
        self.assertIn("use update", result["error"])
        webhook_calls = [
            request for request in FakeApiHandler.requests
            if request[1] == "/webhook/sns-pub-threads"
        ]
        self.assertEqual([], webhook_calls)

    def test_delete_resolves_post_and_updates_exactly_one_active_row(self):
        FakeApiHandler.active_posts_enabled = True
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

    def test_uncertain_delete_requires_reconciliation_and_blocks_retry(self):
        FakeApiHandler.active_posts_enabled = True
        plan = self.runtime.preview(
            channel="threads", operation="delete", payload={}, topic="demo", note_path="",
            session_id=self.SESSION_ID, turn_id=self.PREVIEW_TURN,
            user_message_id=self.PREVIEW_MESSAGE_ID,
        )
        FakeApiHandler.publisher_uncertain_delete = True
        result = self.approve_and_dispatch(plan, "내려줘")
        self.assertEqual("reconciliation_required", result["status"])
        self.assertEqual("existing-post", result["post_id"])
        with self.assertRaisesRegex(self.module.ReceiptError, "reconciliation"):
            self.runtime.preview(
                channel="threads", operation="delete", payload={}, topic="demo", note_path="",
                session_id=self.SESSION_ID, turn_id="retry-preview", user_message_id=20,
            )
        delete_calls = [
            request for request in FakeApiHandler.requests
            if request[0] == "POST" and request[1] == "/webhook/sns-del-threads"
        ]
        self.assertEqual(1, len(delete_calls))
        self.assertEqual([], [request for request in FakeApiHandler.requests if request[0] == "PATCH"])

    def test_delete_rejects_duplicate_active_rows_before_mutation(self):
        FakeApiHandler.active_posts_enabled = True
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

    def test_threads_and_linkedin_text_contracts_are_enforced_before_receipt(self):
        invalid = (
            ("threads", "가" * 501, "500 characters"),
            ("threads", "본문 #AI", "hashtags"),
            ("threads", "본문#AI", "hashtags"),
            ("threads", "본문 #C#", "hashtags"),
            ("threads", "본문 #F#", "hashtags"),
            ("threads", "본문 https://example.com", "URLs"),
            ("threads", "본문 www.example.com", "URLs"),
            ("threads", "본문 ftp://example.com/file", "URLs"),
            ("threads", "본문 mailto:hello@example.com", "URLs"),
            ("linkedin", "본문 https://example.com", "URLs"),
        )
        for channel, content, message in invalid:
            with self.subTest(channel=channel, message=message):
                with self.assertRaisesRegex(self.module.ValidationError, message):
                    self.runtime.preview(
                        channel=channel,
                        operation="publish",
                        payload={"content": content},
                        topic="contract",
                        note_path="note.md",
                        session_id="stateless-contract",
                        turn_id="stateless-turn",
                        issue_receipt=True,
                        user_message_id=self.PREVIEW_MESSAGE_ID,
                    )

        self.assertEqual([], list((Path(self.tmp.name) / "receipts").glob("*.json")))

        valid = self.runtime.preview(
            channel="threads",
            operation="publish",
            payload={
                "content": (
                    "C#과 F#, README.md, Node.js, main.py, v2.alpha는 기술 표기이고 "
                    "module.config, System.IOUtils, my.appconfig, foo.designTokens, "
                    "example.company, ASP.NET, System.IO, ML.NET, foo.dev, Acme.com은 "
                    "식별자나 이름이고 donggu.site/post는 scheme 없는 문자열이며 "
                    "me@mail.example.com은 이메일이다"
                )
            },
            topic="contract",
            note_path="note.md",
            session_id="stateless-contract",
            turn_id="stateless-turn",
            issue_receipt=False,
        )
        self.assertEqual("preview", valid["status"])

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
    def test_tistory_tags_are_normalized_and_deduplicated(self):
        clean = self.module._validate_payload(
            "tistory",
            "publish",
            {
                "title": "demo",
                "content": "body",
                "tags": [" #FDE ", "fde", "고객인터뷰", "도메인지식"],
            },
            allowed_image_hosts={"img.test"},
            resolve_image_hosts=False,
        )
        self.assertEqual(["FDE", "고객인터뷰", "도메인지식"], clean["tags"])

    def test_tistory_tag_limit_is_applied_after_deduplication(self):
        clean = self.module._validate_payload(
            "tistory",
            "publish",
            {
                "title": "demo",
                "content": "body",
                "tags": [
                    "FDE", "fde", "#FDE", " FDE ",
                    "고객인터뷰", "고객인터뷰", "#고객인터뷰", " 고객인터뷰 ",
                    "도메인지식", "도메인지식", "#도메인지식",
                ],
            },
            allowed_image_hosts={"img.test"},
            resolve_image_hosts=False,
        )
        self.assertEqual(["FDE", "고객인터뷰", "도메인지식"], clean["tags"])

    def test_maily_tags_do_not_inherit_tistory_public_tag_restrictions(self):
        tags = ["newsletter/editorial", "x" * 31]
        clean = self.module._validate_payload(
            "maily",
            "publish",
            {
                "title": "demo",
                "subtitle": "subtitle",
                "content": "body",
                "tags": tags,
                "dry_run": True,
            },
            allowed_image_hosts={"img.test"},
            resolve_image_hosts=False,
        )
        self.assertEqual(tags, clean["tags"])

    def test_tistory_tags_reject_internal_namespaces_and_platform_overflow(self):
        for tags in (
            ["FDE", "고객인터뷰", "채널/Blog"],
            [f"tag{i}" for i in range(11)],
        ):
            with self.subTest(tags=tags), self.assertRaises(self.module.ValidationError):
                self.module._validate_payload(
                    "tistory",
                    "publish",
                    {"title": "demo", "content": "body", "tags": tags},
                    allowed_image_hosts={"img.test"},
                    resolve_image_hosts=False,
                )
    def test_tistory_requires_at_least_three_public_tags(self):
        invalid_payloads = (
            {"title": "demo", "content": "body"},
            {"title": "demo", "content": "body", "tags": []},
            {"title": "demo", "content": "body", "tags": ["FDE", "고객인터뷰"]},
        )
        for payload in invalid_payloads:
            with self.subTest(payload=payload), self.assertRaises(self.module.ValidationError):
                self.module._validate_payload(
                    "tistory",
                    "publish",
                    payload,
                    allowed_image_hosts={"img.test"},
                    resolve_image_hosts=False,
                )


    def test_tistory_publish_uses_loopback_publisher_transport(self):
        runtime = self.direct_runtime()
        plan = runtime.preview(
            channel="tistory",
            operation="publish",
            payload={
                "title": "Demo",
                "content": "Body",
                "tags": ["FDE", "고객인터뷰", "업무분석"],
            },
            topic="direct-tistory",
            note_path="Blog/direct-tistory.md",
            session_id=self.SESSION_ID,
            turn_id=self.PREVIEW_TURN,
            user_message_id=self.PREVIEW_MESSAGE_ID,
        )
        runtime.approve(
            plan["receipt_id"],
            approval_text="발행해줘",
            session_id=self.SESSION_ID,
            turn_id=self.APPROVAL_TURN,
            user_message_id=self.APPROVAL_MESSAGE_ID,
        )

        result = runtime.dispatch(plan["receipt_id"], session_id=self.SESSION_ID)

        self.assertEqual("completed", result["status"])
        requests = [item for item in FakeApiHandler.requests if item[1] == "/publish-sync/tistory"]
        self.assertEqual(1, len(requests))
        headers = {key.lower(): value for key, value in requests[0][2].items()}
        self.assertEqual("publisher-secret", headers["x-api-token"])
        self.assertEqual(plan["receipt_id"], headers["x-idempotency-key"])
        self.assertNotIn("x-sns-token", headers)
        self.assertEqual({"dry_run": False}, requests[0][3]["options"])

    def test_tistory_update_uses_loopback_with_approved_ledger_post(self):
        runtime = self.direct_runtime()
        FakeApiHandler.active_posts_enabled = True
        FakeApiHandler.active_post = {
            "id": 28,
            "post_id": "306",
            "url": "https://donggu1105.tistory.com/306",
            "note_path": "Blog/demo.md",
        }
        plan = runtime.preview(
            channel="tistory",
            operation="update",
            payload={
                "title": "Updated",
                "content": "Body",
                "tags": ["FDE", "고객인터뷰", "업무분석"],
            },
            topic="demo",
            note_path="Blog/demo.md",
            session_id=self.SESSION_ID,
            turn_id=self.PREVIEW_TURN,
            user_message_id=self.PREVIEW_MESSAGE_ID,
        )
        runtime.approve(
            plan["receipt_id"],
            approval_text="업데이트 적용해줘",
            session_id=self.SESSION_ID,
            turn_id=self.APPROVAL_TURN,
            user_message_id=self.APPROVAL_MESSAGE_ID,
        )

        result = runtime.dispatch(plan["receipt_id"], session_id=self.SESSION_ID)

        self.assertEqual("completed", result["status"])
        requests = [item for item in FakeApiHandler.requests if item[1] == "/update-sync/tistory"]
        self.assertEqual(1, len(requests))
        self.assertEqual("306", requests[0][3]["post_id"])
        self.assertEqual({"dry_run": False}, requests[0][3]["options"])

    def test_maily_real_send_uses_loopback_after_separate_confirmation(self):
        runtime = self.direct_runtime()
        plan = runtime.preview(
            channel="maily",
            operation="publish",
            payload={
                "title": "Title",
                "subtitle": "Subtitle",
                "content": "Body",
                "dry_run": False,
            },
            topic="direct-mail",
            note_path="Maily/direct-mail.md",
            session_id=self.SESSION_ID,
            turn_id=self.PREVIEW_TURN,
            user_message_id=self.PREVIEW_MESSAGE_ID,
        )
        runtime.approve(
            plan["receipt_id"],
            approval_text="발행해줘",
            session_id=self.SESSION_ID,
            turn_id=self.APPROVAL_TURN,
            user_message_id=self.APPROVAL_MESSAGE_ID,
        )
        runtime.confirm_irreversible(
            plan["receipt_id"],
            confirmation_text="메일 최종 발송 승인해줘",
            session_id=self.SESSION_ID,
            turn_id=self.CONFIRM_TURN,
            user_message_id=self.CONFIRM_MESSAGE_ID,
        )

        result = runtime.dispatch(plan["receipt_id"], session_id=self.SESSION_ID)

        self.assertEqual("completed", result["status"])
        requests = [item for item in FakeApiHandler.requests if item[1] == "/publish-sync/maily"]
        self.assertEqual(1, len(requests))
        headers = {key.lower(): value for key, value in requests[0][2].items()}
        self.assertEqual("publisher-secret", headers["x-api-token"])
        self.assertNotIn("x-sns-token", headers)

    def test_nonlocal_channel_keeps_webhook_transport(self):
        runtime = self.direct_runtime()
        plan = runtime.preview(
            channel="threads",
            operation="publish",
            payload={"content": "hello"},
            topic="direct-threads",
            note_path="Threads/direct-threads.md",
            session_id=self.SESSION_ID,
            turn_id=self.PREVIEW_TURN,
            user_message_id=self.PREVIEW_MESSAGE_ID,
        )
        runtime.approve(
            plan["receipt_id"],
            approval_text="발행해줘",
            session_id=self.SESSION_ID,
            turn_id=self.APPROVAL_TURN,
            user_message_id=self.APPROVAL_MESSAGE_ID,
        )

        result = runtime.dispatch(plan["receipt_id"], session_id=self.SESSION_ID)

        self.assertEqual("completed", result["status"])
        requests = [item for item in FakeApiHandler.requests if item[1] == "/webhook/sns-pub-threads"]
        self.assertEqual(1, len(requests))
        headers = {key.lower(): value for key, value in requests[0][2].items()}
        self.assertEqual("webhook-secret", headers["x-sns-token"])
        self.assertNotIn("x-api-token", headers)

    def test_tistory_update_dry_run_is_rejected_before_receipt(self):
        runtime = self.direct_runtime()
        FakeApiHandler.active_posts_enabled = True
        FakeApiHandler.active_post = {
            "id": 28,
            "post_id": "306",
            "url": "https://donggu1105.tistory.com/306",
            "note_path": "Blog/demo.md",
        }
        with self.assertRaises(self.module.ValidationError):
            runtime.preview(
                channel="tistory",
                operation="update",
                payload={
                    "title": "Updated",
                    "content": "Body",
                    "tags": ["FDE", "고객인터뷰", "업무분석"],
                    "dry_run": True,
                },
                topic="demo",
                note_path="Blog/demo.md",
                session_id=self.SESSION_ID,
                turn_id=self.PREVIEW_TURN,
                user_message_id=self.PREVIEW_MESSAGE_ID,
            )
        self.assertFalse(any(item[0] == "POST" for item in FakeApiHandler.requests))

    def test_from_env_requires_loopback_publisher_token(self):
        env = {
            "SNS_WEBHOOK_TOKEN": "webhook-secret",
            "SUPABASE_URL": "https://fvfayignxybdyyravorg.supabase.co",
            "SUPABASE_SERVICE_KEY": "service-secret",
        }
        with mock.patch.dict(os.environ, env, clear=True):
            with self.assertRaises(self.module.ValidationError):
                self.module.PublishingRuntime.from_env()


    def test_tistory_delete_uses_loopback_with_approved_ledger_post(self):
        runtime = self.direct_runtime()
        FakeApiHandler.active_posts_enabled = True
        FakeApiHandler.active_post = {
            "id": 28,
            "post_id": "306",
            "url": "https://donggu1105.tistory.com/306",
            "note_path": "Blog/demo.md",
        }
        plan = runtime.preview(
            channel="tistory",
            operation="delete",
            payload={},
            topic="demo",
            note_path="",
            session_id=self.SESSION_ID,
            turn_id=self.PREVIEW_TURN,
            user_message_id=self.PREVIEW_MESSAGE_ID,
        )
        runtime.approve(
            plan["receipt_id"],
            approval_text="삭제해줘",
            session_id=self.SESSION_ID,
            turn_id=self.APPROVAL_TURN,
            user_message_id=self.APPROVAL_MESSAGE_ID,
        )

        result = runtime.dispatch(plan["receipt_id"], session_id=self.SESSION_ID)

        self.assertEqual("completed", result["status"])
        requests = [item for item in FakeApiHandler.requests if item[1] == "/unpublish-sync/tistory"]
        self.assertEqual(1, len(requests))
        self.assertEqual({"post_id": "306"}, requests[0][3])

    def test_maily_draft_uses_loopback_without_ledger_insert(self):
        runtime = self.direct_runtime()
        plan = runtime.preview(
            channel="maily",
            operation="publish",
            payload={
                "title": "Draft",
                "subtitle": "Subtitle",
                "content": "Body",
                "dry_run": True,
            },
            topic="direct-draft",
            note_path="Maily/direct-draft.md",
            session_id=self.SESSION_ID,
            turn_id=self.PREVIEW_TURN,
            user_message_id=self.PREVIEW_MESSAGE_ID,
        )
        runtime.approve(
            plan["receipt_id"],
            approval_text="발행해줘",
            session_id=self.SESSION_ID,
            turn_id=self.APPROVAL_TURN,
            user_message_id=self.APPROVAL_MESSAGE_ID,
        )

        result = runtime.dispatch(plan["receipt_id"], session_id=self.SESSION_ID)

        self.assertEqual("completed_draft", result["status"])
        requests = [item for item in FakeApiHandler.requests if item[1] == "/publish-sync/maily"]
        self.assertEqual(1, len(requests))
        self.assertEqual({"dry_run": True}, requests[0][3]["options"])
        ledger_inserts = [
            item for item in FakeApiHandler.requests
            if item[0] == "POST" and item[1] == "/rest/v1/published_posts"
        ]
        self.assertEqual([], ledger_inserts)

    def test_local_publisher_uncertainty_requires_reconciliation(self):
        runtime = self.direct_runtime()
        plan = runtime.preview(
            channel="tistory",
            operation="publish",
            payload={
                "title": "Demo",
                "content": "Body",
                "tags": ["FDE", "고객인터뷰", "업무분석"],
            },
            topic="uncertain-local",
            note_path="Blog/uncertain-local.md",
            session_id=self.SESSION_ID,
            turn_id=self.PREVIEW_TURN,
            user_message_id=self.PREVIEW_MESSAGE_ID,
        )
        runtime.approve(
            plan["receipt_id"],
            approval_text="발행해줘",
            session_id=self.SESSION_ID,
            turn_id=self.APPROVAL_TURN,
            user_message_id=self.APPROVAL_MESSAGE_ID,
        )
        FakeApiHandler.publisher_uncertain_without_identifiers = True

        result = runtime.dispatch(plan["receipt_id"], session_id=self.SESSION_ID)

        self.assertEqual("reconciliation_required", result["status"])
        self.assertEqual("published_identifiers_missing_after_submit", result["error"])
        ledger_inserts = [
            item for item in FakeApiHandler.requests
            if item[0] == "POST" and item[1] == "/rest/v1/published_posts"
        ]
        self.assertEqual([], ledger_inserts)


    def test_production_runtime_cannot_fall_back_to_publisher_webhooks(self):
        with self.assertRaises(self.module.ValidationError):
            self.module.PublishingRuntime(
                receipt_root=Path(self.tmp.name) / "production-receipts",
                webhook_base_url="https://n8n.donggu.site/webhook",
                webhook_token="webhook-secret",
                ledger=self.runtime.ledger,
            )


if __name__ == "__main__":
    unittest.main()
