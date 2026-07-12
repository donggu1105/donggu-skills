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

1. **현재 후보를 claim하기 전에** portable helper의 read-only recovery preflight를 실행한다.

```bash
test -f "$SKILL_DIR/scripts/apply-action.py"
python3 "$SKILL_DIR/scripts/apply-action.py" \
  --vault-root "$CORE_REVIEW_VAULT_PATH" --recovery-status
```

exit 0의 exact JSON `state,candidate_code`만 수용한다. `state=no_transaction`이면 `candidate_code=null`이어야 하며 2번으로 진행한다. `state=prepared|rolled_back`이면 현재 메시지의 후보를 claim하지 않고 journal 후보를 보관한 뒤 `--recover-only`를 실행한다. prepared는 모든 leaf와 hidden stage/backup을 먼저 검증한 뒤 before bytes로 rollback하며, cleanup 실패 exit 6이면 durable `rolled_back` journal로 재시도한다. rollback 성공 후에만 보관한 후보를 release한다. `state=committed`이면 **절대 `--recover-only`로 정리하거나 release하지 않는다.** journal 후보의 DB 상태를 조회한다. DB가 `approved`/`processing`이면 journal의 모든 after hash를 readback 검증한 뒤 `complete(...,'applied',...)`하고, 이미 `applied`면 그대로 다음 단계로 간다. 그 후에만 `--ack-candidate <journal_candidate_code>`를 실행한다. ack exit 0 뒤 recovery-status가 `no_transaction`임을 확인한다. 이 처리가 끝난 뒤에만 현재 메시지 후보 claim으로 넘어간다. preflight exit 4는 비정규·손상 journal을 포함한 integrity failure이므로 claim하지 않고 수동 복구를 보고한다.
2. `claim_core_review_candidate(p_candidate_code,p_decision_message_id)`를 호출한다.
3. 반환 후보의 필수 필드와 `proposed_changes`가 정확히 action 하나인지 검증한다. 장부에 없는 작업을 보태지 않는다.
4. 먼저 정한 `SKILL_DIR`의 portable helper만 사용한다. cwd의 script나 다른 profile의 복사본을 찾지 않는다. Hermes native tool `donggu_core_plan`이 있으면 아래 direct helper dry-run 대신 `vault_root`와 exact envelope를 전달해 receipt를 받는다. 이 tool도 package 내부의 동일 helper만 호출한다.

```bash
printf '%s' "$APPLY_ENVELOPE_JSON" | python3 "$SKILL_DIR/scripts/apply-action.py" \
  --vault-root "$CORE_REVIEW_VAULT_PATH" --dry-run
```

5. helper stdin envelope는 `schema_version,candidate_code,candidate_type,source_note_path,source_sha256,claim,target_note_paths,action` **정확히 8개 key**만 가진 schema version 1 JSON이다. claim/경로/action은 claim RPC가 반환한 한 후보에서 그대로 만들며 본문·DB credential을 넣지 않는다. `replace`의 claim은 null일 수 있고, `new_core`의 claim은 비어 있지 않은 한 줄 문자열이어야 한다.
6. dry-run exit 0과 stdout `status=planned`를 확인한 뒤에만, **동일 envelope**에서 `--dry-run`만 빼고 helper를 한 번 실행한다. dry-run은 write/stage/mtime 변경이 0이어야 한다. Native plan을 사용했다면 direct apply 대신 `donggu_core_apply(receipt_id, approval_text=<현재 triggering 승인 메시지 전체>)`를 한 번 호출한다. 성공 반환은 최종 완료가 아니라 `status=vault_committed_reconciliation_required,journal_state=committed`여야 하며, 13번의 DB complete·after-hash readback·ack까지 반드시 계속한다. Native와 direct apply를 같은 후보에 함께 실행하지 않는다.
7. helper가 자동 적용하는 action은 다음 둘뿐이다.
   - `replace`: `candidate_type`이 `fix_link` 또는 `link_existing`일 때만 허용하고 action key는 `op,schema_version,old,new` 정확히 4개다. source는 Inbox 밖의 허용 root일 수 있고, lowercase SHA-256 일치, `old` 정확히 1회일 때만 byte-preserving 교체한다. `target_note_paths`는 1~20개의 정렬·중복 없는 reference target 목록이며 `new` 안의 path-qualified wikilink target(alias/fragment 제거 후 canonical path)과 정확히 같아야 한다. target도 snapshot에 포함해 commit 직전까지 hash/존재를 재검증한다.
   - `create_core_with_backlink`: `candidate_type=new_core`이며 action key는 `op,schema_version,template_version,core_path,moc_path,moc_sha256,trace_field` 정확히 7개다. schema/template version은 1, target은 정렬·중복 없는 `[core_path,moc_path]` pair여야 한다. `10_Sources`의 trace field는 `extracted_to`, `50_Channel_Packs`는 `decomposed_to`로 고정한다.
8. `replace` source/reference target의 허용 root는 `10_Sources`, `20_Core`, `40_Snippets`, `50_Channel_Packs`, `60_MOCs`다. `new_core` source는 `10_Sources` 또는 `50_Channel_Packs`, 새 CORE는 `20_Core`, MOC는 `60_MOCs`로 제한한다. 어느 위치든 `00_Inbox` component, 절대경로, `..`, symlink, 비정규 파일, binary/non-UTF-8을 거부한다. source/MOC hash는 lowercase SHA-256과 정확히 일치하고 CORE는 없어야 한다.
9. create template v1은 현재 시각 없이 `type: core`, `template_version: 1`, path-qualified source/MOC wikilink, claim heading과 claim 본문으로 고정한다. source frontmatter의 고정 list field에 path-qualified CORE link를 구조적으로 append하며 필드가 없으면 frontmatter 닫힘 직전에 `extracted_to`/`decomposed_to`를 결정적으로 생성한다. MOC는 지원 heading `## 연결된 CORE` 또는 `## 💡 Core 연결`이 정확히 하나면 그 section에 append하고, 둘 다 없으면 canonical `## 연결된 CORE`를 생성하며, 둘 이상이면 거부한다. alias/fragment가 달라도 같은 canonical CORE target이면 중복으로 거부한다.
10. `add_link`, `remove_link`, `recommend_only`, `merge`, `classify`, `status_cleanup`, `skill_drift`, op-only/natural-language create action은 자동 적용하지 않는다. `release_core_review_candidate(...,'action requires deterministic re-evaluation')` 후 완전한 새 후보를 요청한다.
11. helper는 root부터 directory chain과 file을 descriptor에 고정하고 `O_NOFOLLOW`/`fstat` 및 `dir_fd` 기반 read/stage/unlink만 사용한다. leaf 교체는 macOS `renameatx_np`의 `RENAME_SWAP|RENAME_NOFOLLOW_ANY`로 기존 leaf를 원자적으로 capture한 뒤 before hash를 비교하고, 불일치면 즉시 swap-back한다. 신규 leaf는 `RENAME_EXCL|RENAME_NOFOLLOW_ANY`로만 생성한다. 이 API가 없는 플랫폼에서는 apply를 fail-closed한다. 모든 desired 결과는 stage 전에 8 MiB 이하인지 확인한다.
12. apply 전에는 candidate code, `state=prepared`, before/after hash, same-parent stage/backup 이름만 담은 metadata-only durable journal을 만든다. exact-byte readback 뒤 journal을 원자적으로 `state=committed`로 바꾸며, **stdout 결과나 DB ack 전에는 journal·backup·stage를 삭제하지 않는다.** apply stdout은 `status=applied,candidate_code,state=committed,paths,hashes` exact result다. prepared recovery는 모든 leaf가 before/after 중 하나이고 hidden stage가 그 leaf의 정확한 complementary snapshot이며 backup도 exact before인지 **첫 swap 전에 전부 검증**한다. rollback byte 검증 후 journal을 `rolled_back`으로 rewrite하고 cleanup한다. committed `--recover-only`는 after hash만 검증해 `reconciliation_required`를 보고하고 파일·artifact·journal을 변경하지 않는다. `--ack-candidate CR-...`는 matching committed journal과 모든 leaf의 exact after hash를 요구하고, 그때만 artifact와 journal을 정리한다. ack cleanup 실패는 committed journal을 남긴 retryable exit 6이다. journal 이름의 symlink/FIFO/directory를 포함한 모든 directory entry는 일반 dry-run/apply를 차단하며 recovery에서는 exit 4다. 모든 malformed regular journal도 syntax/extra key/hash/type에 관계없이 exit 4다. journal·stdout에는 note body/Vault root를 넣지 않는다.
13. helper exit별 장부 처리는 다음과 같다. RPC 결과는 항상 정확히 1행인지 확인한다.
   - dry-run/apply exit 2 또는 **apply 전임을 확인한** exit 70: Vault 변경 없이 `release_core_review_candidate`. exit 70을 사후 적용 실패로 간주하지 않는다.
   - apply exit 0 + `status=applied,candidate_code=<현재 후보>,state=committed`: 상대경로/after hash를 descriptor-anchored readback으로 검증하고 DB를 `complete_core_review_candidate(...,'applied',...)`한 뒤 `--ack-candidate <현재 후보>`를 실행한다. ack 전 journal은 반드시 committed로 남아 있어야 한다.
   - apply exit 5 + stderr `state=committed`: Vault commit 또는 결과 보고 mutation은 끝났다. release하지 않는다. `--recovery-status`의 committed 후보를 기준으로 DB 상태 조회 → after hash 검증 → 필요하면 complete → ack 순서로 reconcile한다. stdout이나 현재 메시지 후보로 추측하지 않는다.
   - exit 3: rollback 검증 성공이므로 `release_core_review_candidate`로 `proposed` 복귀.
   - 일반 dry-run/apply exit 4 + `recovery required`: 현재 후보를 release한 뒤 새 claim을 시도하지 말고 1번 preflight부터 다시 시작한다.
   - apply 또는 recovery-only exit 4 + `rollback incomplete`/`recovery failed`: release하지 않고 preflight의 journal candidate/state로 수동 복구를 보고한다. committed 후보는 절대 release하지 않는다.
   - recovery/ack exit 6: cleanup만 남은 retryable 상태다. `rolled_back`이면 `--recover-only`, `committed`면 DB applied 상태를 확인한 뒤 `--ack-candidate`를 같은 후보 코드로 재시도한다. exit 6을 failed로 바꾸지 않는다.
   - recovery/ack exit 5: mutation은 끝났고 실제 stdout write/flush가 실패했다. preflight 후보/state로 recovery-status를 다시 조회해 위 reconciliation을 계속한다. helper는 실제 closed pipe에서 fd 1을 `/dev/null`로 바꾸므로 interpreter exit 120이 아니라 mutation 후 5, mutation 전 70을 반환한다.

**이전 transaction은 언제나 현재 candidate claim보다 먼저 처리한다.** helper 밖에서 Vault를 직접 보정하거나 action 외 status 정리·문구 개선·추가 링크를 끼워 넣지 않는다.

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
