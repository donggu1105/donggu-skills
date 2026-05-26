---
name: finding-duplicate-notes
description: Use when auditing personal knowledge management vaults (Obsidian, PARA, LYT, Zettelkasten, second brain) for duplicate, overlapping, or near-duplicate notes — surfaces semantic duplicates, naming twins, absorbed-but-not-merged notes, snippet twins, redundant sources — before consolidation rituals or when atomicity (1 idea = 1 note) seems compromised
---

# Finding Duplicate Notes

## Overview

**Atomicity audit for the vault.** When the same idea is scattered across multiple notes, it violates 1 idea = 1 note, muddies citations, and weakens MOC curation. Surfaces 5 duplicate patterns + recommends actions for the user to decide on.

**No auto-merge. Candidate discovery + action recommendations only.** Subtle differences may be intentional (e.g. snippet A/B variants).

## When to Use

- Monthly consolidation ritual
- When an atomicity-suspect note shows up
- Regular check once a vault has 100+ notes
- Before organizing teaching assets — deduplicate before assembling modules
- When another audit (e.g. `checking-vault-health`) surfaces duplicate signals

## When NOT to Use

- Vault under 50 notes — duplication unlikely
- Plain broken-link check — use `checking-vault-health`
- Atomicity check on a single note — different skill domain

## Core Principle

**Five flavors of violating "1 idea = 1 note":**
- Same meaning (different phrasing)
- Subtle naming differences
- Absorbed callout exists but the body is still alive
- Parts scattered (snippet variants)
- External material captured multiple times

Each pattern needs a different action — never batch-process them.

## 5 Duplicate Patterns

| Pattern | Signal | Action |
|---|---|---|
| **Semantic duplicates** | Different titles, same core claim | Recommend merge — consolidate into one, archive the other with alias |
| **Naming twins** | Nearly identical titles (e.g. `CORE - X` vs `CORE - X에 대하여`) | Pick one, redirect the other (alias frontmatter) |
| **Absorbed-not-merged** | "Absorbed into [[Y]]" callout exists but the note is still alive as a standalone | Delete the body, set `status: archived`, preserve the alias |
| **Snippet twins** | Same Hook/Lesson spread across 2+ notes | Pick the best version, archive the rest — or preserve if it's an intentional variant |
| **Source redundancy** | Same external material captured in 2+ SOURCE notes | Merge — consolidate into 1 SOURCE, batch-fix citations to the other |

## Workflow

1. **List vault structure** — `list_files_in_dir` on core folders (CORE / Source / Snippet)
2. **Collect CORE titles** — list filenames in the CORE folder via `list_files_in_dir` (title = filename)
3. **Semantic duplicate detection** — review the full CORE title list → identify pairs that say the same idea with different words. Example: "AI는 도구" + "기술은 수단" → same idea?
4. **Naming twin detection** — fuzzy match for nearly identical title pairs (e.g. 80%+ character match)
5. **Absorbed-not-merged detection** — **check both signals**:
   - (a) body callout: `simple_search "흡수"` or `"통합 안내"` → check whether that note is actually archived
   - (b) frontmatter keys: `simple_search "evolves_from:"` or `"superseded_by:"` → list notes that explicitly declare an evolution pair. **If these keys exist, intent is already preserved = no action needed** (avoids false positives)
6. **Snippet twin detection** — list Hook/Lesson/One-liner/Proof folders → sample first lines → find pairs with similar opening sentences
7. **Source redundancy detection** — match SOURCE titles + match frontmatter URLs
8. **Map each finding to an action** — use the 5-pattern table above
9. **Write the report** — formatted for the user to adopt actions from

## Report Format (standard)

```
# Note Duplication Audit — <vault>
Date: YYYY-MM-DD · Checked all 5 patterns

## 🔄 Semantic Duplicates (N)
1. **"X" ↔ "Y"**
   - Note A: [[CORE - X]]
   - Note B: [[CORE - Y]]
   - Diagnosis: A's body explicitly says "subset of B" → absorption complete on A's side
   - Recommended action: set A's frontmatter `status: archived`, delete the body (preserve alias)

## 🪞 Naming Twins (N)
2. **"CORE - X" ↔ "CORE - X에 대하여"** (90% character match)
   - A: 12 citations
   - B: 0 citations (dead)
   - Action: archive B, add "X에 대하여" to A's aliases

## 📋 Absorbed-Not-Merged (N)
- ...

## ✂️ Snippet Twins (N)
- ...

## 📚 Source Redundancy (N)
- ...

## One-line summary
[1-3 recommended actions]
```

## Time Budget

| Vault size | Check time | Tool uses |
|---|---|---|
| 100-300 notes | 15-20 min | 30-50 |
| 300-1000 notes | 30-45 min | 60-80 |
| 1000+ notes | 45-60 min | sampling required, sample per layer |

**Hard limit**: submit a partial report past 100 tool uses or 60 minutes.

## Common Mistakes

| Mistake | Fix |
|---|---|
| Attempting auto-merge | User decision gate is mandatory. Proceed only after explicit adoption |
| Recommending merge for every finding | May be intentional variants (A/B test, audience split, evolution trace). Add a diagnosis step |
| Auto-computing semantic distance | Out of skill scope. Only the user can verify their own voice |
| Judging subtle snippet differences as duplicates | Hook variants are intentional per channel / audience. Same opening 5 words ≠ duplicate |
| Bulk-archiving absorbed notes | The body may still hold alias / citation value. Confirm via callout first |
| Searching common frontmatter values | `simple_search "status: archived"` blows up tokens. Bypass with folder + sampling |

## Red Flags — STOP

- "Recommend merge for every finding" → ignoring the possibility of intentional variation
- "Recommend bulk-deleting all snippet twins" → ignoring audience / channel variation
- "Auto-archive absorbed notes" → ignoring the user's callout intent
- Tool uses passed 100+ and the report is unfinished → stop immediately and submit a partial report

## Example: Semantic Duplicate (atomicity violation)

```
1. **"AI는 도구이지 판단자가 아니다" ↔ "기술은 수단이다"**
   - Note A: [[CORE - AI는 도구, 판단은 사람]] (created 2026-02-02, 12 citations)
   - Note B: [[CORE - 기술은 수단이다]] (created 2025-12-31, 23 citations)
   - First callout in A's body: "이 CORE는 [[CORE - 기술은 수단이다]]의 부분집합으로 통합되었다"
   - Diagnosis: A's self-diagnosis explicitly says it's absorbed into B. But A still has status: evergreen.
   - Recommended action:
     (a) change A's status to `absorbed` + preserve only the aphorism in the body, fold the main body into B
     (b) keep A's file itself (alias / citation value) — just shorten the body
```

## Example: Snippet Twin (intentional variant — preserve)

```
2. **"AI가 코드의 95%를 짠다고" ↔ "AI가 코드를 짠다고 그래서 뭐"**
   - Note A: [[HOOK - AI가 코드의 95%를 짰다고]]
   - Note B: body of the post that used it ([[LinkedIn - AI가 코드의 95%를 짠다고 그래서 뭐]])
   - Diagnosis: A = Hook component (reusable), B = the variant of that Hook used in a specific post
   - Recommended action: **preserve**. Hook component and published variant are separate things. Just add a [[HOOK - ...]] citation in post B (for reuse tracking)
```

## Example: Naming Twin (needs cleanup)

```
3. **"CORE - 풀스택은 직군이 아니라 책임이다" ↔ "CORE - 풀스택은 직군이 아닌 책임이다"** (95% character match)
   - A: 18 citations, status: evergreen
   - B: 0 citations, status: draft
   - Diagnosis: B is a draft trace of A — mis-named and survived
   - Recommended action: archive or delete B, add alias "직군이 아닌 책임" to A
```

## Action Rules (after user decision)

Follow-up actions that can be automated once adopted:

- **archive**: add `status: archived` to the file's frontmatter + move to `99_Archive/` or preserve as alias
- **add alias**: append to frontmatter `aliases: [<old name>]` → preserves wikilink compatibility
- **shorten body**: leave only a 1-2 line aphorism in the body and redirect to the main link
- **batch-fix citations**: if other notes cite [[B]], swap them to [[A]] in bulk (Obsidian's built-in rename or a vault-wide find-replace)

No automation — proceed only after explicit user adoption.

## Vault-Specific Context

Atomicity conventions differ per PKM system:

- **LYT (Linking Your Thinking)**: atomic notes in Atlas/POV strictly follow 1 idea = 1 note
- **Zettelkasten**: even stricter (Andy Matuschak evergreen)
- **PARA**: atomicity rule is weaker (Projects/Areas are containers)
- **Personal Branding vault**: CORE = atomic POV, so apply strictly

Read the guide note (e.g. `_GUIDES/CONTENT_PIPELINE.md`) first to confirm the atomicity rule before starting the check.

## Related Skills

- **`checking-vault-health`**: flow check across the content pipeline (entry / refinement / exit / curation). Atomicity is secondary there. Cross-reference with this skill.
- **`extract-core`**: journal → CORE promotion ritual. After running this skill, if duplicates are found, tighten the overlap check when creating new CORE notes in extract-core.
