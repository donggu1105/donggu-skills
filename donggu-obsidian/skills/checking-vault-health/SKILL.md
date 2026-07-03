---
name: checking-vault-health
description: Use when running periodic health checks on personal knowledge management vaults (Obsidian, PARA, LYT, Zettelkasten, second brain) to surface pipeline blockages, guide violations, broken wikilinks, stale stubs, MOC threshold gaps, and uncited sources before weekly recovery rituals
---

# Checking Vault Health

## Overview

A periodic checkup that identifies **where the content pipeline of a PKM vault is blocked**. Not a broken-link audit. The health metric is whether each of the 4 layers — entry (capture) → refinement (extraction / promotion) → exit (assembly / publishing) → curation (MOC) — flows into the next.

## When to Use

- Right before a weekend extraction ritual — surface stale journals and uncited SOURCE notes
- Monthly system retrospectives — find stalled layers
- Before adding a new content domain — verify vault coherence
- Periodic checks once a vault exceeds 100+ notes (sampling becomes mandatory past 300+)

## When NOT to Use

- Vault has fewer than 50 notes — the system itself is immature, so the check has no meaning
- Plain broken-link hunts — `obsidian_simple_search` is enough
- First-time vault structure design — different skill domain

## Core Principle

View the vault through the **4-layer mapping**. A flat list of findings is not a health check.

```
Entry (Capture)       → Refinement (Extract / Promote)  → Exit (Assemble / Publish)  → Curation (MOC)
Journal · Source      → CORE · Pattern                   → Channel Pack               → MOC + cross-link
0 new in 7 days?      → extracted_to 0?                  → Guide violations?          → No MOC for 5+ topic?
```

What you measure is whether each layer *flows* into the next. Stagnation between stages is the biggest signal that the system is broken.

## Workflow (8 steps, sample as conditions allow)

1. **List vault structure** — `list_files_in_vault` + `list_files_in_dir` on 4-5 key folders
2. **Entry check** — **first check: verify the journal sub-folder actually exists** (use `list_files_in_dir` on paths like `70_Projects/<project>/journal/`). If the folder is missing, immediately flag P0 (`simple_search "type: journal"` alone misses this because template hits hide it). If the folder exists, count notes created in the last 7 days
3. **Refinement check** — `simple_search` for `"extracted_to: \[\]"` to list journals that were never extracted. Identify SOURCEs with 0 citations for 1+ weeks
4. **Guide violations** — frontmatter `type` enum violations, anti-patterns (e.g. "writing the body directly into a Channel Pack")
5. **Link integrity** — broken wikilinks, especially comma/whitespace typo patterns (e.g. `[[CORE - X 판단은 사람]]` vs `[[CORE - X, 판단은 사람]]`)
6. **Stub backlog** — `status: draft` or `status: stub` + `created < (today - 2 weeks)`
7. **MOC threshold** — same topic appears in 5+ notes but no MOC exists (Nick Milo's rule)
8. **1-3 positive signals** — for balance, identify what's working well

## Report Format (standard)

```
# Vault Health — <vault-name>
Date: YYYY-MM-DD · Scope: N folders, M notes sampled

## P0 — [Layer]: [concrete problem]
**Finding**: ...
**Impact**: The system's [which flow] is blocked
**Action**: [concrete command or next step]

## P1 — ...
## P2 — ...
...

## Positive signals (preserve)
- ...

## One-line summary
[1-3 prioritized action commands]
```

P priority:
- **P0**: System entry severed (0 journal / capture entries for 7+ days)
- **P1**: Pipeline stalled (no extraction / citation for 1+ weeks) + guide anti-pattern violations
- **P2**: broken wikilinks (many found)
- **P3**: stub backlog + MOC threshold reached
- **P4**: naming / frontmatter consistency

## Time Budget

| Vault size | Check time | Tool uses | Sampling |
|---|---|---|---|
| 100-300 notes | 10-15 min | 30-50 | List core folders + sample 5-10 notes |
| 300+ notes | 20-30 min | 60-80 | Force a representative sample per folder |
| 1000+ notes | 30-45 min | 80-100 | Only 1 folder deep per layer, metadata-only for the rest |

**Hard limit**: stop and submit a partial report once you exceed 100 tool uses or 30 minutes.

## Common Mistakes

| Mistake | Fix |
|---|---|
| Report has only *findings* and no *actions* | Every P must include "Action: concrete command" |
| Skipping entry (journal / capture) and only checking exit (broken links) | Enforce the 4-layer mapping rule — at least 1 item per layer |
| Only negative findings, no balance | Force the "Positive signals" section with 1-3 items |
| Reading the whole vault | Sampling rule violated. Sampling is mandatory at 100+ |
| Reading the same frontmatter key 50 times | Use metadata batch retrieval or search |
| Searching directly for common frontmatter values | Searches like `simple_search "status: draft"` blow up to 100k+ token results. **Constrain by enum value + folder** (e.g. `obsidian_list_files_in_dir "20_Core"` then sample with batch_get_file_contents) |
| Report exceeds 5000 chars | 5 lines max per P, one-line summary is literally 1 line |
| Bulk status remediation right after the audit | Before flipping any status (e.g. drafting→published), read each note's **first callout** — 기록용/리프레시 구버전은 `archived`가 맞지 `published`가 아니다 (2026-07-03 사고: 리프레시 페어 구버전에 가짜 발행 기록이 찍힘) |

## Red Flags — STOP and Restart

- "I read the entire vault" → sampling rule violated, time budget blown
- "I only checked broken links" → 4-layer mapping missing
- "There are no action commands" → P priority is meaningless
- "I didn't write positive signals" → user loses balance
- Tool uses passed 100 and the report is unfinished → stop immediately and submit a partial report

## Example: Entry severed (P0)

```
## P0 — Entry severed: 0 Build Journal entries

**Finding**: Queried `70_Projects/*/journal/` → 0 results. 0 new journals in the last 7 days.
**Impact**: The system entry is blocked; the pipeline feeding CORE promotion and LinkedIn daily material is not working.
**Action**: Pick 1 active project and create `70_Projects/<project>/journal/YYYY-MM-DD.md`. Apply TPL - Build Journal. Start the nightly 5-15 min rule.
```

## Example: Refinement stalled (P1)

```
## P1 — Refinement stalled: 5 unextracted journals

**Finding**: `simple_search "extracted_to: []"` returned 5 results (all 1+ weeks old).
**Impact**: Atomic insights in journals are not being promoted to CORE → 0 new teaching assets accumulated.
**Action**: Run the weekend extraction ritual. Skim only the "💎 추출 후보" section of each journal → 1-3 new CORE notes. Use the /extract-core skill.
```

## Vault-Specific Context

Layer mapping differs by PKM system. The skill is the framework; the mapping depends on the user's vault:

- **LYT (Linking Your Thinking)**: Inbox → Atlas/POV → MOC → Channel Pack
- **PARA**: Projects → Areas → Resources → Archive (different identity)
- **Zettelkasten**: Fleeting → Literature → Permanent → Drafts
- **Second Brain (CODE)**: Capture → Organize → Distill → Express

Read the vault's guide note (e.g. `_GUIDES/CONTENT_PIPELINE.md`) or CLAUDE.md first to lock in the layer mapping before starting the check.

## Related Skills (auto-chain)

When the vault health check surfaces the following signals, **immediately chain into a separate skill** — it flows naturally into the next step in the same task:

| Signal found | Chain target | Reason |
|---|---|---|
| Semantic duplicates, naming twins, or absorbed-not-merged callouts | **`finding-duplicate-notes`** | Atomicity audit is its own area. Full audit of the 5 duplicate patterns. |
| 5+ journals with `extracted_to: []`, no extraction for 1+ weeks | **`extract-core`** | Weekend extraction ritual. Trigger the journal → CORE promotion ritual. |
| 5+ notes on the same topic but no MOC | (user does this directly) | MOC creation is hand-curation, not a skill domain. |

**Chain rules**:
- After noting the finding in the vault health report, explicitly state something like "Recommend expanding this finding with the `finding-duplicate-notes` skill"
- Only chain after the user agrees (subagent or direct execution)
- No blanket auto-chaining — keep the user's decision gate

**Cross-reference rules (follows the writing-skills guide)**:
- Do NOT use `**REQUIRED SUB-SKILL:**` — neither is strictly required
- Use `**Chain recommended:**` — call only after the user decides
