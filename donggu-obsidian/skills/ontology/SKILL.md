---
name: ontology
description: Use when routing, inspecting, curating, or previewing work in the ontology Vault.
---

# Ontology Operations

Use one entry point for the ontology Vault. Do not route to generic PKM skills. Classify the area, read its live authority files, and perform only the requested job.

## Establish authority

1. Resolve the concrete Vault root from trusted channel context or configured runtime. Never fall back to a similarly named or deprecated Vault.
2. Read root `AGENTS.md` before interpreting the layout.
3. Classify the request as `Personal Branding`, `FDE Community`, `FDE Projects`, or `Life OS` with [routing](references/routing.md).
4. Read the nearest area rules before note contents. For Personal Branding, `_GUIDES/RULES.md` is the operating authority; read schema or voice guides only when needed.
5. Read only the target files and the smallest useful linked neighborhood.

If the root or authority cannot be verified, stop before mutation. Live Vault authority and physical structure outrank this skill.

## Choose the operation

- **Find or explain:** search and read immediately. Return paths and concise findings.
- **Develop an Inbox capture:** load [Personal Branding](references/personal-branding.md). Selection feeds publication; it does not authorize CORE extraction.
- **Curate an approved publication:** load [Personal Branding](references/personal-branding.md) and run **선택 → 추출 → 통합** from that publication.
- **Work on an FDE record:** load [FDE Projects](references/fde-projects.md). Retrieval and proposals are allowed; mutation is proposal-only.
- **Work on FDE Community operations or the separation candidate:** load [FDE Community](references/fde-community.md). Use only the fixed native separation action; other edits are proposal-only.
- **Run a health or duplicate check:** load [maintenance](references/maintenance.md). Scope the check before reading broadly.
- **Prepare or apply a supported CORE change:** load [mutation](references/mutation.md).
- **Record Daily or Capture:** hand off to `donggu-obsidian:life-os` and its native tools.

Read-only requests do not require approval. Requests spanning areas remain read-only and are split into separate proposals.

## Personal Branding invariant

**Inbox selection is publication input only.** Help select and develop raw material, but do not connect, strengthen, or create CORE from an Inbox capture.

CORE integration begins from a **completed and approved publication only**:

1. identify one reusable claim or pattern,
2. search 기존 CORE and relevant MOCs,
3. decide whether to connect, strengthen, create one 새 CORE, or skip,
4. present **후보 하나** with source, relationship, destination, and actual preview.

Snippet and new-MOC work are proposal-only until a dedicated native authority path exists. Do not expose scores, candidate codes, database states, receipts, hashes, or internal action enums.

## Mutation boundary

Only exact `수정안 보여줘` creates an executable preview. It keeps `현재 Vault 변경 0건`. Apply only after a later persisted user message exactly equal to `적용해줘`, and only when the current session already has a valid native receipt for a supported CORE action or the fixed FDE Community separation action. Then run native apply, read-back, and acknowledgement.

Customer FDE Projects, ad-hoc FDE Community edits, Snippet, authority-file, and other unsupported edits are proposal-only: show the diff, but do not call a generic file mutation tool. See [mutation](references/mutation.md).

Inbox notes are raw evidence. Never move, classify, archive, merge, or delete them based only on age, count, or an automated score.

## Maintenance boundary

Do not run a daily full-Vault ritual. A publish event checks only that approved publication and its relevant CORE/MOC neighborhood. Broader duplicate or health checks are bounded and explicit. Normal results stay quiet; report actual issues or execution failures only. See [maintenance](references/maintenance.md).

## Output

Lead with the result. For a preview, show:

1. target and reason,
2. existing knowledge relationship,
3. files that would change,
4. actual diff,
5. explicit statement that nothing has changed,
6. whether the candidate is native-applicable or proposal-only.

After a supported native apply, report changed files, read-back, acknowledgement, and rollback handle. Never claim completion from a proposal or tool request alone.
