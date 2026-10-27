---
name: extract-core
description: Use after a post is published (or the user says 코어 뽑아줘/환류/코어 환류) to score its reusable claims against existing CORE notes and propose LINK/NEW/MERGE/HOLD; writes the vault only after the user picks a candidate.
---

# Extract Core

발행된 글에서 재사용할 주장(CORE 후보)을 뽑고, 기존 CORE와 비교해 제안한다. 사용자가 후보를 고르면 그때 CORE 노트를 만들거나 기존 CORE에 연결한다.

**핵심 규칙: 기존 CORE 연결이 먼저, 동구가 실제로 쓴 말을 보존, 사용자가 고르기 전엔 Vault 변경 0건.**

## Two moments

| 시점 | 트리거 | 하는 일 |
|---|---|---|
| **작성 단계** (기본) | `writing-social-content`가 초안을 확정해 보여 줄 때 (항상) | 초안 논지를 기존 CORE와 대조해 LINK/NEW/MERGE/HOLD 제안. 사용자가 고르면 CORE를 만들거나 연결하고, 원하면 그 CORE 문장으로 초안 논지를 다듬는다 |
| **발행 단계** (확인) | 실발행 직후, LinkedIn "발행했어" | 작성 단계에서 이미 연결됐으면 재리뷰하지 않는다. 발행 본문이 초안과 논지가 달라졌는지만 보고, 파생 채널 노트 `## 연결`을 맞춘다. 작성 단계 리뷰가 없던 글이면 전체 리뷰 |

작성 단계 리뷰는 초안 아래 짧게 붙인다 (후보 1~3줄 + 추천 1개). 초안 본문을 CORE에 맞춰 사용자 몰래 고치지 않는다. 사용자가 "그 코어로 다듬어"라고 할 때만 논지를 바꾼다. 초안이 아직 저장되지 않았으면 CORE의 `- 출고:` 링크는 저장 경로가 정해진 뒤 단다.

## When to use

- `writing-social-content`로 초안을 확정했을 때 (작성 단계)
- `publish-sns`로 실발행이 끝난 직후 (스레드·티스토리·메일리, 장부 기록 확인 후)
- 사용자가 LinkedIn 등을 직접 올렸다고 말한 직후 ("발행했어")
- 사용자가 "코어 뽑아줘", "환류", "코어 환류", "디콤포즈 스킬로 코어 환류"라고 할 때
- 밀린 발행 글을 한꺼번에 점검할 때 (`status: published`인데 본문 `## 연결`에 `CORE:` 줄이 없는 노트. 옛 노트는 `core_principle`도 확인)

## When NOT to use

- 사용자가 "정전", "이건 내 좋은 글"이라며 깊게 쪼개 달라고 할 때 → `decompose-canon`
- 초안 작성·채널 변환 → `writing-social-content`
- 발행 자체 → `publish-sns`
- `00_Inbox` 캡처: 사용자가 노트 하나를 지정한 경우에만 읽기 전용 추천으로 본다. Inbox에서 CORE를 만들지 않는다.

## Paths

- Vault: `~/Library/Application Support/obsidian/obsidian.json`에서 `open` 볼트를 찾는다 (현재 `.../iCloud~md~obsidian/Documents/ontology`). 그 아래 `Personal Branding/`.
- 스키마 정본: `Personal Branding/_GUIDES/RULES.md` (먼저 읽는다).
- 원천: `40_Channel_Packs/<채널>/<채널> - <제목>.md`의 발행 본문 (`## 본문` / `# 발행 원고` / 옛 노트는 `## Draft`·`## 발행`). `## 편집 메모`는 근거로 쓰지 않는다.
- 비교 대상: `20_Core/CORE - <완성 문장>.md` 전체 제목 + 축이 가까운 노트 본문. 같은 축의 `30_Foundations/FOUND - *`, `10_Sources/SOURCE - *`, `80_Cases/CASE - *`도 제목으로 훑어 근거 링크 후보를 찾는다.
- 토폴로지(노드·엣지·배선): `references/topology.md`. 작업 전에 읽는다.
- iCloud 파일이 비어 읽히면(dataless) `brctl download <file>` 후 다시 읽는다.

## Atomicity score (10점)

| 기준 | 점수 | 질문 |
|---|---:|---|
| 한 주장 | 2 | 아이디어가 하나인가? |
| 완전한 문장 | 2 | `X는 Y다` 형태로 혼자 서는가? |
| 자기 목소리 | 2 | 외부 사실 요약이 아니라 동구의 해석인가? |
| 기존 CORE와 비중복 | 2 | 기존 CORE에 연결하는 편이 낫지 않은가? |
| 시간 독립성 | 2 | 특정 시점 표현 없이 다시 쓸 수 있는가? |

- 8~10: `NEW` 또는 기존 CORE `MERGE`(강화) 후보
- 5~7: `HOLD`
- 0~4: 제안하지 않는다
- 건강한 수확량: 글 하나에 CORE 후보 1~2개. 3개 이상이면 채점이 헐겁거나 기존 CORE와 겹친다.

## Workflow

1. 원천을 읽는다. 작성 단계면 방금 확정한 초안, 발행 단계면 발행 본문만 대상으로 하고 편집 메모·전략 섹션은 근거로 쓰지 않는다.
2. `20_Core/`를 제목·본문으로 검색해 같은 축의 기존 CORE를 찾고 가까운 2~3개를 끝까지 읽는다. 같은 축 FOUND·SOURCE·CASE가 있으면 근거 링크 후보로 적어 둔다 (FOUND가 같은 구조를 이미 설명하면 CORE는 결론만 소유).
3. 주장마다 결과 하나를 정한다.
   - `LINK`: 기존 CORE가 이미 그 주장을 가진다 → 연결만
   - `NEW`: 새 원자 CORE
   - `MERGE`: 기존 CORE의 근거·적용을 강화
   - `HOLD`: 보류 (점수 5~7, 또는 근거가 이 글 하나뿐)
4. 사용자에게 보여 준다. 후보마다 한 줄씩:
   ```
   1. NEW · 9/10 · "X는 Y다"  ← 추천
      근거: 본문 속 동구 문장 인용 한 줄
      인접: [[CORE - …]] — 결이 다른 이유 한 줄
      근거·MOC: [[FOUND/SOURCE/CASE - …]] · [[MOC - …]] (있을 때)
   2. LINK · [[CORE - …]] — 이미 같은 주장
   ```
   추천 하나를 먼저 둔다. `NEW`면 완성 문장 제목 후보를 2~3개까지 함께 준다.
5. **멈추고 고르게 한다.** 사용자가 번호를 고르기 전에는 아무것도 쓰지 않는다. "1번으로만 넣어줘" → 정확히 그 하나만 만든다. 고르지 않은 후보의 논지는 새 CORE의 믿음·적용 섹션에 녹이고 따로 노트를 만들지 않는다.
6. 적용 (사용자가 고른 뒤, 같은 턴에 전부):
   - `NEW`: 아래 CORE 노트 형식으로 `20_Core/CORE - <완성 문장>.md` 생성
   - `MERGE`: 기존 CORE의 근거·적용·연결된 콘텐츠에 이 글을 추가 (기존 문장은 고치지 않음)
   - `LINK`: 새 노트 없이 아래 링크만
   - 링크 배선: **`references/topology.md`의 역방향 배선 표를 그대로 따른다** (채널 노트 `## 연결`, 관련 CORE 양방향, 근거로 쓴 SOURCE·FOUND·CASE, MOC 1~2개). 레거시 필드는 갱신만 하고 새로 만들지 않는다.
7. 다시 읽어 확인하고, 만든/고친 파일 목록만 짧게 보고한다.

## CORE note shape

2026-10 기준 살아 있는 형식. 스키마 정본은 `_GUIDES/RULES.md`(필수 frontmatter는 `type` 하나, 선택 `topics`·`created`). 폐지 필드(`persona`, `pillar`, `audience`, `arc`, `track`, `core_action`, `core_targets`, `lead_label`)는 새 노트에 쓰지 않는다. 기존 노트의 폐지 필드는 지우지 않는다.

```markdown
---
type: core
topics: [FDE, AX, ...]
status: draft
created: YYYY-MM-DD
---

# CORE - <완성 문장>

## 💡 핵심 믿음

> **"<동구가 원천 글에 실제로 쓴 문장, 또는 그 압축>"**

<2~3줄 보충>

---

## 🤔 왜 이렇게 믿게 되었나

관찰·경험 (원천 글의 사실). 외부 개념을 확장한 부분은 "나의 해석"으로 구분한다.

---

## 💬 자주 쓰는 표현

- "<원천 글의 실제 문장>"

---

## 근거와 연결

- 객관 구조: [[FOUND - …]]
- 출처: [[SOURCE - …]]
- 출고: [[<채널> - …]]
- 관련: [[CORE - …]] — 관계 한 줄
- MOC: [[MOC - …]]
```

- 새 CORE는 `status: draft`로 만든다. 다른 글에서 다시 쓰여 검증되면 사용자가 `evergreen`으로 올린다.
- 선택 섹션 (원천 글에 재료가 있을 때만): `📖 <A> vs <B>` 대비 표, `🎯 이 원칙의 적용`(또는 글이 준 질문 목록), `🎤 활용 시나리오`. 재료 없이 칸을 채우지 않는다.

## Never

- 사용자가 고르기 전에 CORE 생성·수정·링크 변경
- 글 하나에서 CORE 3개 이상 생성
- 기존 CORE 검색 없이 `NEW` 제안
- 원천 글에 없는 경험·성과를 CORE 근거로 추가
- 동구 문장을 영어 전략 문체나 컨설팅 메모로 바꿔 쓰기
- `00_Inbox` 노트로 CORE 만들기
- 새 MOC 생성 (기존 MOC 관계는 제안에만 적는다)

## Related

- `decompose-canon`: 정전으로 고른 글의 깊은 역분해
- `publish-sns`: 실발행 뒤 이 스킬로 넘긴다
- `writing-social-content`: 글 작성
