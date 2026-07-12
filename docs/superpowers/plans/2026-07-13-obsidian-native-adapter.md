# Obsidian Native Adapter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Completed steps are checked below.

**Goal:** Make `donggu-obsidian` a dual Claude/Hermes plugin without duplicating its crash-atomic CORE mutation implementation.

**Architecture:** A small runtime bridge invokes the existing `apply-action.py` subprocess. Dry-run produces a receipt bound to the exact Vault root and envelope; apply consumes the receipt and runs the same helper.

**Tech Stack:** Python 3 stdlib, `unittest`, existing crash-atomic helper, Hermes `plugin.yaml`.

## Global Constraints

- Keep Claude package ID `donggu-obsidian` unchanged.
- The existing 47 CORE tests must remain green.
- Real Vault files must not be touched by tests.
- Apply requires a current plan receipt and explicit approval text.
- Recovery status is read-only; recovery mutation stays in the existing CLI skill.

---

### Task 1: CORE runtime bridge

**Files:**
- Create: `tests/test_obsidian_runtime_adapter.py`
- Create: `donggu-obsidian/runtime/__init__.py`
- Create: `donggu-obsidian/runtime/core_actions.py`

**Interfaces:**
- Produces: `CoreActionRuntime.plan(vault_root, envelope) -> dict`, `apply(receipt_id, approval_text) -> dict`, `recovery_status(vault_root) -> dict`.

- [x] Write a failing test that builds a temporary Vault, plans a valid replacement, and verifies zero file changes plus a bound receipt.
- [x] Run the focused test and confirm import failure.
- [x] Implement helper discovery, subprocess JSON I/O, exact envelope hashing, and atomic one-time receipts.
- [x] Re-run and expect PASS.
- [x] Write a failing test that applies the receipt, checks the exact link replacement, and rejects replay or empty approval.
- [x] Implement apply and status methods; keep all mutation inside `apply-action.py`.
- [x] Verify helper errors are returned as bounded messages without envelope or Vault content leakage.

### Task 2: Hermes package and Claude regression

**Files:**
- Create: `donggu-obsidian/plugin.yaml`
- Create: `donggu-obsidian/__init__.py`
- Create: `donggu-obsidian/tools.py`
- Modify: `donggu-obsidian/.claude-plugin/plugin.json`
- Modify: `tests/test_native_plugin_packages.py`

**Interfaces:**
- Produces tools `donggu_core_plan`, `donggu_core_apply`, `donggu_core_recovery_status`.

- [x] Extend the failing registration test for the Obsidian package.
- [x] Implement Hermes manifest, schemas, and handlers around `CoreActionRuntime`.
- [x] Assert Claude, marketplace, and Hermes versions all equal `1.6.0` and exactly three tools register.
- [x] Run the adapter tests, existing 47 CORE tests, all repository tests, syntax compilation, and `git diff --check`.
- [x] Install both package subdirectories into a temporary `HERMES_HOME`, enable them, and verify plugin and tool discovery without real credentials or Vault mutation.
