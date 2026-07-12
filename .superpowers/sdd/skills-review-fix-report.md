# Portable Obsidian Skills Review Fix Report

## 상태

DONE — 리뷰의 Critical/Important/Minor 1~7을 모두 재현하고 수정했다.

- 검토 수정 구현 commit SHA: `c75cc9e6b06237073ccef2ded236998a7f8c3987`
- 기준 HEAD: `a6599222301f69b5b62618c482dd8e82c8122d31`
- plugin version: 변경 없음 (`donggu-sns` 2.4.3, `donggu-obsidian` 1.5.1)

## 수정 결과

1. `decompose-canon`을 read/evaluate → metadata-only candidate → mandatory STOP 흐름으로 바꾸고 직접 atom 생성·post/MOC/VOICE 배선을 제거했다.
2. `checking-vault-health`와 `finding-duplicate-notes`에서 자연어 채택, per-item 직접 처리, blanket approval, 자동 archive/move/body 축약, 여러 파일 citation 수정 및 Vault 전체 치환 경로를 제거했다.
3. 위 세 스킬은 `candidate_code`, `source_note_path`, `source_sha256`, `candidate_type`, 단일 `proposed_changes`를 가진 후보 생성 후 종료하며, 실제 변경 가능성은 후보 ID별 `core-review-approval`만 판단한다. 지원되지 않는 action은 승인돼도 release/re-evaluation한다.
4. `tests/test_obsidian_content_flow_contracts.py`의 10개 contract 수를 유지하면서 handoff section 구조, 필수 metadata, 금지 section/직접 적용 동사, blanket/vault-wide 문구 부재를 검사하도록 강화했다.
5. `publish-sns` step 5에 실제 발행 성공만 ledger에 저장하고 `dry_run=true` 성공 응답은 `published_posts`에 INSERT하지 않는 조건을 추가했다.
6. Vault Health 표준 Report Format에 다섯 정수 지표를 고정했다.
7. `decompose-canon`의 retired weekly journal 표현과 duplicate 관련 journal 표현을 capture/routine 경계로 교체했고, 기존 구현 보고서에 `a659922` 구현 SHA를 추가했다.

## TDD 증거

### RED

```text
python3 -m unittest tests.test_obsidian_content_flow_contracts -v
Ran 10 tests
FAILED (failures=21)
```

상반된 직접 적용 단계, 필수 candidate handoff 부재, health template 지표 부재, dry-run ledger 조건 부재, retired journal 표현을 재현했다.

### GREEN / 회귀

```text
python3 -m unittest tests.test_obsidian_content_flow_contracts -v
Ran 10 tests in 0.002s
OK

python3 -m unittest discover -s donggu-obsidian/skills/core-review-approval/tests -p 'test_*.py' -q
Ran 47 tests in 3.389s
OK

claude plugin validate .
✔ Validation passed

git diff --check
(exit 0)
```

정확한 automated test 수는 **57개(contracts 10 + helper 47)**이며 실패는 0개다. plugin validation은 별도 1회 통과했다.

## 범위

수정 파일은 portable skill 4개, contract test 1개, 구현 보고서 1개와 이 보고서뿐이다. AI/FDE, live Vault, n8n repository, env/credential, plugin manifest/version은 수정하지 않았다. 기존 untracked `.superpowers/sdd/progress.md`와 `.superpowers/sdd/reviews/`는 건드리거나 commit하지 않았다.
