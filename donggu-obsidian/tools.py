"""Hermes schemas and handlers for the native CORE and Life OS runtimes."""
from __future__ import annotations

from collections import OrderedDict
from datetime import date
import hashlib
import json
from pathlib import Path
import threading
import time
from typing import Any, Dict, Optional

from .runtime import (
    CoreActionRuntime,
    CoreApprovalError,
    CoreRuntimeError,
    LifeOSError,
    LifeOSRuntime,
)


_RUNTIME: Optional[CoreActionRuntime] = None
_RUNTIME_LOCK = threading.Lock()
_LIFE_OS_RUNTIME: Optional[LifeOSRuntime] = None
_LIFE_OS_RUNTIME_LOCK = threading.Lock()
_TRUSTED_TURN_TTL_SECONDS = 300.0
_TRUSTED_TURN_LIMIT = 256


class _TrustedTurnCache:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._turns: OrderedDict[tuple[str, ...], tuple[float, str]] = OrderedDict()

    def clear(self) -> None:
        with self._lock:
            self._turns.clear()

    def put(self, identity: tuple[str, ...], text: str) -> None:
        now = time.monotonic()
        with self._lock:
            self._prune(now)
            self._turns[identity] = (now, text)
            self._turns.move_to_end(identity)
            while len(self._turns) > _TRUSTED_TURN_LIMIT:
                self._turns.popitem(last=False)

    def consume(self, identity: tuple[str, ...]) -> str:
        now = time.monotonic()
        with self._lock:
            self._prune(now)
            captured = self._turns.pop(identity, None)
        if captured is None:
            raise CoreRuntimeError("trusted Discord turn is unavailable or mismatched")
        return captured[1]

    def _prune(self, now: float) -> None:
        while self._turns:
            _identity, (captured_at, _text) = next(iter(self._turns.items()))
            if now - captured_at <= _TRUSTED_TURN_TTL_SECONDS:
                break
            self._turns.popitem(last=False)


_TRUSTED_TURNS = _TrustedTurnCache()


def _runtime() -> CoreActionRuntime:
    global _RUNTIME
    if _RUNTIME is None:
        with _RUNTIME_LOCK:
            if _RUNTIME is None:
                _RUNTIME = CoreActionRuntime.from_package()
    return _RUNTIME


def _life_os_runtime() -> LifeOSRuntime:
    global _LIFE_OS_RUNTIME
    if _LIFE_OS_RUNTIME is None:
        with _LIFE_OS_RUNTIME_LOCK:
            if _LIFE_OS_RUNTIME is None:
                _LIFE_OS_RUNTIME = LifeOSRuntime.from_environment()
    return _LIFE_OS_RUNTIME


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
        if message.get("role") != "user":
            continue
        text = message.get("content")
        message_id = message.get("id")
        if not isinstance(text, str) or isinstance(message_id, bool) or not isinstance(message_id, int) or message_id <= 0:
            raise CoreRuntimeError("trusted Hermes user message is unavailable")
        return message_id, text
    raise CoreRuntimeError("trusted Hermes user message is unavailable")


def _latest_user_row_id(session_id: str) -> int:
    try:
        from hermes_state import SessionDB
        db = SessionDB()
        try:
            messages = db.get_messages(session_id)
        finally:
            db.close()
    except Exception as exc:
        raise CoreRuntimeError("trusted Hermes user row is unavailable") from exc
    for message in reversed(messages):
        if message.get("role") != "user":
            continue
        message_id = message.get("id")
        if isinstance(message_id, bool) or not isinstance(message_id, int) or message_id <= 0:
            raise CoreRuntimeError("trusted Hermes user row is unavailable")
        return message_id
    raise CoreRuntimeError("trusted Hermes user row is unavailable")


def _platform_name(value: Any) -> str:
    return str(getattr(value, "value", value) or "").strip().lower()


def _turn_identity(
    *, platform: str, chat_id: str, user_id: str, thread_id: str,
    profile: str, message_id: str, session_key: str,
) -> tuple[str, ...]:
    values = (platform, chat_id, user_id, thread_id, profile, message_id, session_key)
    if platform != "discord" or not chat_id or not user_id or not message_id or not session_key:
        raise CoreRuntimeError("trusted Discord source identity is unavailable")
    return values


def capture_trusted_discord_turn(*, event: Any, gateway: Any, **_kwargs: Any) -> None:
    """Capture only Discord's normalized author text before gateway preparation."""
    try:
        import discord

        raw = event.raw_message
        source = event.source
        if not isinstance(raw, discord.Message):
            return None
        platform = _platform_name(source.platform)
        message_id = str(event.message_id or "")
        if (
            platform != "discord"
            or message_id != str(raw.id)
            or message_id != str(source.message_id or "")
            or str(source.user_id or "") != str(raw.author.id)
            or bool(getattr(source, "is_bot", False))
            or bool(getattr(raw.author, "bot", False))
            or not isinstance(raw.content, str)
        ):
            return None
        text = raw.content.strip()
        if not text:
            return None
        session_key = gateway._session_key_for_source(source)
        if not isinstance(session_key, str) or not session_key:
            return None
        identity = _turn_identity(
            platform=platform,
            chat_id=str(source.chat_id or ""),
            user_id=str(source.user_id or ""),
            thread_id=str(source.thread_id or ""),
            profile=str(source.profile or ""),
            message_id=message_id,
            session_key=session_key,
        )
        _TRUSTED_TURNS.put(identity, text)
    except (AttributeError, CoreRuntimeError, ImportError, TypeError):
        return None
    return None


def _trusted_life_os_turn() -> tuple[int, str, str]:
    try:
        from gateway.session_context import get_session_env
    except Exception as exc:
        raise CoreRuntimeError("trusted Hermes session context is required") from exc
    context = {
        name: get_session_env(name, "")
        for name in (
            "HERMES_SESSION_PLATFORM", "HERMES_SESSION_CHAT_ID",
            "HERMES_SESSION_USER_ID", "HERMES_SESSION_THREAD_ID",
            "HERMES_SESSION_PROFILE", "HERMES_SESSION_MESSAGE_ID",
            "HERMES_SESSION_ID", "HERMES_SESSION_KEY",
        )
    }
    identity = _turn_identity(
        platform=context["HERMES_SESSION_PLATFORM"].strip().lower(),
        chat_id=context["HERMES_SESSION_CHAT_ID"],
        user_id=context["HERMES_SESSION_USER_ID"],
        thread_id=context["HERMES_SESSION_THREAD_ID"],
        profile=context["HERMES_SESSION_PROFILE"],
        message_id=context["HERMES_SESSION_MESSAGE_ID"],
        session_key=context["HERMES_SESSION_KEY"],
    )
    session_id = context["HERMES_SESSION_ID"]
    session_key = context["HERMES_SESSION_KEY"]
    if not session_id or not session_key:
        raise CoreRuntimeError("trusted Hermes session context is required")
    message_text = _TRUSTED_TURNS.consume(identity)
    row_id = _latest_user_row_id(session_id)
    key_material = json.dumps(
        {
            "chat_id": identity[1],
            "message_id": identity[5],
            "platform": identity[0],
            "row_id": row_id,
            "session_id": session_id,
            "session_key": identity[6],
            "user_id": identity[2],
        },
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )
    message_key = "hermes-discord:" + hashlib.sha256(key_material.encode("utf-8")).hexdigest()
    return row_id, message_text, message_key


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
RECOVER_SCHEMA = _receipt_schema(
    "donggu_core_recover",
    "Recover one interrupted applying receipt without approval text or forward apply.",
)
READBACK_SCHEMA = _receipt_schema(
    "donggu_core_readback", "Verify actual Vault after hashes through descriptor-relative receipt paths.",
)
REVOKE_SCHEMA = _receipt_schema(
    "donggu_core_revoke", "Revoke one still-planned receipt without calling the mutation helper.",
)
ACK_SCHEMA = {
    "name": "donggu_core_ack",
    "description": "Acknowledge a matching committed journal after DB completion and verified local read-back.",
    "parameters": {
        "type": "object",
        "properties": {
            "receipt_id": {"type": "string"},
            "completion_nonce": {"type": "string"},
        },
        "required": ["receipt_id", "completion_nonce"],
        "additionalProperties": False,
    },
}

_LIFE_OS_DATE_PROPERTY = {
    "type": "string",
    "pattern": r"^\d{4}-\d{2}-\d{2}$",
}

LIFE_OS_STATUS_SCHEMA = {
    "name": "donggu_life_os_status",
    "description": "Read the current Life OS Daily state and next prompt.",
    "parameters": {
        "type": "object",
        "properties": {"date": _LIFE_OS_DATE_PROPERTY},
        "additionalProperties": False,
    },
}

LIFE_OS_START_DAILY_SCHEMA = {
    "name": "donggu_life_os_start_daily",
    "description": "Start a Life OS Daily flow and return its next prompt.",
    "parameters": {
        "type": "object",
        "properties": {"date": _LIFE_OS_DATE_PROPERTY},
        "additionalProperties": False,
    },
}

LIFE_OS_RECORD_SCHEMA = {
    "name": "donggu_life_os_record",
    "description": "Commit one trusted Life OS Discord turn and return the next prompt.",
    "parameters": {
        "type": "object",
        "properties": {
            "operation": {
                "type": "string",
                "enum": ["answer", "skip", "pause", "resume", "capture", "free_record"],
            },
            "date": _LIFE_OS_DATE_PROPERTY,
            "follow_up_question": {"type": "string", "minLength": 1, "maxLength": 300},
            "attachment_paths": {
                "type": "array",
                "items": {"type": "string"},
                "maxItems": 10,
            },
        },
        "required": ["operation"],
        "additionalProperties": False,
    },
}


def _ok(payload: Dict[str, Any]) -> str:
    return json.dumps({"success": True, **payload}, ensure_ascii=False)


def _error(exc: Exception) -> str:
    return json.dumps({"success": False, "error": str(exc)}, ensure_ascii=False)


def _optional_iso_date(value: Any) -> Optional[date]:
    if value is None:
        return None
    return date.fromisoformat(value)


def handle_recovery_status(args: dict, **_kwargs) -> str:
    try:
        return _ok(_runtime().recovery_status(Path(str(args.get("vault_root") or ""))))
    except CoreRuntimeError as exc:
        return _error(exc)


def handle_plan(args: dict, **kwargs) -> str:
    try:
        session_id = _trusted_session_id(kwargs)
        message_id, message_text = _latest_trusted_user_message(session_id)
        runtime = _runtime()
        result = runtime.plan(
            Path(str(args.get("vault_root") or "")), args.get("envelope"),
            session_id=session_id,
            plan_message_id=message_id,
            latest_user_text=message_text,
        )
        try:
            latest_message_id, latest_message_text = _latest_trusted_user_message(session_id)
            if (latest_message_id, latest_message_text) != (message_id, message_text):
                raise CoreApprovalError("preview request was overtaken by a newer persisted user message")
        except CoreRuntimeError:
            runtime.revoke(result["receipt_id"])
            raise
        return _ok(result)
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
        message_id, message_text = _latest_trusted_user_message(session_id)
        return _ok(_runtime().apply(
            str(args.get("receipt_id") or ""), latest_user_text=message_text,
            session_id=session_id, user_message_id=message_id,
            latest_user_reader=lambda: _latest_trusted_user_message(session_id),
        ))
    except CoreRuntimeError as exc:
        return _error(exc)


def handle_recover(args: dict, **_kwargs) -> str:
    try:
        return _ok(_runtime().recover(str(args.get("receipt_id") or "")))
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
        return _ok(_runtime().ack(
            str(args.get("receipt_id") or ""),
            completion_nonce=str(args.get("completion_nonce") or ""),
        ))
    except CoreRuntimeError as exc:
        return _error(exc)


def handle_life_os_status(args: dict, **_kwargs) -> str:
    try:
        return _ok(_life_os_runtime().status(_optional_iso_date(args.get("date"))))
    except (CoreRuntimeError, LifeOSError, ValueError, TypeError) as exc:
        return _error(exc)


def handle_life_os_start_daily(args: dict, **_kwargs) -> str:
    try:
        return _ok(_life_os_runtime().start_daily(_optional_iso_date(args.get("date"))))
    except (CoreRuntimeError, LifeOSError, ValueError, TypeError) as exc:
        return _error(exc)


def handle_life_os_record(args: dict, **kwargs) -> str:
    try:
        _row_id, message_text, message_key = _trusted_life_os_turn()
        result = _life_os_runtime().record(
            str(args.get("operation") or ""),
            message_text=message_text,
            message_key=message_key,
            attachment_paths=tuple(Path(value) for value in args.get("attachment_paths") or ()),
            follow_up_question=args.get("follow_up_question"),
            target_date=_optional_iso_date(args.get("date")),
        )
        return _ok(result)
    except (CoreRuntimeError, LifeOSError, ValueError, TypeError) as exc:
        return _error(exc)
