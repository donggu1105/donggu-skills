"""Shared publishing runtime for Claude and Hermes adapters.

The runtime is intentionally stdlib-only. It binds every mutation to an
expiring preview receipt, routes only to closed webhook paths, and completes
the durable ``published_posts`` ledger after a successful external mutation.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from contextlib import contextmanager
import fcntl
import hashlib
import hmac
import ipaddress
import json
import os
from pathlib import Path
import re
import secrets
import socket
import stat
import tempfile
import threading
import time
from typing import Any, Callable, Dict, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener


class PublishingError(Exception):
    pass


class ValidationError(PublishingError):
    pass


class ApprovalError(PublishingError):
    pass


class ReceiptError(PublishingError):
    pass


class TransportError(PublishingError):
    def __init__(self, message: str, *, uncertain: bool = True):
        super().__init__(message)
        self.uncertain = uncertain


_RECEIPT_RE = re.compile(r"^[A-Za-z0-9_-]{20,80}$")
_MAX_TEXT = 500_000
_DEFAULT_WEBHOOK_BASE = "https://n8n.donggu.site/webhook"
_EXPECTED_SUPABASE_HOST = "fvfayignxybdyyravorg.supabase.co"

_ENDPOINTS = {
    ("tistory", "publish"): "sns-pub-tistory",
    ("tistory", "update"): "sns-update-tistory",
    ("tistory", "delete"): "sns-del-tistory",
    ("maily", "publish"): "sns-pub-maily",
    ("threads", "publish"): "sns-pub-threads",
    ("threads", "delete"): "sns-del-threads",
    ("linkedin", "publish"): "sns-pub-linkedin",
    ("instagram", "publish"): "sns-pub-instagram",
}

_CONTRACTS = {
    ("tistory", "publish"): ({"title", "content"}, {"category", "tags", "cover_image"}),
    ("tistory", "update"): ({"title", "content"}, {"category", "tags", "cover_image", "dry_run"}),
    ("maily", "publish"): ({"title", "content", "subtitle"}, {"tags", "dry_run"}),
    ("threads", "publish"): ({"content"}, {"image_urls"}),
    ("linkedin", "publish"): ({"content"}, set()),
    ("instagram", "publish"): ({"image_urls", "caption"}, set()),
    ("tistory", "delete"): (set(), set()),
    ("threads", "delete"): (set(), set()),
}


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _nonempty(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > _MAX_TEXT:
        raise ValidationError(f"{field} must be a non-empty bounded string")
    return value


_DENIAL_RE = re.compile(
    r"취소|보류|하지\s*마|하지\s*말|올리지\s*마|게시하지\s*마|발행하지\s*마|"
    r"삭제하지\s*마|보내지\s*마|안\s*(?:돼|해|할래)",
    re.IGNORECASE,
)
_APPROVAL_RE = re.compile(
    r"(?:^|[\s:])(?:승인(?:해\s*줘|합니다|할게|함)?|올려\s*줘|내려\s*줘|게시해\s*줘|"
    r"발행해\s*줘|삭제해\s*줘|진행해\s*줘)(?:$|[\s.!?])",
    re.IGNORECASE,
)


def _require_explicit_approval(value: Any) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > _MAX_TEXT:
        raise ApprovalError("the current user message does not explicitly approve this operation")
    text = value
    if _DENIAL_RE.search(text) or _APPROVAL_RE.search(text) is None:
        raise ApprovalError("the current user message does not explicitly approve this operation")
    return text


def _require_maily_confirmation(value: Any) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > _MAX_TEXT:
        raise ApprovalError("the current user message must explicitly confirm the final Maily send")
    text = value
    lowered = text.lower()
    required = (
        ("메일" in text or "maily" in lowered),
        "최종" in text,
        any(token in text for token in ("발송", "전송", "보내")),
        any(token in text for token in ("승인", "확인", "해줘", "해 줘")),
    )
    if _DENIAL_RE.search(text) or not all(required):
        raise ApprovalError("the current user message must explicitly confirm the final Maily send")
    return text


def _message_id(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValidationError(f"{field} must be a positive integer")
    return value


def _validate_url(value: Any, field: str) -> str:
    text = _nonempty(value, field)
    parsed = urlparse(text)
    if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password or not parsed.hostname:
        raise ValidationError(f"{field} must be an https URL")
    hostname = parsed.hostname.lower()
    if hostname == "localhost" or hostname.endswith(".local"):
        raise ValidationError(f"{field} must not target a local address")
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        address = None
    if address is not None and not address.is_global:
        raise ValidationError(f"{field} must not target a private or local address")
    return text


def _validate_image_url(value: Any, *, allowed_hosts: set[str], resolve_dns: bool = True) -> str:
    text = _validate_url(value, "image_url")
    hostname = str(urlparse(text).hostname).lower()
    if hostname not in allowed_hosts:
        raise ValidationError("image URL host is not allowlisted")
    if resolve_dns:
        try:
            answers = socket.getaddrinfo(hostname, 443, type=socket.SOCK_STREAM)
        except socket.gaierror:
            raise ValidationError("image URL host could not be resolved") from None
        addresses = {answer[4][0] for answer in answers if answer[4]}
        if not addresses:
            raise ValidationError("image URL host could not be resolved")
        for raw_address in addresses:
            try:
                address = ipaddress.ip_address(raw_address)
            except ValueError:
                raise ValidationError("image URL resolved to an invalid address") from None
            if not address.is_global:
                raise ValidationError("image URL must not resolve to a private or local address")
    return text


def _validate_service_base(value: str, *, service: str, allow_test_origins: bool) -> str:
    text = _nonempty(value, f"{service} base URL").rstrip("/")
    parsed = urlparse(text)
    if parsed.username or parsed.password or parsed.query or parsed.fragment or not parsed.hostname:
        raise ValidationError(f"invalid {service} base URL")
    if allow_test_origins:
        if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost"}:
            raise ValidationError(f"invalid test {service} origin")
        return text
    if service == "webhook":
        valid = parsed.scheme == "https" and parsed.hostname == "n8n.donggu.site" and parsed.port is None and parsed.path == "/webhook"
    else:
        valid = parsed.scheme == "https" and parsed.hostname == _EXPECTED_SUPABASE_HOST and parsed.port is None and parsed.path in {"", "/"}
    if not valid:
        raise ValidationError(f"untrusted {service} origin")
    return text


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _validate_payload(
    channel: str, operation: str, payload: Any, *,
    allowed_image_hosts: set[str], resolve_image_hosts: bool,
) -> Dict[str, Any]:
    key = (channel, operation)
    if key not in _CONTRACTS:
        raise ValidationError("unsupported channel or operation")
    if not isinstance(payload, dict):
        raise ValidationError("payload must be an object")
    required, optional = _CONTRACTS[key]
    keys = set(payload)
    if not required.issubset(keys) or not keys.issubset(required | optional):
        raise ValidationError("payload does not match the closed channel contract")
    clean: Dict[str, Any] = {}
    for field, value in payload.items():
        if field in {"title", "content", "subtitle", "caption", "category"}:
            clean[field] = _nonempty(value, field)
        elif field in {"cover_image"}:
            clean[field] = _validate_image_url(
                value, allowed_hosts=allowed_image_hosts, resolve_dns=resolve_image_hosts,
            )
        elif field in {"tags"}:
            if not isinstance(value, list) or len(value) > 50:
                raise ValidationError("tags must be a bounded string list")
            clean[field] = [_nonempty(item, "tag") for item in value]
        elif field == "image_urls":
            if not isinstance(value, list) or not 1 <= len(value) <= 10:
                raise ValidationError("image_urls must contain 1 to 10 URLs")
            clean[field] = [
                _validate_image_url(
                    item, allowed_hosts=allowed_image_hosts, resolve_dns=resolve_image_hosts,
                )
                for item in value
            ]
        elif field == "dry_run":
            if type(value) is not bool:
                raise ValidationError("dry_run must be boolean")
            clean[field] = value
        else:  # exact-key validation above makes this defensive only
            raise ValidationError("unsupported payload field")
    return clean


def _request_json(method: str, url: str, *, headers: Dict[str, str], body: Optional[Dict[str, Any]] = None, timeout: int = 60) -> Any:
    data = None if body is None else _canonical(body)
    request = Request(url, data=data, method=method, headers=headers)
    try:
        with build_opener(_NoRedirect()).open(request, timeout=timeout) as response:
            raw = response.read()
            if not 200 <= response.status < 300:
                raise TransportError(f"HTTP {response.status}", uncertain=response.status >= 500)
    except HTTPError as exc:
        raise TransportError(f"HTTP {exc.code}", uncertain=exc.code >= 500) from None
    except (URLError, OSError, TimeoutError):
        raise TransportError("network request failed", uncertain=True) from None
    try:
        return json.loads(raw or b"null")
    except (ValueError, UnicodeError):
        raise TransportError("remote returned invalid JSON") from None


@dataclass
class SupabaseLedger:
    base_url: str
    service_key: str
    timeout: int = 30
    allow_test_origins: bool = False

    def __post_init__(self) -> None:
        self.base_url = _validate_service_base(
            self.base_url,
            service="supabase",
            allow_test_origins=self.allow_test_origins,
        )
        self.service_key = _nonempty(self.service_key, "Supabase service key")

    @classmethod
    def from_env(cls) -> "SupabaseLedger":
        base = os.getenv("SUPABASE_URL", "").strip()
        key = os.getenv("SUPABASE_SERVICE_KEY", "").strip()
        if not base or not key:
            raise ValidationError("SUPABASE_URL and SUPABASE_SERVICE_KEY are required")
        return cls(base_url=base, service_key=key)

    @property
    def endpoint(self) -> str:
        return self.base_url.rstrip("/") + "/rest/v1/published_posts"

    def _headers(self, prefer: Optional[str] = None) -> Dict[str, str]:
        headers = {
            "apikey": self.service_key,
            "Authorization": "Bearer " + self.service_key,
            "Content-Type": "application/json",
        }
        if prefer:
            headers["Prefer"] = prefer
        return headers

    def find_active(self, topic: str, channel: str) -> Dict[str, Any]:
        query = urlencode({
            "select": "id,post_id,url,note_path",
            "topic": "eq." + topic,
            "channel": "eq." + channel,
            "deleted_at": "is.null",
            "order": "published_at.desc",
            "limit": "2",
        })
        rows = _request_json("GET", self.endpoint + "?" + query, headers=self._headers(), timeout=self.timeout)
        if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict):
            raise ValidationError("no active ledger post found")
        ledger_id = rows[0].get("id")
        if isinstance(ledger_id, bool) or not isinstance(ledger_id, (int, str)) or str(ledger_id).strip() == "":
            raise ValidationError("active ledger row has no id")
        post_id = rows[0].get("post_id")
        if not isinstance(post_id, str) or not post_id:
            raise ValidationError("active ledger row has no post_id")
        return {
            "id": ledger_id, "post_id": post_id,
            "url": rows[0].get("url"), "note_path": rows[0].get("note_path"),
        }

    def record_publish(self, *, topic: str, channel: str, note_path: str, post_id: Any, url: Any) -> None:
        body = {
            "topic": topic,
            "channel": channel,
            "note_path": note_path,
            "post_id": post_id if isinstance(post_id, str) and post_id else None,
            "url": url if isinstance(url, str) and url else None,
        }
        rows = _request_json(
            "POST",
            self.endpoint,
            headers=self._headers("return=representation"),
            body=body,
            timeout=self.timeout,
        )
        if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict):
            raise ValidationError("ledger insert did not return exactly one row")
        row = rows[0]
        for field in ("topic", "channel", "note_path", "post_id", "url"):
            if row.get(field) != body[field]:
                raise ValidationError("ledger insert representation mismatch")

    def mark_deleted(self, *, ledger_id: Any, channel: str, post_id: str) -> None:
        query = urlencode({
            "id": "eq." + str(ledger_id),
            "channel": "eq." + channel,
            "post_id": "eq." + post_id,
            "deleted_at": "is.null",
        })
        body = {"deleted_at": datetime.now(timezone.utc).isoformat()}
        rows = _request_json(
            "PATCH",
            self.endpoint + "?" + query,
            headers=self._headers("return=representation"),
            body=body,
            timeout=self.timeout,
        )
        if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict):
            raise ValidationError("ledger delete update did not return exactly one row")
        row = rows[0]
        if (
            str(row.get("id")) != str(ledger_id)
            or row.get("channel") not in {None, channel}
            or row.get("post_id") != post_id
            or row.get("deleted_at") != body["deleted_at"]
        ):
            raise ValidationError("ledger delete representation mismatch")


class ReceiptStore:
    def __init__(self, root: Path, ttl_seconds: int = 900):
        self.root = Path(root).expanduser()
        self.ttl_seconds = int(ttl_seconds)
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        try:
            os.chmod(self.root, 0o700)
        except OSError:
            pass
        self._signing_key = secrets.token_bytes(32)

    def _signature(self, receipt: Dict[str, Any]) -> str:
        body = {key: value for key, value in receipt.items() if key != "receipt_hmac"}
        return hmac.new(self._signing_key, _canonical(body), hashlib.sha256).hexdigest()

    def _path(self, receipt_id: str) -> Path:
        if not isinstance(receipt_id, str) or _RECEIPT_RE.fullmatch(receipt_id) is None:
            raise ReceiptError("invalid receipt id")
        return self.root / (receipt_id + ".json")

    @contextmanager
    def _lock(self, receipt_id: str):
        lock_path = self.root / (self._path(receipt_id).stem + ".lock")
        fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
        with os.fdopen(fd, "a+b", closefd=True) as stream:
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)

    def _write(self, receipt: Dict[str, Any]) -> None:
        receipt["receipt_hmac"] = self._signature(receipt)
        target = self._path(str(receipt["receipt_id"]))
        fd, temp_name = tempfile.mkstemp(prefix=".receipt-", dir=str(self.root))
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "wb", closefd=True) as stream:
                stream.write(_canonical(receipt))
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp_name, target)
            os.chmod(target, 0o600)
        except Exception:
            try:
                os.close(fd)
            except OSError:
                pass
            try:
                os.unlink(temp_name)
            except OSError:
                pass
            raise

    def issue(self, data: Dict[str, Any]) -> Dict[str, Any]:
        now = int(time.time())
        receipt = {
            **data,
            "receipt_id": secrets.token_urlsafe(24),
            "state": "planned",
            "created_at": now,
            "expires_at": now + self.ttl_seconds,
        }
        self._write(receipt)
        return receipt

    def load(self, receipt_id: str, *, require_state: Optional[str] = None) -> Dict[str, Any]:
        path = self._path(receipt_id)
        try:
            if stat.S_ISLNK(path.lstat().st_mode):
                raise ReceiptError("invalid receipt file")
            receipt = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            raise ReceiptError("receipt not found or invalid") from None
        if receipt.get("receipt_id") != receipt_id:
            raise ReceiptError("receipt binding mismatch")
        expected_hmac = receipt.get("receipt_hmac")
        if not isinstance(expected_hmac, str) or not hmac.compare_digest(expected_hmac, self._signature(receipt)):
            raise ReceiptError("receipt integrity check failed")
        if (
            int(receipt.get("expires_at", 0)) <= int(time.time())
            and receipt.get("state") in {"planned", "approved", "confirmed"}
        ):
            raise ReceiptError("receipt expired")
        if require_state is not None and receipt.get("state") != require_state:
            raise ReceiptError("receipt is not available for this operation")
        return receipt

    def transition(self, receipt: Dict[str, Any], state: str, **updates: Any) -> Dict[str, Any]:
        next_receipt = {**receipt, **updates, "state": state, "updated_at": int(time.time())}
        self._write(next_receipt)
        return next_receipt

    def claim(
        self,
        receipt_id: str,
        expected_state: str,
        next_state: str,
        *,
        validator: Optional[Callable[[Dict[str, Any]], None]] = None,
        **updates: Any,
    ) -> Dict[str, Any]:
        with self._lock(receipt_id):
            receipt = self.load(receipt_id, require_state=expected_state)
            if validator is not None:
                validator(receipt)
            return self.transition(receipt, next_state, **updates)

    def status(self, receipt_id: str) -> Dict[str, Any]:
        receipt = self.load(receipt_id)
        return {
            "receipt_id": receipt_id,
            "state": receipt.get("state"),
            "channel": receipt.get("channel"),
            "operation": receipt.get("operation"),
            "expires_at": receipt.get("expires_at"),
            "result": receipt.get("result"),
        }


class PublishingRuntime:
    def __init__(
        self,
        *,
        receipt_root: Path,
        webhook_base_url: str,
        webhook_token: str,
        ledger: SupabaseLedger,
        receipt_ttl_seconds: int = 900,
        timeout: int = 200,
        allow_test_origins: bool = False,
        image_allowed_hosts: Optional[set[str]] = None,
    ):
        self.store = ReceiptStore(receipt_root, receipt_ttl_seconds)
        self.webhook_base_url = _validate_service_base(
            webhook_base_url,
            service="webhook",
            allow_test_origins=allow_test_origins,
        )
        self.webhook_token = _nonempty(webhook_token, "webhook token")
        self.ledger = ledger
        self.timeout = int(timeout)
        self.image_allowed_hosts = set(image_allowed_hosts or ({"img.test"} if allow_test_origins else {_EXPECTED_SUPABASE_HOST}))
        self.resolve_image_hosts = not allow_test_origins
        self._authorization_lock = threading.Lock()
        self._consumed_authorizations: Dict[tuple[str, int], str] = {}

    def _consume_authorization(
        self, *, session_digest: str, user_message_id: int, receipt_id: str,
        claim: Callable[[], Dict[str, Any]],
    ) -> Dict[str, Any]:
        key = (session_digest, user_message_id)
        with self._authorization_lock:
            if key in self._consumed_authorizations:
                raise ApprovalError("this persisted user authorization was already used for another receipt")
            receipt = claim()
            self._consumed_authorizations[key] = receipt_id
            return receipt

    @classmethod
    def from_env(cls) -> "PublishingRuntime":
        token = os.getenv("SNS_WEBHOOK_TOKEN", "").strip()
        if not token:
            raise ValidationError("SNS_WEBHOOK_TOKEN is required")
        home = Path(os.getenv("HERMES_HOME", str(Path.home() / ".hermes"))).expanduser()
        return cls(
            receipt_root=home / "state" / "donggu-publishing" / "receipts",
            webhook_base_url=_DEFAULT_WEBHOOK_BASE,
            webhook_token=token,
            ledger=SupabaseLedger.from_env(),
        )

    def preview(
        self, *, channel: str, operation: str, payload: Any, topic: str, note_path: str,
        session_id: str, turn_id: str, issue_receipt: bool = True,
        user_message_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        session_id = _nonempty(session_id, "trusted session id")
        turn_id = _nonempty(turn_id, "trusted turn id")
        channel = _nonempty(channel, "channel").lower()
        operation = _nonempty(operation, "operation").lower()
        topic = _nonempty(topic, "topic")
        clean = _validate_payload(
            channel, operation, payload,
            allowed_image_hosts=self.image_allowed_hosts,
            resolve_image_hosts=self.resolve_image_hosts,
        )
        if operation in {"publish", "update"}:
            note_path = _nonempty(note_path, "note_path")
        elif not isinstance(note_path, str):
            raise ValidationError("note_path must be a string")
        resolved = None
        if operation in {"update", "delete"}:
            resolved = self.ledger.find_active(topic, channel)
        binding = {
            "channel": channel,
            "operation": operation,
            "payload": clean,
            "topic": topic,
            "note_path": note_path,
            "resolved": resolved,
        }
        payload_sha256 = _sha256(binding)
        receipt = None
        if issue_receipt:
            preview_message_id = _message_id(user_message_id, "trusted preview user message id")
            receipt = self.store.issue({
                **binding,
                "payload_sha256": payload_sha256,
                "session_sha256": hashlib.sha256(session_id.encode("utf-8")).hexdigest(),
                "preview_turn_sha256": hashlib.sha256(turn_id.encode("utf-8")).hexdigest(),
                "preview_message_id": preview_message_id,
            })
        preview: Dict[str, Any] = {"payload": clean}
        if "content" in clean:
            preview["content_chars"] = len(clean["content"])
        if "caption" in clean:
            preview["caption_chars"] = len(clean["caption"])
        preview["image_count"] = len(clean.get("image_urls", []))
        if resolved:
            preview["current_url"] = resolved.get("url")
            preview["post_id"] = resolved.get("post_id")
        result = {
            "status": "planned" if receipt is not None else "preview",
            "channel": channel,
            "operation": operation,
            "topic": topic,
            "payload_sha256": payload_sha256,
            "irreversible": channel == "maily" and operation == "publish" and clean.get("dry_run") is not True,
            "preview": preview,
        }
        if receipt is not None:
            result["receipt_id"] = receipt["receipt_id"]
            result["expires_at"] = receipt["expires_at"]
        return result

    def receipt_status(self, receipt_id: str) -> Dict[str, Any]:
        return self.store.status(receipt_id)

    @staticmethod
    def _verify_binding(receipt: Dict[str, Any]) -> None:
        binding = {
            "channel": receipt.get("channel"),
            "operation": receipt.get("operation"),
            "payload": receipt.get("payload"),
            "topic": receipt.get("topic"),
            "note_path": receipt.get("note_path"),
            "resolved": receipt.get("resolved"),
        }
        expected = receipt.get("payload_sha256")
        actual = _sha256(binding)
        if not isinstance(expected, str) or not secrets.compare_digest(expected, actual):
            raise ReceiptError("receipt payload binding mismatch")

    def approve(
        self, receipt_id: str, *, approval_text: str, session_id: str, turn_id: str,
        user_message_id: int,
    ) -> Dict[str, Any]:
        approval_text = _require_explicit_approval(approval_text)
        approval_message_id = _message_id(user_message_id, "trusted approval user message id")
        session_digest = hashlib.sha256(_nonempty(session_id, "trusted session id").encode("utf-8")).hexdigest()
        turn_digest = hashlib.sha256(_nonempty(turn_id, "trusted turn id").encode("utf-8")).hexdigest()

        def validate(receipt: Dict[str, Any]) -> None:
            self._verify_binding(receipt)
            if not secrets.compare_digest(str(receipt.get("session_sha256") or ""), session_digest):
                raise ApprovalError("approval must come from the preview session")
            if secrets.compare_digest(str(receipt.get("preview_turn_sha256") or ""), turn_digest):
                raise ApprovalError("approval must come from a later user turn")
            preview_message_id = receipt.get("preview_message_id")
            if not isinstance(preview_message_id, int) or approval_message_id <= preview_message_id:
                raise ApprovalError("approval must come from a newly persisted user message")

        receipt = self._consume_authorization(
            session_digest=session_digest,
            user_message_id=approval_message_id,
            receipt_id=receipt_id,
            claim=lambda: self.store.claim(
                receipt_id,
                "planned",
                "approved",
                validator=validate,
                approval_sha256=hashlib.sha256(approval_text.strip().encode("utf-8")).hexdigest(),
                approval_turn_sha256=turn_digest,
                approval_message_id=approval_message_id,
            ),
        )
        return {"status": "approved", "receipt_id": receipt_id, "expires_at": receipt["expires_at"]}

    def confirm_irreversible(
        self, receipt_id: str, *, confirmation_text: str, session_id: str, turn_id: str,
        user_message_id: int,
    ) -> Dict[str, Any]:
        confirmation_text = _require_maily_confirmation(confirmation_text)
        confirmation_message_id = _message_id(user_message_id, "trusted confirmation user message id")
        session_digest = hashlib.sha256(_nonempty(session_id, "trusted session id").encode("utf-8")).hexdigest()
        turn_digest = hashlib.sha256(_nonempty(turn_id, "trusted turn id").encode("utf-8")).hexdigest()

        def validate(receipt: Dict[str, Any]) -> None:
            self._verify_binding(receipt)
            if not secrets.compare_digest(str(receipt.get("session_sha256") or ""), session_digest):
                raise ApprovalError("confirmation must come from the preview session")
            if secrets.compare_digest(str(receipt.get("approval_turn_sha256") or ""), turn_digest):
                raise ApprovalError("confirmation must come from a later user turn")
            approval_message_id = receipt.get("approval_message_id")
            if not isinstance(approval_message_id, int) or confirmation_message_id <= approval_message_id:
                raise ApprovalError("confirmation must come from a newly persisted user message")
            is_real_maily = (
                receipt.get("channel") == "maily"
                and receipt.get("operation") == "publish"
                and isinstance(receipt.get("payload"), dict)
                and receipt["payload"].get("dry_run") is not True
            )
            if not is_real_maily:
                raise ReceiptError("receipt does not require irreversible confirmation")

        receipt = self._consume_authorization(
            session_digest=session_digest,
            user_message_id=confirmation_message_id,
            receipt_id=receipt_id,
            claim=lambda: self.store.claim(
                receipt_id,
                "approved",
                "confirmed",
                validator=validate,
                confirmation_sha256=hashlib.sha256(confirmation_text.strip().encode("utf-8")).hexdigest(),
                confirmation_turn_sha256=turn_digest,
                confirmation_message_id=confirmation_message_id,
            ),
        )
        return {"status": "confirmed", "receipt_id": receipt_id, "expires_at": receipt["expires_at"]}

    def dispatch(self, receipt_id: str, *, session_id: str) -> Dict[str, Any]:
        session_digest = hashlib.sha256(_nonempty(session_id, "trusted session id").encode("utf-8")).hexdigest()
        observed = self.store.load(receipt_id)
        self._verify_binding(observed)
        real_maily = (
            observed.get("channel") == "maily"
            and observed.get("operation") == "publish"
            and isinstance(observed.get("payload"), dict)
            and observed["payload"].get("dry_run") is not True
        )
        expected_state = "confirmed" if real_maily else "approved"

        def validate(receipt: Dict[str, Any]) -> None:
            self._verify_binding(receipt)
            if not secrets.compare_digest(str(receipt.get("session_sha256") or ""), session_digest):
                raise ApprovalError("dispatch must use the preview session")

        receipt = self.store.claim(
            receipt_id,
            expected_state,
            "dispatching",
            validator=validate,
        )
        channel = receipt["channel"]
        operation = receipt["operation"]
        webhook_payload = dict(receipt["payload"])
        if operation in {"update", "delete"}:
            webhook_payload["post_id"] = receipt["resolved"]["post_id"]
        endpoint = _ENDPOINTS[(channel, operation)]
        headers = {
            "Content-Type": "application/json",
            "X-SNS-Token": self.webhook_token,
            "X-Idempotency-Key": receipt_id,
        }
        try:
            response = _request_json(
                "POST",
                self.webhook_base_url + "/" + endpoint,
                headers=headers,
                body=webhook_payload,
                timeout=self.timeout,
            )
        except TransportError as exc:
            state = "uncertain" if exc.uncertain else "failed"
            result = {"status": state, "error": str(exc), "receipt_id": receipt_id}
            self.store.transition(receipt, state, result=result, payload=None)
            return result
        if not isinstance(response, dict) or response.get("success") is not True:
            result = {"status": "failed", "error": "publisher reported failure", "receipt_id": receipt_id}
            self.store.transition(receipt, "failed", result=result, payload=None)
            return result

        result = {
            "status": "completed",
            "receipt_id": receipt_id,
            "channel": channel,
            "operation": operation,
            "url": response.get("url"),
            "post_id": response.get("post_id"),
        }
        if operation != "delete":
            try:
                result["url"] = _validate_url(response.get("url"), "publisher url")
                if channel in {"tistory", "threads"}:
                    result["post_id"] = _nonempty(response.get("post_id"), "publisher post_id")
            except ValidationError:
                result["status"] = "reconciliation_required"
                result["error"] = "external mutation succeeded but required identifiers are missing or invalid"
                self.store.transition(receipt, "reconciliation_required", result=result, payload=None)
                return result

        if channel == "maily" and operation == "publish" and receipt["payload"].get("dry_run") is True:
            result["status"] = "completed_draft"
            self.store.transition(receipt, "completed_draft", result=result, payload=None)
            return result

        try:
            if operation == "publish":
                self.ledger.record_publish(
                    topic=receipt["topic"],
                    channel=channel,
                    note_path=receipt["note_path"],
                    post_id=result.get("post_id"),
                    url=result.get("url"),
                )
            elif operation == "delete":
                self.ledger.mark_deleted(
                    ledger_id=receipt["resolved"]["id"],
                    channel=channel,
                    post_id=receipt["resolved"]["post_id"],
                )
        except PublishingError:
            result["status"] = "reconciliation_required"
            result["error"] = "external mutation succeeded but ledger completion failed"
            self.store.transition(receipt, "reconciliation_required", result=result, payload=None)
            return result
        self.store.transition(receipt, "completed", result=result, payload=None)
        return result
