"""Deterministic, bounded Markdown runtime for Life OS Daily notes."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict, dataclass, replace
from datetime import date, datetime
import fcntl
import json
import os
from pathlib import Path
import re
import stat
import tempfile
from typing import Any, Iterator, Sequence
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


QUESTIONS = (
    "오늘 어떤 일이 있었나?",
    "감정과 에너지는 어떤가?",
    "진행한 일과 막힌 일은?",
    "생각·배움·결정은?",
    "내일 가장 중요한 한 가지는?",
)

_START = "<!-- life-os:record:start -->"
_END = "<!-- life-os:record:end -->"
_STATE_PREFIX = "%% life-os-state: "
_STATE_PATTERN = re.compile(r"(?m)^%% life-os-state: ([^\r\n]+) %%(?:\r?\n|$)")
_SNAPSHOT_LINE = re.compile(r"(?m)^<% LifeOS\.Project\.snapshot\(\) %>(?:\r?\n|$)")
_TEMPLATE_EXPRESSION = re.compile(r"<%.*?%>", re.DOTALL)
_DAILY_HEADING = "## Daily Record"
_PLACEHOLDER = "%%Your Record%%"
_ALLOWED_STATUSES = {"not_started", "active", "paused", "completed"}
_DIRECTORY = getattr(os, "O_DIRECTORY", 0)
_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)


class LifeOSError(Exception):
    """The configured Life OS data cannot be read or safely mutated."""


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


@dataclass(frozen=True)
class _Document:
    prefix: str
    content: str
    suffix: str


def _checked_directory(value: Path) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        raise LifeOSError("Vault root must be absolute")
    try:
        info = path.lstat()
    except OSError:
        raise LifeOSError("Vault root is unavailable") from None
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
        raise LifeOSError("Vault root must be a non-symlink directory")
    return path


def _checked_child(parent: Path, name: str) -> Path:
    child = parent / name
    try:
        info = child.lstat()
    except OSError:
        raise LifeOSError(f"{name} directory is unavailable") from None
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
        raise LifeOSError(f"{name} must be a non-symlink directory")
    return child


def _prepare_private_state_root(value: Path) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        raise LifeOSError("State root must be absolute")
    created = False
    try:
        try:
            path.mkdir(parents=True, mode=0o700)
            created = True
        except FileExistsError:
            pass
        info = path.lstat()
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
            raise LifeOSError("State root must be a non-symlink directory")
        if created:
            os.chmod(path, 0o700)
            info = path.lstat()
        if info.st_uid != os.geteuid():
            raise LifeOSError("Existing state root must be owned by the current user")
        if stat.S_IMODE(info.st_mode) != 0o700:
            raise LifeOSError("Existing state root must have mode 0700")
    except LifeOSError:
        raise
    except OSError:
        raise LifeOSError("State root is unavailable") from None
    return path


def _checked_external_state_root(vault_root: Path, value: Path) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        raise LifeOSError("State root must be absolute")
    existing_ancestor = path
    try:
        while True:
            try:
                existing_ancestor.lstat()
                break
            except FileNotFoundError:
                parent = existing_ancestor.parent
                if parent == existing_ancestor:
                    raise LifeOSError("State root ancestry is unavailable")
                existing_ancestor = parent
        current = Path(os.path.realpath(existing_ancestor))
        while True:
            if os.path.samefile(current, vault_root):
                raise LifeOSError("State root must be outside the Vault")
            parent = current.parent
            if parent == current:
                break
            current = parent
    except LifeOSError:
        raise
    except OSError:
        raise LifeOSError("State root ancestry is unavailable") from None
    canonical_vault = Path(os.path.realpath(vault_root))
    canonical_state = Path(os.path.realpath(path))
    try:
        canonical_state.relative_to(canonical_vault)
    except ValueError:
        return path
    raise LifeOSError("State root must be outside the Vault")


def _canonical_state(state: WorkflowState) -> str:
    return json.dumps(asdict(state), ensure_ascii=False, separators=(",", ":"), sort_keys=True)


class LifeOSRuntime:
    """Owns Daily creation and mutations inside one explicit Markdown block."""

    QUESTIONS = QUESTIONS

    def __init__(self, *, vault_root: Path, state_root: Path, timezone: ZoneInfo):
        if not isinstance(timezone, ZoneInfo) or timezone.key != "Asia/Seoul":
            raise LifeOSError("Timezone must be Asia/Seoul")
        self.timezone = timezone
        self.vault_root = _checked_directory(vault_root)
        self.life_root = _checked_child(self.vault_root, "Life OS")
        self.periodic_root = _checked_child(self.life_root, "0. PeriodicNotes")
        self.template_root = _checked_child(self.periodic_root, "Templates")
        external_state_root = _checked_external_state_root(self.vault_root, state_root)
        self.state_root = _prepare_private_state_root(external_state_root)
        template = self._template_path()
        try:
            template_info = template.lstat()
        except OSError:
            raise LifeOSError("Daily template is unavailable") from None
        if stat.S_ISLNK(template_info.st_mode) or not stat.S_ISREG(template_info.st_mode):
            raise LifeOSError("Daily template must be a non-symlink file")

    @classmethod
    def from_environment(cls) -> "LifeOSRuntime":
        raw_vault = os.environ.get("DONGGU_LIFE_OS_VAULT_ROOT")
        if not raw_vault:
            raise LifeOSError("DONGGU_LIFE_OS_VAULT_ROOT is required")
        raw_state = os.environ.get("DONGGU_LIFE_OS_STATE_ROOT")
        if raw_state:
            state_root = Path(raw_state).expanduser()
        else:
            xdg_state = os.environ.get("XDG_STATE_HOME")
            state_root = (Path(xdg_state).expanduser() if xdg_state else Path.home() / ".local/state") / "donggu-life-os"
        timezone_name = os.environ.get("DONGGU_LIFE_OS_TIMEZONE", "Asia/Seoul")
        try:
            timezone = ZoneInfo(timezone_name)
        except (ZoneInfoNotFoundError, ValueError):
            raise LifeOSError("DONGGU_LIFE_OS_TIMEZONE is invalid") from None
        return cls(vault_root=Path(raw_vault).expanduser(), state_root=state_root, timezone=timezone)

    def daily_path(self, value: date) -> Path:
        if not isinstance(value, date):
            raise LifeOSError("Daily date is invalid")
        return self.periodic_root / f"{value:%Y}" / "Daily" / f"{value:%m}" / f"{value:%Y-%m-%d}.md"

    def status(self, target_date: date | None = None) -> dict[str, Any]:
        selected = target_date or datetime.now(self.timezone).date()
        with self._mutation_lock():
            path = self.daily_path(selected)
            if not path.exists():
                return self._result(path, self._initial_state(selected))
            text = self._read_document(path)
            if text.count(_START) == 0 and text.count(_END) == 0 and _STATE_PREFIX not in text:
                return self._result(path, self._initial_state(selected))
            document, state = self._parse_block(text, selected)
            del document
            return self._result(path, state)

    def start_daily(self, target_date: date | None = None, *, resume: bool = False) -> dict[str, Any]:
        selected = target_date or datetime.now(self.timezone).date()
        with self._mutation_lock():
            path = self._ensure_daily(selected)
            document, state = self._read_or_install_block(path, selected)
            if state.status == "not_started" or (resume and state.status == "paused"):
                state = replace(state, status="active")
                self._commit_document(path, self._render(document, state))
            return self._result(path, state)

    def record(
        self,
        operation: str,
        *,
        message_text: str,
        message_key: str,
        attachment_paths: Sequence[Path] = (),
        follow_up_question: str | None = None,
        target_date: date | None = None,
    ) -> dict[str, Any]:
        if operation != "answer":
            raise LifeOSError("unsupported Life OS operation")
        if attachment_paths or follow_up_question is not None:
            raise LifeOSError("attachments and follow-ups are not supported yet")
        text = self._checked_message(message_text)
        key = self._checked_message_key(message_key)
        selected = target_date or datetime.now(self.timezone).date()
        with self._mutation_lock():
            path = self._ensure_daily(selected)
            document, state = self._read_or_install_block(path, selected)
            if state.status == "not_started":
                state = replace(state, status="active")
            if state.status != "active" or state.next_question is None:
                raise LifeOSError("Daily workflow is not accepting an answer")
            question_number = state.next_question
            answered = tuple(sorted((*state.answered, question_number)))
            next_question = question_number + 1 if question_number < len(self.QUESTIONS) else None
            status = "active" if next_question is not None else "completed"
            entry = (
                f"#### {question_number}. {self.QUESTIONS[question_number - 1]}\n"
                f"{text}\n"
                f"%% life-os-message: {key} %%\n\n"
            )
            state = replace(
                state,
                status=status,
                next_question=next_question,
                answered=answered,
                last_message_key=key,
            )
            document = replace(document, content=document.content + entry)
            self._commit_document(path, self._render(document, state))
            return self._result(path, state)

    def _template_path(self) -> Path:
        return self.template_root / "Daily.md"

    def _initial_state(self, selected: date) -> WorkflowState:
        return WorkflowState(
            version=1,
            date=selected.isoformat(),
            status="not_started",
            next_question=1,
            answered=(),
            skipped=(),
            follow_up_count=0,
            pending_follow_up=None,
            last_message_key=None,
        )

    @contextmanager
    def _mutation_lock(self) -> Iterator[None]:
        lock_path = self.state_root / "mutation.lock"
        flags = os.O_CREAT | os.O_RDWR | _NOFOLLOW
        try:
            descriptor = os.open(lock_path, flags, 0o600)
        except OSError:
            raise LifeOSError("Life OS mutation lock is unavailable") from None
        with os.fdopen(descriptor, "a+b", closefd=True) as stream:
            try:
                os.fchmod(stream.fileno(), 0o600)
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
                yield
            finally:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)

    def _ensure_daily(self, selected: date) -> Path:
        path = self.daily_path(selected)
        if path.exists():
            info = path.lstat()
            if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
                raise LifeOSError("Daily note must be a non-symlink file")
            return path
        try:
            template = self._template_path().read_bytes().decode("utf-8")
        except (OSError, UnicodeError):
            raise LifeOSError("Daily template is unreadable") from None
        rendered, count = _SNAPSHOT_LINE.subn("", template)
        if count > 1 or _TEMPLATE_EXPRESSION.search(rendered) or "<%" in rendered:
            raise LifeOSError("Daily template contains an unsupported expression")
        self._prepare_daily_parent(selected)
        self._atomic_replace(path, rendered)
        return path

    def _prepare_daily_parent(self, selected: date) -> Path:
        current = self.periodic_root
        for name in (f"{selected:%Y}", "Daily", f"{selected:%m}"):
            child = current / name
            try:
                child.mkdir(mode=0o755, exist_ok=True)
                info = child.lstat()
            except OSError:
                raise LifeOSError("Daily directory is unavailable") from None
            if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
                raise LifeOSError("Daily directory must be a non-symlink directory")
            current = child
        return current

    def _read_or_install_block(self, path: Path, selected: date) -> tuple[_Document, WorkflowState]:
        text = self._read_document(path)
        start_count, end_count = text.count(_START), text.count(_END)
        if start_count == 0 and end_count == 0:
            if _STATE_PREFIX in text:
                raise LifeOSError("Daily note contains an orphaned Life OS state")
            document = self._install_block(text)
            state = self._initial_state(selected)
            self._commit_document(path, self._render(document, state))
            return document, state
        return self._parse_block(text, selected)

    def _read_block(self, path: Path, selected: date) -> tuple[_Document, WorkflowState]:
        return self._parse_block(self._read_document(path), selected)

    def _read_document(self, path: Path) -> str:
        try:
            info = path.lstat()
            if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
                raise LifeOSError("Daily note must be a non-symlink file")
            return path.read_bytes().decode("utf-8")
        except LifeOSError:
            raise
        except (OSError, UnicodeError):
            raise LifeOSError("Daily note is unreadable") from None

    def _install_block(self, text: str) -> _Document:
        heading_pattern = re.compile(rf"(?m)^{re.escape(_DAILY_HEADING)}(?:\r?\n|$)")
        headings = list(heading_pattern.finditer(text))
        if len(headings) != 1:
            raise LifeOSError("Daily note must contain one Daily Record heading")
        split_at = headings[0].end()
        prefix, suffix = text[:split_at], text[split_at:]
        placeholder = re.match(rf"{re.escape(_PLACEHOLDER)}(?:\r?\n|$)", suffix)
        if placeholder:
            suffix = suffix[placeholder.end():]
        return _Document(prefix=prefix, content="\n### Daily Check-in\n\n", suffix=suffix)

    def _parse_block(self, text: str, selected: date) -> tuple[_Document, WorkflowState]:
        if text.count(_START) != 1 or text.count(_END) != 1:
            raise LifeOSError("Daily note contains duplicate or malformed Life OS blocks")
        if text.index(_START) > text.index(_END):
            raise LifeOSError("Daily note contains malformed Life OS block markers")
        prefix, remainder = text.split(_START, 1)
        block, suffix = remainder.split(_END, 1)
        if _START in block or _END in prefix or _START in suffix or _END in suffix:
            raise LifeOSError("Daily note contains malformed Life OS block markers")
        matches = list(_STATE_PATTERN.finditer(block))
        if len(matches) != 1 or text.count(_STATE_PREFIX) != 1:
            raise LifeOSError("Daily note must contain one Life OS state")
        match = matches[0]
        raw = match.group(1)
        try:
            payload = json.loads(raw)
            state = self._validated_state(payload, selected)
        except (json.JSONDecodeError, TypeError, ValueError):
            raise LifeOSError("Daily note contains malformed Life OS state") from None
        if raw != _canonical_state(state):
            raise LifeOSError("Daily note contains non-canonical Life OS state")
        content = block[:match.start()] + block[match.end():]
        return _Document(prefix=prefix, content=content, suffix=suffix), state

    def _validated_state(self, payload: Any, selected: date) -> WorkflowState:
        fields = tuple(WorkflowState.__dataclass_fields__)
        if not isinstance(payload, dict) or set(payload) != set(fields):
            raise ValueError("invalid state fields")
        if payload["version"] != 1 or isinstance(payload["version"], bool):
            raise ValueError("invalid state version")
        if payload["date"] != selected.isoformat() or payload["status"] not in _ALLOWED_STATUSES:
            raise ValueError("invalid state binding")
        next_question = payload["next_question"]
        if next_question is not None and (isinstance(next_question, bool) or not isinstance(next_question, int) or not 1 <= next_question <= len(QUESTIONS)):
            raise ValueError("invalid next question")
        answered = self._question_tuple(payload["answered"])
        skipped = self._question_tuple(payload["skipped"])
        if set(answered) & set(skipped) or next_question in set(answered) | set(skipped):
            raise ValueError("contradictory question state")
        follow_up_count = payload["follow_up_count"]
        if isinstance(follow_up_count, bool) or not isinstance(follow_up_count, int) or not 0 <= follow_up_count <= 2:
            raise ValueError("invalid follow-up count")
        pending = payload["pending_follow_up"]
        if pending is not None:
            if set(pending) != {"for_question", "question"} or pending["for_question"] not in answered or not isinstance(pending["question"], str) or not pending["question"]:
                raise ValueError("invalid pending follow-up")
        last_key = payload["last_message_key"]
        if last_key is not None and (not isinstance(last_key, str) or not last_key):
            raise ValueError("invalid last message key")
        status = payload["status"]
        if status == "not_started" and (answered or skipped or next_question != 1):
            raise ValueError("invalid not-started state")
        if status == "completed" and (next_question is not None or set(answered) | set(skipped) != set(range(1, len(QUESTIONS) + 1))):
            raise ValueError("invalid completed state")
        if status in {"active", "paused"}:
            if next_question is None:
                raise ValueError("invalid incomplete state")
            expected_progress = set(range(1, next_question))
            if set(answered) | set(skipped) != expected_progress:
                raise ValueError("noncontiguous question state")
        return WorkflowState(
            version=1,
            date=payload["date"],
            status=status,
            next_question=next_question,
            answered=answered,
            skipped=skipped,
            follow_up_count=follow_up_count,
            pending_follow_up=pending,
            last_message_key=last_key,
        )

    @staticmethod
    def _question_tuple(value: Any) -> tuple[int, ...]:
        if not isinstance(value, list) or any(isinstance(item, bool) or not isinstance(item, int) for item in value):
            raise ValueError("invalid question list")
        result = tuple(value)
        if result != tuple(sorted(set(result))) or any(not 1 <= item <= len(QUESTIONS) for item in result):
            raise ValueError("invalid question list")
        return result

    @staticmethod
    def _checked_message(value: str) -> str:
        if not isinstance(value, str) or not value.strip() or len(value.encode("utf-8")) > 100_000:
            raise LifeOSError("message text is invalid")
        if any(marker in value for marker in (_START, _END, _STATE_PREFIX)):
            raise LifeOSError("message text contains a reserved marker")
        return value.strip()

    @staticmethod
    def _checked_message_key(value: str) -> str:
        if not isinstance(value, str) or not value or len(value.encode("utf-8")) > 512 or any(char in value for char in "\r\n%"):
            raise LifeOSError("message key is invalid")
        return value

    def _render(self, document: _Document, state: WorkflowState) -> str:
        content = document.content
        if content and not content.endswith(("\n", "\r")):
            content += "\n"
        state_line = f"{_STATE_PREFIX}{_canonical_state(state)} %%\n"
        return document.prefix + _START + content + state_line + _END + document.suffix

    def _commit_document(self, path: Path, text: str) -> None:
        self._atomic_replace(path, text)

    @staticmethod
    def _atomic_replace(path: Path, text: str) -> None:
        data = text.encode("utf-8")
        descriptor = -1
        temp_name = ""
        try:
            descriptor, temp_name = tempfile.mkstemp(prefix=f".{path.name}.life-os-", dir=str(path.parent))
            with os.fdopen(descriptor, "wb", closefd=True) as stream:
                descriptor = -1
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp_name, path)
            temp_name = ""
            directory_fd = os.open(path.parent, os.O_RDONLY | _DIRECTORY | _NOFOLLOW)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        except OSError:
            raise LifeOSError("Daily note could not be committed atomically") from None
        finally:
            if descriptor >= 0:
                os.close(descriptor)
            if temp_name:
                try:
                    os.unlink(temp_name)
                except OSError:
                    pass

    def _result(self, path: Path, state: WorkflowState, **extra: Any) -> dict[str, Any]:
        result: dict[str, Any] = {
            "path": str(path),
            **asdict(state),
            "answered": list(state.answered),
            "skipped": list(state.skipped),
            "question": (
                state.pending_follow_up["question"]
                if state.pending_follow_up is not None
                else self.QUESTIONS[state.next_question - 1] if state.next_question is not None else None
            ),
        }
        result.update(extra)
        return result


__all__ = ["LifeOSError", "LifeOSRuntime", "WorkflowState"]
