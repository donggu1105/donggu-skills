#!/usr/bin/env python3
"""Apply the package-owned FDE Community separation manifest atomically.

This helper is intentionally separate from the CORE helper.  It accepts one
versioned operation and never accepts caller-supplied file bodies, arbitrary
write paths, moves, or deletes.
"""
from __future__ import annotations

import errno
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import secrets
import stat
import sys
from contextlib import contextmanager
from typing import Any, Dict, List, Optional, TextIO, Tuple


# Reuse the audited descriptor-relative primitives without widening the CORE
# helper's candidate surface.
_CORE_PATH = Path(__file__).with_name("apply-action.py")
_CORE_SPEC = importlib.util.spec_from_file_location("donggu_core_apply_helper", _CORE_PATH)
if _CORE_SPEC is None or _CORE_SPEC.loader is None:  # pragma: no cover - packaging failure
    raise RuntimeError("CORE helper primitives are unavailable")
_core = importlib.util.module_from_spec(_CORE_SPEC)
_CORE_SPEC.loader.exec_module(_core)

_MANIFEST_PATH = Path(__file__).with_name("fde_community_manifest.py")
_MANIFEST_SPEC = importlib.util.spec_from_file_location("donggu_fde_community_manifest", _MANIFEST_PATH)
if _MANIFEST_SPEC is None or _MANIFEST_SPEC.loader is None:  # pragma: no cover - packaging failure
    raise RuntimeError("FDE Community manifest is unavailable")
_manifest_module = importlib.util.module_from_spec(_MANIFEST_SPEC)
_MANIFEST_SPEC.loader.exec_module(_manifest_module)

ValidationError = _core.ValidationError
ApplyError = _core.ApplyError
CleanupRetryError = _core.CleanupRetryError

MAX_STDIN = 1 * 1024 * 1024
MAX_FILE = 8 * 1024 * 1024
MAX_JOURNAL = 256 * 1024
JOURNAL = ".fde-community-review-journal.json"
TARGET_ROOT = "FDE Community"
CANDIDATE_TYPE = "fde_community_separation"
OPERATION = "create_fde_community_structure"
MANIFEST_ID = _manifest_module.MANIFEST_ID
MANIFEST_VERSION = _manifest_module.MANIFEST_VERSION
MANIFEST_SHA256 = _manifest_module.MANIFEST_SHA256
MANIFEST = dict(_manifest_module.MANIFEST)
MANIFEST_PATHS = tuple(sorted(MANIFEST))
SOURCE_PATH = str(_manifest_module.SOURCE_PATH)
NEW_PATHS = tuple(sorted(str(value) for value in _manifest_module.NEW_PATHS))
LEGACY_PATHS = tuple(sorted(str(value) for value in _manifest_module.LEGACY_PATHS))

if hashlib.sha256(json.dumps(MANIFEST, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")).hexdigest() != MANIFEST_SHA256:  # pragma: no cover - package integrity failure
    raise RuntimeError("FDE Community manifest digest mismatch")

ENVELOPE_KEYS = {
    "schema_version", "candidate_code", "candidate_type", "source_note_path",
    "source_sha256", "claim", "target_note_paths", "action",
}
ACTION_KEYS = {
    "op", "schema_version", "template_version", "manifest_id",
    "manifest_sha256", "before_hashes",
}
JOURNAL_KEYS = {
    "version", "kind", "candidate_code", "token", "state", "entries",
    "legacy_entries", "tree",
}
ENTRY_KEYS = {"path", "before", "after"}
LEGACY_ENTRY_KEYS = {
    "path", "existed", "before", "after", "backup", "stage", "mode",
    "backup_identity", "before_identity", "stage_identity",
}
TREE_KEYS = {"stage", "target", "installed", "identity"}


def _reject_duplicate_keys(pairs: List[Tuple[str, object]]) -> Dict[str, object]:
    result: Dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValidationError()
        result[key] = value
    return result


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def transaction_sha256(candidate_code: str, entries: List[Dict[str, Any]]) -> str:
    hashes = {
        entry["path"]: {"before": entry["before"], "after": entry["after"]}
        for entry in entries
    }
    return hashlib.sha256(_canonical({"candidate_code": candidate_code, "hashes": hashes})).hexdigest()


def _bounded(value: object, *, allow_empty: bool = False) -> str:
    return _core.bounded_string(value, allow_empty=allow_empty)


def _validate_hash(value: object) -> str:
    return _core.validate_hash(value)


def _safe_rel(value: object) -> Tuple[str, PurePosixPath]:
    text = _bounded(value)
    root = PurePosixPath(text).parts[0] if PurePosixPath(text).parts else ""
    if root not in {"Personal Branding", TARGET_ROOT}:
        raise ValidationError()
    return _core.safe_relative(text, root)


def _open_dir_at(parent_fd: int, name: str) -> int:
    try:
        fd = os.open(name, os.O_RDONLY | _core.DIRECTORY | _core.NOFOLLOW, dir_fd=parent_fd)
        if not stat.S_ISDIR(os.fstat(fd).st_mode):
            os.close(fd)
            raise ValidationError()
        return fd
    except (OSError, ValidationError):
        raise ValidationError()


def _read_from_dir(parent_fd: int, parts: Tuple[str, ...]) -> Optional[bytes]:
    """Read a relative file under an already-open directory, safely."""
    if not parts:
        raise ValidationError()
    fd = os.dup(parent_fd)
    file_fd = -1
    try:
        for component in parts[:-1]:
            try:
                next_fd = os.open(component, os.O_RDONLY | _core.DIRECTORY | _core.NOFOLLOW, dir_fd=fd)
            except FileNotFoundError:
                return None
            except OSError:
                raise ValidationError()
            os.close(fd)
            fd = next_fd
            if not stat.S_ISDIR(os.fstat(fd).st_mode):
                raise ValidationError()
        try:
            file_fd = os.open(parts[-1], os.O_RDONLY | _core.NOFOLLOW | _core.NONBLOCK, dir_fd=fd)
        except FileNotFoundError:
            return None
        except OSError:
            raise ValidationError()
        info = os.fstat(file_fd)
        if not stat.S_ISREG(info.st_mode):
            raise ValidationError()
        # read_at performs the stable inode/size check.
        data = _core.read_at(fd, parts[-1], max_size=MAX_FILE, text=False)
        return data
    finally:
        if file_fd >= 0:
            os.close(file_fd)
        os.close(fd)


def _read_rel(root: Path, rel: str) -> Optional[bytes]:
    _text, path = _safe_rel(rel)
    root_fd = _core.open_root(root)
    try:
        return _read_from_dir(root_fd, tuple(path.parts))
    finally:
        os.close(root_fd)


def _child_kind(parent_fd: int, name: str) -> Optional[str]:
    try:
        info = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    except FileNotFoundError:
        return None
    except OSError:
        raise ValidationError()
    if stat.S_ISLNK(info.st_mode):
        raise ValidationError()
    if stat.S_ISDIR(info.st_mode):
        return "dir"
    if stat.S_ISREG(info.st_mode):
        return "file"
    raise ValidationError()


def _target_dir_absent(root: Path) -> None:
    root_fd = _core.open_root(root)
    try:
        if _child_kind(root_fd, TARGET_ROOT) is not None:
            raise ValidationError()
    finally:
        os.close(root_fd)


def parse_envelope(stdin: TextIO) -> Dict[str, Any]:
    raw = stdin.read(MAX_STDIN + 1)
    try:
        if len(raw.encode("utf-8")) > MAX_STDIN:
            raise ValidationError()
        value = json.loads(raw, object_pairs_hook=_reject_duplicate_keys)
    except (ValueError, TypeError, UnicodeError):
        raise ValidationError()
    if not isinstance(value, dict) or set(value) != ENVELOPE_KEYS:
        raise ValidationError()
    if type(value["schema_version"]) is not int or value["schema_version"] != 1:
        raise ValidationError()
    if _bounded(value["candidate_type"]) != CANDIDATE_TYPE:
        raise ValidationError()
    candidate_code = _bounded(value["candidate_code"])
    if _core.CODE_RE.fullmatch(candidate_code) is None:
        raise ValidationError()
    _bounded(value["claim"], allow_empty=True)
    if value["source_note_path"] != SOURCE_PATH:
        raise ValidationError()
    _validate_hash(value["source_sha256"])
    targets = value["target_note_paths"]
    if targets != list(MANIFEST_PATHS) or targets != sorted(set(targets)):
        raise ValidationError()
    action = value["action"]
    if not isinstance(action, dict) or set(action) != ACTION_KEYS:
        raise ValidationError()
    if action["op"] != OPERATION:
        raise ValidationError()
    if type(action["schema_version"]) is not int or action["schema_version"] != 1:
        raise ValidationError()
    if type(action["template_version"]) is not int or action["template_version"] != MANIFEST_VERSION:
        raise ValidationError()
    if action["manifest_id"] != MANIFEST_ID:
        raise ValidationError()
    if action["manifest_sha256"] != MANIFEST_SHA256:
        raise ValidationError()
    before_hashes = action["before_hashes"]
    if not isinstance(before_hashes, dict) or set(before_hashes) != set(MANIFEST_PATHS):
        raise ValidationError()
    for rel in MANIFEST_PATHS:
        expected = before_hashes[rel]
        if rel in LEGACY_PATHS:
            _validate_hash(expected)
        else:
            if expected is not None:
                raise ValidationError()
    return value


def prepare(root: Path, env: Dict[str, Any]) -> Dict[str, Any]:
    source = _read_rel(root, SOURCE_PATH)
    if source is None or digest(source) != env["source_sha256"]:
        raise ValidationError()
    _target_dir_absent(root)
    before_hashes = env["action"]["before_hashes"]
    originals: Dict[str, Optional[bytes]] = {}
    desired: Dict[str, bytes] = {}
    legacy_refs: Dict[str, Any] = {}
    legacy_modes: Dict[str, int] = {}
    legacy_identities: Dict[str, List[int]] = {}
    try:
        for rel in MANIFEST_PATHS:
            current = _read_rel(root, rel)
            expected = before_hashes[rel]
            if expected is None:
                if current is not None:
                    raise ValidationError()
            else:
                if current is None or digest(current) != expected:
                    raise ValidationError()
                _text, path = _safe_rel(rel)
                legacy_refs[rel] = _core.PathRef(root, path, True)
                info = os.stat(
                    legacy_refs[rel].name,
                    dir_fd=legacy_refs[rel].parent_fd,
                    follow_symlinks=False,
                )
                if not stat.S_ISREG(info.st_mode):
                    raise ValidationError()
                legacy_modes[rel] = stat.S_IMODE(info.st_mode)
                legacy_identities[rel] = [int(info.st_dev), int(info.st_ino)]
            originals[rel] = current
            desired[rel] = str(MANIFEST[rel]).encode("utf-8")
            if len(desired[rel]) > MAX_FILE:
                raise ValidationError()
        if set(legacy_refs) != set(LEGACY_PATHS):
            raise ValidationError()
        return {
            "root": root,
            "originals": originals,
            "desired": desired,
            "legacy_refs": legacy_refs,
            "legacy_modes": legacy_modes,
            "legacy_identities": legacy_identities,
            "legacy_originals": {rel: originals[rel] for rel in LEGACY_PATHS},
            "legacy_desired": {rel: desired[rel] for rel in LEGACY_PATHS},
            "new_files": {rel: desired[rel] for rel in NEW_PATHS},
        }
    except Exception:
        _close_legacy_refs(legacy_refs)
        raise


def result_json(
    status: str,
    originals: Dict[str, Optional[bytes]],
    desired: Dict[str, bytes],
    candidate_code: Optional[str] = None,
    tree_identity: Optional[List[int]] = None,
) -> str:
    paths = sorted(desired)
    hashes: Dict[str, Dict[str, Optional[str]]] = {}
    for rel in paths:
        before = originals[rel]
        hashes[rel] = {
            "before": digest(before) if before is not None else None,
            "after": digest(desired[rel]),
        }
    payload: Dict[str, Any] = {"status": status, "paths": paths, "hashes": hashes}
    if candidate_code is not None:
        payload.update({"candidate_code": candidate_code, "state": "committed"})
    if tree_identity is not None:
        payload["tree_identity"] = tree_identity
    return json.dumps(payload, separators=(",", ":"), sort_keys=True)


def _mkdir_unique(parent_fd: int, prefix: str) -> str:
    for _ in range(100):
        name = prefix + secrets.token_hex(12)
        try:
            os.mkdir(name, 0o700, dir_fd=parent_fd)
            _core.fsync_fd(parent_fd)
            return name
        except FileExistsError:
            continue
        except OSError:
            raise ApplyError()
    raise ApplyError()


def _ensure_stage_dirs(stage_fd: int, components: Tuple[str, ...]) -> int:
    fd = os.dup(stage_fd)
    try:
        for component in components:
            try:
                next_fd = os.open(component, os.O_RDONLY | _core.DIRECTORY | _core.NOFOLLOW, dir_fd=fd)
            except FileNotFoundError:
                try:
                    os.mkdir(component, 0o700, dir_fd=fd)
                    _core.fsync_fd(fd)
                    next_fd = os.open(component, os.O_RDONLY | _core.DIRECTORY | _core.NOFOLLOW, dir_fd=fd)
                except OSError:
                    raise ApplyError()
            except OSError:
                raise ApplyError()
            os.close(fd)
            fd = next_fd
        return fd
    except Exception:
        os.close(fd)
        raise


def _stage_tree(root: Path, files: Dict[str, bytes], token: str) -> str:
    if _core.RENAMEATX_NP is None:
        raise ApplyError()
    root_fd = _core.open_root(root)
    stage_name = None
    try:
        stage_name = _mkdir_unique(root_fd, ".fde-community-tree-" + token + "-")
        stage_fd = _open_dir_at(root_fd, stage_name)
        try:
            for rel in sorted(files):
                path = PurePosixPath(rel)
                if path.parts[0] != TARGET_ROOT:
                    raise ValidationError()
                parent_fd = _ensure_stage_dirs(stage_fd, tuple(path.parts[1:-1]))
                try:
                    temp_name = _core.write_temp(parent_fd, ".fde-community-file-", files[rel], 0o644)
                    _core.atomic_exclusive_at(parent_fd, temp_name, path.parts[-1])
                    _core.fsync_fd(parent_fd)
                finally:
                    os.close(parent_fd)
            _core.fsync_fd(stage_fd)
        finally:
            os.close(stage_fd)
        return stage_name
    except Exception:
        if stage_name is not None:
            try:
                _remove_tree_at(root_fd, stage_name)
            except Exception:
                pass
        raise
    finally:
        os.close(root_fd)


def _restore_named_capture(parent_fd: int, capture: str, source: str) -> bool:
    try:
        try:
            os.stat(source, dir_fd=parent_fd, follow_symlinks=False)
            return False
        except FileNotFoundError:
            pass
        _core.atomic_exclusive_at(parent_fd, capture, source)
        _core.fsync_fd(parent_fd)
        return True
    except Exception:
        return False


def _remove_captured_file(parent_fd: int, source: str, expected_identity: List[int]) -> None:
    capture = _move_exclusive_for_cleanup(parent_fd, source, ".fde-community-tree-cleanup-")
    try:
        if _identity_at_file(parent_fd, capture) != expected_identity:
            if not _restore_named_capture(parent_fd, capture, source):
                raise ApplyError()
            raise ApplyError()
        final_capture = _move_exclusive_for_cleanup(parent_fd, capture, ".fde-community-tree-delete-")
        if _identity_at_file(parent_fd, final_capture) != expected_identity:
            if not _restore_named_capture(parent_fd, final_capture, capture):
                raise ApplyError()
            if not _restore_named_capture(parent_fd, capture, source):
                raise ApplyError()
            raise ApplyError()
        _remove_owned_file_at(parent_fd, final_capture, expected_identity)
    except Exception:
        raise


def _identity_at_file(parent_fd: int, name: str) -> List[int]:
    try:
        info = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    except OSError:
        raise ApplyError()
    if not stat.S_ISREG(info.st_mode):
        raise ApplyError()
    return [int(info.st_dev), int(info.st_ino)]


def _remove_owned_file_at(parent_fd: int, name: str, expected_identity: List[int]) -> None:
    """Remove a regular file only after an identity-bound atomic swap.

    ``unlink(name)`` cannot bind the final delete to an inode.  Swapping the
    candidate with a fresh private sentinel first makes a replacement at the
    candidate name observable before any delete is attempted.  The shared
    writer fence protects the private sentinel for cooperating writers; an
    uncooperative replacement is retained and causes a retryable failure.
    """
    sentinel: Optional[str] = None
    sentinel_identity: Optional[List[int]] = None
    try:
        sentinel = _core.write_temp(parent_fd, ".fde-community-delete-sentinel-", b"", 0o600)
        sentinel_identity = _identity_at_file(parent_fd, sentinel)
        assert sentinel is not None and sentinel_identity is not None
        if _identity_at_file(parent_fd, name) != expected_identity:
            raise ApplyError()
        _core.atomic_swap_at(parent_fd, name, sentinel)
        _core.fsync_fd(parent_fd)
        captured_identity = _identity_at_file(parent_fd, sentinel)
        if captured_identity != expected_identity:
            # The candidate was replaced.  Restore the foreign object to the
            # public capture name only while the other side is still our
            # sentinel; never unlink an object whose identity is unknown.
            if _identity_at_file(parent_fd, name) == sentinel_identity:
                _core.atomic_swap_at(parent_fd, name, sentinel)
                _core.fsync_fd(parent_fd)
                if _identity_at_file(parent_fd, sentinel) == sentinel_identity:
                    os.unlink(sentinel, dir_fd=parent_fd)
                    sentinel = None
            raise ApplyError()
        os.unlink(sentinel, dir_fd=parent_fd)
        sentinel = None
        if _identity_at_file(parent_fd, name) != sentinel_identity:
            raise ApplyError()
        os.unlink(name, dir_fd=parent_fd)
        _core.fsync_fd(parent_fd)
    finally:
        if sentinel is not None and sentinel_identity is not None:
            try:
                if _identity_at_file(parent_fd, sentinel) == sentinel_identity:
                    os.unlink(sentinel, dir_fd=parent_fd)
                    _core.fsync_fd(parent_fd)
            except Exception:
                # Preserve an uncertain sentinel for reconciliation.
                pass


def _remove_owned_tree_object_at(parent_fd: int, name: str, expected_identity: List[int]) -> None:
    """Remove a directory only after an identity-bound atomic swap."""
    sentinel: Optional[str] = None
    sentinel_identity: Optional[List[int]] = None
    try:
        sentinel = _mkdir_unique(parent_fd, ".fde-community-delete-sentinel-")
        sentinel_identity = _identity_at(parent_fd, sentinel)
        assert sentinel is not None and sentinel_identity is not None
        if _identity_at(parent_fd, name) != expected_identity:
            raise ApplyError()
        _core.atomic_swap_at(parent_fd, name, sentinel)
        _core.fsync_fd(parent_fd)
        captured_identity = _identity_at(parent_fd, sentinel)
        if captured_identity != expected_identity:
            if _identity_at(parent_fd, name) == sentinel_identity:
                _core.atomic_swap_at(parent_fd, name, sentinel)
                _core.fsync_fd(parent_fd)
                if _identity_at(parent_fd, sentinel) == sentinel_identity:
                    os.rmdir(sentinel, dir_fd=parent_fd)
                    sentinel = None
            raise ApplyError()
        os.rmdir(sentinel, dir_fd=parent_fd)
        sentinel = None
        if _identity_at(parent_fd, name) != sentinel_identity:
            raise ApplyError()
        os.rmdir(name, dir_fd=parent_fd)
        _core.fsync_fd(parent_fd)
    finally:
        if sentinel is not None and sentinel_identity is not None:
            try:
                if _identity_at(parent_fd, sentinel) == sentinel_identity:
                    os.rmdir(sentinel, dir_fd=parent_fd)
                    _core.fsync_fd(parent_fd)
            except Exception:
                pass


def _remove_tree_at(parent_fd: int, name: str, expected_identity: Optional[List[int]] = None) -> None:
    fd = -1
    try:
        fd = os.open(name, os.O_RDONLY | _core.DIRECTORY | _core.NOFOLLOW, dir_fd=parent_fd)
        info = os.fstat(fd)
        if not stat.S_ISDIR(info.st_mode):
            raise ApplyError()
        identity = [int(info.st_dev), int(info.st_ino)]
        if expected_identity is not None and identity != expected_identity:
            raise ApplyError()
        for child in os.listdir(fd):
            try:
                child_info = os.stat(child, dir_fd=fd, follow_symlinks=False)
            except OSError:
                raise ApplyError()
            child_identity = [int(child_info.st_dev), int(child_info.st_ino)]
            if stat.S_ISDIR(child_info.st_mode):
                captured = _move_exclusive_for_cleanup(fd, child, ".fde-community-tree-cleanup-")
                if _identity_at(fd, captured) != child_identity:
                    if not _restore_named_capture(fd, captured, child):
                        raise ApplyError()
                    raise ApplyError()
                _remove_tree_at(fd, captured, child_identity)
            elif stat.S_ISREG(child_info.st_mode):
                _remove_captured_file(fd, child, child_identity)
            else:
                raise ApplyError()
        os.close(fd)
        fd = -1
        captured = _move_exclusive_for_cleanup(parent_fd, name, ".fde-community-tree-cleanup-")
        if _identity_at(parent_fd, captured) != identity:
            if not _restore_named_capture(parent_fd, captured, name):
                raise ApplyError()
            raise ApplyError()
        # The directory is now private and was captured by identity. Remove
        # it through an identity-bound swap; a replacement at the public name
        # is retained and causes fail-closed cleanup.
        _remove_owned_tree_object_at(parent_fd, captured, identity)
    except FileNotFoundError:
        if expected_identity is None:
            return
        raise ApplyError()
    except OSError:
        raise ApplyError()
    finally:
        if fd >= 0:
            os.close(fd)


def _read_tree_file(root: Path, tree_name: str, rel: str) -> Optional[bytes]:
    path = PurePosixPath(rel)
    if not path.parts or path.parts[0] != TARGET_ROOT:
        raise ValidationError()
    root_fd = _core.open_root(root)
    tree_fd = -1
    try:
        tree_fd = _open_dir_at(root_fd, tree_name)
        return _read_from_dir(tree_fd, tuple(path.parts[1:]))
    except ValidationError:
        return None
    finally:
        if tree_fd >= 0:
            os.close(tree_fd)
        os.close(root_fd)


def _collect_tree_entries(fd: int, prefix: Tuple[str, ...] = ()) -> Tuple[set[Tuple[str, ...]], set[Tuple[str, ...]]]:
    files: set[Tuple[str, ...]] = set()
    directories: set[Tuple[str, ...]] = set()
    for child in os.listdir(fd):
        kind = _child_kind(fd, child)
        relative = prefix + (child,)
        if kind == "file":
            files.add(relative)
        elif kind == "dir":
            directories.add(relative)
            child_fd = _open_dir_at(fd, child)
            try:
                nested_files, nested_directories = _collect_tree_entries(child_fd, relative)
                files.update(nested_files)
                directories.update(nested_directories)
            finally:
                os.close(child_fd)
        else:  # pragma: no cover - _child_kind rejects this first
            raise ApplyError()
    return files, directories


def _tree_matches(root: Path, tree_name: str, files: Dict[str, bytes]) -> bool:
    root_fd = _core.open_root(root)
    tree_fd = -1
    try:
        tree_fd = _open_dir_at(root_fd, tree_name)
        actual_files, actual_directories = _collect_tree_entries(tree_fd)
        expected_files = {tuple(PurePosixPath(rel).parts[1:]) for rel in files}
        expected_directories: set[Tuple[str, ...]] = set()
        for relative in expected_files:
            for index in range(1, len(relative)):
                expected_directories.add(relative[:index])
        if actual_files != expected_files or actual_directories != expected_directories:
            return False
        for relative, expected in files.items():
            actual = _read_from_dir(tree_fd, tuple(PurePosixPath(relative).parts[1:]))
            if actual != expected:
                return False
        return True
    finally:
        if tree_fd >= 0:
            os.close(tree_fd)
        os.close(root_fd)


def _legacy_stage_and_backup(plan: Dict[str, Any], token: str) -> Tuple[Dict[str, str], Dict[str, str]]:
    stages: Dict[str, str] = {}
    backups: Dict[str, str] = {}
    plan["stage_identities"] = {}
    plan["backup_identities"] = {}
    try:
        for rel in sorted(LEGACY_PATHS):
            ref = plan["legacy_refs"][rel]
            stages[rel] = _core.write_temp(
                ref.parent_fd,
                ".fde-community-stage-" + token + "-",
                plan["legacy_desired"][rel],
                plan["legacy_modes"][rel],
            )
            backups[rel] = _core.write_temp(ref.parent_fd, ".fde-community-backup-" + token + "-", plan["legacy_originals"][rel], 0o600)
            plan["stage_identities"][rel] = _artifact_identity(ref, stages[rel])
            plan["backup_identities"][rel] = _artifact_identity(ref, backups[rel])
            if plan["stage_identities"][rel] is None or plan["backup_identities"][rel] is None:
                raise ApplyError()
            _core.fsync_fd(ref.parent_fd)
        return stages, backups
    except Exception:
        for rel in LEGACY_PATHS:
            ref = plan["legacy_refs"].get(rel)
            if ref is None:
                continue
            artifacts = (
                (
                    stages.get(rel),
                    plan["stage_identities"].get(rel),
                    {digest(plan["legacy_desired"][rel])},
                ),
                (
                    backups.get(rel),
                    plan["backup_identities"].get(rel),
                    {digest(plan["legacy_originals"][rel])},
                ),
            )
            for name, identity, allowed_hashes in artifacts:
                if name is None or identity is None:
                    continue
                try:
                    _cleanup_one_artifact(ref, name, [identity], allowed_hashes)
                except Exception:
                    pass
        raise


def _artifact_hash(ref: Any, name: str) -> Optional[str]:
    try:
        info = os.stat(name, dir_fd=ref.parent_fd, follow_symlinks=False)
    except FileNotFoundError:
        return None
    except OSError:
        raise ApplyError()
    if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_FILE:
        raise ApplyError()
    return digest(_core.read_at(ref.parent_fd, name, max_size=MAX_FILE, text=False))


def _artifact_mode(ref: Any, name: str) -> Optional[int]:
    try:
        info = os.stat(name, dir_fd=ref.parent_fd, follow_symlinks=False)
    except FileNotFoundError:
        return None
    except OSError:
        raise ApplyError()
    if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_FILE:
        raise ApplyError()
    return stat.S_IMODE(info.st_mode)


def _artifact_identity(ref: Any, name: str) -> Optional[List[int]]:
    try:
        info = os.stat(name, dir_fd=ref.parent_fd, follow_symlinks=False)
    except FileNotFoundError:
        return None
    except OSError:
        raise ApplyError()
    if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_FILE:
        raise ApplyError()
    return [int(info.st_dev), int(info.st_ino)]


def _validate_legacy_artifacts(journal: Dict[str, Any], plan: Dict[str, Any], *, required: bool) -> None:
    for entry in journal["legacy_entries"]:
        ref = plan["legacy_refs"][entry["path"]]
        backup_hash = _artifact_hash(ref, entry["backup"])
        stage_hash = _artifact_hash(ref, entry["stage"])
        backup_identity = _artifact_identity(ref, entry["backup"])
        stage_identity = _artifact_identity(ref, entry["stage"])
        if required and (
            backup_hash is None
            or stage_hash is None
            or backup_identity is None
            or stage_identity is None
        ):
            raise ApplyError()
        if backup_hash is not None and backup_hash != entry["before"]:
            raise ApplyError()
        if stage_hash is not None and stage_hash not in {entry["before"], entry["after"]}:
            raise ApplyError()
        if backup_identity is not None and backup_identity != entry["backup_identity"]:
            raise ApplyError()
        if stage_identity is not None and stage_identity not in [entry["stage_identity"], entry["before_identity"]]:
            raise ApplyError()
        if stage_hash is not None and _artifact_mode(ref, entry["stage"]) != entry["mode"]:
            raise ApplyError()


def _legacy_modes_match(refs: Dict[str, Any], entries: List[Dict[str, Any]]) -> bool:
    for entry in entries:
        ref = refs[entry["path"]]
        try:
            info = os.stat(ref.name, dir_fd=ref.parent_fd, follow_symlinks=False)
        except OSError:
            return False
        if not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) != entry["mode"]:
            return False
    return True


def _validate_visible_legacy(
    root: Path,
    refs: Dict[str, Any],
    entries: List[Dict[str, Any]],
) -> None:
    for entry in entries:
        ref = refs[entry["path"]]
        current = _read_rel(root, entry["path"])
        current_hash = digest(current) if current is not None else None
        current_identity = _artifact_identity(ref, ref.name)
        if current_hash not in {entry["before"], entry["after"]}:
            raise ApplyError()
        if current_identity is None:
            raise ApplyError()
        if entry["before"] != entry["after"]:
            if current_hash == entry["before"] and current_identity != entry["before_identity"]:
                raise ApplyError()
            if current_hash == entry["after"] and current_identity != entry["stage_identity"]:
                raise ApplyError()
        elif current_identity not in [entry["before_identity"], entry["stage_identity"]]:
            raise ApplyError()


def _plan_legacy_modes_match(plan: Dict[str, Any]) -> bool:
    for rel, mode in plan["legacy_modes"].items():
        ref = plan["legacy_refs"][rel]
        try:
            info = os.stat(ref.name, dir_fd=ref.parent_fd, follow_symlinks=False)
        except OSError:
            return False
        if not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) != mode:
            return False
    return True


def _move_exclusive_for_cleanup(parent_fd: int, source: str, prefix: str) -> str:
    for _ in range(100):
        destination = prefix + secrets.token_hex(8)
        try:
            _core.atomic_exclusive_at(parent_fd, source, destination)
            _core.fsync_fd(parent_fd)
            return destination
        except OSError as exc:
            if exc.errno == errno.EEXIST:
                continue
            raise
    raise ApplyError()


def _restore_moved_artifact(ref: Any, capture: str, source: str) -> bool:
    try:
        if _artifact_identity(ref, source) is not None:
            return False
        _core.atomic_exclusive_at(ref.parent_fd, capture, source)
        _core.fsync_fd(ref.parent_fd)
        return True
    except Exception:
        return False


def _cleanup_one_artifact(ref: Any, name: str, expected_identities: List[List[int]], allowed_hashes: set[str]) -> bool:
    try:
        current_identity = _artifact_identity(ref, name)
    except Exception:
        return False
    if current_identity is None:
        return True
    if current_identity not in expected_identities:
        return False
    capture: Optional[str] = None
    try:
        capture = _move_exclusive_for_cleanup(ref.parent_fd, name, ".fde-community-cleanup-file-")
        if _artifact_identity(ref, capture) not in expected_identities:
            _restore_moved_artifact(ref, capture, name)
            return False
        if _artifact_hash(ref, capture) not in allowed_hashes:
            _restore_moved_artifact(ref, capture, name)
            return False
        tombstone = _move_exclusive_for_cleanup(ref.parent_fd, capture, ".fde-community-delete-file-")
        if _artifact_identity(ref, tombstone) not in expected_identities or _artifact_hash(ref, tombstone) not in allowed_hashes:
            _restore_moved_artifact(ref, tombstone, capture)
            return False
        # Capture once more immediately before deletion. The externally
        # visible tombstone name is never deleted after a check; if it was
        # replaced between validation and this boundary, the foreign inode is
        # restored and cleanup remains retryable.
        final_capture = _move_exclusive_for_cleanup(ref.parent_fd, tombstone, ".fde-community-final-delete-")
        final_identity = _artifact_identity(ref, final_capture)
        if final_identity not in expected_identities:
            _restore_moved_artifact(ref, final_capture, tombstone)
            return False
        _remove_owned_file_at(ref.parent_fd, final_capture, final_identity)
        return True
    except Exception:
        return False


def _tree_owned_subset(root: Path, tree_name: str, files: Dict[str, bytes]) -> bool:
    if _tree_state(root, tree_name) != "dir":
        return _tree_state(root, tree_name) is None
    root_fd = _core.open_root(root)
    tree_fd = -1
    try:
        tree_fd = _open_dir_at(root_fd, tree_name)
        actual_files, actual_directories = _collect_tree_entries(tree_fd)
        expected_files = {tuple(PurePosixPath(rel).parts[1:]) for rel in files}
        expected_directories: set[Tuple[str, ...]] = set()
        for relative in expected_files:
            for index in range(1, len(relative)):
                expected_directories.add(relative[:index])
        if not actual_files.issubset(expected_files) or not actual_directories.issubset(expected_directories):
            return False
        for relative in actual_files:
            rel = TARGET_ROOT + "/" + "/".join(relative)
            if _read_from_dir(tree_fd, relative) != files[rel]:
                return False
        return True
    finally:
        if tree_fd >= 0:
            os.close(tree_fd)
        os.close(root_fd)


def _journal_legacy_refs(root: Path, journal: Dict[str, Any]) -> Dict[str, Any]:
    refs: Dict[str, Any] = {}
    try:
        for entry in journal["legacy_entries"]:
            _text, path = _safe_rel(entry["path"])
            refs[entry["path"]] = _core.PathRef(root, path, True)
        return refs
    except Exception:
        _close_legacy_refs(refs)
        raise


def _close_legacy_refs(refs: Dict[str, Any]) -> None:
    closed: set[int] = set()
    for ref in refs.values():
        for attribute in ("parent_fd", "root_fd"):
            descriptor = getattr(ref, attribute, -1)
            if isinstance(descriptor, int) and descriptor >= 0 and descriptor not in closed:
                try:
                    os.close(descriptor)
                except OSError:
                    pass
                closed.add(descriptor)
            try:
                setattr(ref, attribute, -1)
            except Exception:
                pass


def _cleanup_journal_artifacts(root: Path, journal: Dict[str, Any]) -> bool:
    refs = _journal_legacy_refs(root, journal)
    try:
        ok = True
        for entry in journal["legacy_entries"]:
            ref = refs[entry["path"]]
            for name, identities, allowed in (
                (entry["stage"], [entry["stage_identity"], entry["before_identity"]], {entry["before"], entry["after"]}),
                (entry["backup"], [entry["backup_identity"]], {entry["before"]}),
            ):
                if not _cleanup_one_artifact(ref, name, identities, allowed):
                    ok = False
        return ok
    finally:
        _close_legacy_refs(refs)


def _cleanup_rolled_back(root: Path, journal: Dict[str, Any]) -> bool:
    tree_files = {rel: str(MANIFEST[rel]).encode("utf-8") for rel in NEW_PATHS}
    tree_name = journal["tree"]["stage"]
    target_state = _tree_state(root, TARGET_ROOT)
    if target_state == "dir" and _tree_identity(root, TARGET_ROOT) == journal["tree"]["identity"]:
        return False
    refs = _journal_legacy_refs(root, journal)
    try:
        _validate_legacy_artifacts(journal, {"legacy_refs": refs}, required=True)
        _validate_visible_legacy(root, refs, journal["legacy_entries"])
    except Exception:
        return False
    finally:
        _close_legacy_refs(refs)
    ok = _cleanup_journal_artifacts(root, journal)
    if _tree_state(root, tree_name) is not None:
        if (
            _tree_identity(root, tree_name) != journal["tree"]["identity"]
            or not _tree_owned_subset(root, tree_name, tree_files)
        ):
            ok = False
        elif not _cleanup_owned_tree(root, tree_name, journal["tree"]["identity"], tree_files):
            ok = False
    if not ok:
        return False
    refs = _journal_legacy_refs(root, journal)
    try:
        # This is the last visible-state fence. The journal must remain
        # recoverable if a concurrent writer replaces a legacy leaf after the
        # earlier validation but before journal removal.
        _validate_visible_legacy(root, refs, journal["legacy_entries"])
        if not _legacy_modes_match(refs, journal["legacy_entries"]):
            return False
        _validate_visible_legacy(root, refs, journal["legacy_entries"])
    except Exception:
        return False
    finally:
        _close_legacy_refs(refs)
    try:
        _remove_journal(root)
    except Exception:
        return False
    return True


def _legacy_unchanged(plan: Dict[str, Any]) -> bool:
    for rel in LEGACY_PATHS:
        current = _read_rel(plan["root"], rel)
        if current != plan["legacy_originals"][rel]:
            return False
    return True


def _cas_install_with_identities(
    ref: Any,
    original: bytes,
    desired: bytes,
    stage: str,
    *,
    expected_target_identity: List[int],
    expected_stage_identity: List[int],
    result_target_identity: List[int],
    result_stage_identity: List[int],
) -> bool:
    try:
        if _artifact_identity(ref, ref.name) != expected_target_identity:
            return False
        if _artifact_identity(ref, stage) != expected_stage_identity:
            return False
        if not _core.cas_install(ref, original, desired, stage):
            return False
        return (
            _artifact_identity(ref, ref.name) == result_target_identity
            and _artifact_identity(ref, stage) == result_stage_identity
        )
    except Exception:
        return False


def _swap_legacy(plan: Dict[str, Any], stages: Dict[str, str]) -> bool:
    for rel in sorted(LEGACY_PATHS):
        ref = plan["legacy_refs"][rel]
        if not ref.revalidate_parent():
            return False
        current = _read_rel(plan["root"], rel)
        if current != plan["legacy_originals"][rel]:
            return False
        try:
            staged = _core.read_at(ref.parent_fd, stages[rel], text=False)
            if digest(staged) != digest(plan["legacy_desired"][rel]):
                return False
            if not _cas_install_with_identities(
                ref,
                plan["legacy_originals"][rel],
                plan["legacy_desired"][rel],
                stages[rel],
                expected_target_identity=plan["legacy_identities"][rel],
                expected_stage_identity=plan["stage_identities"][rel],
                result_target_identity=plan["stage_identities"][rel],
                result_stage_identity=plan["legacy_identities"][rel],
            ):
                return False
            _core.fsync_fd(ref.parent_fd)
        except (OSError, ApplyError):
            return False
        if (
            _read_rel(plan["root"], rel) != plan["legacy_desired"][rel]
            or not _plan_legacy_modes_match(plan)
        ):
            return False
    return True


def _restore_legacy(plan: Dict[str, Any], stages: Dict[str, str]) -> bool:
    ok = True
    for rel in reversed(sorted(LEGACY_PATHS)):
        ref = plan["legacy_refs"][rel]
        try:
            current = _read_rel(plan["root"], rel)
            if current == plan["legacy_originals"][rel]:
                continue
            if current != plan["legacy_desired"][rel]:
                ok = False
                continue
            if not _cas_install_with_identities(
                ref,
                plan["legacy_desired"][rel],
                plan["legacy_originals"][rel],
                stages[rel],
                expected_target_identity=plan["stage_identities"][rel],
                expected_stage_identity=plan["legacy_identities"][rel],
                result_target_identity=plan["legacy_identities"][rel],
                result_stage_identity=plan["stage_identities"][rel],
            ):
                ok = False
                continue
            _core.fsync_fd(ref.parent_fd)
        except Exception:
            ok = False
    return ok and _legacy_unchanged(plan) and _plan_legacy_modes_match(plan)


def _cleanup_legacy(plan: Dict[str, Any], stages: Dict[str, str], backups: Dict[str, str]) -> bool:
    ok = True
    for rel in LEGACY_PATHS:
        ref = plan["legacy_refs"][rel]
        before_hash = digest(plan["legacy_originals"][rel])
        after_hash = digest(plan["legacy_desired"][rel])
        for name in (stages.get(rel), backups.get(rel)):
            if not name:
                continue
            allowed = {before_hash} if name == backups.get(rel) else {before_hash, after_hash}
            identities = plan["backup_identities"] if name == backups.get(rel) else plan["stage_identities"]
            expected_identity = identities.get(rel)
            if expected_identity is None:
                ok = False
                continue
            allowed_identities = [expected_identity]
            if not _cleanup_one_artifact(ref, name, allowed_identities, allowed):
                ok = False
    return ok


def _journal_payload(
    candidate_code: str,
    token: str,
    state: str,
    plan: Dict[str, Any],
    stages: Dict[str, str],
    backups: Dict[str, str],
    tree_stage: str,
    tree_installed: bool,
) -> Dict[str, Any]:
    entries = [
        {
            "path": rel,
            "before": digest(plan["originals"][rel]) if plan["originals"][rel] is not None else None,
            "after": digest(plan["desired"][rel]),
        }
        for rel in MANIFEST_PATHS
    ]
    legacy_entries = []
    for rel in sorted(LEGACY_PATHS):
        ref = plan["legacy_refs"][rel]
        mode = plan["legacy_modes"][rel]
        backup_identity = plan["backup_identities"][rel]
        stage_identity = plan["stage_identities"][rel]
        current_backup_identity = _artifact_identity(ref, backups[rel])
        current_stage_identity = _artifact_identity(ref, stages[rel])
        if (
            backup_identity is None
            or stage_identity is None
            or current_backup_identity != backup_identity
            or current_stage_identity not in [stage_identity, plan["legacy_identities"][rel]]
        ):
            raise ApplyError()
        before_hash = digest(plan["legacy_originals"][rel])
        after_hash = digest(plan["legacy_desired"][rel])
        stage_hash = _artifact_hash(ref, stages[rel])
        if stage_hash not in {before_hash, after_hash}:
            raise ApplyError()
        if before_hash != after_hash:
            if stage_hash == after_hash and current_stage_identity != stage_identity:
                raise ApplyError()
            if stage_hash == before_hash and current_stage_identity != plan["legacy_identities"][rel]:
                raise ApplyError()
        current_hash = digest(_read_rel(plan["root"], rel) or b"")
        current_identity = _artifact_identity(ref, ref.name)
        if before_hash != after_hash:
            if current_hash == before_hash and current_identity != plan["legacy_identities"][rel]:
                raise ApplyError()
            if current_hash == after_hash and current_identity != stage_identity:
                raise ApplyError()
        elif current_identity not in [stage_identity, plan["legacy_identities"][rel]]:
            raise ApplyError()
        legacy_entries.append({
            "path": rel,
            "existed": True,
            "before": digest(plan["legacy_originals"][rel]),
            "after": digest(plan["legacy_desired"][rel]),
            "backup": backups[rel],
            "stage": stages[rel],
            "mode": mode,
            "backup_identity": backup_identity,
            "before_identity": plan["legacy_identities"][rel],
            "stage_identity": stage_identity,
        })
    current_tree_name = TARGET_ROOT if tree_installed else tree_stage
    tree_identity = _tree_identity(plan["root"], current_tree_name)
    return {
        "version": 1,
        "kind": "fde_community",
        "candidate_code": candidate_code,
        "token": token,
        "state": state,
        "entries": entries,
        "legacy_entries": legacy_entries,
        "tree": {
            "stage": tree_stage,
            "target": TARGET_ROOT,
            "installed": tree_installed,
            "identity": tree_identity,
        },
    }


def _write_journal(root: Path, payload: Dict[str, Any], *, install: bool) -> None:
    data = _canonical(payload)
    if len(data) > MAX_JOURNAL:
        raise ApplyError()
    root_fd = _core.open_root(root)
    temp: Optional[str] = None
    temp_identity: Optional[List[int]] = None
    temp_hash: Optional[str] = None
    temp_ref = None
    old_ref = None
    old_identity: Optional[List[int]] = None
    old_hash: Optional[str] = None
    try:
        if not install:
            old_ref = _core.PathRef(root, PurePosixPath(JOURNAL), True)
            old_identity = _artifact_identity(old_ref, JOURNAL)
            old_hash = _artifact_hash(old_ref, JOURNAL)
            if old_identity is None or old_hash is None:
                raise ApplyError()
        temp_name = _core.write_temp(root_fd, ".fde-community-journal-", data, 0o600)
        temp = temp_name
        temp_ref = _core.PathRef(root, PurePosixPath(temp_name), True)
        temp_identity = _artifact_identity(temp_ref, temp_name)
        temp_hash = _artifact_hash(temp_ref, temp_name)
        if temp_identity is None or temp_hash is None:
            raise ApplyError()
        assert old_identity is not None or install
        assert old_hash is not None or install
        if install:
            _core.atomic_exclusive_at(root_fd, temp_name, JOURNAL)
            temp = None
        else:
            assert old_identity is not None and old_hash is not None
            _core.atomic_swap_at(root_fd, temp_name, JOURNAL)
            if not _cleanup_one_artifact(temp_ref, temp_name, [old_identity], {old_hash}):
                temp = None
                raise CleanupRetryError()
            temp = None
        _core.fsync_fd(root_fd)
    finally:
        if temp is not None and temp_ref is not None and temp_identity is not None and temp_hash is not None:
            _cleanup_one_artifact(temp_ref, temp, [temp_identity], {temp_hash})
        if temp_ref is not None:
            _close_legacy_refs({"temp": temp_ref})
        if old_ref is not None:
            _close_legacy_refs({"old": old_ref})
        os.close(root_fd)


def _remove_journal(root: Path) -> None:
    root_fd = _core.open_root(root)
    ref = None
    try:
        try:
            os.stat(JOURNAL, dir_fd=root_fd, follow_symlinks=False)
        except FileNotFoundError:
            return
        ref = _core.PathRef(root, PurePosixPath(JOURNAL), True)
        expected_identity = _artifact_identity(ref, JOURNAL)
        expected_hash = _artifact_hash(ref, JOURNAL)
        if expected_identity is None or expected_hash is None:
            raise CleanupRetryError()
        assert expected_identity is not None and expected_hash is not None
        if not _cleanup_one_artifact(ref, JOURNAL, [expected_identity], {expected_hash}):
            raise CleanupRetryError()
        _core.fsync_fd(ref.parent_fd)
    except OSError:
        raise CleanupRetryError()
    finally:
        if ref is not None:
            _close_legacy_refs({"journal": ref})
        os.close(root_fd)


def _parse_journal(data: bytes) -> Dict[str, Any]:
    try:
        value = json.loads(data.decode("utf-8"), object_pairs_hook=_reject_duplicate_keys)
        if not isinstance(value, dict) or set(value) != JOURNAL_KEYS:
            raise ApplyError()
        if value["version"] != 1 or value["kind"] != "fde_community":
            raise ApplyError()
        candidate = value["candidate_code"]
        token = value["token"]
        if not isinstance(candidate, str) or _core.CODE_RE.fullmatch(candidate) is None:
            raise ApplyError()
        if not isinstance(token, str) or len(token) != 24 or any(ch not in "0123456789abcdef" for ch in token):
            raise ApplyError()
        if value["state"] not in {"prepared", "committed", "rolled_back"}:
            raise ApplyError()
        entries = value["entries"]
        if not isinstance(entries, list) or len(entries) != len(MANIFEST_PATHS):
            raise ApplyError()
        seen = set()
        for entry in entries:
            if not isinstance(entry, dict) or set(entry) != ENTRY_KEYS:
                raise ApplyError()
            rel = entry["path"]
            if rel in seen or rel not in MANIFEST_PATHS:
                raise ApplyError()
            _safe_rel(rel)
            if entry["before"] is not None:
                _validate_hash(entry["before"])
            _validate_hash(entry["after"])
            if entry["after"] != digest(str(MANIFEST[rel]).encode("utf-8")):
                raise ApplyError()
            seen.add(rel)
        if seen != set(MANIFEST_PATHS):
            raise ApplyError()
        legacy = value["legacy_entries"]
        if not isinstance(legacy, list) or len(legacy) != len(LEGACY_PATHS):
            raise ApplyError()
        seen = set()
        artifact_names: set[str] = set()
        for entry in legacy:
            if not isinstance(entry, dict) or set(entry) != LEGACY_ENTRY_KEYS:
                raise ApplyError()
            rel = entry["path"]
            if rel in seen or rel not in LEGACY_PATHS or entry["existed"] is not True:
                raise ApplyError()
            _safe_rel(rel)
            _validate_hash(entry["before"])
            _validate_hash(entry["after"])
            if entry["after"] != digest(str(MANIFEST[rel]).encode("utf-8")):
                raise ApplyError()
            for key, prefix in (("backup", ".fde-community-backup-" + token + "-"), ("stage", ".fde-community-stage-" + token + "-")):
                name = entry[key]
                if (
                    not isinstance(name, str)
                    or not name.startswith(prefix)
                    or "/" in name
                    or name in artifact_names
                ):
                    raise ApplyError()
                artifact_names.add(name)
            if isinstance(entry["mode"], bool) or not isinstance(entry["mode"], int) or not 0 <= entry["mode"] <= 0o7777:
                raise ApplyError()
            for identity_key in ("backup_identity", "before_identity", "stage_identity"):
                identity = entry[identity_key]
                if (
                    not isinstance(identity, list)
                    or len(identity) != 2
                    or any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in identity)
                ):
                    raise ApplyError()
            seen.add(rel)
        if seen != set(LEGACY_PATHS):
            raise ApplyError()
        tree = value["tree"]
        if not isinstance(tree, dict) or set(tree) != TREE_KEYS:
            raise ApplyError()
        if tree["target"] != TARGET_ROOT or not isinstance(tree["installed"], bool):
            raise ApplyError()
        identity = tree["identity"]
        if (
            not isinstance(identity, list)
            or len(identity) != 2
            or any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in identity)
        ):
            raise ApplyError()
        stage = tree["stage"]
        if not isinstance(stage, str) or not stage.startswith(".fde-community-tree-" + token + "-") or "/" in stage:
            raise ApplyError()
        return value
    except ApplyError:
        raise
    except (ValueError, TypeError, UnicodeError, KeyError):
        raise ApplyError()


def _read_journal(root: Path) -> Optional[Dict[str, Any]]:
    _reject_orphan_journal_temps(root)
    root_fd = _core.open_root(root)
    try:
        try:
            info = os.stat(JOURNAL, dir_fd=root_fd, follow_symlinks=False)
        except FileNotFoundError:
            return None
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_JOURNAL:
            raise ApplyError()
        data = _core.read_at(root_fd, JOURNAL, max_size=MAX_JOURNAL, text=False)
    finally:
        os.close(root_fd)
    return _parse_journal(data)


def _reject_orphan_journal_temps(root: Path) -> None:
    """Never treat an uncommitted journal temp as no transaction.

    A process can die after the temp is durably created but before the rename
    or the Python ``finally`` block runs.  There is no safe way to bind that
    orphan to a transaction after the journal payload has been lost, so keep
    it and fail closed instead of unlinking it or reporting a clean vault.
    """
    root_fd = _core.open_root(root)
    try:
        try:
            names = os.listdir(root_fd)
        except OSError:
            raise ApplyError()
        for name in names:
            if not name.startswith(".fde-community-journal-"):
                continue
            try:
                info = os.stat(name, dir_fd=root_fd, follow_symlinks=False)
            except OSError:
                raise ApplyError()
            if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_JOURNAL:
                raise ApplyError()
            raise ApplyError()
    finally:
        os.close(root_fd)


@contextmanager
def _writer_fence(root: Path):
    """Serialize native FDE writers on the physical Vault root inode."""
    root_fd = _core.open_root(root)
    try:
        try:
            fcntl.flock(root_fd, fcntl.LOCK_EX)
        except OSError:
            raise ApplyError()
        yield
    finally:
        try:
            fcntl.flock(root_fd, fcntl.LOCK_UN)
        except OSError:
            pass
        os.close(root_fd)


def _journal_status(root: Path) -> Dict[str, Any]:
    journal = _read_journal(root)
    if journal is None:
        return {
            "state": "no_transaction",
            "candidate_code": None,
            "transaction_sha256": None,
            "tree_identity": None,
            "current_tree_identity": None,
        }
    current_tree_identity: Optional[List[int]] = None
    if _tree_state(root, TARGET_ROOT) == "dir":
        current_tree_identity = _tree_identity(root, TARGET_ROOT)
    return {
        "state": journal["state"],
        "candidate_code": journal["candidate_code"],
        "transaction_sha256": transaction_sha256(journal["candidate_code"], journal["entries"]),
        "tree_identity": journal["tree"]["identity"],
        "current_tree_identity": current_tree_identity,
    }


def _tree_state(root: Path, name: str) -> Optional[str]:
    root_fd = _core.open_root(root)
    try:
        return _child_kind(root_fd, name)
    finally:
        os.close(root_fd)


def _tree_identity(root: Path, name: str) -> List[int]:
    root_fd = _core.open_root(root)
    tree_fd = -1
    try:
        tree_fd = _open_dir_at(root_fd, name)
        info = os.fstat(tree_fd)
        return [int(info.st_dev), int(info.st_ino)]
    finally:
        if tree_fd >= 0:
            os.close(tree_fd)
        os.close(root_fd)


def _identity_at(parent_fd: int, name: str) -> List[int]:
    try:
        info = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    except OSError:
        raise ApplyError()
    if not stat.S_ISDIR(info.st_mode):
        raise ApplyError()
    return [int(info.st_dev), int(info.st_ino)]


def _capture_tree_for_cleanup(parent_fd: int, source: str) -> Tuple[str, List[int]]:
    """Move a tree into a private slot while leaving an empty placeholder."""
    slot = _mkdir_unique(parent_fd, ".fde-community-cleanup-")
    placeholder_identity = _identity_at(parent_fd, slot)
    try:
        _core.atomic_swap_at(parent_fd, source, slot)
        _core.fsync_fd(parent_fd)
        return slot, placeholder_identity
    except Exception:
        try:
            _remove_tree_at(parent_fd, slot, placeholder_identity)
        except Exception:
            pass
        raise


def _restore_captured_tree(parent_fd: int, source: str, slot: str, placeholder_identity: List[int]) -> bool:
    """Restore a captured tree only while the source name is still our placeholder."""
    try:
        if _identity_at(parent_fd, source) != placeholder_identity:
            return False
        _core.atomic_swap_at(parent_fd, slot, source)
        _core.fsync_fd(parent_fd)
        _remove_tree_at(parent_fd, slot, placeholder_identity)
        return True
    except Exception:
        return False


def _cleanup_owned_tree(root: Path, name: str, expected_identity: List[int], files: Dict[str, bytes]) -> bool:
    root_fd = _core.open_root(root)
    slot: Optional[str] = None
    placeholder_identity: Optional[List[int]] = None
    try:
        slot, placeholder_identity = _capture_tree_for_cleanup(root_fd, name)
        if _identity_at(root_fd, slot) != expected_identity or not _tree_owned_subset(root, slot, files):
            _restore_captured_tree(root_fd, name, slot, placeholder_identity)
            return False
        _remove_tree_at(root_fd, slot, expected_identity)
        if _identity_at(root_fd, name) != placeholder_identity:
            return False
        try:
            _remove_tree_at(root_fd, name, placeholder_identity)
        except Exception:
            return False
        return True
    except Exception:
        return False
    finally:
        os.close(root_fd)


def _verify_entries(root: Path, entries: List[Dict[str, Any]], expected: str) -> bool:
    for entry in entries:
        current = _read_rel(root, entry["path"])
        actual = digest(current) if current is not None else None
        wanted = entry[expected]
        if actual != wanted:
            return False
    return True


def _recover_prepared_with_refs(
    root: Path,
    journal: Dict[str, Any],
    refs: Dict[str, Any],
) -> Tuple[str, str]:
    tree_stage = journal["tree"]["stage"]
    target_state = _tree_state(root, TARGET_ROOT)
    stage_state = _tree_state(root, tree_stage)
    tree_files = {rel: str(MANIFEST[rel]).encode("utf-8") for rel in NEW_PATHS}
    if target_state == "dir":
        if (
            stage_state is not None
            or not _tree_matches(root, TARGET_ROOT, tree_files)
            or _tree_identity(root, TARGET_ROOT) != journal["tree"]["identity"]
        ):
            raise ApplyError()
        target_installed = True
    elif target_state is None:
        if (
            stage_state != "dir"
            or not _tree_matches(root, tree_stage, tree_files)
            or _tree_identity(root, tree_stage) != journal["tree"]["identity"]
        ):
            raise ApplyError()
        target_installed = False
    else:
        raise ApplyError()

    plan = {"legacy_refs": refs}
    _validate_legacy_artifacts(journal, plan, required=True)
    _validate_visible_legacy(root, refs, journal["legacy_entries"])
    for entry in journal["legacy_entries"]:
        current = _read_rel(root, entry["path"])
        current_hash = digest(current) if current is not None else None
        if current_hash not in {entry["before"], entry["after"]}:
            raise ApplyError()
        stage_hash = _artifact_hash(refs[entry["path"]], entry["stage"])
        if stage_hash not in {entry["before"], entry["after"]}:
            raise ApplyError()
        if current_hash == entry["before"] and stage_hash != entry["after"]:
            raise ApplyError()
        if current_hash == entry["after"] and stage_hash != entry["before"]:
            raise ApplyError()

    if not _legacy_modes_match(refs, journal["legacy_entries"]):
        raise ApplyError()

    # Restore every visible legacy leaf only after the complete transaction and
    # all required artifacts have passed validation.
    for entry in reversed(journal["legacy_entries"]):
        ref = refs[entry["path"]]
        if digest(_read_rel(root, entry["path"]) or b"") == entry["after"]:
            before = _core.read_at(ref.parent_fd, entry["stage"], max_size=MAX_FILE, text=False)
            if digest(before) != entry["before"]:
                raise ApplyError()
            desired = str(MANIFEST[entry["path"]]).encode("utf-8")
            if not _cas_install_with_identities(
                ref,
                desired,
                before,
                entry["stage"],
                expected_target_identity=entry["stage_identity"],
                expected_stage_identity=entry["before_identity"],
                result_target_identity=entry["before_identity"],
                result_stage_identity=entry["stage_identity"],
            ):
                raise ApplyError()
            _core.fsync_fd(ref.parent_fd)
            if digest(_read_rel(root, entry["path"]) or b"") != entry["before"]:
                raise ApplyError()

    if target_installed:
        root_fd = _core.open_root(root)
        try:
            # Capture the owned tree back into the transaction stage; never
            # recursively delete a live destination during recovery.
            _core.atomic_exclusive_at(root_fd, TARGET_ROOT, tree_stage)
            _core.fsync_fd(root_fd)
            if _tree_identity(root, tree_stage) != journal["tree"]["identity"]:
                raise ApplyError()
        finally:
            os.close(root_fd)
    if not _verify_entries(root, journal["entries"], "before"):
        raise ApplyError()
    if not _legacy_modes_match(refs, journal["legacy_entries"]):
        raise ApplyError()

    rolled_back = dict(journal)
    rolled_back["state"] = "rolled_back"
    rolled_back["tree"] = {
        "stage": tree_stage,
        "target": TARGET_ROOT,
        "installed": False,
        "identity": _tree_identity(root, tree_stage),
    }
    _write_journal(root, rolled_back, install=False)
    if not _cleanup_rolled_back(root, rolled_back):
        raise CleanupRetryError()
    return "prepared", journal["candidate_code"]


def _recover_prepared(root: Path, journal: Dict[str, Any]) -> Tuple[str, str]:
    refs = _journal_legacy_refs(root, journal)
    try:
        return _recover_prepared_with_refs(root, journal, refs)
    finally:
        _close_legacy_refs(refs)


def _recover(root: Path) -> Optional[Tuple[str, str]]:
    journal = _read_journal(root)
    if journal is None:
        return None
    if journal["state"] == "committed":
        if not _verify_entries(root, journal["entries"], "after"):
            raise ApplyError()
        refs = _journal_legacy_refs(root, journal)
        try:
            _validate_legacy_artifacts(journal, {"legacy_refs": refs}, required=True)
            _validate_visible_legacy(root, refs, journal["legacy_entries"])
            modes_match = _legacy_modes_match(refs, journal["legacy_entries"])
        finally:
            _close_legacy_refs(refs)
        if not modes_match:
            raise ApplyError()
        tree_files = {rel: str(MANIFEST[rel]).encode("utf-8") for rel in NEW_PATHS}
        if (
            _tree_state(root, TARGET_ROOT) != "dir"
            or not _tree_matches(root, TARGET_ROOT, tree_files)
            or _tree_identity(root, TARGET_ROOT) != journal["tree"]["identity"]
        ):
            raise ApplyError()
        return "committed", journal["candidate_code"]
    if journal["state"] == "prepared":
        return _recover_prepared(root, journal)
    if journal["state"] == "rolled_back":
        if not _cleanup_rolled_back(root, journal):
            raise CleanupRetryError()
        return "prepared", journal["candidate_code"]
    raise ApplyError()


def _ack(root: Path, candidate_code: str, expected_transaction: str, *, retain_journal: bool = False) -> Tuple[str, str]:
    journal = _read_journal(root)
    if journal is None or journal["state"] != "committed" or journal["candidate_code"] != candidate_code:
        raise ApplyError()
    if transaction_sha256(journal["candidate_code"], journal["entries"]) != expected_transaction:
        raise ApplyError()
    if not _verify_entries(root, journal["entries"], "after"):
        raise ApplyError()
    refs = _journal_legacy_refs(root, journal)
    try:
        _validate_legacy_artifacts(journal, {"legacy_refs": refs}, required=True)
        _validate_visible_legacy(root, refs, journal["legacy_entries"])
        modes_match = _legacy_modes_match(refs, journal["legacy_entries"])
    finally:
        _close_legacy_refs(refs)
    if not modes_match:
        raise ApplyError()
    tree_files = {rel: str(MANIFEST[rel]).encode("utf-8") for rel in NEW_PATHS}
    if (
        _tree_state(root, TARGET_ROOT) != "dir"
        or not _tree_matches(root, TARGET_ROOT, tree_files)
        or _tree_identity(root, TARGET_ROOT) != journal["tree"]["identity"]
    ):
        raise ApplyError()
    if not retain_journal:
        if not _cleanup_journal_artifacts(root, journal):
            raise CleanupRetryError()
        _remove_journal(root)
    return "committed", candidate_code


def _apply(plan: Dict[str, Any], candidate_code: str) -> int:
    if _core.RENAMEATX_NP is None:
        _close_legacy_refs(plan.get("legacy_refs", {}))
        return 3
    root = plan["root"]
    token = secrets.token_hex(12)
    stages: Dict[str, str] = {}
    backups: Dict[str, str] = {}
    tree_stage: Optional[str] = None
    tree_stage_identity: Optional[List[int]] = None
    tree_installed = False
    journal_installed = False
    prepared: Optional[Dict[str, Any]] = None
    try:
        tree_stage = _stage_tree(root, plan["new_files"], token)
        tree_stage_identity = _tree_identity(root, tree_stage)
        stages, backups = _legacy_stage_and_backup(plan, token)
        if not _legacy_unchanged(plan):
            raise ApplyError()
        prepared = _journal_payload(candidate_code, token, "prepared", plan, stages, backups, tree_stage, False)
        _write_journal(root, prepared, install=True)
        journal_installed = True
        root_fd = _core.open_root(root)
        try:
            _core.atomic_exclusive_at(root_fd, tree_stage, TARGET_ROOT)
            tree_installed = True
            _core.fsync_fd(root_fd)
        finally:
            os.close(root_fd)
        if not _swap_legacy(plan, stages):
            raise ApplyError()
        installed = _journal_payload(candidate_code, token, "prepared", plan, stages, backups, tree_stage, True)
        _write_journal(root, installed, install=False)
        if (
            not _verify_entries(root, installed["entries"], "after")
            or not _legacy_modes_match(plan["legacy_refs"], installed["legacy_entries"])
        ):
            raise ApplyError()
        committed = dict(installed)
        committed["state"] = "committed"
        _write_journal(root, committed, install=False)
        return 0
    except Exception:
        # A committed journal is durable evidence that the after-state may be
        # externally visible. Never attempt an implicit rollback from here.
        if journal_installed:
            try:
                visible = _read_journal(root)
            except Exception:
                return 4
            if visible is None:
                return 4
            if isinstance(visible, dict) and visible.get("state") == "committed":
                return 4
        restored = True
        try:
            if tree_installed:
                expected_tree_identity = prepared["tree"]["identity"] if prepared is not None else None
                if (
                    not _tree_matches(root, TARGET_ROOT, plan["new_files"])
                    or expected_tree_identity is None
                    or _tree_identity(root, TARGET_ROOT) != expected_tree_identity
                ):
                    restored = False
                else:
                    root_fd = _core.open_root(root)
                    try:
                        _core.atomic_exclusive_at(root_fd, TARGET_ROOT, tree_stage)
                        _core.fsync_fd(root_fd)
                        if tree_stage is None or _tree_identity(root, tree_stage) != expected_tree_identity:
                            restored = False
                    finally:
                        os.close(root_fd)
            if restored and stages:
                restored = _restore_legacy(plan, stages)
            if restored and prepared is not None and not _verify_entries(root, prepared["entries"], "before"):
                restored = False
            if restored and journal_installed and prepared is not None and tree_stage is not None:
                rolled_back = _journal_payload(
                    candidate_code, token, "rolled_back", plan, stages, backups, tree_stage, False,
                )
                _write_journal(root, rolled_back, install=False)
                restored = _cleanup_rolled_back(root, rolled_back)
        except Exception:
            restored = False
        return 3 if restored else 4
    finally:
        # On a successful committed return, artifacts remain until ack. Before
        # journal installation, all artifacts must be gone.
        if not journal_installed:
            cleanup_ok = True
            if tree_stage is not None:
                try:
                    root_fd = _core.open_root(root)
                    try:
                        _remove_tree_at(root_fd, tree_stage, tree_stage_identity)
                    finally:
                        os.close(root_fd)
                except Exception:
                    cleanup_ok = False
            if not _cleanup_legacy(plan, stages, backups):
                cleanup_ok = False
            if not cleanup_ok:
                _close_legacy_refs(plan.get("legacy_refs", {}))
                return 4
        _close_legacy_refs(plan.get("legacy_refs", {}))


def parse_args(argv: List[str]) -> Tuple[Path, bool, bool, bool, Optional[str], Optional[str], bool]:
    args = list(argv)
    dry_run = "--dry-run" in args
    recover_only = "--recover-only" in args
    status_only = "--recovery-status" in args
    retain_journal = "--ack-retain-journal" in args
    ack_candidate: Optional[str] = None
    ack_transaction: Optional[str] = None
    for flag in ("--dry-run", "--recover-only", "--recovery-status", "--ack-retain-journal"):
        while flag in args:
            args.remove(flag)
    if "--ack-candidate" in args:
        index = args.index("--ack-candidate")
        if index + 1 >= len(args):
            raise ValidationError()
        ack_candidate = args[index + 1]
        del args[index:index + 2]
        if _core.CODE_RE.fullmatch(ack_candidate) is None:
            raise ValidationError()
    if "--ack-transaction" in args:
        index = args.index("--ack-transaction")
        if index + 1 >= len(args) or ack_candidate is None:
            raise ValidationError()
        ack_transaction = args[index + 1]
        del args[index:index + 2]
        _validate_hash(ack_transaction)
    if (ack_candidate is None) != (ack_transaction is None) or (retain_journal and ack_candidate is None):
        raise ValidationError()
    if sum((dry_run, recover_only, status_only, ack_candidate is not None)) > 1:
        raise ValidationError()
    if len(args) != 2 or args[0] != "--vault-root" or not args[1] or "\x00" in args[1]:
        raise ValidationError()
    return Path(args[1]), dry_run, recover_only, status_only, ack_candidate, ack_transaction, retain_journal


def _safe_write(stream: TextIO, value: str) -> bool:
    try:
        stream.write(value + "\n")
        stream.flush()
        return True
    except BrokenPipeError:
        return False


def run(argv: List[str], stdin: TextIO = sys.stdin, stdout: TextIO = sys.stdout, stderr: TextIO = sys.stderr) -> int:
    plan: Optional[Dict[str, Any]] = None
    try:
        root, dry_run, recover_only, status_only, ack_candidate, ack_transaction, retain_journal = parse_args(argv)
        if status_only:
            return 0 if _safe_write(stdout, json.dumps(_journal_status(root), separators=(",", ":"), sort_keys=True)) else 70
        if ack_candidate is not None:
            with _writer_fence(root):
                _ack(root, ack_candidate, str(ack_transaction), retain_journal=retain_journal)
            payload = {"status": "acknowledged", "state": "committed", "candidate_code": ack_candidate}
            return 0 if _safe_write(stdout, json.dumps(payload, separators=(",", ":"), sort_keys=True)) else 5
        if recover_only:
            with _writer_fence(root):
                recovered = _recover(root)
            if recovered is None:
                payload = {"status": "no_transaction", "state": "no_transaction", "candidate_code": None}
            elif recovered[0] == "committed":
                payload = {"status": "reconciliation_required", "state": "committed", "candidate_code": recovered[1]}
            else:
                payload = {"status": "recovered", "state": "prepared", "candidate_code": recovered[1]}
            return 0 if _safe_write(stdout, json.dumps(payload, separators=(",", ":"), sort_keys=True)) else 70
        if _read_journal(root) is not None:
            _safe_write(stderr, "recovery required")
            return 4
        env = parse_envelope(stdin)
        plan = prepare(root, env)
        if dry_run:
            return 0 if _safe_write(stdout, result_json("planned", plan["originals"], plan["desired"])) else 70
        with _writer_fence(root):
            code = _apply(plan, str(env["candidate_code"]))
        if code == 0:
            payload = result_json(
                "applied",
                plan["originals"],
                plan["desired"],
                str(env["candidate_code"]),
                _tree_identity(plan["root"], TARGET_ROOT),
            )
            if not _safe_write(stdout, payload):
                return 5
        elif code == 3:
            _safe_write(stderr, "apply failed; rollback verified")
        else:
            _safe_write(stderr, "apply failed; rollback incomplete")
        return code
    except ValidationError:
        _safe_write(stderr, "validation failed")
        return 2
    except CleanupRetryError:
        _safe_write(stderr, "cleanup retry required")
        return 6
    except ApplyError:
        _safe_write(stderr, "recovery failed")
        return 4
    except Exception:
        _safe_write(stderr, "unexpected failure")
        return 70
    finally:
        if plan is not None:
            _close_legacy_refs(plan.get("legacy_refs", {}))


if __name__ == "__main__":
    raise SystemExit(run(sys.argv[1:]))
