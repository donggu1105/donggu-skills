"""Hermes registration entrypoint for the dual-harness donggu Obsidian package."""
from __future__ import annotations

from .tools import (
    ACK_SCHEMA,
    APPLY_SCHEMA,
    PLAN_SCHEMA,
    READBACK_SCHEMA,
    RECEIPT_STATUS_SCHEMA,
    RECOVERY_STATUS_SCHEMA,
    REVOKE_SCHEMA,
    handle_ack,
    handle_apply,
    handle_plan,
    handle_readback,
    handle_receipt_status,
    handle_recovery_status,
    handle_revoke,
)


def register(ctx) -> None:
    registrations = [
        (
            "donggu_core_recovery_status", RECOVERY_STATUS_SCHEMA, handle_recovery_status,
            "Read the helper journal state without changing the Vault.", "🩺",
        ),
        (
            "donggu_core_plan", PLAN_SCHEMA, handle_plan,
            "Create a zero-write, absolute-expiry local receipt.", "🧪",
        ),
        (
            "donggu_core_receipt_status", RECEIPT_STATUS_SCHEMA, handle_receipt_status,
            "Inspect bounded private receipt state without mutation.", "🧾",
        ),
        (
            "donggu_core_apply", APPLY_SCHEMA, handle_apply,
            "Apply one receipt after exact persisted natural-language confirmation.", "🧠",
        ),
        (
            "donggu_core_readback", READBACK_SCHEMA, handle_readback,
            "Read actual after hashes through descriptor-relative paths.", "🔎",
        ),
        (
            "donggu_core_revoke", REVOKE_SCHEMA, handle_revoke,
            "Revoke a planned receipt without invoking the helper.", "🚫",
        ),
        (
            "donggu_core_ack", ACK_SCHEMA, handle_ack,
            "Clean a matching committed journal after verified read-back.", "✅",
        ),
    ]
    for name, schema, handler, description, emoji in registrations:
        ctx.register_tool(
            name=name,
            toolset="donggu_obsidian",
            schema=schema,
            handler=handler,
            description=description,
            emoji=emoji,
        )
