# Hermes-first Life OS Discord Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship and deploy a Hermes-first `donggu-obsidian:life-os` skill that starts a KST 22:00 Discord Daily check-in, records each answer immediately in the Obsidian Daily note, and archives Discord attachments as real Vault files.

**Architecture:** A deterministic `LifeOSRuntime` owns bounded Markdown mutation, state, locking, date selection, Capture, and attachment storage. Three native Hermes tools wrap that runtime, while one shared `SKILL.md` owns conversational routing. Discord channel state is recoverable from the Daily note, so cron delivery does not depend on sharing a Hermes session with later channel replies.

**Tech Stack:** Python 3.11+ standard library, `unittest`, Obsidian Flavored Markdown, Hermes Agent v0.20 native plugins/tools/skills/cron, Discord REST API v10.

## Global Constraints

- Hermes Agent is the primary runtime; Claude Code and Codex are secondary manual clients of the same `SKILL.md`.
- Do not modify Hermes Agent core or add dependencies.
- Public repository files must not contain Discord IDs, personal absolute paths, or credentials.
- Automated Vault writes are restricted to `Life OS/0. PeriodicNotes/`, `Life OS/-1. Capture/`, and `Life OS/Attachments/`.
- Preserve every byte outside the bounded `life-os:record` block when updating an existing Daily note.
- The attachment directory is flat and permanently contains only real user attachments.
- The five core questions are fixed; allow at most two non-recursive follow-up questions per Daily check-in.
- Use KST (`Asia/Seoul`) for every date boundary and the `0 22 * * *` cron.
- Use TDD for every runtime or adapter behavior and commit each task independently.
- Do not copy third-party LifeOS template text into this public repository.

---

## File map

- `donggu-obsidian/runtime/life_os.py`: deterministic Life OS state, Markdown, date, Capture, lock, and attachment runtime.
- `donggu-obsidian/runtime/__init__.py`: public runtime exports without disturbing CORE exports.
- `donggu-obsidian/tools.py`: Hermes schemas, singleton, trusted-message lookup, and Life OS handlers.
- `donggu-obsidian/__init__.py`: registers three Life OS tools after the eight existing CORE tools.
- `donggu-obsidian/skills/life-os/SKILL.md`: provider-neutral conversation and routing contract.
- `donggu-obsidian/skills/life-os/scripts/life-os.py`: thin local CLI over `LifeOSRuntime`.
- `tests/test_life_os_runtime.py`: state, Markdown, date, Capture, attachment, atomicity, and security tests.
- `tests/test_life_os_plugin.py`: Hermes schema, handler, trusted-message, and registration tests.
- `tests/test_life_os_skill_contract.py`: skill prose, CLI, question, routing, and safety contract tests.
- `tests/test_native_plugin_packages.py`: expected Obsidian version and full native tool surface.
- `donggu-obsidian/.claude-plugin/plugin.json`: Claude package version `1.9.1`.
- `donggu-obsidian/plugin.yaml`: Hermes version, description, and eleven provided tools.
- `.claude-plugin/marketplace.json`: marketplace version `1.9.1`.
- `donggu-obsidian/README.md`: Hermes-first Life OS install/config/use guide.
- `README.md`: marketplace Life OS listing and corrected skill counts.

---

### Task 1: Daily state and bounded Markdown runtime

**Files:**
- Create: `donggu-obsidian/runtime/life_os.py`
- Create: `tests/test_life_os_runtime.py`
- Modify: `donggu-obsidian/runtime/__init__.py`

**Interfaces:**
- Produces: `LifeOSError`, `WorkflowState`, `LifeOSRuntime.from_environment()`, `LifeOSRuntime.status()`, `LifeOSRuntime.start_daily()`, and `LifeOSRuntime.record()`.
- `LifeOSRuntime.record()` signature is `record(operation: str, *, message_text: str, message_key: str, attachment_paths: Sequence[Path] = (), follow_up_question: str | None = None, target_date: date | None = None) -> dict[str, Any]`.
- Later tasks consume `LifeOSRuntime.QUESTIONS`, `LifeOSRuntime.daily_path()`, and JSON-serializable result dictionaries.

- [ ] **Step 1: Write failing tests for Daily creation and bounded preservation**

```python
class LifeOSRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.vault = self.base / "vault"
        template = self.vault / "Life OS/0. PeriodicNotes/Templates/Daily.md"
        template.parent.mkdir(parents=True)
        template.write_text(
            "## Project List\n<% LifeOS.Project.snapshot() %>\n\n"
            "## Daily Record\n%%Your Record%%\n\n"
            "## Habit\n- [ ] Breakfast\n\n"
            "```LifeOS\nTaskDoneListByTime\n```\n",
            encoding="utf-8",
        )
        self.runtime = LifeOSRuntime(
            vault_root=self.vault,
            state_root=self.base / "state",
            timezone=ZoneInfo("Asia/Seoul"),
        )

    def test_start_daily_renders_known_snapshot_and_preserves_template_blocks(self):
        result = self.runtime.start_daily(date(2026, 8, 7))
        text = Path(result["path"]).read_text(encoding="utf-8")
        self.assertNotIn("<%", text)
        self.assertIn("- [ ] Breakfast", text)
        self.assertIn("```LifeOS\nTaskDoneListByTime\n```", text)
        self.assertIn("<!-- life-os:record:start -->", text)
        self.assertEqual(1, result["next_question"])

    def test_record_changes_only_bounded_block(self):
        self.runtime.start_daily(date(2026, 8, 7))
        path = self.runtime.daily_path(date(2026, 8, 7))
        original = path.read_text(encoding="utf-8")
        before, after = original.split("<!-- life-os:record:start -->", 1)
        _block, suffix = after.split("<!-- life-os:record:end -->", 1)
        self.runtime.record(
            "answer", message_text="산책을 했다", message_key="s1:1",
            target_date=date(2026, 8, 7),
        )
        updated = path.read_text(encoding="utf-8")
        self.assertTrue(updated.startswith(before + "<!-- life-os:record:start -->"))
        self.assertTrue(updated.endswith("<!-- life-os:record:end -->" + suffix))
        self.assertIn("산책을 했다", updated)
```

- [ ] **Step 2: Run the new tests and confirm RED**

Run: `python3 -m unittest tests.test_life_os_runtime -v`

Expected: import failure because `donggu-obsidian/runtime/life_os.py` does not exist.

- [ ] **Step 3: Implement the state model, path validation, template rendering, and bounded block**

```python
QUESTIONS = (
    "오늘 어떤 일이 있었나?",
    "감정과 에너지는 어떤가?",
    "진행한 일과 막힌 일은?",
    "생각·배움·결정은?",
    "내일 가장 중요한 한 가지는?",
)

@dataclass(frozen=True)
class WorkflowState:
    version: int
    date: str
    status: str
    next_question: int | None
    answered: tuple[int, ...]
    skipped: tuple[int, ...]
    follow_up_count: int
    pending_follow_up: dict[str, Any] | None
    last_message_key: str | None

class LifeOSRuntime:
    QUESTIONS = QUESTIONS

    def __init__(self, *, vault_root: Path, state_root: Path, timezone: ZoneInfo):
        self.vault_root = _checked_directory(vault_root)
        self.life_root = _checked_child(self.vault_root, "Life OS")
        self.state_root = _prepare_private_state_root(state_root)
        self.timezone = timezone

    def daily_path(self, value: date) -> Path:
        return self.life_root / "0. PeriodicNotes" / f"{value:%Y}" / "Daily" / f"{value:%m}" / f"{value:%Y-%m-%d}.md"

    def start_daily(self, target_date: date | None = None, *, resume: bool = False) -> dict[str, Any]:
        selected = target_date or datetime.now(self.timezone).date()
        with self._mutation_lock():
            path = self._ensure_daily(selected)
            document, state = self._read_or_install_block(path, selected)
            if state.status == "not_started" or (resume and state.status == "paused"):
                state = replace(state, status="active")
                self._commit_document(path, self._render(document, state))
            return self._result(path, state)
```

The implementation must use a single canonical JSON state comment, reject duplicate or malformed blocks, remove only the exact standalone snapshot expression, reject all other `<% ... %>` expressions, and atomically replace files with sibling temporary files plus `fsync`.

- [ ] **Step 4: Export the runtime types**

```python
from .life_os import LifeOSError, LifeOSRuntime, WorkflowState

__all__ = [
    "CoreActionRuntime", "CoreApprovalError", "CoreHelperError",
    "CoreReceiptError", "CoreReceiptStore", "CoreRuntimeError",
    "LifeOSError", "LifeOSRuntime", "WorkflowState",
]
```

- [ ] **Step 5: Run the focused tests and confirm GREEN**

Run: `python3 -m unittest tests.test_life_os_runtime -v`

Expected: all Task 1 tests pass.

- [ ] **Step 6: Commit Task 1**

```bash
git add donggu-obsidian/runtime/life_os.py donggu-obsidian/runtime/__init__.py tests/test_life_os_runtime.py
git commit -m "feat(obsidian): add bounded Life OS Daily runtime"
```

---

### Task 2: Conversation operations, follow-ups, date resolution, and Capture

**Files:**
- Modify: `donggu-obsidian/runtime/life_os.py`
- Modify: `tests/test_life_os_runtime.py`

**Interfaces:**
- Extends `LifeOSRuntime.record()` for `answer`, `skip`, `pause`, `resume`, `capture`, and `free_record`.
- Produces `LifeOSRuntime.resolve_target_date(command: str | None = None) -> date` and `LifeOSRuntime.capture_path(date) -> Path`.
- Keeps `pending_follow_up` as `{"for_question": int, "question": str}` or `None`.

- [ ] **Step 1: Write failing tests for the full five-question state machine**

```python
def test_questions_followups_pause_resume_and_completion(self):
    day = date(2026, 8, 7)
    self.runtime.start_daily(day)
    first = self.runtime.record(
        "answer", message_text="회의가 길었다", message_key="s1:1",
        follow_up_question="무엇이 가장 힘들었나?", target_date=day,
    )
    self.assertEqual("무엇이 가장 힘들었나?", first["question"])
    second = self.runtime.record(
        "answer", message_text="결정이 계속 바뀐 점", message_key="s1:2",
        target_date=day,
    )
    self.assertEqual(2, second["next_question"])
    paused = self.runtime.record(
        "pause", message_text="그만", message_key="s1:3", target_date=day,
    )
    self.assertEqual("paused", paused["status"])
    resumed = self.runtime.record(
        "resume", message_text="이어서 하자", message_key="s1:4", target_date=day,
    )
    self.assertEqual("active", resumed["status"])
    for index in range(2, 6):
        result = self.runtime.record(
            "answer", message_text=f"답변 {index}", message_key=f"s1:{index + 3}",
            target_date=day,
        )
    self.assertEqual("completed", result["status"])

def test_capture_appends_timestamped_entry_without_starting_daily(self):
    result = self.runtime.record(
        "capture", message_text="책 아이디어", message_key="s2:1",
        target_date=date(2026, 8, 7),
    )
    text = Path(result["path"]).read_text(encoding="utf-8")
    self.assertIn("# Capture — 2026-08-07", text)
    self.assertIn("책 아이디어", text)
    self.assertFalse(self.runtime.daily_path(date(2026, 8, 7)).exists())
```

- [ ] **Step 2: Run the state-machine tests and confirm RED**

Run: `python3 -m unittest tests.test_life_os_runtime.LifeOSRuntimeTests.test_questions_followups_pause_resume_and_completion tests.test_life_os_runtime.LifeOSRuntimeTests.test_capture_appends_timestamped_entry_without_starting_daily -v`

Expected: failures because operations and Capture are not implemented.

- [ ] **Step 3: Implement operation dispatch and durable follow-up state**

```python
def record(self, operation: str, *, message_text: str, message_key: str,
           attachment_paths: Sequence[Path] = (), follow_up_question: str | None = None,
           target_date: date | None = None) -> dict[str, Any]:
    if operation not in {"answer", "skip", "pause", "resume", "capture", "free_record"}:
        raise LifeOSError("unsupported Life OS operation")
    selected = target_date or self.resolve_target_date()
    with self._mutation_lock():
        if operation == "capture":
            return self._append_capture(selected, message_text, message_key, attachment_paths)
        path = self._ensure_daily(selected)
        document, state = self._read_or_install_block(path, selected)
        if self._message_already_committed(document, message_key):
            return self._result(path, state, duplicate=True)
        next_document, next_state = self._apply_operation(
            document, state, operation, message_text, message_key,
            follow_up_question=follow_up_question,
        )
        self._commit_document(path, self._render(next_document, next_state))
        return self._result(path, next_state)
```

Follow-up rules are exact: only a core answer may install one, length is 1–300 characters after trimming, count is incremented when installed, a follow-up answer clears it, and no follow-up answer may create another follow-up.

- [ ] **Step 4: Implement KST target selection and free Daily records**

```python
def resolve_target_date(self, command: str | None = None) -> date:
    today = datetime.now(self.timezone).date()
    if command == "yesterday":
        return today - timedelta(days=1)
    today_state = self._optional_state(today)
    if today_state and today_state.status in {"active", "paused", "completed"}:
        return today
    yesterday = today - timedelta(days=1)
    old_state = self._optional_state(yesterday)
    if old_state and old_state.status in {"active", "paused"}:
        return yesterday
    return today
```

`free_record` appends a timestamped subsection inside the bounded block but does not start or advance the five-question workflow.

- [ ] **Step 5: Run focused and complete runtime tests**

Run: `python3 -m unittest tests.test_life_os_runtime -v`

Expected: all Daily, follow-up, command, Capture, and date tests pass.

- [ ] **Step 6: Commit Task 2**

```bash
git add donggu-obsidian/runtime/life_os.py tests/test_life_os_runtime.py
git commit -m "feat(obsidian): add resumable Life OS conversation state"
```

---

### Task 3: Attachment storage, security, and crash recovery

**Files:**
- Modify: `donggu-obsidian/runtime/life_os.py`
- Modify: `tests/test_life_os_runtime.py`

**Interfaces:**
- Produces `StoredAttachment(number: int, path: Path, sha256: str, wikilink: str)`.
- `LifeOSRuntime._store_attachments(paths: Sequence[Path]) -> tuple[StoredAttachment, ...]` is called before note rendering while holding the Vault mutation lock.
- Existing content hash is the attachment idempotency key.

- [ ] **Step 1: Write failing attachment and security tests**

```python
def test_attachment_numbering_hash_reuse_and_direct_links(self):
    cache = self.base / "cache/documents"
    cache.mkdir(parents=True)
    first = cache / "uuid-report.PDF"
    first.write_bytes(b"same bytes")
    day = date(2026, 8, 7)
    self.runtime.start_daily(day)
    result = self.runtime.record(
        "answer", message_text="첨부했어", message_key="s3:1",
        attachment_paths=[first], target_date=day,
    )
    stored = self.vault / "Life OS/Attachments/A001 - report.pdf"
    self.assertEqual(b"same bytes", stored.read_bytes())
    self.assertIn("[[Life OS/Attachments/A001 - report.pdf]]", Path(result["path"]).read_text())
    duplicate = cache / "another-name.pdf"
    duplicate.write_bytes(b"same bytes")
    self.runtime.record(
        "answer", message_text="같은 파일", message_key="s3:2",
        attachment_paths=[duplicate], target_date=day,
    )
    self.assertEqual([stored], list((self.vault / "Life OS/Attachments").iterdir()))

def test_rejects_symlink_cache_path_and_preserves_pending_question(self):
    outside = self.base / "outside.pdf"
    outside.write_bytes(b"secret")
    cache = self.base / "cache/documents"
    cache.mkdir(parents=True)
    link = cache / "link.pdf"
    link.symlink_to(outside)
    day = date(2026, 8, 7)
    self.runtime.start_daily(day)
    with self.assertRaises(LifeOSError):
        self.runtime.record(
            "answer", message_text="첨부", message_key="s4:1",
            attachment_paths=[link], target_date=day,
        )
    self.assertEqual(1, self.runtime.status(day)["next_question"])
```

- [ ] **Step 2: Run attachment tests and confirm RED**

Run: `python3 -m unittest tests.test_life_os_runtime.LifeOSRuntimeTests.test_attachment_numbering_hash_reuse_and_direct_links tests.test_life_os_runtime.LifeOSRuntimeTests.test_rejects_symlink_cache_path_and_preserves_pending_question -v`

Expected: failures because attachment storage is not implemented.

- [ ] **Step 3: Implement cache-root validation, hashing, naming, and atomic copy**

```python
@dataclass(frozen=True)
class StoredAttachment:
    number: int
    path: Path
    sha256: str
    wikilink: str

def _store_one_attachment(self, source: Path) -> StoredAttachment:
    checked = self._checked_cache_file(source)
    digest = _file_sha256(checked)
    existing = self._attachment_by_hash(digest)
    if existing is not None:
        return existing
    number = self._next_attachment_number()
    filename = f"A{number:03d} - {self._readable_name(checked.name)}"
    destination = self.attachments_root / filename
    self._atomic_copy_verified(checked, destination, digest)
    return StoredAttachment(
        number=number, path=destination, sha256=digest,
        wikilink=f"[[Life OS/Attachments/{filename}]]",
    )
```

Accept only regular non-symlink files under active Hermes `cache/images`, `cache/audio`, or `cache/documents` roots, plus explicit temporary cache roots passed by tests. Enforce the Hermes maximum attachment byte setting, sanitize basename/control/path characters, lowercase the extension, and reject conflicting destinations.

- [ ] **Step 4: Add crash-window and concurrency tests**

Add tests that inject failure immediately after attachment rename and immediately before note rename, retry the same bytes, and assert one A-number plus one note link. Add an eight-thread test that records distinct trusted keys and asserts valid JSON state, no duplicate answers, and sequential A-numbers.

- [ ] **Step 5: Run runtime security and concurrency tests**

Run: `python3 -m unittest tests.test_life_os_runtime -v`

Expected: all tests pass; no temporary file remains in `Life OS/Attachments/`.

- [ ] **Step 6: Commit Task 3**

```bash
git add donggu-obsidian/runtime/life_os.py tests/test_life_os_runtime.py
git commit -m "feat(obsidian): archive Life OS attachments atomically"
```

---

### Task 4: Hermes native tools and plugin version 1.9.1

**Files:**
- Modify: `donggu-obsidian/tools.py`
- Modify: `donggu-obsidian/__init__.py`
- Modify: `donggu-obsidian/plugin.yaml`
- Modify: `donggu-obsidian/.claude-plugin/plugin.json`
- Modify: `.claude-plugin/marketplace.json`
- Create: `tests/test_life_os_plugin.py`
- Modify: `tests/test_native_plugin_packages.py`

**Interfaces:**
- Produces native tools `donggu_life_os_status`, `donggu_life_os_start_daily`, and `donggu_life_os_record` in toolset `donggu_obsidian`.
- Reuses `_latest_trusted_user_message(session_id) -> tuple[int, str]`.
- Adds `_life_os_runtime() -> LifeOSRuntime` as a separate thread-safe singleton from the existing CORE runtime.

- [ ] **Step 1: Write failing schema, registration, and trusted-message tests**

```python
def test_life_os_tools_register_after_existing_core_surface(self):
    package = load_package(ROOT / "donggu-obsidian", "life_os_plugin_test")
    ctx = FakeContext()
    package.register(ctx)
    self.assertEqual(
        [
            "donggu_core_recovery_status", "donggu_core_plan",
            "donggu_core_receipt_status", "donggu_core_apply",
            "donggu_core_recover", "donggu_core_readback",
            "donggu_core_revoke", "donggu_core_ack",
            "donggu_life_os_status", "donggu_life_os_start_daily",
            "donggu_life_os_record",
        ],
        [item["name"] for item in ctx.tools],
    )

def test_record_handler_uses_only_hook_captured_discord_text(self):
    tools.capture_trusted_discord_turn(
        event=discord_event(content="오늘 산책했어"), gateway=gateway,
    )
    payload = json.loads(tools.handle_life_os_record(
        {"operation": "answer", "attachment_paths": []},
    ))
    self.assertTrue(payload["success"])
    runtime.record.assert_called_once_with(
        "answer", message_text="오늘 산책했어",
        message_key=mock.ANY, attachment_paths=(),
        follow_up_question=None, target_date=None,
    )
```

- [ ] **Step 2: Run plugin tests and confirm RED**

Run: `python3 -m unittest tests.test_life_os_plugin tests.test_native_plugin_packages.NativePluginPackageTests.test_obsidian_registers_exact_native_tool_surface -v`

Expected: missing schemas/handlers and old eight-tool expectation.

- [ ] **Step 3: Add strict Life OS schemas and handlers**

```python
LIFE_OS_RECORD_SCHEMA = {
    "name": "donggu_life_os_record",
    "description": "Commit one trusted Life OS Discord turn and return the next prompt.",
    "parameters": {
        "type": "object",
        "properties": {
            "operation": {"type": "string", "enum": ["answer", "skip", "pause", "resume", "capture", "free_record"]},
            "date": {"type": "string", "pattern": r"^\d{4}-\d{2}-\d{2}$"},
            "follow_up_question": {"type": "string", "minLength": 1, "maxLength": 300},
            "attachment_paths": {"type": "array", "items": {"type": "string"}, "maxItems": 10},
        },
        "required": ["operation"],
        "additionalProperties": False,
    },
}

def handle_life_os_record(args: dict, **kwargs) -> str:
    try:
        _row_id, message_text, message_key = _trusted_life_os_turn()
        result = _life_os_runtime().record(
            str(args.get("operation") or ""),
            message_text=message_text,
            message_key=message_key,
            attachment_paths=tuple(Path(value) for value in args.get("attachment_paths") or ()),
            follow_up_question=args.get("follow_up_question"),
            target_date=_optional_iso_date(args.get("date")),
        )
        return _ok(result)
    except (CoreRuntimeError, LifeOSError, ValueError, TypeError) as exc:
        return _error(exc)
```

Status and start handlers accept only an optional ISO date; start does not require a persisted user message so cron can call it in a fresh session.

- [ ] **Step 4: Register the three tools and bump every manifest to 1.9.1**

Append the Life OS registrations after the eight CORE registrations. Register the trusted-turn capture as `pre_gateway_dispatch`, declare it in `provides_hooks`, and extend `provides_tools` in the same order. Register the bundled `life-os` skill through `ctx.register_skill()` so Hermes resolves `donggu-obsidian:life-os`. Set `donggu-obsidian` to `1.9.1` in Claude JSON, Hermes YAML, and marketplace JSON. Update the Hermes description to mention both CORE and Life OS without removing the CORE contract.

- [ ] **Step 5: Run plugin and manifest tests**

Run: `python3 -m unittest tests.test_life_os_plugin tests.test_native_plugin_packages -v`

Expected: all tests pass; exactly eleven Obsidian native tools and the namespaced Life OS skill are registered, and all three version sources equal `1.9.1`.

- [ ] **Step 6: Commit Task 4**

```bash
git add donggu-obsidian/tools.py donggu-obsidian/__init__.py donggu-obsidian/plugin.yaml donggu-obsidian/.claude-plugin/plugin.json .claude-plugin/marketplace.json tests/test_life_os_plugin.py tests/test_native_plugin_packages.py
git commit -m "feat(obsidian): expose Hermes Life OS native tools"
```

---

### Task 5: Shared skill, CLI, and public documentation

**Files:**
- Create: `donggu-obsidian/skills/life-os/SKILL.md`
- Create: `donggu-obsidian/skills/life-os/scripts/life-os.py`
- Create: `tests/test_life_os_skill_contract.py`
- Modify: `donggu-obsidian/README.md`
- Modify: `README.md`

**Interfaces:**
- Claude Code command: `/donggu-obsidian:life-os`.
- Hermes channel binding skill name: `donggu-obsidian:life-os`.
- CLI actions: `status`, `start`, and `record`; JSON goes to stdout and errors to stderr with exit code 2.

- [ ] **Step 1: Write failing skill and CLI contract tests**

```python
class LifeOSSkillContractTests(unittest.TestCase):
    def test_skill_declares_questions_routes_and_native_tools(self):
        text = SKILL.read_text(encoding="utf-8")
        self.assertIn("name: life-os", text)
        for question in (
            "오늘 어떤 일이 있었나?", "감정과 에너지는 어떤가?",
            "진행한 일과 막힌 일은?", "생각·배움·결정은?",
            "내일 가장 중요한 한 가지는?",
        ):
            self.assertEqual(1, text.count(question))
        for tool in ("donggu_life_os_status", "donggu_life_os_start_daily", "donggu_life_os_record"):
            self.assertIn(tool, text)
        self.assertIn("Hermes cache path", text)
        self.assertIn("최대 2개", text)

    def test_cli_status_uses_shared_runtime(self):
        proc = subprocess.run(
            [sys.executable, str(CLI), "--vault-root", str(self.vault), "status", "--date", "2026-08-07"],
            text=True, capture_output=True, check=False,
        )
        self.assertEqual(0, proc.returncode, proc.stderr)
        self.assertEqual("not_started", json.loads(proc.stdout)["status"])
```

- [ ] **Step 2: Run skill tests and confirm RED**

Run: `python3 -m unittest tests.test_life_os_skill_contract -v`

Expected: missing `life-os` skill and CLI.

- [ ] **Step 3: Write the Hermes-first SKILL.md**

The skill must contain these exact workflow branches:

```markdown
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
```

Also document `건너뛰기`, `그만`, `이어서 하자`, free Daily record, Capture, attachment paths, two-follow-up cap, manual Claude/Codex CLI fallback, and the exact allowed Vault roots. Daily and Capture are the only supported routes.

- [ ] **Step 4: Implement the thin CLI**

```python
def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    runtime = LifeOSRuntime(
        vault_root=Path(args.vault_root),
        state_root=Path(args.state_root).expanduser(),
        timezone=ZoneInfo(args.timezone),
    )
    if args.command == "status":
        result = runtime.status(_optional_date(args.date))
    elif args.command == "start":
        result = runtime.start_daily(_optional_date(args.date), resume=args.resume)
    else:
        text = sys.stdin.read()
        result = runtime.record(
            args.operation, message_text=text,
            message_key=args.message_key or f"manual:{uuid.uuid4().hex}",
            attachment_paths=tuple(Path(value) for value in args.attachment),
            follow_up_question=args.follow_up_question,
            target_date=_optional_date(args.date),
        )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0
```

Load the shared runtime by descriptor-relative import without copying its implementation.

- [ ] **Step 5: Update README files and skill counts**

Document environment keys, Hermes plugin install command, channel binding example without real IDs, cron behavior, Claude command, Codex shared-link setup, and attachment layout. Correct the root and plugin skill counts and include `life-os` in both skill tables.

- [ ] **Step 6: Run skill and documentation tests**

Run: `python3 -m unittest tests.test_life_os_skill_contract tests.test_obsidian_content_flow_contracts -v`

Expected: all tests pass and existing content-flow skill contracts remain unchanged.

- [ ] **Step 7: Commit Task 5**

```bash
git add donggu-obsidian/skills/life-os donggu-obsidian/README.md README.md tests/test_life_os_skill_contract.py
git commit -m "feat(obsidian): add shared Life OS conversation skill"
```

---

### Task 6: Full regression, source publication, and installability

**Files:**
- Modify only files required to fix test or review findings.

**Interfaces:**
- Produces one pushed public `main` revision that Hermes can install by repository subdirectory.

- [ ] **Step 1: Run the complete repository test suite**

Run: `python3 -m unittest discover -s tests -v`

Expected: all tests pass.

- [ ] **Step 2: Run package-local legacy tests**

Run: `python3 -m unittest discover -s donggu-obsidian/skills/core-review-approval/tests -v`

Expected: all legacy CORE approval tests pass.

- [ ] **Step 3: Run static and repository checks**

```bash
python3 -m compileall -q donggu-obsidian tests
git diff --check
git status --short
```

Expected: compile succeeds, no whitespace errors, and only intentional implementation files are changed.

- [ ] **Step 4: Review the complete diff against the approved design**

Confirm every design section maps to a test or deployment step, no unrestricted Vault fallback exists, no personal path/Discord ID is committed, and the existing eight CORE tools are behaviorally unchanged.

- [ ] **Step 5: Commit any review fixes and rerun the complete suite**

```bash
git add -u
git commit -m "fix(obsidian): harden Life OS runtime boundaries"
python3 -m unittest discover -s tests -v
```

Expected: the fix commit is omitted when there are no review changes; the final suite passes either way.

- [ ] **Step 6: Push the public source and verify the remote head**

```bash
git push origin main
git ls-remote origin refs/heads/main
git rev-parse HEAD
```

Expected: the two hashes match exactly.

---

### Task 7: Deploy the plugin, Discord channel, and Hermes routing

**Files and external state:**
- Create directory: target Vault `Life OS/Attachments/`.
- Modify via official config command and one reviewed patch: `~/.hermes/config.yaml`.
- Replace install: `~/.hermes/plugins/donggu-obsidian/` from the pushed public subdirectory.
- Create symlink: `~/.codex/skills/life-os` → public canonical skill directory.
- Create or reuse: Discord `대장간 > 알림 > #life-os`.

**Interfaces:**
- Produces a concrete Discord channel ID used by routing and cron.
- Produces enabled Hermes plugin version `1.9.1` and the explicitly loadable
  plugin skill `donggu-obsidian:life-os`.

- [ ] **Step 1: Re-read the Vault rules and validate deployment prerequisites**

Run from the target Vault root:

```bash
sed -n '1,260p' 'Personal Branding/_GUIDES/RULES.md'
hermes gateway status
hermes cron status
hermes config get timezone --json
```

Expected: gateway and cron are healthy and timezone is `Asia/Seoul`.

- [ ] **Step 2: Create or reuse the Discord channel without exposing the token**

Run the following with the Hermes virtualenv Python. It loads the bot token into process memory from `~/.hermes/.env`, resolves the exact guild/category by name, verifies `Manage Channels`, reuses one exact channel match, or creates one channel. It prints only the channel ID.

```python
from dotenv import dotenv_values
from pathlib import Path
import requests

token = str(dotenv_values(Path.home() / ".hermes/.env").get("DISCORD_BOT_TOKEN") or "")
if not token:
    raise SystemExit("Discord credential is unavailable")

def request(method, path, body=None):
    response = requests.request(
        method, "https://discord.com/api/v10" + path, json=body,
        headers={
            "Authorization": "Bot " + token,
            "Content-Type": "application/json",
            "User-Agent": "Hermes-Agent (https://github.com/NousResearch/hermes-agent)",
        },
        timeout=20,
    )
    response.raise_for_status()
    return response.json()

guilds = [g for g in request("GET", "/users/@me/guilds") if g.get("name") == "대장간"]
if len(guilds) != 1:
    raise SystemExit("expected exactly one target guild")
guild = guilds[0]
if int(guild.get("permissions", "0")) & (1 << 4) == 0:
    raise SystemExit("bot lacks Manage Channels")
channels = request("GET", f"/guilds/{guild['id']}/channels")
categories = [c for c in channels if c.get("type") == 4 and c.get("name") == "알림"]
if len(categories) != 1:
    raise SystemExit("expected exactly one target category")
parent_id = categories[0]["id"]
matches = [c for c in channels if c.get("type") == 0 and c.get("name") == "life-os"]
wrong_parent = [c for c in matches if c.get("parent_id") != parent_id]
if wrong_parent or len(matches) > 1:
    raise SystemExit("ambiguous life-os channel")
channel = matches[0] if matches else request(
    "POST", f"/guilds/{guild['id']}/channels",
    {"name": "life-os", "type": 0, "parent_id": parent_id,
     "topic": "Life OS Daily check-in · Hermes Agent"},
)
readback = request("GET", f"/channels/{channel['id']}")
if (
    readback.get("guild_id") != guild["id"]
    or readback.get("type") != 0
    or readback.get("parent_id") != parent_id
    or readback.get("name") != "life-os"
):
    raise SystemExit("channel readback failed verification")
# This successful GET proves the bot can view the channel.
print(readback["id"])
```

Expected: one decimal channel ID; no token or other credential appears.

- [ ] **Step 3: Configure the Vault root and channel routing without narrowing existing channels**

Use `hermes config set --force DONGGU_LIFE_OS_VAULT_ROOT "$PWD"` from the target Vault root. Set `discord.free_response_channels` to the union of its existing CSV/list values and the resolved channel ID. Set `discord.channel_prompts.<channel-id>` to the approved Life OS-only prompt.

Because Hermes requires `channel_skill_bindings` to be a YAML list, inspect the existing `discord:` block and apply one exact patch that adds:

```yaml
channel_skill_bindings:
  - id: "the decimal ID returned by Step 2"
    skill: donggu-obsidian:life-os
```

If a bindings list already exists, append or replace only the entry with the same ID. Leave `allowed_channels` absent when absent; if it already exists, append the ID without removing entries. Run `hermes config check` after the patch.

- [ ] **Step 4: Install the pushed plugin and link the Codex skill**

```bash
hermes plugins install --force --enable donggu1105/donggu-skills/donggu-obsidian
LIFE_OS_SKILL_SOURCE="$(pwd)/donggu-obsidian/skills/life-os"
LIFE_OS_CODEX_SKILLS="$(python3 -c 'from pathlib import Path; print(Path.home() / ".codex/skills")')"
ln -s "$LIFE_OS_SKILL_SOURCE" "$LIFE_OS_CODEX_SKILLS/life-os"
```

If the Codex link already exists, verify it resolves to that exact canonical directory instead of replacing it blindly.

- [ ] **Step 5: Restart and verify Hermes discovery**

```bash
hermes gateway restart
hermes gateway status
hermes plugins list --plain --no-bundled
(cd ~/.hermes/hermes-agent && ./venv/bin/python -c 'import json; from tools.skills_tool import skill_view; result = json.loads(skill_view("donggu-obsidian:life-os", preprocess=False)); assert result.get("success"), result')
hermes tools list --platform discord
```

Expected: gateway healthy; `donggu-obsidian` enabled at `1.9.1`; qualified
`skill_view` succeeds; the plugin skill remains absent from the flat skill
index by design; `donggu_obsidian` toolset is enabled on Discord.

---

### Task 8: Create the cron and run the live smoke test

**External state:**
- Create one active Hermes cron named `Life OS 데일리 체크인 (22:00)`.
- Write the initial workflow state into today's real Daily note.
- Deliver the first real question to Discord `#life-os`.

**Interfaces:**
- Cron consumes the installed `donggu-obsidian:life-os` skill and `donggu_life_os_start_daily` tool.
- Discord replies consume the channel binding and `donggu_life_os_record` tool.

- [ ] **Step 1: Create or reconcile the unique cron job**

List jobs first and resolve the exact name to zero or one job ID. Edit that ID
when present; otherwise create the job and capture the returned ID:

```bash
LIFE_OS_VAULT_ROOT="$(pwd)"
LIFE_OS_CRON_NAME='Life OS 데일리 체크인 (22:00)'
LIFE_OS_CRON_PROMPT='Use the donggu-obsidian:life-os skill. Call donggu_life_os_start_daily for the current KST date. Return only its pending question; if completed, return 오늘 Daily 기록은 이미 완료됐어요.'
LIFE_OS_CHANNEL_ID="$(hermes --oneshot 'Read-only Discord lookup: list channels in the guild named 대장간 and return only the decimal ID of the unique text channel named life-os whose parent category is 알림. Do not mutate anything.' --toolsets discord_admin)"
case "$LIFE_OS_CHANNEL_ID" in ''|*[!0-9]*) exit 1 ;; esac

life_os_cron_ids() {
  python3 -c '
import re, sys
name = sys.argv[1]
current = None
for raw in sys.stdin:
    line = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", raw.rstrip("\n"))
    match = re.match(r"\s*([0-9a-f]{12})\b", line)
    if match:
        current = match.group(1)
    named = re.match(r"\s*Name:\s+(.*)$", line)
    if named and named.group(1) == name and current:
        print(current)
' "$LIFE_OS_CRON_NAME"
}

LIFE_OS_CRON_LIST="$(hermes cron list --all)"
LIFE_OS_CRON_IDS="$(printf '%s\n' "$LIFE_OS_CRON_LIST" | life_os_cron_ids)"
LIFE_OS_CRON_MATCH_COUNT="$(printf '%s\n' "$LIFE_OS_CRON_IDS" | sed '/^$/d' | wc -l | tr -d ' ')"
case "$LIFE_OS_CRON_MATCH_COUNT" in
  0)
    LIFE_OS_CRON_CREATE="$(hermes cron create '0 22 * * *' "$LIFE_OS_CRON_PROMPT" \
      --name "$LIFE_OS_CRON_NAME" \
      --deliver "discord:${LIFE_OS_CHANNEL_ID}" \
      --skill donggu-obsidian:life-os \
      --workdir "$LIFE_OS_VAULT_ROOT")"
    LIFE_OS_CRON_JOB_ID="$(printf '%s\n' "$LIFE_OS_CRON_CREATE" | \
      python3 -c 'import re,sys; text=sys.stdin.read(); match=re.search(r"Created job:\s*([0-9a-f]{12})\b", text); print(match.group(1) if match else "")')"
    ;;
  1)
    LIFE_OS_CRON_JOB_ID="$LIFE_OS_CRON_IDS"
    hermes cron edit "$LIFE_OS_CRON_JOB_ID" \
      --schedule '0 22 * * *' \
      --prompt "$LIFE_OS_CRON_PROMPT" \
      --name "$LIFE_OS_CRON_NAME" \
      --deliver "discord:${LIFE_OS_CHANNEL_ID}" \
      --skill donggu-obsidian:life-os \
      --workdir "$LIFE_OS_VAULT_ROOT"
    ;;
  *)
    echo 'expected exactly one cron job ID for the exact job name' >&2
    exit 1
    ;;
esac
case "$LIFE_OS_CRON_JOB_ID" in ''|*[!0-9a-f]*) exit 1 ;; esac

LIFE_OS_CRON_LIST="$(hermes cron list --all)"
LIFE_OS_CRON_IDS="$(printf '%s\n' "$LIFE_OS_CRON_LIST" | life_os_cron_ids)"
LIFE_OS_CRON_MATCH_COUNT="$(printf '%s\n' "$LIFE_OS_CRON_IDS" | sed '/^$/d' | wc -l | tr -d ' ')"
if [ "$LIFE_OS_CRON_MATCH_COUNT" != 1 ] || [ "$LIFE_OS_CRON_IDS" != "$LIFE_OS_CRON_JOB_ID" ]; then
  echo 'expected exactly one cron job ID for the exact job name' >&2
  exit 1
fi
```

Run from the target Vault root. The readback call is read-only and the
decimal-only guard fails closed before cron creation. The post-create/edit
`cron list --all` readback proves the exact name resolves to the captured
unique ID; ambiguity fails before any smoke run.

- [ ] **Step 2: Force one run and wait for a terminal execution record**

```bash
hermes cron run "$LIFE_OS_CRON_JOB_ID"
hermes cron runs "$LIFE_OS_CRON_JOB_ID" --limit 5
```

Expected: newest run reaches `completed`; scheduler remains healthy.

- [ ] **Step 3: Verify the real Daily mutation is bounded**

Read today's KST path and assert:

- exactly one `life-os:record:start` and `life-os:record:end` marker;
- one valid version-1 state with `status: active` and `next_question: 1`;
- original Project List, Habit, Energy allocation, Completed today, and LifeOS code blocks remain present;
- no external cache path, token, Discord ID, or personal absolute path appears in the note.

- [ ] **Step 4: Verify the Discord delivery read-only**

Use Hermes `discord_admin` read-only `list_channels` and `fetch_messages`/Discord core read action to confirm the target channel is under `알림` and the newest bot message contains only `오늘 어떤 일이 있었나?` plus minimal conversational framing.

- [ ] **Step 5: Verify the final deployment state**

```bash
hermes cron list
hermes cron status
hermes gateway status
hermes config check
git status --short
```

Expected: one active 22:00 job, healthy scheduler/gateway/config, and clean public repository. Record the channel ID, cron job ID, plugin version, pushed commit hash, test counts, and any live-inbound validation gap in the final handoff.
