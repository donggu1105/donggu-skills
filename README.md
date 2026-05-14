# donggu-skills

Personal Claude Code skill collection by **강동현** (`joeykang` / 동구).

도메인별 폴더로 분류된 monorepo. 각 skill은 `~/.claude/skills/`에 symlink로 연결돼 Claude Code의 flat namespace에서 직접 호출 가능.

---

## Skills

### 📚 `obsidian-pkm/` — Obsidian PKM vault operations

LYT (Linking Your Thinking) / PARA / Zettelkasten 스타일 PKM vault 운영 자동화. 콘텐츠 파이프라인 (캡처 → 정제 → 출고 → 큐레이션) 사이클의 정기 의례에 사용.

| Skill | 용도 | 호출 |
|---|---|---|
| [checking-vault-health](./obsidian-pkm/checking-vault-health) | vault 콘텐츠 파이프라인 4 layer 점검 (입구·정제·출구·큐레이션) | `/checking-vault-health` |
| [extract-core](./obsidian-pkm/extract-core) | 빌드 저널 → atomic CORE 승격 의례 | `/extract-core` |
| [finding-duplicate-notes](./obsidian-pkm/finding-duplicate-notes) | 중복·겹침 노트 5 패턴 audit (semantic / naming twins / absorbed-not-merged / snippet twins / source redundancy) | `/finding-duplicate-notes` |

**Skill 간 chain 권장 흐름**:
- `checking-vault-health` 중 absorbed callout 발견 → `finding-duplicate-notes` chain
- `checking-vault-health` 중 `extracted_to: []` 5+건 → `extract-core` chain
- `extract-core` 채택 시점 → `finding-duplicate-notes`로 기존 CORE 중복 검사

각 skill의 `## 관련 Skill` 섹션 참조.

---

## Install

### 단일 skill
```bash
git clone https://github.com/joeykang/donggu-skills.git ~/workspace/projects/donggu-skills
ln -s ~/workspace/projects/donggu-skills/obsidian-pkm/checking-vault-health ~/.claude/skills/checking-vault-health
```

### 전체 (도메인 단위)
```bash
git clone https://github.com/joeykang/donggu-skills.git ~/workspace/projects/donggu-skills
cd ~/workspace/projects/donggu-skills
for skill in obsidian-pkm/*/; do
  name=$(basename "$skill")
  ln -sf "$(pwd)/obsidian-pkm/$name" ~/.claude/skills/$name
done
```

Claude Code가 다음 호출 시 자동 인식 (system reminder에 skill 등록 확인됨).

---

## Update

```bash
cd ~/workspace/projects/donggu-skills
git pull
```

symlink 통해 `~/.claude/skills/`에 자동 반영. Claude Code 재시작 X.

---

## Disclaimer

이 skill들은 broadly applicable로 작성됐지만 **개인 PKM convention 일부 가정**:
- LYT-Lite 구조 (Inbox / Atlas / Sources / Efforts)
- 8-folder Personal Branding pattern (10_Sources / 20_Core / 25_Foundations / 30_Cases / 40_Snippets / 50_Channel_Packs / 60_MOCs / 70_Projects)
- frontmatter `type` enum (core / source / case / snippet / project / moc / channel-pack / channel-index / foundation / journal / guide)

다른 vault 적용 시 각 skill의 `## Vault-Specific Context` 섹션 참조 + path 매핑 조정 필요.

---

## 향후 도메인 (계획)

monorepo 구조라 도메인 추가는 새 폴더 + skill로 자연 확장:

```
donggu-skills/
├── obsidian-pkm/        ← 현재
├── marketing/           ← 예정 (콘텐츠 카피·SEO·소셜)
├── dev/                 ← 예정 (코드 리뷰·아키텍처)
└── ax-consulting/       ← 예정 (AI 도입·임원 자료)
```

도메인이 충분히 커지면 **Claude Code plugin으로 분기** 가능 — `donggu-pkm:checking-vault-health` 같은 namespace로.

---

## License

MIT
