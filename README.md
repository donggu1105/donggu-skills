# donggu-skills

Personal Claude Code **plugin marketplace** by **강동현** (`joeykang` / 동구).

Domain-organized monorepo. 각 도메인이 별도 plugin namespace로 등록 — `donggu-<domain>:<skill>` 형식으로 호출.

---

## 🧩 Plugins

| Plugin | Namespace | Description |
|---|---|---|
| [donggu-obsidian](./donggu-obsidian) | `donggu-obsidian:` | Obsidian PKM vault operations (health audit, journal extraction, duplicate detection) |
| *(future)* donggu-marketing | `donggu-marketing:` | TBD — content strategy, copy editing, social |
| *(future)* donggu-dev | `donggu-dev:` | TBD — code review, architecture patterns |

---

## 🚀 Install

### 1. Add marketplace

Claude Code 안에서:
```
/plugin marketplace add donggu1105/donggu-skills
```

### 2. Install plugin

```
/plugin install donggu-obsidian@donggu-skills
```

→ Claude Code가 다음 호출부터 namespace 인식: `donggu-obsidian:checking-vault-health`

---

## 🔄 Update

```
/plugin marketplace update donggu-skills
```

→ git pull 동등 작업, 다음 호출 시 새 내용 사용.

---

## 📐 구조

```
donggu-skills/                       (marketplace repo)
├── .claude-plugin/
│   └── marketplace.json             ← plugins 카탈로그
├── donggu-obsidian/                 (plugin)
│   ├── .claude-plugin/
│   │   └── plugin.json              ← namespace = "donggu-obsidian"
│   ├── skills/
│   │   ├── checking-vault-health/SKILL.md
│   │   ├── extract-core/SKILL.md
│   │   └── finding-duplicate-notes/SKILL.md
│   └── README.md
├── README.md
└── LICENSE
```

### 새 도메인 추가 절차

1. 새 plugin 폴더 생성 (예: `donggu-marketing/`)
2. `donggu-marketing/.claude-plugin/plugin.json` 작성 (name: "donggu-marketing")
3. `donggu-marketing/skills/<skill-name>/SKILL.md` 작성
4. root `marketplace.json`의 `plugins` array에 새 plugin 추가
5. git commit + push
6. 사용자가 `/plugin install donggu-marketing@donggu-skills`로 install

---

## 🎯 사용 가정

- LYT / PARA / Zettelkasten 스타일 PKM vault (obsidian plugin)
- 다른 도메인은 plugin별 README 참조

---

## License

MIT
