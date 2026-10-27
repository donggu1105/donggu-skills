# donggu-skills

> **강동현**([@donggu1105](https://github.com/donggu1105))의 Agent Skills 모음 — Claude Code · Codex · Hermes · Cursor 등 [Agent Skills](https://agentskills.io) 표준을 읽는 모든 에이전트에서 같은 폴더를 쓴다.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
[![Agent Skills](https://img.shields.io/badge/Agent%20Skills-spec-0A7)](https://agentskills.io/specification)
[![Skills](https://img.shields.io/badge/skills-12-green)](#skills)

스킬 하나 = `skills/<이름>/SKILL.md` 폴더 하나. 플러그인·마켓플레이스·네임스페이스 없음. 호출은 Claude Code `/<이름>`, Codex `$<이름>`, Hermes는 설명문으로 자동 선택.

> **Why this exists**: 실제 운영 경계를 이해하는 domain-native skill을 한 저장소에서 관리한다. Vault 구조와 라우팅은 각 Vault의 권위 파일이 소유하고, 이 저장소는 절차(how)와 필요한 네이티브 runtime만 제공한다.

---

## Install

```bash
npx skills add donggu1105/donggu-skills -g          # 깔린 에이전트를 감지해 전부 연결
npx skills add donggu1105/donggu-skills -g -s make-card-news -s donggu-deck   # 일부만
npx skills update                                    # 전체 갱신
```

정본은 `~/.agents/skills/<이름>`에 한 벌만 놓이고, `~/.claude/skills` · `~/.codex/skills` · `~/.hermes/skills` 등 각 에이전트 폴더에는 심링크가 걸린다. 그래서 갱신이 한 번이고 런타임 간 버전 차이가 생기지 않는다.

Hermes에서 **실제 발행**(tistory·maily·threads·linkedin·instagram)까지 하려면 네이티브 어댑터를 플러그인으로 연결한다 (아래 [Hermes native publisher](#hermes-native-publisher)).

---

## Skills

| Skill | 언제 | 결과물 |
|---|---|---|
| **writing-social-content** | Blog·LinkedIn·Threads·Maily 텍스트 작성·변환 | 채널별 확정 초안 |
| **make-card-news** | 확정 원고 → 카드뉴스/캐러셀 (인스타·링크드인·쓰레드) | `01..NN.png` + `cards.pdf` + `cards.json` + `qa.json`, 볼트 적재 |
| **get-ai-image** | 사용자 이미지가 없을 때 대표이미지·삽화 생성 | 이미지 파일 |
| **publish-sns** | tistory·maily·threads·linkedin·instagram 발행·삭제 (승인 게이트) | 발행 결과 + ledger |
| **extract-core** | 발행 직후 "코어 환류" — CORE 후보 채점·제안, 고른 것만 생성·연결 | CORE 노트 + 링크 |
| **decompose-canon** | "정전"으로 고른 글의 깊은 역분해 | CORE·부품 후보 |
| **youtube** | YouTube Longform + Shorts 후보 기획·회고 | 영상 Pack |
| **get-youtube-scripts** | 자막 전용 폴백 (소스 언어 선택 오류·429 회피) | 자막 텍스트 |
| **save-youtube-source** | YouTube 영상을 Obsidian 참고 노트로 | 소스 노트 |
| **donggu-deck** | 발표 자료·덱·장표 — 스타일 계약 + 부품 전시장 14종 | 단일 `index.html` + `assets/` |
| **industry-profit-growth-strategy-radar** | AX로 바뀌는 실제 산업을 산업 하나·기업 하나·숫자 세 개로 학습 | 학습 카드 |
| **apply-wishket** | 위시켓 프로젝트 제안서 초안·지원 (제출은 HITL 게이트) | 제안서 + 지원 결과 |

### 경계 — 말 / 이미지 / 영상 기획 / 발행

```text
writing-social-content   = 말        — 글자만 작성
get-ai-image             = 이미지    — 사용자 제공 이미지가 없을 때 생성
make-card-news           = 카드뉴스  — 확정 원고를 1080×1350 이미지 세트(+PDF)로 렌더
youtube                  = 영상 기획  — Longform + Shorts 후보 Pack
publish-sns              = 발행      — 승인 뒤 확정 텍스트·이미지 반영
extract-core             = 환류      — 발행 글에서 CORE 후보 제안·선택 반영
decompose-canon          = 역분해    — 정전 글의 CORE·강의 부품 추출
```

### 텍스트 작성 구조

`writing-social-content`는 하나의 라우터와 스킬 내부 reference로 동작한다.

```text
사용자 source·URL·브리프
        ↓
FDE | 1인 빌더 페르소나 + 글별 오디언스 잠금
        ↓
common-voice + 요청 채널 규칙
        ↓
근거 장부 + 채널별 논지 잠금
        ↓
요청 채널의 번들된 문체 예시로 톤 캘리브레이션
        ↓
채널별 독립 초안
```

- 모든 지원 채널은 `FDE`와 `1인 빌더` 페르소나를 모두 사용할 수 있다.
- 핵심 오디언스는 페르소나와 별도로 글마다 정하며 채널에 고정하지 않는다.
- `DA`는 위시켓 내부 역할이며 공개 페르소나 선택지가 아니다.
- 페르소나 선택은 source가 뒷받침하지 않는 사실을 추가할 권한을 주지 않는다.
- 로드 순서: `personas.md` → `common-voice.md` → 요청 채널 규칙.
- 현재 논지를 잠근 뒤 요청 채널의 기존 발행 글 발췌만 문체 예시로 읽는다.
- 발췌의 사실·사례·결론은 재사용하지 않는다.
- 외부 보이스 문서, 과거 글, 특정 Vault 경로를 런타임에 요구하지 않는다.
- 현재 source가 내용의 정본이다.
- 다른 채널 문장을 길이만 바꿔 재사용하지 않는다.
- Blog·LinkedIn·Threads·Maily를 별도 스킬로 쪼개지 않는다.

### 작성 이후

```text
텍스트 확정
├── 파일 저장 요청 → target-native 파일 도구
├── 이미지 요청    → 사용자 제공 이미지 / get-ai-image / make-card-news
├── 영상 기획      → youtube
└── 게시 요청      → publish-sns preview·approval
```

`writing-social-content`는 저장 경로, schema, frontmatter, 이미지, 게시를 소유하지 않는다. 저장 대상이 Obsidian이어도 해당 Vault의 규칙은 저장 단계에서만 적용한다.

LinkedIn·Threads의 외부 URL은 본문에 넣지 않는다. 작성 결과와 게시 preview는 URL 없는 canonical body만 다룬다.

### 발행 안전 경계

- 실제 외부 게시·수정·삭제는 `publish-sns`만 수행한다.
- preview와 사용자 승인 없이 게시하지 않는다.
- Maily 실제 발송은 별도 2차 확인이 필요하다.
- native preview는 Threads 500자 초과·해시태그·명백한 본문 URL 문자열과 LinkedIn의 명백한 본문 URL 문자열을 거부한다.
- LinkedIn·Threads 게시 payload는 URL 없는 본문만 허용한다.
- Instagram payload는 `publish-sns/prepare_instagram.py`가 채널 노트에서 만든다 — 임베드 순서 → `image_urls`, 캡션 섹션 → `caption`, 동의 고지·재발행 게이트.
- 외부 결과는 ledger read-back까지 확인한다.

---

## Hermes native publisher

`publish-sns` 스킬은 어느 에이전트에서나 preview·검증까지 하지만, **실제 mutation은 Hermes에서만** 한다. 그 어댑터가 `hermes/donggu-sns/`다 (`plugin.yaml`, `tools.py`, `runtime/`).

```bash
git clone https://github.com/donggu1105/donggu-skills ~/workspace/donggu-skills
ln -s ~/workspace/donggu-skills/hermes/donggu-sns ~/.hermes/plugins/donggu-sns
hermes plugins doctor donggu-sns        # 8 tools 등록 확인
```

필요 환경변수: `PUBLISHER_API_TOKEN`(Tistory·Maily loopback API), `SNS_WEBHOOK_TOKEN`(나머지 채널), `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`. 제공 도구: `donggu_publishing_preview` → `donggu_publishing_execute`, Maily는 `donggu_publishing_confirm_maily`, 상태 조회 `donggu_publishing_receipt_status`.

---

## Repo structure

```text
donggu-skills/
├── skills/<name>/SKILL.md        ← 스킬 12개 (Agent Skills spec: name + description frontmatter)
│   └── scripts/ references/ templates/ assets/ examples/   (스킬별 필요한 것만)
├── hermes/donggu-sns/            ← Hermes 네이티브 발행 어댑터 (plugin.yaml · tools.py · runtime/)
├── tests/                        ← 스킬 계약 + 런타임 테스트 (python -m pytest tests)
├── docs/                         ← 설계 노트·계획
├── README.md
└── LICENSE
```

이전 구조(`donggu-<domain>/` 플러그인 5개 + Claude·Codex·Hermes 매니페스트)는 2026-10-27에 걷어냈다. 런타임마다 다른 복사본을 읽어 버전이 어긋나던 문제가 원인이었고, 마지막 플러그인 릴리스는 태그 `donggu-sns--v2.14.1` · `donggu-ppt--v1.0.1`에 남아 있다. 기존 `/plugin install donggu-*@donggu-skills` 사용자는 그 플러그인을 지우고 위 `npx skills add` 한 줄로 갈아타면 된다.

---

## Skill 작성 원칙

- **frontmatter는 spec 필드만**: `name`(폴더명과 동일), `description`(언제 쓰는지 + 무엇을 하는지). 선택: `license`, `compatibility`, `metadata`.
- **runtime-neutral**: 특정 에이전트의 도구 이름·경로(`AskUserQuestion`, `skill_view(`, `MEDIA:`, `~/.hermes/profiles`)를 SKILL.md에 쓰지 않는다. 테스트가 grep으로 막는다.
- **user-neutral**: 개인 자격증명·내부 URL·고객사 이름을 넣지 않는다. 공개 저장소다.
- **경계 문서화**: 무엇을 하지 않는지(저장·이미지·게시 중 소유하지 않는 것)를 명시한다.
- **TDD·authority first·사용자 결정 게이트·progressive disclosure**: [superpowers:writing-skills](https://github.com/obra/superpowers) 가이드를 따른다. 결정적 hash·journal·rollback은 prompt가 아니라 코드와 테스트가 소유한다.
- **버전은 git 태그**: 매니페스트 번호 없음. 릴리스가 필요하면 `vYYYY.MM.DD` 태그.

---

## Contributing

개인 모음이지만 issue/PR 환영:

- **Bug report**: skill 사용 중 잘못된 동작 → [Issues](https://github.com/donggu1105/donggu-skills/issues)
- **Feature request**: 새 skill 아이디어 또는 기존 skill 개선
- **Vault convention 차이**: 본인 PKM 시스템 (PARA·Zettelkasten 등) 적용 시 매핑 어려움 보고

기여 가이드: Fork → branch → `skills/<name>/SKILL.md` 수정 또는 신규 폴더 추가 → RED test 명시(baseline 결과) → broadly applicable 검수(특정 vault convention 하드코딩 X) → `python -m pytest tests` → PR.

---

## Author

**강동현 (donggu)** · AI Product Engineer — 코드 짤 줄 아는 AX 전략가, 조직 이해하는 LLM 개발자. (C)트랙 LLM 개발과 (D)트랙 AX 전략의 다리 포지셔닝. [GitHub @donggu1105](https://github.com/donggu1105)

## License

[MIT](./LICENSE) © 2026 강동현 (donggu)
