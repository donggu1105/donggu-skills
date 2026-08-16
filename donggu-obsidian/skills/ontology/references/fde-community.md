# FDE Community boundary

`FDE Community/` is the top-level operating authority for the independent FDE·AX community. It is not a second physical Vault and it is not a customer project under `FDE Projects/`.

## Ownership

- `FDE Community/`: 운영 원칙, 이벤트, 미팅, 녹음 포인터, 사례, 결정, 액션, 운영 인덱스.
- `Personal Branding/60_Projects/FDE Community/`: 공개 콘텐츠, 글감, 전략 원문, 채널 산출물, IMAX 구현·빌드·배포 자산.
- `FDE Projects/<고객사>/`: 고객사별 인터뷰, 딜리버리 판단, 도메인 검증, 패턴, 플레이북.

Do not duplicate one canonical document across areas. Connect areas with wikilinks and keep each fact under the authority that owns it.

## External source boundary

KakaoTalk is an external source. Read it only through the approved read-only source tool when current conversation state matters. Do not copy full chat history or raw transcripts into the Vault. Store only a source pointer, bounded observation, operating judgment, decision, or approved summary.

## Privacy and retention

- Do not create a long-lived member CRM by default.
- Collect event-level personal information only when needed.
- Separate consent, access scope, and retention period.
- Meeting and recording notes must not expose unnecessary names, contacts, customer identifiers, or raw private conversation.

## Native separation action

The one package-owned `fde-community-separation.v1` manifest is native-applicable. It creates exactly eight files under top-level `FDE Community/` and updates exactly five bridge/content files under `Personal Branding/`.

The action guarantees:

- create 8, modify 5, move 0, delete 0,
- no IMAX path change,
- fixed package-owned paths and bodies,
- current-file hash preconditions,
- descriptor-relative path confinement and symlink rejection,
- a dedicated receipt namespace and crash-atomic journal,
- exact persisted preview and apply gates,
- read-back before acknowledgement.

Use `donggu_fde_community_recovery_status` first. On exact persisted `수정안 보여줘`, call `donggu_fde_community_plan`; do not construct an envelope. Show the actual fixed diff and state `현재 Vault 변경 0건`. Only a later, separate persisted message exactly equal to `적용해줘` may call `donggu_fde_community_apply`. Then call read-back and acknowledge only after all thirteen hashes match.

All later FDE Community edits remain proposal-only unless a separate dedicated native action explicitly supports them. Never fall back to generic filesystem mutation.
