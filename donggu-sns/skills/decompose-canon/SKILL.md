---
name: decompose-canon
description: Use when the user marks a finished post as canon (정전, 이건 내 좋은 글, 디콤포즈해줘) and wants its reusable CORE claims and Teaching parts extracted; link-first, a few proposals, writes only what the user picks.
---

# Decompose Canon (정전 역분해)

검증된 글 하나 → 재사용 원자 몇 개(CORE 후보 + 강의 부품 후보)와 연결 계획. 좋은 글을 앞으로의 글감으로 되돌리는 작업이다.

**핵심 규칙: 새로 만들기 전에 연결, 다시 쓴 문장보다 동구가 실제로 쓴 문장, 사용자가 고르기 전엔 Vault 변경 0건.** 글 하나는 노트 15개를 캐는 채석장이 아니다.

## When to use

- 사용자가 글을 정전으로 지목하고 쪼개 달라고 할 때 ("정전", "이건 내 좋은 글", "디콤포즈해줘", "디컴포즈")
- 정전 글의 CORE·강의 부품을 함께 평가할 때
- 기존 원자와 겹침·양방향 링크를 점검할 때

## When NOT to use

- 일반 발행 직후 CORE 후보 → `extract-core` (평범한 발행 글은 이 스킬로 시작하지 않는다)
- 새 글 작성·채널 변환 → `writing-social-content`

## Workflow

1. **정전 본문 읽기**: 발행 본문(`## 본문` / `# 발행 원고` / 옛 `## Draft`)과 기존 `## 연결`·`## 부품`을 읽는다. 정전 목록은 `40_Channel_Packs/<채널>/_anchors/VOICE - <채널>.md`의 `canon:`이다. Vault 경로·iCloud 처리·스키마는 `extract-core`의 Paths를 따른다.
2. **먼저 검색**:
   - `20_Core/`: 이미 그 주장을 가진 CORE가 있으면 `LINK`가 우선
   - `60_Projects/Teaching/PARTS - *.md`: 기존 강의 부품 (읽기 전용)
   - `50_MOCs/`: 기존 허브. 새 MOC는 만들지 않는다
3. **후보 만들기 (쓰기 없음)**:
   - **CORE**: `extract-core`의 원자성 점수 5기준으로 채점. 글 하나에 1~2개
   - **강의 부품**: Hook / Closing / Confession / Demo. 본문 문장 그대로. 재사용성·자기완결성·목소리·겹침을 본다
4. **분류**: 후보마다 `LINK` / `NEW` / `MERGE` / `HOLD` / `FLAG`와 기존 원자·MOC와의 관계를 적는다.
5. **보고하고 멈춘다**:
   ```
   | # | 종류 | 결과 | 후보 (동구 문장) | 기존 관계 | 적용하면 |
   |---|---|---|---|---|---|
   | 1 | CORE | NEW 9/10 | "…" | [[CORE - …]]와 결이 다름 | CORE 생성 + 링크 4곳 |
   | 2 | 부품 | Hook | "…" | 없음 | 채널 노트 부품표에 기록 |
   ```
   사용자가 번호를 고를 때까지 아무것도 쓰지 않는다.
6. **고른 것만 적용**:
   - CORE: `extract-core`의 적용 단계와 CORE 노트 형식을 그대로 따른다 (생성·MERGE·LINK + `## 연결` 배선).
   - 강의 부품: 기본은 원천 채널 노트의 `## 부품` 표에 행으로 기록한다. `60_Projects/Teaching/PARTS - *.md`에는 사용자가 명시할 때만 추가한다.
   - 정전 지정: 사용자가 원하면 해당 채널 `VOICE - <채널>.md`의 `canon:` 목록에 추가한다 (채널 노트 frontmatter에 `canon` 필드를 만들지 않는다).
7. 다시 읽어 확인하고, 바뀐 파일 목록만 보고한다.

## Common mistakes

| 실수 | 고치기 |
|---|---|
| 글 하나에서 후보 14개 | 채점 + 예산: CORE 1~2, 부품 소수 |
| 기존 CORE 무시하고 평행 후보 | 검색 먼저, 있으면 `LINK`/`MERGE` |
| 원자를 컨설팅 메모로 부풀림 | 부품은 실제 한 줄, CORE는 `X는 Y다` |
| 영어 전략 문체로 재작성 | 동구 평서체·실제 표현 보존 |
| 새 MOC를 묻지 않고 생성 | 기존 MOC 관계만 기록 |
| 고르기 전에 파일 수정 | 보고 후 멈춤, 고른 것만 적용 |

## Red flags — STOP

- CORE 후보가 3개 이상 → 채점이 헐겁거나 기존 CORE와 중복
- 사용자가 고르지 않았는데 쓰려 함
- 새 원자·MOC·VOICE 파일을 묻지 않고 만들려 함

## Related

- `extract-core`: 점수 기준, CORE 노트 형식, 링크 배선의 정본
- `publish-sns`, `writing-social-content`
