---
name: writing-x
description: Use when writing a Twitter/X post — Korean noun-form (140자) or English indie hacker thread — retrieves channel voice, winning patterns, and past X posts to maintain consistent tone. Korean and English pools require separate timing
---

# Writing X (Twitter) Post

## Overview

X 채널 글 작성. **한국어/영어 풀 분리**. 기존 발행 글 voice 학습 + indie hacker / quote tweet 알고리즘 최적화.

**Core**: Socratic retrieve. 한국어=명사형 건조 빌더 톤, 영어=indie hacker 데이터 노출.

## When to Use

- X 채널에 새 글 작성 (한국어 또는 영어)
- 단일 트윗 (280자) 또는 스레드 (5~10개)
- 빌더·창업가 풀 도달

## When NOT to Use

- 다른 채널 → 각 채널 스킬
- 한국어+영어 동시 발행 — 시간 분리 필수 (SimClusters 다름)

## Workflow

### 자동 retrieve

1. **VOICE** — `obsidian:read 1_SNS/X/_anchors/VOICE - X.md`
   → 한국어 풀(명사형) / 영어 풀(indie hacker) 분리

2. **CHANNEL_GUIDE** — `obsidian:read 1_SNS/X/_anchors/CHANNEL_GUIDE - X.md`
   → 외부 링크 페널티, Premium 효과, 발행 시간

3. **WINNING_PATTERNS** — `obsidian:read 1_SNS/X/_anchors/WINNING_PATTERNS - X.md`
   → (영어) 회고×BLUF×명사형+스크린샷 / (한국어) 튜토리얼×Thread Listicle×명사형 / 인사이트×PAS×명사형

4. **기존 발행 글 샘플**:
   - `X - *.md` 파일 list
   - 사용자 1~3개 선택
   - 종결·해시태그·Thread 1/N 패턴 학습

### 대화형

5. **언어 선택**: "한국어 풀 / 영어 풀?"
6. **글 정보**: "어떤 글?"
7. **단일 vs 스레드**: "단일 280자 / 스레드 N개?"
8. **GENRE**: 회고 / 튜토리얼 / 인사이트·오피니언 / 공지
9. **STRUCTURE**: BLUF / Thread Listicle / PAS
10. **PROJECT 연결 ❓**
11. **CORE 인용 ❓**

### 생성

#### 한국어 풀
- **명사형 종결** ("~함", "~됨", "~한 결과")
- 1인칭 생략 또는 "나"
- 140자 안, 한 줄 줄바꿈
- 건조한 빌더 톤 (정중 존댓말 X, 친근 반말 X)
- Thread는 "1/N" 명시

#### 영어 풀
- **indie hacker 톤** — "I shipped X. Here's what broke."
- Past simple, casual
- 280자 한도 (Premium 더)
- Thread "🧵" 또는 "1/" 명시
- 스크린샷·차트·MRR 데이터 첨부
- 해시태그 `#buildinpublic` `#indiehackers` `#solofounder`

### 공통
- 외부 링크는 본문 X, 첫 댓글에
- 한국어/영어 같은 시간 발행 금지

### 저장

12. **Path**: `1_SNS/X/X - <title>.md`

13. **frontmatter**:
    ```yaml
    type: content
    channel: x
    language: korean | english
    project: <프로젝트명>
    blog_version: "[[Blog - <title>]]"
    status: draft
    ```

## Common Mistakes

| 실수 | 수정 |
|---|---|
| 한국어에 정중 존댓말 | LinkedIn 톤. 명사형 건조 빌더 톤으로 |
| 영어에 LinkedIn formal | indie hacker 카주얼 톤으로 |
| 한국어+영어 같은 시간 발행 | SimClusters 다름 — 시간 분리 |
| 본문 외부 링크 | 첫 댓글에 |
| 스크린샷·이미지 없이 링크만 | 영어 풀에선 데이터 노출 필수 |

## 관련 Skill

- 마스터 글: `donggu-sns:writing-blog`
- 다른 채널: `writing-linkedin`, `writing-threads`, `writing-instagram`, `writing-youtube`

## 태그

#sns #x #twitter #content-writing #voice-learning #buildinpublic
