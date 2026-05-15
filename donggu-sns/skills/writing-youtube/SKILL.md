---
name: writing-youtube
description: Use when writing a YouTube Shorts script (30-60초) or long-form video outline (8-12min) — retrieves channel voice, winning patterns, and past YouTube scripts to maintain consistent tone learned from user's own writing
---

# Writing YouTube Post (Shorts or Long-form)

## Overview

YouTube 채널 글 작성. **Shorts와 롱폼 거의 다른 채널**. 기존 발행 스크립트 voice 학습 + retention 알고리즘 최적화.

**Core**: Socratic retrieve. Shorts=친근 반말+0~3초 결과 선공개, 롱폼=정중 존댓말+선예고+후증명.

## When to Use

- YouTube Shorts 스크립트 (30~60초)
- YouTube 롱폼 영상 아우트라인 (8~12분)
- 시청자=한국 1인 창업가/PE/AI 빌더

## When NOT to Use

- 다른 채널 → 각 채널 스킬
- 실시간 라이브 → 별도

## Workflow

### 자동 retrieve

1. **VOICE** — `obsidian:read 1_SNS/YouTube/_anchors/VOICE - YouTube.md`
   → Shorts/롱폼 분리 voice 룰

2. **CHANNEL_GUIDE** — `obsidian:read 1_SNS/YouTube/_anchors/CHANNEL_GUIDE - YouTube.md`
   → 외부 링크 정책, 썸네일·제목 공식, 발행 시간

3. **WINNING_PATTERNS** — `obsidian:read 1_SNS/YouTube/_anchors/WINNING_PATTERNS - YouTube.md`
   → Shorts(회고×BLUF) / 롱폼 튜토리얼·인터뷰 Top 3

4. **기존 발행 글 샘플**:
   - `YouTube - *.md` 파일 list
   - 사용자 1~3개 선택
   - 자막 패턴·인사 시그니처·챕터 구조 학습

### 대화형

5. **포맷**: "Shorts 60초 / 롱폼 10분?"
6. **글 정보**: "어떤 영상?"
7. **GENRE**: 회고 (Shorts) / 튜토리얼 (롱폼) / 인터뷰 (롱폼) 등
8. **PROJECT 연결 ❓**
9. **CORE 인용 ❓**

### 생성 (Shorts)

10. **60초 스크립트**:
    - 0~3초: 결과 선공개 (앱 화면·결과 화면 풀샷) + 자막 강한 한 줄
    - 3~10초: 본인 토킹헤드 정면 + 핵심 한 줄
    - 10~25초: B-roll + 디테일 1~2개
    - 25~40초: 두 번째 디테일
    - 40~52초: 토킹헤드 클로즈업 + 미괄식 결론
    - 52~60초: 앱 화면 + CTA 자막

11. **자막**: 한 줄 5~8 단어, 한국식 키워드 강조 (노란/빨간)

12. **친근 반말** ("~ 였어요", "~함")

### 생성 (롱폼)

10'. **8~12분 아우트라인**:
    - 0:00 후크 — 결과 화면 + "혼자 3주"
    - 0:15 약속 — "오늘 영상에서 ~ 보여드립니다"
    - 1:00 챕터 1 (3~4분)
    - 5:00 챕터 2 (3~4분)
    - 8:00 챕터 3 (선택)
    - 미괄식 결론 (1분)
    - CTA + 끝화면

11'. **정중 존댓말** ("~였습니다", "~했습니다")

12'. **인사 시그니처** ("안녕하세요, ~ 입니다")

### 공통

13. **썸네일·제목**:
    - 텍스트 3~6 단어
    - 본인 표정 + 결과 화면 split
    - 제목: 숫자+결핍+행동

14. **편집**: CapCut/DaVinci Resolve, lo-fi BGM 시리즈 고정

15. **Shorts 절단 전략**: 롱폼 1편 → Shorts 3개 절단 발행

### 저장

16. **Path**: `1_SNS/YouTube/YouTube - <title>.md`

17. **frontmatter**:
    ```yaml
    type: content
    channel: youtube
    format: shorts | longform
    project: <프로젝트명>
    blog_version: "[[Blog - <title>]]"
    status: draft
    ```

## Common Mistakes

| 실수 | 수정 |
|---|---|
| 기존 영상 안 보고 작성 | 발행 스크립트 1~3개 필수 retrieve (자막 패턴 통일) |
| Shorts에 미괄식 + 긴 설명 | retention 무너짐. 0~3초 결과 선공개 |
| 롱폼 5분 출시 영상 | 알고리즘 "Shorts에 둘 걸" 인식해 추천 약화 — 8~12분으로 |
| 자막 없이 음성만 | 음소거 시청자 이탈 |
| 본인 톤 vs 인사이트 위주 안 통일 | 토킹헤드 정면 1인칭 유지 |

## 관련 Skill

- 마스터 글: `donggu-sns:writing-blog`
- 다른 채널: `writing-linkedin`, `writing-threads`, `writing-x`, `writing-instagram`

## 태그

#sns #youtube #shorts #longform #content-writing #voice-learning
