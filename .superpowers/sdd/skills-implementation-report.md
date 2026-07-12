# Obsidian Content Skills Implementation Report

## 상태

Task 1~5 구현 및 검증 완료. 작업 기준은 계획 커밋 `11dcc16`이며, 변경은 지정 worktree 안의 portable skill·contract test·plugin manifest·계획 체크리스트·이 보고서로 제한했다.

## 구현 결과

- `writing-social-content`: `origin`/`adapt` 모드, `type: channel_pack`, `derived_from` lineage, channel-native 본문 계약을 추가하고 `type: content` 및 절대적 무계보 규칙을 제거했다.
- `publish-sns`: 성공한 `published_posts` persistence만 existing DB trigger를 통해 발행 완료 이벤트를 만들며, 실패·dry-run은 이벤트를 만들지 않고 CORE/Snippet/MOC를 직접 생성하지 않는 경계를 명시했다.
- `extract-core`: routine 우선순위를 newly published Channel Pack → curated Source → explicit Inbox recommendation-only request로 고정하고, persistence 전 기존 CORE 검색 및 `LINK/NEW/MERGE/HOLD` 판정을 요구했다.
- `decompose-canon`: routine 발행 검토와 분리하고 explicit canon selection 이후의 deep decomposition으로 한정했다.
- `checking-vault-health`: 후보 0건이어도 매일 다섯 지표를 출력하는 read-only 계약과 Inbox age/count-only 후보화 금지를 추가했다.
- `finding-duplicate-notes`: full five-pattern audit를 monthly/on-demand로 제한하고 daily care는 threshold signal만 허용했다.
- 버전 동기화: `donggu-sns` `2.4.2 → 2.4.3`, `donggu-obsidian` `1.5.0 → 1.5.1`; 각 plugin manifest와 marketplace version을 함께 갱신했다.
- `tests/test_obsidian_content_flow_contracts.py`: 정확한 skill path를 읽는 10개 semantic contract test를 추가했다.

## TDD 및 검증 증거

### RED

```text
python3 -m unittest tests.test_obsidian_content_flow_contracts -v
Ran 10 tests
FAILED (failures=7)
```

예상대로 origin/adapt·발행 이벤트·routine/deep 경계·daily health·monthly/on-demand 계약 부재로 실패했다.

### GREEN / 회귀

```text
python3 -m unittest tests.test_obsidian_content_flow_contracts -v
Ran 10 tests in 0.001s
OK

python3 -m unittest discover -s donggu-obsidian/skills/core-review-approval/tests -p 'test_*.py' -q
Ran 47 tests in 3.466s
OK

claude plugin validate .
✔ Validation passed
```

## 변경 파일

- `.claude-plugin/marketplace.json`
- `donggu-sns/.claude-plugin/plugin.json`
- `donggu-sns/skills/writing-social-content/SKILL.md`
- `donggu-sns/skills/publish-sns/SKILL.md`
- `donggu-obsidian/.claude-plugin/plugin.json`
- `donggu-obsidian/skills/extract-core/SKILL.md`
- `donggu-obsidian/skills/decompose-canon/SKILL.md`
- `donggu-obsidian/skills/checking-vault-health/SKILL.md`
- `donggu-obsidian/skills/finding-duplicate-notes/SKILL.md`
- `tests/test_obsidian_content_flow_contracts.py`
- `docs/superpowers/plans/2026-07-13-obsidian-content-skills.md`
- `.superpowers/sdd/skills-implementation-report.md`

## 범위 및 이슈

- AI 뉴스/FDE 관련 파일, 다른 profile, live Vault, n8n repository, env/credential 파일은 수정하지 않았다.
- 기존 `.superpowers/sdd/progress.md`는 orchestration 상태 파일로 보고 commit 범위에서 제외했다.
- 차단 이슈 없음.
