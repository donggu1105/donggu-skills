# donggu-sns

> Portable SNS authoring and gated publishing — part of [`donggu-skills`](../) marketplace.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](../LICENSE)
[![Skills](https://img.shields.io/badge/skills-7-green)](#-skills)

Blog·LinkedIn·Threads·Maily 텍스트 작성, Instagram·Shorts 아티팩트 생성, YouTube 기획, 외부 채널 발행을 역할별 스킬로 분리한다.

---

## 경계 — 말 / 물건 / 발행

```text
writing-social-content   = 말       — 글자만 작성
make-*                   = 물건     — 카드·영상 아티팩트 생성
youtube                  = 영상 기획 — Longform + Shorts Pack
publish-sns              = 발행     — 승인 뒤 외부 채널 반영
```

## Skills

| Skill | 사용 시점 | Output |
|---|---|---|
| **writing-social-content** | Blog·LinkedIn·Threads·Maily 텍스트 작성·변환 | 채널별 확정 초안 |
| **make-insta-card-news** | Instagram 카드뉴스 이미지 | 1080×1350 PNG 세트 |
| **make-shorts** | 세로 숏폼 영상 | CapCut 드래프트 |
| **youtube** | YouTube Longform + Shorts Pack 기획·회고 | 영상 Pack |
| **publish-sns** | tistory·maily·threads·linkedin·instagram 발행·삭제 | 발행 결과 + ledger |
| **get-stock-image** | 스톡 이미지 검색·저장 | 이미지 파일 |
| **get-ai-image** | 로컬 생성 이미지 | 이미지 파일 |

---

## 텍스트 작성 구조

`writing-social-content`는 하나의 라우터와 스킬 내부 reference로 동작한다.

```text
writing-social-content/
├── SKILL.md
└── references/
    ├── common-voice.md
    ├── blog.md
    ├── linkedin.md
    ├── threads.md
    └── maily.md
```

```text
사용자 source·URL·브리프
        ↓
common-voice + 요청 채널 reference
        ↓
채널별 독립 초안
```

- 공통 보이스와 요청받은 채널 reference만 읽는다.
- 외부 VOICE 문서, canon 글, 특정 Vault 경로를 요구하지 않는다.
- 현재 source가 내용의 정본이다.
- 다른 채널 문장을 길이만 바꿔 재사용하지 않는다.
- Blog·LinkedIn·Threads·Maily를 별도 스킬로 쪼개지 않는다.

## 작성 이후

```text
텍스트 확정
├── 파일 저장 요청 → target-native 파일 도구
├── 이미지 요청    → get-stock-image / get-ai-image
├── 카드 요청      → make-insta-card-news
├── 영상 요청      → youtube / make-shorts
└── 게시 요청      → publish-sns preview·approval
```

`writing-social-content`는 저장 경로, schema, frontmatter, 이미지, 게시를 소유하지 않는다. 저장 대상이 Obsidian이어도 해당 Vault의 규칙은 저장 단계에서만 적용한다.

---

## 발행 안전 경계

- 실제 외부 게시·수정·삭제는 `publish-sns`만 수행한다.
- preview와 사용자 승인 없이 게시하지 않는다.
- Maily 실제 발송은 별도 2차 확인이 필요하다.
- 외부 결과는 ledger read-back까지 확인한다.

---

## Dependencies

- 텍스트 작성: 추가 런타임 의존성 없음
- YouTube research: `baoyu-youtube-transcript`; thumbnail design/QA: `youtube-thumbnail-design`
- make-shorts: `edge-tts`, `pyCapCut`
- make-insta-card-news: Playwright 또는 headless render API
- publishing adapter: `SNS_WEBHOOK_TOKEN`, `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`

---

## Related

- 마켓플레이스: [donggu-skills](../)
- Vault 운영: [donggu-obsidian](../donggu-obsidian/)
