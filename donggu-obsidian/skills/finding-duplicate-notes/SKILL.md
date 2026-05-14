---
name: finding-duplicate-notes
description: Use when auditing personal knowledge management vaults (Obsidian, PARA, LYT, Zettelkasten, second brain) for duplicate, overlapping, or near-duplicate notes — surfaces semantic duplicates, naming twins, absorbed-but-not-merged notes, snippet twins, redundant sources — before consolidation rituals or when atomicity (1 idea = 1 note) seems compromised
---

# Finding Duplicate Notes

## Overview

vault의 **atomicity 검수**. 같은 idea가 여러 노트에 분산되면 1 idea = 1 note 원칙 위반 + 인용 헷갈림 + MOC 큐레이션 약화. 5개 중복 패턴 식별 + 사용자 결정용 조치 추천.

**자동 merge X. 후보 발굴 + 조치 추천만.** 미세 차이가 의도일 수 있음 (예: snippet A/B 변형).

## When to Use

- 월 1회 consolidation 의례
- atomic 의심 노트 발견 시
- vault 노트 100+ 후 정기
- 강의 자산 정리 전 — 중복 제거 후 모듈 조립
- 다른 audit (예: `checking-vault-health`)에서 중복 신호 발견 시

## When NOT to Use

- vault 50개 미만 — 중복 가능성 낮음
- 단순 broken link 점검 — `checking-vault-health` 사용
- 단순 atomicity 검수 (1 노트만) — 별도 skill 영역

## Core Principle

**"1 idea = 1 note"** 위반 5종:
- 의미 동일 (다른 표현)
- 명명 미세 차이
- 흡수 표시 있지만 본문 살아있음
- 부품 분산 (snippet 변형)
- 외부 자료 중복 캡처

각 패턴별 다른 조치 — 일괄 처리 금지.

## 중복 패턴 5종

| 패턴 | 신호 | 조치 |
|---|---|---|
| **Semantic duplicates** | 다른 제목, 같은 핵심 주장 | merge 권장 — 하나로 통합, 다른 거 archive + alias |
| **Naming twins** | 거의 같은 제목 (예: `CORE - X` vs `CORE - X에 대하여`) | 1개 채택, 다른 거 redirect (alias frontmatter) |
| **Absorbed-not-merged** | "[[Y]]에 흡수됨" callout 있지만 별도 노트로 살아있음 | 본문 삭제, `status: archived` + alias 보존 |
| **Snippet twins** | 같은 Hook/Lesson 2+ 노트에 분산 | 1 best version 채택, 나머지 archive 또는 의도적 변형이면 보존 |
| **Source redundancy** | 같은 외부 자료 2+ SOURCE 캡처 | 합병 — 1 SOURCE에 통합, 다른 SOURCE 인용 일괄 fix |

## Workflow

1. **vault 구조 list** — `list_files_in_dir` 핵심 폴더 (CORE/Source/Snippet)
2. **CORE 제목 모음** — `list_files_in_dir`로 CORE 폴더의 파일명 list (제목 = 파일명)
3. **Semantic duplicate detection** — 모든 CORE 제목 list 검토 → 같은 idea 다른 표현 쌍 식별. 예: "AI는 도구" + "기술은 수단" → 같은 idea?
4. **Naming twin detection** — fuzzy match로 거의 같은 제목 쌍 (예: 80%+ 글자 일치)
5. **Absorbed-not-merged detection** — **두 시그널 모두 검사**:
   - (a) 본문 callout: `simple_search "흡수"` or `"통합 안내"` → 해당 노트가 archived 됐는지 확인
   - (b) frontmatter 키: `simple_search "evolves_from:"` 또는 `"superseded_by:"` → 진화 짝 관계 명시 노트 list. **이 키 있으면 이미 의도 보존 완료 = 조치 X** (false positive 방지)
6. **Snippet twin detection** — Hook/Lesson/One-liner/Proof 폴더 list → 첫 줄 sampling → 비슷한 시작 문장 쌍
7. **Source redundancy detection** — SOURCE 제목 매칭 + frontmatter URL 매칭
8. **각 발견에 조치 매핑** — 위 5 패턴 표 활용
9. **보고서 작성** — 사용자가 채택할 수 있게

## Report Format (표준)

```
# Note Duplication Audit — <vault>
점검 일자: YYYY-MM-DD · 패턴 5종 검사

## 🔄 Semantic Duplicates (N건)
1. **"X" ↔ "Y"**
   - 노트 A: [[CORE - X]]
   - 노트 B: [[CORE - Y]]
   - 진단: A 본문이 "B의 부분집합" 명시 → A 흡수 완료
   - 조치 권장: A의 frontmatter `status: archived`, 본문 삭제 (alias 보존)

## 🪞 Naming Twins (N건)
2. **"CORE - X" ↔ "CORE - X에 대하여"** (글자 일치 90%)
   - A: 12회 인용
   - B: 0회 인용 (dead)
   - 조치: B archive, A의 alias에 "X에 대하여" 추가

## 📋 Absorbed-Not-Merged (N건)
- ...

## ✂️ Snippet Twins (N건)
- ...

## 📚 Source Redundancy (N건)
- ...

## 한 줄 요약
[채택 권장 액션 1-3개]
```

## Time Budget

| vault 크기 | 점검 시간 | tool use |
|---|---|---|
| 100-300 노트 | 15-20분 | 30-50회 |
| 300-1000 노트 | 30-45분 | 60-80회 |
| 1000+ 노트 | 45-60분 | sampling 강제, layer당 표본 |

**Hard limit**: tool use 100회 또는 60분 초과 시 partial report.

## Common Mistakes

| Mistake | Fix |
|---|---|
| 자동 merge 시도 | 사용자 결정 게이트 필수. 채택 명시 후만 진행 |
| 모든 발견을 merge로 권장 | 의도적 변형 (A/B test, 청중 분기, 진화 흔적)일 수 있음. 진단 단계 추가 |
| Semantic distance 자동 계산 | skill 영역 X. 사용자 voice 검증은 본인만 가능 |
| Snippet 미세 차이를 중복 판정 | Hook의 변형은 channel·청중별 의도. 시작 5단어 같다고 중복 X |
| Absorbed 노트 일괄 archive | 본문이 alias·인용 가치 있을 수 있음. callout 확인 후만 |
| 흔한 frontmatter 값 검색 | `simple_search "status: archived"` 같은 흔한 값 토큰 폭발. 폴더+sampling 우회 |

## Red Flags — STOP

- "모든 발견을 merge로 권장" → 변형 의도 가능성 무시
- "snippet twin 일괄 삭제 권장" → 청중·채널 변형 무시
- "absorbed 노트 자동 archive" → 본인 callout 의도 무시
- tool use 100+ 넘었는데 보고서 미완성 → 즉시 중단 + partial 제출

## Example: Semantic Duplicate (atomicity 위반)

```
1. **"AI는 도구이지 판단자가 아니다" ↔ "기술은 수단이다"**
   - 노트 A: [[CORE - AI는 도구, 판단은 사람]] (작성 2026-02-02, 12회 인용)
   - 노트 B: [[CORE - 기술은 수단이다]] (작성 2025-12-31, 23회 인용)
   - A의 본문 첫 callout: "이 CORE는 [[CORE - 기술은 수단이다]]의 부분집합으로 통합되었다"
   - 진단: A 자기 진단으로 B 흡수 명시. 단 A는 status: evergreen 유지.
   - 조치 권장:
     (a) A의 `status: absorbed` 변경 + 본문 격언만 보존, 메인 본문은 B에 통합
     (b) A 파일 자체는 보존 (alias·인용 가치) — 본문만 단축
```

## Example: Snippet Twin (의도적 변형 — 보존)

```
2. **"AI가 코드의 95%를 짠다고" ↔ "AI가 코드를 짠다고 그래서 뭐"**
   - 노트 A: [[HOOK - AI가 코드의 95%를 짰다고]]
   - 노트 B: 사용된 게시물 본문 ([[LinkedIn - AI가 코드의 95%를 짠다고 그래서 뭐]])
   - 진단: A = Hook 부품 (재사용 가능), B = 특정 게시물의 그 Hook 변형
   - 조치 권장: **보존**. Hook 부품과 출고물 변형은 별개. 단지 게시물 B에 [[HOOK - ...]] 인용 추가 권장 (재사용 추적)
```

## Example: Naming Twin (정리 필요)

```
3. **"CORE - 풀스택은 직군이 아니라 책임이다" ↔ "CORE - 풀스택은 직군이 아닌 책임이다"** (글자 일치 95%)
   - A: 18회 인용, status: evergreen
   - B: 0회 인용, status: draft
   - 진단: B는 A의 초안 흔적 — 잘못 명명되어 살아남음
   - 조치 권장: B archive 또는 삭제, A에 alias "직군이 아닌 책임" 추가
```

## 조치 룰 (사용자 결정 후)

채택 시 자동 가능한 후속 작업:

- **archive**: 파일 frontmatter `status: archived` 추가 + 별도 `99_Archive/` 이동 또는 alias 보존
- **alias 추가**: frontmatter `aliases: [<old name>]` 배열 추가 → wikilink 호환성 유지
- **본문 단축**: 본문은 1-2줄 격언만 남기고 메인 link로 redirect
- **인용 일괄 fix**: 다른 노트들이 [[B]]를 인용 중이면 [[A]]로 일괄 치환 (옵시디언 앱 내장 rename 기능 또는 vault-wide find-replace)

자동 X — 사용자가 명시 채택 후 진행.

## Vault-Specific Context

PKM 시스템마다 atomicity 컨벤션 다름:

- **LYT (Linking Your Thinking)**: Atlas/POV의 atomic note 1 idea = 1 note 엄격
- **Zettelkasten**: 더 엄격 (Andy Matuschak evergreen)
- **PARA**: atomicity 룰 약함 (Projects/Areas는 컨테이너)
- **Personal Branding vault**: CORE = atomic POV, 따라서 엄격 적용

가이드 노트 (예: `_GUIDES/CONTENT_PIPELINE.md`) 먼저 read해서 atomicity 룰 확인 후 점검 시작.

## 관련 Skill

- **`checking-vault-health`**: 콘텐츠 파이프라인 흐름 점검 (입구·정제·출구·큐레이션). atomicity는 보조. 이 skill과 cross-reference.
- **`extract-core`**: 저널 → CORE 승격 의례. 이 skill 사용 후 중복 발견되면 extract-core에서 새 CORE 만들 때 기존 CORE 매칭 검사 강화.
