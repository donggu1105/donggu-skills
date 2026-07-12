---
name: extract-core
description: Use when reviewing recent Obsidian capture notes and published content to propose atomic CORE candidates, score them against existing CORE notes, and place metadata-only proposals into a human-approved review queue without modifying the vault.
---

# Extract Core

## Core rule

**탐지·평가·제안까지만 자동화하고, Vault 변경은 후보 한 건의 명시 승인 뒤에만 수행한다.**

`00_Inbox`는 사용자의 의사결정 큐다. 자동 이동·승격·병합·삭제·상태 변경을 하지 않는다. 이 스킬은 후보를 만들고 보고하며, 실제 적용은 `core-review-approval`의 단일 후보 계약을 따른다.

## When to use

- 최근 `00_Inbox`와 `10_Sources`에서 재사용 가능한 주장을 찾을 때
- 발행 직후 콘텐츠에서 CORE 후보를 제안할 때
- 매일 05:40 검토 큐에서 신규·중복·링크·분류 후보를 묶어 볼 때
- 기존 CORE와 겹치거나 더 원자적으로 다듬어야 할 후보를 평가할 때

## Scope

기본 탐색 범위:

1. 최근 변경된 `00_Inbox/`
2. 최근 변경된 `10_Sources/`
3. 비교 대상인 `20_Core/`
4. 발행 이벤트가 가리키는 source note

전체 Vault를 읽지 않는다. 최근 변경, 미처리 발행 이벤트, 실패 delivery retry만 대상으로 삼고, 본문은 필요한 노트만 제한적으로 읽는다.

## Atomicity score

각 후보를 10점으로 평가한다.

| 기준 | 점수 | 질문 |
|---|---:|---|
| 한 주장 | 2 | 한 노트에 아이디어가 하나인가? |
| 완전한 문장 | 2 | `X는 Y다` 형태의 독립 주장인가? |
| 자기 목소리 | 2 | 외부 사실 요약이 아니라 사용자의 해석인가? |
| 기존 CORE와 비중복 | 2 | 유사 CORE에 흡수할 편이 낫지 않은가? |
| 시간 독립성 | 2 | 특정 시점 표현 없이 다시 쓸 수 있는가? |

- 8~10: `new_core` 또는 기존 CORE 강화 후보
- 5~7: `hold` 후보
- 0~4: 제안하지 않거나 SOURCE로 유지

점수는 자동 승격 권한이 아니다.

## Workflow

1. 최근 source path와 발행 이벤트를 읽기 전용으로 수집한다.
2. path가 Vault root 아래의 안전한 상대 `.md`인지 확인한다. 절대경로, `..`, symlink 탈출, `.env*`, binary를 제외한다.
3. source excerpt를 읽고 atomic claim을 추출한다. 장부에는 본문 저장 금지이며, metadata와 제한된 redacted excerpt만 전달한다.
4. `20_Core` 제목·path metadata 전체와 관련 CORE excerpt를 비교해 중복 여부를 판정한다.
5. 후보 하나에는 source 하나, action 하나만 둔다. 다른 정리 작업을 끼워 넣지 않는다.
6. source path와 source SHA-256을 후보 생성 시점에 고정한다.
7. 후보를 Supabase 장부에 `proposed`로 기록한다. 사용자에게 보이는 candidate code는 `CR-YYYYMMDD-NNNNNN` 형식이다.
8. 신규·retry 후보를 합쳐 우선순위 상위 3~5건만 Discord 일일 보고로 보낸다.
9. 사용자가 정확히 한 candidate code에 `승인`, `보류`, `거절` 중 하나를 붙여 답하도록 안내한다.
10. 7일 동안 응답이 없으면 삭제하지 않고 `stale` 상태로 보류한다.

## Candidate contract

후보는 다음을 충족해야 한다.

- `candidate_code` 하나
- 안전한 `source_note_path` 하나
- 생성 시점의 `source_sha256` 하나
- `candidate_type` 하나
- `proposed_changes` action 하나
- 1,800자 이하의 안전한 Discord 요약
- 승인 명령 footer에 현재 candidate code 정확히 한 번

허용 후보 유형은 `new_core`, `merge`, `fix_link`, `classification`, `status_cleanup`, `skill_drift`다. 이 스킬은 후보 유형을 제안할 수 있지만, 결정적으로 적용할 수 없는 action을 자연어로 보완하지 않는다.

## Human approval

유효한 명령 형식:

```text
CR-YYYYMMDD-NNNNNN 승인
CR-YYYYMMDD-NNNNNN 보류
CR-YYYYMMDD-NNNNNN 거절
```

- 항목별 승인만 허용한다.
- 쉼표 목록, 범위, `전체 승인`, `둘 다 승인`, 추가 설명이 붙은 문장은 실행하지 않는다.
- `보류`는 DB·Vault를 변경하지 않는다.
- `거절`은 해당 후보 하나만 reject한다.
- `승인`은 claim 후 현재 path·SHA·action을 다시 검증한다.
- source SHA가 달라졌으면 이전 승인을 재사용하지 않고 release 후 재평가한다.
- source가 `00_Inbox`면 승인되어도 자동 수정하지 않고 `recommend_only`로 유지한다.

실제 처리는 반드시 `core-review-approval` 스킬로 넘긴다.

## Daily report

```text
# CORE 검토 — YYYY-MM-DD
신규 N · 재시도 M · 7일 보류 S

1. CR-YYYYMMDD-NNNNNN · new_core · 9/10
   주장: X는 Y다
   판단: 자기 목소리, 기존 CORE와 비중복
   영향: 새 CORE 제안 · Vault 변경 전
   명령: CR-YYYYMMDD-NNNNNN 승인|보류|거절
```

후보가 없고 retry도 없으면 알림하지 않는다. URL·URI·이메일·전화번호·시크릿·내부 사용자 ID를 보고에 넣지 않는다.

## Failure handling

- 장부 적재 실패: source event를 처리 완료로 표시하지 않는다.
- Discord 전송 실패: 후보를 재생성하지 않고 같은 candidate delivery만 재시도한다.
- duplicate event: candidate와 메시지를 추가 생성하지 않는다.
- malformed model output: 후보를 저장하지 않고 event를 queued로 남긴다.
- source SHA drift: 적용하지 않고 `proposed`로 release한다.
- skill drift: 재현·테스트·명시적 스킬 수정 전까지 보고만 한다.

## Never

- `00_Inbox`를 자동으로 비우기
- 후보 여러 건을 한 요청에서 승인하기
- 승인 전에 CORE 생성·병합·이동·삭제·상태 변경하기
- source hash 불일치를 강행하기
- 장부에 Vault 본문이나 시크릿 저장하기
- 실패 retry에서 새 후보를 만들기
- 스킬을 자동 수정하기
- 후보가 없는데 Discord 알림 보내기

## Related skills

- `checking-vault-health`: 파이프라인 병목 탐지
- `finding-duplicate-notes`: 기존 CORE 중복 심화 점검
- `decompose-canon`: 완성 글에서 재사용 부품 역추출
- `core-review-approval`: 단일 후보 승인·보류·거절 및 안전 적용
