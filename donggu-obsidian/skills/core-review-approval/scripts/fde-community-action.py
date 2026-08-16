#!/usr/bin/env python3
"""Apply the package-owned FDE Community separation manifest atomically.

This helper is intentionally separate from the CORE helper.  It accepts one
versioned operation and never accepts caller-supplied file bodies, arbitrary
write paths, moves, or deletes.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import secrets
import stat
import sys
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
LEGACY_ENTRY_KEYS = {"path", "existed", "before", "after", "backup", "stage", "mode"}
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
        "legacy_originals": {rel: originals[rel] for rel in LEGACY_PATHS},
        "legacy_desired": {rel: desired[rel] for rel in LEGACY_PATHS},
        "new_files": {rel: desired[rel] for rel in NEW_PATHS},
    }


def result_json(status: str, originals: Dict[str, Optional[bytes]], desired: Dict[str, bytes], candidate_code: Optional[str] = None) -> str:
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


def _remove_tree_at(parent_fd: int, name: str) -> None:
    fd = -1
    try:
        fd = os.open(name, os.O_RDONLY | _core.DIRECTORY | _core.NOFOLLOW, dir_fd=parent_fd)
        if not stat.S_ISDIR(os.fstat(fd).st_mode):
            raise ApplyError()
        for child in os.listdir(fd):
            kind = _child_kind(fd, child)
            if kind == "dir":
                _remove_tree_at(fd, child)
            elif kind == "file":
                os.unlink(child, dir_fd=fd)
                _core.fsync_fd(fd)
            else:
                raise ApplyError()
        os.close(fd)
        fd = -1
        os.rmdir(name, dir_fd=parent_fd)
        _core.fsync_fd(parent_fd)
    except FileNotFoundError:
        return
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
    try:
        for rel in sorted(LEGACY_PATHS):
            ref = plan["legacy_refs"][rel]
            stages[rel] = _core.write_temp(ref.parent_fd, ".fde-community-stage-" + token + "-", plan["legacy_desired"][rel], 0o644)
            backups[rel] = _core.write_temp(ref.parent_fd, ".fde-community-backup-" + token + "-", plan["legacy_originals"][rel], 0o600)
            _core.fsync_fd(ref.parent_fd)
        return stages, backups
    except Exception:
        for rel, names in ((rel, (stages.get(rel), backups.get(rel))) for rel in LEGACY_PATHS):
            ref = plan["legacy_refs"].get(rel)
            if ref is None:
                continue
            for name in names:
                if name:
                    try:
                        os.unlink(name, dir_fd=ref.parent_fd)
                    except OSError:
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


def _validate_legacy_artifacts(journal: Dict[str, Any], plan: Dict[str, Any], *, required: bool) -> None:
    for entry in journal["legacy_entries"]:
        ref = plan["legacy_refs"][entry["path"]]
        backup_hash = _artifact_hash(ref, entry["backup"])
        stage_hash = _artifact_hash(ref, entry["stage"])
        if required and (backup_hash is None or stage_hash is None):
            raise ApplyError()
        if backup_hash is not None and backup_hash != entry["before"]:
            raise ApplyError()
        if stage_hash is not None and stage_hash not in {entry["before"], entry["after"]}:
            raise ApplyError()


def _artifact_cleanup_safe(ref: Any, name: str, allowed_hashes: set[str]) -> bool:
    try:
        actual = _artifact_hash(ref, name)
    except Exception:
        return False
    return actual is None or actual in allowed_hashes


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
    for entry in journal["legacy_entries"]:
        _text, path = _safe_rel(entry["path"])
        refs[entry["path"]] = _core.PathRef(root, path, True)
    return refs


def _cleanup_journal_artifacts(root: Path, journal: Dict[str, Any]) -> bool:
    refs = _journal_legacy_refs(root, journal)
    ok = True
    for entry in journal["legacy_entries"]:
        ref = refs[entry["path"]]
        for name, allowed in (
            (entry["stage"], {entry["before"], entry["after"]}),
            (entry["backup"], {entry["before"]}),
        ):
            if not _artifact_cleanup_safe(ref, name, allowed):
                ok = False
                continue
            try:
                os.unlink(name, dir_fd=ref.parent_fd)
                _core.fsync_fd(ref.parent_fd)
            except FileNotFoundError:
                pass
            except OSError:
                ok = False
    return ok


def _cleanup_rolled_back(root: Path, journal: Dict[str, Any]) -> bool:
    tree_files = {rel: str(MANIFEST[rel]).encode("utf-8") for rel in NEW_PATHS}
    tree_name = journal["tree"]["stage"]
    target_state = _tree_state(root, TARGET_ROOT)
    if target_state == "dir" and _tree_identity(root, TARGET_ROOT) == journal["tree"]["identity"]:
        return False
    ok = _cleanup_journal_artifacts(root, journal)
    if _tree_state(root, tree_name) is not None:
        if (
            _tree_identity(root, tree_name) != journal["tree"]["identity"]
            or not _tree_owned_subset(root, tree_name, tree_files)
        ):
            ok = False
        else:
            root_fd = _core.open_root(root)
            try:
                _remove_tree_at(root_fd, tree_name)
            except Exception:
                ok = False
            finally:
                os.close(root_fd)
    if not ok:
        return False
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
        except Exception:
            return False
        if digest(staged) != digest(plan["legacy_desired"][rel]):
            return False
        try:
            _core.atomic_swap_at(ref.parent_fd, stages[rel], ref.name)
            _core.fsync_fd(ref.parent_fd)
        except (OSError, ApplyError):
            return False
        if _read_rel(plan["root"], rel) != plan["legacy_desired"][rel]:
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
            if _core.digest(_core.read_at(ref.parent_fd, stages[rel], text=False)) != digest(plan["legacy_originals"][rel]):
                ok = False
                continue
            _core.atomic_swap_at(ref.parent_fd, stages[rel], ref.name)
            _core.fsync_fd(ref.parent_fd)
        except Exception:
            ok = False
    return ok and _legacy_unchanged(plan)


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
            if not _artifact_cleanup_safe(ref, name, allowed):
                ok = False
                continue
            try:
                os.unlink(name, dir_fd=ref.parent_fd)
                _core.fsync_fd(ref.parent_fd)
            except FileNotFoundError:
                pass
            except OSError:
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
        mode = stat.S_IMODE(os.stat(ref.name, dir_fd=ref.parent_fd, follow_symlinks=False).st_mode)
        legacy_entries.append({
            "path": rel,
            "existed": True,
            "before": digest(plan["legacy_originals"][rel]),
            "after": digest(plan["legacy_desired"][rel]),
            "backup": backups[rel],
            "stage": stages[rel],
            "mode": mode,
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
    temp = None
    try:
        temp = _core.write_temp(root_fd, ".fde-community-journal-", data, 0o600)
        if install:
            _core.atomic_exclusive_at(root_fd, temp, JOURNAL)
            temp = None
        else:
            _core.atomic_swap_at(root_fd, temp, JOURNAL)
            # After swap, the old journal resides at the temporary name.
            os.unlink(temp, dir_fd=root_fd)
            temp = None
        _core.fsync_fd(root_fd)
    finally:
        if temp is not None:
            try:
                os.unlink(temp, dir_fd=root_fd)
            except OSError:
                pass
        os.close(root_fd)


def _remove_journal(root: Path) -> None:
    root_fd = _core.open_root(root)
    try:
        try:
            os.unlink(JOURNAL, dir_fd=root_fd)
        except FileNotFoundError:
            return
        _core.fsync_fd(root_fd)
    except OSError:
        raise CleanupRetryError()
    finally:
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
            if not isinstance(entry["mode"], int) or not 0 <= entry["mode"] <= 0o7777:
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


def _journal_status(root: Path) -> Dict[str, Any]:
    journal = _read_journal(root)
    if journal is None:
        return {"state": "no_transaction", "candidate_code": None, "transaction_sha256": None}
    return {
        "state": journal["state"],
        "candidate_code": journal["candidate_code"],
        "transaction_sha256": transaction_sha256(journal["candidate_code"], journal["entries"]),
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


def _verify_entries(root: Path, entries: List[Dict[str, Any]], expected: str) -> bool:
    for entry in entries:
        current = _read_rel(root, entry["path"])
        actual = digest(current) if current is not None else None
        wanted = entry[expected]
        if actual != wanted:
            return False
    return True


def _recover_prepared(root: Path, journal: Dict[str, Any]) -> Tuple[str, str]:
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

    refs = _journal_legacy_refs(root, journal)
    plan = {"legacy_refs": refs}
    _validate_legacy_artifacts(journal, plan, required=True)
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

    # Restore every visible legacy leaf only after the complete transaction and
    # all required artifacts have passed validation.
    for entry in reversed(journal["legacy_entries"]):
        ref = refs[entry["path"]]
        if digest(_read_rel(root, entry["path"]) or b"") == entry["after"]:
            _core.atomic_swap_at(ref.parent_fd, entry["stage"], ref.name)
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
        finally:
            os.close(root_fd)
    if not _verify_entries(root, journal["entries"], "before"):
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


def _recover(root: Path) -> Optional[Tuple[str, str]]:
    journal = _read_journal(root)
    if journal is None:
        return None
    if journal["state"] == "committed":
        if not _verify_entries(root, journal["entries"], "after"):
            raise ApplyError()
        tree_files = {rel: str(MANIFEST[rel]).encode("utf-8") for rel in NEW_PATHS}
        if _tree_state(root, TARGET_ROOT) != "dir" or not _tree_matches(root, TARGET_ROOT, tree_files):
            raise ApplyError()
        return "committed", journal["candidate_code"]
    if journal["state"] == "prepared":
        return _recover_prepared(root, journal)
    if journal["state"] == "rolled_back":
        if not _cleanup_rolled_back(root, journal):
            raise CleanupRetryError()
        return "prepared", journal["candidate_code"]
    raise ApplyError()


def _ack(root: Path, candidate_code: str, expected_transaction: str) -> Tuple[str, str]:
    journal = _read_journal(root)
    if journal is None or journal["state"] != "committed" or journal["candidate_code"] != candidate_code:
        raise ApplyError()
    if transaction_sha256(journal["candidate_code"], journal["entries"]) != expected_transaction:
        raise ApplyError()
    if not _verify_entries(root, journal["entries"], "after"):
        raise ApplyError()
    tree_files = {rel: str(MANIFEST[rel]).encode("utf-8") for rel in NEW_PATHS}
    if (
        _tree_state(root, TARGET_ROOT) != "dir"
        or not _tree_matches(root, TARGET_ROOT, tree_files)
        or _tree_identity(root, TARGET_ROOT) != journal["tree"]["identity"]
    ):
        raise ApplyError()
    if not _cleanup_journal_artifacts(root, journal):
        raise CleanupRetryError()
    _remove_journal(root)
    return "committed", candidate_code


def _apply(plan: Dict[str, Any], candidate_code: str) -> int:
    if _core.RENAMEATX_NP is None:
        return 3
    root = plan["root"]
    token = secrets.token_hex(12)
    stages: Dict[str, str] = {}
    backups: Dict[str, str] = {}
    tree_stage: Optional[str] = None
    tree_installed = False
    journal_installed = False
    prepared: Optional[Dict[str, Any]] = None
    try:
        tree_stage = _stage_tree(root, plan["new_files"], token)
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
        if not _verify_entries(root, installed["entries"], "after"):
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
                if not _tree_matches(root, TARGET_ROOT, plan["new_files"]):
                    restored = False
                else:
                    root_fd = _core.open_root(root)
                    try:
                        _core.atomic_exclusive_at(root_fd, TARGET_ROOT, tree_stage)
                        _core.fsync_fd(root_fd)
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
            if tree_stage is not None:
                try:
                    root_fd = _core.open_root(root)
                    try:
                        _remove_tree_at(root_fd, tree_stage)
                    finally:
                        os.close(root_fd)
                except Exception:
                    pass
            _cleanup_legacy(plan, stages, backups)


def parse_args(argv: List[str]) -> Tuple[Path, bool, bool, bool, Optional[str], Optional[str]]:
    args = list(argv)
    dry_run = "--dry-run" in args
    recover_only = "--recover-only" in args
    status_only = "--recovery-status" in args
    ack_candidate: Optional[str] = None
    ack_transaction: Optional[str] = None
    for flag in ("--dry-run", "--recover-only", "--recovery-status"):
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
    if (ack_candidate is None) != (ack_transaction is None):
        raise ValidationError()
    if sum((dry_run, recover_only, status_only, ack_candidate is not None)) > 1:
        raise ValidationError()
    if len(args) != 2 or args[0] != "--vault-root" or not args[1] or "\x00" in args[1]:
        raise ValidationError()
    return Path(args[1]), dry_run, recover_only, status_only, ack_candidate, ack_transaction


def _safe_write(stream: TextIO, value: str) -> bool:
    try:
        stream.write(value + "\n")
        stream.flush()
        return True
    except BrokenPipeError:
        return False


def run(argv: List[str], stdin: TextIO = sys.stdin, stdout: TextIO = sys.stdout, stderr: TextIO = sys.stderr) -> int:
    try:
        root, dry_run, recover_only, status_only, ack_candidate, ack_transaction = parse_args(argv)
        if status_only:
            return 0 if _safe_write(stdout, json.dumps(_journal_status(root), separators=(",", ":"), sort_keys=True)) else 70
        if ack_candidate is not None:
            _ack(root, ack_candidate, str(ack_transaction))
            payload = {"status": "acknowledged", "state": "committed", "candidate_code": ack_candidate}
            return 0 if _safe_write(stdout, json.dumps(payload, separators=(",", ":"), sort_keys=True)) else 5
        if recover_only:
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
        code = _apply(plan, str(env["candidate_code"]))
        if code == 0:
            payload = result_json("applied", plan["originals"], plan["desired"], str(env["candidate_code"]))
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


if __name__ == "__main__":
    raise SystemExit(run(sys.argv[1:]))
