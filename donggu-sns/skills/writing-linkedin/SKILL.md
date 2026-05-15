---
name: writing-linkedin
description: Use when writing a LinkedIn post (1,200-1,400자 compressed) for Korean IT/startup/PE/B2B audience — retrieves channel voice, winning patterns, and past LinkedIn posts to maintain consistent tone learned from user's own writing
---

# Writing LinkedIn Post

## Overview

LinkedIn 채널 글 작성. **기존 발행 글의 voice·tone 학습** + 한국 1인 창업가/PE 풀 알고리즘 최적화 (dwell time + 댓글).

**Core**: Socratic retrieve. 자동 자산은 강제, 선택 자산은 한 결정씩 물어봄.

## When to Use

- LinkedIn 채널에 새 글 작성
- Blog 마스터 글 압축 변형 또는 단독 인사이트 글
- 한국 IT/스타트업/PE/B2B 타겟 도달

## When NOT to Use

- 다른 채널 → 각 채널 스킬 사용
- 영어권 전용 콘텐츠 → X 영어 풀로

## Workflow

### 자동 retrieve

1. **VOICE** — `obsidian:read 1_SNS/LinkedIn/_anchors/VOICE - LinkedIn.md`
   → 정중 존댓말·첫 3줄 후크·단문 호흡

2. **CHANNEL_GUIDE** — `obsidian:read 1_SNS/LinkedIn/_anchors/CHANNEL_GUIDE - LinkedIn.md`
   → 분량 1,200~1,400자, 외부 링크 페널티, 발행 시간

3. **WINNING_PATTERNS** — `obsidian:read 1_SNS/LinkedIn/_anchors/WINNING_PATTERNS - LinkedIn.md`
   → 회고×BLUF / 인사이트×PAS / 튜토리얼×Listicle Top 3 combo

4. **기존 발행 글 샘플** (voice 학습):
   - `obsidian:list_files_in_dir 1_SNS/LinkedIn/`
   - `LinkedIn - *.md` 파일 list
   - 사용자에게 1~3개 선택 받음 (또는 "최근 2개 자동")
   - 선택한 글 read → 후크 패턴·종결 어미·시그니처 표현·댓글 유도 패턴 학습

### 대화형 (AskUserQuestion)

5. **글 정보**: "어떤 글이에요?"
6. **GENRE**: 회고 / 인사이트·오피니언 / 공지·출시 / 튜토리얼 / 인터뷰 등
7. **STRUCTURE**: BLUF / PAS / SAR / Listicle 등
8. **PROJECT 연결 ❓** → PROJECT retrieve
9. **CORE 인용 ❓** → 후보 선택
10. **마스터 블로그 있으면 retrieve 자동 추천 ❓** (PROJECT의 related_blog)

### 생성

11. **첫 3줄 후크** (모바일 ~210자 잘림) — 기존 글 후크 패턴 모방
12. **단문 + 줄바꿈** (벽돌 텍스트 회피)
13. **마지막 줄 댓글 유도 질문** ("여러분은 어떠세요?")
14. **외부 링크는 본문 금지** — "전체 회고는 댓글에 ↓" 명시
15. **분량 1,200~1,400자**

### 저장

16. **Path**: `1_SNS/LinkedIn/LinkedIn - <title>.md`

17. **frontmatter**:
    ```yaml
    type: content
    channel: linkedin
    project: <프로젝트명>
    blog_version: "[[Blog - <title>]]"
    status: draft
    ```

## Common Mistakes

| 실수 | 수정 |
|---|---|
| 기존 글 안 보고 작성 | 발행 글 1~3개 필수 retrieve |
| 본문에 외부 링크 | 첫 댓글에 빼기 (도달 -30~50%) |
| 2,000자+ 길게 | 1,200~1,400자로 압축 (한국 LinkedIn은 짧은 호흡 선호) |
| 영어 클리셰 ("Here's why ↓", 🚀) | 회피 |
| 댓글 유도 질문 없이 끝맺음 | 마지막 줄에 질문 박기 |

## 관련 Skill

- Blog 마스터: `donggu-sns:writing-blog`
- 다른 채널: `donggu-sns:writing-threads`, `writing-x`, `writing-instagram`, `writing-youtube`

## 태그

#sns #linkedin #content-writing #voice-learning
