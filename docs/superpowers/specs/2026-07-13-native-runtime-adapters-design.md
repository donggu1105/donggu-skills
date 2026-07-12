# Claude·Hermes Native Runtime Adapters Design

**Date:** 2026-07-13
**Status:** Approved

## Goal

Keep `donggu-sns` and `donggu-obsidian` as existing Claude Code plugins while making the same package roots installable as native Hermes plugins. Skill prose remains single-source; deterministic execution code is shared by both harnesses.

## Packaging

Each existing Claude package becomes a dual-harness package:

```text
donggu-sns/
├── .claude-plugin/plugin.json
├── plugin.yaml                 # Hermes manifest
├── __init__.py                 # Hermes registrations
├── tools.py                    # Hermes handlers/schemas
├── runtime/                    # shared deterministic core + CLI
└── skills/                     # existing skill source

donggu-obsidian/
├── .claude-plugin/plugin.json
├── plugin.yaml
├── __init__.py
├── tools.py
├── runtime/                    # bridge to existing crash-atomic helper
└── skills/
```

Hermes supports repository subdirectory installs, so the packages are installable independently:

```bash
hermes plugins install donggu1105/donggu-skills/donggu-sns --enable
hermes plugins install donggu1105/donggu-skills/donggu-obsidian --enable
```

## Publishing contract

`donggu-sns/runtime/publishing.py` owns:

1. Strict channel/operation payload validation.
2. Local preview generation and SHA-256 payload binding.
3. A one-time, expiring receipt under `$HERMES_HOME/state/donggu-publishing/receipts/`.
4. Fixed HTTPS webhook/Supabase origins and redirect refusal; callers cannot provide an arbitrary URL.
5. `X-SNS-Token` authentication and `X-Idempotency-Key` receipt binding.
6. Supabase `published_posts` ledger insertion after publish success.
7. Ledger lookup before update/delete; no post ID is accepted from conversation memory.
8. Ledger `deleted_at` update after delete success.
9. Explicit `reconciliation_required` state if the external publication succeeds but ledger completion fails.
10. Exact single-row ledger write verification and channel-specific success identifier validation.
11. One-shot dispatch: a network-uncertain receipt cannot be replayed automatically.

The preview tool does not publish. Runtime states are deliberately separate:
`preview → approve → dispatch`; Maily real-send is
`preview → approve → confirm_maily → dispatch`. Payload binding is rechecked under the
receipt lock before every state transition. Maily dry-run ends as `completed_draft` and is
never inserted into `published_posts`.

The Claude skill calls the shared CLI when available; the Hermes plugin calls the same Python runtime directly.

## Obsidian contract

The existing `core-review-approval/scripts/apply-action.py` remains the sole mutation implementation. It already enforces exact schemas, path and hash binding, dry-run zero writes, crash-atomic staging, rollback, recovery journals, and acknowledgement.

The adapter adds:

1. `donggu_core_plan`: invokes the helper with `--dry-run`, then issues a one-time receipt bound to the exact envelope, Vault root identity, paths, and before/after hashes.
2. `donggu_core_apply`: calls the existing `validate-approval.py`, requires exact `<candidate_code> 승인`, rechecks the receipt/root binding, then invokes the same helper without `--dry-run`.
3. `donggu_core_recovery_status`: read-only journal status.

No duplicate Vault mutation implementation is introduced.

Vault commit is non-terminal. The bridge returns `operation_completed: false` with
`vault_committed_reconciliation_required` until DB completion, after-hash read-back, and
journal acknowledgement finish. Timeout or malformed helper output triggers recovery-status
inspection; unresolved outcomes retain the envelope as `outcome_unknown`.

## Safety boundaries

- Preview is always separate from external or filesystem mutation.
- Receipt TTL is 15 minutes.
- Receipt files are mode `0600` and atomically created.
- Tokens and service keys never appear in tool output.
- Webhook paths and Supabase table are closed constants.
- Direct mutation fallback is forbidden; adapter/configuration failure is fail-closed.
- Tests use a local HTTP server and temporary Vault only.
- No production post or real Vault mutation is used for verification.
- Existing Claude package IDs remain unchanged.
- Codex is not a target for these operational packages.

## Versioning

- `donggu-sns`: `2.4.2` → `2.5.0`
- `donggu-obsidian`: `1.5.0` → `1.6.0`

Claude JSON and Hermes YAML versions must match per package.
