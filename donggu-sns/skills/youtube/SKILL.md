---
name: youtube
description: Use when planning, building, reviewing, or operating the user's YouTube channel in Obsidian, including long-form episodes, Shorts packs, title-thumbnail hypotheses, production safety, analytics retrospectives, and post-publication CORE reconciliation.
---

# YouTube

## Overview

YouTube를 기존 글의 영상 변환기가 아니라 **독립 제작 라인**으로 운영한다. 기존 CORE·CASE·Blog는 선택 입력이며, 모든 발행물은 마지막에 CORE 환원 `create | update | merge | compose`를 완료한다.

## When to Use

- YouTube 아이디어를 캡처·검증·승격할 때
- Longform + Shorts Pack을 기획·제작할 때
- 제목·썸네일·훅 가설을 만들 때
- 촬영·편집·공개 안전성을 점검할 때
- 발행 후 리텐션·시청자·A/B 결과를 회고할 때
- 영상에서 CORE·Snippet·다음 콘텐츠를 환원할 때

경쟁 영상 자막·챕터·SRT 수집은 `baoyu-youtube-transcript`, 썸네일 설계·시각 QA는 `youtube-thumbnail-design`, 이미지 생성은 `get-ai-image`, 실제 Shorts 아티팩트 제작은 `make-shorts`, 주간 인박스 CORE 추출은 `extract-core`, 실제 SNS 게시는 `publish-sns`를 사용한다.

## Source of Truth

작업 전 vault에서 다음을 읽는다.

```text
Personal Branding/_GUIDES/SCHEMA.md
Personal Branding/_GUIDES/CONTENT_PIPELINE.md
Personal Branding/50_Channel_Packs/YouTube/INDEX - YouTube.md
Personal Branding/50_Channel_Packs/YouTube/_anchors/
```

상태·enum·완료 조건은 이 파일들이 정본이다. 스킬과 vault가 다르면 vault 정본을 따르고 스킬 수정 후보를 보고한다.

## Core Contract

1. **입력 독립성** — 기존 CORE·CASE·Blog 연결을 제작 입장 조건으로 삼지 않는다.
2. **패키징 선행** — 풀스크립트 전에 제목·썸네일·훅 가설 3개를 만든다.
3. **팩 단위** — 모든 Longform에서 Shorts 후보 0~3개를 검토한다.
4. **선택 발행** — Shorts 검토는 필수지만 발행은 독립 가치가 있을 때만 한다.
5. **공개 안전성** — 고객·회사·개인정보·시크릿을 사전 제작과 최종 편집에서 두 번 검수한다.
6. **필수 환원** — `reviewed` 전에 CORE 환원 4가지 중 하나를 실제 반영한다.
7. **전문 기능 분리** — transcript·thumbnail 구현을 복제하지 않고 upstream 전문 스킬을 호출한 뒤 결과만 Pack 계약에 맞춘다.

## Specialist Routing

### Transcript Routing

경쟁·참고 영상 URL에서 자막, 챕터, SRT, 표지, 번역 또는 반복 가공용 캐시가 필요하면 `baoyu-youtube-transcript`를 기본으로 사용한다.

`01-preproduction.md`에는 원문 전체를 복제하지 않고 다음만 남긴다.

- 출처 URL과 영상 메타데이터
- `evidence_labels`: `transcript-backed | competitor-backed | YouTube-validation-backed | strategic-judgment`
- 주장·근거·훅·구조·반론·CTA
- `관찰 / 해석 / 차용하지 않을 요소`
- 동구님의 1인칭 근거와 공개 경계에 맞게 바꿀 부분

`baoyu-youtube-transcript`가 원본 언어 트랙을 잘못 고르거나, 여러 트랙 요청으로 `429`가 나거나, 대화에 clean text만 즉시 반환해야 할 때만 `get-youtube-scripts`를 fallback으로 사용한다. fallback은 `*-orig` 우선·단일 트랙 다운로드 역할이며 저장·챕터·SRT를 대신하지 않는다.

### Thumbnail Routing

패키징 3가설 뒤 `youtube-thumbnail-design`으로 썸네일 브리프와 시각 QA를 수행한다. 이미지 생성 backend는 upstream의 `belt`가 준비돼 있으면 사용하고, 없으면 `get-ai-image`로 생성한다. backend가 달라도 아래 완료 계약은 같다.

- 의미가 다른 제목·썸네일 약속 최대 3개
- 120px 모바일 축소 가독성
- 우하단 재생시간 overlay safe zone
- 제목과 썸네일 정보 중복 여부
- 한 개의 명확한 focal point와 밝은·어두운 UI 대비
- 영상이 실제 이행하는 약속과 공개 안전성
- 실제 파일 경로·선택 이유·사용자 선택 기록

선택 전에는 최종 대본이나 발행 패키지를 확정하지 않는다. 결과는 `03-release-pack.md`에 기록한다.

## Workflow

### 1. Capture

`TPL - Video Idea`로 `_backlog/IDEA - <소재>.md`를 만든다.

최소 프로퍼티:

```yaml
type: video_idea
channel: youtube
status: captured
idea_source: field | viewer-question | community | search | build | trend | vault
series:
viewer_goal: acquire | retain | authority
format: long | short
production_effort: low | medium | high
visibility: private
evidence_labels: []
decision_reason:
```

한 줄 전제만으로 캡처한다. 캡처 단계에서 기존 CORE를 검색하거나 억지로 연결하지 않는다.

### 2. Editorial Gate

다섯 조건 중 네 개 이상이면 승격한다.

- 구체적인 시청자 질문
- 1인칭 근거 또는 방어 가능한 각도
- 화면·데모·다이어그램·비교
- 반복 가능한 시리즈
- 공개 가능한 경계

미달이면 `icebox` 또는 `dropped`다.

### 3. Package

의미 있게 다른 조합 3개를 작성한다.

| 조합 | 제목 | 썸네일 | 첫 훅 | 유입 표면 | 약속 |
|---|---|---|---|---|---|
| A | | | | search/home/subscriptions | |
| B | | | | | |
| C | | | | | |

각 조합에서 제목이 말하는 정보와 썸네일이 추가하는 정보를 분리한다. 동구님이 조합을 선택한 뒤에 아웃라인·대본을 확정한다. 편집 후 영상이 선택한 약속을 실제 이행하는지 다시 확인한다.

### 4. Build Episode

`<YYYY-MM-slug>/`에 다음 파일을 만든다.

```text
00-brief.md
01-preproduction.md
02-production.md
03-release-pack.md
04-retro-core.md
Shorts/   # 실제 make 후보만
```

`00-brief.md`만 lifecycle 프로퍼티를 소유한다. 단계 파일에 상태를 중복하지 않는다.

- `01-preproduction`: 수요·출처·transcript evidence·경험/추정 분리·반론·아웃라인·샷·합성 데이터
- `02-production`: A-roll·화면·B-roll·썸네일 사진·편집 패스·최종 QC
- `03-release-pack`: Longform 패키지와 Shorts 후보 판단
- `04-retro-core`: 24~48시간·7~14일 회고와 CORE 환원

익숙한 FDE·AX 주제는 불릿 아웃라인이 기본이다. 숫자·법률·보안·민감 표현만 풀스크립트로 쓴다.

### 5. Shorts Pack

모든 Longform에서 후보 0~3개를 검토한다.

```yaml
type: video_short
format: short
parent_episode: "[[00-brief]]"
short_type: cutdown | rerecord | screen-first | standalone
```

통과 기준:

- 첫 1~2초에 상황이나 결과가 이해됨
- 30~60초 안에 독립 결론이 있음
- 세로 화면에서 별도 가치가 있음
- Longform을 보지 않아도 이해 가능

통과하지 않으면 `skip`을 기록한다. Longform과 Shorts를 한 format 값에 합치지 않는다. 실제 `make` 후보만 Shorts 노트를 만든다.

### 6. Safety Gate

두 번 확인한다.

**사전 제작:** 고객·회사 특정, 동의, NDA, 합성 데이터, 외부 AI 도구 입력.

**최종 편집:** 내부 URL, 브라우저 탭, 알림, 파일명, 대시보드, 사용자 정보, API 키·토큰, 음성 속 고유명사.

불명확하면 `visibility: restricted`를 유지하고 발행하지 않는다.

### 7. Publish and Review

- 24~48시간: 유입 표면별 패키징과 Intro
- 7~14일: Top moment·Spike·Dip·댓글·시청자 구성·A/B
- 초기 6편 후, 이후 약 90일: 시리즈·포맷·시청자 목표·제작 노력 비교

YouTube Studio가 원시 지표 정본이다. vault에는 수치 복제가 아니라 관찰·판단·다음 행동을 기록한다.

## CORE Reconciliation

모든 Pack의 마지막 게이트다.

1. 새 주장 후보를 한 문장으로 쓴다.
2. `20_Core/`에서 유사 CORE를 검색한다.
3. 하나를 선택하고 실제 파일에 반영한다.

| action | 조건 | 완료 증거 |
|---|---|---|
| `create` | 새로운 atomic POV. 기본값. | 새 CORE 링크 |
| `update` | 기존 주장에 근거·사례·반례·조건 추가 | 수정된 canonical CORE 링크 |
| `merge` | 사실상 같은 CORE가 중복 | 병합된 canonical CORE 링크 |
| `compose` | 새로움이 복수 CORE의 조합 | 2개 이상 CORE와 조합 논리 |

`none`은 허용하지 않는다. 파생 Shorts가 부모와 같은 주장을 반복하면 새 CORE를 만들지 않고 부모의 `core_targets`를 참조한다. 독립 Shorts는 자체 환원을 수행한다.

frontmatter:

```yaml
core_action: create | update | merge | compose
core_targets:
  - "[[CORE - ...]]"
```

## Completion Gate

다음이 모두 확인돼야 완료라고 보고한다.

- [ ] Longform 패키징 가설과 최종 약속이 일치함
- [ ] 사용자 선택과 `decision_reason`이 기록됨
- [ ] 경쟁 영상 조사 시 `evidence_labels`와 관찰·해석·비차용 요소가 기록됨
- [ ] 썸네일 사용 시 실제 파일을 120px·overlay·정보 중복·약속·안전성 기준으로 검수함
- [ ] Shorts 후보 0~3개의 `make/skip` 판단이 기록됨
- [ ] 공개 안전성 2차 검수 완료
- [ ] 발행 후 회고 또는 아직 발행 전이라는 상태가 명확함
- [ ] CORE action을 선택함
- [ ] 대상 CORE를 실제 생성·수정·병합·연결함
- [ ] `core_action`·`core_targets`가 채워짐
- [ ] 완료 시에만 `status: reviewed`

## Common Mistakes

| 실수 | 수정 |
|---|---|
| 기존 글·CORE를 먼저 찾음 | YouTube 아이디어에서 독립 시작. 기존 자산은 선택 입력 |
| 대본 후 제목·썸네일 | 패키징 3가설을 먼저 만들고 편집 후 재확인 |
| 모든 Longform을 Shorts 3개로 자름 | 검토는 필수, 독립 가치 없으면 전부 skip |
| 파생 Shorts마다 새 CORE 생성 | 같은 주장은 부모 Pack의 CORE 대상 참조 |
| CTR·영상 길이 절대 기준 | 유입 표면·시리즈·유사 영상 문맥으로 해석 |
| `published`를 완료로 취급 | 회고 + CORE 환원 뒤에만 `reviewed` |
| raw footage를 iCloud vault에 저장 | vault 밖 media root에 저장하고 링크만 기록 |

## Red Flags

- 이름에 불필요한 수식어, Longform·Shorts format 혼합, CORE 환원 생략
- CORE 입력이 없다는 이유로 아이디어를 중단
- Shorts 후보 판단 없이 Pack 완료
- 고객 식별 가능 화면을 그대로 사용
- `core_targets`가 비었는데 `status: reviewed`

이 중 하나라도 있으면 완료하지 말고 해당 게이트로 돌아간다.

## Related Skills

- `baoyu-youtube-transcript` — 경쟁·참고 영상의 자막·챕터·SRT·표지·캐시 수집 기본 경로
- `get-youtube-scripts` — `*-orig` 선택·단일 트랙·429 회피가 필요한 captions-only fallback
- `youtube-thumbnail-design` — 썸네일 브리프·디자인·120px 시각 QA
- `get-ai-image` — `belt`가 없을 때 썸네일 이미지 생성 backend
- `make-shorts` — 승인된 Shorts의 9:16 CapCut 아티팩트 제작
- `extract-core` — 주간 인박스·저널 CORE 후보 추출
- `writing-social-content` — 영상에서 검증된 인사이트의 텍스트 채널 독립 작성
- `publish-sns` — 지원되는 외부 채널 발행
