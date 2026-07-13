#!/usr/bin/env python3
"""Apply one bounded, deterministic CORE review action to a local Vault."""

import hashlib
import ctypes
import json
import os
import platform
from pathlib import Path, PurePosixPath
import re
import secrets
import stat
import sys
from typing import Dict, List, Optional, TextIO, Tuple

MAX_STDIN = 1024 * 1024
MAX_FILE = 8 * 1024 * 1024
MAX_TEXT_FIELD = 64 * 1024
MAX_TARGETS = 20
JOURNAL = ".core-review-journal.json"
ALLOWED_ROOTS = ("10_Sources", "20_Core", "40_Snippets", "50_Channel_Packs", "60_MOCs")
CANDIDATE_TYPES = {"new_core", "link_existing", "merge", "fix_link", "classify", "status_cleanup", "skill_drift"}
ENVELOPE_KEYS = {
    "schema_version", "candidate_code", "candidate_type", "source_note_path",
    "source_sha256", "claim", "target_note_paths", "action",
}
REPLACE_KEYS = {"op", "schema_version", "old", "new"}
CREATE_KEYS = {
    "op", "schema_version", "template_version", "core_path", "moc_path",
    "moc_sha256", "trace_field",
}
HASH_RE = re.compile(r"^[0-9a-f]{64}$")
CODE_RE = re.compile(r"^CR-[0-9]{8}-[0-9]{6}$")
WIKILINK_RE = re.compile(r"\[\[([^\[\]]+)\]\]")
NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)
DIRECTORY = getattr(os, "O_DIRECTORY", 0)
NONBLOCK = getattr(os, "O_NONBLOCK", 0)
RENAME_SWAP = 0x00000002
RENAME_EXCL = 0x00000004
RENAME_NOFOLLOW_ANY = 0x00000010


def _load_renameatx():
    if platform.system() != "Darwin":
        return None
    try:
        function = ctypes.CDLL(None, use_errno=True).renameatx_np
        function.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
        function.restype = ctypes.c_int
        return function
    except (AttributeError, OSError):
        return None


RENAMEATX_NP = _load_renameatx()


class ValidationError(Exception):
    pass


class ApplyError(Exception):
    pass


class CleanupRetryError(Exception):
    pass


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def exact_keys(value: object, keys: set) -> Dict[str, object]:
    if not isinstance(value, dict) or set(value) != keys:
        raise ValidationError()
    return value


def bounded_string(value: object, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str):
        raise ValidationError()
    try:
        encoded = value.encode("utf-8")
    except UnicodeError:
        raise ValidationError()
    if len(encoded) > MAX_TEXT_FIELD or (not allow_empty and not value):
        raise ValidationError()
    if any(ord(ch) < 32 and ch not in "\t\n\r" for ch in value):
        raise ValidationError()
    return value


def validate_hash(value: object) -> str:
    if not isinstance(value, str) or HASH_RE.fullmatch(value) is None:
        raise ValidationError()
    return value


def safe_relative(value: object, expected_root: str) -> Tuple[str, PurePosixPath]:
    text = bounded_string(value)
    if "\\" in text or any(ch in text for ch in "\r\n\t[]#|^\""):
        raise ValidationError()
    path = PurePosixPath(text)
    if path.is_absolute() or str(path) != text or path.suffix != ".md":
        raise ValidationError()
    if len(path.parts) < 2 or path.parts[0] != expected_root:
        raise ValidationError()
    if any(part in ("", ".", "..", "00_Inbox") or part.startswith(".env") for part in path.parts):
        raise ValidationError()
    return text, path


def open_root(root: Path) -> int:
    fd = -1
    try:
        if not root.is_absolute():
            raise OSError()
        if (
            len(root.parts) > 1
            and root.parts[1] == "var"
            and os.path.realpath("/var") == "/private/var"
        ):
            root = Path("/private/var", *root.parts[2:])
        fd = os.open(root.anchor, os.O_RDONLY | DIRECTORY | NOFOLLOW)
        for part in root.parts[1:]:
            next_fd = os.open(part, os.O_RDONLY | DIRECTORY | NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = next_fd
        if not stat.S_ISDIR(os.fstat(fd).st_mode):
            raise OSError()
        return fd
    except OSError:
        if fd >= 0:
            try:
                os.close(fd)
            except OSError:
                pass
        raise ValidationError()


class PathRef:
    def __init__(self, root: Path, rel: PurePosixPath, must_exist: bool):
        self.root = root
        self.rel = rel
        self.name = rel.parts[-1]
        self.root_fd = open_root(root)
        self.root_identity = self._identity(self.root_fd)
        fd = os.dup(self.root_fd)
        try:
            for part in rel.parts[:-1]:
                next_fd = os.open(part, os.O_RDONLY | DIRECTORY | NOFOLLOW, dir_fd=fd)
                os.close(fd)
                fd = next_fd
                if not stat.S_ISDIR(os.fstat(fd).st_mode):
                    raise OSError()
            self.parent_fd = fd
            self.parent_identity = self._identity(fd)
            fd = -1
            exists = self.exists()
            if must_exist != exists:
                raise ValidationError()
            if exists:
                info = os.stat(self.name, dir_fd=self.parent_fd, follow_symlinks=False)
                if not stat.S_ISREG(info.st_mode):
                    raise ValidationError()
        except (OSError, ValidationError):
            if fd >= 0:
                os.close(fd)
            os.close(self.root_fd)
            raise ValidationError()

    @staticmethod
    def _identity(fd: int) -> Tuple[int, int]:
        info = os.fstat(fd)
        return info.st_dev, info.st_ino

    def exists(self) -> bool:
        try:
            os.stat(self.name, dir_fd=self.parent_fd, follow_symlinks=False)
            return True
        except FileNotFoundError:
            return False
        except OSError:
            raise ValidationError()

    def revalidate_parent(self) -> bool:
        fd = -1
        try:
            fd = open_root(self.root)
            if self._identity(fd) != self.root_identity:
                return False
            for part in self.rel.parts[:-1]:
                next_fd = os.open(part, os.O_RDONLY | DIRECTORY | NOFOLLOW, dir_fd=fd)
                os.close(fd)
                fd = next_fd
            return self._identity(fd) == self.parent_identity
        except (OSError, ValidationError):
            return False
        finally:
            if fd >= 0:
                os.close(fd)


def checked_path(root: Path, rel: PurePosixPath, must_exist: bool) -> PathRef:
    return PathRef(root, rel, must_exist)


def read_at(parent_fd: int, name: str, *, max_size: int = MAX_FILE, text: bool = True) -> bytes:
    fd = -1
    try:
        fd = os.open(name, os.O_RDONLY | NOFOLLOW | NONBLOCK, dir_fd=parent_fd)
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_size > max_size:
            raise ValidationError()
        chunks = []
        total = 0
        while True:
            chunk = os.read(fd, min(1024 * 1024, max_size + 1 - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if total > max_size:
                raise ValidationError()
        after = os.fstat(fd)
        if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
                after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns):
            raise ValidationError()
        data = b"".join(chunks)
    except (OSError, OverflowError):
        raise ValidationError()
    finally:
        if fd >= 0:
            os.close(fd)
    if text:
        try:
            decoded = data.decode("utf-8")
        except UnicodeDecodeError:
            raise ValidationError()
        if any(ord(ch) < 32 and ch not in "\t\n\r" for ch in decoded):
            raise ValidationError()
    return data


def read_regular(path: PathRef) -> bytes:
    if not path.revalidate_parent():
        raise ValidationError()
    data = read_at(path.parent_fd, path.name)
    if not path.revalidate_parent():
        raise ValidationError()
    return data


def wikilink(path: str) -> str:
    return "[[" + path[:-3] + "]]"


def canonical_link_target(raw: str) -> str:
    target = raw.split("|", 1)[0].split("#", 1)[0]
    if target.endswith(".md"):
        target = target[:-3]
    rel = target + ".md"
    root = PurePosixPath(rel).parts[0] if PurePosixPath(rel).parts else ""
    if root not in ALLOWED_ROOTS:
        raise ValidationError()
    return safe_relative(rel, root)[0]


def link_targets(text: str) -> List[str]:
    return [canonical_link_target(match.group(1)) for match in WIKILINK_RE.finditer(text)]


def contains_link(text: str, rel: str) -> bool:
    for match in WIKILINK_RE.finditer(text):
        try:
            if canonical_link_target(match.group(1)) == rel:
                return True
        except ValidationError:
            # Existing notes may contain title-only links.  They cannot equal a
            # path-qualified target and are irrelevant to canonical duplicate
            # detection.
            continue
    return False


def newline_of(text: str) -> str:
    return "\r\n" if "\r\n" in text else "\n"


def append_frontmatter_link(data: bytes, field: str, link: str) -> bytes:
    text = data.decode("utf-8")
    target = canonical_link_target(link[2:-2])
    if contains_link(text, target):
        raise ValidationError()
    nl = newline_of(text)
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].rstrip("\r\n") != "---":
        raise ValidationError()
    end = next((i for i in range(1, len(lines)) if lines[i].rstrip("\r\n") == "---"), None)
    if end is None:
        raise ValidationError()
    matches = [i for i in range(1, end) if re.match(r"^" + re.escape(field) + r"\s*:", lines[i])]
    if len(matches) > 1:
        raise ValidationError()
    item = '  - "' + link + '"' + nl
    if not matches:
        lines[end:end] = [field + ":" + nl, item]
        return "".join(lines).encode("utf-8")
    index = matches[0]
    match = re.fullmatch(re.escape(field) + r"\s*:\s*(.*?)\r?\n?", lines[index])
    if match is None:
        raise ValidationError()
    tail = match.group(1).strip()
    if tail:
        if tail == "[]":
            lines[index:index + 1] = [field + ":" + nl, item]
        else:
            try:
                values = json.loads(tail)
            except (ValueError, TypeError):
                raise ValidationError()
            if not isinstance(values, list) or not all(isinstance(v, str) for v in values):
                raise ValidationError()
            if any(contains_link(value, target) for value in values):
                raise ValidationError()
            rendered = [field + ":" + nl]
            rendered.extend('  - "' + value.replace('"', '\\"') + '"' + nl for value in values + [link])
            lines[index:index + 1] = rendered
    else:
        insert = index + 1
        item_indent = None
        while insert < end:
            if not lines[insert].strip():
                insert += 1
                continue
            list_match = re.fullmatch(r"(\s*)-\s+.+\r?\n?", lines[insert])
            if list_match is None:
                break
            if item_indent is None:
                item_indent = list_match.group(1)
            elif list_match.group(1) != item_indent:
                raise ValidationError()
            insert += 1
        if item_indent is None:
            raise ValidationError()
        lines.insert(insert, item_indent + '- "' + link + '"' + nl)
    return "".join(lines).encode("utf-8")


def append_moc_link(data: bytes, link: str) -> bytes:
    text = data.decode("utf-8")
    target = canonical_link_target(link[2:-2])
    if contains_link(text, target):
        raise ValidationError()
    nl = newline_of(text)
    lines = text.splitlines(keepends=True)
    supported = {"## 연결된 CORE", "## 💡 Core 연결"}
    headings = [i for i, line in enumerate(lines) if line.rstrip("\r\n") in supported]
    if len(headings) > 1:
        raise ValidationError()
    item = "- " + link + nl
    if not headings:
        if text and not text.endswith(("\n", "\r")):
            text += nl
        if text and not text.endswith(nl + nl):
            text += nl
        return (text + "## 연결된 CORE" + nl + nl + item).encode("utf-8")
    start = headings[0]
    next_heading = next((i for i in range(start + 1, len(lines)) if re.match(r"^##\s+", lines[i])), len(lines))
    insert = next_heading
    while insert > start + 1 and not lines[insert - 1].strip():
        insert -= 1
    addition = []
    if insert == start + 1 or lines[insert - 1].strip():
        addition.append(nl)
    addition.append(item)
    if next_heading < len(lines):
        addition.append(nl)
    lines[insert:insert] = addition
    return "".join(lines).encode("utf-8")


def core_template(claim: str, source_link: str, moc_link: str) -> bytes:
    if "\r" in claim or "\n" in claim or any(ord(ch) < 32 for ch in claim):
        raise ValidationError()
    return (
        "---\ntype: core\ntemplate_version: 1\nsource: \"" + source_link +
        "\"\nmoc: \"" + moc_link + "\"\n---\n\n# " + claim + "\n\n" + claim + "\n"
    ).encode("utf-8")


def result_json(status_value: str, originals: Dict[str, Optional[bytes]], desired: Dict[str, bytes], candidate_code: Optional[str] = None) -> str:
    paths = sorted(desired)
    hashes = {}
    for rel in paths:
        before = originals.get(rel)
        hashes[rel] = {"before": digest(before) if before is not None else None, "after": digest(desired[rel])}
    payload = {"status": status_value, "paths": paths, "hashes": hashes}
    if candidate_code is not None:
        payload.update({"candidate_code": candidate_code, "state": "committed"})
    return json.dumps(payload, separators=(",", ":"), sort_keys=True)


def reject_duplicate_keys(pairs: List[Tuple[str, object]]) -> Dict[str, object]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValidationError()
        result[key] = value
    return result


def parse_envelope(stdin: TextIO) -> Dict[str, object]:
    raw = stdin.read(MAX_STDIN + 1)
    try:
        size = len(raw.encode("utf-8"))
    except UnicodeError:
        raise ValidationError()
    if size > MAX_STDIN:
        raise ValidationError()
    try:
        value = json.loads(raw, object_pairs_hook=reject_duplicate_keys)
    except (ValueError, TypeError):
        raise ValidationError()
    env = exact_keys(value, ENVELOPE_KEYS)
    candidate_type = bounded_string(env["candidate_type"])
    if candidate_type not in CANDIDATE_TYPES:
        raise ValidationError()
    if type(env["schema_version"]) is not int or env["schema_version"] != 1 or CODE_RE.fullmatch(bounded_string(env["candidate_code"])) is None:
        raise ValidationError()
    if env["claim"] is not None:
        bounded_string(env["claim"])
    validate_hash(env["source_sha256"])
    targets = env["target_note_paths"]
    if not isinstance(targets, list) or not all(isinstance(item, str) for item in targets):
        raise ValidationError()
    if targets != sorted(set(targets)) or len(targets) > MAX_TARGETS:
        raise ValidationError()
    return env


def prepare(root: Path, env: Dict[str, object]) -> Tuple[Dict[str, PathRef], Dict[str, Optional[bytes]], Dict[str, bytes]]:
    source_value = bounded_string(env["source_note_path"])
    source_root = PurePosixPath(source_value).parts[0] if PurePosixPath(source_value).parts else ""
    if source_root not in ALLOWED_ROOTS:
        raise ValidationError()
    source_rel, source_parts = safe_relative(source_value, source_root)
    source_path = checked_path(root, source_parts, True)
    source_data = read_regular(source_path)
    if digest(source_data) != env["source_sha256"]:
        raise ValidationError()
    action = env["action"]
    if not isinstance(action, dict):
        raise ValidationError()
    op = action.get("op")
    candidate_type = env["candidate_type"]
    paths = {source_rel: source_path}
    originals: Dict[str, Optional[bytes]] = {source_rel: source_data}
    desired: Dict[str, bytes] = {}

    if op == "replace":
        exact_keys(action, REPLACE_KEYS)
        if candidate_type not in ("fix_link", "link_existing"):
            raise ValidationError()
        if type(action["schema_version"]) is not int or action["schema_version"] != 1:
            raise ValidationError()
        target_values = env["target_note_paths"]
        if not isinstance(target_values, list) or not 1 <= len(target_values) <= MAX_TARGETS:
            raise ValidationError()
        checked_targets = []
        for target in target_values:
            target_text = bounded_string(target)
            target_root = PurePosixPath(target_text).parts[0] if PurePosixPath(target_text).parts else ""
            if target_root not in ALLOWED_ROOTS:
                raise ValidationError()
            target_rel, target_parts = safe_relative(target_text, target_root)
            target_ref = checked_path(root, target_parts, True)
            target_data = read_regular(target_ref)
            paths[target_rel] = target_ref
            originals[target_rel] = target_data
            checked_targets.append(target_rel)
        old = bounded_string(action["old"])
        new = bounded_string(action["new"])
        new_targets = link_targets(new)
        if len(new_targets) != len(set(new_targets)) or sorted(new_targets) != checked_targets:
            raise ValidationError()
        old_bytes, new_bytes = old.encode("utf-8"), new.encode("utf-8")
        if source_data.count(old_bytes) != 1:
            raise ValidationError()
        result = source_data.replace(old_bytes, new_bytes, 1)
        if len(result) > MAX_FILE:
            raise ValidationError()
        desired[source_rel] = result
        return paths, originals, desired

    if op != "create_core_with_backlink" or candidate_type != "new_core":
        raise ValidationError()
    if source_root not in ("10_Sources", "50_Channel_Packs"):
        raise ValidationError()
    exact_keys(action, CREATE_KEYS)
    if (type(action["schema_version"]) is not int or type(action["template_version"]) is not int or
            action["schema_version"] != 1 or action["template_version"] != 1):
        raise ValidationError()
    expected_trace = "extracted_to" if source_root == "10_Sources" else "decomposed_to"
    if action["trace_field"] != expected_trace:
        raise ValidationError()
    core_rel, core_parts = safe_relative(action["core_path"], "20_Core")
    moc_rel, moc_parts = safe_relative(action["moc_path"], "60_MOCs")
    targets = env["target_note_paths"]
    if not isinstance(targets, list) or targets != sorted([core_rel, moc_rel]) or len(targets) != 2:
        raise ValidationError()
    core_path = checked_path(root, core_parts, False)
    moc_path = checked_path(root, moc_parts, True)
    moc_data = read_regular(moc_path)
    if digest(moc_data) != validate_hash(action["moc_sha256"]):
        raise ValidationError()
    core_link, source_link, moc_link = wikilink(core_rel), wikilink(source_rel), wikilink(moc_rel)
    desired[source_rel] = append_frontmatter_link(source_data, expected_trace, core_link)
    desired[moc_rel] = append_moc_link(moc_data, core_link)
    desired[core_rel] = core_template(bounded_string(env["claim"]), source_link, moc_link)
    if any(len(data) > MAX_FILE for data in desired.values()):
        raise ValidationError()
    paths.update({core_rel: core_path, moc_rel: moc_path})
    originals.update({core_rel: None, moc_rel: moc_data})
    return paths, originals, desired


def fsync_fd(fd: int) -> None:
    os.fsync(fd)


def write_temp(parent_fd: int, prefix: str, data: bytes, mode: int) -> str:
    for _ in range(100):
        name = prefix + secrets.token_hex(12)
        fd = -1
        try:
            fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | NOFOLLOW, mode, dir_fd=parent_fd)
            os.fchmod(fd, mode)
            view = memoryview(data)
            while view:
                written = os.write(fd, view)
                if written <= 0:
                    raise OSError()
                view = view[written:]
            os.fsync(fd)
            os.close(fd)
            return name
        except FileExistsError:
            if fd >= 0:
                os.close(fd)
            continue
        except Exception:
            if fd >= 0:
                os.close(fd)
            try:
                os.unlink(name, dir_fd=parent_fd)
            except OSError:
                pass
            raise
    raise ApplyError()


def unlink_at(parent_fd: int, name: str) -> None:
    os.unlink(name, dir_fd=parent_fd)


def renameatx_at(parent_fd: int, source: str, target: str, flags: int) -> None:
    if RENAMEATX_NP is None:
        raise ApplyError()
    if "/" in source or "/" in target or not source or not target:
        raise ApplyError()
    result = RENAMEATX_NP(parent_fd, os.fsencode(source), parent_fd, os.fsencode(target), flags | RENAME_NOFOLLOW_ANY)
    if result != 0:
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error))


def atomic_swap_at(parent_fd: int, left: str, right: str) -> None:
    renameatx_at(parent_fd, left, right, RENAME_SWAP)


def atomic_exclusive_at(parent_fd: int, source: str, target: str) -> None:
    renameatx_at(parent_fd, source, target, RENAME_EXCL)


def name_hash(parent_fd: int, name: str) -> Optional[str]:
    try:
        return digest(read_at(parent_fd, name, text=False))
    except ValidationError:
        try:
            os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
        except FileNotFoundError:
            return None
        raise ApplyError()


def unchanged(path: PathRef, original: Optional[bytes]) -> bool:
    if not path.revalidate_parent():
        return False
    if original is None:
        try:
            return not path.exists()
        except ValidationError:
            return False
    try:
        return read_regular(path) == original
    except ValidationError:
        return False


def journal_bytes(candidate_code: str, token: str, state: str, paths: Dict[str, PathRef], originals: Dict[str, Optional[bytes]], desired: Dict[str, bytes], backups: Dict[str, Optional[str]], stages: Dict[str, str]) -> bytes:
    entries = []
    for rel in sorted(desired):
        original = originals[rel]
        mode = None
        if original is not None:
            mode = stat.S_IMODE(os.stat(paths[rel].name, dir_fd=paths[rel].parent_fd, follow_symlinks=False).st_mode)
        entries.append({
            "path": rel,
            "existed": original is not None,
            "backup": backups[rel],
            "stage": stages[rel],
            "before": digest(original) if original is not None else None,
            "after": digest(desired[rel]),
            "mode": mode,
        })
    return json.dumps({"version": 2, "candidate_code": candidate_code, "token": token, "state": state, "entries": entries}, separators=(",", ":"), sort_keys=True).encode("utf-8")


def install_journal(root: Path, data: bytes) -> None:
    root_fd = open_root(root)
    stage = None
    try:
        stage = write_temp(root_fd, ".core-review-journal-stage-", data, 0o600)
        atomic_exclusive_at(root_fd, stage, JOURNAL)
        stage = None
        fsync_fd(root_fd)
    finally:
        if stage is not None:
            try:
                unlink_at(root_fd, stage)
            except OSError:
                pass
        os.close(root_fd)


def rewrite_journal(root: Path, data: bytes) -> bool:
    root_fd = open_root(root)
    stage = None
    try:
        stage = write_temp(root_fd, ".core-review-journal-state-", data, 0o600)
        atomic_swap_at(root_fd, stage, JOURNAL)
        if name_hash(root_fd, stage) is None:
            raise ApplyError()
        fsync_fd(root_fd)
        try:
            unlink_at(root_fd, stage)
            stage = None
            fsync_fd(root_fd)
            return True
        except OSError:
            return False
    finally:
        if stage is not None:
            try:
                unlink_at(root_fd, stage)
            except OSError:
                pass
        os.close(root_fd)


def remove_journal(root: Path) -> None:
    root_fd = open_root(root)
    unlinked = False
    try:
        try:
            unlink_at(root_fd, JOURNAL)
            unlinked = True
        except FileNotFoundError:
            return
        try:
            fsync_fd(root_fd)
        except OSError:
            if not unlinked:
                raise
            # The runtime directory entry is already gone. A crash may make the
            # committed journal reappear, but matching ack is idempotent and can
            # safely run again on the next preflight.
            return
    finally:
        os.close(root_fd)


def journal_exists(root: Path) -> bool:
    root_fd = open_root(root)
    try:
        try:
            info = os.stat(JOURNAL, dir_fd=root_fd, follow_symlinks=False)
        except FileNotFoundError:
            return False
        return True
    finally:
        os.close(root_fd)


def cleanup_backups(paths: Dict[str, PathRef], backups: Dict[str, Optional[str]]) -> bool:
    ok = True
    for rel, name in backups.items():
        if name is None:
            continue
        try:
            unlink_at(paths[rel].parent_fd, name)
            fsync_fd(paths[rel].parent_fd)
        except FileNotFoundError:
            pass
        except OSError:
            ok = False
    return ok


def cleanup_artifacts(paths: Dict[str, PathRef], backups: Dict[str, Optional[str]], stages: Dict[str, str]) -> bool:
    ok = cleanup_backups(paths, backups)
    for rel, name in stages.items():
        try:
            unlink_at(paths[rel].parent_fd, name)
            fsync_fd(paths[rel].parent_fd)
        except FileNotFoundError:
            pass
        except OSError:
            ok = False
    return ok


def rollback(paths: Dict[str, PathRef], originals: Dict[str, Optional[bytes]], desired: Dict[str, bytes], stages: Dict[str, str]) -> bool:
    ok = True
    for rel in reversed(list(desired)):
        ref, original, stage = paths[rel], originals[rel], stages[rel]
        try:
            target_hash = name_hash(ref.parent_fd, ref.name)
            if original is None:
                if target_hash is None:
                    continue
                if target_hash != digest(desired[rel]):
                    raise ApplyError()
                capture = stage
                if name_hash(ref.parent_fd, capture) is not None:
                    raise ApplyError()
                atomic_exclusive_at(ref.parent_fd, ref.name, capture)
            else:
                if target_hash == digest(original):
                    continue
                if target_hash != digest(desired[rel]) or name_hash(ref.parent_fd, stage) != digest(original):
                    raise ApplyError()
                atomic_swap_at(ref.parent_fd, stage, ref.name)
            fsync_fd(ref.parent_fd)
        except Exception:
            ok = False
    for rel in desired:
        if not unchanged(paths[rel], originals[rel]):
            ok = False
    return ok


def cas_install(ref: PathRef, original: Optional[bytes], desired: bytes, stage: str) -> bool:
    if not ref.revalidate_parent():
        return False
    try:
        if original is None:
            atomic_exclusive_at(ref.parent_fd, stage, ref.name)
            return name_hash(ref.parent_fd, ref.name) == digest(desired)
        atomic_swap_at(ref.parent_fd, stage, ref.name)
        if name_hash(ref.parent_fd, stage) == digest(original):
            return name_hash(ref.parent_fd, ref.name) == digest(desired)
        atomic_swap_at(ref.parent_fd, stage, ref.name)
        return False
    except (OSError, ApplyError):
        return False


def apply_changes(candidate_code: str, paths: Dict[str, PathRef], originals: Dict[str, Optional[bytes]], desired: Dict[str, bytes]) -> int:
    order = sorted(desired, key=lambda rel: 0 if rel.startswith("20_Core/") else (1 if rel.startswith(("10_Sources/", "50_Channel_Packs/")) else 2))
    stages: Dict[str, str] = {}
    backups: Dict[str, Optional[str]] = {}
    journal_installed = False
    root = next(iter(paths.values())).root
    if RENAMEATX_NP is None:
        return 3
    token = secrets.token_hex(12)
    try:
        for rel in order:
            ref = paths[rel]
            original = originals[rel]
            mode = 0o644 if original is None else stat.S_IMODE(os.stat(ref.name, dir_fd=ref.parent_fd, follow_symlinks=False).st_mode)
            stages[rel] = write_temp(ref.parent_fd, ".core-review-stage-" + token + "-", desired[rel], mode)
        if not all(unchanged(paths[rel], originals[rel]) for rel in originals):
            raise ApplyError()
        for index, rel in enumerate(order):
            original = originals[rel]
            if original is None:
                backups[rel] = None
            else:
                backups[rel] = write_temp(paths[rel].parent_fd, ".core-review-backup-" + token + "-%d-" % index, original, 0o600)
                fsync_fd(paths[rel].parent_fd)
        prepared = journal_bytes(candidate_code, token, "prepared", paths, originals, desired, backups, stages)
        install_journal(root, prepared)
        journal_installed = True
        for rel in order:
            if not cas_install(paths[rel], originals[rel], desired[rel], stages[rel]):
                raise ApplyError()
            fsync_fd(paths[rel].parent_fd)
            if not paths[rel].revalidate_parent():
                raise ApplyError()
        for rel in order:
            if read_regular(paths[rel]) != desired[rel]:
                raise ApplyError()
        for rel in originals:
            if rel not in desired and not unchanged(paths[rel], originals[rel]):
                raise ApplyError()
        committed_data = journal_bytes(candidate_code, token, "committed", paths, originals, desired, backups, stages)
        journal_state_clean = rewrite_journal(root, committed_data)
        if not journal_state_clean:
            return 5
        return 0
    except Exception:
        restored = rollback(paths, originals, desired, stages)
        if restored and journal_installed:
            if cleanup_artifacts(paths, backups, stages):
                backups, stages = {}, {}
                try:
                    remove_journal(root)
                    journal_installed = False
                except Exception:
                    restored = False
            else:
                restored = False
        return 3 if restored else 4
    finally:
        if not journal_installed:
            cleanup_artifacts(paths, backups, stages)


def parse_journal(data: bytes) -> Dict[str, object]:
    try:
        value = json.loads(data.decode("utf-8"), object_pairs_hook=reject_duplicate_keys)
        exact_keys(value, {"version", "candidate_code", "token", "state", "entries"})
        if type(value["version"]) is not int or value["version"] != 2 or value["state"] not in ("prepared", "committed", "rolled_back"):
            raise ApplyError()
        candidate_code = value["candidate_code"]
        if not isinstance(candidate_code, str) or CODE_RE.fullmatch(candidate_code) is None:
            raise ApplyError()
        token = value["token"]
        entries = value["entries"]
        if not isinstance(token, str) or re.fullmatch(r"[0-9a-f]{24}", token) is None or not isinstance(entries, list) or not 1 <= len(entries) <= 3:
            raise ApplyError()
        seen = set()
        for entry in entries:
            exact_keys(entry, {"path", "existed", "backup", "stage", "before", "after", "mode"})
            rel_text = entry["path"]
            if type(entry["existed"]) is not bool or not isinstance(rel_text, str) or rel_text in seen:
                raise ApplyError()
            root = PurePosixPath(rel_text).parts[0] if PurePosixPath(rel_text).parts else ""
            if root not in ALLOWED_ROOTS:
                raise ApplyError()
            safe_relative(rel_text, root)
            validate_hash(entry["after"])
            stage = entry["stage"]
            if not isinstance(stage, str) or not stage.startswith(".core-review-stage-" + token + "-") or "/" in stage:
                raise ApplyError()
            if entry["existed"]:
                validate_hash(entry["before"])
                if type(entry["mode"]) is not int or not 0 <= entry["mode"] <= 0o7777:
                    raise ApplyError()
                if not isinstance(entry["backup"], str) or not entry["backup"].startswith(".core-review-backup-" + token + "-") or "/" in entry["backup"]:
                    raise ApplyError()
            elif entry["before"] is not None or entry["backup"] is not None or entry["mode"] is not None:
                raise ApplyError()
            seen.add(rel_text)
        return value
    except ApplyError:
        raise
    except (ValueError, UnicodeError, TypeError, ValidationError, KeyError, AttributeError):
        raise ApplyError()


def read_journal(root: Path) -> Optional[Dict[str, object]]:
    root_fd = open_root(root)
    try:
        try:
            info = os.stat(JOURNAL, dir_fd=root_fd, follow_symlinks=False)
        except FileNotFoundError:
            return None
        if not stat.S_ISREG(info.st_mode):
            raise ApplyError()
        try:
            data = read_at(root_fd, JOURNAL, max_size=MAX_TEXT_FIELD, text=True)
        except ValidationError:
            raise ApplyError()
    finally:
        os.close(root_fd)
    return parse_journal(data)


def journal_transaction_sha256(journal: Dict[str, object]) -> str:
    entries = journal.get("entries")
    if not isinstance(entries, list):
        raise ApplyError()
    hashes: Dict[str, Dict[str, Optional[str]]] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise ApplyError()
        path = entry.get("path")
        before = entry.get("before")
        after = entry.get("after")
        if not isinstance(path, str) or (before is not None and not isinstance(before, str)) or not isinstance(after, str):
            raise ApplyError()
        hashes[path] = {"before": before, "after": after}
    payload = {"candidate_code": journal["candidate_code"], "hashes": hashes}
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    ).hexdigest()


def recovery_status(root: Path) -> Tuple[str, Optional[str]]:
    journal = read_journal(root)
    if journal is None:
        return "no_transaction", None
    return str(journal["state"]), str(journal["candidate_code"])


def journal_refs(root: Path, journal: Dict[str, object]) -> Tuple[Dict[str, PathRef], Dict[str, Optional[str]]]:
    refs: Dict[str, PathRef] = {}
    current: Dict[str, Optional[str]] = {}
    for entry in journal["entries"]:
        rel_text = entry["path"]
        rel = PurePosixPath(rel_text)
        try:
            try:
                ref = PathRef(root, rel, True)
            except ValidationError:
                ref = PathRef(root, rel, False)
            refs[rel_text] = ref
            current[rel_text] = name_hash(ref.parent_fd, ref.name)
        except ValidationError:
            raise ApplyError()
    return refs, current


def artifact_maps(journal: Dict[str, object]) -> Tuple[Dict[str, Optional[str]], Dict[str, str]]:
    entries = journal["entries"]
    return ({entry["path"]: entry["backup"] for entry in entries},
            {entry["path"]: entry["stage"] for entry in entries})


def recover_incomplete(root: Path) -> Optional[Tuple[str, str]]:
    journal = read_journal(root)
    if journal is None:
        return None
    state = str(journal["state"])
    candidate = str(journal["candidate_code"])
    entries = journal["entries"]
    refs, current = journal_refs(root, journal)
    try:
        if state == "committed":
            for entry in entries:
                if current[entry["path"]] != entry["after"]:
                    raise ApplyError()
            return state, candidate

        if state == "prepared":
            # Validate every leaf and hidden artifact before the first mutation.
            for entry in entries:
                rel = entry["path"]
                if entry["existed"]:
                    if current[rel] not in (entry["before"], entry["after"]):
                        raise ApplyError()
                    expected_stage = entry["after"] if current[rel] == entry["before"] else entry["before"]
                    if name_hash(refs[rel].parent_fd, entry["stage"]) != expected_stage:
                        raise ApplyError()
                    if name_hash(refs[rel].parent_fd, entry["backup"]) != entry["before"]:
                        raise ApplyError()
                else:
                    if current[rel] not in (None, entry["after"]):
                        raise ApplyError()
                    expected_stage = entry["after"] if current[rel] is None else None
                    if name_hash(refs[rel].parent_fd, entry["stage"]) != expected_stage:
                        raise ApplyError()
            for entry in reversed(entries):
                rel = entry["path"]
                ref = refs[rel]
                if entry["existed"] and current[rel] == entry["after"]:
                    atomic_swap_at(ref.parent_fd, entry["stage"], ref.name)
                elif not entry["existed"] and current[rel] == entry["after"]:
                    atomic_exclusive_at(ref.parent_fd, ref.name, entry["stage"])
                fsync_fd(ref.parent_fd)
            for entry in entries:
                expected = entry["before"] if entry["existed"] else None
                if name_hash(refs[entry["path"]].parent_fd, refs[entry["path"]].name) != expected:
                    raise ApplyError()
            journal = dict(journal)
            journal["state"] = "rolled_back"
            if not rewrite_journal(root, json.dumps(journal, separators=(",", ":"), sort_keys=True).encode("utf-8")):
                raise CleanupRetryError()
        elif state != "rolled_back":
            raise ApplyError()

        for entry in entries:
            expected = entry["before"] if entry["existed"] else None
            if current.get(entry["path"]) is not None and state == "rolled_back":
                current[entry["path"]] = name_hash(refs[entry["path"]].parent_fd, refs[entry["path"]].name)
            if name_hash(refs[entry["path"]].parent_fd, refs[entry["path"]].name) != expected:
                raise ApplyError()
        backups, stages = artifact_maps(journal)
        if not cleanup_artifacts(refs, backups, stages):
            raise CleanupRetryError()
        try:
            remove_journal(root)
        except Exception:
            raise CleanupRetryError()
        return "prepared", candidate
    except CleanupRetryError:
        raise
    except Exception:
        raise ApplyError()


def acknowledge_candidate(root: Path, candidate_code: str) -> Tuple[str, str]:
    journal = read_journal(root)
    if journal is None or journal["state"] != "committed" or journal["candidate_code"] != candidate_code:
        raise ApplyError()
    refs, current = journal_refs(root, journal)
    for entry in journal["entries"]:
        if current[entry["path"]] != entry["after"]:
            raise ApplyError()
    backups, stages = artifact_maps(journal)
    if not cleanup_artifacts(refs, backups, stages):
        raise CleanupRetryError()
    try:
        remove_journal(root)
    except Exception:
        raise CleanupRetryError()
    return "committed", candidate_code


def parse_args(argv: List[str]) -> Tuple[Path, bool, bool, bool, Optional[str]]:
    dry_run = False
    recover_only = False
    status_only = False
    ack_candidate = None
    args = list(argv)
    if "--dry-run" in args:
        args.remove("--dry-run")
        dry_run = True
    if "--recover-only" in args:
        args.remove("--recover-only")
        recover_only = True
    if "--recovery-status" in args:
        args.remove("--recovery-status")
        status_only = True
    if "--ack-candidate" in args:
        index = args.index("--ack-candidate")
        if index + 1 >= len(args):
            raise ValidationError()
        ack_candidate = args[index + 1]
        del args[index:index + 2]
        if not isinstance(ack_candidate, str) or CODE_RE.fullmatch(ack_candidate) is None:
            raise ValidationError()
    if sum((dry_run, recover_only, status_only, ack_candidate is not None)) > 1:
        raise ValidationError()
    if len(args) != 2 or args[0] != "--vault-root":
        raise ValidationError()
    root_text = args[1]
    if not root_text or "\x00" in root_text:
        raise ValidationError()
    return Path(root_text), dry_run, recover_only, status_only, ack_candidate


def silence_broken_stdout(stream: TextIO) -> None:
    try:
        if stream is sys.stdout or stream.fileno() == 1:
            fd = os.open(os.devnull, os.O_WRONLY)
            try:
                os.dup2(fd, 1)
            finally:
                os.close(fd)
    except Exception:
        pass


def safe_write(stream: TextIO, message: str) -> bool:
    try:
        stream.write(message)
        stream.flush()
        return True
    except BrokenPipeError:
        silence_broken_stdout(stream)
        return False
    except Exception:
        return False


def run(argv: List[str], stdin: TextIO = sys.stdin, stdout: TextIO = sys.stdout, stderr: TextIO = sys.stderr) -> int:
    mutated = False
    recovery_candidate: Optional[str] = None
    recovery_state: Optional[str] = None
    try:
        root, dry_run, recover_only, status_only, ack_candidate = parse_args(argv)
        if status_only:
            journal = read_journal(root)
            if journal is None:
                recovery_state, recovery_candidate = "no_transaction", None
                transaction_sha256 = None
            else:
                recovery_state = str(journal["state"])
                recovery_candidate = str(journal["candidate_code"])
                transaction_sha256 = journal_transaction_sha256(journal)
            payload = {
                "state": recovery_state,
                "candidate_code": recovery_candidate,
                "transaction_sha256": transaction_sha256,
            }
            return 0 if safe_write(stdout, json.dumps(payload, separators=(",", ":"), sort_keys=True) + "\n") else 70
        if ack_candidate is not None:
            recovery_state, recovery_candidate = recovery_status(root)
            acknowledge_candidate(root, ack_candidate)
            mutated = True
            payload = {"status": "acknowledged", "state": "committed", "candidate_code": ack_candidate}
            if not safe_write(stdout, json.dumps(payload, separators=(",", ":"), sort_keys=True) + "\n"):
                safe_write(stderr, "ack result reporting failed candidate_code=%s state=committed\n" % ack_candidate)
                return 5
            return 0
        if recover_only:
            recovery_state, recovery_candidate = recovery_status(root)
            recovered = recover_incomplete(root)
            if recovered is None:
                payload = {"status": "no_transaction", "state": "no_transaction", "candidate_code": None}
            elif recovered[0] == "committed":
                payload = {"status": "reconciliation_required", "state": "committed", "candidate_code": recovered[1]}
            else:
                mutated = True
                payload = {"status": "recovered", "state": "prepared", "candidate_code": recovered[1]}
            if not safe_write(stdout, json.dumps(payload, separators=(",", ":"), sort_keys=True) + "\n"):
                if mutated:
                    safe_write(stderr, "recovery result reporting failed candidate_code=%s state=%s\n" % (recovery_candidate, recovery_state))
                    return 5
                return 70
            return 0
        if journal_exists(root):
            safe_write(stderr, "recovery required\n")
            return 4
        env = parse_envelope(stdin)
        paths, originals, desired = prepare(root, env)
        if dry_run:
            if not safe_write(stdout, result_json("planned", originals, desired) + "\n"):
                return 70
            return 0
        code = apply_changes(str(env["candidate_code"]), paths, originals, desired)
        if code in (0, 5):
            mutated = True
        if code == 0:
            if not safe_write(stdout, result_json("applied", originals, desired, str(env["candidate_code"])) + "\n"):
                safe_write(stderr, "applied; result reporting failed candidate_code=%s state=committed\n" % env["candidate_code"])
                return 5
        elif code == 3:
            safe_write(stderr, "apply failed; rollback verified\n")
        elif code == 5:
            safe_write(stderr, "applied; cleanup attention required candidate_code=%s state=committed\n" % env["candidate_code"])
        else:
            safe_write(stderr, "apply failed; rollback incomplete\n")
        return code
    except ValidationError:
        safe_write(stderr, "validation failed\n")
        return 2
    except CleanupRetryError:
        safe_write(stderr, "cleanup retry required candidate_code=%s state=%s\n" % (recovery_candidate, recovery_state))
        return 6
    except ApplyError:
        if recovery_candidate is not None and recovery_state is not None:
            safe_write(stderr, "recovery failed candidate_code=%s state=%s\n" % (recovery_candidate, recovery_state))
        else:
            safe_write(stderr, "recovery failed\n")
        return 4
    except Exception:
        if mutated:
            safe_write(stderr, "mutation completed; result reporting failed\n")
            return 5
        safe_write(stderr, "unexpected failure\n")
        return 70


if __name__ == "__main__":
    raise SystemExit(run(sys.argv[1:]))
