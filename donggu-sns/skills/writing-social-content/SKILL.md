---
name: writing-social-content
description: Use when writing a text post for the user's Obsidian-vault SNS channels — Blog, LinkedIn, X/Twitter, Threads, or Maily newsletter — in the user's learned voice, including drafting a fresh post for a channel, writing the same topic for another channel, or formatting a note for publishing. Not for Instagram card images or short-form video.
---

# Writing Social Content

## Overview

사용자의 **텍스트 SNS 채널 전부**(Blog·LinkedIn·X·Threads·Maily)를 한 스킬로 작성한다. **각 채널은 독립적이다** — 마스터/변형 위계가 없다. 어느 채널도 다른 채널의 원천이 아니고, 모든 글은 주제 브리프 + 그 채널 VOICE(하드룰)와 정전(canon) 글에서 **새로** 쓴다. 핵심은 **voice-learning** — 그 채널의 정전·기존 발행 글에서 톤·종결·시그니처를 학습해 일관 유지. 채널 차이는 [채널 매트릭스]로 흡수하고, 작성 절차(retrieve→대화형→생성→저장)는 공통이다.

**Core**: Socratic retrieve. 자동 자산(VOICE·CHANNEL_GUIDE·정전 글)은 강제, 선택 자산(GENRE·STRUCTURE·PROJECT·CORE)은 한 결정씩 물어본다.

> **canon에서 배우는 건 보이스(톤·종결·시그니처·후크)지 내용·결론(CORE)이 아니다.** 새 소재는 기본 **채굴 모드** — 그 소재만의 새 앵글을 판다(기존 CORE로 수렴 금지, "얼마 전에 나는 ~썼다"式 자기 인용 금지). **수렴 모드**(기존 CORE 강화·연결)는 사용자가 명시할 때만. 매번 같은 코어로 수렴시키면 글이 다 똑같아지고 새 코어가 안 쌓인다 — 지금은 코어를 넓히는 단계라 채굴이 기본.

## When to Use
- 텍스트 채널(blog·linkedin·x·threads·maily) 중 하나에 새 글 작성
- 같은 주제를 다른 채널용으로 새로 작성 (각 채널 독립 — 마스터 없음)
- 기존 노트를 발행 가능한 형식(`## 발행`/`## Draft`)으로 정형화

## When NOT to Use
- Instagram 카드 이미지 → `donggu-sns:make-insta-card-news`
- 세로 숏폼 영상(Shorts·Reels) → `donggu-sns:make-shorts`
- 실제 게시·삭제 → `donggu-sns:publish-sns`

## 채널 매트릭스 (단일 기준표)

| 채널 | VOICE 앵커 | 분량 | 톤 | 핵심 규칙 | 저장 / 발행 형식 |
|---|---|---|---|---|---|
| **blog** | `VOICE - Blog` (CHANNEL_GUIDE 없음) | 2,000~2,500자 | voice 학습 | GENRE×STRUCTURE, 롱폼 | `Blog/Blog - <t>.md` · tistory 발행 = 본문 그대로(첫 줄=제목) |
| **linkedin** | `VOICE - LinkedIn` | 1,200~1,400자 | 장르별(에세이 평서체/행사 존댓말) | 첫 3줄 후크(모바일 ~210자), 단문+줄바꿈, 끝 댓글유도, 링크는 첫 댓글 | `LinkedIn/...` · 발행 = `## Draft` 확정본 |
| **x (ko)** | `VOICE - X` 한국어 풀 | 140자 / 스레드 | 명사형 건조 빌더 | "~함/~됨" 종결, Thread "1/N", 링크 첫 댓글 | `X/...` (`language: korean`) |
| **x (en)** | `VOICE - X` 영어 풀 | 280자 / 스레드 | indie hacker | "I shipped X.", `#buildinpublic`, 스크린샷·데이터, "🧵" | `X/...` (`language: english`) |
| **threads** | `VOICE - Threads` | 500자 / 5~7타래 | 친근 반말 | 5~7줄 짧은 호흡, 미완 끝맺음, 링크 첫 댓글 | `Threads/...` · 발행 = `## 발행`(아래) |
| **maily** | `VOICE - Maily` | 뉴스레터 편지 | 편지체 | 인사 → `### 소제목` 본문 → "오늘 한 가지만" → 맺음 | `Maily/...` · 발행 = `## 발행`(아래) |

> 경로 베이스: `Personal Branding/50_Channel_Packs/1_SNS/<채널>/`. 각 채널 `_anchors/`에 VOICE·CHANNEL_GUIDE. (WINNING_PATTERNS는 폐기 — 추상 combo가 글을 평균값으로 끌어당김. 보이스는 VOICE의 `canon:` 정전 글로 학습한다.)
> ⚠️ x: 한국어/영어 풀은 **같은 시간 발행 금지**(SimClusters 다름).

## Workflow (공통)

### 1. 자동 retrieve (입력 없음)
- 채널 `_anchors/`: **VOICE**(하드룰 + `canon:` 정전 글 목록) + **CHANNEL_GUIDE**(분량·알고리즘; blog는 없음)
- **정전(canon) 글 우선 + 기존 발행 글 1~3개**: VOICE의 `canon:`을 먼저 읽고, 없으면 `<채널> - *.md`에서 최근/대표 글 → 종결 어미 비율·시그니처·후크를 학습. *이게 voice-learning의 핵심 — 추상 규칙만 보면 평균값으로 homogenize된다. 실제 글이 보이스의 기준.*

### 2. 대화형 (AskUserQuestion, 한 결정씩)
채널 → 글 정보 → GENRE(회고/튜토리얼/인사이트/공지…) → STRUCTURE(BLUF/미괄식/PAS/Listicle…) → PROJECT 연결❓ → **CORE 모드❓ (매번 필수로 묻는다): 채굴(기본 — 기존 CORE 안 엮고 새 앵글) / 수렴(어떤 CORE를 엮을지 골라 강화). "어떤 코어를 쓸지, 아니면 안 쓸지"를 항상 확인한다.**
(x = 언어 선택 / threads·x = 단일 vs 스레드)

### 3. 생성
- 매트릭스의 채널 규칙(분량·톤·핵심) 적용
- **voice 일관성 강제**: 정전 글의 종결 어미 비율 모방, 시그니처 표현 재사용, 회피 단어(과장 형용사·AI 클리셰) 제거
- 정전(canon) 글의 후크·구조·종결을 따른다 (추상 combo·템플릿 아님 — 실제 글이 기준). **단 canon에서 가져오는 건 보이스지 내용·결론(CORE)이 아니다 — 내용은 위 CORE 모드 결정을 따른다(채굴이면 기존 코어 재사용·자기 인용 금지).**
- **blog: 본문 확정 후 이미지 배치**(아래 [블로그 이미지 배치]) — 동구님이 찍은 캡처가 없을 때만

### 4. 저장
- Path: `1_SNS/<채널>/<채널> - <title>.md`
- frontmatter: `type: content` · `channel: <ch>` · `project:` · `status: draft` · (같은 주제의 다른 채널 글이 있으면) `related: "[[<채널> - <t>]]"` (대등 링크 — 마스터 참조 아님) · (x) `language:`
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

> **적용 대상: `blog`(티스토리) 채널만.** LinkedIn·Threads·Maily·X는 이 절차 대상이 아니다 — 본문 삽화·대표이미지를 끼우지 않는다(각 채널 이미지 규칙은 위 [발행 형식] 참고: threads=`![[]]` 임베드 순서, instagram=카드 파이프라인, maily/linkedin=이미지 안 넣음).

블로그 본문이 확정되면 **대표이미지 1장 + 문단(섹션)마다 1장**을 `donggu-sns:get-stock-image`로 받아 끼운다. 카드/캐러셀이 아니라 본문에 흐르는 **무료 스톡 사진·삽화**다. 동구님이 직접 찍은 캡처·결과물이 있으면 **그게 1순위**, 이 절차는 그게 없을 때.

**원칙: 1장이 1주제.** 글 전체 무드는 대표이미지가, 각 섹션의 논점은 그 섹션 사진이 받친다. 같은 사진 재사용 금지, 장식용 추상 이미지 남발 금지 — 섹션이 말하는 그것을 보여준다.

**소스 선택 (stock | ai):** 같은 자리에 두 방법 중 하나를 쓴다 — 실제 사진/무드면 **스톡**(`donggu-sns:get-stock-image`), 주제 맞춤·일러스트·특정 장면을 만들고 싶으면 **AI 생성**(`donggu-sns:get-ai-image`, 로컬 ComfyUI 무료가 기본). **저장 경로·파일명·임베드 규칙은 둘 다 동일** → 어느 쪽이든 발행 파이프라인은 그대로. 글자(한글) 박힌 이미지는 둘 다 부적합 → 카드(`make-insta-card-news`). 동구님이 직접 찍은 결과물이 있으면 그게 1순위.

**절차**
1. **섹션 분해** — 리드(대표이미지) + `##`/`###` 소제목별로 1블록. 소제목이 없으면 의미 문단 단위.
2. **블록마다 프롬프트 뽑기** — 대표이미지는 글 전체 주제, 섹션은 그 섹션의 핵심 논점에서. 소스에 따라 밀도가 다르다:
   - **stock**: 영어 키워드 1개 + `--kind` (예: "채용시장에 나와 보니" → `job interview office` /photo, "문제는 그 뒤에 있다" → `missing puzzle piece` /concept)
   - **ai**: 키워드 1개론 약하다 → **서술형 영어 프롬프트**(장면 + 조명/무드 + 스타일). 섹션 논점을 한 장면으로 번역한다. (예: "문제는 그 뒤에 있다" → `a single missing puzzle piece on a wooden desk, soft directional light, editorial minimalism`). 글자(한글) 넣지 말 것.
3. **소스 실행** → vault에 저장 (stock=`get-stock-image` 키워드 / ai=`get-ai-image` 프롬프트). 경로는 토픽 슬러그 폴더 하나에 모은다: `<채널폴더>/_img/<토픽슬러그>/hero.jpg`, `01-<섹션>.jpg` … (파일명은 vault 전역 유일하게). AI면 프롬프트는 영어로, 대표이미지=가로 1200x630.
4. **저장 후 반드시 Read로 주제 적합성 확인** → 어긋나면 재시도: **stock**은 `--index` 올려 다음 후보, **ai**는 프롬프트를 더 구체화(장면·소재 명시)하거나 `--seed`를 바꿔 재생성.
5. **본문에 임베드** — 대표이미지는 제목 바로 아래(리드 앞), 섹션 이미지는 그 `##` 소제목 바로 아래에 `![[hero.jpg]]` 형식. **임베드 위치 = 발행본에서 보일 위치.**
6. commons/openverse(CC) 결과면 반환 JSON의 `license`·`credit` 확인 → 출처표기 필요 시 글 말미 `## 🔗 연결`/출처에 적는다.

> 업로드는 신경 안 써도 된다 — `publish-sns`(발행 주체)가 `![[…]]`를 Supabase Storage(`sns-media`)에 올리고 공개 URL로 치환한다. 작성자는 **vault에 파일 저장 + 위치에 임베드**까지만.

> **대표이미지(썸네일/OG) = 리드 이미지(첫 임베드).** 티스토리 발행 시 발행기가 이 hero를 글의 대표이미지로도 업로드한다(목록·SNS 공유 카드에 뜨는 썸네일). hero는 섹션 사진보다 더 신경 써서 **글 전체를 대표할 한 장**으로 고를 것. 등록·수정 동일.

## Common Mistakes
| 실수 | 수정 |
|---|---|
| 정전 글 안 보고 작성 | VOICE 하드룰만 추론 = 평균값 homogenize. VOICE `canon:` 정전 글 필수 retrieve |
| 채널 톤 혼용 (LinkedIn 존댓말 → Threads에) | 매트릭스 톤 준수 (threads=반말, x-ko=명사형, linkedin=장르별) |
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
