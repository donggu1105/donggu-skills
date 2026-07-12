---
name: finding-duplicate-notes
description: Use when auditing personal knowledge management vaults (Obsidian, PARA, LYT, Zettelkasten, second brain) for duplicate, overlapping, or near-duplicate notes — surfaces semantic duplicates, naming twins, absorbed-but-not-merged notes, snippet twins, redundant sources — before consolidation rituals or when atomicity (1 idea = 1 note) seems compromised
---

# Finding Duplicate Notes

## Overview

**Atomicity audit for the vault.** When the same idea is scattered across multiple notes, it violates 1 idea = 1 note, muddies citations, and weakens MOC curation. Surfaces 5 duplicate patterns + recommends actions for the user to decide on.

**No auto-merge. Candidate discovery + action recommendations only.** Subtle differences may be intentional (e.g. snippet A/B variants).

**Cadence boundary:** the full five-pattern audit is **monthly or on-demand** only. Daily care must not run a full-Vault semantic duplicate scan; it may emit a metadata-only **threshold signal** and recommend this skill for a later explicit run.

이 스킬은 report와 metadata-only candidate까지만 생성한다. 자연어 채택이나 blanket approval로 Vault mutation은 수행하지 않는다. mutation 후보 생성 뒤 종료하고, 실제 변경 가능성은 후보 ID별 `core-review-approval`만 판단한다.

## When to Use

- Monthly consolidation ritual
- On-demand after an explicit duplicate/atomicity request
- When an atomicity-suspect note shows up
- Before organizing teaching assets — deduplicate before assembling modules
- When another audit (e.g. `checking-vault-health`) surfaces duplicate signals

## When NOT to Use

- Vault under 50 notes — duplication unlikely
- Plain broken-link check — use `checking-vault-health`
- Atomicity check on a single note — different skill domain
- Daily full-Vault semantic scanning — daily health may report a threshold signal only

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
| **Source redundancy** | Same external material captured in 2+ SOURCE notes | Recommend one source/path-scoped candidate at a time; never bulk-rewrite citations |

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
| Bulk status changes without opening each note | A duplicate pair's old note often self-declares "리프레시 버전 있음 · 비교·기록용" in its **first callout** — bulk-marking it `published` fabricates a publish record. Read the first callout before ANY status flip: 기록용·리프레시 구버전 → `archived`, never `published` (2026-07-03 실제 사고: 카지노 딜러 리프레시 페어 양쪽이 published로 찍혔다가 교정) |

## Red Flags — STOP

- "Recommend merge for every finding" → ignoring the possibility of intentional variation
- "Recommend bulk-deleting all snippet twins" → ignoring audience / channel variation
- "Auto-archive absorbed notes" → ignoring the user's callout intent
- "Flip statuses in bulk during cleanup" → refresh pairs hide in first callouts; open each note first
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

## Candidate handoff — mandatory STOP

각 mutation 권고는 다음 metadata-only candidate 하나로 분리한다.

- `candidate_code`: `CR-YYYYMMDD-NNNNNN` 하나
- `source_note_path`: 안전한 non-Inbox 상대 경로 하나
- `source_sha256`: 생성 시점 lowercase SHA-256 하나
- `candidate_type`: 실제 queue enum 하나
- `proposed_changes`: source 하나에 대한 결정적 action 하나

후보 생성 뒤 종료한다. 정확히 `CR-YYYYMMDD-NNNNNN 승인|보류|거절` 형식만 `core-review-approval`에 전달한다. 자연어 채택, per-item 구두 동의, 후보 목록, 범위, `전체 승인`, `다 합쳐`는 승인으로 간주하지 않는다.

`core-review-approval`이 지원하는 `fix_link`/`link_existing`의 source-local `replace`만 그 스킬의 path·SHA·target 검증을 거쳐 적용될 수 있다. archive, alias, body 축약, move, merge, status 변경, 여러 노트 citation 수정은 현재 지원 action이 아니므로 metadata로만 남기고 승인돼도 release/re-evaluation한다. 여러 파일 또는 Vault 전체 치환 후보는 생성하지 않는다. 이 스킬은 어떤 파일도 직접 수정·이동·삭제하지 않는다. **STOP.**

## Vault-Specific Context

Atomicity conventions differ per PKM system:

- **LYT (Linking Your Thinking)**: atomic notes in Atlas/POV strictly follow 1 idea = 1 note
- **Zettelkasten**: even stricter (Andy Matuschak evergreen)
- **PARA**: atomicity rule is weaker (Projects/Areas are containers)
- **Personal Branding vault**: CORE = atomic POV, so apply strictly

Read the guide note (e.g. `_GUIDES/CONTENT_PIPELINE.md`) first to confirm the atomicity rule before starting the check.

## Related Skills

- **`checking-vault-health`**: flow check across the content pipeline (entry / refinement / exit / curation). Atomicity is secondary there. Cross-reference with this skill.
- **`extract-core`**: capture/Source/Channel Pack → CORE candidate ritual. If duplicates are found, tighten the overlap check when proposing new CORE notes.
