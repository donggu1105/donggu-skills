# donggu-obsidian

Obsidian PKM vault operations skill collection. Part of [`donggu-skills`](../) marketplace.

## Skills

| Skill | 호출 | 용도 |
|---|---|---|
| [checking-vault-health](./skills/checking-vault-health) | `donggu-obsidian:checking-vault-health` | vault 4 layer (입구·정제·출구·큐레이션) 점검 |
| [extract-core](./skills/extract-core) | `donggu-obsidian:extract-core` | 빌드 저널 → atomic CORE 승격 의례 |
| [finding-duplicate-notes](./skills/finding-duplicate-notes) | `donggu-obsidian:finding-duplicate-notes` | 5 패턴 중복 audit (semantic / naming / absorbed / snippet / source) |

## Chain 흐름

```
checking-vault-health → finding-duplicate-notes (중복 신호 발견 시)
checking-vault-health → extract-core (추출 안 된 저널 5+건)
extract-core → finding-duplicate-notes (채택 시 기존 CORE 중복 검사)
```

각 SKILL.md의 `## 관련 Skill` 섹션 참조.

## 사용 가정

- LYT / PARA / Zettelkasten 스타일 PKM vault
- frontmatter `type` enum 컨벤션 (core / source / case / snippet / project / moc / channel-pack / channel-index / foundation / journal / guide)
- 다른 vault 적용 시 각 SKILL.md의 `## Vault-Specific Context` 섹션 참조 + path 매핑 조정 필요

## License

MIT
