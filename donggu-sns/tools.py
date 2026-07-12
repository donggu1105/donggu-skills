"""Hermes tool schemas and handlers for donggu publishing."""
from __future__ import annotations

import json
import os
from typing import Any, Dict

from .runtime import PublishingError, PublishingRuntime


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
        "properties": {"receipt_id": {"type": "string"}, "approval_text": {"type": "string"}},
        "required": ["receipt_id", "approval_text"],
        "additionalProperties": False,
    },
}

CONFIRM_SCHEMA = {
    "name": "donggu_publishing_confirm_maily",
    "description": "Record the second, later-turn confirmation for an already approved Maily real send.",
    "parameters": {
        "type": "object",
        "properties": {"receipt_id": {"type": "string"}, "confirmation_text": {"type": "string"}},
        "required": ["receipt_id", "confirmation_text"],
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


def handle_preview(args: dict, **_kw) -> str:
    try:
        return _ok(PublishingRuntime.from_env().preview(
            channel=str(args.get("channel") or ""), operation=str(args.get("operation") or ""),
            payload=args.get("payload"), topic=str(args.get("topic") or ""), note_path=str(args.get("note_path") or ""),
        ))
    except PublishingError as exc:
        return _error(exc)


def handle_approve(args: dict, **_kw) -> str:
    try:
        return _ok(PublishingRuntime.from_env().approve(
            str(args.get("receipt_id") or ""), approval_text=str(args.get("approval_text") or ""),
        ))
    except PublishingError as exc:
        return _error(exc)


def handle_confirm(args: dict, **_kw) -> str:
    try:
        return _ok(PublishingRuntime.from_env().confirm_irreversible(
            str(args.get("receipt_id") or ""), confirmation_text=str(args.get("confirmation_text") or ""),
        ))
    except PublishingError as exc:
        return _error(exc)


def handle_dispatch(args: dict, **_kw) -> str:
    try:
        return _ok(PublishingRuntime.from_env().dispatch(str(args.get("receipt_id") or "")))
    except PublishingError as exc:
        return _error(exc)


def handle_status(args: dict, **_kw) -> str:
    try:
        return _ok(PublishingRuntime.from_env().receipt_status(str(args.get("receipt_id") or "")))
    except PublishingError as exc:
        return _error(exc)
