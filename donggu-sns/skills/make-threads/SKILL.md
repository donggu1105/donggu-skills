---
name: make-threads
description: Use when writing or formatting a Threads post note in the Obsidian vault for automated publishing — defines the note structure (frontmatter, `## 발행` section, image embeds) that the publisher extracts mechanically, plus the 500-char/single-hashtag/no-link constraints of the Threads channel. Ensures the note publishes as-is without manual cleanup.
---

# Make Threads Note

## Overview

Threads 게시물을 **옵시디언 노트만으로 발행 가능하게** 만드는 형식 규격.
발행기는 노트의 **`## 발행` 섹션 하나만** 기계적으로 집어간다 — 섹션 안 텍스트가
본문 그대로, 섹션 안 `![[이미지]]` 임베드가 첨부 이미지 그대로 나간다.

**핵심: `## 발행` 안에 쓴 것 = Threads에 올라가는 것. 그 밖은 전부 무시된다.**

## When to Use

- vault `Personal Branding/50_Channel_Packs/1_SNS/Threads/`에 Threads 노트 작성
- 기존 Threads 노트를 자동 발행 가능한 형식으로 정형화
- voice·톤·후크는 `donggu-sns:writing-threads`가 담당 — 이 스킬은 **형식** 담당

## 노트 구조

```
경로: 1_SNS/Threads/Threads - <토픽>.md

frontmatter:
  type: content
  channel: threads
  status: draft          # 발행 후 published
  tags: 브랜드 태그(동구 필수 + 해당 브랜드) + 채널/Threads   # 표준 그대로, 키 발명 금지

## 발행                  ← 발행기가 읽는 유일한 섹션
(본문 텍스트 그대로 — 마크다운 장식 없이)
![[이미지1.png]]         ← 첨부할 때만, 본문 텍스트 아래에
![[이미지2.png]]

## 발행 전략 / ## 연결 / 기타 섹션   ← 자유 (발행기 무시)
```

## `## 발행` 섹션 규칙

| 규칙 | 이유 |
|---|---|
| 본문을 `>` 인용블록으로 감싸지 말 것 | `>`까지 그대로 발행됨. 섹션 안 = 최종본 |
| 변형(옵션 A/B) 금지 — 확정본 하나만 | 비교·시안은 섹션 밖에 두면 됨 |
| **500자 한도** (이미지 임베드 줄 제외하고 세기) | 초과 시 발행 실패. 작성 후 글자수 확인 |
| 해시태그는 **본문 마지막 줄 1개만** (예: `#바이브코딩`) | Threads는 1개=토픽 태그, 남발=스팸 처리 |
| 외부 링크 본문 금지 → "첫 댓글" 운영 메모는 섹션 밖에 | 본문 링크는 도달 페널티 |
| 끝은 답글 유도 — 질문("어떻게 생각함?") 또는 미완 끝맺음("↓", "...") | reply 1개 = 도달 폭발 채널 |
| 이미지: 0장=텍스트, 1장=단일 이미지, 2장 이상=캐러셀 (임베드 순서 = 게시 순서) | 발행기가 장수로 모드 자동 판별 |
| 이미지 비율 4:5 세로형 권장 | 1:1 비권장 (채널 가이드) |

## 함정

- **임의 섹션명(`## 본문`, `## 이미지` 등) 발명 = 발행 안 됨.** 발행기는 `## 발행`만 찾는다.
  이미지도 별도 섹션이 아니라 `## 발행` 안에 임베드.
- **frontmatter 키 발명 금지** (`brand:`, `title:` 등) — 제목은 파일명, 브랜드는 표준 `tags:`로.
- 톤이 정중 존댓말로 흐르면 `writing-threads`의 VOICE 앵커부터 다시 — 이 스킬은 형식만 맞춘다.
- 타래(연속 답글)는 자동 발행 미지원 — 타래 초안은 섹션 밖에 두고 수동 발행.

## 발행

발행 파이프라인(웹훅 주소·인증·페이로드)은 **개인 인프라 문서**를 따른다 — 공개 스킬에는
싣지 않는다. 노트가 위 규격이면 발행기가 `## 발행` 섹션에서 본문·이미지를 추출해 올린다.

- **발행 전 본문 미리보기 + 명시 승인 필수.** 게시 5분 내 수정도 금지(알고리즘 점수 리셋).

## 관련 Skill

- voice·후크·구조: `donggu-sns:writing-threads`
- 다른 채널 형식: `make-maily`, `make-insta-card-news`
