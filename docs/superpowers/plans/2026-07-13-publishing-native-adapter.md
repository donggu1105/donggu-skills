# Publishing Native Adapter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Completed steps are checked below.

**Goal:** Make `donggu-sns` a dual Claude/Hermes plugin backed by one safe publishing runtime.

**Architecture:** A stdlib-only runtime validates closed channel contracts, issues one-time preview receipts, dispatches to fixed n8n endpoints, and updates the Supabase ledger. Claude uses a CLI wrapper; Hermes registers handlers around the same functions.

**Tech Stack:** Python 3 stdlib, `unittest`, local `http.server`, Claude plugin JSON, Hermes `plugin.yaml`.

## Global Constraints

- Keep Claude package ID `donggu-sns` unchanged.
- Never print credentials.
- No production publication during tests.
- Preview and dispatch are separate calls.
- Publish success plus ledger failure returns `reconciliation_required`.
- Codex exposure is forbidden.

---

### Task 1: Publishing runtime and receipt contract

**Files:**
- Create: `tests/test_publishing_runtime.py`
- Create: `donggu-sns/runtime/__init__.py`
- Create: `donggu-sns/runtime/publishing.py`

**Interfaces:**
- Produces: `PublishingRuntime.preview(...)`, `approve(...)`, `confirm_maily(...)`, `dispatch(...)`, and `ReceiptStore.status(...)`.

- [x] Write a failing `unittest` that previews a Threads payload, verifies no HTTP call, and asserts a `0600` receipt bound to the canonical payload hash.
- [x] Run `python3 -m unittest tests.test_publishing_runtime.PublishingRuntimeTests.test_preview_issues_bound_receipt -v`; expect import failure.
- [x] Implement strict payload validation, canonical JSON, atomic receipt creation, and redacted preview.
- [x] Re-run the focused test; expect PASS.
- [x] Add a failing local-HTTP integration test proving dispatch sends only the fixed endpoint, token header, and receipt idempotency header; empty approval must fail before HTTP.
- [x] Implement one-shot dispatch with `dispatching`, `completed`, `failed`, `uncertain`, and `reconciliation_required` states.
- [x] Add tests for Maily second confirmation, unsupported payload fields, and replay rejection.

### Task 2: Supabase ledger completion

**Files:**
- Modify: `tests/test_publishing_runtime.py`
- Modify: `donggu-sns/runtime/publishing.py`

**Interfaces:**
- Produces: `SupabaseLedger.find_active(...)`, `record_publish(...)`, `mark_deleted(...)`.

- [x] Write failing local-server tests for publish INSERT, update/delete pre-lookup, and delete PATCH.
- [x] Run focused tests and confirm failures are missing ledger behavior.
- [x] Implement URL-encoded REST filters and closed-table requests using `SUPABASE_URL` and `SUPABASE_SERVICE_KEY`.
- [x] Verify success, webhook-success/ledger-failure reconciliation, and no credential leakage.

### Task 3: Claude CLI and Hermes registration

**Files:**
- Create: `donggu-sns/runtime/publishing_cli.py`
- Create: `donggu-sns/plugin.yaml`
- Create: `donggu-sns/__init__.py`
- Create: `donggu-sns/tools.py`
- Modify: `donggu-sns/.claude-plugin/plugin.json`
- Modify: `donggu-sns/skills/publish-sns/SKILL.md`
- Create: `tests/test_native_plugin_packages.py`

**Interfaces:**
- Produces tools `donggu_publishing_preview`, `donggu_publishing_approve`, `donggu_publishing_confirm_maily`, `donggu_publishing_dispatch`, `donggu_publishing_receipt_status`.

- [x] Write failing manifest/registration tests with a fake PluginContext.
- [x] Implement manifest, schemas, handlers, token requirement check, and CLI JSON I/O.
- [x] Update the skill to prefer native tools or the shared CLI while preserving preview and ledger rules.
- [x] Assert Claude, marketplace, and Hermes versions all equal `2.5.0` and plugin registration exposes exactly five publishing tools.
- [x] Run all repository tests and `git diff --check`.
