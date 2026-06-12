---
name: writing-threads
description: Use when writing a Threads post (single 500자 or 5타래) in casual Korean tone for reply-driven algorithm — retrieves channel voice, winning patterns, and past Threads posts to maintain consistent tone learned from user's own writing
---

# Writing Threads Post

## Overview

Threads 채널 글 작성. **기존 발행 글의 voice·tone 학습** + 답글·체류시간 알고리즘 최적화 (reply 1개 = 도달 폭발).

**Core**: Socratic retrieve. 친근 반말체, 5~7줄 짧은 호흡.

## When to Use

- Threads 채널에 새 글 작성
- 단일 게시물 (500자) 또는 타래 (5~7개)
- 가벼운 회고·질문·공지

## When NOT to Use

- 다른 채널 → 각 채널 스킬 사용
- 풀버전 회고·튜토리얼 → Blog/LinkedIn

## Workflow

### 자동 retrieve

1. **VOICE** — `obsidian:read 1_SNS/Threads/_anchors/VOICE - Threads.md`
   → 친근 반말·평어체, 5~7줄, 미완 끝맺음

2. **CHANNEL_GUIDE** — `obsidian:read 1_SNS/Threads/_anchors/CHANNEL_GUIDE - Threads.md`
   → 답글 가중치, 발행 시간, 이미지 4:5

3. **WINNING_PATTERNS** — `obsidian:read 1_SNS/Threads/_anchors/WINNING_PATTERNS - Threads.md`
   → 회고×미괄식 / 인사이트×Q&A / 공지×BLUF Top 3

4. **기존 발행 글 샘플**:
   - `Threads - *.md` 파일 list
   - 사용자 1~3개 선택 (또는 최근 2개 자동)
   - 종결 어미·후크 패턴·이모지 사용·미완 끝맺음 패턴 학습

### 대화형

5. **글 정보**: "어떤 글?"
6. **단일 vs 타래**: "단일 게시물 / 타래 5개?"
7. **GENRE**: 회고 / 인사이트 / 공지·출시 / 질문 등
8. **STRUCTURE**: 미괄식 / Q&A / BLUF 등
9. **PROJECT 연결 ❓**
10. **CORE 인용 ❓**

### 생성

11. **친근 반말 또는 평어체** ("~ 였어요", "~함", "~다")
12. **5~7줄 짧은 호흡**, 단락당 1~2문장
13. **줄 시작 이모지** OK (✔️ ▶︎ 📌 👇)
14. **미완 끝맺음** ("↓", "...", "어떻게 생각함?")
15. **외부 링크는 첫 댓글**
16. 단일 500자 한도 / 타래 5~7개

### 저장

17. **Path**: `1_SNS/Threads/Threads - <title>.md`

18. **frontmatter**:
    ```yaml
    type: content
    channel: threads
    project: <프로젝트명>
    blog_version: "[[Blog - <title>]]"
    status: draft
    ```

19. **발행 형식 = `make-threads` 스킬 규격** — 확정본을 **`## 발행` 섹션**에
    인용블록 없이 그대로(+`![[이미지]]` 임베드, 해시태그 마지막 1개). 자동 발행기는
    이 섹션만 집어간다. 시안 비교·타래 초안·전략은 섹션 밖에.

## Common Mistakes

| 실수 | 수정 |
|---|---|
| 정중 존댓말 풀버전 | LinkedIn 톤. 친근 반말로 |
| 7줄 넘는 길게 | 5~7줄. 단락 분할 |
| 답글 유도 없이 끝 | 미완 끝맺음 또는 질문 박기 |
| 본문 외부 링크 | 첫 댓글에 |

## 관련 Skill

- 마스터 글: `donggu-sns:writing-blog`
- 다른 채널: `writing-linkedin`, `writing-x`, `writing-instagram`, `writing-youtube`

## 태그

#sns #threads #content-writing #voice-learning
