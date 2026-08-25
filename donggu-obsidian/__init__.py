"""Hermes registration entrypoint for the dual-harness donggu Obsidian package."""
from __future__ import annotations

from functools import partial
from pathlib import Path

from .tools import (
    ACK_SCHEMA,
    APPLY_SCHEMA,
    FDE_ACK_SCHEMA,
    FDE_APPLY_SCHEMA,
    FDE_DAILY_CAPTURE_UPSERT_SCHEMA,
    FDE_PLAN_SCHEMA,
    FDE_READBACK_SCHEMA,
    FDE_RECEIPT_STATUS_SCHEMA,
    FDE_RECOVER_SCHEMA,
    FDE_RECOVERY_STATUS_SCHEMA,
    FDE_REVOKE_SCHEMA,
    LIFE_OS_FINALIZE_DAILY_SCHEMA,
    LIFE_OS_RECORD_SCHEMA,
    LIFE_OS_START_DAILY_SCHEMA,
    LIFE_OS_STATUS_SCHEMA,
    PLAN_SCHEMA,
    READBACK_SCHEMA,
    RECOVER_SCHEMA,
    RECEIPT_STATUS_SCHEMA,
    RECOVERY_STATUS_SCHEMA,
    REVOKE_SCHEMA,
    capture_trusted_discord_turn,
    handle_ack,
    handle_apply,
    handle_fde_ack,
    handle_fde_apply,
    handle_fde_daily_capture_upsert,
    handle_fde_plan,
    handle_fde_readback,
    handle_fde_receipt_status,
    handle_fde_recover,
    handle_fde_recovery_status,
    handle_fde_revoke,
    handle_life_os_finalize_daily,
    handle_life_os_record,
    handle_life_os_start_daily,
    handle_life_os_status,
    handle_plan,
    handle_readback,
    handle_recover,
    handle_receipt_status,
    handle_recovery_status,
    handle_revoke,
)


def register(ctx) -> None:
    summary_llm = getattr(ctx, "llm", None)
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
            "donggu_core_recover", RECOVER_SCHEMA, handle_recover,
            "Recover one interrupted apply without forward mutation replay.", "🛟",
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
        (
            "donggu_fde_community_recovery_status", FDE_RECOVERY_STATUS_SCHEMA,
            handle_fde_recovery_status,
            "Read the dedicated FDE Community journal state.", "🩺",
        ),
        (
            "donggu_fde_community_plan", FDE_PLAN_SCHEMA, handle_fde_plan,
            "Create a zero-write receipt for the fixed FDE Community separation manifest.", "🧪",
        ),
        (
            "donggu_fde_community_receipt_status", FDE_RECEIPT_STATUS_SCHEMA,
            handle_fde_receipt_status,
            "Inspect one FDE Community receipt without Vault mutation.", "🧾",
        ),
        (
            "donggu_fde_community_apply", FDE_APPLY_SCHEMA, handle_fde_apply,
            "Apply the fixed manifest after exact persisted approval.", "🏛️",
        ),
        (
            "donggu_fde_community_recover", FDE_RECOVER_SCHEMA, handle_fde_recover,
            "Recover an interrupted FDE Community transaction without replay.", "🛟",
        ),
        (
            "donggu_fde_community_readback", FDE_READBACK_SCHEMA, handle_fde_readback,
            "Verify all thirteen FDE Community paths after apply.", "🔎",
        ),
        (
            "donggu_fde_community_revoke", FDE_REVOKE_SCHEMA, handle_fde_revoke,
            "Revoke one planned FDE Community receipt.", "🚫",
        ),
        (
            "donggu_fde_community_ack", FDE_ACK_SCHEMA, handle_fde_ack,
            "Clean the matching committed FDE Community journal after read-back.", "✅",
        ),
        (
            "donggu_life_os_status", LIFE_OS_STATUS_SCHEMA, handle_life_os_status,
            "Read the current Life OS Daily state and next prompt.", "📋",
        ),
        (
            "donggu_life_os_start_daily", LIFE_OS_START_DAILY_SCHEMA, handle_life_os_start_daily,
            "Start a Life OS Daily flow and return its next prompt.", "🌅",
        ),
        (
            "donggu_life_os_record", LIFE_OS_RECORD_SCHEMA,
            partial(handle_life_os_record, summary_llm=summary_llm),
            "Commit one trusted Life OS Discord turn and return the next prompt.", "✍️",
        ),
        (
            "donggu_life_os_finalize_daily", LIFE_OS_FINALIZE_DAILY_SCHEMA,
            partial(handle_life_os_finalize_daily, summary_llm=summary_llm),
            "Retry one pending Life OS Daily AI summary.", "📝",
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
    ctx.register_tool(
        name="donggu_fde_daily_capture_upsert",
        toolset="fde_community_capture",
        schema=FDE_DAILY_CAPTURE_UPSERT_SCHEMA,
        handler=handle_fde_daily_capture_upsert,
        description="Create or compare-and-swap one authorized FDE Community daily Capture.",
        emoji="🗒️",
    )
    ctx.register_skill(
        name="life-os",
        path=Path(__file__).parent / "skills" / "life-os" / "SKILL.md",
        description="Record and resume Life OS Daily check-ins and captures.",
    )
    ctx.register_hook("pre_gateway_dispatch", capture_trusted_discord_turn)
