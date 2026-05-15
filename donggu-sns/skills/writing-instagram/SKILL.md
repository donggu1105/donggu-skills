---
name: writing-instagram
description: Use when creating an Instagram carousel (7-10 cards extracted from blog insights) or caption — retrieves channel voice, winning patterns, and past Instagram posts to maintain consistent tone learned from user's own writing
---

# Writing Instagram Post

## Overview

Instagram 채널 글 작성. **블로그 마스터 → 인사이트 카드 5장 추출** 미러 패턴. 캐러셀 1등 (2026 engagement 1.92% vs Reels 0.50%).

**Core**: Socratic retrieve. 기존 발행 글 voice 학습 + 비주얼 우선·저장 유도.

## When to Use

- Instagram 캐러셀 7~10장 작성
- 블로그 마스터의 인사이트 추출 미러
- 릴스 30~60초 (옵션)

## When NOT to Use

- 마스터 블로그 없음 → 먼저 `writing-blog` 사용
- 단순 인스타 사진 게시 → 직접 작성

## Workflow

### 자동 retrieve

1. **VOICE** — `obsidian:read 1_SNS/Instagram/01_VOICE - Instagram.md`
   → 친근 정중, 캡션 첫 1~3줄이 전부, 카드 25~40자

2. **CHANNEL_GUIDE** — `obsidian:read 1_SNS/Instagram/00_CHANNEL_GUIDE - Instagram.md`
   → 캐러셀 1080x1350, 해시태그 5개 하드 캡, bio 5개 링크

3. **WINNING_PATTERNS** — `obsidian:read 1_SNS/Instagram/02_WINNING_PATTERNS - Instagram.md`
   → 튜토리얼×Listicle / 회고×양괄식 / 공지×BLUF Top 3

4. **기존 발행 글 샘플**:
   - `Instagram - *.md` 파일 list
   - 사용자 1~3개 선택
   - 후크·CTA·해시태그 5개 세트·시각 위계 패턴 학습

### 대화형

5. **포맷**: "캐러셀 / 릴스 30초?"
6. **글 정보**: "어떤 글? 마스터 블로그 wikilink?"
7. **PROJECT 연결 ❓** → 마스터 블로그 자동 추천 (related_blog)
8. **GENRE**: 튜토리얼·Listicle / 회고·양괄식 / 공지·BLUF
9. **CORE 인용 ❓**

### 생성 (캐러셀)

10. **카드 7~10장**:
    - 카드 1: 후크 1줄 (5~8 단어, 가장 큰 타이포)
    - 카드 2~3: 맥락/약점 자백
    - 카드 4~7: 인사이트 5개 (블로그에서 추출)
    - 카드 8: 미괄식 결론 1줄
    - 카드 9: 한 줄 저장용 카드 (북마크 미끼)
    - 카드 10: CTA ("전체 글은 프로필 링크 ↓")

11. **캡션 ~500자**: 첫 1~3줄 후크 → 본문 → CTA → 해시태그 5개

12. **해시태그 5개**: 광범위 1~2 + 니치 2~3 (기존 글 해시태그 세트 모방)

### 생성 (릴스)

11'. **30~60초 스크립트**: 0~3초 후크 → 핵심 메시지 3개 → CTA

### 저장

13. **Path**: `1_SNS/Instagram/Instagram - <title>.md`

14. **frontmatter**:
    ```yaml
    type: content
    channel: instagram
    format: carousel | reels
    project: <프로젝트명>
    blog_version: "[[Blog - <title>]]"
    status: draft
    ```

## Common Mistakes

| 실수 | 수정 |
|---|---|
| 기존 글 안 보고 작성 | 발행 글 1~3개 필수 retrieve (시각 위계·해시태그 통일) |
| 미괄식 + 긴 캡션 | 캡션 1~3줄 후크 + 캐러셀로 분해 |
| 해시태그 30+ | 5개 하드 캡 (2025.12 이후 스팸 처리) |
| 카드 첫 장 약한 후크 | 80% 가중치, 후크에 시간 70% |
| LinkedIn 톤 옮기기 | 친근 정중으로 변환 |

## 관련 Skill

- 마스터 글: `donggu-sns:writing-blog`
- 다른 채널: `writing-linkedin`, `writing-threads`, `writing-x`, `writing-youtube`

## 태그

#sns #instagram #carousel #content-writing #voice-learning
