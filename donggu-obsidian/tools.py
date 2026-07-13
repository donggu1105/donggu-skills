"""Hermes schemas and handlers for the minimal native CORE receipt runtime."""
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


def _trusted_session_id(kwargs: dict) -> str:
    session_id = kwargs.get("session_id")
    if not isinstance(session_id, str) or not session_id:
        raise CoreRuntimeError("trusted Hermes session context is required")
    return session_id


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
            text = message["content"]
            message_id = message.get("id")
            if isinstance(message_id, int) and message_id > 0:
                return message_id, text
            raise CoreRuntimeError("trusted Hermes user message is unavailable")
    raise CoreRuntimeError("trusted Hermes user message is unavailable")


def _receipt_schema(name: str, description: str) -> Dict[str, Any]:
    return {
        "name": name,
        "description": description,
        "parameters": {
            "type": "object",
            "properties": {"receipt_id": {"type": "string"}},
            "required": ["receipt_id"],
            "additionalProperties": False,
        },
    }


RECOVERY_STATUS_SCHEMA = {
    "name": "donggu_core_recovery_status",
    "description": "Read the crash-atomic helper journal state before claiming a candidate.",
    "parameters": {
        "type": "object",
        "properties": {"vault_root": {"type": "string"}},
        "required": ["vault_root"],
        "additionalProperties": False,
    },
}

PLAN_SCHEMA = {
    "name": "donggu_core_plan",
    "description": "Run a zero-write helper dry-run and persist one expiring local receipt.",
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

RECEIPT_STATUS_SCHEMA = _receipt_schema(
    "donggu_core_receipt_status", "Inspect bounded private receipt state without mutation.",
)
APPLY_SCHEMA = _receipt_schema(
    "donggu_core_apply",
    "Apply one planned receipt only when the latest persisted user text is exactly 적용해줘.",
)
READBACK_SCHEMA = _receipt_schema(
    "donggu_core_readback", "Verify actual Vault after hashes through descriptor-relative receipt paths.",
)
REVOKE_SCHEMA = _receipt_schema(
    "donggu_core_revoke", "Revoke one still-planned receipt without calling the mutation helper.",
)
ACK_SCHEMA = _receipt_schema(
    "donggu_core_ack", "Acknowledge a matching committed journal after verified local read-back.",
)


def _ok(payload: Dict[str, Any]) -> str:
    return json.dumps({"success": True, **payload}, ensure_ascii=False)


def _error(exc: Exception) -> str:
    return json.dumps({"success": False, "error": str(exc)}, ensure_ascii=False)


def handle_recovery_status(args: dict, **_kwargs) -> str:
    try:
        return _ok(_runtime().recovery_status(Path(str(args.get("vault_root") or ""))))
    except CoreRuntimeError as exc:
        return _error(exc)


def handle_plan(args: dict, **_kwargs) -> str:
    try:
        return _ok(_runtime().plan(
            Path(str(args.get("vault_root") or "")), args.get("envelope"),
        ))
    except CoreRuntimeError as exc:
        return _error(exc)


def handle_receipt_status(args: dict, **_kwargs) -> str:
    try:
        return _ok(_runtime().receipt_status(str(args.get("receipt_id") or "")))
    except CoreRuntimeError as exc:
        return _error(exc)


def handle_apply(args: dict, **kwargs) -> str:
    try:
        session_id = _trusted_session_id(kwargs)
        _message_id, message_text = _latest_trusted_user_message(session_id)
        return _ok(_runtime().apply(
            str(args.get("receipt_id") or ""), latest_user_text=message_text,
        ))
    except CoreRuntimeError as exc:
        return _error(exc)


def handle_readback(args: dict, **_kwargs) -> str:
    try:
        return _ok(_runtime().readback(str(args.get("receipt_id") or "")))
    except CoreRuntimeError as exc:
        return _error(exc)


def handle_revoke(args: dict, **_kwargs) -> str:
    try:
        return _ok(_runtime().revoke(str(args.get("receipt_id") or "")))
    except CoreRuntimeError as exc:
        return _error(exc)


def handle_ack(args: dict, **_kwargs) -> str:
    try:
        return _ok(_runtime().ack(str(args.get("receipt_id") or "")))
    except CoreRuntimeError as exc:
        return _error(exc)
