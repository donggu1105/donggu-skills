---
name: extract-core
description: Use when running weekend extraction rituals on personal knowledge management vaults (Obsidian, PARA, LYT, Zettelkasten) — surfaces atomic claim candidates from build journals' "extracted candidate" sections, evaluates atomicity, scores top 3-5 for promotion to atomic permanent notes (CORE), and triggers automated extraction tracking via frontmatter linking
---

# Extract Core

## Overview

저널의 "💎 추출 후보" → atomic 평가 → CORE 승격 후보 추천. **승격 자동화 X, 추천만**. 사용자가 채택 결정 → skill이 CORE 노트 생성 + 저널의 `extracted_to:` 자동 link.

## When to Use

- 주말 1회 정기 추출 의례 (30-60분)
- 저널 5+개 누적 후
- LinkedIn 데일리 글감 부족 시 — 누적된 후보 발굴
- 강의 자산 누적 시점 — CORE를 Pattern으로 진화 후보 식별

## When NOT to Use

- 저널 0-2개 — 데이터 부족
- 글 마감 직전 — 추출은 정제 단계, 출고 직전 X
- atomic 의심 노트 검수 — 별도 skill 영역

## Core Principle

**추출은 평가 + 추천. 자동 채택 X.** 본인 voice 검증·atomicity 평가는 사람만 가능. skill은 후보 정제 + 점수화 + 메타데이터 자동화.

## Atomic 평가 5 기준

각 후보를 5개 기준으로 평가 → 점수 합산 (10점 만점):

| 기준 | 만점 | 검사 질문 |
|---|---|---|
| **1 idea = 1 note** | 2 | 후보 안에 2개 이상 아이디어 섞임? |
| **"X는 Y다" 문장형** | 2 | 완성된 문장으로 표현 가능? ("AI 어려움" X, "AI는 도구이지 판단자가 아니다" ✅) |
| **본인 voice** | 2 | 객관 사실 정리 아니라 본인 의견·해석인가? |
| **기존 CORE 중복 X** | 2 | 비슷한 CORE 이미 있나? (vault search 필요) |
| **시간 좌표 없음** | 2 | "이번 주 ..." 같은 시점 종속 표현 없는가? |

**총점 8+ → 채택 권장 / 5-7 → 보류 (재검토) / 4 이하 → 폐기 또는 다른 형태로**

## Workflow

1. **저널 list** — `obsidian_list_files_in_dir "70_Projects/<프로젝트>/journal/"` (또는 전체 프로젝트 sweep)
2. **기간 필터** — frontmatter `date` 또는 파일명 YYYY-MM-DD로 시간 범위 좁힘 (default: 지난 7일)
3. **추출 후보 발췌** — 각 저널의 "## 💎 추출 후보" 섹션만 `obsidian_get_file_contents`로 읽기
4. **통합 list** — 모든 후보 한 곳에 모음 (저널 출처 보존)
5. **atomic 평가** — 각 후보 5 기준 점수화
6. **기존 CORE 중복 검사** — `obsidian_simple_search "CORE - <키워드>"` 으로 중복 후보 식별
7. **추천 분류** — 채택(8+)/보류(5-7)/폐기(4-)
8. **사용자에게 결정 요청** — 명시적 채택 받기 ("1, 3번 채택")
9. **CORE 노트 자동 생성** — 채택된 후보별:
   - `obsidian_append_content` filepath: `20_Core/CORE - <문장>.md`
   - frontmatter: `type: core`, `title`, `topics`, `audience`, `tone`, `status: draft`, `created`
   - 본문: `## 💡 핵심 주장` callout + 출처 link
10. **저널 `extracted_to:` 업데이트** — 채택된 후보의 출처 저널 frontmatter에 `[[CORE - X]]` 자동 추가

## Report Format

```
# 추출 의례 — <기간>
저널 N개 검토 · 후보 M개 식별

## ⭐ 채택 권장 (점수 8+)
1. **"X는 Y다"** — 점수 9/10
   - 출처: [[2026-05-13]] 후보 1
   - 평가: atomic 강함, 본인 voice OK, 기존 CORE 중복 없음
   - 승격 시 → `CORE - X는 Y다.md` 신규

2. ...

## 🟡 보류 (점수 5-7)
3. **"..."** — 점수 6/10
   - 출처: ...
   - 부족: 너무 넓음 ("Y가 정확히 뭔지" 구체화 필요)
   - 권장: 다음 주 재검토 또는 split

## ❌ 폐기 (점수 4 이하)
4. **"..."** — 점수 3/10
   - 부족: 본인 voice 아니라 외부 자료 정리 (SOURCE로 옮기기)

## 📊 메타
- 검토 저널: N개
- 후보 총: M개
- 채택 권장: K개 (1주 적정치 2-3개)
- 평균 atomic 점수: X/10
```

## Common Mistakes

| Mistake | Fix |
|---|---|
| 한 주에 5+ 채택 권장 | atomicity 평준화. 평균 2-3개 적정. 너무 많이 권장하면 점수 기준 재검토 |
| 기존 CORE 중복 검사 빼먹음 | 채택 전 vault search 필수 — 비슷한 CORE 있으면 보류·통합 권장 |
| "보류" 카테고리 안 쓰고 채택/폐기 binary | 보류 = 다음 주 재검토 의미. atomicity 부족하지만 가치 있는 후보 보존 |
| 본인 voice 검증 빼먹음 | "이게 본인 표현인가, 외부 자료 정리인가" 매 후보 검수 |
| 채택 자동 진행 | 사용자 명시적 채택 결정 받기. 자동 승격 X |
| 저널 `extracted_to:` 업데이트 빠뜨림 | 채택 후 즉시 출처 저널 frontmatter 업데이트 — 추적 가능성 핵심 |

## Time Budget

| 저널 수 | 검토 시간 | 우선순위 |
|---|---|---|
| 3-7개 | 20-30분 | 모든 저널의 "💎 추출 후보" 전부 |
| 8-15개 | 30-45분 | 후보 풍부한 저널 우선 (3+ 후보 있는 것) |
| 15+개 | sampling 강제 | 가장 최근 7개 또는 사용자 명시 프로젝트 |

## Red Flags

- 저널의 "💎 추출 후보" 섹션 빈 칸만 있음 → 저널 작성 룰 위반 (다듬으려 하지 말고 raw 톤). 사용자 알림 후 추출 중단
- 모든 후보 점수 < 5 → 저널이 빌드 활동 X 일기·잡담. 사용자 알림
- 채택 권장이 1주에 5+ → 점수 기준 너무 후함. 재검토
- 같은 atomic claim이 2 저널에 중복 → 통합 안내, 하나만 채택

## Example: 채택 권장 (점수 9)

```
1. **"AI는 도구이지 판단자가 아니다"** — 점수 9/10
   - 출처: [[2026-05-13]] 후보 1 ("AI가 코드 95% 짜도 검증은 사람")
   - 평가:
     ✅ 1 idea (도구 vs 판단자 단일 대비)
     ✅ "X는 Y다" 완성형
     ✅ 본인 voice (외부 자료 인용 아닌 주장)
     ⚠️ 중복: [[CORE - AI는 도구, 판단은 사람]] 이미 존재 — 동일 본질. **보류 권장으로 격하**
     ✅ 시간 좌표 없음
   - 권장 조치: 기존 CORE에 흡수, 출처 저널의 `extracted_to:` 만 업데이트
```

## Example: 폐기 (점수 3)

```
2. **"AI 협업 도구가 빠르게 발전 중"** — 점수 3/10
   - 출처: [[2026-05-12]] 후보 1
   - 평가:
     ❌ 객관 사실 (본인 voice X)
     ❌ "X는 Y다" 형태 약함
     ❌ 시간 좌표 ("빠르게 발전 중" = 현재 시점 종속)
   - 권장: SOURCE 노트 형태로 옮기거나 폐기
```

## CORE 생성 시 자동 frontmatter

채택 시 자동 생성되는 CORE 노트의 frontmatter (`TPL - Core` 컨벤션 매칭):

```yaml
---
type: core
title: <Y의 완성 문장>
topics:
  - <추론 또는 사용자 입력>
channels: [linkedin, blog, teaching]
audience: [dev, pm, non-dev-product-builder]
tone: direct
status: draft
created: YYYY-MM-DD (오늘 날짜)
source_journal: "[[저널 파일]]"
---

# CORE - <Y의 완성 문장>

## 💡 핵심 주장
> **"<핵심 문장 한 줄>"**

(저널 출처에서 추출된 컨텍스트 1-2 문장)

## 🤔 왜 이게 중요한가?
- (사용자가 채움)

## 🎯 실제 적용 예시
- (사용자가 채움)

## 📂 연결된 콘텐츠

### 출처 저널
- [[<저널 파일>]]

### 관련 CORE
- (자동 추천 또는 사용자가 채움)

## 태그
#core #<topic>
```

## 저널 frontmatter 업데이트

CORE 채택 시 저널의 frontmatter `extracted_to:` 배열에 `[[CORE - X]]` 추가:

```yaml
# Before
extracted_to: []

# After
extracted_to:
  - "[[CORE - AI는 도구이지 판단자가 아니다]]"
```

이 트래킹이 후일 retrospective에서 "어느 저널이 가장 많은 CORE를 낳았나" 분석 가능.

## Vault-Specific Context

각 vault의 컨벤션 다름. 저널 경로·CORE 폴더·frontmatter 키는 사용자 vault 가이드 (예: `_GUIDES/CONTENT_PIPELINE.md`) 먼저 확인 후 매핑:

- **LYT (Linking Your Thinking)**: 저널 → `Atlas/02-POV/`로 승격
- **Personal Branding vault**: 저널 → `20_Core/CORE - X.md`
- **PARA**: 저널 → `Resources/Permanent Notes/`
- **Zettelkasten**: Fleeting Notes → Permanent Notes

CORE 노트 제목 컨벤션도 vault마다 다름 — 단순히 "Y의 문장" 또는 "TYPE - 문장" 형식 결정 후 진행.
