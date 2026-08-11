# donggu-sns

> Portable SNS authoring and gated publishing — part of [`donggu-skills`](../) marketplace.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](../LICENSE)
[![Skills](https://img.shields.io/badge/skills-4-green)](#-skills)

Blog·LinkedIn·Threads·Maily 텍스트 작성, AI 이미지 생성, YouTube 기획, 외부 채널 발행을 역할별 스킬로 분리한다.

---

## 경계 — 말 / 이미지 / 영상 기획 / 발행

```text
writing-social-content   = 말        — 글자만 작성
get-ai-image             = 이미지    — 사용자 제공 이미지가 없을 때 생성
youtube                  = 영상 기획  — Longform + Shorts 후보 Pack
publish-sns              = 발행      — 승인 뒤 확정 텍스트·이미지 반영
```

## Skills

| Skill | 사용 시점 | Output |
|---|---|---|
| **writing-social-content** | Blog·LinkedIn·Threads·Maily 텍스트 작성·변환 | 채널별 확정 초안 |
| **youtube** | YouTube Longform + Shorts 후보 기획·회고 | 영상 Pack |
| **publish-sns** | tistory·maily·threads·linkedin·instagram 발행·삭제 | 발행 결과 + ledger |
| **get-ai-image** | 사용자 이미지가 없을 때 대표이미지·삽화 생성 | 이미지 파일 |

---

## 텍스트 작성 구조

`writing-social-content`는 하나의 라우터와 스킬 내부 reference로 동작한다.

```text
writing-social-content/
├── SKILL.md
└── references/
    ├── personas.md
    ├── common-voice.md
    ├── blog.md
    ├── examples-blog.md
    ├── linkedin.md
    ├── examples-linkedin.md
    ├── threads.md
    ├── examples-threads.md
    ├── maily.md
    └── examples-maily.md
```

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

## 작성 이후

```text
텍스트 확정
├── 파일 저장 요청 → target-native 파일 도구
├── 이미지 요청    → 사용자 제공 이미지 / get-ai-image
├── 영상 기획      → youtube
└── 게시 요청      → publish-sns preview·approval
```

`writing-social-content`는 저장 경로, schema, frontmatter, 이미지, 게시를 소유하지 않는다. 저장 대상이 Obsidian이어도 해당 Vault의 규칙은 저장 단계에서만 적용한다.

LinkedIn·Threads의 외부 URL은 본문에 넣지 않는다. 작성 결과와 게시 preview는 URL 없는 canonical body만 다룬다.

---

## 발행 안전 경계

- 실제 외부 게시·수정·삭제는 `publish-sns`만 수행한다.
- preview와 사용자 승인 없이 게시하지 않는다.
- Maily 실제 발송은 별도 2차 확인이 필요하다.
- native preview는 Threads 500자 초과·해시태그·명백한 본문 URL 문자열과 LinkedIn의 명백한 본문 URL 문자열을 거부한다.
- LinkedIn·Threads 게시 payload는 URL 없는 본문만 허용한다.
- 외부 결과는 ledger read-back까지 확인한다.

---

## Install

Claude Code에서는 기존 `donggu-skills` marketplace의 `donggu-sns`를 설치한다. Codex에서는 다음 명령으로 repo marketplace와 plugin을 설치한다.

```bash
codex plugin marketplace add donggu1105/donggu-skills
codex plugin add donggu-sns@donggu-skills
```

설치 후에는 새 thread에서 `donggu-sns`의 skill 목록을 다시 로드한다. Claude Code와 Codex는 같은 `skills/` 트리를 읽고, Hermes `plugin.yaml`은 같은 package root에서 trusted native publishing tools를 추가로 제공한다. 실제 mutation은 Hermes에서만 수행한다.

## Dependencies

- 텍스트 작성: 추가 런타임 의존성 없음
- YouTube research: `baoyu-youtube-transcript`; thumbnail design/QA: `youtube-thumbnail-design`
- AI 이미지: 선택한 `get-ai-image` backend의 기존 환경변수 또는 로컬 ComfyUI
- publishing adapter: `PUBLISHER_API_TOKEN`(Tistory·Maily loopback API), `SNS_WEBHOOK_TOKEN`(나머지 채널), `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`

---

## Related

- 마켓플레이스: [donggu-skills](../)
- Vault 운영: [donggu-obsidian](../donggu-obsidian/)
