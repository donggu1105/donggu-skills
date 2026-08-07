"""Deterministic, bounded Markdown runtime for Life OS Daily notes."""
from __future__ import annotations

from contextlib import contextmanager
import ctypes
from dataclasses import asdict, dataclass, replace
from datetime import date, datetime, timedelta
import errno
import fcntl
import hashlib
import importlib
import json
import os
from pathlib import Path
import re
import secrets
import stat
import sys
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
_ATTACHMENT_LINK = re.compile(r"\[\[Life OS/Attachments/(A\d{3,} - [^\]\r\n]+)\]\]")
_ATTACHMENT_TEMP = re.compile(r"^\.life-os-attachment-[0-9a-f]{16}$")
_DEFAULT_MAX_ATTACHMENT_BYTES = 32 * 1024 * 1024
_NOTE_STAGE_PREFIX = ".life-os-note-stage-"
_NOTE_ARCHIVE_PREFIX = ".life-os-note-archive-"
_NOTE_ABORTED_PREFIX = ".life-os-note-aborted-"
_SENSITIVE_MESSAGE_PATTERNS = (
    re.compile(r"<(?:@!?|@&|#)[0-9]{17,20}>"),
    re.compile(r"(?<![0-9])[0-9]{17,20}(?![0-9])"),
    re.compile(r"https?://(?:cdn\.discordapp\.com|media\.discordapp\.net)/", re.IGNORECASE),
    re.compile(r"(?:^|[\\/])\.hermes[\\/]cache(?:[\\/]|$)", re.IGNORECASE),
    re.compile(r"/(?:Users|home)/[^/\s]+(?:/|$)"),
    re.compile(r"[A-Za-z]:\\Users\\[^\\\s]+(?:\\|$)", re.IGNORECASE),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"(?:sk-(?:proj-)?|gh[pousr]_|github_pat_|xox[baprs]-)[A-Za-z0-9_-]{16,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{20,}"),
    re.compile(r"\bBearer\s+[A-Za-z0-9._-]{16,}", re.IGNORECASE),
    re.compile(
        r"\b(?:[A-Za-z0-9]+[_-])*(?:api[_-]?key|access[_-]?token|token|secret|password)"
        r"\s*[:=]\s*\S{8,}",
        re.IGNORECASE,
    ),
)


class LifeOSError(Exception):
    """The configured Life OS data cannot be read or safely mutated."""


class _DailyMissing(Exception):
    """The selected date has no Daily directory or note yet."""


class _ConcurrentMutation(LifeOSError):
    """The destination changed after Life OS read its source snapshot."""

    def __init__(self) -> None:
        super().__init__("Life OS note changed concurrently; retry the operation")


def _load_exclusive_rename() -> tuple[Any, int] | None:
    try:
        library = ctypes.CDLL(None, use_errno=True)
        if sys.platform == "darwin":
            function = library.renameatx_np
            function.argtypes = [
                ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p,
                ctypes.c_uint,
            ]
            function.restype = ctypes.c_int
            return function, 0x00000004 | 0x00000010
        if sys.platform.startswith("linux"):
            function = library.renameat2
            function.argtypes = [
                ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p,
                ctypes.c_uint,
            ]
            function.restype = ctypes.c_int
            return function, 0x00000001
    except (AttributeError, OSError):
        pass
    return None


_EXCLUSIVE_RENAME = _load_exclusive_rename()


def _load_exchange_rename() -> tuple[Any, int] | None:
    try:
        library = ctypes.CDLL(None, use_errno=True)
        if sys.platform == "darwin":
            function = library.renameatx_np
            function.argtypes = [
                ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p,
                ctypes.c_uint,
            ]
            function.restype = ctypes.c_int
            return function, 0x00000002 | 0x00000010
        if sys.platform.startswith("linux"):
            function = library.renameat2
            function.argtypes = [
                ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p,
                ctypes.c_uint,
            ]
            function.restype = ctypes.c_int
            return function, 0x00000002
    except (AttributeError, OSError):
        pass
    return None


_EXCHANGE_RENAME = _load_exchange_rename()


def _exclusive_rename_at(directory_fd: int, source: str, target: str) -> None:
    if _EXCLUSIVE_RENAME is None:
        raise OSError("exclusive rename is unavailable")
    function, flags = _EXCLUSIVE_RENAME
    result = function(
        directory_fd, os.fsencode(source), directory_fd, os.fsencode(target), flags,
    )
    if result != 0:
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error))


def _exchange_rename_at(
    source_directory_fd: int,
    source: str,
    target_directory_fd: int,
    target: str,
) -> None:
    if _EXCHANGE_RENAME is None:
        raise OSError(errno.ENOTSUP, "atomic exchange is unavailable")
    function, flags = _EXCHANGE_RENAME
    result = function(
        source_directory_fd,
        os.fsencode(source),
        target_directory_fd,
        os.fsencode(target),
        flags,
    )
    if result != 0:
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error))


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


@dataclass(frozen=True)
class _TextSnapshot:
    text: str
    device: int
    inode: int
    size: int
    uid: int
    mode: int
    nlink: int
    mtime_ns: int
    ctime_ns: int
    sha256: str


@dataclass(frozen=True)
class _TempIdentity:
    device: int
    inode: int
    size: int
    mtime_ns: int
    ctime_ns: int
    sha256: str


@dataclass(frozen=True)
class _EntryIdentity:
    device: int
    inode: int
    size: int
    uid: int
    mode: int
    nlink: int
    mtime_ns: int
    ctime_ns: int
    sha256: str | None
    link_target: str | None


def checked_life_os_message_text(value: str) -> str:
    """Validate text before it can cross a Life OS persistence boundary."""
    if not isinstance(value, str) or not value.strip() or len(value.encode("utf-8")) > 100_000:
        raise LifeOSError("message text is invalid")
    text = value.strip()
    if any(pattern.search(text) for pattern in _SENSITIVE_MESSAGE_PATTERNS):
        raise LifeOSError("message text contains sensitive content")
    return text


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


def _file_sha256_fd(descriptor: int) -> str:
    digest = hashlib.sha256()
    try:
        os.lseek(descriptor, 0, os.SEEK_SET)
        for chunk in iter(lambda: os.read(descriptor, 1024 * 1024), b""):
            digest.update(chunk)
        os.lseek(descriptor, 0, os.SEEK_SET)
    except OSError:
        raise LifeOSError("cache attachment is unreadable") from None
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


def _open_verified_temp_at(
    directory_fd: int, name: str, descriptor: int, digest: str, kind: str,
) -> _TempIdentity:
    try:
        before = os.fstat(descriptor)
        path_before = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_uid != os.geteuid()
            or stat.S_IMODE(before.st_mode) != 0o600
            or before.st_nlink != 1
            or not os.path.samestat(before, path_before)
        ):
            raise OSError()
        actual_digest = _file_sha256_fd(descriptor)
        after = os.fstat(descriptor)
        path_after = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        before_identity = (
            before.st_dev, before.st_ino, before.st_size,
            before.st_mtime_ns, before.st_ctime_ns, before.st_nlink,
        )
        after_identity = (
            after.st_dev, after.st_ino, after.st_size,
            after.st_mtime_ns, after.st_ctime_ns, after.st_nlink,
        )
        if (
            before_identity != after_identity
            or not os.path.samestat(after, path_after)
            or actual_digest != digest
        ):
            raise OSError()
        return _TempIdentity(
            device=after.st_dev,
            inode=after.st_ino,
            size=after.st_size,
            mtime_ns=after.st_mtime_ns,
            ctime_ns=after.st_ctime_ns,
            sha256=actual_digest,
        )
    except (LifeOSError, OSError):
        raise LifeOSError(f"temporary {kind} changed before publication") from None


def _published_temp_matches(
    directory_fd: int, name: str, source_descriptor: int, expected: _TempIdentity,
) -> bool:
    descriptor = -1
    try:
        source_before = os.fstat(source_descriptor)
        descriptor = os.open(
            name, os.O_RDONLY | os.O_NONBLOCK | _NOFOLLOW, dir_fd=directory_fd,
        )
        before = os.fstat(descriptor)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_uid != os.geteuid()
            or stat.S_IMODE(before.st_mode) != 0o600
            or before.st_nlink != 1
            or before.st_dev != expected.device
            or before.st_ino != expected.inode
            or before.st_size != expected.size
            or not os.path.samestat(source_before, before)
        ):
            return False
        actual_digest = _file_sha256_fd(descriptor)
        after = os.fstat(descriptor)
        source_after = os.fstat(source_descriptor)
        path_after = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        return (
            before.st_dev == after.st_dev
            and before.st_ino == after.st_ino
            and before.st_size == after.st_size
            and before.st_mtime_ns == after.st_mtime_ns
            and before.st_ctime_ns == after.st_ctime_ns
            and before.st_nlink == after.st_nlink == source_after.st_nlink == 1
            and os.path.samestat(source_before, source_after)
            and os.path.samestat(source_after, after)
            and os.path.samestat(after, path_after)
            and after.st_mtime_ns == expected.mtime_ns
            and actual_digest == expected.sha256
        )
    except (LifeOSError, OSError):
        return False
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def _open_stable_entry_at(
    directory_fd: int, name: str,
) -> tuple[int, _EntryIdentity]:
    descriptor = -1
    try:
        before = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        if stat.S_ISREG(before.st_mode):
            descriptor = os.open(
                name, os.O_RDONLY | os.O_NONBLOCK | _NOFOLLOW, dir_fd=directory_fd,
            )
            if not os.path.samestat(before, os.fstat(descriptor)):
                raise OSError()
            digest = _file_sha256_fd(descriptor)
            link_target = None
        elif stat.S_ISLNK(before.st_mode):
            digest = None
            link_target = os.readlink(name, dir_fd=directory_fd)
        else:
            raise OSError()
        after = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        before_identity = (
            before.st_dev, before.st_ino, before.st_size, before.st_uid,
            before.st_mode, before.st_nlink, before.st_mtime_ns, before.st_ctime_ns,
        )
        after_identity = (
            after.st_dev, after.st_ino, after.st_size, after.st_uid,
            after.st_mode, after.st_nlink, after.st_mtime_ns, after.st_ctime_ns,
        )
        if before_identity != after_identity:
            raise OSError()
        return descriptor, _EntryIdentity(
            device=after.st_dev,
            inode=after.st_ino,
            size=after.st_size,
            uid=after.st_uid,
            mode=after.st_mode,
            nlink=after.st_nlink,
            mtime_ns=after.st_mtime_ns,
            ctime_ns=after.st_ctime_ns,
            sha256=digest,
            link_target=link_target,
        )
    except (LifeOSError, OSError):
        if descriptor >= 0:
            os.close(descriptor)
        raise LifeOSError("note exchange entry is unavailable for manual recovery") from None


def _entry_matches_identity_at(
    directory_fd: int,
    name: str,
    source_descriptor: int,
    expected: _EntryIdentity,
) -> bool:
    descriptor = -1
    try:
        before = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        if (
            before.st_dev != expected.device
            or before.st_ino != expected.inode
            or before.st_size != expected.size
            or before.st_uid != expected.uid
            or before.st_mode != expected.mode
            or before.st_nlink != expected.nlink
            or before.st_mtime_ns != expected.mtime_ns
        ):
            return False
        if stat.S_ISREG(before.st_mode):
            descriptor = os.open(
                name, os.O_RDONLY | os.O_NONBLOCK | _NOFOLLOW, dir_fd=directory_fd,
            )
            opened = os.fstat(descriptor)
            if (
                not os.path.samestat(before, opened)
                or source_descriptor < 0
                or not os.path.samestat(os.fstat(source_descriptor), opened)
            ):
                return False
            digest = _file_sha256_fd(descriptor)
            if digest != expected.sha256:
                return False
        elif stat.S_ISLNK(before.st_mode):
            if source_descriptor >= 0 or os.readlink(name, dir_fd=directory_fd) != expected.link_target:
                return False
        else:
            return False
        after = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        return (
            os.path.samestat(before, after)
            and before.st_size == after.st_size
            and before.st_uid == after.st_uid
            and before.st_mode == after.st_mode
            and before.st_nlink == after.st_nlink
            and before.st_mtime_ns == after.st_mtime_ns
            and before.st_ctime_ns == after.st_ctime_ns
        )
    except (LifeOSError, OSError):
        return False
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def _quarantine_published_entry(directory_fd: int, name: str, kind: str) -> None:
    for _attempt in range(10):
        recovery_name = f".life-os-recovery-{secrets.token_hex(8)}"
        try:
            _exclusive_rename_at(directory_fd, name, recovery_name)
            os.fsync(directory_fd)
            raise LifeOSError(f"temporary {kind} changed during publication")
        except FileExistsError:
            continue
        except LifeOSError:
            raise
        except OSError:
            raise LifeOSError(
                f"temporary {kind} changed and could not be quarantined safely"
            ) from None
    raise LifeOSError(f"temporary {kind} recovery name could not be allocated")


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
        self._periodic_identity = self.periodic_root.lstat()
        self.template_root = _checked_child(self.periodic_root, "Templates")
        self._template_root_identity = self.template_root.lstat()
        self.cache_roots = tuple(Path(root).expanduser() for root in cache_roots) if cache_roots is not None else None
        if max_attachment_bytes is not None:
            if isinstance(max_attachment_bytes, bool) or not isinstance(max_attachment_bytes, int) or max_attachment_bytes < 0:
                raise LifeOSError("maximum attachment bytes is invalid")
            self._max_attachment_bytes_override = max_attachment_bytes
        else:
            self._max_attachment_bytes_override = None
        external_state_root = _checked_external_state_root(self.vault_root, state_root)
        self.state_root = _prepare_private_state_root(external_state_root)
        self._state_root_identity = self.state_root.lstat()
        vault_identity = json.dumps(
            {"st_dev": self._vault_identity.st_dev, "st_ino": self._vault_identity.st_ino},
            separators=(",", ":"),
            sort_keys=True,
        )
        namespace_name = hashlib.sha256(vault_identity.encode("utf-8")).hexdigest()
        self.state_namespace = _prepare_private_state_root(self.state_root / namespace_name)
        self._state_namespace_identity = self.state_namespace.lstat()
        self.claims_root = _prepare_private_state_root(self.state_namespace / "claims")
        self._claims_root_identity = self.claims_root.lstat()
        self.note_archives_root = _prepare_private_state_root(
            self.state_namespace / "note-archives"
        )
        self._note_archives_root_identity = self.note_archives_root.lstat()
        template = self._template_path()
        try:
            template_info = template.lstat()
        except OSError:
            raise LifeOSError("Daily template is unavailable") from None
        if stat.S_ISLNK(template_info.st_mode) or not stat.S_ISREG(template_info.st_mode):
            raise LifeOSError("Daily template must be a non-symlink file")
        self._template_identity = template_info

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

    @property
    def max_attachment_bytes(self) -> int:
        if self._max_attachment_bytes_override is not None:
            return self._max_attachment_bytes_override
        configured: Any = None
        try:
            from hermes_cli.config import load_config_readonly

            raw_config = load_config_readonly()
            discord_config = raw_config.get("discord", {})
            if not isinstance(discord_config, dict):
                raise LifeOSError("Hermes Discord attachment configuration is invalid")
            configured = discord_config.get("max_attachment_bytes")
        except (ImportError, ModuleNotFoundError):
            configured = None
        if configured is None:
            configured = os.environ.get("DISCORD_MAX_ATTACHMENT_BYTES")
        if configured is None or configured == "":
            return _DEFAULT_MAX_ATTACHMENT_BYTES
        if isinstance(configured, bool):
            raise LifeOSError("Hermes Discord attachment limit is invalid")
        try:
            value = int(configured)
        except (TypeError, ValueError):
            raise LifeOSError("Hermes Discord attachment limit is invalid") from None
        if value < 0:
            raise LifeOSError("Hermes Discord attachment limit is invalid")
        return value

    @max_attachment_bytes.setter
    def max_attachment_bytes(self, value: int) -> None:
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise LifeOSError("maximum attachment bytes is invalid")
        self._max_attachment_bytes_override = value

    def resolve_target_date(self, command: str | None = None) -> date:
        with self._mutation_lock():
            return self._resolve_target_date_unlocked(command)

    def _resolve_target_date_unlocked(self, command: str | None = None) -> date:
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
        with self._mutation_lock():
            selected = target_date or self._resolve_target_date_unlocked()
            path = self.daily_path(selected)
            text = self._read_daily(selected)
            if text is None:
                return self._result(path, self._initial_state(selected))
            if text.count(_START) == 0 and text.count(_END) == 0 and _STATE_PREFIX not in text:
                return self._result(path, self._initial_state(selected))
            document, state = self._parse_block(text, selected)
            return self._result(path, state, content=document.content)

    def start_daily(self, target_date: date | None = None, *, resume: bool = False) -> dict[str, Any]:
        selected = target_date or datetime.now(self.timezone).date()
        with self._mutation_lock():
            path = self._ensure_daily(selected)
            for _attempt in range(3):
                try:
                    snapshot = self._read_daily_snapshot(selected)
                except _ConcurrentMutation:
                    continue
                if snapshot is None:
                    raise LifeOSError("Daily note is unavailable")
                document, state = self._document_and_state(snapshot.text, selected)
                if state.status == "not_started" or (resume and state.status == "paused"):
                    state = replace(state, status="active")
                rendered = self._render(document, state)
                if rendered != snapshot.text:
                    try:
                        self._publish_daily(selected, rendered, snapshot)
                    except _ConcurrentMutation:
                        continue
                return self._result(path, state, content=document.content)
            raise LifeOSError("Daily note changed concurrently; retry the operation")

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
        with self._mutation_lock() as namespace_fd:
            selected = target_date or self._resolve_target_date_unlocked()
            claim_target = {
                "date": selected.isoformat(),
                "kind": "capture" if operation == "capture" else "daily",
                "operation": operation,
            }
            claim = self._begin_global_claim(namespace_fd, key, claim_target)
            if claim.get("status") == "committed":
                if claim["target"] == claim_target:
                    current = self._committed_outcome_for_key(selected, operation, key)
                    if current is not None:
                        return {**current, "duplicate": True}
                    self._write_global_claim(namespace_fd, key, {
                        "version": 1, "key": key, "status": "pending",
                        "target": claim_target,
                    })
                else:
                    return {**claim["outcome"], "duplicate": True}
            recovered = self._committed_outcome_for_key(selected, operation, key)
            if recovered is not None:
                recovered = {**recovered, "duplicate": True}
                if self._commit_global_claim(namespace_fd, key, claim_target, recovered):
                    return recovered
            if operation == "capture":
                for _attempt in range(3):
                    result = self._append_capture(selected, text, key, attachment_paths)
                    if self._commit_global_claim(
                        namespace_fd, key, claim_target, result,
                    ):
                        return result
                raise LifeOSError("Capture note changed concurrently; retry the operation")
            path = self._ensure_daily(selected)
            stored = self._store_attachments(attachment_paths)
            text = self._text_with_attachments(text, stored)
            for _attempt in range(3):
                try:
                    snapshot = self._read_daily_snapshot(selected)
                except _ConcurrentMutation:
                    continue
                if snapshot is None:
                    raise LifeOSError("Daily note is unavailable")
                document, state = self._document_and_state(snapshot.text, selected)
                if self._message_already_committed(document.content, key):
                    result = self._result(path, state, content=document.content, duplicate=True)
                    if self._commit_global_claim(
                        namespace_fd, key, claim_target, result,
                    ):
                        return result
                    continue
                document, state = self._apply_operation(
                    document,
                    state,
                    operation,
                    text,
                    key,
                    follow_up_question=follow_up_question,
                )
                try:
                    self._publish_daily(selected, self._render(document, state), snapshot)
                except _ConcurrentMutation:
                    continue
                result = self._result(path, state, content=document.content)
                if self._commit_global_claim(namespace_fd, key, claim_target, result):
                    return result
            raise LifeOSError("Daily note changed concurrently; retry the operation")

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
            if follow_up_question is not None or state.status not in {"active", "paused"}:
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
            status = "completed" if state.next_question is None else "active"
            return replace(document, content=document.content + entry), replace(
                state, status=status, pending_follow_up=None, last_message_key=key,
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
            status = "active"
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
        text = self._read_daily(selected)
        if text is None:
            return None
        if text.count(_START) == 0 and text.count(_END) == 0 and _STATE_PREFIX not in text:
            return None
        _document, state = self._parse_block(text, selected)
        return state

    def _append_capture(
        self, selected: date, text: str, key: str, attachment_paths: Sequence[Path],
    ) -> dict[str, Any]:
        path = self.capture_path(selected)
        stored = self._store_attachments(attachment_paths)
        text = self._text_with_attachments(text, stored)
        entry = self._timestamped_entry("Capture", text, key)
        with self._capture_directory() as directory_fd:
            for _attempt in range(3):
                try:
                    snapshot = self._read_capture_snapshot_at(directory_fd, path.name)
                except _ConcurrentMutation:
                    continue
                if snapshot is not None:
                    if self._message_already_committed(snapshot.text, key):
                        return {"path": str(path), "date": selected.isoformat(), "status": "captured", "duplicate": True}
                    document = snapshot.text
                else:
                    document = f"# Capture — {selected.isoformat()}\n\n"
                try:
                    self._atomic_publish_note_at(
                        directory_fd, path.name, document + entry, snapshot,
                    )
                except _ConcurrentMutation:
                    continue
                break
            else:
                raise LifeOSError("Capture note changed concurrently; retry the operation")
        return {"path": str(path), "date": selected.isoformat(), "status": "captured", "duplicate": False}

    @property
    def attachments_root(self) -> Path:
        return self.life_root / "Attachments"

    def _store_attachments(self, paths: Sequence[Path]) -> tuple[StoredAttachment, ...]:
        return tuple(self._store_one_attachment(Path(path)) for path in paths)

    def _reconcile_attachment_temps(self) -> None:
        """Fail closed without mutating residual attachment temp entries."""
        with self._attachments_directory() as directory_fd:
            try:
                entries = tuple(os.listdir(directory_fd))
            except OSError:
                raise LifeOSError("attachment directory is unreadable") from None
            if any(name.startswith(".life-os-recovery-") for name in entries):
                raise LifeOSError("temporary attachment requires manual recovery")
            for name in entries:
                if not name.startswith(".life-os-attachment-"):
                    continue
                if _ATTACHMENT_TEMP.fullmatch(name) is None:
                    raise LifeOSError("temporary attachment entry is invalid")
                raise LifeOSError("temporary attachment requires manual recovery")

    def _store_one_attachment(self, source: Path) -> StoredAttachment:
        with self._open_cache_attachment(source) as (source_descriptor, source_name):
            self._reconcile_attachment_temps()
            digest = _file_sha256_fd(source_descriptor)
            existing = self._attachment_by_hash(digest)
            if existing is not None:
                return existing
            number = self._next_attachment_number()
            filename = f"A{number:03d} - {self._readable_name(source_name)}"
            destination = self.attachments_root / filename
            self._atomic_copy_verified(source_descriptor, destination, digest)
            return StoredAttachment(
                number=number,
                path=destination,
                sha256=digest,
                wikilink=f"[[Life OS/Attachments/{filename}]]",
            )

    @contextmanager
    def _open_cache_attachment(self, source: Path) -> Iterator[tuple[int, str]]:
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
        if not relative_parts:
            raise LifeOSError("cache attachment path must name a file")
        directory_fds: list[int] = []
        source_descriptor = -1
        try:
            current_fd = os.open(matching_root, os.O_RDONLY | _DIRECTORY | _NOFOLLOW)
            directory_fds.append(current_fd)
            for name in relative_parts[:-1]:
                current_fd = os.open(
                    name,
                    os.O_RDONLY | _DIRECTORY | _NOFOLLOW,
                    dir_fd=current_fd,
                )
                directory_fds.append(current_fd)
            source_name = relative_parts[-1]
            before = os.stat(source_name, dir_fd=current_fd, follow_symlinks=False)
            if stat.S_ISLNK(before.st_mode) or not stat.S_ISREG(before.st_mode):
                raise LifeOSError("cache attachment must be a non-symlink regular file")
            source_descriptor = os.open(source_name, os.O_RDONLY | _NOFOLLOW, dir_fd=current_fd)
            after = os.fstat(source_descriptor)
            if not os.path.samestat(before, after):
                raise LifeOSError("cache attachment changed while being opened")
            if self.max_attachment_bytes and after.st_size > self.max_attachment_bytes:
                raise LifeOSError("cache attachment exceeds the configured size limit")
        except OSError:
            if source_descriptor >= 0:
                os.close(source_descriptor)
            for directory_fd in reversed(directory_fds):
                os.close(directory_fd)
            raise LifeOSError("cache attachment is unavailable") from None
        except LifeOSError:
            if source_descriptor >= 0:
                os.close(source_descriptor)
            for directory_fd in reversed(directory_fds):
                os.close(directory_fd)
            raise
        try:
            yield source_descriptor, source_name
        finally:
            os.close(source_descriptor)
            for directory_fd in reversed(directory_fds):
                os.close(directory_fd)

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
            os.fsync(life_fd)
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

    def _atomic_copy_verified(self, source_descriptor: int, destination: Path, digest: str) -> None:
        if destination.parent != self.attachments_root:
            raise LifeOSError("attachment destination conflicts with an existing file")
        descriptor = -1
        temp_name = ""
        try:
            with self._attachments_directory() as directory_fd:
                for _attempt in range(10):
                    candidate = f".life-os-attachment-{secrets.token_hex(8)}"
                    try:
                        descriptor = os.open(
                            candidate,
                            os.O_CREAT | os.O_EXCL | os.O_RDWR | _NOFOLLOW,
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
                os.lseek(source_descriptor, 0, os.SEEK_SET)
                with os.fdopen(descriptor, "wb", closefd=False) as output_stream:
                    total = 0
                    for chunk in iter(lambda: os.read(source_descriptor, 1024 * 1024), b""):
                        total += len(chunk)
                        if self.max_attachment_bytes and total > self.max_attachment_bytes:
                            raise LifeOSError("cache attachment exceeds the configured size limit")
                        output_stream.write(chunk)
                        hasher.update(chunk)
                    output_stream.flush()
                    os.fsync(output_stream.fileno())
                if hasher.hexdigest() != digest:
                    raise LifeOSError("cache attachment changed while being copied")
                temp_identity = _open_verified_temp_at(
                    directory_fd, temp_name, descriptor, digest, "attachment",
                )
                try:
                    _exclusive_rename_at(directory_fd, temp_name, destination.name)
                except FileExistsError:
                    raise LifeOSError("attachment destination conflicts with an existing file") from None
                temp_name = ""
                if not _published_temp_matches(
                    directory_fd, destination.name, descriptor, temp_identity,
                ):
                    _quarantine_published_entry(
                        directory_fd, destination.name, "attachment",
                    )
                os.fsync(directory_fd)
        except LifeOSError:
            raise
        except OSError:
            raise LifeOSError("attachment could not be committed atomically") from None
        finally:
            if descriptor >= 0:
                os.close(descriptor)

    @staticmethod
    def _text_with_attachments(text: str, attachments: Sequence[StoredAttachment]) -> str:
        if not attachments:
            return text
        return text + "\n" + "\n".join(attachment.wikilink for attachment in attachments)

    @contextmanager
    def _capture_directory(self) -> Iterator[int]:
        vault_fd = -1
        life_fd = -1
        directory_fd = -1
        try:
            vault_fd = os.open(self.vault_root, os.O_RDONLY | _DIRECTORY | _NOFOLLOW)
            if not os.path.samestat(self._vault_identity, os.fstat(vault_fd)):
                raise LifeOSError("Vault root changed after runtime construction")
            life_fd = os.open("Life OS", os.O_RDONLY | _DIRECTORY | _NOFOLLOW, dir_fd=vault_fd)
            if not os.path.samestat(self._life_identity, os.fstat(life_fd)):
                raise LifeOSError("Life OS directory changed after runtime construction")
            try:
                os.mkdir("-1. Capture", mode=0o755, dir_fd=life_fd)
            except FileExistsError:
                pass
            before = os.stat("-1. Capture", dir_fd=life_fd, follow_symlinks=False)
            if stat.S_ISLNK(before.st_mode) or not stat.S_ISDIR(before.st_mode):
                raise LifeOSError("Capture directory must be a non-symlink directory")
            directory_fd = os.open(
                "-1. Capture", os.O_RDONLY | _DIRECTORY | _NOFOLLOW, dir_fd=life_fd,
            )
            if not os.path.samestat(before, os.fstat(directory_fd)):
                raise LifeOSError("Capture directory changed during validation")
            os.fsync(life_fd)
        except LifeOSError:
            if directory_fd >= 0:
                os.close(directory_fd)
            if life_fd >= 0:
                os.close(life_fd)
            if vault_fd >= 0:
                os.close(vault_fd)
            raise
        except OSError:
            if directory_fd >= 0:
                os.close(directory_fd)
            if life_fd >= 0:
                os.close(life_fd)
            if vault_fd >= 0:
                os.close(vault_fd)
            raise LifeOSError("Capture directory is unavailable") from None
        try:
            yield directory_fd
        finally:
            os.close(directory_fd)
            os.close(life_fd)
            os.close(vault_fd)

    @staticmethod
    def _read_capture_at(directory_fd: int, name: str) -> str | None:
        snapshot = LifeOSRuntime._read_capture_snapshot_at(directory_fd, name)
        return None if snapshot is None else snapshot.text

    @staticmethod
    def _read_capture_snapshot_at(directory_fd: int, name: str) -> _TextSnapshot | None:
        LifeOSRuntime._reconcile_note_temps(directory_fd, name)
        return LifeOSRuntime._read_text_snapshot_at(
            directory_fd,
            name,
            unavailable="Capture note is unavailable",
            nonregular="Capture note must be a non-symlink file",
            unreadable="Capture note is unreadable",
        )

    @staticmethod
    def _reconcile_note_temps(directory_fd: int, name: str) -> None:
        prefix = f".{name}.life-os-"
        try:
            directory_entries = tuple(os.listdir(directory_fd))
        except OSError:
            raise LifeOSError("note directory is unreadable") from None
        if any(entry.startswith(".life-os-recovery-") for entry in directory_entries):
            raise LifeOSError("temporary note requires manual recovery")
        entries = tuple(entry for entry in directory_entries if entry.startswith(prefix))
        if not entries:
            return
        if len(entries) != 1 or not re.fullmatch(r"[0-9a-f]{16}", entries[0][len(prefix):]):
            raise LifeOSError("temporary note entry is invalid")
        raise LifeOSError("temporary note requires manual recovery")

    @staticmethod
    def _read_text_snapshot_at(
        directory_fd: int,
        name: str,
        *,
        unavailable: str,
        nonregular: str,
        unreadable: str,
    ) -> _TextSnapshot | None:
        descriptor = -1
        try:
            descriptor = os.open(name, os.O_RDONLY | os.O_NONBLOCK | _NOFOLLOW, dir_fd=directory_fd)
        except FileNotFoundError:
            return None
        except OSError:
            raise LifeOSError(unavailable) from None
        try:
            before = os.fstat(descriptor)
            if not stat.S_ISREG(before.st_mode):
                raise LifeOSError(nonregular)
            with os.fdopen(descriptor, "rb", closefd=True) as stream:
                descriptor = -1
                data = stream.read()
                after = os.fstat(stream.fileno())
            identity_before = (
                before.st_dev, before.st_ino, before.st_size,
                before.st_mtime_ns, before.st_ctime_ns,
            )
            identity_after = (
                after.st_dev, after.st_ino, after.st_size,
                after.st_mtime_ns, after.st_ctime_ns,
            )
            if identity_before != identity_after or len(data) != after.st_size:
                raise _ConcurrentMutation
            return _TextSnapshot(
                text=data.decode("utf-8"),
                device=after.st_dev,
                inode=after.st_ino,
                size=after.st_size,
                uid=after.st_uid,
                mode=after.st_mode,
                nlink=after.st_nlink,
                mtime_ns=after.st_mtime_ns,
                ctime_ns=after.st_ctime_ns,
                sha256=hashlib.sha256(data).hexdigest(),
            )
        except _ConcurrentMutation:
            raise
        except LifeOSError:
            raise
        except (OSError, UnicodeError):
            raise LifeOSError(unreadable) from None
        finally:
            if descriptor >= 0:
                os.close(descriptor)

    def _atomic_publish_note_at(
        self,
        directory_fd: int,
        name: str,
        text: str,
        expected: _TextSnapshot | None,
    ) -> None:
        data = text.encode("utf-8")
        if expected is not None:
            self._exchange_publish_note_at(directory_fd, name, data, expected)
            return
        descriptor = -1
        temp_name = ""
        try:
            for _attempt in range(10):
                candidate = f".{name}.life-os-{secrets.token_hex(8)}"
                try:
                    descriptor = os.open(
                        candidate,
                        os.O_CREAT | os.O_EXCL | os.O_RDWR | _NOFOLLOW,
                        0o600,
                        dir_fd=directory_fd,
                    )
                    temp_name = candidate
                    break
                except FileExistsError:
                    continue
            if descriptor < 0:
                raise OSError("temporary note allocation failed")
            with os.fdopen(descriptor, "wb", closefd=False) as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            temp_identity = _open_verified_temp_at(
                directory_fd,
                temp_name,
                descriptor,
                hashlib.sha256(data).hexdigest(),
                "note",
            )
            try:
                _exclusive_rename_at(directory_fd, temp_name, name)
            except FileExistsError:
                raise _ConcurrentMutation from None
            temp_name = ""
            if not _published_temp_matches(
                directory_fd, name, descriptor, temp_identity,
            ):
                _quarantine_published_entry(directory_fd, name, "note")
            os.fsync(directory_fd)
        except _ConcurrentMutation:
            raise
        except OSError:
            raise LifeOSError("note could not be committed atomically") from None
        finally:
            if descriptor >= 0:
                os.close(descriptor)

    @staticmethod
    def _finalize_note_stage(
        archive_fd: int,
        stage_name: str,
        prefix: str,
        transaction_id: str,
        target_name: str,
    ) -> str:
        final_name = f"{prefix}{transaction_id}-{target_name}"
        try:
            _exclusive_rename_at(archive_fd, stage_name, final_name)
            os.fsync(archive_fd)
            return final_name
        except OSError:
            raise LifeOSError(
                "note archive transaction requires manual recovery"
            ) from None

    @staticmethod
    def _open_expected_note_entry(
        directory_fd: int, name: str, expected: _TextSnapshot,
    ) -> tuple[int, _EntryIdentity]:
        descriptor, identity = _open_stable_entry_at(directory_fd, name)
        if (
            not stat.S_ISREG(identity.mode)
            or identity.device != expected.device
            or identity.inode != expected.inode
            or identity.size != expected.size
            or identity.uid != expected.uid
            or identity.mode != expected.mode
            or identity.nlink != expected.nlink
            or identity.mtime_ns != expected.mtime_ns
            or identity.ctime_ns != expected.ctime_ns
            or identity.sha256 != expected.sha256
        ):
            if descriptor >= 0:
                os.close(descriptor)
            raise _ConcurrentMutation
        return descriptor, identity

    def _exchange_publish_note_at(
        self,
        directory_fd: int,
        name: str,
        data: bytes,
        expected: _TextSnapshot,
    ) -> None:
        writer_fd = -1
        old_fd = -1
        displaced_fd = -1
        stage_name = ""
        transaction_id = secrets.token_hex(8)
        try:
            with self._note_archives_directory() as archive_fd:
                try:
                    entries = tuple(os.listdir(archive_fd))
                except OSError:
                    raise LifeOSError("Life OS note archive is unreadable") from None
                if any(entry.startswith(_NOTE_STAGE_PREFIX) for entry in entries):
                    raise LifeOSError("note archive transaction requires manual recovery")
                if os.fstat(archive_fd).st_dev != os.fstat(directory_fd).st_dev:
                    raise LifeOSError("note archive and Vault must use the same filesystem")
                if _EXCHANGE_RENAME is None:
                    raise LifeOSError("atomic note exchange is unavailable")
                stage_name = f"{_NOTE_STAGE_PREFIX}{transaction_id}-{name}"
                try:
                    writer_fd = os.open(
                        stage_name,
                        os.O_CREAT | os.O_EXCL | os.O_RDWR | _NOFOLLOW,
                        0o600,
                        dir_fd=archive_fd,
                    )
                    with os.fdopen(writer_fd, "wb", closefd=False) as stream:
                        stream.write(data)
                        stream.flush()
                        os.fsync(stream.fileno())
                    writer_identity = _open_verified_temp_at(
                        archive_fd,
                        stage_name,
                        writer_fd,
                        hashlib.sha256(data).hexdigest(),
                        "note",
                    )
                    os.fsync(archive_fd)
                except (LifeOSError, OSError):
                    raise LifeOSError("note archive candidate could not be persisted") from None
                current = LifeOSRuntime._read_text_snapshot_at(
                    directory_fd,
                    name,
                    unavailable="note is unavailable",
                    nonregular="note must be a non-symlink file",
                    unreadable="note is unreadable",
                )
                if current != expected:
                    self._finalize_note_stage(
                        archive_fd, stage_name, _NOTE_ABORTED_PREFIX,
                        transaction_id, name,
                    )
                    stage_name = ""
                    raise _ConcurrentMutation
                try:
                    old_fd, old_identity = self._open_expected_note_entry(
                        directory_fd, name, expected,
                    )
                except _ConcurrentMutation:
                    self._finalize_note_stage(
                        archive_fd, stage_name, _NOTE_ABORTED_PREFIX,
                        transaction_id, name,
                    )
                    stage_name = ""
                    raise
                try:
                    _exchange_rename_at(archive_fd, stage_name, directory_fd, name)
                except OSError as exc:
                    if exc.errno in {
                        errno.EXDEV, errno.ENOTSUP, errno.EOPNOTSUPP,
                        errno.EINVAL, errno.ENOSYS,
                    }:
                        self._finalize_note_stage(
                            archive_fd, stage_name, _NOTE_ABORTED_PREFIX,
                            transaction_id, name,
                        )
                        stage_name = ""
                        raise LifeOSError("atomic note exchange is unavailable") from None
                    raise LifeOSError(
                        "note archive transaction requires manual recovery"
                    ) from None
                os.fsync(archive_fd)
                os.fsync(directory_fd)
                if not _published_temp_matches(
                    directory_fd, name, writer_fd, writer_identity,
                ):
                    displaced_fd, displaced_identity = _open_stable_entry_at(
                        directory_fd, name,
                    )
                    if not _entry_matches_identity_at(
                        archive_fd, stage_name, old_fd, old_identity,
                    ):
                        raise LifeOSError(
                            "note archive transaction requires manual recovery"
                        )
                    final_name = self._finalize_note_stage(
                        archive_fd, stage_name, _NOTE_ARCHIVE_PREFIX,
                        transaction_id, name,
                    )
                    stage_name = ""
                    if (
                        not _entry_matches_identity_at(
                            archive_fd, final_name, old_fd, old_identity,
                        )
                        or not _entry_matches_identity_at(
                            directory_fd, name, displaced_fd, displaced_identity,
                        )
                    ):
                        raise LifeOSError(
                            "note archive transaction requires manual recovery"
                        )
                    raise _ConcurrentMutation
                if _entry_matches_identity_at(
                    archive_fd, stage_name, old_fd, old_identity,
                ):
                    final_name = self._finalize_note_stage(
                        archive_fd, stage_name, _NOTE_ARCHIVE_PREFIX,
                        transaction_id, name,
                    )
                    stage_name = ""
                    if _published_temp_matches(
                        directory_fd, name, writer_fd, writer_identity,
                    ):
                        return
                    displaced_fd, displaced_identity = _open_stable_entry_at(
                        directory_fd, name,
                    )
                    if (
                        not _entry_matches_identity_at(
                            archive_fd, final_name, old_fd, old_identity,
                        )
                        or not _entry_matches_identity_at(
                            directory_fd, name, displaced_fd, displaced_identity,
                        )
                    ):
                        raise LifeOSError(
                            "note archive transaction requires manual recovery"
                        )
                    raise _ConcurrentMutation
                displaced_fd, displaced_identity = _open_stable_entry_at(
                    archive_fd, stage_name,
                )
                if not _published_temp_matches(
                    directory_fd, name, writer_fd, writer_identity,
                ):
                    raise LifeOSError(
                        "note archive rollback requires manual recovery"
                    )
                try:
                    _exchange_rename_at(archive_fd, stage_name, directory_fd, name)
                except OSError:
                    raise LifeOSError(
                        "note archive rollback requires manual recovery"
                    ) from None
                os.fsync(archive_fd)
                os.fsync(directory_fd)
                if (
                    not _entry_matches_identity_at(
                        directory_fd, name, displaced_fd, displaced_identity,
                    )
                    or not _published_temp_matches(
                        archive_fd, stage_name, writer_fd, writer_identity,
                    )
                ):
                    raise LifeOSError(
                        "note archive rollback requires manual recovery"
                    )
                self._finalize_note_stage(
                    archive_fd, stage_name, _NOTE_ABORTED_PREFIX,
                    transaction_id, name,
                )
                stage_name = ""
                raise _ConcurrentMutation
        except _ConcurrentMutation:
            raise
        except LifeOSError:
            raise
        except OSError:
            raise LifeOSError("note could not be committed atomically") from None
        finally:
            for descriptor in (displaced_fd, old_fd, writer_fd):
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

    def _read_template(self) -> str:
        descriptors: list[int] = []
        try:
            vault_fd = os.open(self.vault_root, os.O_RDONLY | _DIRECTORY | _NOFOLLOW)
            descriptors.append(vault_fd)
            if not os.path.samestat(self._vault_identity, os.fstat(vault_fd)):
                raise LifeOSError("Vault root changed after runtime construction")
            life_fd = os.open("Life OS", os.O_RDONLY | _DIRECTORY | _NOFOLLOW, dir_fd=vault_fd)
            descriptors.append(life_fd)
            if not os.path.samestat(self._life_identity, os.fstat(life_fd)):
                raise LifeOSError("Life OS directory changed after runtime construction")
            periodic_fd = os.open(
                "0. PeriodicNotes", os.O_RDONLY | _DIRECTORY | _NOFOLLOW, dir_fd=life_fd,
            )
            descriptors.append(periodic_fd)
            if not os.path.samestat(self._periodic_identity, os.fstat(periodic_fd)):
                raise LifeOSError("Periodic notes directory changed after runtime construction")
            template_root_fd = os.open(
                "Templates", os.O_RDONLY | _DIRECTORY | _NOFOLLOW, dir_fd=periodic_fd,
            )
            descriptors.append(template_root_fd)
            if not os.path.samestat(self._template_root_identity, os.fstat(template_root_fd)):
                raise LifeOSError("Template directory changed after runtime construction")
            before = os.stat("Daily.md", dir_fd=template_root_fd, follow_symlinks=False)
            if not os.path.samestat(self._template_identity, before):
                raise LifeOSError("Daily template changed after runtime construction")
            template_fd = os.open("Daily.md", os.O_RDONLY | _NOFOLLOW, dir_fd=template_root_fd)
            descriptors.append(template_fd)
            if not os.path.samestat(before, os.fstat(template_fd)):
                raise LifeOSError("Daily template changed during validation")
            with os.fdopen(template_fd, "rb", closefd=False) as stream:
                return stream.read().decode("utf-8")
        except LifeOSError:
            raise
        except (OSError, UnicodeError):
            raise LifeOSError("Daily template is unreadable") from None
        finally:
            for descriptor in reversed(descriptors):
                os.close(descriptor)

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
    def _state_namespace_directory(self) -> Iterator[int]:
        state_fd = -1
        namespace_fd = -1
        try:
            state_fd = os.open(self.state_root, os.O_RDONLY | _DIRECTORY | _NOFOLLOW)
            state_info = os.fstat(state_fd)
            if (
                not os.path.samestat(self._state_root_identity, state_info)
                or not stat.S_ISDIR(state_info.st_mode)
                or state_info.st_uid != os.geteuid()
                or stat.S_IMODE(state_info.st_mode) != 0o700
            ):
                raise LifeOSError("Life OS state root changed after runtime construction")
            namespace_fd = os.open(
                self.state_namespace.name,
                os.O_RDONLY | _DIRECTORY | _NOFOLLOW,
                dir_fd=state_fd,
            )
            namespace_info = os.fstat(namespace_fd)
            if (
                not os.path.samestat(self._state_namespace_identity, namespace_info)
                or not stat.S_ISDIR(namespace_info.st_mode)
                or namespace_info.st_uid != os.geteuid()
                or stat.S_IMODE(namespace_info.st_mode) != 0o700
            ):
                raise LifeOSError("Life OS state namespace changed after runtime construction")
        except LifeOSError:
            if namespace_fd >= 0:
                os.close(namespace_fd)
            if state_fd >= 0:
                os.close(state_fd)
            raise
        except OSError:
            if namespace_fd >= 0:
                os.close(namespace_fd)
            if state_fd >= 0:
                os.close(state_fd)
            raise LifeOSError("Life OS state namespace is unavailable") from None
        try:
            yield namespace_fd
        finally:
            os.close(namespace_fd)
            os.close(state_fd)

    @contextmanager
    def _note_archives_directory(self) -> Iterator[int]:
        descriptor = -1
        with self._state_namespace_directory() as namespace_fd:
            try:
                descriptor = os.open(
                    "note-archives",
                    os.O_RDONLY | _DIRECTORY | _NOFOLLOW,
                    dir_fd=namespace_fd,
                )
                info = os.fstat(descriptor)
                if (
                    not os.path.samestat(self._note_archives_root_identity, info)
                    or not stat.S_ISDIR(info.st_mode)
                    or info.st_uid != os.geteuid()
                    or stat.S_IMODE(info.st_mode) != 0o700
                ):
                    raise LifeOSError("Life OS note archive changed after runtime construction")
                yield descriptor
            except LifeOSError:
                raise
            except OSError:
                raise LifeOSError("Life OS note archive is unavailable") from None
            finally:
                if descriptor >= 0:
                    os.close(descriptor)

    @contextmanager
    def _mutation_lock(self) -> Iterator[int]:
        descriptor = -1
        created = False
        with self._state_namespace_directory() as namespace_fd:
            try:
                try:
                    descriptor = os.open(
                        "mutation.lock", os.O_CREAT | os.O_EXCL | os.O_RDWR | _NOFOLLOW,
                        0o600, dir_fd=namespace_fd,
                    )
                    created = True
                except FileExistsError:
                    descriptor = os.open("mutation.lock", os.O_RDWR | _NOFOLLOW, dir_fd=namespace_fd)
                info = os.fstat(descriptor)
                if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or info.st_size != 0:
                    raise LifeOSError("Existing Life OS mutation lock is unsafe")
                if created:
                    os.fchmod(descriptor, 0o600)
                elif stat.S_IMODE(info.st_mode) != 0o600:
                    raise LifeOSError("Existing Life OS mutation lock must have mode 0600")
            except LifeOSError:
                if descriptor >= 0:
                    os.close(descriptor)
                raise
            except OSError:
                if descriptor >= 0:
                    os.close(descriptor)
                raise LifeOSError("Life OS mutation lock is unavailable") from None
            with os.fdopen(descriptor, "a+b", closefd=True) as stream:
                try:
                    fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
                    yield namespace_fd
                finally:
                    fcntl.flock(stream.fileno(), fcntl.LOCK_UN)

    @contextmanager
    def _claims_directory(self, namespace_fd: int) -> Iterator[int]:
        descriptor = -1
        try:
            descriptor = os.open("claims", os.O_RDONLY | _DIRECTORY | _NOFOLLOW, dir_fd=namespace_fd)
            info = os.fstat(descriptor)
            if (
                not os.path.samestat(self._claims_root_identity, info)
                or not stat.S_ISDIR(info.st_mode)
                or info.st_uid != os.geteuid()
                or stat.S_IMODE(info.st_mode) != 0o700
            ):
                raise LifeOSError("Life OS claim directory changed after runtime construction")
        except LifeOSError:
            if descriptor >= 0:
                os.close(descriptor)
            raise
        except OSError:
            if descriptor >= 0:
                os.close(descriptor)
            raise LifeOSError("Life OS claim directory is unavailable") from None
        try:
            yield descriptor
        finally:
            os.close(descriptor)

    @staticmethod
    def _claim_name(key: str) -> str:
        return hashlib.sha256(key.encode("utf-8")).hexdigest() + ".json"

    def _read_global_claim(self, namespace_fd: int, key: str) -> dict[str, Any] | None:
        with self._claims_directory(namespace_fd) as claims_fd:
            descriptor = -1
            try:
                descriptor = os.open(
                    self._claim_name(key), os.O_RDONLY | os.O_NONBLOCK | _NOFOLLOW,
                    dir_fd=claims_fd,
                )
            except FileNotFoundError:
                return None
            except OSError:
                raise LifeOSError("Life OS message claim is unavailable") from None
            try:
                info = os.fstat(descriptor)
                if (
                    not stat.S_ISREG(info.st_mode)
                    or info.st_uid != os.geteuid()
                    or stat.S_IMODE(info.st_mode) != 0o600
                ):
                    raise LifeOSError("Life OS message claim is unsafe")
                with os.fdopen(descriptor, "rb", closefd=True) as stream:
                    descriptor = -1
                    raw = stream.read().decode("utf-8")
                payload = json.loads(raw)
            except LifeOSError:
                raise
            except (OSError, UnicodeError, json.JSONDecodeError):
                raise LifeOSError("Life OS message claim is malformed") from None
            finally:
                if descriptor >= 0:
                    os.close(descriptor)
        if (
            not isinstance(payload, dict)
            or payload.get("version") != 1
            or payload.get("key") != key
            or payload.get("status") not in {"pending", "committed"}
            or not isinstance(payload.get("target"), dict)
            or (payload["status"] == "committed" and not isinstance(payload.get("outcome"), dict))
        ):
            raise LifeOSError("Life OS message claim is malformed")
        return payload

    def _write_global_claim(self, namespace_fd: int, key: str, payload: dict[str, Any]) -> None:
        raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        with self._claims_directory(namespace_fd) as claims_fd:
            self._atomic_replace_at(claims_fd, self._claim_name(key), raw)

    def _begin_global_claim(
        self, namespace_fd: int, key: str, target: dict[str, str],
    ) -> dict[str, Any]:
        existing = self._read_global_claim(namespace_fd, key)
        if existing is not None:
            if existing["target"] != target:
                if existing["status"] == "committed":
                    return existing
                raise LifeOSError("trusted message is already claimed by another Life OS target")
            return existing
        pending = {"version": 1, "key": key, "status": "pending", "target": target}
        self._write_global_claim(namespace_fd, key, pending)
        return pending

    def _commit_global_claim(
        self, namespace_fd: int, key: str, target: dict[str, str], outcome: dict[str, Any],
    ) -> bool:
        pending = {
            "version": 1, "key": key, "status": "pending", "target": target,
        }
        try:
            selected = date.fromisoformat(target["date"])
            operation = target["operation"]
        except (KeyError, TypeError, ValueError):
            raise LifeOSError("Life OS message claim target is malformed") from None
        if self._committed_outcome_for_key(selected, operation, key) is None:
            return False
        self._write_global_claim(namespace_fd, key, {
            "version": 1,
            "key": key,
            "status": "committed",
            "target": target,
            "outcome": outcome,
        })
        try:
            if self._committed_outcome_for_key(selected, operation, key) is None:
                self._write_global_claim(namespace_fd, key, pending)
                return False
            claim = self._read_global_claim(namespace_fd, key)
            if (
                claim is None
                or claim["status"] != "committed"
                or claim["target"] != target
            ):
                raise LifeOSError("Life OS message claim changed during commit")
            if self._committed_outcome_for_key(selected, operation, key) is not None:
                return True
        except LifeOSError:
            self._write_global_claim(namespace_fd, key, pending)
            raise
        self._write_global_claim(namespace_fd, key, pending)
        return False

    def _committed_outcome_for_key(
        self, selected: date, operation: str, key: str,
    ) -> dict[str, Any] | None:
        if operation == "capture":
            path = self.capture_path(selected)
            with self._capture_directory() as directory_fd:
                content = self._read_capture_at(directory_fd, path.name)
            if content is not None and content.count(f"{_MESSAGE_PREFIX}{key} %%") == 1:
                return {
                    "path": str(path), "date": selected.isoformat(),
                    "status": "captured", "duplicate": True,
                }
            return None
        text = self._read_daily(selected)
        if text is None or text.count(f"{_MESSAGE_PREFIX}{key} %%") != 1:
            return None
        document, state = self._parse_block(text, selected)
        return self._result(
            self.daily_path(selected), state, content=document.content, duplicate=True,
        )

    def _ensure_daily(self, selected: date) -> Path:
        path = self.daily_path(selected)
        for _attempt in range(3):
            try:
                if self._read_daily_snapshot(selected) is not None:
                    return path
                break
            except _ConcurrentMutation:
                continue
        else:
            raise LifeOSError("Daily note changed concurrently; retry the operation")
        template = self._read_template()
        rendered, count = _SNAPSHOT_LINE.subn("", template)
        if count > 1 or _TEMPLATE_EXPRESSION.search(rendered) or "<%" in rendered:
            raise LifeOSError("Daily template contains an unsupported expression")
        try:
            self._publish_daily(selected, rendered, None)
        except _ConcurrentMutation:
            try:
                current = self._read_daily_snapshot(selected)
            except _ConcurrentMutation:
                current = None
            if current is None:
                raise LifeOSError("Daily note changed concurrently; retry the operation") from None
        return path

    @contextmanager
    def _daily_directory(self, selected: date, *, create: bool) -> Iterator[int]:
        descriptors: list[int] = []
        try:
            vault_fd = os.open(self.vault_root, os.O_RDONLY | _DIRECTORY | _NOFOLLOW)
            descriptors.append(vault_fd)
            if not os.path.samestat(self._vault_identity, os.fstat(vault_fd)):
                raise LifeOSError("Vault root changed after runtime construction")
            life_fd = os.open("Life OS", os.O_RDONLY | _DIRECTORY | _NOFOLLOW, dir_fd=vault_fd)
            descriptors.append(life_fd)
            if not os.path.samestat(self._life_identity, os.fstat(life_fd)):
                raise LifeOSError("Life OS directory changed after runtime construction")
            periodic_fd = os.open(
                "0. PeriodicNotes", os.O_RDONLY | _DIRECTORY | _NOFOLLOW, dir_fd=life_fd,
            )
            descriptors.append(periodic_fd)
            if not os.path.samestat(self._periodic_identity, os.fstat(periodic_fd)):
                raise LifeOSError("Periodic notes directory changed after runtime construction")
            current_fd = periodic_fd
            for name in (f"{selected:%Y}", "Daily", f"{selected:%m}"):
                if create:
                    try:
                        os.mkdir(name, mode=0o755, dir_fd=current_fd)
                    except FileExistsError:
                        pass
                try:
                    before = os.stat(name, dir_fd=current_fd, follow_symlinks=False)
                except FileNotFoundError:
                    if create:
                        raise LifeOSError("Daily directory changed during validation") from None
                    raise _DailyMissing from None
                if stat.S_ISLNK(before.st_mode) or not stat.S_ISDIR(before.st_mode):
                    raise LifeOSError("Daily directory must be a non-symlink directory")
                child_fd = os.open(
                    name, os.O_RDONLY | _DIRECTORY | _NOFOLLOW, dir_fd=current_fd,
                )
                descriptors.append(child_fd)
                if not os.path.samestat(before, os.fstat(child_fd)):
                    raise LifeOSError("Daily directory changed during validation")
                if create:
                    os.fsync(current_fd)
                current_fd = child_fd
        except _DailyMissing:
            for descriptor in reversed(descriptors):
                os.close(descriptor)
            raise
        except LifeOSError:
            for descriptor in reversed(descriptors):
                os.close(descriptor)
            raise
        except OSError:
            for descriptor in reversed(descriptors):
                os.close(descriptor)
            raise LifeOSError("Daily directory is unavailable") from None
        try:
            yield current_fd
        finally:
            for descriptor in reversed(descriptors):
                os.close(descriptor)

    def _read_daily(self, selected: date) -> str | None:
        snapshot = self._read_daily_snapshot(selected)
        return None if snapshot is None else snapshot.text

    def _read_daily_snapshot(self, selected: date) -> _TextSnapshot | None:
        try:
            with self._daily_directory(selected, create=False) as directory_fd:
                return self._read_daily_snapshot_at(directory_fd, f"{selected:%Y-%m-%d}.md")
        except _DailyMissing:
            return None

    @staticmethod
    def _read_daily_snapshot_at(directory_fd: int, name: str) -> _TextSnapshot | None:
        LifeOSRuntime._reconcile_note_temps(directory_fd, name)
        return LifeOSRuntime._read_text_snapshot_at(
            directory_fd,
            name,
            unavailable="Daily note is unavailable",
            nonregular="Daily note must be a non-symlink file",
            unreadable="Daily note is unreadable",
        )

    def _publish_daily(
        self, selected: date, text: str, expected: _TextSnapshot | None,
    ) -> None:
        with self._daily_directory(selected, create=True) as directory_fd:
            self._atomic_publish_note_at(
                directory_fd, f"{selected:%Y-%m-%d}.md", text, expected,
            )

    def _document_and_state(
        self, text: str, selected: date,
    ) -> tuple[_Document, WorkflowState]:
        start_count, end_count = text.count(_START), text.count(_END)
        if start_count == 0 and end_count == 0:
            if _STATE_PREFIX in text:
                raise LifeOSError("Daily note contains an orphaned Life OS state")
            return self._install_block(text), self._initial_state(selected)
        return self._parse_block(text, selected)

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
        status = payload["status"]
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
                or status not in {"active", "paused"}
                or follow_up_count < 1
            ):
                raise ValueError("invalid pending follow-up")
            try:
                self._checked_follow_up(pending["question"])
            except LifeOSError:
                raise ValueError("invalid pending follow-up") from None
        last_key = payload["last_message_key"]
        if last_key is not None and (not isinstance(last_key, str) or not last_key):
            raise ValueError("invalid last message key")
        if status == "not_started" and (answered or skipped or next_question != 1):
            raise ValueError("invalid not-started state")
        if status == "completed" and (next_question is not None or set(answered) | set(skipped) != set(range(1, len(QUESTIONS) + 1))):
            raise ValueError("invalid completed state")
        if status in {"active", "paused"}:
            if next_question is None and pending is None:
                raise ValueError("invalid incomplete state")
            expected_progress = (
                set(range(1, len(QUESTIONS) + 1))
                if next_question is None
                else set(range(1, next_question))
            )
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
        text = checked_life_os_message_text(value)
        if any(marker in text for marker in (_START, _END, _STATE_PREFIX, _MESSAGE_PREFIX)):
            raise LifeOSError("message text contains a reserved marker")
        return text

    @staticmethod
    def _checked_follow_up(value: str) -> str:
        question = checked_life_os_message_text(value)
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

    @classmethod
    def _attachment_references(cls, content: str | None) -> list[str]:
        references: list[str] = []
        seen: set[str] = set()
        for match in _ATTACHMENT_LINK.finditer(content or ""):
            filename = match.group(1)
            name_match = _ATTACHMENT_NAME.fullmatch(filename)
            if name_match is None or int(name_match.group(1)) < 1:
                continue
            readable_name = name_match.group(2)
            if cls._readable_name(readable_name) != readable_name:
                continue
            reference = match.group(0)
            if reference not in seen:
                references.append(reference)
                seen.add(reference)
        return references

    def _result(
        self, path: Path, state: WorkflowState, *, content: str | None = None, **extra: Any,
    ) -> dict[str, Any]:
        result: dict[str, Any] = {
            "path": str(path),
            **asdict(state),
            "answered": list(state.answered),
            "skipped": list(state.skipped),
            "attachments": self._attachment_references(content),
            "question": (
                state.pending_follow_up["question"]
                if state.pending_follow_up is not None
                else self.QUESTIONS[state.next_question - 1] if state.next_question is not None else None
            ),
        }
        result.update(extra)
        return result


__all__ = ["LifeOSError", "LifeOSRuntime", "StoredAttachment", "WorkflowState"]
