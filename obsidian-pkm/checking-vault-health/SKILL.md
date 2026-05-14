---
name: checking-vault-health
description: Use when running periodic health checks on personal knowledge management vaults (Obsidian, PARA, LYT, Zettelkasten, second brain) to surface pipeline blockages, guide violations, broken wikilinks, stale stubs, MOC threshold gaps, and uncited sources before weekly recovery rituals
---

# Checking Vault Health

## Overview

PKM vault의 **콘텐츠 파이프라인 어디가 막혔는지** 식별하는 정기 점검. broken link audit 아님. 입구(캡처) → 정제(추출·승격) → 출구(조립·출고) → 큐레이션(MOC) 4 layer 각각이 다음 단계로 흐르는지가 health metric.

## When to Use

- 주말 추출 의례 직전 — 묵은 저널·인용 안 된 SOURCE 식별
- 월 1회 시스템 회고 — 정체된 layer 발견
- 새 콘텐츠 도메인 추가 전 — vault 정합성 확인
- vault 노트 100+ 후 정기 점검 (300+면 sampling 강제)

## When NOT to Use

- vault 노트 50개 미만 — 시스템 자체가 미성숙, 점검 의미 없음
- 단순 broken link 찾기 — `obsidian_simple_search`로 충분
- vault 구조 처음 설계 — 다른 skill 영역

## Core Principle

**4 layer 매핑**으로 본다. 단순 발견 list ≠ health check.

```
입구 (캡처)        → 정제 (추출·승격)   → 출구 (조립·출고)   → 큐레이션 (MOC)
저널·Source       → CORE·Pattern      → Channel Pack       → MOC + cross-link
신규 7일 0건?      → extracted_to 0?   → 가이드 위반?       → 5+ topic MOC 없음?
```

각 layer가 다음으로 *흐르는지*가 측정 대상. 단계 별 정체 = 시스템 망함의 가장 큰 signal.

## Workflow (8 step, 사정에 따라 sampling)

1. **vault 구조 list** — `list_files_in_vault` + 핵심 폴더 4-5개 `list_files_in_dir`
2. **입구 점검** — **first check: 저널 sub-folder 존재 자체를 확인** (`list_files_in_dir`로 `70_Projects/<프로젝트>/journal/` 같은 경로). 폴더가 없으면 즉시 P0 (`simple_search "type: journal"`만으론 템플릿 hit에 가려져 놓침). 폴더 있으면 7일 이내 신규 노트 count
3. **정제 점검** — `simple_search` "extracted_to: \[\]" 으로 추출 안 된 저널 list. SOURCE 중 1주+ 인용 0건 식별
4. **가이드 위반** — frontmatter `type` enum 위반, 안티 패턴 (예: "Channel Pack에 본문 직접 작성")
5. **링크 무결성** — broken wikilink, 특히 콤마·공백 typo 패턴 (예: `[[CORE - X 판단은 사람]]` vs `[[CORE - X, 판단은 사람]]`)
6. **stub 적체** — `status: draft` 또는 `status: stub` + `created < (today - 2 weeks)`
7. **MOC 임계** — 같은 topic 5+ 노트인데 MOC 없는 경우 (Nick Milo 룰)
8. **긍정 신호 1-3개** — 균형 위해 잘 작동하는 면 식별

## Report Format (표준)

```
# Vault Health — <vault-name>
점검 일자: YYYY-MM-DD · 범위: 폴더 N개, 노트 M개 표본

## P0 — [Layer]: [구체 문제]
**발견**: ...
**영향**: 시스템 [어떤 흐름]이 막힘
**조치**: [구체 명령 또는 다음 행동]

## P1 — ...
## P2 — ...
...

## 긍정 신호 (보존)
- ...

## 한 줄 요약
[우선순위 1-3개 액션 명령]
```

P 우선순위:
- **P0**: 시스템 입구 단절 (저널·캡처 0건 7일+)
- **P1**: 파이프라인 정체 (추출·인용 안 됨 1주+) + 가이드 안티 패턴 위반
- **P2**: broken wikilink (다수 발견)
- **P3**: stub 적체 + MOC 임계 도달
- **P4**: 명명·frontmatter 일관성

## Time Budget

| vault 크기 | 점검 시간 | tool use | sampling |
|---|---|---|---|
| 100-300 노트 | 10-15분 | 30-50회 | 핵심 폴더 list + 표본 노트 5-10 |
| 300+ 노트 | 20-30분 | 60-80회 | 폴더별 representative sample 강제 |
| 1000+ 노트 | 30-45분 | 80-100회 | layer당 1개 폴더만 deep, 나머지 metadata만 |

**Hard limit**: tool use 100회 또는 30분 초과 시 중단 + partial report.

## Common Mistakes

| Mistake | Fix |
|---|---|
| 보고서가 *발견*만 있고 *조치* 없음 | 매 P마다 "조치: 구체 명령" 필수 |
| 입구 (저널/캡처) 빼고 출구 (broken link)만 봄 | 4 layer 매핑 룰 강제, layer 별 최소 1 항목 |
| 균형 없이 부정 발견만 list | "긍정 신호" 섹션 1-3개 강제 |
| 전체 vault 다 읽음 | sampling 룰 위반. 100+ 면 sampling 강제 |
| 같은 frontmatter 키 50번 읽음 | metadata batch retrieval 또는 search 활용 |
| 흔한 frontmatter 값을 직접 검색 | `simple_search "status: draft"` 같은 흔한 값은 100k+ 토큰 결과 폭발. **enum 값 + 폴더 한정** (예: `obsidian_list_files_in_dir "20_Core"` 후 batch_get_file_contents로 sampling) |
| 보고서 5000자 넘음 | 한 P당 5줄 이내, 한 줄 요약은 1줄 |

## Red Flags — STOP and Restart

- "전체 vault 다 읽었다" → sampling 룰 위반, 시간 budget 초과
- "broken link만 점검했다" → 4 layer 매핑 빠짐
- "조치 명령 없다" → P 우선순위 무의미
- "긍정 신호 안 적었다" → 사용자 균형 감각 X
- tool use 100회 넘었는데 보고서 미완성 → 즉시 중단 + partial 제출

## Example: 입구 단절 (P0)

```
## P0 — 입구 단절: Build Journal 0건

**발견**: `70_Projects/*/journal/` 조회 → 결과 0건. 7일 이내 신규 저널 0.
**영향**: 시스템 입구가 막혀 CORE 승격·LinkedIn 데일리 원료 파이프라인 작동 안 함.
**조치**: 진행 중인 프로젝트 1개 골라 `70_Projects/<프로젝트>/journal/YYYY-MM-DD.md` 생성. TPL - Build Journal 적용. 매일 저녁 5-15분 룰 시작.
```

## Example: 정제 정체 (P1)

```
## P1 — 정제 정체: 추출 안 된 저널 5건

**발견**: `simple_search "extracted_to: []"` 결과 5건 (모두 1주+ 묵음).
**영향**: 저널의 atomic insight가 CORE로 승격 안 됨 → 강의 자산 누적 0.
**조치**: 주말 추출 의례 진행. 각 저널의 "💎 추출 후보" 섹션만 훑기 → 1-3개 CORE 신규. /extract-core 스킬 활용.
```

## Vault-Specific Context

PKM 시스템마다 layer 매핑 다름. skill은 framework, 매핑은 사용자 vault에 따라:

- **LYT (Linking Your Thinking)**: Inbox → Atlas/POV → MOC → Channel Pack
- **PARA**: Projects → Areas → Resources → Archive (정체성 다름)
- **Zettelkasten**: Fleeting → Literature → Permanent → Drafts
- **Second Brain (CODE)**: Capture → Organize → Distill → Express

각 vault의 가이드 노트 (예: `_GUIDES/CONTENT_PIPELINE.md`) 또는 CLAUDE.md 먼저 read해서 layer mapping 확정 후 점검 시작.

## 관련 Skill (자동 Chain)

vault health 점검 중 다음 신호 발견 시 **별도 skill을 즉시 chain 호출** 권장 — 동일 task에서 자연스럽게 다음 단계로 흐름:

| 발견 신호 | Chain 대상 | 이유 |
|---|---|---|
| Semantic duplicates, naming twins, absorbed-not-merged callout 발견 | **`finding-duplicate-notes`** | atomicity 점검은 별도 영역. 5 중복 패턴 풀 audit. |
| `extracted_to: []` 저널 5건+, 추출 안 됨 1주+ | **`extract-core`** | 주말 추출 의례. 저널 → CORE 승격 의례 트리거. |
| 5+ topic 같은데 MOC 없음 | (사용자 직접) | MOC 생성은 hand-curation 영역, skill 영역 X. |

**Chain 룰**:
- vault health 보고서에 발견 항목 명시 후, "이 발견은 `finding-duplicate-notes` skill로 확장 audit 권장" 같은 명시 안내
- 사용자가 동의하면 즉시 chain 호출 (subagent 또는 직접 실행)
- 일괄 자동 chain X — 사용자 결정 게이트 유지

**Cross-reference 룰 (writing-skills 가이드 따름)**:
- `**REQUIRED SUB-SKILL:**` X — 둘 다 필수 아님
- `**Chain 권장:**` O — 사용자 결정 후 호출
