# donggu-obsidian

![Skills](https://img.shields.io/badge/skills-1-green)

Hermes-native Vault runtime for bounded transactions, FDE Community daily Capture persistence, and Life OS Daily/Capture recording.

## User-facing skill

| Skill | Qualified name | Responsibility |
|---|---|---|
| `life-os` | `donggu-obsidian:life-os` | Record Daily check-ins, Capture entries, attachments, and recoverable structured AI summaries through the native Life OS runtime |

The former `ontology` prompt skill has been retired. Vault structure and routing are owned by the Vault's own `AGENTS.md`, `RULES.md`, `HOME.md`, and `INDEX` files. General Obsidian syntax and wiki workflows use their separate portable skills instead of this package.

## Native runtime

```text
native Vault tools
  |- deterministic CORE plan / apply / recovery / read-back / rollback
  |- fixed FDE Community separation transaction
  |- bounded FDE Community daily Capture upsert (cron-authorized only)
  `- trusted-turn Life OS Daily and Capture runtime
```

The files under `skills/core-review-approval/scripts/` are internal compatibility helpers used by the native runtime and existing automation. The directory deliberately has no `SKILL.md`; receipt, hash, journal, recovery, and write-boundary protocols are not user-facing prompt skills.

## Install or update in Hermes

```bash
hermes plugins install --force --enable donggu1105/donggu-skills/donggu-obsidian
hermes config check
```

The only registered plugin skill is:

```text
skill_view("donggu-obsidian:life-os")
```

Do not copy it into `~/.hermes/skills/`; that creates a stale duplicate. Claude Code uses `/donggu-obsidian:life-os`; Codex may link the same skill directory at `.codex/skills/life-os`.

## Life OS configuration

| Key | Meaning |
|---|---|
| `DONGGU_LIFE_OS_VAULT_ROOT` | Absolute Vault root containing `Life OS/` |
| `DONGGU_LIFE_OS_STATE_ROOT` | Private state directory outside the Vault |
| `DONGGU_LIFE_OS_TIMEZONE` | `Asia/Seoul` |

The Life OS skill may write only under its documented Daily, Capture, and attachment roots. It must use native tools and must not fall back to generic filesystem mutation.

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

Bind the qualified skill only. Merge these entries into the existing Discord section; never replace the whole section. Preserve the existing global `require_mention` value — 기존 global `require_mention` 값은 보존. If `allowed_channels` already exists, add only the Life OS channel; if it is absent, keep it absent.

The optional 22:00 check-in uses `Asia/Seoul` and cron `0 22 * * *`:

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

A scheduled check-in calls only `donggu_life_os_start_daily`; ongoing answers and summary completion remain bound to the trusted Life OS channel turn.

Attachments are copied into the flat `Life OS/Attachments/` layout and linked from Daily or Capture. Never persist a temporary cache path or URL.

### 수동 복구

If the runtime reports a temporary/manual-recovery condition, stop writes. Preserve `.<note>.life-os-*`, `.life-os-attachment-*`, `.life-os-recovery-*`, and the `DONGGU_LIFE_OS_STATE_ROOT` archives under `note-archives/`, including `.life-os-note-stage-*`, `.life-os-note-archive-*`, and `.life-os-note-aborted-*`, byte-for-byte. Existing-note replacement is allowed only on the 같은 filesystem with atomic exchange. Compare each residual with the canonical file and original by size and SHA-256 (`비교`), do not follow symlinks, and 삭제하지 않는다 before verified recovery or explicit verified GC.

## FDE Community daily Capture writer

`donggu_fde_daily_capture_upsert` is registered in its own `fde_community_capture` toolset. It is available only to the two authorized cron jobs and is not exposed through the user-facing Life OS skill.

| Boundary | Enforcement |
|---|---|
| Caller | Cron session only; any live gateway session identity is rejected |
| Authorization | Exact resolved delivery channel and cron identity |
| Path | Fixed dated file under `FDE Community/Inbox/` |
| Rooms | Public and operator lanes write separate files |
| Commit | Exclusive create or compare-and-swap replacement |
| Content | Eight fixed sections with PII and internal-label refusal |
| Scope | Capture create/replace only — no promotion, move, delete, or authority edit |

## Verification

From the repository root:

```bash
python3 -m unittest -v tests.test_ontology_skill_contract
python3 -m unittest -v tests.test_life_os_plugin
python3 -m unittest -v tests.test_native_plugin_packages
python3 -m unittest discover -s donggu-obsidian/skills/core-review-approval/tests -p 'test_*.py' -v
claude plugin validate .
```

For operational cutover, keep the previous installed plugin and Hermes config as rollback backups until the Life OS skill, native tool catalog, and authorized cron writer all pass read-back.
