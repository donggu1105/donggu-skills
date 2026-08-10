# donggu-skills

> Personal Claude Code skill marketplace by **강동현** ([@donggu1105](https://github.com/donggu1105))

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
[![Claude Code](https://img.shields.io/badge/Claude%20Code-Plugin%20Marketplace-8B5CF6)](https://claude.com/claude-code)
[![Plugins](https://img.shields.io/badge/plugins-5-blue)](#-plugins)
[![Skills](https://img.shields.io/badge/skills-13-green)](#-plugins)

Domain-organized monorepo. 각 도메인이 별도 plugin namespace로 등록되어 `donggu-<domain>:<skill>` 형식으로 호출.

> **Why this exists**: 실제 운영 경계를 이해하는 domain-native skill과 runtime을 한 저장소에서 관리한다. Obsidian은 범용 PKM 의례가 아니라 ontology Vault의 Personal Branding, FDE Projects, Life OS 책임을 구분한다.

---

## 📑 Table of Contents

- [🧩 Plugins](#-plugins)
- [🚀 Quick Start](#-quick-start)
- [🔄 Update](#-update)
- [📐 Repo Structure](#-repo-structure)
- [🛠️ Skill 작성 원칙](#️-skill-작성-원칙)
- [🗺️ Roadmap](#️-roadmap)
- [🤝 Contributing](#-contributing)

---

## 🧩 Plugins

### 📚 `donggu-obsidian` — Ontology-aware Vault operations

사용자-facing 진입점은 두 개입니다. `ontology`가 읽기·큐레이션·제한 점검·후보별 diff를 통합하고, `life-os`는 Daily와 Capture의 native 기록만 담당합니다.

| Skill | 호출 | 용도 |
|---|---|---|
| `ontology` | `donggu-obsidian:ontology` | Personal Branding / FDE Projects / Life OS 라우팅, `선택 → 추출 → 통합`, 후보별 preview와 승인 적용 |
| `life-os` | `/donggu-obsidian:life-os` | Daily 대화 체크인, Capture, 첨부 기록, 구조화된 AI 정리 |

CORE 적용의 hash·journal·rollback은 plugin native runtime이 소유하며 별도 prompt skill로 노출하지 않습니다. 전체 Vault daily scan과 정상 상태 알림도 기본 운영에서 제외합니다.

---

### 🎬 `donggu-docs` — Document & deck authoring

강의·세미나·워크샵·런칭 발표용 **단일 HTML 덱** 빌드 시스템. 22개 잠긴 레이아웃(S01~S22) + 4개 컬러 테마 + 정규식 검증기 기반으로 매번 같은 톤이 자동 보장. 원본은 [bytonylee/future-slide-skill](https://github.com/bytonylee/future-slide-skill)의 `tightened-slide`, 본 plugin은 강의 톤으로 재작성한 donggu 버전 (Apache-2.0 → MIT derivative).

| Skill | 호출 | 용도 | Time budget |
|---|---|---|---|
| `make-ppt-slide` | `donggu-docs:make-ppt-slide` | 강의·세미나·워크샵 단일 HTML 덱 빌드 (`index.html` + `images/`) | 30-90분 |

**자연어 트리거 예시**:
- "강의 덱 만들어줘"
- "세미나용 8페이지 한국어 발표 자료 만들어줘"
- "PPT 대신 HTML 슬라이드로 빌드해줘"

---

## 🚀 Quick Start

### 1️⃣ Marketplace 추가

**Claude Code 안에서** (권장):
```
/plugin marketplace add donggu1105/donggu-skills
```

**CLI에서**:
```bash
claude plugin marketplace add donggu1105/donggu-skills
```

### 2️⃣ Plugin install

```
/plugin install donggu-obsidian@donggu-skills
```

또는:
```bash
claude plugin install donggu-obsidian@donggu-skills
```

### 3️⃣ 첫 호출

```
/donggu-obsidian:ontology
/donggu-obsidian:life-os
```

또는 자연어 트리거:
- "이 글에서 다시 쓸 CORE가 있는지 보여줘"
- "FDE 프로젝트 노트 중복을 범위 안에서 점검해줘"
- 실행 가능한 preview의 exact trigger: "수정안 보여줘"

---

## 🔄 Update

```bash
claude plugin marketplace update donggu-skills
```

→ git pull 등가. 다음 skill 호출부터 새 내용 자동 적용.

특정 plugin 제거:
```bash
claude plugin disable donggu-obsidian
# 또는 영구 제거:
claude plugin uninstall donggu-obsidian@donggu-skills
```

---

## 📐 Repo Structure

```
donggu-skills/                       ← marketplace repo
├── .claude-plugin/
│   └── marketplace.json             ← plugins 카탈로그
├── donggu-obsidian/                 ← plugin (namespace: donggu-obsidian:)
│   ├── .claude-plugin/
│   │   └── plugin.json              ← plugin 메타
│   ├── skills/
│   │   ├── ontology/
│   │   │   ├── SKILL.md
│   │   │   └── references/
│   │   ├── core-review-approval/    ← internal helper scripts, no SKILL.md
│   │   └── life-os/
│   │       ├── SKILL.md
│   │       └── scripts/life-os.py
│   ├── runtime/                     ← CORE transaction + Life OS runtime
│   └── README.md
├── donggu-docs/                     ← plugin (namespace: donggu-docs:)
│   ├── .claude-plugin/
│   │   └── plugin.json
│   ├── skills/
│   │   └── make-ppt-slide/
│   │       ├── SKILL.md
│   │       ├── assets/              ← template.html, motion.min.js
│   │       ├── references/          ← layouts, layout-lock, themes, checklist, image-prompts, map-component
│   │       └── scripts/             ← validate-deck.mjs
│   └── README.md
├── README.md                        ← 본 파일
└── LICENSE
```

**파일 역할**:
- `marketplace.json` — 이 repo의 모든 plugin을 entry로 정의. 새 도메인 plugin 추가 시 `plugins` array 확장.
- `plugin.json` — 각 plugin의 namespace + 메타. `name` 필드가 호출 시 prefix.
- `SKILL.md` — 각 skill의 frontmatter(`name`, `description`) + 본문(workflow, examples).

---

## 🛠️ Skill 작성 원칙

본 marketplace의 모든 skill은 [superpowers:writing-skills](https://github.com/obra/superpowers) 가이드 준수:

| 원칙 | 적용 |
|---|---|
| **TDD 기반** | RED (baseline subagent) → GREEN (skill 작성) → REFACTOR (loophole 잠그기) |
| **Authority first** | root `AGENTS.md`와 영역 규칙을 읽고 실제 운영 경계에 맞춤 |
| **사용자 결정 게이트** | 후보 하나의 실제 diff → 별도 `적용해줘` → read-back |
| **Progressive disclosure** | umbrella `SKILL.md`는 짧게, 세부 절차는 필요할 때 reference 로드 |
| **Runtime separation** | 결정적 hash·journal·rollback은 prompt가 아니라 코드와 테스트가 소유 |

---

## 🗺️ Roadmap

| Plugin | Status | Skills | Description |
|---|---|---|---|
| **donggu-obsidian** | ✅ `v2.1.0` | 2 | Ontology-aware Vault operations and recoverable Life OS AI summaries |
| **donggu-docs** | ✅ `v1.0.0` | 1 | Document & deck authoring (tightened HTML slide decks) |
| 🔲 donggu-marketing | planned | — | 콘텐츠 전략·카피·소셜 콘텐츠 |
| 🔲 donggu-dev | planned | — | 코드 리뷰·아키텍처 패턴·디버깅 의례 |
| 🔲 donggu-ax | planned | — | AI 도입·AX 컨설팅·임원 자료 |
| 🔲 donggu-content-pipeline | planned | — | 콘텐츠 출고 파이프라인 (Channel Pack 조립·CASE 발굴) |

### 새 plugin 추가 절차

1. `donggu-<domain>/.claude-plugin/plugin.json` 작성 (name: `donggu-<domain>`)
2. `donggu-<domain>/skills/<skill-name>/SKILL.md` 작성
3. root `.claude-plugin/marketplace.json`의 `plugins` array에 entry 추가
4. `git push`
5. 사용자가 `claude plugin marketplace update donggu-skills` 후 `claude plugin install donggu-<domain>@donggu-skills`

---

## 🤝 Contributing

이 marketplace는 personal collection이지만 issue/PR 환영:

- **Bug report**: skill 사용 중 잘못된 동작 → [Issues](https://github.com/donggu1105/donggu-skills/issues)
- **Feature request**: 새 skill 아이디어 또는 기존 skill 개선
- **Vault convention 차이**: 본인 PKM 시스템 (PARA·Zettelkasten 등) 적용 시 매핑 어려움 보고

기여 가이드:
1. Fork → branch → SKILL.md 수정 또는 신규 skill 추가
2. **RED test 명시** (PR description에 baseline subagent 결과 첨부)
3. **broadly applicable 검수** — 특정 vault convention 하드코딩 X
4. PR

---

## 👤 Author

**강동현 (donggu)** · AI Product Engineer

코드 짤 줄 아는 AX 전략가, 조직 이해하는 LLM 개발자. (C)트랙 LLM 개발과 (D)트랙 AX 전략의 다리 포지셔닝.

- GitHub: [@donggu1105](https://github.com/donggu1105)
- 정체성 anchor: [MOC - AI Product Engineering](https://github.com/donggu1105) (private vault)

---

## 📜 License

[MIT](./LICENSE) © 2026 강동현 (donggu)
