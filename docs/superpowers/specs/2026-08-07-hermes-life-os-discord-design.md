# Hermes-first Life OS Discord Design

**Date:** 2026-08-07
**Status:** Approved

## Goal

Provide one public `life-os` skill in `donggu-obsidian` whose primary runtime is
Hermes Agent. A dedicated Discord text channel starts a five-question Daily
check-in at 22:00 Asia/Seoul, records every answer immediately in the current
Obsidian Daily note, resumes from durable note state after interruptions, and
archives Discord attachments as real Vault files.

Claude Code and Codex consume the same skill prose as secondary, manually
invoked clients. Hermes owns the unattended cron and real-time Discord path.

## Selected approach

Use a flat Discord channel backed by durable Daily-note state.

- The main channel remains the conversation surface; there is no per-day
  thread and no one-minute polling worker.
- Hermes binds every message in the configured channel to `life-os` and allows
  replies without a bot mention.
- The 22:00 cron starts or resumes the Daily workflow and posts the pending
  question to the channel.
- Discord session history is helpful context but is not workflow state. The
  hidden state marker in the Daily note is authoritative.

This deliberately avoids depending on cron-to-gateway session continuity.
Hermes cron deliveries and ordinary channel turns may use different sessions;
both recover the same workflow state from the Vault.

## Scope

### In scope

- One `life-os` skill under `donggu-obsidian/skills/life-os/`.
- A deterministic native Hermes runtime and three Life OS tools.
- Daily start, answer, skip, pause, resume, completion, and free Daily record.
- Daily Capture append for “일단 기록해줘”.
- Manual routing to existing Weekly, Monthly, Quarterly, and Yearly notes.
- Discord attachment ingestion into a flat `Life OS/Attachments/` directory.
- Idempotent Discord channel bootstrap and a daily Hermes cron job.
- Hermes channel binding, prompt, allowlist, gateway restart, and smoke checks.

### Out of scope

- Editing Hermes Agent core.
- A custom Discord bot, webhook service, or message polling daemon.
- Copying third-party LifeOS template text into the public repository.
- Automatic publication into `Personal Branding/` or any other Vault area.
- Reminders after the 22:00 prompt.
- Automated Weekly, Monthly, Quarterly, or Yearly cron jobs.

## Package architecture

```text
donggu-obsidian/
├── .claude-plugin/plugin.json
├── plugin.yaml
├── __init__.py
├── tools.py
├── runtime/
│   ├── __init__.py
│   └── life_os.py
└── skills/
    └── life-os/
        ├── SKILL.md
        └── scripts/
            └── life-os.py
```

`SKILL.md` owns conversational behavior:

- intent routing;
- the five core questions and at most two follow-up questions per check-in;
- selection of the native tool operation;
- user-facing next-question and completion messages;
- direct Markdown fallback rules for Claude Code and Codex.

`runtime/life_os.py` owns deterministic behavior:

- configured Vault resolution and path validation;
- KST date and period resolution;
- Daily creation from the Vault-local template;
- bounded check-in block parsing and mutation;
- file locks and atomic replacement;
- trusted Hermes message-id idempotency;
- attachment validation, numbering, hashing, copying, and recovery.

`skills/life-os/scripts/life-os.py` is a thin CLI over the same runtime for
Claude Code, Codex, tests, and local diagnostics. It does not reimplement Vault
mutation.

## Configuration contract

Hermes is configured locally; deployment-specific paths and Discord IDs are
never committed to the public repository.

- `DONGGU_LIFE_OS_VAULT_ROOT`: absolute Obsidian Vault root.
- `DONGGU_LIFE_OS_TIMEZONE`: optional IANA timezone; defaults to
  `Asia/Seoul`.
- `DONGGU_LIFE_OS_STATE_ROOT`: optional private lock-state directory; defaults
  to `$XDG_STATE_HOME/donggu-life-os` or `~/.local/state/donggu-life-os`.
- Hermes `timezone`: explicitly set to `Asia/Seoul` for cron evaluation.

The runtime resolves `Life OS/` below the configured Vault root. It fails
closed when the root is missing, relative, a symlink, or does not contain the
expected Life OS template and periodic-note directories. Native Hermes tools
do not accept an arbitrary Vault root from the model.

The Discord deployment adds the created channel ID to the free-response and
skill-routing settings:

```yaml
discord:
  free_response_channels:
    - "<life-os-channel-id>"
  channel_skill_bindings:
    - id: "<life-os-channel-id>"
      skill: life-os
  channel_prompts:
    "<life-os-channel-id>": |-
      This is the dedicated Life OS channel. Use the life-os skill for every
      user turn. The native Life OS tools are the only automated Vault write
      path. Never write outside Life OS and never retain a Hermes cache path.
```

If `allowed_channels` already exists as a non-empty allowlist, deployment
appends the Life OS ID rather than replacing the list. If it is absent,
deployment leaves it absent so adding Life OS does not silently restrict
existing Discord behavior. Existing Discord configuration is otherwise
preserved. The new channel inherits the parent category permission overwrites.

## Hermes native tools

### `donggu_life_os_status`

Read-only. Returns the selected date, Daily path, workflow status, pending
question, answered questions, follow-up count, and attachment references.
It accepts an optional explicit date for “어제 이어서”; absent a date, it uses
the date-resolution rules below.

### `donggu_life_os_start_daily`

Creates or opens the selected Daily, installs the bounded Life OS record block
when absent, and returns the pending question. It is idempotent:

- `not_started` becomes `active` at question 1;
- `active` returns the current pending question without resetting answers;
- `paused` remains paused unless the operation explicitly requests resume;
- `completed` returns completion and never starts a second check-in.

### `donggu_life_os_record`

Accepts only a bounded operation enum and an optional list of agent-visible
attachment cache paths. Operations are `answer`, `skip`, `pause`, `resume`,
`capture`, and `free_record`.

For Hermes turns, the handler reads the latest persisted user message, session
ID, and message row ID from Hermes `SessionDB`; model-supplied answer text or
Discord message IDs are not trusted. The `(session_id, message_row_id)` pair is
the native idempotency key. Attachment paths remain model-selected because
Hermes exposes media paths in the current prompt, but the runtime accepts only
regular, non-symlink files beneath the active Hermes image, audio, or document
cache roots.

The tool returns the committed path, new state, and either the next question
or a completion message. Tool failure never advances the question.

## User interaction

The core Daily questions are asked one at a time:

1. 오늘 어떤 일이 있었나?
2. 감정과 에너지는 어떤가?
3. 진행한 일과 막힌 일은?
4. 생각·배움·결정은?
5. 내일 가장 중요한 한 가지는?

The agent may ask at most two follow-up questions across the whole check-in.
A follow-up is stored immediately after the answer that caused it, then the
workflow returns to the next unanswered core question.

Control phrases:

- `건너뛰기`: record the current question as skipped and continue.
- `그만`: preserve state as `paused` and stop asking.
- `이어서 하자`: resume the newest eligible paused or active Daily.
- `오늘 정리하자`: start or resume today's Daily.
- `어제 이어서`: explicitly target yesterday's Daily.
- `일단 기록해줘`: append a timestamped Capture entry.

With no explicit period or command, the dedicated Discord channel defaults to
Daily. A normal message during an active check-in is the pending answer. A
normal message without an active check-in becomes a free Daily record; it does
not silently start the five-question sequence.

## Cron behavior

One Hermes job runs at `0 22 * * *` in `Asia/Seoul` with:

- a unique stable name;
- the `life-os` skill attached;
- the Vault root as `workdir`;
- delivery to the exact Discord channel ID;
- a self-contained prompt that calls `donggu_life_os_start_daily` and returns
  only the pending question or the already-completed notice.

The job does not reset active state and does not send a second reminder. Cron's
existing scheduler lock and execution ledger remain the scheduling audit
source; Vault-side idempotency remains the content audit source.

## Daily file contract

Daily files remain at the existing Vault-local convention:

```text
Life OS/0. PeriodicNotes/YYYY/Daily/MM/YYYY-MM-DD.md
```

If the file is absent, the runtime reads the existing Vault-local Daily
template. It renders the known standalone LifeOS snapshot Templater expression
to empty output because Hermes cannot execute Obsidian Templater. Any other
unrecognized `<% ... %>` expression fails closed rather than leaving executable
template text or guessing its result. Existing LifeOS code blocks are retained.

Automation mutates only a bounded block immediately below `## Daily Record`:

```markdown
<!-- life-os:record:start -->
### Daily Check-in

#### 1. 오늘 어떤 일이 있었나?
사용자의 실제 답변
%% life-os-message: <session-id>:<trusted-message-row-id> %%

%% life-os-state: {"version":1,"date":"2026-08-07","status":"active","next_question":2,"answered":[1],"skipped":[],"follow_up_count":0,"last_message_key":"<session-id>:<trusted-message-row-id>"} %%
<!-- life-os:record:end -->
```

The state is a single canonical JSON object inside an Obsidian comment. Runtime
parsing rejects duplicate blocks, duplicate state markers, unknown versions,
invalid question numbers, or contradictory answered/skipped sets. It never
repairs ambiguity by overwriting user content.

All template content, LifeOS code blocks, habits, and user-authored text outside
the bounded block are byte-preserved.

## Date resolution

All date boundaries use the configured IANA timezone.

1. Before today's workflow starts, the newest active or paused Daily from the
   previous calendar day remains the default resume target.
2. Once today's workflow starts, today becomes the default target.
3. `어제 이어서` explicitly selects yesterday even when today is active.
4. The next 22:00 cron may start today without modifying an incomplete prior
   Daily.
5. A completed Daily is never reopened implicitly.

## Capture contract

Capture entries append to one daily file:

```text
Life OS/-1. Capture/YYYY-MM-DD.md
```

The file contains `# Capture — YYYY-MM-DD` followed by timestamped entries.
The runtime appends atomically and directly links any stored attachment. It
does not classify, move, or promote the capture.

## Attachment contract

```text
Life OS/Attachments/
├── A001 - readable-name.ext
└── A002 - another-file.ext
```

- The directory is flat and contains only actual user attachments.
- Markdown wrappers, subdirectories, manifests, URLs, and Hermes cache paths
  are forbidden.
- The next number is the highest existing valid `A###` number plus one.
- Names are normalized to a readable basename, path separators and control
  characters are removed, and the original lowercase extension is preserved.
- Files larger than the configured Hermes attachment limit are rejected before
  Vault mutation.
- SHA-256 is computed before allocation. An identical existing attachment is
  reused instead of copied again.
- New files are copied to a same-directory temporary file, fsynced, verified by
  hash, and atomically renamed.
- The consuming Daily or Capture note links the actual Vault file directly.
- Images may be embedded; other files use a wikilink.
- A temporary Hermes path or Discord CDN URL is never written into a note.

An interruption after file rename but before note commit can leave an unlinked
file. Retrying hashes existing files, reuses the matching A-number, and then
commits the note link. No private manifest is needed in the attachment folder.

## Concurrency and idempotency

- One advisory lock under the private state root serializes Life OS mutations
  for the configured Vault. Its directory name is a SHA-256 digest of the
  canonical Vault path; no personal path is written into the lock filename.
- The private state directory and lock use modes `0700` and `0600`. No lock or
  manifest is stored in the Vault or attachment directory.
- Note replacement uses a sibling temporary file, flush, fsync, atomic rename,
  and parent-directory fsync.
- A trusted Hermes `(session_id, message_row_id)` key appears once in the
  bounded record block.
- Reprocessing the same message returns the prior result without adding text,
  advancing state, or copying another attachment.
- Attachment identity is content hash, not a temporary cache filename.
- A failed attachment validation, copy, note parse, or atomic commit leaves the
  pending question unchanged.
- The runtime never follows a symlink in the Vault root, Life OS path, template,
  Daily path, Capture path, attachment directory, or cache file.

## Discord channel bootstrap

The target deployment uses one text channel named `life-os` below an existing
category. Hermes Agent v0.20.0 documentation advertises channel management, but
the installed `discord_admin` action schema has no create/edit/delete channel
operation. Deployment therefore performs one authenticated Discord REST call
using the already configured Hermes bot credential without printing or
persisting the token.

Bootstrap is idempotent:

1. List channels in the selected guild.
2. Reuse exactly one text channel with the requested name and parent category.
3. Fail on multiple matches or a same-name channel under another parent.
4. Otherwise create one text channel with the parent category ID and a Life OS
   topic, inheriting category permissions.
5. Read it back and verify guild, parent, name, type, and bot visibility.

The bot must hold `Manage Channels`; deployment verifies the permission before
mutation. No reusable channel-administration tool is added to the public
plugin.

## Versioning and distribution

- Bump `donggu-obsidian` from `1.8.0` to `1.9.0` in both Claude and Hermes
  manifests because this adds a public skill and native tools.
- Extend, rather than replace, the existing CORE tool registrations.
- Update package README with Life OS configuration and Hermes-first usage.
- Hermes installs/enables the `donggu-obsidian` plugin from the public package.
- Claude Code uses `/donggu-obsidian:life-os`.
- Codex points its user skill entry at the same public `SKILL.md`; copied forks
  are not created.

## Verification

Automated tests use temporary Vaults and temporary Hermes cache roots. They
cover:

- missing/existing Daily creation and preservation;
- known-template rendering and unknown Templater rejection;
- all five questions, two-follow-up cap, skip, pause, resume, and completion;
- free Daily record and Capture append;
- current/previous-day resolution across the KST boundary;
- duplicate trusted message replay;
- attachment numbering, filename normalization, deduplication, and direct
  links;
- crash windows before file rename and before note commit;
- corrupt/duplicate state markers;
- path traversal, symlink, non-regular cache file, and size rejection;
- concurrent record attempts;
- Hermes schemas and plugin registration without regressing existing CORE
  tools.

Deployment checks then verify:

1. Claude and Hermes manifest versions match.
2. `hermes plugins list` shows `donggu-obsidian` enabled.
3. Hermes discovers `life-os` and all three native tools.
4. The Discord text channel exists under the intended parent and is visible to
   the bot.
5. Free-response, skill binding, and prompt contain the exact channel ID. An
   existing allowlist includes it without losing prior entries; an absent
   allowlist remains absent.
6. Gateway restart is healthy.
7. The cron list contains one active KST 22:00 job with the exact delivery
   target, skill, and workdir.
8. A forced cron run posts the first question and creates an `active` Daily
   state without disturbing the rest of the note.

The implementation is complete when Hermes can receive an ordinary, unmentioned
message in the dedicated Discord channel, commit it exactly once under
`## Daily Record`, archive any attachment as a real Vault file, and return the
correct next question. If a real inbound user turn is not available during
deployment, native runtime and gateway binding tests establish the path and the
forced cron delivery remains the final live smoke checkpoint.

## Safety boundaries

- Hermes core is unchanged.
- Discord IDs, personal absolute paths, and bot credentials remain local.
- The bot credential is never placed in a command argument, log, tool result,
  committed file, or generated note.
- Automated writes are restricted to `Life OS/0. PeriodicNotes/`,
  `Life OS/-1. Capture/`, and `Life OS/Attachments/`.
- `Personal Branding/` and every other top-level Vault area are outside this
  workflow.
- Failures are explicit and fail closed; the skill does not fall back to an
  unrestricted filesystem write.
