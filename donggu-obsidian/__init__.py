"""Hermes registration entrypoint for the dual-harness donggu Obsidian package."""
from __future__ import annotations

from .tools import (
    APPLY_SCHEMA,
    PLAN_SCHEMA,
    STATUS_SCHEMA,
    handle_apply,
    handle_plan,
    handle_recovery_status,
)


def register(ctx) -> None:
    ctx.register_tool(
        name="donggu_core_plan",
        toolset="donggu_obsidian",
        schema=PLAN_SCHEMA,
        handler=handle_plan,
        description="Run the crash-atomic helper in zero-write dry-run mode and bind the exact action to a receipt.",
        emoji="🧪",
    )
    ctx.register_tool(
        name="donggu_core_apply",
        toolset="donggu_obsidian",
        schema=APPLY_SCHEMA,
        handler=handle_apply,
        description="Commit a DB-claimed CORE action to the Vault; DB completion and journal acknowledgement remain mandatory.",
        emoji="🧠",
    )
    ctx.register_tool(
        name="donggu_core_recovery_status",
        toolset="donggu_obsidian",
        schema=STATUS_SCHEMA,
        handler=handle_recovery_status,
        description="Read the CORE helper's durable journal state without changing the Vault.",
        emoji="🩺",
    )
