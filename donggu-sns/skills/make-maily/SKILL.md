---
name: make-maily
description: Use when writing or formatting a Maily (maily.so) newsletter note in the Obsidian vault — defines the note structure (title/subtitle/tags/body), the markdown subset that converts cleanly to Maily's native Editor.js blocks (headers, quotes, lists, dividers), and the publish webhook contract. Ensures the email renders pretty in Maily without manual editor work.
---

# Make Maily Newsletter

## Overview

메일리(maily.so) 뉴스레터를 **옵시디언 노트만으로 완성**하기 위한 형식 규격.
발행기가 메일리 에디터의 **Markdown 도구(Ctrl+⇧+M)**로 본문을 네이티브 블록에
변환하므로, 아래 마크다운 부분집합으로 쓰면 에디터에서 손볼 필요 없이 이쁘게 나온다.
(2026-06-12 라이브 검증)

## When to Use

- vault `Personal Branding/50_Channel_Packs/1_SNS/Maily/`에 뉴스레터 노트 작성
- 기존 Maily 노트를 발행 가능한 형식으로 정형화
- voice·톤은 `donggu-sns:writing-blog` 등 채널 voice 스킬과 조합해 쓴다 — 이 스킬은 **형식** 담당

## 노트 구조 (`## 발행` 섹션)

```
1행: 메일 제목 (이메일 제목 필드로 전달)
2행: 부제목 — 이메일 내용 미리보기 영역. 받은편지함에서 제목 아래 보이는 한 줄.
     ⚠️ 빼먹지 말 것: 비우면 본문 첫 문장이 잘려 나감. 후킹 한 줄로.
(빈 줄)
본문 (아래 마크다운 부분집합)
```

frontmatter: `channel: maily`, `status: draft`, 브랜드 태그 6종 + 메일리 태그는
발행 시 `tags` 배열로 전달 (에디터의 "태그 (쉼표로 구분)" 필드에 입력됨).

## 본문 마크다운 → 메일리 블록 매핑 (변환 검증됨)

| 마크다운 | 메일리 블록 | 비고 |
|---|---|---|
| 일반 문단 (빈 줄 구분) | 텍스트 | |
| `### 소제목` | 제목(헤더) | 섹션 구분 기본. h3 권장 |
| `**볼드**` | 텍스트 강조 | 인라인 |
| `[라벨](url)` / 맨 URL | 링크 | |
| `> 인용` | 인용 블록 | 핵심 문장·"오늘 한 가지만" 분리에 |
| `1. 항목` | 번호 목록 | |
| `- 항목` | 불릿 목록 | |
| `---` | 가로줄 | 섹션 전환(인사→본문→맺음) |

**에디터 전용(마크다운 불가, 필요 시 발행 후 수동)**: 버튼, 이미지, 테이블, 칼럼/글 박스,
코드 하이라이트, 위젯. — 글에 꼭 필요하면 dry_run 초안 만들고 에디터에서 추가 후 발행.

## 편지 프레임 (구조 권장)

```
안녕하세요, 동구입니다.        ← 인사
(훅/이번 편지 소개 1~2문단)
---
### 본문 소제목 1~3개          ← 섹션당 2~3문단, 핵심은 > 인용 또는 **볼드**
---
### 오늘 한 가지만             ← 실천 한 줄
(답장 유도 문장)
동구 드림                      ← 맺음
```

## 발행

발행 파이프라인(웹훅 주소·인증·페이로드)은 **개인 인프라 문서**를 따른다 — 공개 스킬에는
싣지 않는다. 노트가 위 형식(1행 제목·2행 부제목·마크다운 본문)이면 발행기가 제목→부제목→
태그 입력 후 Markdown 도구로 본문을 블록 변환해 올린다.

- 초안 저장(dry run)으로 먼저 확인 → **실발송은 취소 불가**이므로 반드시 미리보기 컨펌 후.

## 함정

- 부제목 누락 = 받은편지함 미리보기에 본문 첫 줄이 그대로 노출 (제일 흔한 실수)
- `####` 이하 레벨·중첩 인용·중첩 목록은 미검증 — `###`/단일 레벨만 사용
- 이미지가 필요한 편지는 dry_run → 에디터에서 이미지 블록 추가 → 발행 순서로
