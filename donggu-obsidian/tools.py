"""Hermes tool schemas and handlers for CORE review Vault operations."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from .runtime import CoreActionRuntime, CoreRuntimeError


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
        "properties": {
            "receipt_id": {"type": "string"},
            "approval_text": {"type": "string", "description": "The exact valid single-candidate approval message."},
        },
        "required": ["receipt_id", "approval_text"],
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


def handle_plan(args: dict, **_kw) -> str:
    try:
        result = CoreActionRuntime.from_package().plan(
            Path(str(args.get("vault_root") or "")),
            args.get("envelope"),
        )
        return _ok(result)
    except CoreRuntimeError as exc:
        return _error(exc)


def handle_apply(args: dict, **_kw) -> str:
    try:
        result = CoreActionRuntime.from_package().apply(
            str(args.get("receipt_id") or ""),
            approval_text=str(args.get("approval_text") or ""),
        )
        return _ok(result)
    except CoreRuntimeError as exc:
        return _error(exc)


def handle_recovery_status(args: dict, **_kw) -> str:
    try:
        result = CoreActionRuntime.from_package().recovery_status(Path(str(args.get("vault_root") or "")))
        return _ok(result)
    except CoreRuntimeError as exc:
        return _error(exc)
