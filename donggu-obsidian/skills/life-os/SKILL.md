---
name: life-os
description: Use when recording or resuming Life OS Daily check-ins, quick captures, or attachments from a dedicated Hermes channel, Claude Code, or Codex.
---

# Life OS

Keep conversation state in the target Daily note. Ask one question at a time and commit every trusted turn immediately through the shared runtime.
Support Daily and Capture only.

## Routing

- “오늘 정리하자” or no explicit period in the dedicated channel → Daily.
- “일단 기록해줘” → Capture.
- “어제 이어서” → yesterday's Daily.

## Hermes path

1. Call `donggu_life_os_status` before interpreting a normal channel message.
2. Start only on an explicit start command or the scheduled start prompt.
3. During an active check-in, call `donggu_life_os_record` once for the trusted latest turn.
4. Return only the tool's next question or completion summary.
5. Never use generic filesystem tools as a fallback when a native tool fails.

The hook and all native tools accept live turns only from the exact configured `life-os` Discord channel binding. Cron may call only `donggu_life_os_start_daily` when its Discord auto-delivery target is that same channel; status and record are forbidden from cron. A captured trusted turn is reserved until the runtime call succeeds and its JSON result is serialized, then committed; failures release it for a same-key retry.

For an explicit Daily start, call `donggu_life_os_start_daily` once and return its question. An explicit start resumes a paused Daily without resetting its answers or pending question. Treat the state embedded in the Daily note as the durable workflow state. Never defer a Vault mutation to private cache or batch answers for a later write.

### Exact record calls

Every `donggu_life_os_record` call requires `operation`. Select exactly one call for the latest turn:

- Pending answer → `donggu_life_os_record(operation="answer")`.
- `건너뛰기` → `donggu_life_os_record(operation="skip")`.
- `그만` → `donggu_life_os_record(operation="pause")`.
- `이어서 하자` → `donggu_life_os_record(operation="resume")`.
- `일단 기록해줘` → `donggu_life_os_record(operation="capture")`.
- Normal message with no active check-in → `donggu_life_os_record(operation="free_record")`; create a free Daily record without starting the sequence.

Add `follow_up_question` only to an `answer` call when proposing one short follow-up. Add `attachment_paths` only when the latest turn includes attachments. Add `date` only for an explicit target date such as yesterday. Never pass `control`, `text`, `message_text`, `message_key`, or `session_id`. The native handler uses the trusted Discord-authored turn captured before gateway preparation, uses `SessionDB` only for the persisted user row ID, and constructs the trusted key from the Hermes session, row, platform, and source identities.

Ask these fixed questions individually, in order:

1. 오늘 어떤 일이 있었나?
2. 감정과 에너지는 어떤가?
3. 진행한 일과 막힌 일은?
4. 생각·배움·결정은?
5. 내일 가장 중요한 한 가지는?

After each answer, optionally propose one short, non-recursive follow-up and pass it with that same record call. Ask 최대 2개 follow-ups across the check-in. Return the committed next question only; never send several questions together.

Pass agent-visible attachment paths to `donggu_life_os_record`. A Hermes cache path is input only: let the native runtime copy the actual file into `Life OS/Attachments/` and link that Vault attachment. Never write a cache path, URL, wrapper note, manifest, or attachment subdirectory.
For an attachment-only Discord turn, the native hook records the deterministic text `첨부 파일`; never derive answer text from injected document content or cache metadata.

Allow automated Vault writes only under:

- `Life OS/0. PeriodicNotes/`
- `Life OS/-1. Capture/`
- `Life OS/Attachments/`

## Manual path

In Claude Code, invoke `/donggu-obsidian:life-os`. In Codex, link this skill as `$life-os`. When native Hermes tools are unavailable outside Hermes, run `scripts/life-os.py`; it imports the shared runtime and preserves the same Daily state, question order, immediate commits, and Vault boundaries. Do not replace the CLI with generic filesystem mutation.
