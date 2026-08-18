"""Bounded, cron-authorized writer for FDE Community daily analysis Captures."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import date
import ctypes
import errno
import fcntl
import hashlib
import os
from pathlib import Path, PurePosixPath
import re
import secrets
import stat
from typing import Any, Callable, Iterator, Mapping, Sequence


class FDEDailyCaptureError(Exception):
    """The requested daily Capture cannot be safely written."""


_ROOM_CONTRACTS = {
    "public": {
        "cron_job_id": "fdc11961e59f",
        "filename": "CAPTURE - {date} - 오픈카톡 일일 분석.md",
        "title": "오픈카톡 일일 분석",
        "topics": ("forward-deployed-engineer", "community", "openchat"),
    },
    "operators": {
        "cron_job_id": "28e24dbebacd",
        "filename": "CAPTURE - {date} - 운영진방 일일 분석.md",
        "title": "운영진방 일일 분석",
        "topics": ("forward-deployed-engineer", "community", "openchat", "operations"),
    },
}
_SECTION_ORDER = (
    ("coverage", "수집 범위"),
    ("situation", "상황"),
    ("problems", "문제"),
    ("insights", "인사이트"),
    ("participant_map", "참여자 지형"),
    ("actions", "대상별 액션"),
    ("judgment_holds", "판단 보류"),
    ("wiki_candidates", "Wiki 축적 후보"),
)
_ALLOWED_KEYS = frozenset(key for key, _heading in _SECTION_ORDER)
_MAX_ITEM_CHARS = 5000
_MAX_ITEMS = 40
_MAX_FILE_BYTES = 96 * 1024
_MAX_READ_BYTES = 128 * 1024
_HASH_RE = re.compile(r"^[0-9a-f]{64}$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_SENSITIVE_PATTERNS = (
    re.compile(r"(?<!\d)01[016789]-?\d{3,4}-?\d{4}(?!\d)"),
    re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE),
    re.compile(r"\bmember_[0-9a-z_-]{4,}\b", re.IGNORECASE),
    re.compile(r"\b(?:화자|speaker)\s*[A-Z0-9_-]+\b", re.IGNORECASE),
    re.compile(r"<(?:@!?|@&|#)\d{17,20}>"),
    re.compile(r"(?<!\d)\d{17,20}(?!\d)"),
    re.compile(r"(?:sk-(?:proj-)?|gh[pousr]_|github_pat_|xox[baprs]-)[A-Za-z0-9_-]{16,}"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
)
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f\u2028\u2029]")
_DIRECT = getattr(os, "O_DIRECTORY", 0)
_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)
_NONBLOCK = getattr(os, "O_NONBLOCK", 0)


def _load_rename_primitives() -> tuple[tuple[Any, int] | None, tuple[Any, int] | None]:
    try:
        library = ctypes.CDLL(None, use_errno=True)
        if sys_platform() == "darwin":
            function = library.renameatx_np
            function.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
            function.restype = ctypes.c_int
            return (function, 0x00000004 | 0x00000010), (function, 0x00000002 | 0x00000010)
        if sys_platform().startswith("linux"):
            function = library.renameat2
            function.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
            function.restype = ctypes.c_int
            return (function, 0x00000001), (function, 0x00000002)
    except (AttributeError, OSError):
        pass
    return None, None


def sys_platform() -> str:
    import sys

    return sys.platform


_EXCLUSIVE_RENAME, _EXCHANGE_RENAME = _load_rename_primitives()


def _rename_at(binding: tuple[Any, int], directory_fd: int, source: str, target: str) -> None:
    function, flags = binding
    result = function(
        directory_fd,
        os.fsencode(source),
        directory_fd,
        os.fsencode(target),
        flags,
    )
    if result != 0:
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error))


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _valid_hash(value: Any) -> bool:
    return isinstance(value, str) and _HASH_RE.fullmatch(value) is not None


def _validate_date(value: Any) -> str:
    if not isinstance(value, str) or _DATE_RE.fullmatch(value) is None:
        raise FDEDailyCaptureError("analysis_date must be YYYY-MM-DD")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise FDEDailyCaptureError("analysis_date is invalid") from exc
    if parsed.isoformat() != value:
        raise FDEDailyCaptureError("analysis_date is invalid")
    return value


def _checked_text(value: Any, *, label: str) -> str:
    if not isinstance(value, str):
        raise FDEDailyCaptureError(f"{label} must be text")
    text = value.strip()
    if not text or len(text) > _MAX_ITEM_CHARS:
        raise FDEDailyCaptureError(f"{label} is empty or too long")
    if _CONTROL_RE.search(text):
        raise FDEDailyCaptureError(f"{label} contains unsupported control characters")
    if any(pattern.search(text) for pattern in _SENSITIVE_PATTERNS):
        raise FDEDailyCaptureError(f"{label} contains sensitive or internal identifiers")
    return text


def _normalize_sections(value: Any) -> dict[str, tuple[str, ...]]:
    if not isinstance(value, Mapping) or set(value) != _ALLOWED_KEYS:
        raise FDEDailyCaptureError("sections have an invalid shape")
    normalized: dict[str, tuple[str, ...]] = {}
    for key, _heading in _SECTION_ORDER:
        raw = value[key]
        if isinstance(raw, str):
            items = (_checked_text(raw, label=key),)
        elif isinstance(raw, Sequence) and not isinstance(raw, (bytes, bytearray, str)):
            if not raw or len(raw) > _MAX_ITEMS:
                raise FDEDailyCaptureError(f"{key} is empty or too large")
            items = tuple(_checked_text(item, label=key) for item in raw)
        else:
            raise FDEDailyCaptureError(f"{key} must be text or a list of text")
        normalized[key] = items
    return normalized


def _render_markdown(room_kind: str, analysis_date: str, sections: Mapping[str, tuple[str, ...]]) -> bytes:
    contract = _ROOM_CONTRACTS[room_kind]
    lines = [
        "---",
        "type: capture",
        "area: fde-community",
        "status: inbox",
        "source: kakao",
        f"created: {analysis_date}",
        f"updated: {analysis_date}",
        "topics:",
        *(f"  - {topic}" for topic in contract["topics"]),
        "---",
        "",
        f"# {contract['title']} — {analysis_date}",
        "",
    ]
    for key, heading in _SECTION_ORDER:
        lines.append(f"## {heading}")
        values = sections[key]
        if len(values) == 1 and key == "coverage":
            lines.append(values[0])
        else:
            lines.extend(f"- {item}" for item in values)
        lines.append("")
    data = ("\n".join(lines).rstrip() + "\n").encode("utf-8")
    if len(data) > _MAX_FILE_BYTES:
        raise FDEDailyCaptureError("rendered Capture is too large")
    return data


def _open_directory(root: Path) -> tuple[int, int]:
    root_fd = -1
    inbox_fd = -1
    try:
        root_fd = os.open(root, os.O_RDONLY | _DIRECT | _NOFOLLOW)
        fde_fd = os.open("FDE Community", os.O_RDONLY | _DIRECT | _NOFOLLOW, dir_fd=root_fd)
        try:
            inbox_fd = os.open("Inbox", os.O_RDONLY | _DIRECT | _NOFOLLOW, dir_fd=fde_fd)
        finally:
            os.close(fde_fd)
        return root_fd, inbox_fd
    except OSError as exc:
        for descriptor in (inbox_fd, root_fd):
            if descriptor >= 0:
                os.close(descriptor)
        raise FDEDailyCaptureError("FDE Community Inbox is unavailable or unsafe") from exc


def _read_leaf(directory_fd: int, name: str) -> tuple[bytes | None, os.stat_result | None]:
    file_fd = -1
    try:
        try:
            file_fd = os.open(name, os.O_RDONLY | _NOFOLLOW | _NONBLOCK, dir_fd=directory_fd)
        except FileNotFoundError:
            return None, None
        info = os.fstat(file_fd)
        if not stat.S_ISREG(info.st_mode) or info.st_size > _MAX_READ_BYTES:
            raise FDEDailyCaptureError("daily Capture target is not a bounded regular file")
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = os.read(file_fd, min(1024 * 1024, _MAX_READ_BYTES + 1 - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if total > _MAX_READ_BYTES:
                raise FDEDailyCaptureError("daily Capture target is too large")
        after = os.fstat(file_fd)
        if (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns) != (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
        ):
            raise FDEDailyCaptureError("daily Capture changed while being read")
        return b"".join(chunks), after
    except OSError as exc:
        raise FDEDailyCaptureError("daily Capture could not be read safely") from exc
    finally:
        if file_fd >= 0:
            os.close(file_fd)


def _write_stage(directory_fd: int, data: bytes) -> str:
    stage = f".fde-daily-capture-{secrets.token_hex(12)}"
    file_fd = -1
    try:
        file_fd = os.open(stage, os.O_WRONLY | os.O_CREAT | os.O_EXCL | _NOFOLLOW, 0o600, dir_fd=directory_fd)
        offset = 0
        while offset < len(data):
            written = os.write(file_fd, data[offset:])
            if written <= 0:
                raise OSError(errno.EIO, "short write")
            offset += written
        os.fsync(file_fd)
        info = os.fstat(file_fd)
        if not stat.S_ISREG(info.st_mode) or info.st_size != len(data):
            raise OSError(errno.EIO, "invalid stage")
        return stage
    except OSError as exc:
        if stage:
            try:
                os.unlink(stage, dir_fd=directory_fd)
            except FileNotFoundError:
                pass
        raise FDEDailyCaptureError("daily Capture stage could not be written") from exc
    finally:
        if file_fd >= 0:
            os.close(file_fd)


@contextmanager
def _writer_lock(lock_root: Path) -> Iterator[None]:
    lock_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    lock_path = lock_root / "fde-daily-capture.lock"
    file_fd = os.open(lock_path, os.O_RDWR | os.O_CREAT | _NOFOLLOW, 0o600)
    try:
        fcntl.flock(file_fd, fcntl.LOCK_EX)
        yield
    except OSError as exc:
        raise FDEDailyCaptureError("daily Capture writer lock failed") from exc
    finally:
        try:
            fcntl.flock(file_fd, fcntl.LOCK_UN)
        finally:
            os.close(file_fd)


class FDEDailyCaptureRuntime:
    """Create or compare-and-swap one fixed daily Capture under FDE Community/Inbox."""

    def __init__(self, *, vault_root: Path, lock_root: Path) -> None:
        self.vault_root = Path(vault_root).expanduser().resolve(strict=True)
        self.lock_root = Path(lock_root).expanduser()
        self.before_commit_hook: Callable[[Path], None] | None = None

    @classmethod
    def from_environment(cls) -> "FDEDailyCaptureRuntime":
        vault = os.getenv("DONGGU_FDE_COMMUNITY_VAULT_ROOT", "").strip()
        if not vault:
            raise FDEDailyCaptureError("DONGGU_FDE_COMMUNITY_VAULT_ROOT is required")
        try:
            from hermes_constants import get_hermes_home  # type: ignore[reportMissingImports]

            state_root = Path(get_hermes_home()) / "state" / "donggu-obsidian" / "fde-daily-capture"
        except Exception:
            state_root = Path.home() / ".hermes" / "state" / "donggu-obsidian" / "fde-daily-capture"
        return cls(vault_root=Path(vault), lock_root=state_root)

    def upsert(
        self,
        *,
        room_kind: str,
        analysis_date: str,
        expected_before_sha256: str | None,
        sections: Any,
        cron_job_id: str,
    ) -> dict[str, Any]:
        if room_kind not in _ROOM_CONTRACTS:
            raise FDEDailyCaptureError("room_kind is not supported")
        contract = _ROOM_CONTRACTS[room_kind]
        if cron_job_id != contract["cron_job_id"]:
            raise FDEDailyCaptureError("cron job is not authorized for this Capture")
        normalized_date = _validate_date(analysis_date)
        if expected_before_sha256 is not None and not _valid_hash(expected_before_sha256):
            raise FDEDailyCaptureError("expected_before_sha256 is invalid")
        normalized_sections = _normalize_sections(sections)
        desired = _render_markdown(room_kind, normalized_date, normalized_sections)
        desired_hash = _sha256_bytes(desired)
        filename = contract["filename"].format(date=normalized_date)
        relative = PurePosixPath("FDE Community", "Inbox", filename)
        target_path = self.vault_root / relative

        with _writer_lock(self.lock_root):
            root_fd = -1
            directory_fd = -1
            stage: str | None = None
            swapped = False
            try:
                root_fd, directory_fd = _open_directory(self.vault_root)
                current, current_info = _read_leaf(directory_fd, filename)
                before_hash = None if current is None else _sha256_bytes(current)
                if current == desired:
                    return {
                        "status": "unchanged",
                        "path": str(relative),
                        "before_sha256": before_hash,
                        "after_sha256": desired_hash,
                        "bytes": len(desired),
                        "readback_verified": True,
                    }
                if current is None:
                    if expected_before_sha256 is not None:
                        raise FDEDailyCaptureError("daily Capture precondition changed")
                    if _EXCLUSIVE_RENAME is None:
                        raise FDEDailyCaptureError("exclusive atomic install is unavailable")
                else:
                    if expected_before_sha256 is None or expected_before_sha256 != before_hash:
                        raise FDEDailyCaptureError("daily Capture precondition changed")
                    if _EXCHANGE_RENAME is None:
                        raise FDEDailyCaptureError("atomic exchange is unavailable")

                stage = _write_stage(directory_fd, desired)
                if self.before_commit_hook is not None:
                    self.before_commit_hook(target_path)
                if current is None:
                    try:
                        _rename_at(_EXCLUSIVE_RENAME, directory_fd, stage, filename)
                    except FileExistsError as exc:
                        raise FDEDailyCaptureError("daily Capture appeared concurrently") from exc
                    stage = None
                else:
                    _rename_at(_EXCHANGE_RENAME, directory_fd, stage, filename)
                    swapped = True
                    captured, _captured_info = _read_leaf(directory_fd, stage)
                    captured_hash = None if captured is None else _sha256_bytes(captured)
                    if captured_hash != before_hash:
                        _rename_at(_EXCHANGE_RENAME, directory_fd, stage, filename)
                        swapped = False
                        raise FDEDailyCaptureError("daily Capture changed concurrently")

                os.fsync(directory_fd)
                readback, readback_info = _read_leaf(directory_fd, filename)
                if readback != desired or readback_info is None:
                    if current is None:
                        try:
                            os.unlink(filename, dir_fd=directory_fd)
                        except FileNotFoundError:
                            pass
                        os.fsync(directory_fd)
                    elif swapped and stage is not None:
                        _rename_at(_EXCHANGE_RENAME, directory_fd, stage, filename)
                        swapped = False
                        os.fsync(directory_fd)
                    raise FDEDailyCaptureError("daily Capture read-back failed")
                after_hash = _sha256_bytes(readback)
                if after_hash != desired_hash:
                    raise FDEDailyCaptureError("daily Capture read-back hash mismatch")

                if stage is not None:
                    os.unlink(stage, dir_fd=directory_fd)
                    stage = None
                    os.fsync(directory_fd)
                return {
                    "status": "created" if current is None else "updated",
                    "path": str(relative),
                    "before_sha256": before_hash,
                    "after_sha256": after_hash,
                    "bytes": len(readback),
                    "readback_verified": True,
                }
            except OSError as exc:
                raise FDEDailyCaptureError("daily Capture atomic commit failed") from exc
            finally:
                if stage is not None and directory_fd >= 0:
                    try:
                        os.unlink(stage, dir_fd=directory_fd)
                    except FileNotFoundError:
                        pass
                    except OSError:
                        pass
                for descriptor in (directory_fd, root_fd):
                    if descriptor >= 0:
                        os.close(descriptor)
