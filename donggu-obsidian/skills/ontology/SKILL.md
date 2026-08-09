---
name: ontology
description: Use when reading, curating, maintaining, or safely changing the ontology Vault.
---

# Ontology Operations

Use one entry point for the ontology Vault. Do not route to a collection of generic PKM skills. Classify the area, read its authority files, and perform only the requested job.

## Establish authority

1. Resolve the concrete Vault root from trusted channel context or configured runtime. Never fall back to a similarly named or deprecated Vault.
2. Read root `AGENTS.md` before interpreting the layout.
3. Classify the request as `Personal Branding`, `FDE Projects`, or `Life OS` with [routing](references/routing.md).
4. Read the nearest area rules before note contents. For Personal Branding, `_GUIDES/RULES.md` is the operating authority; read schema or voice guides only when the request needs them.
5. Read only the target files and the smallest useful linked neighborhood.

If the root or an authority file cannot be verified, stop before mutation and report the missing prerequisite. Never infer Vault rules from a generic methodology.

## Choose the operation

- **Find or explain:** search and read immediately. Return paths and concise findings.
- **Curate Personal Branding:** load [personal-branding](references/personal-branding.md). One loop handles selected Inbox captures and completed, approved posts: **선택 → 추출 → 통합**.
- **Work on an FDE record:** load [FDE Projects](references/fde-projects.md) and preserve the Ontology Lens boundary.
- **Run a health or duplicate check:** load [maintenance](references/maintenance.md). Scope the check before reading broadly.
- **Change the Vault:** load [mutation](references/mutation.md) before preparing any write.
- **Record Daily or Capture:** hand off to `donggu-obsidian:life-os`. Do not use generic filesystem mutation in Life OS.

Read-only requests do not require approval. Requests that combine areas stay read-only until each area has a separate, candidate-specific change proposal.

## Curation contract

For either a selected raw capture or an approved published post:

1. Identify one reusable claim or pattern.
2. Search existing CORE and relevant MOC notes before proposing a new note.
3. Decide in natural language: connect to an existing CORE, strengthen one, create a new CORE, or skip.
4. Propose Snippet or MOC work only when the source and area rules justify it.
5. Present **후보 하나** with source, relationship, destination, and actual change preview.

Do not expose scores, candidate codes, database states, transaction vocabulary, or internal action enums. Those are implementation details, not the user's knowledge work.

## Mutation boundary

A request such as “수정안 보여줘” is preview-only. Produce the actual diff and keep Vault 변경 0건. Apply only after a separate scoped approval as defined in [mutation](references/mutation.md), then verify by read-back.

Inbox notes are raw evidence. Never move, classify, archive, merge, or delete them based only on age, count, or an automated score.

## Maintenance boundary

Do not run a daily full-Vault ritual. A publish event checks that post and its relevant CORE/MOC neighborhood. Broader duplicate or health checks are bounded, explicit maintenance operations. Normal results stay quiet; report actual issues or execution failures only. See [maintenance](references/maintenance.md).

## Output

Lead with the result. For a preview, show:

1. target and reason,
2. existing knowledge relationship,
3. files that would change,
4. actual diff,
5. explicit statement that nothing has changed,
6. the single approval phrase or scoped button.

After apply, report changed files, read-back result, and rollback handle. Never claim success from a planned action or tool request alone.
