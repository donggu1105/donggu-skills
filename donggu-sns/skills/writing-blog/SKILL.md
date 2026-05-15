---
name: writing-blog
description: Use when writing a Blog post (long-form 2,000-2,500자) on user's personal Obsidian-vault-backed blog channel — retrieves channel voice, winning patterns, and past published posts to maintain consistent tone learned from user's own writing
---

# Writing Blog Post

## Overview

Blog 채널 글 작성. **기존 발행 글의 voice·tone을 자동 학습**해서 일관 유지. 같은 채널엔 같은 톤 — 사용자가 글 쓰면 쓸수록 voice가 정착.

**Core**: Socratic retrieve. VOICE·WINNING_PATTERNS·기존 글은 자동, 글 종류·구조·PROJECT/CORE/SNIPPET은 선택.

## When to Use

- 사용자 Blog 채널에 새 글 작성 (Tistory/Velog/본인 도메인)
- 풀버전 회고·튜토리얼·인사이트·해설·리뷰·리스티클 등
- 다른 채널 변형의 *마스터*가 필요할 때

## When NOT to Use

- 다른 채널 → `donggu-sns:writing-linkedin/threads/x/instagram/youtube`
- 짧은 인사이트 메모 → 직접 작성

## Workflow

### 자동 retrieve (사용자 입력 없음)

1. **VOICE** — `obsidian:read Personal Branding/50_Channel_Packs/1_SNS/Blog/_anchors/VOICE - Blog.md`
   → 톤·종결·호흡·시그니처·회피 룰

2. **(Blog는 CHANNEL_GUIDE 없음** — 마스터)

3. **WINNING_PATTERNS** — `obsidian:read 1_SNS/Blog/_anchors/WINNING_PATTERNS - Blog.md`
   → Top 3 combo + Winning Voice + 케이스

4. **기존 발행 글 샘플 retrieve (voice 학습용)**:
   - `obsidian:list_files_in_dir 1_SNS/Blog/`
   - `Blog - *.md` 파일 list (CHANNEL_GUIDE·WINNING_PATTERNS·VOICE 제외)
   - **사용자에게 AskUserQuestion**: "기존 발행 글 중 voice 샘플로 참고할 것 선택?" (1~3개 선택, 또는 "최근 2개 자동")
   - 선택한 글 read → 문장 패턴·시그니처 표현·종결 어미 학습

### 대화형 retrieve (AskUserQuestion, 한 결정씩)

5. **글 정보**: "어떤 글이에요? (제목·핵심 메시지)" → 자유 입력

6. **GENRE 선택**: "어떤 글 종류?"
   - 회고 / 튜토리얼 / 공지·출시 / 인터뷰 / 인사이트·오피니언 / 해설 / 리뷰 / 리스티클

7. **STRUCTURE 선택**: "어떤 구조?"
   - BLUF(두괄식) / 미괄식 / 양괄식 / SAR / CARL / Q&A / Listicle / AIDA·PAS·BAB

8. **PROJECT 연결 ❓**: YES → `70_Projects/PROJECT - <project>.md` retrieve → related_blog·related_cores 파싱

9. **CORE 인용 ❓**: YES → 후보 선택 또는 직접 입력

10. **SNIPPET ❓**: YES → 종류·파일 선택

### 생성

11. **voice 일관성 강제**:
    - 기존 글 샘플의 종결 어미 비율 (예: "였습니다" 70% / "였어요" 30%) 모방
    - 시그니처 표현 ("결국 ~ 같습니다" 등) 재사용
    - 회피 단어 (과장 형용사·AI 클리셰) 적용
    - WINNING_PATTERNS의 Top 3 combo에서 사용자 선택한 GENRE×STRUCTURE 패턴 적용

12. **분량**: 2,000~2,500자 sweet spot

### 저장

13. **Path**: `Personal Branding/50_Channel_Packs/1_SNS/Blog/Blog - <title>.md`

14. **frontmatter**:
    ```yaml
    type: content
    channel: blog
    project: <프로젝트명>
    linkedin_version: "[[LinkedIn - <title>]]"
    tags: [채널/Blog, 브랜드/..., 주제/...]
    status: draft
    ```

## Common Mistakes

| 실수 | 수정 |
|---|---|
| 기존 글 안 보고 작성 | VOICE만 추론하면 일관성 깨짐 — 발행 글 1~3개 필수 retrieve |
| 디폴트 회고형 강제 | GENRE는 사용자 선택. 회고 디폴트 X |
| 미괄식 강제 | STRUCTURE는 사용자 선택. 회고가 아니면 BLUF가 흔함 |
| WINNING_PATTERNS 무시 | Top 3 combo 중 사용자가 선택한 것 따라야 |
| 기존 글 시그니처 표현 무시 | "결국 ~ 같습니다" 등 누적된 시그니처 재사용 |

## 관련 Skill

- 다른 채널: `donggu-sns:writing-linkedin`, `writing-threads`, `writing-x`, `writing-instagram`, `writing-youtube`
- vault health: `donggu-obsidian:checking-vault-health`

## 태그

#sns #blog #content-writing #voice-learning
