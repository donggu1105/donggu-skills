# donggu-obsidian

![Skills](https://img.shields.io/badge/skills-2-green)

Ontology-aware Obsidian operations for the `donggu-skills` marketplace and Hermes native plugin runtime.

## User-facing skills

| Skill | Qualified name | Responsibility |
|---|---|---|
| `ontology` | `donggu-obsidian:ontology` | Route Personal Branding, FDE Projects, and Life OS requests; retrieve notes; run one curation loop; prepare candidate-scoped diffs; perform bounded maintenance |
| `life-os` | `donggu-obsidian:life-os` | Record Daily check-ins, Capture entries, attachments, and recoverable structured AI summaries through the native Life OS runtime |

The ontology skill replaces separate extraction, decomposition, duplicate, and health rituals. Duplicate search is part of integration; maintenance is explicit and bounded. It never runs a daily full-Vault scan and does not send healthy-state reports.

## Architecture

```text
trusted channel or explicit call
          |
          v
donggu-obsidian:ontology
  |- read root AGENTS.md
  |- classify Personal Branding / FDE Projects / Life OS
  |- load only the required reference
  |- read or prepare one candidate-specific diff
  `- apply only after a separate scoped approval

native CORE tools
  `- deterministic plan / apply / recovery / read-back / rollback

donggu-obsidian:life-os
  `- trusted-turn Daily and Capture runtime with recoverable AI summaries
```

The files under `skills/core-review-approval/scripts/` are internal compatibility helpers used by the native CORE runtime and existing n8n worker. The directory deliberately has no `SKILL.md`; database, receipt, hash, and journal protocols are not a user-facing prompt skill.

## Install or update in Hermes

```bash
hermes plugins install --force --enable donggu1105/donggu-skills/donggu-obsidian
hermes config check
```

Plugin skills are registered by `ctx.register_skill()` and loaded with qualified names:

```text
skill_view("donggu-obsidian:ontology")
skill_view("donggu-obsidian:life-os")
```

They do not appear in the global bare-skill index. Do not copy them into `~/.hermes/skills/`; that creates stale collisions.

## Channel binding

Merge the entry into the existing Discord configuration instead of replacing the section:

```yaml
discord:
  channel_skill_bindings:
    - id: "<ontology-channel-id>"
      skill: donggu-obsidian:ontology
  channel_prompts:
    "<ontology-channel-id>": >-
      Treat this channel as work on the configured ontology Vault. Read root
      AGENTS.md and the target area rules first. Read freely, but show one actual
      diff and wait for a separate 적용해줘 before any Vault mutation.
```

Keep concrete Vault paths, Discord IDs, and credentials in local configuration only.

## Life OS configuration

| Key | Meaning |
|---|---|
| `DONGGU_LIFE_OS_VAULT_ROOT` | Absolute Vault root containing `Life OS/` |
| `DONGGU_LIFE_OS_STATE_ROOT` | Private state directory outside the Vault; defaults under `$XDG_STATE_HOME` or `~/.local/state` |
| `DONGGU_LIFE_OS_TIMEZONE` | `Asia/Seoul` |

The Life OS skill may write only under its documented Daily, Capture, and attachment roots. It must use native tools and must not fall back to generic filesystem mutation.

Manual status probe:

```bash
python3 donggu-obsidian/skills/life-os/scripts/life-os.py \
  --vault-root "$DONGGU_LIFE_OS_VAULT_ROOT" status
```

### Life OS channel and schedule

Bind the qualified skill only. Merge these entries into the existing Discord section; never replace the whole section. Preserve the existing global `require_mention` value — 기존 global `require_mention` 값은 보존. If `allowed_channels` already exists, add only the Life OS channel; if it is absent, keep it absent.

다섯 번째 질문 또는 마지막 follow-up이 저장되면 원문 답변을 먼저 커밋한다. 이어서
Hermes host-owned `ctx.llm.complete_structured()`가 일곱 필드의 Korean Daily 정리를 만들고,
native runtime이 canonical summary block을 별도 원자 교환으로 넣는다. 모델 호출이 실패해도
원문은 유지되고 `summary_status: pending` 영수증으로 남는다. 같은 전용 채널에서
`donggu_life_os_finalize_daily`를 한 번 호출하면 재시도할 수 있다.

```yaml
discord:
  free_response_channels:
    - "<life-os-channel-id>"
  channel_skill_bindings:
    - id: "<life-os-channel-id>"
      skill: donggu-obsidian:life-os
  channel_prompts:
    "<life-os-channel-id>": >-
      Use only the donggu-obsidian:life-os skill and its native tools. Never
      fall back to generic filesystem mutation.
```

Hermes registers this plugin skill outside the global skill index. Verify it with `skill_view("donggu-obsidian:life-os")`. Claude Code uses `/donggu-obsidian:life-os`; Codex may link the same directory at `.codex/skills/life-os`.

The optional 22:00 check-in uses `Asia/Seoul` and cron `0 22 * * *`. Capture the exact job ID once and reuse it for edit, read-back, manual run, and history:

```bash
LIFE_OS_VAULT_ROOT="$(pwd)"
LIFE_OS_CHANNEL_ID="<life-os-channel-id>"
LIFE_OS_CRON_JOB_ID="<captured-job-id>"

hermes cron create '0 22 * * *' \
  'Use donggu-obsidian:life-os and call donggu_life_os_start_daily.' \
  --name 'Life OS 데일리 체크인 (22:00)' \
  --deliver "discord:${LIFE_OS_CHANNEL_ID}" \
  --skill donggu-obsidian:life-os \
  --workdir "$LIFE_OS_VAULT_ROOT"

hermes cron edit "$LIFE_OS_CRON_JOB_ID" \
  --schedule '0 22 * * *' \
  --deliver "discord:${LIFE_OS_CHANNEL_ID}" \
  --skill donggu-obsidian:life-os \
  --workdir "$LIFE_OS_VAULT_ROOT"

hermes cron list --all
hermes cron run "$LIFE_OS_CRON_JOB_ID"
hermes cron runs "$LIFE_OS_CRON_JOB_ID" --limit 5
```

Do not run when exact-name read-back resolves to zero or multiple job IDs. Keep concrete channel IDs in local configuration.

Attachments are copied into a flat `Life OS/Attachments/` layout and linked from Daily or Capture. Never persist a temporary cache path or URL.

### 수동 복구

If the runtime reports a temporary/manual-recovery condition, stop writes. Preserve `.<note>.life-os-*`, `.life-os-attachment-*`, and `.life-os-recovery-*` files byte-for-byte. Also preserve `DONGGU_LIFE_OS_STATE_ROOT` Vault state under `note-archives/`, including `.life-os-note-stage-*`, `.life-os-note-archive-*`, and `.life-os-note-aborted-*`.

Existing-note replacement is allowed only when the state archive and Vault are on the **같은 filesystem** and support **atomic exchange**. Compare each residual with the canonical file and original by size and SHA-256 (`비교`). Do not follow symlinks. Do not delete (`삭제하지 않는다`) a residual or archive until comparison, a separate backup, and explicit **verified GC** or manual verification are complete.

## Safety contract

- Read the actual Vault authority files before note contents.
- Keep Inbox raw until the user selects an item; selection feeds publication work only.
- Use the `선택 → 추출 → 통합` loop only for a completed and approved publication.
- Search existing CORE before proposing a new one.
- Show one actual diff and state zero writes before approval.
- Accept exact `적용해줘` only in a later persisted user message bound to the current candidate.
- Read the applied files back and preserve a rollback handle.
- Keep Ontology Lens as the FDE project source of truth; store pointers and judgments rather than copies.
- Stay silent on healthy checks; notify only on actionable issues or execution failure.

## Verification

From the repository root:

```bash
python3.11 -m unittest -v tests.test_ontology_skill_contract
python3.11 -m unittest -v tests.test_obsidian_content_flow_contracts
python3.11 -m unittest -v tests.test_native_plugin_packages
python3.11 -m unittest discover -s donggu-obsidian/skills/core-review-approval/tests -p 'test_*.py' -v
claude plugin validate .
```

For an operational cutover, keep the previous installed plugin and Hermes config as rollback backups until the qualified skill loads and a read-only Vault probe succeeds.
