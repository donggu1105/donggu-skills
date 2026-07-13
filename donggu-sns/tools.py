"""Hermes tool schemas and handlers for donggu publishing."""
from __future__ import annotations

import json
import os
import threading
from typing import Any, Dict, Optional

from .runtime import PublishingError, PublishingRuntime


_RUNTIME: Optional[PublishingRuntime] = None
_RUNTIME_LOCK = threading.Lock()


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
        if message.get("role") == "user" and isinstance(message.get("content"), str):
            text = message["content"].strip()
            message_id = message.get("id")
            if text and isinstance(message_id, int) and message_id > 0:
                return message_id, text
    raise PublishingError("trusted Hermes user message is unavailable")


PREVIEW_SCHEMA = {
    "name": "donggu_publishing_preview",
    "description": "Validate and show the exact SNS payload without mutation. Show it to the user before approval.",
    "parameters": {
        "type": "object",
        "properties": {
            "channel": {"type": "string", "enum": ["tistory", "maily", "threads", "linkedin", "instagram"]},
            "operation": {"type": "string", "enum": ["publish", "update", "delete"]},
            "payload": {"type": "object"},
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
    return all(os.getenv(name, "").strip() for name in ("SNS_WEBHOOK_TOKEN", "SUPABASE_URL", "SUPABASE_SERVICE_KEY"))


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
