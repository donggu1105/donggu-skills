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
12. HMAC-SHA256 over the complete receipt, including state and approval metadata.
13. Expiry enforcement in `planned`, `approved`, and `confirmed` states.
14. Delete lookup rejects duplicate active rows and PATCHes by the exact ledger row `id`.
15. Image URLs use a fixed host allowlist and reject non-global DNS answers.

The preview tool does not publish. Hermes supplies trusted host `session_id` and binds a unique
`turn_id` in its tool-dispatch approval ContextVar. Approval/confirmation handlers read that
turn ID plus the latest persisted user message from Hermes `SessionDB`; model-provided approval
strings are not accepted. The receipt also binds the preview user-message row ID: approval must
use a larger persisted row ID, and Maily confirmation must use a row newer than approval. Approval
must use the same session and a later turn with an explicit approval phrase. Maily confirmation
must use a third turn whose user message explicitly confirms the **final Maily send**. Each persisted authorization row is atomically consumed by exactly one receipt across approval and confirmation; blanket reuse across planned receipts is forbidden. Runtime
states are deliberately separate:
`preview → approve → dispatch`; Maily real-send is
`preview → approve → confirm_maily → dispatch`. Payload binding is rechecked under the
receipt lock before every state transition. Maily dry-run ends as `completed_draft` and is
never inserted into `published_posts`.

The Claude skill may call the shared CLI for stateless `preview` only. All receipt status and
mutations require the trusted in-process Hermes runtime. The Hermes plugin calls the same
Python core directly.

## Obsidian contract

The existing `core-review-approval/scripts/apply-action.py` remains the sole mutation implementation. It already enforces exact schemas, path and hash binding, dry-run zero writes, crash-atomic staging, rollback, recovery journals, and acknowledgement.

The adapter adds:

1. `donggu_core_plan`: invokes the helper with `--dry-run`, then issues a one-time, process-HMAC-signed receipt bound to the exact envelope, Vault root identity, paths, and before/after hashes.
2. `donggu_core_apply`: takes only `receipt_id`; the handler reads the actual latest user message across the full Hermes `SessionDB` session, calls the existing `validate-approval.py` for exact `<candidate_code> 승인`, requires the plan session and a persisted message row no older than plan, validates the receipt read-only, atomically commits `(session_sha256,message_id)` for one receipt only in a profile-local durable SQLite UNIQUE store whose exact parent/file modes are descriptor-enforced as `0700/0600` on every consume, then claims the receipt, rechecks the receipt/root binding, and invokes the same helper without `--dry-run`.
3. `donggu_core_recovery_status`: read-only journal status.
4. Recovery journal classification only when both its candidate code and deterministic transaction fingerprint (`candidate_code + path별 before/after hashes`) match the HMAC-bound receipt; same-code foreign journals never inherit receipt hashes.
5. Component-by-component Vault root traversal without following symlinks.

No duplicate Vault mutation implementation is introduced.

Vault commit is non-terminal. The bridge returns `operation_completed: false` with
`vault_committed_reconciliation_required` until DB completion, after-hash read-back, and
journal acknowledgement finish. Timeout or malformed helper output triggers recovery-status
inspection; unresolved outcomes retain the envelope as `outcome_unknown`.

## Safety boundaries

- Preview is always separate from external or filesystem mutation.
- Receipt TTL is 15 minutes.
- Receipt files are mode `0600`, atomically created, and HMAC-signed with a process-memory-only key.
- Gateway restart intentionally invalidates unfinished publishing receipts; re-preview instead of recovering them.
- Tokens and service keys never appear in tool output.
- Webhook paths and Supabase table are closed constants.
- Direct mutation fallback is forbidden; adapter/configuration failure is fail-closed.
- Tests use a local HTTP server and temporary Vault only.
- No production post or real Vault mutation is used for verification.
- Existing Claude package IDs remain unchanged.
- Codex is not a target for these operational packages.

## Versioning

- `donggu-sns`: `2.5.0` → `2.5.1`
- `donggu-obsidian`: `1.6.0` → `1.6.1`

Claude JSON and Hermes YAML versions must match per package.
