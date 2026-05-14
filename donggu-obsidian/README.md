# donggu-obsidian

> Obsidian PKM vault operations skill collection — part of [`donggu-skills`](../) marketplace.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](../LICENSE)
[![Skills](https://img.shields.io/badge/skills-3-green)](#-skills)
[![Compatible](https://img.shields.io/badge/PKM-LYT%20%7C%20PARA%20%7C%20Zettelkasten-blue)](#-사용-가정)

LYT / PARA / Zettelkasten 스타일 PKM vault 운영의 정기 의례 자동화. **콘텐츠 파이프라인** (저널 → CORE → Channel Pack → CASE)을 운영하는 PKM 사용자용.

---

## 📚 Skills

| Skill | 호출 | 사용 시점 | Output |
|---|---|---|---|
| **checking-vault-health** | `donggu-obsidian:checking-vault-health` | 월 1회 시스템 회고, 주말 추출 직전 | 4 layer 보고서 (P0-P4 + 긍정 신호 + 한 줄 요약) |
| **extract-core** | `donggu-obsidian:extract-core` | 주말 1회 (저널 5-7건 누적 후) | atomic claim 후보 3-5개 (점수 + 채택 권장) |
| **finding-duplicate-notes** | `donggu-obsidian:finding-duplicate-notes` | 월 1회 또는 atomic 의심 노트 발견 시 | 5 패턴 중복 발견 + 조치 추천 |

---

## 🔁 Skill Chain 흐름

```
                 ┌────────────────────────┐
                 │  checking-vault-health │  (월 1회 시스템 점검)
                 └────────────┬───────────┘
                              │
                ┌─────────────┼──────────────┐
                ▼                            ▼
       absorbed callout 발견           extracted_to: [] 5+건
                │                            │
                ▼                            ▼
   ┌───────────────────────┐    ┌────────────────────────┐
   │ finding-duplicate-    │    │     extract-core       │  (주말 추출 의례)
   │       notes           │    └───────────┬────────────┘
   └───────────────────────┘                │
                ▲                            │
                │     채택 시 기존 CORE      │
                └────────── 중복 검사 ──────┘
```

각 skill의 `## 관련 Skill` 섹션이 자동 chain 권장.

---

## 🧬 Skill 상세

### 🩺 `checking-vault-health`

PKM vault의 **콘텐츠 파이프라인 4 layer** (입구·정제·출구·큐레이션) 흐름 점검. broken link audit 아님.

**점검 카테고리 5종**:
1. 입구 단절 (저널·캡처 0건 7일+) — **P0**
2. 파이프라인 정체 (추출·인용 안 됨 1주+) — **P1**
3. 가이드 안티 패턴 (Channel Pack에 본문 직접 작성 등) — **P1**
4. broken wikilink (콤마·공백 typo) — **P2**
5. stub 적체 + MOC 임계 미달 — **P3**

**보고서 형식**: P0-P4 (발견·영향·조치 3줄) + 긍정 신호 1-3개 + 한 줄 요약.

### 💎 `extract-core`

빌드 저널의 "💎 추출 후보" 섹션을 atomic CORE로 승격하는 주말 의례.

**Atomic 평가 5 기준** (각 2점, 총 10점):
- 1 idea = 1 note (1개 아이디어만?)
- "X는 Y다" 문장형 (완성된 주장?)
- 본인 voice (객관 정리 아님?)
- 기존 CORE 중복 X (vault search)
- 시간 좌표 없음 (영구 자산?)

**채택 후 자동 작업**:
- 새 CORE 노트 생성 (`TPL - Core` 컨벤션 매칭)
- 저널 frontmatter `extracted_to: [[CORE - X]]` 자동 link

### 🔍 `finding-duplicate-notes`

vault의 1 idea = 1 note 위반 발굴. 5 패턴 audit:

| 패턴 | 신호 | 조치 |
|---|---|---|
| **Semantic duplicates** | 다른 제목, 같은 핵심 주장 | merge 권장 — 하나로 통합 + alias 보존 |
| **Naming twins** | 거의 같은 제목 (콤마·공백 차이) | 1개 채택, 다른 거 redirect |
| **Absorbed-not-merged** | "흡수됨" callout 또는 `evolves_from` frontmatter 있지만 본문 살아있음 | 의도 보존이면 OK, 아니면 archive |
| **Snippet twins** | 같은 Hook/Lesson 2+ 노트 분산 | 변형 의도면 보존, 아니면 1개 채택 |
| **Source redundancy** | 같은 외부 자료 2+ SOURCE | 합병 + 인용 일괄 fix |

**자동 merge 절대 X** — 미세 차이가 본인 의도일 수 있음 (snippet A/B 변형 등).

---

## 🎯 사용 가정

- **PKM 시스템**: LYT (Linking Your Thinking) / PARA / Zettelkasten / Second Brain
- **frontmatter `type` enum** 컨벤션 (예: `core | source | case | snippet | project | moc | foundation | journal`)
- **`extracted_to:` 또는 비슷한 추출 추적 키** 사용 (skill이 추출 자동 link)
- **본문 callout 또는 `evolves_from` frontmatter**로 노트 evolution 추적

> 다른 vault 적용 시 각 skill의 `## Vault-Specific Context` 섹션 참조하여 path/key 매핑 조정.

---

## 💡 활용 시나리오

### 주말 의례 (매주 토·일, 30-60분)

```
1. /donggu-obsidian:checking-vault-health
   → 시스템 흐름 점검, 정체 layer 식별

2. /donggu-obsidian:extract-core
   → 그 주 저널 → atomic CORE 후보 3-5개 → 1-3개 채택

3. (1 결과에 중복 신호 있으면) /donggu-obsidian:finding-duplicate-notes
   → 5 패턴 audit → 조치 추천
```

### 월간 retro (월말, 1시간)

```
1. /donggu-obsidian:checking-vault-health   (전월 vault 진화 확인)
2. /donggu-obsidian:finding-duplicate-notes (월 1회 중복 audit)
3. (skill 결과 기반) Pattern 발굴·MOC 보강·강의 자산 정리
```

### 분기 (강의·B2B 자산 정리 직전)

```
1. /donggu-obsidian:finding-duplicate-notes  (중복 정리 → 모듈 조립 가능)
2. (사용자 직접) 누적된 CORE/Foundation/Case로 Teaching Module 조립
```

---

## 🔗 관련

- [donggu-skills marketplace](../) — 본 plugin 부모
- [Claude Code Plugin Spec](https://claude.com/claude-code) — plugin/marketplace 작동 방식
- [superpowers:writing-skills](https://github.com/obra/superpowers) — skill 작성 가이드 (RED-GREEN-REFACTOR)

---

## 📜 License

[MIT](../LICENSE) © 2026 강동현 (donggu)
