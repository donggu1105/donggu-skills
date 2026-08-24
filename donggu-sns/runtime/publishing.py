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
from http.client import HTTPException, IncompleteRead
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
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener


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
_JOB_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9:._-]{0,199}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_MAX_TEXT = 500_000
_MAX_CONTENT_FILE_BYTES = 4 * 1024 * 1024
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")
_DEFAULT_WEBHOOK_BASE = "https://n8n.donggu.site/webhook"
_PUBLISHER_USER_AGENT = "donggu-publisher/1.0"

# `planned` 프리뷰에 쓰는 만료 없음 sentinel. 프리뷰는 외부 변경 0건이라
# 시간이 지나도 위험해지지 않는다. 실행 창은 승인 시점에 따로 열린다.
_NO_EXPIRY = 1 << 62

# IPv4를 감싸는 IPv6 표현. NAT64(RFC 6052)·6to4·Teredo·IPv4-mapped는 새 목적지가
# 아니라 같은 IPv4를 IPv6로 표현한 것이므로, 감싸인 IPv4를 꺼내 판정한다.
_IPV4_EMBEDDED_IPV6_NETWORKS = (
    ipaddress.ip_network("::/96"),
    ipaddress.ip_network("64:ff9b::/96"),
    ipaddress.ip_network("64:ff9b:1::/48"),
    ipaddress.ip_network("2001::/32"),
    ipaddress.ip_network("2002::/16"),
)


def _embedded_ipv4(address):
    """IPv4를 감싼 IPv6이면 그 안의 IPv4를, 아니면 None을 반환한다.

    DNS64가 켜진 네트워크는 정상 공인 호스트에도 NAT64 주소를 IPv4와 함께
    반환한다. 감싸인 IPv4를 실제 목적지로 판정해야 정상 이미지를 막지 않으면서
    내부망을 감싼 NAT64는 그대로 걸러낼 수 있다.
    """
    if not isinstance(address, ipaddress.IPv6Address):
        return None
    if address.ipv4_mapped is not None:
        return address.ipv4_mapped
    if address.sixtofour is not None:
        return address.sixtofour
    if address.teredo is not None:
        return address.teredo[1]
    for network in _IPV4_EMBEDDED_IPV6_NETWORKS:
        if address in network:
            return ipaddress.IPv4Address(int(address) & 0xFFFFFFFF)
    return None
_DEFAULT_PUBLISHER_API_BASE = "http://127.0.0.1:8000"
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

_LOCAL_ENDPOINTS = {
    ("tistory", "publish"): "/publish-sync/tistory",
    ("tistory", "update"): "/update-sync/tistory",
    ("tistory", "delete"): "/unpublish-sync/tistory",
    ("maily", "publish"): "/publish-sync/maily",
}

_CONTRACTS = {
    ("tistory", "publish"): ({"title", "content", "tags"}, {"category", "cover_image"}),
    ("tistory", "update"): ({"title", "content", "tags"}, {"category", "cover_image"}),
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


def _local_api_payload(
    operation: str,
    payload: Dict[str, Any],
    *,
    post_id: Optional[str] = None,
) -> Dict[str, Any]:
    adapted = {key: value for key, value in payload.items() if key != "dry_run"}
    if operation in {"update", "delete"}:
        adapted["post_id"] = _nonempty(post_id, "approved post_id")
    if operation != "delete":
        adapted["options"] = {"dry_run": payload.get("dry_run") is True}
    return adapted


_DENIAL_RE = re.compile(
    r"취소|보류|나중에|일단\s*(?:기다|보류)|하지\s*마|하지\s*말|지\s*마|지\s*말|"
    r"올리지\s*마|게시하지\s*마|발행하지\s*마|삭제하지\s*마|보내지\s*마|"
    r"안\s*(?:돼|해|할래)",
    re.IGNORECASE,
)
_APPROVAL_RE = re.compile(
    r"^\s*(?:(?:네|예|그대로|이대로|지금|최종|계속|블로그|티스토리|게시물|"
    r"포스트|이\s*글|해당\s*글|기존\s*글|업데이트|수정|삭제|발행|게시|"
    r"내용|초안|post\s*\d+)(?:을|를|에|으로|로|은|는)?[\s,:]*){0,6}(?:"
    r"승인(?:해\s*(?:줘|주세요)|합니다|할게|함)?|"
    r"올려\s*(?:줘|주세요)|내려\s*(?:줘|주세요)|"
    r"게시해\s*(?:줘|주세요)|발행해(?:\s*(?:줘|주세요))?|"
    r"삭제해\s*(?:줘|주세요)|진행해\s*(?:줘|주세요)|"
    r"적용해(?:\s*(?:줘|주세요))?"
    r")(?:[.!])?\s*$",
    re.IGNORECASE,
)
_OPERATION_APPROVAL_RE = {
    "publish": re.compile(
        r"(?:올려\s*(?:줘|주세요)|게시해\s*(?:줘|주세요)|"
        r"발행해(?:\s*(?:줘|주세요))?|(?:발행|게시)\s*"
        r"(?:승인|진행|적용)(?:해\s*(?:줘|주세요)|합니다|할게|함)?)",
        re.IGNORECASE,
    ),
    "update": re.compile(
        r"(?:업데이트|수정)(?:을|를)?\s*(?:"
        r"해\s*(?:줘|주세요)|(?:승인|진행|적용)"
        r"(?:해\s*(?:줘|주세요)|합니다|할게|함)?)",
        re.IGNORECASE,
    ),
    "delete": re.compile(
        r"(?:삭제해\s*(?:줘|주세요)|내려\s*(?:줘|주세요)|삭제\s*"
        r"(?:승인|진행|적용)(?:해\s*(?:줘|주세요)|합니다|할게|함)?)",
        re.IGNORECASE,
    ),
}

# 재조정(reconciliation) 해소 전용 승인 문구. 발행/수정/삭제 동사와 겹치지 않아야
# 한 번의 승인이 두 종류의 행위를 동시에 허가하지 않는다.
_RESOLVE_APPROVAL_RE = re.compile(
    r"(?:재조정|리컨실|reconciliation)\s*(?:을|를)?\s*"
    r"(?:해소|정리|종결|해제)"
    r"(?:해\s*(?:줘|주세요)|합니다|할게|함)?",
    re.IGNORECASE,
)

# 해소 방식. 외부 상태를 실제로 확인한 사람이 고른다.
_RESOLUTION_NO_CHANGE = "no_external_change"
_RESOLUTION_RECORDED = "external_change_recorded"
_RESOLUTIONS = (_RESOLUTION_NO_CHANGE, _RESOLUTION_RECORDED)
_OPERATION_INTENT_RE = {
    "publish": re.compile(r"올려|발행|게시(?!물)", re.IGNORECASE),
    "update": re.compile(r"업데이트|수정", re.IGNORECASE),
    "delete": re.compile(r"삭제|내려", re.IGNORECASE),
}
_MAILY_CONFIRM_RE = re.compile(
    r"^\s*(?:(?:네|예)[\s,:]*)?(?:메일리|maily|메일)"
    r"(?:\s*(?:뉴스레터|메일))?\s*최종\s*(?:발송|전송|보내기)\s*"
    r"(?:승인|확인)(?:해\s*(?:줘|주세요)|합니다|할게|함)?(?:[.!])?\s*$",
    re.IGNORECASE,
)
_NONFINAL_INTENT_RE = re.compile(
    r"[?？]|(?:검토|확인)\s*후|(?:문제\s*없|괜찮|가능하)으면|"
    r"(?:내일|나중에|다음에|잠시|아직)|(?:확신|모르|고민)|"
    r"(?:해도|할지|될까|할까|볼까)",
    re.IGNORECASE,
)
_URLISH_RE = re.compile(
    r"(?:[a-z][a-z0-9+.-]*://|www\.|mailto:)",
    re.IGNORECASE,
)
_HASHTAG_RE = re.compile(r"#[^\s#]+", re.UNICODE)
_CODE_LANGUAGE_RE = re.compile(r"(?<!#)\b(?:C|F)#", re.IGNORECASE)
_MARKDOWN_IMAGE_RE = re.compile(
    r"!\[([^\]\r\n]*)\]\(\s*(?:<([^>\r\n]+)>|([^\s)\r\n]+))"
    r"(?:\s+(?:\"[^\"\r\n]*\"|'[^'\r\n]*'|\([^()\r\n]*\)))?\s*\)",
    re.IGNORECASE,
)
_REFERENCE_IMAGE_RE = re.compile(r"!\[[^\]\r\n]*\]\s*\[[^\]\r\n]*\]", re.IGNORECASE)
_RAW_NETWORK_HTML_RE = re.compile(
    r"<\s*/?\s*[A-Za-z][A-Za-z0-9:-]*(?=[\s/>])",
    re.IGNORECASE,
)
_FENCE_OPEN_RE = re.compile(
    r"^(`{3,}|~{3,})[ ]*(?:\.?[\w#.+-]+)?[ ]*$"
)
_FENCE_CLOSE_RE = re.compile(r"^(`{3,}|~{3,})[ ]*$")


def _markdown_lines(content: str) -> list[str]:
    return str(content or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")


def _opening_fence(line: str) -> Optional[str]:
    match = _FENCE_OPEN_RE.fullmatch(line)
    return match.group(1) if match else None


def _is_closing_fence(line: str, opening: str) -> bool:
    match = _FENCE_CLOSE_RE.fullmatch(line)
    return bool(match and secrets.compare_digest(match.group(1), opening))


def _validate_content_contract(channel: str, operation: str, content: str) -> str:
    if operation != "publish":
        return content
    if channel == "threads":
        if len(content) > 500:
            raise ValidationError("threads content must not exceed 500 characters")
        if _HASHTAG_RE.search(_CODE_LANGUAGE_RE.sub("", content)):
            raise ValidationError("threads content must not contain hashtags")
        if _URLISH_RE.search(content):
            raise ValidationError("threads content must not contain URLs")
    elif channel == "linkedin" and _URLISH_RE.search(content):
        raise ValidationError("linkedin content must not contain URLs")
    return content


def _require_explicit_approval(value: Any) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > _MAX_TEXT:
        raise ApprovalError("the current user message does not explicitly approve this operation")
    text = value
    if (
        _DENIAL_RE.search(text)
        or _NONFINAL_INTENT_RE.search(text)
        or _APPROVAL_RE.search(text) is None
    ):
        raise ApprovalError("the current user message does not explicitly approve this operation")
    return text


def _require_operation_approval(value: Any, operation: str) -> str:
    text = _require_explicit_approval(value)
    expected = _OPERATION_APPROVAL_RE.get(operation)
    if expected is None or expected.search(text) is None:
        raise ApprovalError("the approval message does not match the receipt operation")
    if any(
        other != operation and pattern.search(text) is not None
        for other, pattern in _OPERATION_INTENT_RE.items()
    ):
        raise ApprovalError("the approval message mixes different publishing operations")
    return text


def _require_maily_confirmation(value: Any) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > _MAX_TEXT:
        raise ApprovalError("the current user message must explicitly confirm the final Maily send")
    text = value
    if (
        _DENIAL_RE.search(text)
        or _NONFINAL_INTENT_RE.search(text)
        or _MAILY_CONFIRM_RE.fullmatch(text) is None
    ):
        raise ApprovalError("the current user message must explicitly confirm the final Maily send")
    return text


def _message_id(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValidationError(f"{field} must be a positive integer")
    return value


def _optional_job_id(value: Any) -> Optional[str]:
    if not isinstance(value, str) or _JOB_ID_RE.fullmatch(value) is None:
        return None
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
    if address is not None and address.is_multicast:
        raise ValidationError(f"{field} must use a public unicast address")
    return text


def _validate_image_url(value: Any, *, allowed_hosts: set[str], resolve_dns: bool = True) -> str:
    if not isinstance(value, str) or value != value.strip():
        raise ValidationError("image URL contains a browser-normalized path")
    text = _validate_url(value, "image_url")
    if any(ord(char) <= 0x20 or ord(char) == 0x7F for char in text):
        raise ValidationError("image URL contains browser-normalized path ambiguity")
    if "\\" in text or re.search(r"%5c", text, re.IGNORECASE):
        raise ValidationError("image URL contains browser-normalized path ambiguity")
    parsed = urlparse(text)
    for segment in parsed.path.split("/"):
        browser_dot_segment = re.sub(r"%2e", ".", segment, flags=re.IGNORECASE)
        if browser_dot_segment in {".", ".."}:
            raise ValidationError("image URL contains browser-normalized path ambiguity")
    hostname = str(parsed.hostname).lower()
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
        connectable = set()
        for raw_address in addresses:
            try:
                address = ipaddress.ip_address(str(raw_address).split("%", 1)[0])
            except ValueError:
                raise ValidationError("image URL resolved to an invalid address") from None
            embedded = _embedded_ipv4(address)
            if embedded is not None:
                # NAT64 등: 감싸인 실제 IPv4로 판정하고, 연결 대상에서는 제외한다.
                if not embedded.is_global or embedded.is_multicast:
                    raise ValidationError(
                        "image URL must not resolve to a private or local address"
                    )
                continue
            if not address.is_global:
                raise ValidationError("image URL must not resolve to a private or local address")
            if address.is_multicast:
                raise ValidationError("image URL must resolve to a public unicast address")
            connectable.add(address)
        # 모든 응답이 IPv4-embedded일 수 있다(DNS64 전용 네트워크). 그 경우에도
        # 위에서 감싸인 IPv4가 공인임을 확인했고, 발행기가 pinned IPv4로 접속하므로
        # 여기서 추가로 막지 않는다.
    return text


def _extract_markdown_images(content: str) -> list[Dict[str, str]]:
    visible_lines: list[str] = []
    probe_fence: Optional[str] = None
    probe_fence_lines: list[str] = []
    for line in _markdown_lines(content):
        if probe_fence is None:
            opening = _opening_fence(line)
            if opening is not None:
                probe_fence = opening
                probe_fence_lines = [line]
                continue
            visible_lines.append(line)
            continue
        probe_fence_lines.append(line)
        if _is_closing_fence(line, probe_fence):
            probe_fence = None
            probe_fence_lines = []
    if probe_fence is not None:
        visible_lines.extend(probe_fence_lines)
    visible_content = "\n".join(visible_lines)
    if _RAW_NETWORK_HTML_RE.search(visible_content):
        raise ValidationError("raw HTML network resources are not allowed in Tistory content")
    if _REFERENCE_IMAGE_RE.search(visible_content):
        raise ValidationError("reference-style images are not allowed in Tistory content")
    if probe_fence is not None:
        raise ValidationError("unclosed fenced code block in Tistory content")

    images: list[Dict[str, str]] = []
    section = "lead"
    fence: Optional[str] = None
    for line in _markdown_lines(content):
        if fence is None:
            opening = _opening_fence(line)
            if opening is not None:
                fence = opening
                continue
        else:
            if _is_closing_fence(line, fence):
                fence = None
            continue
        if line.startswith("    ") or line.startswith("\t"):
            continue
        if _RAW_NETWORK_HTML_RE.search(line):
            raise ValidationError("raw HTML network resources are not allowed in Tistory content")
        if _REFERENCE_IMAGE_RE.search(line):
            raise ValidationError("reference-style images are not allowed in Tistory content")
        heading = re.match(r"^##\s+(.+?)\s*$", line)
        if heading:
            section = heading.group(1)
        matches = list(_MARKDOWN_IMAGE_RE.finditer(line))
        remainder = _MARKDOWN_IMAGE_RE.sub("", line)
        if "![" in remainder:
            raise ValidationError("unsupported or malformed image syntax in Tistory content")
        for match in matches:
            images.append({
                "alt": match.group(1).strip(),
                "url": (match.group(2) or match.group(3)).strip(),
                "section": section,
            })
    if fence is not None:
        raise ValidationError("unclosed fenced code block in Tistory content")
    return images


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
    elif service == "publisher":
        valid = text == _DEFAULT_PUBLISHER_API_BASE
    else:
        valid = parsed.scheme == "https" and parsed.hostname == _EXPECTED_SUPABASE_HOST and parsed.port is None and parsed.path in {"", "/"}
    if not valid:
        raise ValidationError(f"untrusted {service} origin")
    return text


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _read_content_source(value: Any, *, expected_sha256: Any = None) -> str:
    """Read a publish body from disk so long text is never retyped by an agent.

    Transcribing a multi-thousand-character body through a tool argument is a
    real corruption channel: a single mistyped Hangul syllable ships a typo to a
    public post. The only safe source is the exact file the pipeline produced,
    so this reader is deliberately strict — it refuses anything that is not a
    plain, owned, regular UTF-8 file, and it can verify a caller-supplied digest
    before the bytes are ever bound to a receipt.
    """
    if not isinstance(value, str) or not value.strip():
        raise ValidationError("content_file must be a non-empty path string")
    if len(value) > 4096:
        raise ValidationError("content_file path is too long")
    if _CONTROL_CHARS_RE.search(value) or "\x00" in value:
        raise ValidationError("content_file path contains control characters")
    path = Path(value).expanduser()
    if not path.is_absolute():
        raise ValidationError("content_file must be an absolute path")
    flags = os.O_RDONLY
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        fd = os.open(path, flags)
        with os.fdopen(fd, "rb", closefd=True) as stream:
            file_stat = os.fstat(stream.fileno())
            if not stat.S_ISREG(file_stat.st_mode):
                raise OSError("content_file is not a regular file")
            if hasattr(os, "geteuid") and file_stat.st_uid != os.geteuid():
                raise OSError("content_file is not owned by the current user")
            if file_stat.st_size > _MAX_CONTENT_FILE_BYTES:
                raise OSError("content_file exceeds the size limit")
            raw = stream.read(_MAX_CONTENT_FILE_BYTES + 1)
    except OSError as exc:
        raise ValidationError("content_file is not a readable regular file") from exc
    if len(raw) > _MAX_CONTENT_FILE_BYTES:
        raise ValidationError("content_file exceeds the size limit")
    if raw.startswith(b"\xef\xbb\xbf"):
        raw = raw[3:]
    try:
        text = raw.decode("utf-8")
    except UnicodeError as exc:
        raise ValidationError("content_file must be UTF-8 encoded") from exc
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if not text.strip():
        raise ValidationError("content_file is empty")
    if len(text) > _MAX_TEXT:
        raise ValidationError("content_file content exceeds the length limit")
    if _CONTROL_CHARS_RE.search(text):
        raise ValidationError("content_file contains control characters")
    if expected_sha256 is not None:
        if (
            not isinstance(expected_sha256, str)
            or _SHA256_RE.fullmatch(expected_sha256) is None
        ):
            raise ValidationError("content_sha256 must be a lowercase hex sha256 digest")
        actual = hashlib.sha256(text.encode("utf-8")).hexdigest()
        if not secrets.compare_digest(actual.encode("utf-8"), expected_sha256.encode("utf-8")):
            raise ValidationError("content_file does not match content_sha256")
    return text


def _resolve_payload_sources(payload: Any) -> Any:
    """Expand `content_file` into `content` before the closed contract check.

    The channel contracts stay untouched: by the time `_validate_payload` runs,
    a `content_file` payload is indistinguishable from an inline one, so both
    produce the same receipt binding and the same `payload_sha256`.
    """
    if not isinstance(payload, dict):
        return payload
    has_file = "content_file" in payload
    has_digest = "content_sha256" in payload
    if not has_file and not has_digest:
        return payload
    if has_digest and not has_file:
        raise ValidationError("content_sha256 requires content_file")
    if "content" in payload:
        raise ValidationError("content and content_file are mutually exclusive")
    resolved = {key: value for key, value in payload.items() if key not in {"content_file", "content_sha256"}}
    resolved["content"] = _read_content_source(
        payload["content_file"],
        expected_sha256=payload.get("content_sha256") if has_digest else None,
    )
    return resolved


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
            text = _nonempty(value, field)
            clean[field] = (
                _validate_content_contract(channel, operation, text)
                if field == "content"
                else text
            )
        elif field in {"cover_image"}:
            clean[field] = _validate_image_url(
                value, allowed_hosts=allowed_image_hosts, resolve_dns=resolve_image_hosts,
            )
        elif field in {"tags"}:
            if not isinstance(value, list) or len(value) > 50:
                raise ValidationError("tags must be a bounded string list")
            if channel != "tistory":
                clean[field] = [_nonempty(item, "tag").strip() for item in value]
                continue
            normalized_tags = []
            seen_tags = set()
            for item in value:
                tag = _nonempty(item, "tag").strip().lstrip("#").strip()
                if not tag or len(tag) > 30 or "/" in tag:
                    raise ValidationError("tag must be a public tag without namespaces")
                key = tag.casefold()
                if key not in seen_tags:
                    seen_tags.add(key)
                    normalized_tags.append(tag)
            if not 3 <= len(normalized_tags) <= 10:
                raise ValidationError("tistory requires 3 to 10 distinct tags")
            clean[field] = normalized_tags
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
    if "content" in clean:
        for image in _extract_markdown_images(clean["content"]):
            _validate_image_url(
                image["url"],
                allowed_hosts=allowed_image_hosts,
                resolve_dns=resolve_image_hosts,
            )
    return clean


def _request_json(
    method: str,
    url: str,
    *,
    headers: Dict[str, str],
    body: Optional[Dict[str, Any]] = None,
    timeout: int = 60,
    disable_proxy: bool = False,
) -> Any:
    data = None if body is None else _canonical(body)
    request = Request(url, data=data, method=method, headers=headers)
    handlers: list = [_NoRedirect()]
    if disable_proxy:
        handlers.insert(0, ProxyHandler({}))
    try:
        with build_opener(*handlers).open(request, timeout=timeout) as response:
            raw = response.read()
            if not 200 <= response.status < 300:
                raise TransportError(f"HTTP {response.status}", uncertain=response.status >= 500)
    except HTTPError as exc:
        raise TransportError(f"HTTP {exc.code}", uncertain=exc.code >= 500) from None
    except IncompleteRead:
        raise TransportError("remote response was truncated", uncertain=True) from None
    except HTTPException:
        raise TransportError("remote response was malformed", uncertain=True) from None
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

    def find_active_optional(self, topic: str, channel: str) -> Optional[Dict[str, Any]]:
        query = urlencode({
            "select": "id,post_id,url,note_path",
            "topic": "eq." + topic,
            "channel": "eq." + channel,
            "deleted_at": "is.null",
            "order": "published_at.desc",
            "limit": "2",
        })
        rows = _request_json("GET", self.endpoint + "?" + query, headers=self._headers(), timeout=self.timeout)
        if not isinstance(rows, list):
            raise ValidationError("invalid active ledger response")
        if not rows:
            return None
        if len(rows) != 1 or not isinstance(rows[0], dict):
            raise ValidationError("multiple active ledger posts found")
        ledger_id = rows[0].get("id")
        if isinstance(ledger_id, bool) or not isinstance(ledger_id, (int, str)) or str(ledger_id).strip() == "":
            raise ValidationError("active ledger row has no id")
        post_id = rows[0].get("post_id")
        return {
            "id": ledger_id, "post_id": post_id,
            "url": rows[0].get("url"), "note_path": rows[0].get("note_path"),
        }

    def find_active(self, topic: str, channel: str) -> Dict[str, Any]:
        row = self.find_active_optional(topic, channel)
        if row is None:
            raise ValidationError("no active ledger post found")
        if not isinstance(row.get("post_id"), str) or not row["post_id"]:
            raise ValidationError("active ledger row has no post_id")
        row["url"] = _validate_url(row.get("url"), "active ledger row url")
        return row

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
        try:
            self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
            root_stat = self.root.lstat()
            if stat.S_ISLNK(root_stat.st_mode) or not stat.S_ISDIR(root_stat.st_mode):
                raise OSError("receipt root is not a real directory")
            if hasattr(os, "geteuid") and root_stat.st_uid != os.geteuid():
                raise OSError("receipt root is not owned by the current user")
            os.chmod(self.root, 0o700)
            if stat.S_IMODE(self.root.lstat().st_mode) != 0o700:
                raise OSError("receipt root mode is not 0700")
        except OSError as exc:
            raise ReceiptError("cannot secure receipt root") from exc
        self._signing_key = secrets.token_bytes(32)

    def _signature(self, receipt: Dict[str, Any]) -> str:
        body = {key: value for key, value in receipt.items() if key != "receipt_hmac"}
        return hmac.new(self._signing_key, _canonical(body), hashlib.sha256).hexdigest()

    def _path(self, receipt_id: str) -> Path:
        if not isinstance(receipt_id, str) or _RECEIPT_RE.fullmatch(receipt_id) is None:
            raise ReceiptError("invalid receipt id")
        return self.root / (receipt_id + ".json")

    def _read_receipt_file(self, path: Path) -> Dict[str, Any]:
        flags = os.O_RDONLY
        if hasattr(os, "O_CLOEXEC"):
            flags |= os.O_CLOEXEC
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        try:
            fd = os.open(path, flags)
            with os.fdopen(fd, "rb", closefd=True) as stream:
                file_stat = os.fstat(stream.fileno())
                if not stat.S_ISREG(file_stat.st_mode):
                    raise OSError("receipt is not a regular file")
                if hasattr(os, "geteuid") and file_stat.st_uid != os.geteuid():
                    raise OSError("receipt is not owned by the current user")
                if stat.S_IMODE(file_stat.st_mode) != 0o600:
                    raise OSError("receipt mode is not 0600")
                if file_stat.st_size > 2 * 1024 * 1024:
                    raise OSError("receipt exceeds size limit")
                raw = stream.read(2 * 1024 * 1024 + 1)
            if len(raw) > 2 * 1024 * 1024:
                raise OSError("receipt exceeds size limit")
            receipt = json.loads(raw.decode("utf-8"))
            if not isinstance(receipt, dict):
                raise ValueError("receipt is not an object")
            return receipt
        except (OSError, UnicodeError, ValueError, TypeError) as exc:
            raise ReceiptError("invalid receipt file") from exc

    @contextmanager
    def _named_lock(self, name: str):
        lock_path = self.root / (name + ".lock")
        flags = os.O_CREAT | os.O_RDWR
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        fd = os.open(lock_path, flags, 0o600)
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "a+b", closefd=True) as stream:
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)

    @contextmanager
    def _lock(self, receipt_id: str):
        with self._named_lock(self._path(receipt_id).stem):
            yield

    @contextmanager
    def mutation_lock(self, *, channel: str, topic: str):
        lock_id = hashlib.sha256(
            _canonical({"channel": channel, "topic": topic})
        ).hexdigest()
        with self._named_lock("target-" + lock_id):
            yield

    def _authorization_path(
        self, *, session_digest: str, user_message_id: int,
    ) -> Path:
        if re.fullmatch(r"[0-9a-f]{64}", session_digest) is None:
            raise ApprovalError("invalid authorization session binding")
        if not isinstance(user_message_id, int) or isinstance(user_message_id, bool):
            raise ApprovalError("invalid authorization message binding")
        claim_id = hashlib.sha256(_canonical({
            "session_sha256": session_digest,
            "user_message_id": user_message_id,
        })).hexdigest()
        return self.root / f"authorization-{claim_id}.claim"

    def _read_authorization_claim(
        self, path: Path, *, session_digest: str, user_message_id: int,
    ) -> Dict[str, Any]:
        claim = self._read_receipt_file(path)
        if (
            claim.get("kind") != "authorization_claim"
            or claim.get("session_sha256") != session_digest
            or claim.get("user_message_id") != user_message_id
            or not isinstance(claim.get("receipt_id"), str)
            or _RECEIPT_RE.fullmatch(claim["receipt_id"]) is None
        ):
            raise ReceiptError("invalid authorization claim")
        return claim

    def _write_authorization_claim(self, path: Path, claim: Dict[str, Any]) -> None:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        if hasattr(os, "O_CLOEXEC"):
            flags |= os.O_CLOEXEC
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        try:
            fd = os.open(path, flags, 0o600)
        except FileExistsError:
            raise ApprovalError(
                "this persisted user authorization was already used for another receipt"
            ) from None
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "wb", closefd=True) as stream:
                stream.write(_canonical(claim))
                stream.flush()
                os.fsync(stream.fileno())
            if stat.S_IMODE(path.lstat().st_mode) != 0o600:
                raise OSError("authorization claim mode is not 0600")
            directory_flags = os.O_RDONLY
            if hasattr(os, "O_CLOEXEC"):
                directory_flags |= os.O_CLOEXEC
            if hasattr(os, "O_DIRECTORY"):
                directory_flags |= os.O_DIRECTORY
            directory_fd = os.open(self.root, directory_flags)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        except Exception:
            try:
                os.close(fd)
            except OSError:
                pass
            raise

    def claim_with_authorization(
        self,
        receipt_id: str,
        expected_state: str,
        next_state: str,
        *,
        session_digest: str,
        user_message_id: int,
        authorization_kind: str,
        validator: Callable[[Dict[str, Any]], None],
        authoritative_message_validator: Optional[Callable[[], None]] = None,
        authoritative_claim_executor: Optional[
            Callable[[Callable[[], Dict[str, Any]]], Dict[str, Any]]
        ] = None,
        **updates: Any,
    ) -> Dict[str, Any]:
        authorization_path = self._authorization_path(
            session_digest=session_digest,
            user_message_id=user_message_id,
        )
        with self._lock(receipt_id):
            receipt = self.load(receipt_id, require_state=expected_state)
            validator(receipt)
            with self._named_lock(authorization_path.stem):
                def claim() -> Dict[str, Any]:
                    try:
                        authorization_path.lstat()
                    except FileNotFoundError:
                        pass
                    else:
                        self._read_authorization_claim(
                            authorization_path,
                            session_digest=session_digest,
                            user_message_id=user_message_id,
                        )
                        raise ApprovalError(
                            "this persisted user authorization was already used for another receipt"
                        )
                    self._write_authorization_claim(authorization_path, {
                        "kind": "authorization_claim",
                        "authorization_kind": authorization_kind,
                        "session_sha256": session_digest,
                        "user_message_id": user_message_id,
                        "receipt_id": receipt_id,
                        "created_at": int(time.time()),
                    })
                    return self.transition(receipt, next_state, **updates)

                if authoritative_claim_executor is not None:
                    return authoritative_claim_executor(claim)
                if authoritative_message_validator is not None:
                    authoritative_message_validator()
                return claim()

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
            if stat.S_IMODE(target.lstat().st_mode) != 0o600:
                raise OSError("receipt mode is not 0600 after replace")
            directory_flags = os.O_RDONLY
            if hasattr(os, "O_CLOEXEC"):
                directory_flags |= os.O_CLOEXEC
            if hasattr(os, "O_DIRECTORY"):
                directory_flags |= os.O_DIRECTORY
            directory_fd = os.open(self.root, directory_flags)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
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
            # `planned`는 외부 변경 0건인 읽기 전용 프리뷰다. 여기에 만료를 걸면
            # 사용자가 본문을 읽거나 운영자가 원인을 고치는 시간이 그대로 실행
            # 권한을 태운다(2026-08-24 같은 발행 건에서 3회 만료). 짧은 창은
            # 승인 시점에 열린다 — `_execution_deadline` 참조.
            "expires_at": _NO_EXPIRY,
        }
        self._write(receipt)
        return receipt

    def _execution_deadline(self) -> int:
        """승인/확인 시점부터 시작하는 실행 창의 절대 만료 시각."""
        return int(time.time()) + self.ttl_seconds

    def load(self, receipt_id: str, *, require_state: Optional[str] = None) -> Dict[str, Any]:
        path = self._path(receipt_id)
        try:
            receipt = self._read_receipt_file(path)
        except ReceiptError:
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

    def assert_no_reconciliation(self, *, channel: str, topic: str) -> None:
        """Block a new mutation receipt while the same target has unresolved outcome.

        Terminal reconciliation receipts remain useful after a gateway restart even
        though their process-local HMAC can no longer authorize an operation.  The
        receipt directory is private (0700; files 0600), so this scan uses only the
        non-secret routing fields and never treats a raw file as an authorization.
        """
        for path in self.root.glob("*.json"):
            receipt = self._read_receipt_file(path)
            if receipt.get("receipt_id") != path.stem:
                raise ReceiptError("invalid receipt file")
            if not all(
                isinstance(receipt.get(field), str) and receipt.get(field)
                for field in ("state", "channel", "topic")
            ):
                raise ReceiptError("invalid receipt file")
            if not (
                secrets.compare_digest(
                    str(receipt.get("channel") or "").encode("utf-8"),
                    channel.encode("utf-8"),
                )
                and secrets.compare_digest(
                    str(receipt.get("topic") or "").encode("utf-8"),
                    topic.encode("utf-8"),
                )
            ):
                continue
            state = receipt.get("state")
            if state == "reconciliation_required":
                raise ReceiptError(
                    "unresolved reconciliation blocks a new mutation receipt"
                )
            if state == "dispatching":
                raise ReceiptError(
                    "unresolved mutation blocks a new mutation receipt"
                )

    def list_reconciliations(self) -> list:
        """Return the receipts that currently block new mutations.

        Read-only and approval-free: an operator must be able to see what is stuck
        before deciding how to resolve it.  Only non-secret routing fields are
        exposed — never the HMAC or the raw payload.
        """
        blocking = []
        for path in sorted(self.root.glob("*.json")):
            try:
                receipt = self._read_receipt_file(path)
            except ReceiptError:
                continue
            if receipt.get("receipt_id") != path.stem:
                continue
            state = receipt.get("state")
            if state not in ("reconciliation_required", "dispatching"):
                continue
            result = receipt.get("result")
            result = result if isinstance(result, dict) else {}
            blocking.append({
                "receipt_id": str(receipt.get("receipt_id") or ""),
                "state": str(state),
                "channel": str(receipt.get("channel") or ""),
                "operation": str(receipt.get("operation") or ""),
                "topic": str(receipt.get("topic") or ""),
                "note_path": str(receipt.get("note_path") or ""),
                "url": result.get("url"),
                "post_id": result.get("post_id"),
                "job_id": result.get("job_id"),
                "error": result.get("error"),
                "issued_at": receipt.get("issued_at"),
            })
        return blocking

    def resolve_reconciliation(
        self,
        receipt_id: str,
        *,
        resolution: str,
        evidence: str = "",
        ledger: Any = None,
        approval_digest: str,
        approval_message_id: int,
    ) -> Dict[str, Any]:
        """Close a stuck receipt so the channel can publish again.

        Deliberately does NOT go through `load()`.  The HMAC signing key lives only
        in the gateway process, so a restart invalidates every prior signature —
        while `assert_no_reconciliation` keeps blocking from the file alone.  Going
        through `load()` here would leave restarted receipts permanently blocking
        yet impossible to resolve, which is exactly the state that forced hand-editing
        the receipt JSON on 2026-08-24.

        The HMAC proves *authority to execute*, and resolution is not execution — it
        is closing a mutation that already ended.  Safety here comes from the explicit
        later-turn user approval and the operator's verification of the external
        state, both enforced by the caller.  File structure and routing fields are
        still validated, so a tampered or unrelated file is rejected.
        """
        path = self._path(receipt_id)
        receipt = self._read_receipt_file(path)
        if receipt.get("receipt_id") != receipt_id:
            raise ReceiptError("receipt binding mismatch")
        if not all(
            isinstance(receipt.get(field), str) and receipt.get(field)
            for field in ("state", "channel", "topic")
        ):
            raise ReceiptError("invalid receipt file")
        if receipt.get("state") not in ("reconciliation_required", "dispatching"):
            raise ReceiptError("receipt is not awaiting reconciliation")
        if resolution not in _RESOLUTIONS:
            raise ReceiptError("unknown reconciliation resolution")

        terminal = (
            "resolved_no_external_change"
            if resolution == _RESOLUTION_NO_CHANGE
            else "resolved_external_change_recorded"
        )
        receipt["state"] = terminal
        receipt["resolution"] = resolution
        receipt["resolved_at"] = int(time.time())
        receipt["resolution_evidence"] = str(evidence or "")[:_MAX_TEXT]
        receipt["resolution_approval_sha256"] = approval_digest
        receipt["resolution_message_id"] = approval_message_id
        if ledger is not None:
            receipt["resolution_ledger"] = ledger
        self._write(receipt)
        return receipt

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
        status = {
            "receipt_id": receipt_id,
            "state": receipt.get("state"),
            "channel": receipt.get("channel"),
            "operation": receipt.get("operation"),
            "expires_at": receipt.get("expires_at"),
            "result": receipt.get("result"),
        }
        # 해소된 영수증은 무엇을 근거로 종결했는지 함께 보여준다. 이 기록이
        # 없으면 나중에 "왜 풀렸는지" 확인할 방법이 파일을 직접 여는 것뿐이다.
        if receipt.get("resolution"):
            status["resolution"] = receipt.get("resolution")
            status["resolved_at"] = receipt.get("resolved_at")
            status["resolution_evidence"] = receipt.get("resolution_evidence")
            if receipt.get("resolution_ledger") is not None:
                status["resolution_ledger"] = receipt.get("resolution_ledger")
        return status


class PublishingRuntime:
    def __init__(
        self,
        *,
        receipt_root: Path,
        webhook_base_url: str,
        webhook_token: str,
        ledger: SupabaseLedger,
        publisher_api_base_url: Optional[str] = None,
        publisher_api_token: Optional[str] = None,
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
        if publisher_api_base_url is None and publisher_api_token is None:
            if not allow_test_origins:
                raise ValidationError("publisher API configuration is required")
        elif publisher_api_base_url is None or publisher_api_token is None:
            raise ValidationError("publisher API base URL and token must be configured together")
        self.publisher_api_base_url = (
            _validate_service_base(
                publisher_api_base_url,
                service="publisher",
                allow_test_origins=allow_test_origins,
            )
            if publisher_api_base_url is not None
            else None
        )
        self.publisher_api_token = (
            _nonempty(publisher_api_token, "publisher API token")
            if publisher_api_token is not None
            else None
        )
        self.ledger = ledger
        self.timeout = int(timeout)
        self.image_allowed_hosts = set(image_allowed_hosts or ({"img.test"} if allow_test_origins else {_EXPECTED_SUPABASE_HOST}))
        self.resolve_image_hosts = not allow_test_origins

    @classmethod
    def from_env(cls) -> "PublishingRuntime":
        token = os.getenv("SNS_WEBHOOK_TOKEN", "").strip()
        if not token:
            raise ValidationError("SNS_WEBHOOK_TOKEN is required")
        publisher_token = os.getenv("PUBLISHER_API_TOKEN", "").strip()
        if not publisher_token:
            raise ValidationError("PUBLISHER_API_TOKEN is required")
        home = Path(os.getenv("HERMES_HOME", str(Path.home() / ".hermes"))).expanduser()
        return cls(
            receipt_root=home / "state" / "donggu-publishing" / "receipts",
            webhook_base_url=_DEFAULT_WEBHOOK_BASE,
            webhook_token=token,
            publisher_api_base_url=os.getenv(
                "PUBLISHER_API_BASE_URL", _DEFAULT_PUBLISHER_API_BASE,
            ),
            publisher_api_token=publisher_token,
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
            channel, operation, _resolve_payload_sources(payload),
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
            with self.store.mutation_lock(channel=channel, topic=topic):
                self.store.assert_no_reconciliation(
                    channel=channel, topic=topic,
                )
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
        inline_images = _extract_markdown_images(clean.get("content", ""))
        image_urls = list(clean.get("image_urls", []))
        image_urls.extend(image["url"] for image in inline_images)
        preview["image_count"] = len(dict.fromkeys(image_urls))
        if inline_images:
            preview["inline_images"] = inline_images
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

    def list_reconciliations(self) -> list:
        """List receipts blocking new mutations. Read-only, no approval needed."""
        return self.store.list_reconciliations()

    def resolve_reconciliation(
        self,
        receipt_id: str,
        *,
        resolution: str,
        approval_text: str,
        session_id: str,
        turn_id: str,
        user_message_id: Any,
        evidence: str = "",
        url: str = "",
        post_id: str = "",
    ) -> Dict[str, Any]:
        """Close a stuck reconciliation receipt after explicit user approval.

        Without this path the only way to unblock a channel is hand-editing the
        receipt JSON, which bypasses every safety check.  A reconciliation means
        the external outcome is *unknown*, so the operator must state which
        outcome they verified:

          - `no_external_change`: nothing was published. The channel unblocks and
            the same payload can be re-published.
          - `external_change_recorded`: the mutation did happen. The caller must
            supply the real `url` and `post_id` so the ledger keeps a record
            instead of silently losing the post.
        """
        if resolution not in _RESOLUTIONS:
            raise ValidationError("unknown reconciliation resolution")
        # 해소는 발행/수정/삭제와 다른 행위이므로 전용 문구만 승인으로 인정한다.
        # `_APPROVAL_RE`는 발행 계열 동사 목록이라 여기서는 쓰지 않는다.
        if (
            not isinstance(approval_text, str)
            or not approval_text.strip()
            or len(approval_text) > _MAX_TEXT
        ):
            raise ApprovalError(
                "the current user message does not authorize a reconciliation resolution"
            )
        text = approval_text
        if _DENIAL_RE.search(text) or _NONFINAL_INTENT_RE.search(text):
            raise ApprovalError(
                "the current user message does not authorize a reconciliation resolution"
            )
        if _RESOLVE_APPROVAL_RE.search(text) is None:
            raise ApprovalError(
                "the approval message does not authorize a reconciliation resolution"
            )
        if any(
            pattern.search(text) is not None
            for pattern in _OPERATION_INTENT_RE.values()
        ):
            raise ApprovalError(
                "the approval message mixes reconciliation resolution with a publishing operation"
            )
        approval_message_id = _message_id(
            user_message_id, "trusted approval user message id",
        )
        _nonempty(session_id, "trusted session id")
        _nonempty(turn_id, "trusted turn id")

        ledger = None
        if resolution == _RESOLUTION_RECORDED:
            # 외부 변경이 있었다면 흔적을 남기지 않고 종결하지 않는다.
            ledger = {
                "url": _validate_url(url, "url"),
                "post_id": _nonempty(post_id, "post_id"),
            }

        receipt = self.store.resolve_reconciliation(
            receipt_id,
            resolution=resolution,
            evidence=evidence,
            ledger=ledger,
            approval_digest=hashlib.sha256(text.strip().encode("utf-8")).hexdigest(),
            approval_message_id=approval_message_id,
        )
        return {
            "receipt_id": receipt.get("receipt_id"),
            "state": receipt.get("state"),
            "resolution": receipt.get("resolution"),
            "channel": receipt.get("channel"),
            "topic": receipt.get("topic"),
            "ledger": receipt.get("resolution_ledger"),
        }

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

    def _verify_current_target(self, receipt: Dict[str, Any]) -> None:
        if receipt.get("operation") not in {"update", "delete"}:
            return
        approved = receipt.get("resolved")
        if not isinstance(approved, dict):
            raise ReceiptError("approved target binding is missing")
        current = self.ledger.find_active(
            str(receipt.get("topic") or ""),
            str(receipt.get("channel") or ""),
        )
        if not secrets.compare_digest(_sha256(approved), _sha256(current)):
            raise ReceiptError("approved target changed before dispatch")

    def approve(
        self, receipt_id: str, *, approval_text: str, session_id: str, turn_id: str,
        user_message_id: int,
        authoritative_message_validator: Optional[Callable[[], None]] = None,
        authoritative_claim_executor: Optional[
            Callable[[Callable[[], Dict[str, Any]]], Dict[str, Any]]
        ] = None,
    ) -> Dict[str, Any]:
        approval_text = _require_explicit_approval(approval_text)
        approval_message_id = _message_id(user_message_id, "trusted approval user message id")
        session_digest = hashlib.sha256(_nonempty(session_id, "trusted session id").encode("utf-8")).hexdigest()
        turn_digest = hashlib.sha256(_nonempty(turn_id, "trusted turn id").encode("utf-8")).hexdigest()

        def validate(receipt: Dict[str, Any]) -> None:
            self._verify_binding(receipt)
            _require_operation_approval(
                approval_text, str(receipt.get("operation") or ""),
            )
            if not secrets.compare_digest(str(receipt.get("session_sha256") or ""), session_digest):
                raise ApprovalError("approval must come from the preview session")
            if secrets.compare_digest(str(receipt.get("preview_turn_sha256") or ""), turn_digest):
                raise ApprovalError("approval must come from a later user turn")
            preview_message_id = receipt.get("preview_message_id")
            if not isinstance(preview_message_id, int) or approval_message_id <= preview_message_id:
                raise ApprovalError("approval must come from a newly persisted user message")

        receipt = self.store.claim_with_authorization(
            receipt_id,
            "planned",
            "approved",
            session_digest=session_digest,
            user_message_id=approval_message_id,
            authorization_kind="approve",
            validator=validate,
            authoritative_message_validator=authoritative_message_validator,
            authoritative_claim_executor=authoritative_claim_executor,
            approval_sha256=hashlib.sha256(approval_text.strip().encode("utf-8")).hexdigest(),
            approval_turn_sha256=turn_digest,
            approval_message_id=approval_message_id,
            # 실행 창은 승인 시점에 열린다. 프리뷰를 언제 만들었든 사용자가
            # `발행해`를 보낸 순간부터 짧은 창이 시작된다.
            expires_at=self.store._execution_deadline(),
        )
        return {"status": "approved", "receipt_id": receipt_id, "expires_at": receipt["expires_at"]}

    def confirm_irreversible(
        self, receipt_id: str, *, confirmation_text: str, session_id: str, turn_id: str,
        user_message_id: int,
        authoritative_message_validator: Optional[Callable[[], None]] = None,
        authoritative_claim_executor: Optional[
            Callable[[Callable[[], Dict[str, Any]]], Dict[str, Any]]
        ] = None,
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

        receipt = self.store.claim_with_authorization(
            receipt_id,
            "approved",
            "confirmed",
            session_digest=session_digest,
            user_message_id=confirmation_message_id,
            authorization_kind="confirm_maily",
            validator=validate,
            authoritative_message_validator=authoritative_message_validator,
            authoritative_claim_executor=authoritative_claim_executor,
            confirmation_sha256=hashlib.sha256(confirmation_text.strip().encode("utf-8")).hexdigest(),
            confirmation_turn_sha256=turn_digest,
            confirmation_message_id=confirmation_message_id,
            # Maily 최종 확인도 그 시점부터 실행 창을 다시 연다.
            expires_at=self.store._execution_deadline(),
        )
        return {"status": "confirmed", "receipt_id": receipt_id, "expires_at": receipt["expires_at"]}

    def execute(
        self, receipt_id: str, *, approval_text: str, session_id: str, turn_id: str,
        user_message_id: int,
        authoritative_message_validator: Optional[Callable[[], None]] = None,
        authoritative_claim_executor: Optional[
            Callable[[Callable[[], Dict[str, Any]]], Dict[str, Any]]
        ] = None,
    ) -> Dict[str, Any]:
        """Bind the approval and dispatch in one atomic call.

        `approve` followed by a separate `dispatch` leaves a gap where the caller can
        stall or interleave other work after the user's approval has already been
        consumed — in practice the execution window expired between the two calls
        (2026-08-24).  Nothing about that gap is a user decision point, so collapse it.

        Every guarantee of the two-step path is preserved: later-turn approval, verb
        matching the receipt operation, one-shot consumption, and Maily's separate
        irreversible-send confirmation (which still fails closed here).
        """
        self.approve(
            receipt_id,
            approval_text=approval_text,
            session_id=session_id,
            turn_id=turn_id,
            user_message_id=user_message_id,
            authoritative_message_validator=authoritative_message_validator,
            authoritative_claim_executor=authoritative_claim_executor,
        )
        return self.dispatch(receipt_id, session_id=session_id)

    def dispatch(self, receipt_id: str, *, session_id: str) -> Dict[str, Any]:
        observed = self.store.load(receipt_id)
        self._verify_binding(observed)
        channel = _nonempty(observed.get("channel"), "receipt channel")
        topic = _nonempty(observed.get("topic"), "receipt topic")
        with self.store.mutation_lock(channel=channel, topic=topic):
            self.store.assert_no_reconciliation(channel=channel, topic=topic)
            return self._dispatch_locked(receipt_id, session_id=session_id)

    def _dispatch_locked(self, receipt_id: str, *, session_id: str) -> Dict[str, Any]:
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

        try:
            self._verify_current_target(observed)
        except PublishingError as exc:
            result = {
                "status": "failed",
                "error": str(exc)[:1000],
                "receipt_id": receipt_id,
            }
            self.store.claim(
                receipt_id,
                expected_state,
                "failed",
                validator=validate,
                result=result,
                payload=None,
            )
            return result

        receipt = self.store.claim(
            receipt_id,
            expected_state,
            "dispatching",
            validator=validate,
        )
        try:
            self._verify_current_target(receipt)
        except PublishingError as exc:
            result = {
                "status": "failed",
                "error": str(exc)[:1000],
                "receipt_id": receipt_id,
            }
            self.store.transition(receipt, "failed", result=result, payload=None)
            return result
        channel = receipt["channel"]
        operation = receipt["operation"]
        webhook_payload = dict(receipt["payload"])
        real_publish = operation == "publish" and not (
            channel == "maily" and webhook_payload.get("dry_run") is True
        )
        external_operation = operation in {"publish", "update", "delete"}

        def require_reconciliation(
            error: str, *, url: Optional[str] = None, post_id: Optional[str] = None,
            job_id: Optional[str] = None,
        ) -> Dict[str, Any]:
            result = {
                "status": "reconciliation_required",
                "error": error[:1000],
                "receipt_id": receipt_id,
                "channel": channel,
                "operation": operation,
                "url": url,
                "post_id": post_id,
                "job_id": job_id,
            }
            if operation in {"update", "delete"}:
                resolved = receipt.get("resolved") or {}
                expected_url = resolved.get("url")
                expected_post_id = resolved.get("post_id")
                if url and url != expected_url:
                    result["observed_url"] = url
                if post_id and str(post_id) != str(expected_post_id):
                    result["observed_post_id"] = post_id
                result["url"] = expected_url
                result["post_id"] = expected_post_id
            self.store.transition(
                receipt, "reconciliation_required", result=result, payload=None,
            )
            return result
        if real_publish:
            try:
                existing = self.ledger.find_active_optional(receipt["topic"], channel)
            except PublishingError:
                result = {
                    "status": "failed",
                    "error": "ledger preflight failed; external mutation was not attempted",
                    "receipt_id": receipt_id,
                }
                self.store.transition(receipt, "failed", result=result, payload=None)
                return result
            if existing is not None:
                result = {
                    "status": "reconciliation_required",
                    "error": "active ledger post already exists; use update",
                    "receipt_id": receipt_id,
                    "channel": channel,
                    "operation": operation,
                    "url": existing.get("url"),
                    "post_id": existing.get("post_id"),
                }
                self.store.transition(
                    receipt, "reconciliation_required", result=result, payload=None,
                )
                return result
        key = (channel, operation)
        use_local_publisher = (
            key in _LOCAL_ENDPOINTS and self.publisher_api_base_url is not None
        )
        if use_local_publisher:
            publisher_base = self.publisher_api_base_url
            publisher_token = self.publisher_api_token
            assert publisher_base is not None and publisher_token is not None
            resolved = receipt.get("resolved") or {}
            request_body = _local_api_payload(
                operation,
                webhook_payload,
                post_id=resolved.get("post_id"),
            )
            request_url = publisher_base + _LOCAL_ENDPOINTS[key]
            headers = {
                "Content-Type": "application/json",
                "X-API-Token": publisher_token,
                "X-Idempotency-Key": receipt_id,
                "User-Agent": _PUBLISHER_USER_AGENT,
            }
        else:
            if operation in {"update", "delete"}:
                webhook_payload["post_id"] = receipt["resolved"]["post_id"]
            request_body = webhook_payload
            request_url = self.webhook_base_url + "/" + _ENDPOINTS[key]
            headers = {
                "Content-Type": "application/json",
                "X-SNS-Token": self.webhook_token,
                "X-Idempotency-Key": receipt_id,
                "User-Agent": _PUBLISHER_USER_AGENT,
            }
        try:
            response = _request_json(
                "POST",
                request_url,
                headers=headers,
                body=request_body,
                timeout=self.timeout,
                disable_proxy=use_local_publisher,
            )
        except TransportError as exc:
            if exc.uncertain and external_operation:
                return require_reconciliation(str(exc))
            state = "failed"
            result = {
                "status": state,
                "error": str(exc),
                "receipt_id": receipt_id,
                "channel": channel,
                "operation": operation,
            }
            self.store.transition(receipt, state, result=result, payload=None)
            return result
        if not isinstance(response, dict):
            if external_operation:
                return require_reconciliation("publisher returned a non-object response")
            result = {"status": "failed", "error": "publisher reported failure", "receipt_id": receipt_id}
            self.store.transition(receipt, "failed", result=result, payload=None)
            return result
        if response.get("success") is not True:
            remote_error = response.get("error")
            error = (
                remote_error[:1000]
                if isinstance(remote_error, str) and remote_error.strip()
                else "publisher reported failure"
            )
            if operation in {"publish", "update", "delete"}:
                external_url = None
                external_post_id = None
                external_job_id = _optional_job_id(response.get("job_id"))
                has_external_identifiers = external_job_id is not None
                if operation in {"publish", "update"}:
                    try:
                        external_url = _validate_url(response.get("url"), "publisher url")
                        has_external_identifiers = True
                    except ValidationError:
                        pass
                    try:
                        candidate_post_id = response.get("post_id")
                        if channel in {"tistory", "threads"}:
                            external_post_id = _nonempty(
                                candidate_post_id, "publisher post_id",
                            )
                        elif isinstance(candidate_post_id, str) and candidate_post_id:
                            external_post_id = candidate_post_id
                        if external_post_id is not None:
                            has_external_identifiers = True
                    except ValidationError:
                        pass
                external_mutation_possible = (
                    response.get("external_mutation_possible") is True
                    or has_external_identifiers
                )
                if external_mutation_possible:
                    return require_reconciliation(
                        error, url=external_url, post_id=external_post_id,
                        job_id=external_job_id,
                    )
            result = {"status": "failed", "error": error, "receipt_id": receipt_id}
            self.store.transition(receipt, "failed", result=result, payload=None)
            return result

        result = {
            "status": "completed",
            "receipt_id": receipt_id,
            "channel": channel,
            "operation": operation,
            "url": response.get("url"),
            "post_id": response.get("post_id"),
            "job_id": _optional_job_id(response.get("job_id")),
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

        if operation == "update":
            expected_post_id = _nonempty(
                receipt["resolved"].get("post_id"), "approved update post_id",
            )
            expected_url = _validate_url(
                receipt["resolved"].get("url"), "approved update url",
            )
            if (
                not secrets.compare_digest(str(result.get("post_id") or ""), expected_post_id)
                or not secrets.compare_digest(str(result.get("url") or ""), expected_url)
            ):
                result.update({
                    "status": "reconciliation_required",
                    "error": "publisher updated a target that does not match the approved ledger post",
                    "expected_post_id": expected_post_id,
                    "expected_url": expected_url,
                })
                self.store.transition(
                    receipt, "reconciliation_required", result=result, payload=None,
                )
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
