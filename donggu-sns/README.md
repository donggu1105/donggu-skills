# donggu-sns

> SNS content authoring skill collection — part of [`donggu-skills`](../) marketplace.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](../LICENSE)
[![Skills](https://img.shields.io/badge/skills-7-green)](#-skills)
[![Compatible](https://img.shields.io/badge/Obsidian-PKM-purple)](#-vault-가정)

옵시디언 vault 기반 SNS 작성·발행. **텍스트는 voice-learning 한 스킬**로, **아티팩트(카드·영상)와 발행은 전용 스킬**로 분리.

---

## 🧭 경계 — 말 / 물건 / 발행

```
writing-social-content   = 말 (보이스 대본)   — 글자만 쓴다
make-*                   = 물건 (카드·영상)   — 대본을 쓰지 않는다
publish-sns              = 발행               — 만들지도 쓰지도 않는다
```

## 📚 Skills

| Skill | 호출 | 사용 시점 | Output |
|---|---|---|---|
| **writing-social-content** | `donggu-sns:writing-social-content` | 텍스트 채널 글 작성 — Blog·LinkedIn·X·Threads·Maily (각 채널 독립, voice-learning + 발행 형식) | `<채널> - <title>.md` |
| **make-insta-card-news** | `donggu-sns:make-insta-card-news` | Instagram 카드뉴스 이미지 (DESIGN.md 기반) | 1080×1350 PNG 세트 |
| **make-shorts** | `donggu-sns:make-shorts` | 세로 숏폼 영상 (뉴스→CapCut 9:16) | CapCut 드래프트 |
| **youtube** | `donggu-sns:youtube` | YouTube 독립 아이디어 → transcript·thumbnail 전문 스킬 라우팅 → Longform + Shorts Pack → 회고 → CORE 환원 | Obsidian 영상 Pack |
| **publish-sns** | `donggu-sns:publish-sns` | tistory·maily·threads·linkedin·instagram 발행/삭제 | 발행 + Supabase 레저 |

---

## 🔁 사용 흐름

```
[새 이벤트]
    │
    ▼
┌────────────────────────────────────┐
│  writing-social-content            │  채널 택1 (각 채널 독립)
│  └ 채널 매트릭스 + voice-learning  │  Blog · LinkedIn · X · Threads · Maily
└──────────────┬─────────────────────┘     (같은 스킬, 채널만 바꿈 / 마스터 없음)
               │  발행 형식(`## 발행`/`## Draft`)으로 저장
               ▼
┌────────────────────────────────────┐
│  publish-sns                       │  채널 발행 + 레저 기록
└────────────────────────────────────┘

이미지가 필요하면 → make-insta-card-news (카드)
영상이 필요하면   → make-shorts (세로 숏폼)
YouTube 채널 운영 → youtube (baoyu transcript + thumbnail design 라우팅 + Longform/Shorts Pack + CORE 환원)
```

---

## 🎤 Voice 시스템 (writing-social-content)

채널마다 *고유 voice 자산*(VOICE·CHANNEL_GUIDE)과 **정전(canon) 글**을 학습해 일관 유지 — 같은 채널엔 같은 톤, 쓸수록 voice 정착:

```
Personal Branding/50_Channel_Packs/<channel>/
├── _anchors/
│   ├── CHANNEL_GUIDE - <channel>.md     📜 룰 (분량·후크·알고리즘; Blog는 없음)
│   └── VOICE - <channel>.md             🎤 하드룰 + 정전(canon) 글 포인터 (보이스는 실제 글로 학습)
└── <channel> - <title>.md               📝 발행 글
```

채널별 분량·톤 차이는 writing-social-content의 **채널 매트릭스** 한 표로 관리.

---

## 📂 vault 가정

```
Personal Branding/
├── 50_Channel_Packs/
│   ├── INDEX - Channels.md           도메인 매뉴얼
│   ├── Blog/ LinkedIn/ X/ Threads/ Maily/   (각 _anchors/ + 발행 글)
│   └── Instagram/               (make-insta-card-news 카드)
├── 20_Core/                     atomic claims (CORE 인용 시)
├── 40_Snippets/                 후크·교훈·격언 (옵션)
└── 70_Projects/                 프로젝트 메타 (옵션)
```

자세한 path·frontmatter 스키마: vault `Personal Branding/50_Channel_Packs/INDEX - Channels.md`

---

## 🛠 의존성

- 옵시디언 REST API + MCP (vault retrieve용)
- Claude Code (AskUserQuestion + 글 생성)
- YouTube research: `baoyu-youtube-transcript`; thumbnail design/QA: `youtube-thumbnail-design`
- make-shorts: `edge-tts`, `pyCapCut` / make-insta-card-news: Playwright 또는 headless render api

---

## 🔗 관련

- 마켓플레이스: [donggu-skills](../)
- 짝 도메인: [donggu-obsidian](../donggu-obsidian/) (vault 운영 의례)
