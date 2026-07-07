---
name: checking-vault-health
description: Use when running periodic health checks on personal knowledge management vaults (Obsidian, PARA, LYT, Zettelkasten, second brain) to surface pipeline blockages, guide violations, broken wikilinks, stale stubs, MOC threshold gaps, uncited sources, and orphan published posts that neither cite nor extract canon notes
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
- Engagement-metric auditing — `views`/`likes`/`comments`/`saves`/`shares` were deliberately removed from the vault (2026-07-07, overengineering). Never check for them or recommend metric backfill; CASE selection is manual judgment.

## Core Principle

View the vault through the **4-layer mapping**. A flat list of findings is not a health check.

```
Entry (Capture)       → Refinement (Extract / Promote)   → Exit (Assemble / Publish)  → Curation (MOC)
Capture · Source      → CORE · Pattern (both directions)  → Channel Pack               → MOC + cross-link
0 new in 7 days?      → extracted_to 0? decomposed_to 0?  → Orphan posts? Violations?  → No MOC for 5+ topic?
```

What you measure is whether each layer *flows* into the next. Stagnation between stages is the biggest signal that the system is broken.

**Refinement flows both ways.** Forward: journal → CORE promotion, recorded in the journal's `extracted_to:`. Reverse: a post written first → parts extracted back into canon, recorded in the pack's `decomposed_to:`. Both count as healthy refinement. A published pack with NEITHER a CORE citation NOR `decomposed_to` entries is an **orphan post** — that is the defect, not "the post was written before its parts."

## Workflow (9 steps, sample as conditions allow)

1. **List vault structure** — `list_files_in_vault` + `list_files_in_dir` on 4-5 key folders
2. **Entry check (capture-based)** — journals are OPTIONAL (2026-07-07 필수 해제): a missing `journal/` folder is NOT a finding. Entry is healthy when ANY first-person capture exists in the last 7 days — notes created in the inbox folder (e.g. `00_Inbox/`: 글감, 생각, 뉴스 브리핑, drafts) or in a `journal/` folder if the user keeps one. Flag P0 only when inbox AND journals both show zero new capture for 7+ days
3. **Refinement check (both directions)** — Forward: `simple_search` for `"extracted_to: \[\]"` to list journals that were never extracted; identify SOURCEs with 0 citations for 1+ weeks. Reverse: posts written first must extract parts back — check `decomposed_to:` on recent packs (see step 7)
4. **Guide violations** — frontmatter `type` enum violations, anti-patterns (e.g. a published Channel Pack left with neither cited parts nor `decomposed_to` backfill)
5. **Link integrity** — broken wikilinks, especially comma/whitespace typo patterns (e.g. `[[CORE - X 판단은 사람]]` vs `[[CORE - X, 판단은 사람]]`)
6. **Stub backlog** — `status: draft` or `status: stub` + `created < (today - 2 weeks)`
7. **Canon consistency (output side)** — sample the 3-5 most recent `status: published` Channel Packs. Each must anchor to canon in at least one direction: cites ≥1 CORE (`core_principle` field or a 부품/parts section) OR lists extractions in `decomposed_to:`. Spot-check voice fields (register, pillar) against the vault's `canon: true` reference posts. Flag anchorless packs as orphan output (P1)
8. **MOC threshold** — same topic appears in 5+ notes but no MOC exists (Nick Milo's rule)
9. **1-3 positive signals** — for balance, identify what's working well

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
- **P0**: System entry severed (0 capture of ANY kind — inbox note, 글감, draft, journal — for 7+ days; a missing journal folder alone is NOT P0)
- **P1**: Pipeline stalled (no extraction / citation for 1+ weeks, orphan published posts) + guide anti-pattern violations
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
| Flagging "post written before its parts" as a violation | The reverse flow is legitimate: write the post first, then extract parts into `decomposed_to:`. Only flag packs with NEITHER citations NOR `decomposed_to` |
| Recommending engagement-metric backfill (views/likes/comments/saves/shares) | Deliberately removed 2026-07-07 as overengineering. CASE selection is manual judgment — never resurrect these fields |
| Flagging a missing journal folder as P0 | Journals are optional (2026-07-07). Entry health = any capture (inbox note, 글감, draft, journal) within the last 7 days |
| Auto-promoting inbox notes during remediation | `00_Inbox` is the user's decision queue. List candidates with a one-line recommendation each and get per-item approval. A blanket "다 처리해봐 / fix everything" does NOT cover inbox moves, merges, or deletions |

## Red Flags — STOP and Restart

- "I read the entire vault" → sampling rule violated, time budget blown
- "I only checked broken links" → 4-layer mapping missing
- "There are no action commands" → P priority is meaningless
- "I didn't write positive signals" → user loses balance
- Tool uses passed 100 and the report is unfinished → stop immediately and submit a partial report

## Example: Entry severed (P0)

```
## P0 — Entry severed: no capture in 12 days

**Finding**: Newest note in `00_Inbox/` is 12 days old; no journal folders in use (journals are optional, so that alone is fine — the zero-capture streak is the problem).
**Impact**: No first-person material entering the pipeline — nothing for the weekend extraction to promote, nothing feeding forward-only posts.
**Action**: Capture one thought/글감 into `00_Inbox/` today. Format-free — one raw line is enough.
```

## Example: Refinement stalled (P1)

```
## P1 — Refinement stalled: 5 unextracted journals

**Finding**: `simple_search "extracted_to: []"` returned 5 results (all 1+ weeks old).
**Impact**: Atomic insights in journals are not being promoted to CORE → 0 new teaching assets accumulated.
**Action**: Run the weekend extraction ritual. Skim only the "💎 추출 후보" section of each journal → 1-3 new CORE notes. Use the /extract-core skill.
```

## Example: Orphan output (P1)

```
## P1 — Canon consistency: 2 orphan posts

**Finding**: Of the 5 most recent published packs, 2 cite no CORE and have an empty `decomposed_to:`.
**Impact**: Posts aren't feeding back into canon — the flywheel (글 → 부품 역추출 → 다음 글) breaks silently.
**Action**: For each orphan, extract 1-3 parts (Hook / Lesson / CORE) and backfill `decomposed_to:`. If nothing is extractable, the post may be off-canon — review its register/pillar against the `canon: true` posts.
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

**Remediation gates**:
- `00_Inbox` (or the vault's inbox folder) is the user's decision queue, not backlog to clear. When remediation touches inbox notes — moving to `10_Sources`, promoting, merging duplicates, deleting — STOP and present the candidate list (one-line recommendation per item), then act only on the user's per-item answer.
- A blanket approval covers findings outside the inbox; inbox items always get their own ask.

**Cross-reference rules (follows the writing-skills guide)**:
- Do NOT use `**REQUIRED SUB-SKILL:**` — neither is strictly required
- Use `**Chain recommended:**` — call only after the user decides
