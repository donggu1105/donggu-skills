# donggu-sns

> SNS content authoring skill collection — part of [`donggu-skills`](../) marketplace.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](../LICENSE)
[![Skills](https://img.shields.io/badge/skills-6-green)](#-skills)
[![Compatible](https://img.shields.io/badge/Obsidian-PKM-purple)](#-vault-가정)

옵시디언 vault 기반 SNS 발행 의례 자동화. **채널별 6개 스킬**. 각 스킬은 그 채널의 *기존 발행 글 voice를 자동 학습*해서 일관 적용.

---

## 📚 Skills

| Skill | 호출 | 사용 시점 | Output |
|---|---|---|---|
| **writing-blog** | `donggu-sns:writing-blog` | 블로그 마스터 글 작성 | `Blog - <title>.md` (2,000~2,500자) |
| **writing-linkedin** | `donggu-sns:writing-linkedin` | LinkedIn 한국 IT/PE 타겟 | `LinkedIn - <title>.md` (1,200~1,400자) |
| **writing-threads** | `donggu-sns:writing-threads` | Threads 친근 반말 | `Threads - <title>.md` (500자 단일 / 5타래) |
| **writing-x** | `donggu-sns:writing-x` | X 한국어 또는 영어 indie hacker | `X - <title>.md` |
| **writing-instagram** | `donggu-sns:writing-instagram` | Instagram 캐러셀 7~10장 | `Instagram - <title>.md` |
| **writing-youtube** | `donggu-sns:writing-youtube` | YouTube Shorts 60초 / 롱폼 8~12분 | `YouTube - <title>.md` |

---

## 🔁 사용 흐름

```
[새 이벤트 발생]
    │
    ▼
┌──────────────────────────────┐
│  writing-blog                │  Blog 마스터 (2,250자)
└──────────┬───────────────────┘
           │
           ▼
[Blog 발행 + 1~7일 대기]
           │
           ▼
┌──────────────────────────────┐
│  writing-<채널> × 5          │  채널별 변형
│   writing-linkedin           │
│   writing-threads            │
│   writing-x                  │
│   writing-instagram          │
│   writing-youtube            │
└──────────────────────────────┘
```

각 스킬은 *그 채널의 기존 발행 글 1~3개*를 retrieve해서 voice 일관 유지.

---

## 🧬 공통 패턴 (Socratic retrieve)

각 채널 스킬 동일 구조:

### 자동 retrieve (사용자 입력 X)
1. **VOICE** — `1_SNS/<channel>/VOICE - <channel>.md`
2. **CHANNEL_GUIDE** — `1_SNS/<channel>/CHANNEL_GUIDE - <channel>.md` (Blog는 없음)
3. **WINNING_PATTERNS** — `1_SNS/<channel>/WINNING_PATTERNS - <channel>.md`
4. **기존 발행 글 샘플** — `<channel> - *.md` 1~3개 (사용자 선택 또는 최근 자동)

### 대화형 (AskUserQuestion 한 결정씩)
5. 글 정보 입력
6. GENRE 선택 (8개 중)
7. STRUCTURE 선택 (8개 중)
8. PROJECT 연결 ❓
9. CORE 인용 ❓
10. SNIPPET ❓

### 생성 + 저장
11. voice 일관 (기존 글 종결 어미·시그니처 표현 모방)
12. WINNING_PATTERNS 체크리스트 통과
13. 옵시디언 새 파일 저장

---

## 🎤 Voice 시스템

각 채널마다 *고유 voice 자산 3종*:

```
1_SNS/<channel>/
├── CHANNEL_GUIDE - <channel>.md      📜 룰 (분량·후크·알고리즘)
├── VOICE - <channel>.md              🎤 톤·종결·호흡·시그니처
├── WINNING_PATTERNS - <channel>.md   🎯 실전 combo + 케이스
└── <channel> - <title>.md            📝 발행 글
```

같은 채널엔 같은 톤. 발행하면서 시그니처 표현 누적되면 voice 정착.

---

## 📂 vault 가정

```
Personal Branding/
├── 50_Channel_Packs/1_SNS/
│   ├── INDEX - SNS.md           도메인 매뉴얼
│   ├── Blog/                    (VOICE + WINNING_PATTERNS + 발행 글)
│   ├── LinkedIn/                (CHANNEL_GUIDE + VOICE + WINNING_PATTERNS + 발행 글)
│   ├── Threads/, X/, Instagram/, YouTube/
├── 20_Core/                     atomic claims (CORE 인용 시)
├── 40_Snippets/                 후크·교훈·격언 (옵션)
└── 70_Projects/                 프로젝트 메타 (옵션)
```

자세한 path·frontmatter 스키마: vault `Personal Branding/50_Channel_Packs/1_SNS/INDEX - SNS.md`

---

## 🛠 의존성

- 옵시디언 REST API + MCP (vault retrieve용)
- Claude Code (AskUserQuestion + 글 생성)

---

## 🔗 관련

- 마켓플레이스: [donggu-skills](../)
- 짝 도메인: [donggu-obsidian](../donggu-obsidian/) (vault 운영 의례)
