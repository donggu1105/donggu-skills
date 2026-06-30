---
name: decompose-canon
description: Use when a finished vault post is one you'd hold up as a best/canon piece and its reusable parts should live as atoms for future writing — filling a post's `## 부품` table, replacing *(추출 예정)* placeholders, or mining a proven post into the atom bank. Not for writing new posts (use writing-social-content) or weekly journal "추출 후보" sweeps (use extract-core).
---

# Decompose Canon (정전 역분해)

## Overview

One proven post → a FEW reusable atoms (CORE + 40_Snippets parts) + back-links. The reverse half of the vault loop: good posts FEED the building blocks that future posts get assembled from.

**Core principle: link before create, recommend before adopt, 동구's actual words over reworded prose.** A post is not a quarry for 15 notes — most of its "ideas" already live in existing CORE. Find those first.

**REQUIRED SUB-SKILL:** Use `donggu-obsidian:extract-core` for CORE atomicity scoring (5 criteria, adopt 8+/hold/discard, healthy yield 2-3/week). This skill adds three things extract-core lacks: **post input** (not journals), **부품 extraction**, and **bidirectional wiring into the post**.

## When to Use
- A post is marked `canon` / "이건 내 좋은 글" → mine its parts
- A post's `## 부품` table has *(추출 예정)* placeholders to fill
- Building the reusable atom bank from already-proven posts

## When NOT to Use
- Writing a NEW post / spreading to channels → `writing-social-content` (forward fan-out)
- Weekly journal "💎 추출 후보" sweep → `extract-core`
- A mediocre post — only decompose posts you'd hold up as canon

## Workflow

1. **Read the post's 정본** (`## Draft` / `## 발행` / 본문) + its existing `## 부품` table.
2. **Search the vault FIRST (mandatory, before proposing anything):**
   - `20_Core/` — does a CORE already say this? → prefer **LINK/merge over new**
   - `40_Snippets/` — does a snippet already exist? → reuse
   - `60_MOCs/` — which existing hub does this attach to? (do NOT spawn a new MOC)
3. **Form candidate atoms (draft only — don't create yet):**
   - **CORE candidates** — score with `extract-core`'s 5 criteria. "X는 Y다" form, 동구 voice. **Healthy yield 1-2 per post.** If existing CORE covers it, recommend linking, not a new note.
   - **부품 candidates** — typed HOOK / ONE / PROOF / LESSON. Each is the **actual line from the post (near-verbatim)**, not a reworded essay. Score 4 pts: 재사용성·자족성·동구 목소리·중복 없음. Adopt 3+/4.
4. **조화 평가 — 동구 컨펌 게이트 (필수 STOP).** 만들기 전에, 각 후보가 **기존 볼트 원자와 어떻게 조화를 이룰지**를 한 표로 보여주고 명시적 채택을 받는다. 채점·문장만 나열하면 안 됨 — 반드시 *기존 원자와의 관계*를 보여준다:
   - 후보별 판정: **중복→LINK**(기존 노트명 명시) · **보완→NEW**(붙을 기존 MOC 명시) · **머지→MERGE**(어느 노트에 합칠지) · **충돌→FLAG**(어느 기존 원자와 모순되는지).
   - 전체 그림 한 줄: 이 분해가 atom bank를 어떻게 바꾸나 — 「CORE +N · 부품 +N · 링크 N · 머지 N」, 새 CORE가 강화하는 MOC 군집.
   - 그런 다음 **STOP.** "CORE 1, 부품 2·5 채택 / 3은 기존 링크" 식 명시 응답을 기다린다. **자동 생성 금지.**

   ```
   | 후보 (실제 문장) | 유형 | 판정 | 기존 원자와의 관계 | 권고 |
   |---|---|---|---|---|
   | "…동구 한 줄…" | ONE | 보완(NEW) | [[ONE - …]]와 다른 각도 | 신설 → [[MOC - …]] |
   | "…동구 한 줄…" | CORE | 중복(LINK) | [[CORE - …]]가 이미 말함 | 링크만 |
   ```
5. **Create adopted atoms, exact vault conventions:**
   - CORE → `20_Core/CORE - <문장>.md` (frontmatter per `TPL - Core`)
   - 부품 → `40_Snippets/<타입폴더>/<TYPE> - <slug>.md` (폴더: Hooks·One-liners·Proof·Lessons·CTA). frontmatter는 `TPL - Snippet` 규약: `snippet_type:` 소문자(hook|one-liner|proof|lesson|cta), `topics·channels·tone·status·created`. 본문: `## 문장`(인용)·`## 사용 맥락`·`## 변형 버전`·`## 출처/근거`(출처 역링크)
6. **Wire bidirectionally:**
   - **Post**: fill `## 부품` table with real wikilinks (replace placeholders); frontmatter `canon: true`, `core_principle: "[[CORE - …]]"`, `decomposed_to: [...]`; ensure post is in its `VOICE - <ch>` `canon:` list.
   - **Each atom**: `## 연결` back-link to the source post; CORE → attach to the existing MOC.
7. **Report**: N proposed · scored · adopted · linked · 머지/링크로 흡수된 수. Flag if you wanted >2 new CORE (scoring too loose).

## 부품 atom shape (stay atomic)

```
---
type: snippet
snippet_type: hook        # 소문자: hook | one-liner | proof | lesson | cta
topics: [해자]
channels: [linkedin, blog]
tone: direct
status: evergreen
created: 2026-06-29
---
# HOOK - 팔란티어와 Clay 둘 다 잘 만들어서 이긴 게 아니다

## 문장
> "팔란티어와 Clay. 둘 다 잘 만들어서 이긴 회사가 아니다."

## 사용 맥락
- 컨트래리안 케이스 오프닝. 고유명사를 첫 3줄에 선출.

## 출처/근거
- [[LinkedIn - 잘 만드는 건 더 이상 무기가 아니다]]
```

The body is the 동구 line + ONE line of "왜 재사용되나". Not a memo.

## Common Mistakes (from baseline)

| Mistake | Fix |
|---|---|
| 한 글에서 14개 노트 쏟아냄 | 원자성 채점 + 예산: CORE 1-2, 부품 소수. extract-core "5+ = 너무 헐렁" |
| 기존 CORE 무시하고 평행 노트 신설 | **볼트 검색 먼저.** 있으면 링크/머지. (글의 부품 표가 이미 기존 CORE를 가리킴) |
| 원자를 컨설팅 메모로 부풀림 (Why/Use Case/Framework 표) | 부품 = 글의 실제 한 줄 + why 한 줄. CORE = "X는 Y다" + 짧은 맥락 |
| 영어 전략 프로즈로 다시 씀 | 동구 평서체·실제 표현 보존 (목소리는 사람이 검증) |
| 영어 MOC 새 허브 생성 | 기존 MOC(한글)에 **붙임.** 새 MOC는 명시 요청 시만 |
| 포스트에 역배선 안 함 | 부품 표·`core_principle`·`decomposed_to`·`canon` 채움 |
| 자동 생성 | 채택은 동구가. recommend → STOP → create |
| 미래 글감·관련 토픽 스프롤 | 분해만. 아이디에이션은 범위 밖 |

## Red Flags — STOP

- CORE 후보가 3개 이상 → 채점이 헐렁하거나 기존 CORE와 중복
- 원자에 "Implementation Questions / Decision Framework" 류 섹션이 붙음 → 메모지, 원자 아님
- `source` 위키링크가 실제 파일명과 다름 → 발행 글 정확한 제목 확인
- 새 MOC를 만들고 있음 → 기존 MOC 먼저 찾았나?
- 영어로 쓰고 있음 → 볼트는 한글, 동구 목소리
- 조화 평가표 없이 바로 원자 생성 → STOP. 각 후보의 기존 원자 관계(중복/보완/머지/충돌)를 먼저 보여주고 컨펌받았나?
