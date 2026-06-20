---
name: writing-social-content
description: Use when writing a text post for the user's Obsidian-vault SNS channels — Blog (master long-form), LinkedIn, X/Twitter, Threads, or Maily newsletter — in the user's learned voice, including drafting, adapting a master post to a channel, or formatting a note for publishing. Not for Instagram card images or short-form video.
---

# Writing Social Content

## Overview

사용자의 **텍스트 SNS 채널 전부**(Blog 마스터 + LinkedIn·X·Threads 변형 + Maily 뉴스레터)를 한 스킬로 작성한다. 핵심은 **voice-learning** — 그 채널의 기존 발행 글에서 톤·종결·시그니처를 학습해 일관 유지. 채널 차이는 [채널 매트릭스]로 흡수하고, 작성 절차(retrieve→대화형→생성→저장)는 공통이다.

**Core**: Socratic retrieve. 자동 자산(VOICE·CHANNEL_GUIDE·WINNING_PATTERNS·기존 글)은 강제, 선택 자산(GENRE·STRUCTURE·PROJECT·CORE)은 한 결정씩 물어본다.

## When to Use
- 텍스트 채널(blog·linkedin·x·threads·maily) 중 하나에 새 글/변형 작성
- Blog 마스터 → 다른 채널 압축 변형
- 기존 노트를 발행 가능한 형식(`## 발행`/`## Draft`)으로 정형화

## When NOT to Use
- Instagram 카드 이미지 → `donggu-sns:make-insta-card-news`
- 세로 숏폼 영상(Shorts·Reels) → `donggu-sns:make-shorts`
- 실제 게시·삭제 → `donggu-sns:publish-sns`

## 채널 매트릭스 (단일 기준표)

| 채널 | VOICE 앵커 | 분량 | 톤 | 핵심 규칙 | 저장 / 발행 형식 |
|---|---|---|---|---|---|
| **blog** (마스터) | `VOICE - Blog` (CHANNEL_GUIDE 없음) | 2,000~2,500자 | voice 학습 | GENRE×STRUCTURE, 다른 채널의 원천 | `Blog/Blog - <t>.md` · tistory 발행 = 본문 그대로(첫 줄=제목) |
| **linkedin** | `VOICE - LinkedIn` | 1,200~1,400자 | 정중 존댓말 | 첫 3줄 후크(모바일 ~210자), 단문+줄바꿈, 끝 댓글유도, 링크는 첫 댓글 | `LinkedIn/...` · 발행 = `## Draft` 확정본 |
| **x (ko)** | `VOICE - X` 한국어 풀 | 140자 / 스레드 | 명사형 건조 빌더 | "~함/~됨" 종결, Thread "1/N", 링크 첫 댓글 | `X/...` (`language: korean`) |
| **x (en)** | `VOICE - X` 영어 풀 | 280자 / 스레드 | indie hacker | "I shipped X.", `#buildinpublic`, 스크린샷·데이터, "🧵" | `X/...` (`language: english`) |
| **threads** | `VOICE - Threads` | 500자 / 5~7타래 | 친근 반말 | 5~7줄 짧은 호흡, 미완 끝맺음, 링크 첫 댓글 | `Threads/...` · 발행 = `## 발행`(아래) |
| **maily** | blog/threads voice 조합 | 뉴스레터 편지 | 편지체 | 인사 → `### 소제목` 본문 → "오늘 한 가지만" → 맺음 | `Maily/...` · 발행 = `## 발행`(아래) |

> 경로 베이스: `Personal Branding/50_Channel_Packs/1_SNS/<채널>/`. 각 채널 `_anchors/`에 VOICE·CHANNEL_GUIDE·WINNING_PATTERNS.
> ⚠️ x: 한국어/영어 풀은 **같은 시간 발행 금지**(SimClusters 다름).

## Workflow (공통)

### 1. 자동 retrieve (입력 없음)
- 채널 `_anchors/`: **VOICE**(톤·종결·시그니처) + **CHANNEL_GUIDE**(분량·알고리즘; blog는 없음) + **WINNING_PATTERNS**(Top 3 combo)
- **기존 발행 글 1~3개**: `<채널> - *.md` list → 사용자 선택(또는 최근 2개) → 종결 어미 비율·시그니처·후크 패턴 학습. *이게 voice-learning의 핵심 — 생략하면 일관성이 깨진다.*

### 2. 대화형 (AskUserQuestion, 한 결정씩)
채널 → 글 정보 → GENRE(회고/튜토리얼/인사이트/공지…) → STRUCTURE(BLUF/미괄식/PAS/Listicle…) → PROJECT 연결❓ → CORE 인용❓
(x = 언어 선택 / threads·x = 단일 vs 스레드)

### 3. 생성
- 매트릭스의 채널 규칙(분량·톤·핵심) 적용
- **voice 일관성 강제**: 기존 글 종결 어미 비율 모방, 시그니처 표현 재사용, 회피 단어(과장 형용사·AI 클리셰) 제거
- 선택한 WINNING_PATTERNS combo 적용
- **blog: 본문 확정 후 이미지 배치**(아래 [블로그 이미지 배치]) — 동구님이 찍은 캡처가 없을 때만

### 4. 저장
- Path: `1_SNS/<채널>/<채널> - <title>.md`
- frontmatter: `type: content` · `channel: <ch>` · `project:` · `status: draft` · (변형이면) `blog_version: "[[Blog - <t>]]"` · (x) `language:`
- **발행 채널이면 발행 형식 섹션까지** (아래)

## 발행 형식 (구 make-note 흡수 — 발행기가 읽는 정본)

발행기는 노트의 **딱 한 섹션**만 기계적으로 읽는다. 그 밖 섹션(전략·시안·메모)은 전부 무시된다.

**threads — `## 발행`**
- 본문 그대로 (인용블록 `>`로 감싸지 말 것 — `>`까지 그대로 발행됨)
- ≤500자(이미지 임베드 줄 제외), 해시태그 **본문 끝 1개만**, 외부 링크 본문 금지(첫 댓글)
- 이미지 `![[파일]]` 임베드, **순서 = 게시 순서**(0장=텍스트 · 1장=단일 · 2장+=캐러셀)
- 끝은 답글 유도(질문/미완 끝맺음)
- **타래(5~7개)는 자동 발행 미지원** — `## 발행`엔 단일 ≤500자 하나만 둔다. 타래 초안·첫 댓글 링크 등 운영 메모는 **섹션 밖**에 (발행기는 `## 발행` 한 섹션만 읽음 → 수동 발행)

**maily — `## 발행`**
- 1행 = 메일 제목 / 2행 = **부제목(필수 — 비우면 받은편지함 미리보기가 본문 첫 줄로 깨짐)** / 빈 줄 / 본문
- 본문은 마크다운 부분집합만: `### 소제목` · `**볼드**` · `> 인용` · `1.`/`-` 목록 · `---` 가로줄 (버튼·이미지·테이블은 에디터 전용 → dry_run 후 수동)

**linkedin — `## Draft`** 확정본 한 개.
> 이미지가 필요하면 카드는 `make-insta-card-news` 파이프라인을 재사용한다.

## 블로그 이미지 배치 (대표이미지 + 문단별 삽화)

블로그 본문이 확정되면 **대표이미지 1장 + 문단(섹션)마다 1장**을 `donggu-sns:get-stock-image`로 받아 끼운다. 카드/캐러셀이 아니라 본문에 흐르는 **무료 스톡 사진·삽화**다. 동구님이 직접 찍은 캡처·결과물이 있으면 **그게 1순위**, 이 절차는 그게 없을 때.

**원칙: 1장이 1주제.** 글 전체 무드는 대표이미지가, 각 섹션의 논점은 그 섹션 사진이 받친다. 같은 사진 재사용 금지, 장식용 추상 이미지 남발 금지 — 섹션이 말하는 그것을 보여준다.

**절차**
1. **섹션 분해** — 리드(대표이미지) + `##`/`###` 소제목별로 1블록. 소제목이 없으면 의미 문단 단위.
2. **블록마다 영어 키워드 1개 + `--kind`** 뽑기. 대표이미지는 글 전체 주제, 섹션은 그 섹션의 핵심 논점에서. (예: "채용시장에 나와 보니" → `job interview office` /photo, "문제는 그 뒤에 있다" → `missing puzzle piece` /concept)
3. `get-stock-image` 실행 → vault에 저장. 경로는 토픽 슬러그 폴더 하나에 모은다: `<채널폴더>/_img/<토픽슬러그>/hero.jpg`, `01-<섹션>.jpg` … (파일명은 vault 전역 유일하게).
4. **저장 후 반드시 Read로 주제 적합성 확인** → 어긋나면 `--index` 올려 재시도(스킬 규칙).
5. **본문에 임베드** — 대표이미지는 제목 바로 아래(리드 앞), 섹션 이미지는 그 `##` 소제목 바로 아래에 `![[hero.jpg]]` 형식. **임베드 위치 = 발행본에서 보일 위치.**
6. commons/openverse(CC) 결과면 반환 JSON의 `license`·`credit` 확인 → 출처표기 필요 시 글 말미 `## 🔗 연결`/출처에 적는다.

> 업로드는 신경 안 써도 된다 — `publish-sns`(발행 주체)가 `![[…]]`를 Supabase Storage(`sns-media`)에 올리고 공개 URL로 치환한다. 작성자는 **vault에 파일 저장 + 위치에 임베드**까지만.

## Common Mistakes
| 실수 | 수정 |
|---|---|
| 기존 글 안 보고 작성 | VOICE만 추론 = 일관성 깨짐. 발행 글 1~3개 필수 retrieve |
| 채널 톤 혼용 (LinkedIn 존댓말 → Threads에) | 매트릭스 톤 준수 (threads=반말, x-ko=명사형, linkedin=존댓말) |
| GENRE/STRUCTURE 디폴트 강제 (회고·미괄식) | 사용자 선택 |
| 본문에 외부 링크 | 첫 댓글로 |
| threads `## 발행`에 인용블록/옵션 A·B | 확정본 하나, 인용블록 금지 |
| maily 부제목 누락 | 2행 필수 |
| x 한국어+영어 동시 발행 | 시간 분리 |
| 블로그 이미지 저장만/Read 안 함 | 항상 Read로 주제 적합성 확인, 어긋나면 `--index`↑ |
| 섹션마다 같은 사진/장식용 추상 이미지 | 1장=1주제, 섹션 논점을 보여주는 사진 |

## 경계 (모든 donggu-sns 스킬 공통 헌법)
- **글자만 쓴다.** 카드 이미지·영상은 만들지 않는다 → `make-insta-card-news` / `make-shorts`
- **게시는 안 한다** → `publish-sns`

## 관련 Skill
- 블로그 본문 사진(대표·삽화): `donggu-sns:get-stock-image`
- 카드 이미지: `donggu-sns:make-insta-card-news`
- 숏폼 영상: `donggu-sns:make-shorts`
- 발행: `donggu-sns:publish-sns`
- vault health: `donggu-obsidian:checking-vault-health`

## 태그
#sns #blog #linkedin #threads #x #maily #content-writing #voice-learning
