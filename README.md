# donggu-skills

> Personal Claude Code and Codex skill marketplace by **강동현** ([@donggu1105](https://github.com/donggu1105))

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
[![Claude Code](https://img.shields.io/badge/Claude%20Code-Plugin%20Marketplace-8B5CF6)](https://claude.com/claude-code)
[![Plugins](https://img.shields.io/badge/plugins-6-blue)](#-plugins)
[![Skills](https://img.shields.io/badge/skills-10-green)](#-plugins)

Domain-organized monorepo. 각 도메인이 별도 plugin namespace로 등록되어 `donggu-<domain>:<skill>` 형식으로 호출.

> **Why this exists**: 실제 운영 경계를 이해하는 domain-native skill과 runtime을 한 저장소에서 관리한다. Vault 구조와 라우팅은 각 Vault의 권위 파일이 소유하고, 이 저장소는 필요한 네이티브 runtime만 제공한다.

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

### 📚 `donggu-obsidian` — Native Vault runtime

사용자-facing 진입점은 `life-os` 하나입니다. Vault 구조·라우팅 프롬프트는 각 Vault의 `AGENTS.md`·`RULES.md`·`HOME.md`·`INDEX`가 직접 소유합니다.

| Skill | 호출 | 용도 |
|---|---|---|
| `life-os` | `/donggu-obsidian:life-os` | Daily 대화 체크인, Capture, 첨부 기록, 구조화된 AI 정리 |

CORE·FDE Community transaction의 hash·journal·rollback과 FDE Community 일일 Capture writer는 plugin native runtime이 소유하며 prompt skill로 노출하지 않습니다.

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

### 🔎 `donggu-research` — Grounded public research

`last30days`와 공식 원문으로 전략컨설팅펌의 AI 실무를 학습하고, 동구님의 FDE·DA·AIDP 업무에 옮길 수 있는 산출물과 개입 방식을 뽑습니다.

| Skill | 호출 | 용도 |
|---|---|---|
| `ai-consulting-practice-radar` | `donggu-research:ai-consulting-practice-radar` | `last30days` 기반 컨설팅펌 AI 문제 정의·운영모델·구현·채택·ROI 사례 학습과 FDE·DA 비교 |

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
/donggu-obsidian:life-os
```

Vault의 일반 읽기·검색·정리는 해당 Vault의 권위 파일과 필요한 범용 Obsidian 스킬을 직접 사용합니다.

### Codex — 현재 `donggu-sns` 지원

```bash
codex plugin marketplace add donggu1105/donggu-skills
codex plugin add donggu-sns@donggu-skills
```

업데이트할 때는 marketplace를 갱신한 뒤 plugin을 다시 설치한다.

```bash
codex plugin marketplace upgrade donggu-skills
codex plugin add donggu-sns@donggu-skills
```

설치·업데이트된 skill 목록은 새 thread에서 다시 로드한다. 현재 Codex catalog에는 `donggu-sns`만 등록되어 있으며 나머지 domain plugin은 현재 Codex catalog에 미등록이다.

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
│   └── marketplace.json             ← Claude Code 전체 plugin catalog
├── .agents/plugins/marketplace.json      ← Codex manifest-ready subset catalog
├── donggu-sns/.codex-plugin/plugin.json  ← Codex plugin manifest
├── donggu-obsidian/                 ← plugin (namespace: donggu-obsidian:)
│   ├── .claude-plugin/
│   │   └── plugin.json              ← plugin 메타
│   ├── skills/
│   │   ├── core-review-approval/    ← internal helper scripts, no SKILL.md
│   │   └── life-os/
│   │       ├── SKILL.md
│   │       └── scripts/life-os.py
│   ├── runtime/                     ← native transaction + Capture + Life OS runtime
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
├── donggu-research/                 ← plugin (namespace: donggu-research:)
│   ├── .claude-plugin/plugin.json
│   ├── skills/ai-consulting-practice-radar/SKILL.md
│   └── README.md
├── README.md                        ← 본 파일
└── LICENSE
```

**파일 역할**:
- `.claude-plugin/marketplace.json` — Claude Code가 사용하는 전체 plugin catalog. 새 도메인 plugin 추가 시 `plugins` array 확장.
- `.agents/plugins/marketplace.json` — Codex manifest가 준비된 plugin만 등록하는 subset catalog.
- `<plugin>/.claude-plugin/plugin.json` — Claude Code plugin namespace + 메타. `name` 필드가 호출 시 prefix.
- `<plugin>/.codex-plugin/plugin.json` — Codex plugin 메타와 공유 `skills/` 경로.
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
| **donggu-obsidian** | ✅ `v2.4.0` | 1 | Hermes-native Vault transactions, bounded FDE Capture, and Life OS summaries |
| **donggu-docs** | ✅ `v1.0.0` | 1 | Document & deck authoring (tightened HTML slide decks) |
| **donggu-research** | ✅ `v1.1.0` | 1 | last30days-backed AI consulting practice learning radar |
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