"""Hermes tool schemas and handlers for CORE review Vault operations."""
from __future__ import annotations

import json
from pathlib import Path
import threading
from typing import Any, Dict, Optional

from .runtime import CoreActionRuntime, CoreRuntimeError


_RUNTIME: Optional[CoreActionRuntime] = None
_RUNTIME_LOCK = threading.Lock()


def _runtime() -> CoreActionRuntime:
    global _RUNTIME
    if _RUNTIME is None:
        with _RUNTIME_LOCK:
            if _RUNTIME is None:
                _RUNTIME = CoreActionRuntime.from_package()
    return _RUNTIME


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
        raise CoreRuntimeError("trusted Hermes session/turn context is required")
    return session_id, turn_id


def _latest_trusted_user_message(session_id: str) -> tuple[int, str]:
    try:
        from hermes_state import SessionDB
        db = SessionDB()
        try:
            messages = db.get_messages(session_id)
        finally:
            db.close()
    except Exception as exc:
        raise CoreRuntimeError("trusted Hermes user message is unavailable") from exc
    for message in reversed(messages):
        if message.get("role") == "user" and isinstance(message.get("content"), str):
            text = message["content"].strip()
            message_id = message.get("id")
            if text and isinstance(message_id, int) and message_id > 0:
                return message_id, text
    raise CoreRuntimeError("trusted Hermes user message is unavailable")


PLAN_SCHEMA = {
    "name": "donggu_core_plan",
    "description": (
        "Run a zero-write dry-run for one exact CORE action envelope after recovery preflight and DB claim. "
        "Returns a short-lived receipt bound to the Vault root and envelope."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "vault_root": {"type": "string"},
            "envelope": {"type": "object"},
        },
        "required": ["vault_root", "envelope"],
        "additionalProperties": False,
    },
}

APPLY_SCHEMA = {
    "name": "donggu_core_apply",
    "description": (
        "Apply one preview receipt after the candidate has been claimed in the DB and the user approved that exact candidate. "
        "A successful Vault commit returns vault_committed_reconciliation_required; complete the DB row, verify after hashes, "
        "and acknowledge the committed journal before reporting final completion."
    ),
    "parameters": {
        "type": "object",
        "properties": {"receipt_id": {"type": "string"}},
        "required": ["receipt_id"],
        "additionalProperties": False,
    },
}

STATUS_SCHEMA = {
    "name": "donggu_core_recovery_status",
    "description": "Read the crash-atomic helper journal state before claiming any candidate.",
    "parameters": {
        "type": "object",
        "properties": {"vault_root": {"type": "string"}},
        "required": ["vault_root"],
        "additionalProperties": False,
    },
}


def _ok(payload: Dict[str, Any]) -> str:
    return json.dumps({"success": True, **payload}, ensure_ascii=False)


def _error(exc: Exception) -> str:
    return json.dumps({"success": False, "error": str(exc)}, ensure_ascii=False)


def handle_plan(args: dict, **kwargs) -> str:
    try:
        session_id, turn_id = _trusted_context(kwargs)
        message_id, _message_text = _latest_trusted_user_message(session_id)
        result = _runtime().plan(
            Path(str(args.get("vault_root") or "")),
            args.get("envelope"),
            session_id=session_id,
            turn_id=turn_id,
            user_message_id=message_id,
        )
        return _ok(result)
    except CoreRuntimeError as exc:
        return _error(exc)


def handle_apply(args: dict, **kwargs) -> str:
    try:
        session_id, turn_id = _trusted_context(kwargs)
        message_id, message_text = _latest_trusted_user_message(session_id)
        result = _runtime().apply(
            str(args.get("receipt_id") or ""),
            approval_text=message_text,
            session_id=session_id,
            turn_id=turn_id,
            user_message_id=message_id,
        )
        return _ok(result)
    except CoreRuntimeError as exc:
        return _error(exc)


def handle_recovery_status(args: dict, **_kw) -> str:
    try:
        result = _runtime().recovery_status(Path(str(args.get("vault_root") or "")))
        return _ok(result)
    except CoreRuntimeError as exc:
        return _error(exc)
