---
name: core-review-approval
description: "Use when an authorized Discord CORE candidate thread receives one exact review command, or when an unbound legacy candidate receives one exact CR decision command."
---

# CORE Review Approval

## Core rule

**한 메시지 = 후보 하나 = 결정 하나 = action 하나.** Conversation과 legacy는 서로 fallback하지 않는다. blanket or multi-candidate approval is forbidden.

Accepted trust model:

- the deterministic n8n workflow owns DB claim/complete ordering;
- the native plugin does not independently authenticate DB state; and
- Direct manual apply/ack tool calls outside the mapped workflow are unsupported.

The local receipt binds one plan to one Hermes session and persisted message sequence. The PostgreSQL row owns candidate/thread state and atomic claim. The helper owns crash-atomic Vault mutation. Do not assign the same transition to two layers.

## Conversation entry gate

이 gate는 parent channel `1526033497100390641` 아래 Discord candidate thread에서 user `736583402244931584`가 보낸 메시지에만 적용한다. 해당 위치에서는 이 gate가 유일한 경로다. validator 실패를 legacy `CR-...` 경로로 넘기지 않는다.

현재 로더가 제공한 이 SKILL.md의 절대 경로에서 `SKILL_DIR`를 정하고, 실제 triggering message와 Discord ID를 exact JSON으로 만든다. 모델이 ID를 채우거나 본문을 고치지 않는다.

```bash
SKILL_DIR="<absolute directory containing this loaded SKILL.md>"
test -f "$SKILL_DIR/scripts/validate-conversation.py"
printf '%s' "$CONVERSATION_ENVELOPE_JSON" | \
  python3 "$SKILL_DIR/scripts/validate-conversation.py"
```

exit 0의 exact JSON만 수용한다. 허용 본문은 `수정안 보여줘`, `적용해줘`, `넘겨줘`, `거절할게` 정확히 네 개다. exit 2, wrong thread, wrong user, wrong channel, extra prose, 합성·일괄 명령은 DB/Vault 변경 0건으로 종료한다.

validator 뒤에만 service-role RPC `get_core_review_conversation_by_thread(p_thread_id,p_channel_id,p_requester_user_id)`를 호출한다. Result must be exactly 1 row and preserve the validated thread/channel/user IDs: one thread = one candidate. Candidate code and envelope are resolved only from this durable joined row, never from message text, nearby prose, memory, or a model guess. 0행·2행 이상·mapping 불일치·expired/terminal row면 후보 필드에 접근하지 말고 종료한다.

모든 conversation RPC 성공은 exactly 1 row다. 0행·2행 이상·binding 불일치는 stop이며 DB/Vault 추가 변경 0건이다.

### Preview — `수정안 보여줘`

아래 순서는 고정이다.

1. conversation=`thread_open`, candidate=`proposed`, 둘 다 unexpired이고 source snapshot이 일치하는지 read-only로 확인한다.
2. `donggu_core_recovery_status(vault_root)`를 read-only로 호출한다. 오직 exact `state=no_transaction`, `candidate_code=null`, `transaction_sha256=null`일 때만 계속한다. `prepared|rolled_back|committed`, malformed result, exit 4/5/6이면 현재 후보를 plan/prepare/send하지 않고 아래 **Recovery — existing transaction** 절차로 기존 transaction을 먼저 reconcile한다.
3. 허용 조합은 (`fix_link`, `replace`), (`link_existing`, `replace`), (`new_core`, `create_core_with_backlink`)뿐이다. action 하나를 `schema_version,candidate_code,candidate_type,source_note_path,source_sha256,claim,target_note_paths,action` exact 8-key envelope로 만든다.
4. `donggu_core_plan(vault_root, envelope)`을 한 번 호출한다. The handler itself binds the exact plan `session_id` and persisted preview message row; 모델은 session/message binding을 인자로 만들지 않는다. 반환 `status=planned`, `receipt_id`, native absolute `expires_at`, envelope/path/hash 결과를 private workflow state로 유지한다. 여기까지 Vault changes: 0.
5. `$SKILL_DIR/scripts/render-preview.py`에 exact `{candidate,plan}`을 전달하고 exit 0의 bounded `content,preview_hash,candidate_code`만 수용한다. `render-preview.py` 결과 content는 1,800자 이하여야 하며 “아직 Vault 변경 0건”을 포함한다.
6. Discord 전송 전에 `prepare_core_review_preview(...)`를 validated IDs, source/preview/envelope hash, receipt ID, native absolute `expires_at`으로 호출한다. `thread_open → previewed`, delivery=`prepared` exactly 1 row만 수용한다. 이 prepare에는 아직 존재하지 않는 Discord message ID를 저장하지 않는다. A definite zero-row 결과만 public send 0건, Vault 변경 0건으로 확정하고 planned receipt를 `donggu_core_revoke(receipt_id)`로 폐기한다. timeout/response loss처럼 prepare 결과가 불명확하면 먼저 같은 validated IDs로 exact DB readback을 한다. same receipt ID, source/preview/envelope hash, expiry가 모두 일치하는 `previewed + prepared` exactly 1 row면 second prepare 없이 continue from the exact `prepared` row. exact `thread_open + proposed + no stored receipt` readback이 prepare zero-row를 확정한 때도 send 0건 뒤 revoke한다. 그 외 mismatch or unknown readback이면 `mark_core_review_preview_delivery_ambiguous(...)`를 시도해 DB delivery ambiguity와 planned receipt를 그대로 보존하고 send/revoke하지 않는다.
7. 그 뒤 renderer의 content만 Discord send한다. 모델 문장을 덧붙이지 않는다.
8. send가 반환한 actual Discord message ID로 `complete_core_review_preview_delivery(...)`를 호출해 `prepared → sent` exactly 1 row를 확인한다. 그 전에는 apply claim을 허용하지 않는다.
9. send 결과 또는 sent-finalize 결과가 불명확하면 `mark_core_review_preview_delivery_ambiguous(...)`로 delivery를 `ambiguous`로 고정하고 never resend automatically. receipt를 apply/revoke하지 말고 운영자 reconciliation을 요구한다. 확실한 send 실패이며 메시지가 생성되지 않았음이 증명된 경우에도 자동 재전송하지 않고 같은 ambiguity 절차를 따른다.

### Recovery — existing transaction

이 경로는 preview preflight가 non-clean이거나, DB claim 뒤 process crash/timeout이 발생한 때만 사용한다. 새 승인 문구는 필요 없고 `donggu_core_apply`를 다시 호출하지 않는다.

1. **DB conversation receipt lookup**: validated thread/channel/user IDs로 `get_core_review_conversation_by_thread(...)`를 다시 read-only 호출한다. exactly 1 row의 저장된 `native_receipt_id`, candidate binding, conversation/candidate/completion state만 신뢰한다. journal/stdout/현재 메시지에서 receipt를 추측하지 않는다. receipt가 없거나 row/binding이 0행·2행 이상·불명확하면 plan/apply/release 없이 DB를 ambiguous로 보존하고 운영자에게 넘긴다.
2. 그 exact receipt로 `donggu_core_receipt_status(receipt_id)`를 호출한다. local state가 `applying|reconciliation_required|revoked|ambiguous|acknowledging|completed` 중 무엇인지 DB row와 함께 기록한다. `acknowledging`이 DB `applied + readback_complete_ack_pending` 및 stored nonce와 exact match하면 step 7의 same-nonce ack로 바로 간다. `planned` 또는 다른 DB/local 조합이 설명되지 않으면 recovery apply를 시도하지 않고 ambiguous로 보존한다.
3. `applying|reconciliation_required|revoked|ambiguous|completed`에는 `donggu_core_recover(receipt_id)`를 호출한다. 이 tool은 terminal result에는 idempotent이고 `applying`에서만 journal을 검사하며 forward apply를 절대 실행하지 않는다. matching `prepared|rolled_back`만 helper `--recover-only`를 한 번 실행한다. foreign/malformed/exit 5/unknown은 local `ambiguous`다.
4. 결과가 `revoked`이고 journal이 exact `no_transaction`이면 DB가 아직 `applying + processing`인 경우에만 `release_core_review_conversation(...)`로 `previewed + proposed` 복귀 exactly 1 row를 확인한다. old receipt는 재사용하지 않고 새 preview를 만든다. `ambiguous`면 release/revoke하지 않고 `mark_core_review_conversation_apply_ambiguous(...)` exactly 1 row로 고정한다.
5. 결과가 `vault_committed_reconciliation_required`이면 같은 receipt로 `donggu_core_readback(receipt_id)`을 호출하고 exact actual after hashes를 확인한다. DB가 이미 readback complete이면 저장된 digest와 exact match를 요구하며 새 digest/nonce를 만들지 않는다.
6. DB가 아직 `applying + processing`이면 canonical UUID nonce 하나를 만들고 same receipt/decision/digest로 `complete_core_review_conversation(...)`를 exactly 1 row까지 idempotent retry한다. 이미 `applied + readback_complete_ack_pending`이면 DB에 저장된 nonce를 읽어 그대로 사용한다.
7. DB complete 뒤 same nonce로 `donggu_core_ack(receipt_id, completion_nonce)`를 local receipt가 `completed`가 될 때까지 retry한다. `committed`는 cleanup retry이고 `no_transaction + acknowledging`도 같은 ack를 다시 호출해 local completion을 기록해야 한다.
8. local `completed` 확인 뒤에만 `confirm_core_review_native_ack(...)`를 same receipt/nonce/digest로 호출한다. exactly 1 row의 `native_ack_complete`, final receipt `completed`, journal `no_transaction`을 모두 읽은 뒤 종료한다.

### Apply — `적용해줘`

아래 순서는 single-use mapped workflow다.

1. DB row가 `previewed`, delivery가 `sent`, candidate가 `proposed`이고 conversation/candidate/receipt가 unexpired인지 확인한다. persisted/current `source_sha256`, `preview_hash`, `envelope_hash`, receipt ID, actual preview/decision message IDs가 모두 exact match여야 한다. duplicate/terminal/ambiguous row는 stop한다.
2. `claim_core_review_conversation_apply(...)`를 validated IDs와 exact bindings로 한 번 호출한다. exactly 1 row에서 같은 transaction으로 conversation `previewed → applying`와 candidate `proposed → processing`이 함께 바뀌고 DB에 저장된 receipt ID가 반환되어야 한다. claim 0행/2행/partial이면 native apply를 호출하지 않는다.
3. 성공한 claim 뒤 반환 receipt만 사용해 `donggu_core_apply(receipt_id)`를 정확히 한 번 호출한다. tool 인자에 candidate code, 자연어 승인문, 경로, hash를 넣지 않는다. 성공은 최종 완료가 아니라 `vault_committed_reconciliation_required`다.
4. 즉시 같은 receipt로 `donggu_core_readback(receipt_id)`을 호출한다. exact `readback_verified`와 actual after hashes가 없으면 DB complete/ack/final success를 하지 않는다.
5. n8n generates one canonical UUID `completion_nonce`. 이것은 공개값이 아니며 이 attempt에서 한 번만 만든다. actual after-hash map을 canonical digest로 만들고 `complete_core_review_conversation(...)`에 receipt, decision message ID, digest, bounded result summary, nonce를 전달한다. exactly 1 row의 `applied + readback_complete_ack_pending`과 DB가 반환한 same nonce를 확인한다. 응답 유실 시 새 nonce를 만들지 말고 같은 nonce/receipt/decision/digest로만 idempotent retry한다.
6. DB complete 성공 뒤에만 `donggu_core_ack(receipt_id, completion_nonce)`를 호출한다. `completed`면 같은 receipt, same nonce로 `confirm_core_review_native_ack(...)`를 호출한다. exactly 1 row의 `applied + native_ack_complete`만 성공이다. wrong nonce, digest, receipt, decision, candidate binding은 0행으로 stop한다.
7. 마지막에 final `donggu_core_receipt_status(receipt_id)`가 `completed`이고 `donggu_core_recovery_status(vault_root)`가 exact `no_transaction`인지 확인한다. DB도 `native_ack_complete`인지 다시 읽은 뒤에만 bounded public success를 보낸다.

Apply failure handling:

- **확실한 pre-mutation 실패**: helper/native exit 2 또는 clean journal로 증명된 exit 70은 Vault 변경 0건이다. `release_core_review_conversation(...)`로 atomic `applying → previewed`, `processing → proposed`를 exactly 1 row 확인하고 `donggu_core_revoke(receipt_id)`를 호출한다. 이미 native가 receipt를 revoked로 만들었으면 revoke의 동일 결과만 수용한다. old receipt는 재사용하지 않고 새 preview부터 시작한다.
- **exit 4**: native runtime가 local receipt를 `ambiguous`로 만든다. clean-looking status가 함께 보여도 preserve both DB and local `ambiguous`; `mark_core_review_conversation_apply_ambiguous(...)`만 exactly 1 row로 남기고 never release or revoke. helper recovery를 직접 실행하거나 apply를 재호출하지 않는다.
- **exit 5 또는 unknown outcome**: release/revoke하지 않는다. recovery status가 matching committed이면 `donggu_core_readback`부터 DB complete/ack/confirm을 계속한다. commit 여부를 증명하지 못하면 `mark_core_review_conversation_apply_ambiguous(...)`로 `ambiguous` exactly 1 row를 남긴다. never call apply again.
- **exit 6**: apply 실패가 아니라 cleanup retry다. DB complete에 저장된 same nonce로 ack/status/recovery만 retry한다. never call apply again. clean `no_transaction`이면 receipt/DB confirmation을 이어서 수렴시킨다.
- **DB complete 응답 유실**: same nonce와 exact binding으로 complete만 retry한다. 새 nonce 생성, release, apply replay 금지다.
- **ack/confirm 응답 유실**: DB의 stored nonce와 exact binding을 읽고 final `donggu_core_receipt_status`와 recovery status를 확인한다. local state가 `reconciliation_required|acknowledging`이면 journal이 committed이든 clean `no_transaction`이든 retry same-nonce `donggu_core_ack` until local receipt is `completed`; 새 nonce를 만들지 않는다. only then retry DB confirm. 결과를 증명하지 못하면 ambiguous로 유지한다.

### Hold and reject

`넘겨줘`는 `hold_core_review_conversation(...) only`, `거절할게`는 `reject_core_review_conversation(...) only`를 validated IDs와 actual decision message ID로 한 번 호출한다. 정확히 1행만 성공이며 각각 `held`/`rejected` terminal state다. receipt 유무와 관계없이 Vault changes: 0이고 preview/apply/release로 되돌리지 않는다. planned receipt가 남아 있으면 DB terminal transition 성공 뒤 `donggu_core_revoke(receipt_id)`로만 폐기한다.

## Legacy entry gate

Conversation thread 밖의 unbound legacy 입력만 허용한다. Triggering Discord 메시지 전체를 그대로 validator에 전달한다. 먼저 현재 로더가 제공한 **이 SKILL.md의 절대 경로**에서 부모 디렉터리를 `SKILL_DIR`로 정한다. cwd의 script나 이름으로 찾은 다른 복사본을 사용하지 않는다.

```bash
SKILL_DIR="<absolute directory containing this loaded SKILL.md>"
test -f "$SKILL_DIR/scripts/validate-approval.py"
printf '%s' "$MESSAGE" | python3 "$SKILL_DIR/scripts/validate-approval.py"
```

exit 0의 JSON만 수용한다. exit 2면 Vault 변경 0건으로 종료하고 exact `CR-YYYYMMDD-NNNNNN 승인|보류|거절` 형식만 안내한다. 쉼표 목록, 여러 줄, `둘 다`, `전체`, 범위, 추가 설명은 무효다. A candidate bound to a conversation thread may never use this legacy path; 해당 row가 있으면 conversation의 네 exact command만 안내하고 legacy claim/helper를 호출하지 않는다.

### Legacy decisions

- `보류`: DB/Vault 변경 0건.
- `거절`: `reject_core_review_candidate(p_candidate_code,p_decision_message_id)` exactly 1 row만 허용.
- `승인`: legacy DB claim 뒤 아래 portable procedure를 사용한다. conversation native receipt workflow와 섞지 않는다.

## Approval procedure

1. `$SKILL_DIR/scripts/apply-action.py --vault-root "$CORE_REVIEW_VAULT_PATH" --recovery-status`로 이전 journal을 먼저 처리한다. `no_transaction`만 새 claim으로 진행한다. `state=prepared|rolled_back`은 recover-only 후 DB release한다. `state=committed`는 after-hash readback → DB complete → `--ack-candidate <candidate_code>` 순서로 reconcile한다. stdout이나 현재 메시지 후보로 추측하지 않는다.
2. `claim_core_review_candidate(p_candidate_code,p_decision_message_id)` exactly 1 row 뒤 action 하나와 exact 8-key envelope를 검증한다.
3. 같은 `apply-action.py`에 envelope를 stdin으로 주고 `--dry-run`한다. exit 0 `status=planned`와 Vault byte/mtime 변화 0건을 확인한 뒤 같은 envelope로 apply를 한 번만 실행한다.
4. exit 0 committed이면 actual after hashes를 readback하고 DB complete 뒤 `--ack-candidate <candidate_code>`를 실행한다. exit 2/clean exit 70은 release, exit 5/unknown은 ambiguous, exit 6은 recovery/ack-only retry다. apply replay는 금지다.

허용 action은 다음뿐이다.

- `replace`: candidate type `fix_link|link_existing`, action keys `op,schema_version,old,new`, old exact 1회, target snapshot 일치.
- `create_core_with_backlink`: candidate type `new_core`, action keys `op,schema_version,template_version,core_path,moc_path,moc_sha256,trace_field`.

허용 root는 `10_Sources`, `20_Core`, `40_Snippets`, `50_Channel_Packs`, `60_MOCs`다. `00_Inbox`, 절대경로, `..`, symlink, 비정규 파일, binary/non-UTF-8, source/MOC hash mismatch, existing new CORE는 거부한다. `recommend_only`, merge/classify/status cleanup과 action 외 변경은 release 후 새 후보가 필요하다.

## Public report

Preview content는 renderer output 그대로 1,800자 이하로 보낸다. 최종 success/block 문안은 200자 이하로 보낸다. Never expose candidate code, receipt_id, completion nonce, RPC/internal state, credential, hash, Vault root, absolute path, stage/backup path, or note body publicly. Private operator log에만 final state, 실제 변경 상대경로, action 하나의 diff 요약과 검증 결과를 남긴다.

## Never

- Never mutate Vault files directly; native runtime 또는 이 skill의 portable helper만 사용한다
- DB atomic claim 전에 native apply 호출
- actual readback 전에 DB complete 호출
- DB complete 전에 native ack 호출
- native ack 전에 DB ack confirm 호출
- preview delivery가 sent가 아닌데 apply claim
- 한 메시지에서 후보 둘 이상 처리
- 다른 Hermes profile의 skills/plugins/cron/memory 수정

## Quick state reference

| Stage | Required durable state | Next side effect |
|---|---|---|
| Preview start | thread_open + proposed + clean journal | native plan |
| Prepared | previewed + prepared, no message ID | Discord send |
| Sent | previewed + sent + actual message ID | later apply claim |
| Claimed | applying + processing | native apply once |
| Committed | applying + processing + helper committed | native readback |
| DB complete | applied + readback_complete_ack_pending + nonce | native ack |
| Finished | applied + native_ack_complete + no_transaction | public result |
| Unknown | ambiguous | operator reconciliation only |
