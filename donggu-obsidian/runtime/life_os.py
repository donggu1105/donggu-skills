"""Deterministic, bounded Markdown runtime for Life OS Daily notes."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict, dataclass, replace
from datetime import date, datetime, timedelta
import fcntl
import hashlib
import importlib
import json
import os
from pathlib import Path
import re
import secrets
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
_MESSAGE_PREFIX = "%% life-os-message: "
_STATE_PATTERN = re.compile(r"(?m)^%% life-os-state: ([^\r\n]+) %%(?:\r?\n|$)")
_SNAPSHOT_LINE = re.compile(r"(?m)^<% LifeOS\.Project\.snapshot\(\) %>(?:\r?\n|$)")
_TEMPLATE_EXPRESSION = re.compile(r"<%.*?%>", re.DOTALL)
_DAILY_HEADING = "## Daily Record"
_PLACEHOLDER = "%%Your Record%%"
_ALLOWED_STATUSES = {"not_started", "active", "paused", "completed"}
_DIRECTORY = getattr(os, "O_DIRECTORY", 0)
_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)
_ATTACHMENT_NAME = re.compile(r"^A(\d{3,}) - (.+)$")
_DEFAULT_MAX_ATTACHMENT_BYTES = 32 * 1024 * 1024


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
class StoredAttachment:
    number: int
    path: Path
    sha256: str
    wikilink: str


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


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    descriptor = -1
    try:
        before = path.lstat()
        if stat.S_ISLNK(before.st_mode) or not stat.S_ISREG(before.st_mode):
            raise LifeOSError("cache attachment must be a non-symlink regular file")
        descriptor = os.open(path, os.O_RDONLY | _NOFOLLOW)
        if not os.path.samestat(before, os.fstat(descriptor)):
            raise LifeOSError("cache attachment changed during validation")
        with os.fdopen(descriptor, "rb", closefd=True) as stream:
            descriptor = -1
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    except LifeOSError:
        raise
    except OSError:
        raise LifeOSError("cache attachment is unavailable") from None
    finally:
        if descriptor >= 0:
            os.close(descriptor)
    return digest.hexdigest()


def _file_sha256_at(directory_fd: int, name: str) -> str:
    digest = hashlib.sha256()
    descriptor = -1
    try:
        before = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        if stat.S_ISLNK(before.st_mode) or not stat.S_ISREG(before.st_mode):
            raise LifeOSError("stored attachment must be a non-symlink regular file")
        descriptor = os.open(name, os.O_RDONLY | _NOFOLLOW, dir_fd=directory_fd)
        if not os.path.samestat(before, os.fstat(descriptor)):
            raise LifeOSError("stored attachment changed during validation")
        with os.fdopen(descriptor, "rb", closefd=True) as stream:
            descriptor = -1
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    except LifeOSError:
        raise
    except OSError:
        raise LifeOSError("stored attachment is unavailable") from None
    finally:
        if descriptor >= 0:
            os.close(descriptor)
    return digest.hexdigest()


class LifeOSRuntime:
    """Owns Daily creation and mutations inside one explicit Markdown block."""

    QUESTIONS = QUESTIONS

    def __init__(
        self,
        *,
        vault_root: Path,
        state_root: Path,
        timezone: ZoneInfo,
        cache_roots: Sequence[Path] | None = None,
        max_attachment_bytes: int | None = None,
    ):
        if not isinstance(timezone, ZoneInfo) or timezone.key != "Asia/Seoul":
            raise LifeOSError("Timezone must be Asia/Seoul")
        self.timezone = timezone
        self.vault_root = _checked_directory(vault_root)
        self.life_root = _checked_child(self.vault_root, "Life OS")
        self._vault_identity = self.vault_root.lstat()
        self._life_identity = self.life_root.lstat()
        self.periodic_root = _checked_child(self.life_root, "0. PeriodicNotes")
        self.template_root = _checked_child(self.periodic_root, "Templates")
        self.cache_roots = tuple(Path(root).expanduser() for root in cache_roots) if cache_roots is not None else None
        if max_attachment_bytes is not None:
            if isinstance(max_attachment_bytes, bool) or not isinstance(max_attachment_bytes, int) or max_attachment_bytes < 0:
                raise LifeOSError("maximum attachment bytes is invalid")
            self.max_attachment_bytes = max_attachment_bytes
        else:
            raw_limit = os.environ.get("DISCORD_MAX_ATTACHMENT_BYTES")
            try:
                self.max_attachment_bytes = max(0, int(raw_limit)) if raw_limit not in {None, ""} else _DEFAULT_MAX_ATTACHMENT_BYTES
            except ValueError:
                self.max_attachment_bytes = _DEFAULT_MAX_ATTACHMENT_BYTES
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

    def capture_path(self, value: date) -> Path:
        if not isinstance(value, date):
            raise LifeOSError("Capture date is invalid")
        return self.life_root / "-1. Capture" / f"{value:%Y-%m-%d}.md"

    def resolve_target_date(self, command: str | None = None) -> date:
        if command not in {None, "yesterday"}:
            raise LifeOSError("unsupported Life OS date command")
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

    def status(self, target_date: date | None = None) -> dict[str, Any]:
        selected = target_date or self.resolve_target_date()
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
        if operation not in {"answer", "skip", "pause", "resume", "capture", "free_record"}:
            raise LifeOSError("unsupported Life OS operation")
        text = self._checked_message(message_text)
        key = self._checked_message_key(message_key)
        selected = target_date or self.resolve_target_date()
        with self._mutation_lock():
            if operation == "capture":
                return self._append_capture(selected, text, key, attachment_paths)
            path = self._ensure_daily(selected)
            document, state = self._read_or_install_block(path, selected)
            if self._message_already_committed(document.content, key):
                return self._result(path, state, duplicate=True)
            stored = self._store_attachments(attachment_paths)
            text = self._text_with_attachments(text, stored)
            document, state = self._apply_operation(
                document,
                state,
                operation,
                text,
                key,
                follow_up_question=follow_up_question,
            )
            self._commit_document(path, self._render(document, state))
            return self._result(path, state)

    def _apply_operation(
        self,
        document: _Document,
        state: WorkflowState,
        operation: str,
        text: str,
        key: str,
        *,
        follow_up_question: str | None,
    ) -> tuple[_Document, WorkflowState]:
        if operation == "free_record":
            if follow_up_question is not None:
                raise LifeOSError("follow-up requires a core answer")
            entry = self._timestamped_entry("Free Record", text, key)
            return replace(document, content=document.content + entry), replace(state, last_message_key=key)

        if operation == "pause":
            if follow_up_question is not None or state.status != "active":
                raise LifeOSError("Daily workflow cannot be paused")
            entry = self._control_entry("Paused", text, key)
            return replace(document, content=document.content + entry), replace(
                state, status="paused", last_message_key=key,
            )

        if operation == "resume":
            if follow_up_question is not None or state.status != "paused":
                raise LifeOSError("Daily workflow cannot be resumed")
            entry = self._control_entry("Resumed", text, key)
            return replace(document, content=document.content + entry), replace(
                state, status="active", last_message_key=key,
            )

        if state.pending_follow_up is not None:
            if state.status == "paused":
                raise LifeOSError("Daily workflow is not accepting a response")
            if operation == "skip":
                response = "건너뛰기"
            else:
                response = text
            pending = state.pending_follow_up
            entry = (
                f"##### Follow-up: {pending['question']}\n"
                f"{response}\n"
                f"%% life-os-message: {key} %%\n\n"
            )
            return replace(document, content=document.content + entry), replace(
                state, pending_follow_up=None, last_message_key=key,
            )

        if state.status == "not_started":
            state = replace(state, status="active")
        if state.status != "active" or state.next_question is None:
            raise LifeOSError("Daily workflow is not accepting a response")

        question_number = state.next_question
        if operation == "skip":
            if follow_up_question is not None:
                raise LifeOSError("follow-up requires a core answer")
            answered = state.answered
            skipped = tuple(sorted((*state.skipped, question_number)))
            response = "건너뛰기"
        else:
            answered = tuple(sorted((*state.answered, question_number)))
            skipped = state.skipped
            response = text
        next_question = question_number + 1 if question_number < len(self.QUESTIONS) else None
        status = "active" if next_question is not None else "completed"
        pending_follow_up = None
        follow_up_count = state.follow_up_count
        if operation == "answer" and follow_up_question is not None and follow_up_count < 2:
            question = self._checked_follow_up(follow_up_question)
            pending_follow_up = {"for_question": question_number, "question": question}
            follow_up_count += 1
        entry = (
            f"#### {question_number}. {self.QUESTIONS[question_number - 1]}\n"
            f"{response}\n"
            f"%% life-os-message: {key} %%\n\n"
        )
        next_state = replace(
            state,
            status=status,
            next_question=next_question,
            answered=answered,
            skipped=skipped,
            follow_up_count=follow_up_count,
            pending_follow_up=pending_follow_up,
            last_message_key=key,
        )
        return replace(document, content=document.content + entry), next_state

    def _optional_state(self, selected: date) -> WorkflowState | None:
        path = self.daily_path(selected)
        if not path.exists():
            return None
        text = self._read_document(path)
        if text.count(_START) == 0 and text.count(_END) == 0 and _STATE_PREFIX not in text:
            return None
        _document, state = self._parse_block(text, selected)
        return state

    def _append_capture(
        self, selected: date, text: str, key: str, attachment_paths: Sequence[Path],
    ) -> dict[str, Any]:
        path = self.capture_path(selected)
        with self._capture_directory() as directory_fd:
            document = self._read_capture_at(directory_fd, path.name)
            if document is not None:
                if self._message_already_committed(document, key):
                    return {"path": str(path), "date": selected.isoformat(), "status": "captured", "duplicate": True}
            else:
                document = f"# Capture — {selected.isoformat()}\n\n"
            stored = self._store_attachments(attachment_paths)
            text = self._text_with_attachments(text, stored)
            entry = self._timestamped_entry("Capture", text, key)
            self._atomic_replace_at(directory_fd, path.name, document + entry)
        return {"path": str(path), "date": selected.isoformat(), "status": "captured", "duplicate": False}

    @property
    def attachments_root(self) -> Path:
        return self.life_root / "Attachments"

    def _store_attachments(self, paths: Sequence[Path]) -> tuple[StoredAttachment, ...]:
        return tuple(self._store_one_attachment(Path(path)) for path in paths)

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
            number=number,
            path=destination,
            sha256=digest,
            wikilink=f"[[Life OS/Attachments/{filename}]]",
        )

    def _checked_cache_file(self, source: Path) -> Path:
        path = source.expanduser()
        if not path.is_absolute():
            raise LifeOSError("cache attachment path must be absolute")
        matching_root = None
        relative_parts: tuple[str, ...] = ()
        for candidate in self._active_cache_roots():
            root = Path(candidate).expanduser()
            try:
                relative = path.relative_to(root)
            except ValueError:
                continue
            if ".." in relative.parts:
                continue
            matching_root = root
            relative_parts = relative.parts
            break
        if matching_root is None:
            raise LifeOSError("cache attachment path is outside allowed cache roots")
        try:
            root_info = matching_root.lstat()
            if stat.S_ISLNK(root_info.st_mode) or not stat.S_ISDIR(root_info.st_mode):
                raise LifeOSError("cache attachment root must be a non-symlink directory")
            current = matching_root
            for name in relative_parts[:-1]:
                current = current / name
                info = current.lstat()
                if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
                    raise LifeOSError("cache attachment ancestry must contain only directories")
            info = path.lstat()
        except LifeOSError:
            raise
        except OSError:
            raise LifeOSError("cache attachment is unavailable") from None
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
            raise LifeOSError("cache attachment must be a non-symlink regular file")
        if self.max_attachment_bytes and info.st_size > self.max_attachment_bytes:
            raise LifeOSError("cache attachment exceeds the configured size limit")
        return path

    def _active_cache_roots(self) -> tuple[Path, ...]:
        if self.cache_roots is not None:
            return self.cache_roots
        try:
            module = importlib.import_module("hermes_constants")
            get_hermes_dir = module.get_hermes_dir
            roots = tuple(
                Path(get_hermes_dir(new_subpath, old_name)).expanduser()
                for new_subpath, old_name in (
                    ("cache/images", "image_cache"),
                    ("cache/audio", "audio_cache"),
                    ("cache/documents", "document_cache"),
                )
            )
        except Exception:
            raise LifeOSError("active Hermes cache roots are unavailable") from None
        if any(not root.is_absolute() for root in roots):
            raise LifeOSError("active Hermes cache roots must be absolute")
        return roots

    @contextmanager
    def _attachments_directory(self) -> Iterator[int]:
        vault_fd = -1
        life_fd = -1
        attachments_fd = -1
        try:
            vault_fd = os.open(self.vault_root, os.O_RDONLY | _DIRECTORY | _NOFOLLOW)
            if not os.path.samestat(self._vault_identity, os.fstat(vault_fd)):
                raise LifeOSError("Vault root changed after runtime construction")
            life_fd = os.open("Life OS", os.O_RDONLY | _DIRECTORY | _NOFOLLOW, dir_fd=vault_fd)
            if not os.path.samestat(self._life_identity, os.fstat(life_fd)):
                raise LifeOSError("Life OS directory changed after runtime construction")
            try:
                os.mkdir("Attachments", mode=0o755, dir_fd=life_fd)
            except FileExistsError:
                pass
            before = os.stat("Attachments", dir_fd=life_fd, follow_symlinks=False)
            if stat.S_ISLNK(before.st_mode) or not stat.S_ISDIR(before.st_mode):
                raise LifeOSError("attachment directory must be a non-symlink directory")
            attachments_fd = os.open(
                "Attachments", os.O_RDONLY | _DIRECTORY | _NOFOLLOW, dir_fd=life_fd,
            )
            if not os.path.samestat(before, os.fstat(attachments_fd)):
                raise LifeOSError("attachment directory changed during validation")
        except LifeOSError:
            if attachments_fd >= 0:
                os.close(attachments_fd)
            if life_fd >= 0:
                os.close(life_fd)
            if vault_fd >= 0:
                os.close(vault_fd)
            raise
        except OSError:
            if attachments_fd >= 0:
                os.close(attachments_fd)
            if life_fd >= 0:
                os.close(life_fd)
            if vault_fd >= 0:
                os.close(vault_fd)
            raise LifeOSError("attachment directory is unavailable") from None
        try:
            yield attachments_fd
        finally:
            if attachments_fd >= 0:
                os.close(attachments_fd)
            if life_fd >= 0:
                os.close(life_fd)
            if vault_fd >= 0:
                os.close(vault_fd)

    def _attachment_by_hash(self, digest: str) -> StoredAttachment | None:
        with self._attachments_directory() as directory_fd:
            try:
                entries = tuple(os.listdir(directory_fd))
            except OSError:
                raise LifeOSError("attachment directory is unreadable") from None
            for name in entries:
                match = _ATTACHMENT_NAME.fullmatch(name)
                if match is None:
                    continue
                try:
                    info = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
                except OSError:
                    raise LifeOSError("stored attachment is unavailable") from None
                if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
                    continue
                if _file_sha256_at(directory_fd, name) == digest:
                    path = self.attachments_root / name
                    return StoredAttachment(
                        number=int(match.group(1)),
                        path=path,
                        sha256=digest,
                        wikilink=f"[[Life OS/Attachments/{name}]]",
                    )
        return None

    def _next_attachment_number(self) -> int:
        highest = 0
        with self._attachments_directory() as directory_fd:
            try:
                for name in os.listdir(directory_fd):
                    match = _ATTACHMENT_NAME.fullmatch(name)
                    if match is None:
                        continue
                    info = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
                    if stat.S_ISREG(info.st_mode):
                        highest = max(highest, int(match.group(1)))
            except OSError:
                raise LifeOSError("attachment directory is unreadable") from None
        return highest + 1

    @staticmethod
    def _readable_name(source_name: str) -> str:
        stem, extension = os.path.splitext(source_name)
        if stem.lower().startswith("uuid-"):
            stem = stem[5:]
        stem = re.sub(r'[<>:"/\\|?*\[\]#^\x00-\x1f\x7f]+', " ", stem)
        stem = re.sub(r"\s+", " ", stem).strip(" .-") or "attachment"
        extension = re.sub(r"[^A-Za-z0-9]", "", extension).lower()
        return f"{stem[:120]}{('.' + extension) if extension else ''}"

    def _atomic_copy_verified(self, source: Path, destination: Path, digest: str) -> None:
        if destination.parent != self.attachments_root:
            raise LifeOSError("attachment destination conflicts with an existing file")
        descriptor = -1
        source_descriptor = -1
        temp_name = ""
        try:
            source_info = source.lstat()
            if stat.S_ISLNK(source_info.st_mode) or not stat.S_ISREG(source_info.st_mode):
                raise LifeOSError("cache attachment must remain a non-symlink regular file")
            source_descriptor = os.open(source, os.O_RDONLY | _NOFOLLOW)
            if not os.path.samestat(source_info, os.fstat(source_descriptor)):
                raise LifeOSError("cache attachment changed while being opened")
            with self._attachments_directory() as directory_fd:
                for _attempt in range(10):
                    candidate = f".life-os-attachment-{secrets.token_hex(8)}"
                    try:
                        descriptor = os.open(
                            candidate,
                            os.O_CREAT | os.O_EXCL | os.O_WRONLY | _NOFOLLOW,
                            0o600,
                            dir_fd=directory_fd,
                        )
                        temp_name = candidate
                        break
                    except FileExistsError:
                        continue
                if descriptor < 0:
                    raise OSError("temporary attachment allocation failed")
                hasher = hashlib.sha256()
                with os.fdopen(source_descriptor, "rb", closefd=True) as input_stream, os.fdopen(
                    descriptor, "wb", closefd=True,
                ) as output_stream:
                    source_descriptor = -1
                    descriptor = -1
                    total = 0
                    for chunk in iter(lambda: input_stream.read(1024 * 1024), b""):
                        total += len(chunk)
                        if self.max_attachment_bytes and total > self.max_attachment_bytes:
                            raise LifeOSError("cache attachment exceeds the configured size limit")
                        output_stream.write(chunk)
                        hasher.update(chunk)
                    output_stream.flush()
                    os.fsync(output_stream.fileno())
                if hasher.hexdigest() != digest:
                    raise LifeOSError("cache attachment changed while being copied")
                try:
                    os.link(
                        temp_name,
                        destination.name,
                        src_dir_fd=directory_fd,
                        dst_dir_fd=directory_fd,
                        follow_symlinks=False,
                    )
                except FileExistsError:
                    raise LifeOSError("attachment destination conflicts with an existing file") from None
                os.unlink(temp_name, dir_fd=directory_fd)
                temp_name = ""
                os.fsync(directory_fd)
        except LifeOSError:
            raise
        except OSError:
            raise LifeOSError("attachment could not be committed atomically") from None
        finally:
            if descriptor >= 0:
                os.close(descriptor)
            if source_descriptor >= 0:
                os.close(source_descriptor)
            if temp_name:
                try:
                    with self._attachments_directory() as directory_fd:
                        os.unlink(temp_name, dir_fd=directory_fd)
                except OSError:
                    pass

    @staticmethod
    def _text_with_attachments(text: str, attachments: Sequence[StoredAttachment]) -> str:
        if not attachments:
            return text
        return text + "\n" + "\n".join(attachment.wikilink for attachment in attachments)

    @contextmanager
    def _capture_directory(self) -> Iterator[int]:
        path = self.life_root / "-1. Capture"
        directory_fd = -1
        try:
            path.mkdir(mode=0o755, exist_ok=True)
            path_info = path.lstat()
            if stat.S_ISLNK(path_info.st_mode) or not stat.S_ISDIR(path_info.st_mode):
                raise LifeOSError("Capture directory must be a non-symlink directory")
            directory_fd = os.open(path, os.O_RDONLY | _DIRECTORY | _NOFOLLOW)
            if not os.path.samestat(path_info, os.fstat(directory_fd)):
                raise LifeOSError("Capture directory changed during validation")
        except LifeOSError:
            if directory_fd >= 0:
                os.close(directory_fd)
            raise
        except OSError:
            if directory_fd >= 0:
                os.close(directory_fd)
            raise LifeOSError("Capture directory is unavailable") from None
        try:
            yield directory_fd
        finally:
            os.close(directory_fd)

    @staticmethod
    def _read_capture_at(directory_fd: int, name: str) -> str | None:
        try:
            descriptor = os.open(name, os.O_RDONLY | os.O_NONBLOCK | _NOFOLLOW, dir_fd=directory_fd)
        except FileNotFoundError:
            return None
        except OSError:
            raise LifeOSError("Capture note is unavailable") from None
        try:
            info = os.fstat(descriptor)
            if not stat.S_ISREG(info.st_mode):
                raise LifeOSError("Capture note must be a non-symlink file")
            with os.fdopen(descriptor, "rb", closefd=True) as stream:
                descriptor = -1
                return stream.read().decode("utf-8")
        except LifeOSError:
            raise
        except (OSError, UnicodeError):
            raise LifeOSError("Capture note is unreadable") from None
        finally:
            if descriptor >= 0:
                os.close(descriptor)

    @staticmethod
    def _atomic_replace_at(directory_fd: int, name: str, text: str) -> None:
        data = text.encode("utf-8")
        descriptor = -1
        temp_name = ""
        try:
            for _attempt in range(10):
                candidate = f".{name}.life-os-{secrets.token_hex(8)}"
                try:
                    descriptor = os.open(
                        candidate,
                        os.O_CREAT | os.O_EXCL | os.O_WRONLY | _NOFOLLOW,
                        0o600,
                        dir_fd=directory_fd,
                    )
                    temp_name = candidate
                    break
                except FileExistsError:
                    continue
            if descriptor < 0:
                raise OSError("temporary Capture allocation failed")
            with os.fdopen(descriptor, "wb", closefd=True) as stream:
                descriptor = -1
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(
                temp_name,
                name,
                src_dir_fd=directory_fd,
                dst_dir_fd=directory_fd,
            )
            temp_name = ""
            os.fsync(directory_fd)
        except OSError:
            raise LifeOSError("Capture note could not be committed atomically") from None
        finally:
            if descriptor >= 0:
                os.close(descriptor)
            if temp_name:
                try:
                    os.unlink(temp_name, dir_fd=directory_fd)
                except OSError:
                    pass

    def _timestamped_entry(self, label: str, text: str, key: str) -> str:
        timestamp = datetime.now(self.timezone).strftime("%H:%M")
        return f"## {timestamp} — {label}\n{text}\n{_MESSAGE_PREFIX}{key} %%\n\n"

    @staticmethod
    def _control_entry(label: str, text: str, key: str) -> str:
        return f"##### {label}\n{text}\n{_MESSAGE_PREFIX}{key} %%\n\n"

    @staticmethod
    def _message_already_committed(content: str, key: str) -> bool:
        return f"{_MESSAGE_PREFIX}{key} %%" in content

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
            if (
                not isinstance(pending, dict)
                or set(pending) != {"for_question", "question"}
                or isinstance(pending["for_question"], bool)
                or not isinstance(pending["for_question"], int)
                or pending["for_question"] not in answered
                or not isinstance(pending["question"], str)
                or not 1 <= len(pending["question"]) <= 300
                or pending["question"] != pending["question"].strip()
            ):
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
        if any(marker in value for marker in (_START, _END, _STATE_PREFIX, _MESSAGE_PREFIX)):
            raise LifeOSError("message text contains a reserved marker")
        return value.strip()

    @staticmethod
    def _checked_follow_up(value: str) -> str:
        if not isinstance(value, str):
            raise LifeOSError("follow-up question is invalid")
        question = value.strip()
        if not 1 <= len(question) <= 300 or any(
            marker in question for marker in (_START, _END, _STATE_PREFIX, _MESSAGE_PREFIX)
        ):
            raise LifeOSError("follow-up question is invalid")
        return question

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


__all__ = ["LifeOSError", "LifeOSRuntime", "StoredAttachment", "WorkflowState"]
