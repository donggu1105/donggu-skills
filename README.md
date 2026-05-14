# donggu-skills

> Personal Claude Code skill marketplace by **강동현** ([@donggu1105](https://github.com/donggu1105))

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
[![Claude Code](https://img.shields.io/badge/Claude%20Code-Plugin%20Marketplace-8B5CF6)](https://claude.com/claude-code)
[![Plugins](https://img.shields.io/badge/plugins-1-blue)](#-plugins)
[![Skills](https://img.shields.io/badge/skills-3-green)](#-plugins)

Domain-organized monorepo. 각 도메인이 별도 plugin namespace로 등록되어 `donggu-<domain>:<skill>` 형식으로 호출.

> **Why this exists**: PKM(Obsidian/LYT/Zettelkasten) vault를 콘텐츠 파이프라인(저널 → CORE → Channel Pack → CASE)으로 운영하면서 정기 의례(주간 추출, 월간 health check, 분기 중복 audit)에 사용하는 도구. broadly applicable하게 작성했지만 atomic note + LYT-Lite 구조 기준.

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

### 📚 `donggu-obsidian` — Obsidian PKM vault operations

LYT / PARA / Zettelkasten 스타일 PKM vault 운영 자동화. 매주 추출 의례, 매월 health check, 분기 중복 audit 시 사용.

| Skill | 호출 | 용도 | Time budget |
|---|---|---|---|
| `checking-vault-health` | `donggu-obsidian:checking-vault-health` | 콘텐츠 파이프라인 4 layer (입구·정제·출구·큐레이션) 점검 | 10-15분 |
| `extract-core` | `donggu-obsidian:extract-core` | 빌드 저널 → atomic CORE 승격 의례 | 20-30분 |
| `finding-duplicate-notes` | `donggu-obsidian:finding-duplicate-notes` | 5 패턴 중복 audit (semantic / naming / absorbed / snippet / source) | 15-20분 |

**Skill chain 권장 흐름**:

```
checking-vault-health  ──┬──→  finding-duplicate-notes  (absorbed callout 발견 시)
                         └──→  extract-core             (extracted_to: [] 5+건)

extract-core  ──→  finding-duplicate-notes  (채택 시 기존 CORE 중복 검사)
```

각 skill의 `## 관련 Skill` 섹션이 자동 chain 권장.

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
/donggu-obsidian:checking-vault-health
```

또는 자연어 트리거:
- "내 옵시디언 vault 점검해줘"
- "이번 주 저널에서 CORE 후보 추출해줘"
- "중복 노트 찾아줘"

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
│   │   ├── checking-vault-health/
│   │   │   └── SKILL.md
│   │   ├── extract-core/
│   │   │   └── SKILL.md
│   │   └── finding-duplicate-notes/
│   │       └── SKILL.md
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
| **Broadly applicable** | 특정 vault convention X. `Vault-Specific Context` 섹션이 다른 PKM 시스템 매핑 안내 |
| **사용자 결정 게이트** | skill은 후보 추천만. 자동 채택 X. 모든 변경은 사용자 명시 후 |
| **자기 검수 가능** | `## Common Mistakes`, `## Red Flags` 섹션이 본인 검수 가이드 |
| **Cross-reference** | `## 관련 Skill` 섹션으로 chain 흐름 명시 |

---

## 🗺️ Roadmap

| Plugin | Status | Skills | Description |
|---|---|---|---|
| **donggu-obsidian** | ✅ `v1.0.0` | 3 | Obsidian PKM vault operations |
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
