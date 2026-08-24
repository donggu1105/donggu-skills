"""Hermes tool schemas and handlers for donggu publishing."""
from __future__ import annotations

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


def _normalize_trusted_user_message(content: str) -> str:
    """Strip platform metadata before applying publishing approval grammar.

    Discord persists a trusted user row as a triggering-message header followed
    by a display-name prefix. Those are transport metadata, not user intent.
    Only strip the sender prefix when the trusted header was present; a plain
    user message beginning with brackets must remain unchanged. A structured
    (non-string) row carries no approval grammar and must fail closed.
    """
    if not isinstance(content, str):
        return ""
    text = content.strip()
    if _TRIGGERING_HEADER_RE.match(text):
        text = _TRIGGERING_HEADER_RE.sub("", text, count=1)
        text = _SENDER_PREFIX_RE.sub("", text, count=1)
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
                    "`content_sha256` in place of `content` to load the body from disk."
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


def _trusted_context(kwargs: dict) -> tuple[str, str]:
    session_id = kwargs.get("session_id")
    turn_id = kwargs.get("turn_id")
    if not isinstance(turn_id, str) or not turn_id:
        try:
            from tools.approval import _approval_turn_id
            turn_id = _approval_turn_id.get()
        except Exception:
            turn_id = ""
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


def handle_status(args: dict, **_kw) -> str:
    try:
        return _ok(_runtime().receipt_status(str(args.get("receipt_id") or "")))
    except PublishingError as exc:
        return _error(exc)
