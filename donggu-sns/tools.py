"""Hermes tool schemas and handlers for donggu publishing."""
from __future__ import annotations

import contextvars
import json
import os
import re
import threading
from typing import Any, Dict, Optional

from .runtime import PublishingError, PublishingRuntime


_RUNTIME: Optional[PublishingRuntime] = None
_RUNTIME_LOCK = threading.Lock()

_TRIGGERING_HEADER_RE = re.compile(
    r"^\[Triggering message id:\s*`[^`\r\n]+`[^\r\n]*\]\s*\r?\n\r?\n"
)
_SENDER_PREFIX_RE = re.compile(r"^\[[^\]\r\n]{1,200}\][ \t]*")
# A sender label must look like a display name, never like steering text that a
# strip could hide ("[하지 마] 발행해" must not become "발행해").
_UNSAFE_LABEL_RE = re.compile(
    r"취소|보류|나중|하지\s*마|하지\s*말|지\s*마|지\s*말|안\s*(?:돼|해|할래)|[?？]"
    r"|Recent channel messages|New message|IMPORTANT|INTERNAL|SYSTEM",
    re.IGNORECASE,
)


def _normalize_trusted_user_message(content: str) -> str:
    """Strip platform metadata before applying publishing approval grammar.

    Discord multi-user threads persist a trusted user row as an optional
    triggering-message header followed by a ``[display name]`` prefix. Those are
    transport metadata, not user intent. Hermes stopped persisting the header in
    Oct 2026, so the sender prefix is also stripped from a header-less row, but
    only when the row is a single line and the label cannot carry steering text.
    Everything after the label must still satisfy the full approval grammar.
    A structured (non-string) row carries no approval grammar and fails closed.
    """
    if not isinstance(content, str):
        return ""
    text = content.strip()
    if _TRIGGERING_HEADER_RE.match(text):
        text = _TRIGGERING_HEADER_RE.sub("", text, count=1)
        text = _SENDER_PREFIX_RE.sub("", text, count=1)
    elif "\n" not in text and "\r" not in text:
        label = _SENDER_PREFIX_RE.match(text)
        if label is not None and _UNSAFE_LABEL_RE.search(label.group(0)) is None:
            text = text[label.end():]
    return text.strip()


def _runtime() -> PublishingRuntime:
    global _RUNTIME
    if _RUNTIME is None:
        with _RUNTIME_LOCK:
            if _RUNTIME is None:
                _RUNTIME = PublishingRuntime.from_env()
    return _RUNTIME


def _latest_trusted_user_message(session_id: str) -> tuple[int, str]:
    try:
        from hermes_state import SessionDB
        db = SessionDB()
        try:
            messages = db.get_messages(session_id)
        finally:
            db.close()
    except Exception as exc:
        raise PublishingError("trusted Hermes user message is unavailable") from exc
    for message in reversed(messages):
        if message.get("role") != "user":
            continue
        message_id = message.get("id")
        content = message.get("content")
        normalized = _normalize_trusted_user_message(content)
        if (
            not isinstance(message_id, int)
            or isinstance(message_id, bool)
            or message_id <= 0
            or not isinstance(content, str)
            or not normalized
        ):
            raise PublishingError("latest trusted Hermes user message is invalid")
        return message_id, normalized
    raise PublishingError("trusted Hermes user message is unavailable")


def _authoritative_latest_message_executor(
    session_id: str, expected_message_id: int, expected_text: str,
):
    def execute(action):
        try:
            from hermes_state import SessionDB
            db = SessionDB()
            try:
                def claim_while_transcript_writes_are_locked(conn):
                    row = conn.execute(
                        "SELECT id, content FROM messages "
                        "WHERE session_id = ? AND role = 'user' AND active = 1 "
                        "ORDER BY id DESC LIMIT 1",
                        (session_id,),
                    ).fetchone()
                    if row is None:
                        raise PublishingError(
                            "trusted Hermes user message is unavailable"
                        )
                    message_id = row["id"]
                    content = db._decode_content(row["content"])
                    normalized = _normalize_trusted_user_message(content)
                    if (
                        not isinstance(message_id, int)
                        or isinstance(message_id, bool)
                        or message_id <= 0
                        or not isinstance(content, str)
                        or not normalized
                    ):
                        raise PublishingError(
                            "latest trusted Hermes user message is invalid"
                        )
                    if (
                        message_id != expected_message_id
                        or normalized != expected_text
                    ):
                        raise PublishingError(
                            "trusted Hermes user message changed before authorization claim"
                        )
                    return action()

                return db._execute_write(claim_while_transcript_writes_are_locked)
            finally:
                db.close()
        except PublishingError:
            raise
        except Exception as exc:
            raise PublishingError(
                "trusted Hermes user message is unavailable"
            ) from exc

    return execute


PREVIEW_SCHEMA = {
    "name": "donggu_publishing_preview",
    "description": (
        "Validate and show the exact SNS payload without mutation. Show it to the user "
        "before approval. For any long body, pass `content_file` (absolute path to the "
        "prepared .pub.md) instead of `content` so the exact disk bytes are published; "
        "retyping a long body into `content` risks silent character corruption. Add "
        "`content_sha256` to make the runtime verify those bytes."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "channel": {"type": "string", "enum": ["tistory", "maily", "threads", "linkedin", "instagram"]},
            "operation": {"type": "string", "enum": ["publish", "update", "delete"]},
            "payload": {
                "type": "object",
                "description": (
                    "Channel payload. Use `content_file` (absolute path) plus optional "
                    "`content_sha256` in place of `content` to load the body from disk. "
                    "Threads also accepts `topic_tag` (one, 1-50 chars) and `spoilers` "
                    "(verbatim body substrings to hide, max 10)."
                ),
            },
            "topic": {"type": "string"},
            "note_path": {"type": "string"},
        },
        "required": ["channel", "operation", "payload", "topic", "note_path"],
        "additionalProperties": False,
    },
}

APPROVE_SCHEMA = {
    "name": "donggu_publishing_approve",
    "description": "Bind explicit user approval to a previewed receipt. Call only in a later user turn after showing the preview.",
    "parameters": {
        "type": "object",
        "properties": {"receipt_id": {"type": "string"}},
        "required": ["receipt_id"],
        "additionalProperties": False,
    },
}

CONFIRM_SCHEMA = {
    "name": "donggu_publishing_confirm_maily",
    "description": "Record the second, later-turn confirmation for an already approved Maily real send.",
    "parameters": {
        "type": "object",
        "properties": {"receipt_id": {"type": "string"}},
        "required": ["receipt_id"],
        "additionalProperties": False,
    },
}

DISPATCH_SCHEMA = {
    "name": "donggu_publishing_dispatch",
    "description": "Dispatch only an approved receipt; Maily real send must already be separately confirmed.",
    "parameters": {
        "type": "object",
        "properties": {"receipt_id": {"type": "string"}},
        "required": ["receipt_id"],
        "additionalProperties": False,
    },
}

STATUS_SCHEMA = {
    "name": "donggu_publishing_receipt_status",
    "description": "Read the local state of a publishing receipt.",
    "parameters": {
        "type": "object",
        "properties": {"receipt_id": {"type": "string"}},
        "required": ["receipt_id"],
        "additionalProperties": False,
    },
}

EXECUTE_SCHEMA = {
    "name": "donggu_publishing_execute",
    "description": (
        "Bind the user's later-turn approval and dispatch the receipt in one atomic call. "
        "Preferred over calling approve then dispatch separately — nothing between those two "
        "steps is a user decision point, and the gap lets the execution window expire. "
        "Maily real sends still require donggu_publishing_confirm_maily first."
    ),
    "parameters": {
        "type": "object",
        "properties": {"receipt_id": {"type": "string"}},
        "required": ["receipt_id"],
        "additionalProperties": False,
    },
}

RECONCILIATION_LIST_SCHEMA = {
    "name": "donggu_publishing_list_reconciliations",
    "description": (
        "List publishing receipts stuck in reconciliation that block new publishes. "
        "Read-only; needs no approval. Use this to see what is blocking a channel."
    ),
    "parameters": {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    },
}

RECONCILIATION_RESOLVE_SCHEMA = {
    "name": "donggu_publishing_resolve_reconciliation",
    "description": (
        "Close a stuck reconciliation receipt after verifying the real external state, "
        "so the channel can publish again. Requires an explicit later-turn user approval "
        "such as '재조정 해소해줘'. Choose no_external_change only after confirming nothing "
        "was published; choose external_change_recorded with the real url and post_id when "
        "the mutation did happen."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "receipt_id": {"type": "string"},
            "resolution": {
                "type": "string",
                "enum": ["no_external_change", "external_change_recorded"],
            },
            "evidence": {
                "type": "string",
                "description": "How the external state was verified (URLs checked, HTTP codes, ledger rows).",
            },
            "url": {"type": "string", "description": "Required for external_change_recorded."},
            "post_id": {"type": "string", "description": "Required for external_change_recorded."},
        },
        "required": ["receipt_id", "resolution"],
        "additionalProperties": False,
    },
}


def check_requirements() -> bool:
    return all(os.getenv(name, "").strip() for name in (
        "SNS_WEBHOOK_TOKEN",
        "PUBLISHER_API_TOKEN",
        "SUPABASE_URL",
        "SUPABASE_SERVICE_KEY",
    ))


def _ok(payload: Dict[str, Any]) -> str:
    return json.dumps({"success": True, **payload}, ensure_ascii=False)


def _error(exc: Exception) -> str:
    return json.dumps({"success": False, "error": str(exc)}, ensure_ascii=False)


# Host-provided call identity, bound by the public ``tool_execution`` middleware
# for the duration of one donggu_publishing_* handler call. This replaces the old
# import of a Hermes-internal contextvar, which broke silently when Hermes moved it.
_HOST_CALL_CONTEXT: contextvars.ContextVar[tuple[str, str]] = contextvars.ContextVar(
    "donggu_publishing_host_call_context", default=("", "")
)
_TOOL_PREFIX = "donggu_publishing_"


def bind_host_call_context(*, tool_name: str = "", args: Any = None, next_call=None, **context: Any) -> Any:
    """``tool_execution`` middleware: expose Hermes' session/turn IDs to our handlers.

    Uses only the documented middleware contract (context kwargs + single-use
    ``next_call``). Other tools pass through untouched.
    """
    if not str(tool_name).startswith(_TOOL_PREFIX):
        return next_call(args)
    session_id = context.get("session_id")
    turn_id = context.get("turn_id")
    token = _HOST_CALL_CONTEXT.set((
        session_id if isinstance(session_id, str) else "",
        turn_id if isinstance(turn_id, str) else "",
    ))
    try:
        return next_call(args)
    finally:
        _HOST_CALL_CONTEXT.reset(token)


def _trusted_context(kwargs: dict) -> tuple[str, str]:
    session_id = kwargs.get("session_id")
    turn_id = kwargs.get("turn_id")
    host_session_id, host_turn_id = _HOST_CALL_CONTEXT.get()
    if not isinstance(turn_id, str) or not turn_id:
        turn_id = host_turn_id
    if not isinstance(session_id, str) or not session_id:
        session_id = host_session_id
    elif host_session_id and host_session_id != session_id:
        raise PublishingError("trusted Hermes session context is inconsistent")
    if not isinstance(session_id, str) or not session_id or not isinstance(turn_id, str) or not turn_id:
        raise PublishingError("trusted Hermes session/turn context is required")
    return session_id, turn_id


def handle_preview(args: dict, **kwargs) -> str:
    try:
        session_id, turn_id = _trusted_context(kwargs)
        message_id, _message_text = _latest_trusted_user_message(session_id)
        return _ok(_runtime().preview(
            channel=str(args.get("channel") or ""), operation=str(args.get("operation") or ""),
            payload=args.get("payload"), topic=str(args.get("topic") or ""), note_path=str(args.get("note_path") or ""),
            session_id=session_id, turn_id=turn_id, user_message_id=message_id,
        ))
    except PublishingError as exc:
        return _error(exc)


def handle_approve(args: dict, **kwargs) -> str:
    try:
        session_id, turn_id = _trusted_context(kwargs)
        message_id, message_text = _latest_trusted_user_message(session_id)
        return _ok(_runtime().approve(
            str(args.get("receipt_id") or ""), approval_text=message_text,
            session_id=session_id, turn_id=turn_id, user_message_id=message_id,
            authoritative_claim_executor=_authoritative_latest_message_executor(
                session_id, message_id, message_text,
            ),
        ))
    except PublishingError as exc:
        return _error(exc)


def handle_confirm(args: dict, **kwargs) -> str:
    try:
        session_id, turn_id = _trusted_context(kwargs)
        message_id, message_text = _latest_trusted_user_message(session_id)
        return _ok(_runtime().confirm_irreversible(
            str(args.get("receipt_id") or ""), confirmation_text=message_text,
            session_id=session_id, turn_id=turn_id, user_message_id=message_id,
            authoritative_claim_executor=_authoritative_latest_message_executor(
                session_id, message_id, message_text,
            ),
        ))
    except PublishingError as exc:
        return _error(exc)


def handle_dispatch(args: dict, **kwargs) -> str:
    try:
        session_id, _turn_id = _trusted_context(kwargs)
        return _ok(_runtime().dispatch(
            str(args.get("receipt_id") or ""), session_id=session_id,
        ))
    except PublishingError as exc:
        return _error(exc)


def handle_execute(args: dict, **kwargs) -> str:
    try:
        session_id, turn_id = _trusted_context(kwargs)
        message_id, message_text = _latest_trusted_user_message(session_id)
        return _ok(_runtime().execute(
            str(args.get("receipt_id") or ""), approval_text=message_text,
            session_id=session_id, turn_id=turn_id, user_message_id=message_id,
            authoritative_claim_executor=_authoritative_latest_message_executor(
                session_id, message_id, message_text,
            ),
        ))
    except PublishingError as exc:
        return _error(exc)


def handle_status(args: dict, **_kw) -> str:
    try:
        return _ok(_runtime().receipt_status(str(args.get("receipt_id") or "")))
    except PublishingError as exc:
        return _error(exc)


def handle_list_reconciliations(_args: dict, **_kw) -> str:
    try:
        blocking = _runtime().list_reconciliations()
        return _ok({"reconciliations": blocking, "count": len(blocking)})
    except PublishingError as exc:
        return _error(exc)


def handle_resolve_reconciliation(args: dict, **kwargs) -> str:
    try:
        session_id, turn_id = _trusted_context(kwargs)
        message_id, message_text = _latest_trusted_user_message(session_id)
        return _ok(_runtime().resolve_reconciliation(
            str(args.get("receipt_id") or ""),
            resolution=str(args.get("resolution") or ""),
            approval_text=message_text,
            session_id=session_id, turn_id=turn_id, user_message_id=message_id,
            evidence=str(args.get("evidence") or ""),
            url=str(args.get("url") or ""),
            post_id=str(args.get("post_id") or ""),
        ))
    except PublishingError as exc:
        return _error(exc)
