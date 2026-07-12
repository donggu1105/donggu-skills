---
name: decompose-canon
description: Use when a finished vault post is explicitly selected as a best/canon piece and its reusable CORE or Snippet parts should be evaluated as metadata-only candidates. Not for routine published-content review or capture review (use extract-core).
---

# Decompose Canon (정전 역분해)

## Overview

One proven post → a FEW reusable atom proposals (CORE + 40_Snippets parts) with planned back-links. Good posts can feed future writing, but this skill only reads, evaluates, and creates candidate metadata.

**Core principle: link before new, 동구's actual words over reworded prose, candidate before mutation.** A post is not a quarry for 15 notes. Find existing atoms first.

**Boundary:** routine published posts and capture/routine review are handled by `extract-core`. 이 스킬은 사용자가 좋은 글을 정전으로 명시한 **explicit canon selection** 뒤에만 실행하는 deep decomposition이다. 일반 발행 완료 이벤트나 일일 routine 검토가 자동으로 이 스킬을 시작하지 않는다.

이 스킬은 어떤 자연어 채택을 받더라도 Vault mutation은 수행하지 않는다. 후보 생성 뒤 종료하며, 실제 변경 가능성은 후보 ID별 `core-review-approval` 계약만 판단한다.

**REQUIRED SUB-SKILL:** Use `donggu-obsidian:extract-core` for CORE atomicity scoring (5 criteria, adopt 8+/hold/discard, healthy yield 2-3/week).

## When to Use

- A post is marked `canon` / "이건 내 좋은 글" and the user explicitly requests decomposition
- A canon post's reusable CORE/Snippet parts need evaluation
- Existing atom-bank overlap and bidirectional-link proposals need review

## When NOT to Use

- Writing a new post / spreading to channels → `writing-social-content`
- Routine capture or curated Source review → `extract-core`
- Routine published-post review → `extract-core`
- A mediocre post — only evaluate posts the user explicitly selects as canon

## Workflow

1. **Read the post's canon body** (`## Draft` / `## 발행` / 본문) and existing parts metadata, read-only.
2. **Search the vault first:**
   - `20_Core/` — existing claim coverage; prefer `LINK` over `NEW`
   - `40_Snippets/` — existing near-verbatim parts
   - `60_MOCs/` — existing hub metadata; never create a new MOC here
3. **Form draft proposals without writes:**
   - **CORE** — score with `extract-core`'s 5 criteria. Healthy yield 1-2 per post.
   - **Snippet** — HOOK / ONE / PROOF / LESSON, near-verbatim. Score reuse, self-containment, voice, and overlap.
4. **Classify every proposal:** `LINK`, `NEW`, `MERGE`, `HOLD`, or `FLAG`, and name the existing atom/MOC relationship.
5. **Persist one metadata-only candidate per source/action.** Never combine atom creation, source backfill, MOC wiring, VOICE changes, or cleanup in one candidate.
6. **Show candidate codes and stop.** Natural-language choices such as "CORE 1 채택" are feedback only; they are not approval and trigger no write.

Candidate report shape:

```text
| candidate_code | candidate_type | proposal | existing relationship | planned single action |
|---|---|---|---|---|
| CR-YYYYMMDD-NNNNNN | new_core | "…동구 한 줄…" | [[60_MOCs/MOC - …]] 강화 | create_core_with_backlink |
```

## Candidate handoff — mandatory STOP

각 mutation 후보는 `extract-core`의 metadata-only contract와 동일하게 다음을 포함한다.

- `candidate_code`: `CR-YYYYMMDD-NNNNNN` 하나
- `source_note_path`: 안전한 non-Inbox Channel Pack 상대 경로 하나
- `source_sha256`: 생성 시점 lowercase SHA-256 하나
- `candidate_type`: 실제 queue enum 하나
- `proposed_changes`: 결정적 action 하나

후보 생성 뒤 종료한다. 정확히 `CR-YYYYMMDD-NNNNNN 승인|보류|거절` 형식의 후보 ID별 메시지만 `core-review-approval`에 전달한다. 쉼표 목록, 범위, `전체 승인`, `다 적용`, 자연어 채택은 무효이며 blanket approval로 해석하지 않는다.

`core-review-approval`이 현재 결정적으로 지원하는 `new_core`/`link_existing`/`fix_link` action만 그 스킬 내부 검증을 통과할 수 있다. Snippet 신설, `MERGE`, 포스트 부품표·`canon`·VOICE 수정처럼 지원되지 않는 제안은 `skill_drift`/해당 queue enum 후보로만 남기고 승인돼도 release/re-evaluation할 뿐 Vault를 변경하지 않는다. 이 스킬은 helper를 호출하거나 파일을 생성·수정·이동·삭제하지 않는다. **STOP.**

## Proposed atom shape (review reference only)

```yaml
candidate_type: skill_drift
proposal:
  atom_kind: snippet
  snippet_type: hook
  claim: "팔란티어와 Clay. 둘 다 잘 만들어서 이긴 회사가 아니다."
  source_note_path: 50_Channel_Packs/...
  planned_links:
    - 60_MOCs/MOC - 해자.md
```

This is candidate metadata, not a note template and not permission to create a file.

## Common Mistakes

| Mistake | Fix |
|---|---|
| 한 글에서 14개 후보 생성 | 원자성 채점 + 예산: CORE 1-2, 부품 소수 |
| 기존 CORE 무시하고 평행 후보 생성 | Vault 검색 먼저; 있으면 `LINK`/`MERGE` 후보 |
| 원자를 컨설팅 메모로 부풀림 | 부품은 실제 한 줄, CORE는 `X는 Y다` 주장 |
| 영어 전략 prose로 다시 씀 | 동구 평서체·실제 표현 보존 |
| 새 MOC를 제안 없이 생성 | 기존 MOC 관계를 candidate metadata에만 기록 |
| 자연어 채택 뒤 파일 수정 | 자연어 채택은 승인 아님; 후보 ID별 승인만 handoff |
| 후보 하나에 여러 파일 정리 포함 | source 하나 + action 하나로 분리 |

## Red Flags — STOP

- CORE 후보가 3개 이상 → 채점이 헐렁하거나 기존 CORE와 중복
- candidate code 없이 채택을 요청함 → metadata candidate부터 생성
- 자연어 선택을 승인으로 간주함 → 무효, 변경 0건
- 여러 후보를 한 번에 승인하려 함 → 후보 ID별 한 메시지만 허용
- 새 atom, post, MOC, VOICE 파일을 직접 만지려 함 → 이 스킬 범위 밖
- 지원되지 않는 Snippet/merge action을 직접 보완하려 함 → `core-review-approval` re-evaluation로 종료
