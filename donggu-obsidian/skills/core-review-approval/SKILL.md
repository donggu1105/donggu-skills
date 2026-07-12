---
name: core-review-approval
description: "Use when a Discord message contains a CORE review candidate code such as CR-YYYYMMDD-NNNNNN with 승인, 보류, or 거절, or when applying a previously proposed Obsidian CORE maintenance action."
---

# CORE Review Approval

## Core rule

**한 메시지 = 후보 코드 하나 = 결정 하나 = action 하나.** 시간 압박·낮은 위험·사용자 직급도 이 경계를 완화하지 않는다. 유효하지 않은 문장은 읽기 전용 조회조차 시작하지 않는다.

## Entry gate

Triggering Discord 메시지 전체를 그대로 validator에 전달한다. 먼저 현재 로더가 제공한 **이 SKILL.md의 절대 경로**에서 부모 디렉터리를 `SKILL_DIR`로 정한다. 현재 작업 디렉터리의 `scripts/`를 사용하거나 이름으로 다른 복사본을 검색하지 않는다.

```bash
SKILL_DIR="<absolute directory containing this loaded SKILL.md>"
test -f "$SKILL_DIR/scripts/validate-approval.py"
printf '%s' "$MESSAGE" | python3 "$SKILL_DIR/scripts/validate-approval.py"
```

exit 0의 JSON만 수용한다. exit 2면 변경 0건으로 종료하고 다음 형식 하나만 안내한다.

```text
CR-YYYYMMDD-NNNNNN 승인|보류|거절
```

쉼표 목록, 여러 줄, `둘 다`, `전체`, 범위(`CR-1~CR-5`), 추가 설명이 붙은 문장은 모두 무효다. 후보를 하나씩 나눠 처리하거나 첫 ID만 선택하는 것도 금지한다.

## Decision flow

`decision_message_id`는 실제 triggering Discord message ID여야 한다.

| 결정 | 허용 동작 |
|---|---|
| 보류 | DB·Vault를 변경하지 않고 `proposed` 유지 |
| 거절 | `reject_core_review_candidate(p_candidate_code,p_decision_message_id)` RPC만 호출 |
| 승인 | 아래 승인 절차 수행 |

RPC는 운영 repo `.env`의 Supabase URL·service role을 사용하고 값은 출력하지 않는다. RPC 결과는 **정확히 1행**이어야 한다. 0행·2행 이상·만료·상태 충돌이면 파일을 건드리지 않는다.

## Approval procedure

1. `claim_core_review_candidate(p_candidate_code,p_decision_message_id)`를 호출한다.
2. 반환 후보의 필수 필드와 `proposed_changes`가 정확히 action 하나인지 검증한다. 장부에 없는 작업을 보태지 않는다.
3. `source_note_path`를 `CORE_REVIEW_VAULT_PATH` 아래의 안전한 상대 `.md` 경로로 해석한다. 절대경로, `..`, symlink 탈출, `.env*`, binary는 거부한다.
4. source가 `00_Inbox`면 파일 변경을 금지한다. `recommend_only`로 취급한다.
5. 현재 source SHA-256을 후보의 `source_sha256`과 비교한다. 다르면 파일 변경 없이 `release_core_review_candidate(p_candidate_code,'source hash changed')`를 호출하고 재평가를 요청한다.
6. 변경될 모든 파일을 먼저 읽고 원문·SHA를 메모리에 보관한다. 승인된 action 밖의 status 정리·문구 개선·추가 링크를 끼워 넣지 않는다.
7. **Claim 이후 첫 쓰기 전에 중단되는 모든 경우**(필드/action 불량, unsafe path, old occurrence 불일치, target 충돌, 비결정적 위치)는 `release_core_review_candidate(p_candidate_code,<reason>)`를 호출하고 결과가 정확히 1행인지 확인한다. release가 1행이 아니면 파일을 쓰지 않고 상태 충돌을 보고한다.
8. action을 한 번만 적용한다. 현재 producer·validator·approval 계약에서 실행 가능한 결정적 action은 `replace`뿐이다. source에서 `old`가 정확히 한 번 존재할 때만 그 한 곳을 `new`로 교체한다.
9. `add_link`, `remove_link`, `create_core_with_backlink`, `recommend_only`, `merge`, `classify`, `status_cleanup`, `skill_drift`는 producer가 정확한 위치·필드·완성 결과를 action에 제공하는 계약이 추가되기 전까지 자동 적용하지 않는다. 자연어 설명뿐인 action도 동일하다. `release_core_review_candidate(...,'action requires deterministic re-evaluation')` 후 구체적인 새 후보를 요청한다.
10. 적용 후 모든 변경 파일을 다시 읽어 Markdown/frontmatter, wikilink target, backlink, action 외 diff 없음, source/target 존재를 검증한다.
11. 검증 성공 후에만 `complete_core_review_candidate(p_candidate_code,'applied',result_summary,null)`를 호출하고 결과가 정확히 1행인지 확인한다.

쓰기 이후 실패하면 보관한 원문으로 정확히 롤백하고 hash를 검증한다. 롤백 성공 시 `release_core_review_candidate`로 `proposed`에 돌린다. 롤백 실패 시 `complete_core_review_candidate(...,'failed',result_summary,error)`를 호출하고 즉시 보고한다.

## Report

- 후보 코드와 최종 상태
- 실제 변경 파일
- action 하나의 diff 요약
- SHA·frontmatter·wikilink·backlink 검증 결과
- 변경하지 않은 경우 차단 사유와 필요한 새 명령

## Never

- 한 메시지에서 후보 둘 이상 처리
- ID 없는 승인이나 범위 승인 수용
- source hash 불일치 강행
- `00_Inbox` 수정
- 승인된 action에 다른 정리 작업 추가
- 다른 Hermes profile의 skills/plugins/cron/memory 수정
- 검증 전에 `complete(...,'applied',...)` 호출

## Pressure traps

| 합리화 | 실제 규칙 |
|---|---|
| “둘 다 명시했으니 둘 다 승인이다” | validator가 복수 ID를 거부한다 |
| “각 후보를 독립 처리하면 안전하다” | 한 메시지에서 처리 자체가 금지다 |
| “범위를 지정하면 일괄 승인 가능하다” | 후보 코드 하나만 허용한다 |
| “링크 수정이라 위험이 낮다” | 위험도는 승인 단위를 바꾸지 않는다 |
| “사용자가 재촉한다” | 최신성·원자성 검증을 생략하지 않는다 |
