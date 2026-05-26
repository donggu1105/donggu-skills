---
name: extract-core
description: Use when running weekend extraction rituals on personal knowledge management vaults (Obsidian, PARA, LYT, Zettelkasten) — surfaces atomic claim candidates from build journals' "extracted candidate" sections, evaluates atomicity, scores top 3-5 for promotion to atomic permanent notes (CORE), and triggers automated extraction tracking via frontmatter linking
---

# Extract Core

## Overview

Surface "💎 추출 후보" sections from journals → evaluate atomicity → recommend CORE promotion candidates. **Promotion is not automated, only recommended.** Once the user decides to adopt, the skill creates the CORE note and auto-links the journal's `extracted_to:`.

## When to Use

- Weekly weekend extraction ritual (30-60 min)
- After accumulating 5+ journals
- When you're short on LinkedIn daily material — mine the accumulated backlog
- When teaching assets are stacking up — identify CORE candidates that could evolve into Patterns

## When NOT to Use

- 0-2 journals — not enough data
- Right before a publishing deadline — extraction is the refinement stage, not the publish stage
- Reviewing atomicity of a suspect note — different skill domain

## Core Principle

**Extraction is evaluation + recommendation. No automatic adoption.** Only the human can verify their own voice and assess atomicity. The skill handles candidate refinement, scoring, and metadata automation.

## 5 Atomicity Criteria

Score each candidate on 5 criteria → sum to a 10-point total:

| Criterion | Max | Check question |
|---|---|---|
| **1 idea = 1 note** | 2 | Are there 2+ ideas mixed inside the candidate? |
| **"X는 Y다" sentence form** | 2 | Can it be expressed as a complete sentence? ("AI 어려움" no, "AI는 도구이지 판단자가 아니다" ✅) |
| **Own voice** | 2 | Is this the user's opinion / interpretation, not just objective fact summarization? |
| **No overlap with existing CORE** | 2 | Does a similar CORE already exist? (requires vault search) |
| **No time anchor** | 2 | Free of moment-dependent phrasing like "이번 주 ..."? |

**Total 8+ → recommend adoption / 5-7 → hold (revisit) / 4 or less → discard or convert to another form**

## Workflow

1. **List journals** — `obsidian_list_files_in_dir "70_Projects/<project>/journal/"` (or sweep all projects)
2. **Filter by date** — narrow by frontmatter `date` or filename YYYY-MM-DD (default: last 7 days)
3. **Pull candidates** — for each journal, read only the "## 💎 추출 후보" section via `obsidian_get_file_contents`
4. **Consolidate** — collect all candidates in one place (preserve source journal)
5. **Atomicity scoring** — score each candidate against the 5 criteria
6. **Check overlap with existing CORE** — `obsidian_simple_search "CORE - <keyword>"` to find duplicates
7. **Classify recommendation** — adopt (8+) / hold (5-7) / discard (4 or less)
8. **Ask the user to decide** — get explicit adoption ("adopt 1 and 3")
9. **Auto-create CORE notes** — for each adopted candidate:
   - `obsidian_append_content` filepath: `20_Core/CORE - <sentence>.md`
   - frontmatter: `type: core`, `title`, `topics`, `audience`, `tone`, `status: draft`, `created`
   - body: `## 💡 핵심 주장` callout + source link
10. **Update the journal's `extracted_to:`** — automatically add `[[CORE - X]]` to the frontmatter of the source journal for each adopted candidate

## Report Format

```
# Extraction ritual — <date range>
N journals reviewed · M candidates identified

## ⭐ Adoption recommended (score 8+)
1. **"X는 Y다"** — score 9/10
   - Source: [[2026-05-13]] candidate 1
   - Evaluation: strong atomicity, own voice OK, no overlap with existing CORE
   - On promotion → new `CORE - X는 Y다.md`

2. ...

## 🟡 Hold (score 5-7)
3. **"..."** — score 6/10
   - Source: ...
   - Gap: too broad (needs to specify "what Y exactly is")
   - Recommendation: revisit next week or split

## ❌ Discard (score 4 or less)
4. **"..."** — score 3/10
   - Gap: not own voice, just summarizing external material (move to SOURCE)

## 📊 Meta
- Journals reviewed: N
- Total candidates: M
- Adoption recommended: K (healthy weekly rate is 2-3)
- Average atomicity score: X/10
```

## Common Mistakes

| Mistake | Fix |
|---|---|
| Recommending 5+ adoptions per week | Atomicity should average out. 2-3 per week is healthy. If you keep recommending too many, re-examine scoring |
| Skipping the overlap check with existing CORE | Vault search is mandatory before adoption — if a similar CORE exists, hold or merge instead |
| Skipping the "Hold" category, treating it as adopt/discard binary | Hold = revisit next week. Preserves valuable but not-yet-atomic candidates |
| Skipping own-voice verification | Check every candidate: "Is this their phrasing, or summarized external material?" |
| Auto-adopting | Get explicit user adoption. No auto-promotion |
| Forgetting to update the journal's `extracted_to:` | Update the source journal's frontmatter immediately after adoption — traceability is the whole point |

## Time Budget

| Journal count | Review time | Priority |
|---|---|---|
| 3-7 | 20-30 min | All "💎 추출 후보" sections across all journals |
| 8-15 | 30-45 min | Prefer journals rich in candidates (those with 3+) |
| 15+ | sampling required | Last 7 journals, or the projects the user names |

## Red Flags

- "💎 추출 후보" sections are all empty → journal-writing rule violated (don't polish, keep raw tone). Notify user and stop extraction
- All candidates score < 5 → the journal is a diary / chitchat, not build activity. Notify user
- Recommending 5+ adoptions per week → scoring is too lenient. Re-examine
- The same atomic claim appears in 2 journals → flag for consolidation, adopt only one

## Example: Adoption recommended (score 9)

```
1. **"AI는 도구이지 판단자가 아니다"** — score 9/10
   - Source: [[2026-05-13]] candidate 1 ("AI가 코드 95% 짜도 검증은 사람")
   - Evaluation:
     ✅ 1 idea (single contrast: tool vs judge)
     ✅ "X는 Y다" complete form
     ✅ Own voice (an assertion, not an external citation)
     ⚠️ Overlap: [[CORE - AI는 도구, 판단은 사람]] already exists — same essence. **Downgrade to hold**
     ✅ No time anchor
   - Recommended action: absorb into the existing CORE, only update `extracted_to:` on the source journal
```

## Example: Discard (score 3)

```
2. **"AI 협업 도구가 빠르게 발전 중"** — score 3/10
   - Source: [[2026-05-12]] candidate 1
   - Evaluation:
     ❌ Objective fact (not own voice)
     ❌ Weak "X는 Y다" form
     ❌ Time anchor ("빠르게 발전 중" = anchored to the current moment)
   - Recommendation: move to a SOURCE note or discard
```

## Auto-generated CORE frontmatter

Frontmatter auto-generated for the CORE note on adoption (matches the `TPL - Core` convention):

```yaml
---
type: core
title: <complete Y sentence>
topics:
  - <inferred or user input>
channels: [linkedin, blog, teaching]
audience: [dev, pm, non-dev-product-builder]
tone: direct
status: draft
created: YYYY-MM-DD (today)
source_journal: "[[journal file]]"
---

# CORE - <complete Y sentence>

## 💡 핵심 주장
> **"<core sentence on a single line>"**

(1-2 sentences of context extracted from the source journal)

## 🤔 왜 이게 중요한가?
- (user fills in)

## 🎯 실제 적용 예시
- (user fills in)

## 📂 연결된 콘텐츠

### 출처 저널
- [[<journal file>]]

### 관련 CORE
- (auto-suggested or filled in by user)

## 태그
#core #<topic>
```

## Journal frontmatter update

On CORE adoption, append `[[CORE - X]]` to the source journal's frontmatter `extracted_to:` array:

```yaml
# Before
extracted_to: []

# After
extracted_to:
  - "[[CORE - AI는 도구이지 판단자가 아니다]]"
```

This tracking enables later retrospectives like "which journal yielded the most CORE notes?"

## Vault-Specific Context

Conventions vary per vault. Confirm the journal path, CORE folder, and frontmatter keys against the vault's guide (e.g. `_GUIDES/CONTENT_PIPELINE.md`) before mapping:

- **LYT (Linking Your Thinking)**: journal → promote to `Atlas/02-POV/`
- **Personal Branding vault**: journal → `20_Core/CORE - X.md`
- **PARA**: journal → `Resources/Permanent Notes/`
- **Zettelkasten**: Fleeting Notes → Permanent Notes

The CORE note title convention also differs per vault — decide on simply "the Y sentence" or "TYPE - sentence" format before proceeding.
