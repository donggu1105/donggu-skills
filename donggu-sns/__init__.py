"""Hermes registration entrypoint for the dual-harness donggu SNS package."""
from __future__ import annotations

from .tools import (
    APPROVE_SCHEMA,
    CONFIRM_SCHEMA,
    DISPATCH_SCHEMA,
    PREVIEW_SCHEMA,
    RECONCILIATION_LIST_SCHEMA,
    RECONCILIATION_RESOLVE_SCHEMA,
    STATUS_SCHEMA,
    check_requirements,
    handle_approve,
    handle_confirm,
    handle_dispatch,
    handle_list_reconciliations,
    handle_preview,
    handle_resolve_reconciliation,
    handle_status,
)


def register(ctx) -> None:
    required = [
        "SNS_WEBHOOK_TOKEN",
        "PUBLISHER_API_TOKEN",
        "SUPABASE_URL",
        "SUPABASE_SERVICE_KEY",
    ]
    registrations = [
        ("donggu_publishing_preview", PREVIEW_SCHEMA, handle_preview, "Validate and preview a closed SNS mutation.", "🔎"),
        ("donggu_publishing_approve", APPROVE_SCHEMA, handle_approve, "Bind later-turn approval to the preview receipt.", "✅"),
        ("donggu_publishing_confirm_maily", CONFIRM_SCHEMA, handle_confirm, "Record Maily's separate irreversible-send confirmation.", "✉️"),
        ("donggu_publishing_dispatch", DISPATCH_SCHEMA, handle_dispatch, "Dispatch an already approved and, when required, confirmed receipt.", "📣"),
        ("donggu_publishing_receipt_status", STATUS_SCHEMA, handle_status, "Inspect a publishing receipt without mutation.", "🧾"),
        ("donggu_publishing_list_reconciliations", RECONCILIATION_LIST_SCHEMA, handle_list_reconciliations, "List receipts blocking new publishes.", "🚧"),
        ("donggu_publishing_resolve_reconciliation", RECONCILIATION_RESOLVE_SCHEMA, handle_resolve_reconciliation, "Close a verified reconciliation so the channel unblocks.", "🔓"),
    ]
    for name, schema, handler, description, emoji in registrations:
        ctx.register_tool(
            name=name,
            toolset="donggu_publishing",
            schema=schema,
            handler=handler,
            description=description,
            emoji=emoji,
            requires_env=required,
            check_fn=check_requirements,
        )
