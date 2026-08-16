"""Receipt-backed runtime for the fixed FDE Community separation action."""
from __future__ import annotations

from datetime import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import secrets
import stat
from typing import Any, Dict, Optional

from .core_actions import (
    CoreActionRuntime,
    CoreRuntimeError,
    _valid_hash,
    _checked_vault_root,
    _open_root_descriptor,
)


class FDECommunityValidationError(CoreRuntimeError):
    """The fixed FDE Community preimage is unavailable or unsafe."""


_MANIFEST_PATH = Path(__file__).parents[1] / "skills" / "core-review-approval" / "scripts" / "fde_community_manifest.py"
_MANIFEST_SPEC = importlib.util.spec_from_file_location("donggu_fde_community_manifest_runtime", _MANIFEST_PATH)
if _MANIFEST_SPEC is None or _MANIFEST_SPEC.loader is None:  # pragma: no cover
    raise RuntimeError("FDE Community manifest is unavailable")
_MANIFEST_MODULE = importlib.util.module_from_spec(_MANIFEST_SPEC)
_MANIFEST_SPEC.loader.exec_module(_MANIFEST_MODULE)
MANIFEST_ID = _MANIFEST_MODULE.MANIFEST_ID
MANIFEST_VERSION = _MANIFEST_MODULE.MANIFEST_VERSION
MANIFEST_SHA256 = _MANIFEST_MODULE.MANIFEST_SHA256
SOURCE_PATH = str(_MANIFEST_MODULE.SOURCE_PATH)
LEGACY_PATHS = tuple(sorted(str(value) for value in _MANIFEST_MODULE.LEGACY_PATHS))
NEW_PATHS = tuple(sorted(str(value) for value in _MANIFEST_MODULE.NEW_PATHS))
TARGET_PATHS = tuple(sorted((*NEW_PATHS, *LEGACY_PATHS)))
_MAX_FILE = 8 * 1024 * 1024
if hashlib.sha256(
    json.dumps(
        _MANIFEST_MODULE.MANIFEST,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
).hexdigest() != MANIFEST_SHA256:  # pragma: no cover - package integrity failure
    raise RuntimeError("FDE Community manifest digest mismatch")


def _candidate_code() -> str:
    date_part = datetime.now().astimezone().strftime("%Y%m%d")
    return f"CR-{date_part}-{secrets.randbelow(1_000_000):06d}"


def _read_regular_file(root: Path, relative: str) -> bytes:
    path = PurePosixPath(relative)
    if (
        path.is_absolute()
        or len(path.parts) < 2
        or path.parts[0] not in {"Personal Branding", "FDE Community"}
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise FDECommunityValidationError("invalid FDE Community source path")
    root_fd = -1
    parent_fd = -1
    file_fd = -1
    try:
        root_fd = _open_root_descriptor(root)
        parent_fd = os.dup(root_fd)
        for component in path.parts[:-1]:
            next_fd = os.open(
                component,
                os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0),
                dir_fd=parent_fd,
            )
            os.close(parent_fd)
            parent_fd = next_fd
        file_fd = os.open(
            path.parts[-1],
            os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0),
            dir_fd=parent_fd,
        )
        before = os.fstat(file_fd)
        if not stat.S_ISREG(before.st_mode) or before.st_size > _MAX_FILE:
            raise OSError()
        chunks = []
        total = 0
        while True:
            chunk = os.read(file_fd, min(1024 * 1024, _MAX_FILE + 1 - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if total > _MAX_FILE:
                raise OSError()
        after = os.fstat(file_fd)
        if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
            after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns
        ):
            raise OSError()
        return b"".join(chunks)
    except OSError as exc:
        raise FDECommunityValidationError("FDE Community source could not be read safely") from exc
    finally:
        for descriptor in (file_fd, parent_fd, root_fd):
            if descriptor >= 0:
                os.close(descriptor)


def build_fde_community_envelope(vault_root: Path, candidate_code: Optional[str] = None) -> Dict[str, Any]:
    root, _identity = _checked_vault_root(vault_root)
    before_hashes: Dict[str, Optional[str]] = {}
    for relative in LEGACY_PATHS:
        before_hashes[relative] = hashlib.sha256(_read_regular_file(root, relative)).hexdigest()
    for relative in NEW_PATHS:
        before_hashes[relative] = None
    source_sha256 = before_hashes[SOURCE_PATH]
    if source_sha256 is None:  # pragma: no cover - fixed legacy invariant
        raise FDECommunityValidationError("FDE Community source hash is unavailable")
    return {
        "schema_version": 1,
        "candidate_code": candidate_code or _candidate_code(),
        "candidate_type": "fde_community_separation",
        "source_note_path": SOURCE_PATH,
        "source_sha256": source_sha256,
        "claim": "FDE Community 운영 정본을 Vault 최상위 영역으로 분리",
        "target_note_paths": list(TARGET_PATHS),
        "action": {
            "op": "create_fde_community_structure",
            "schema_version": 1,
            "template_version": MANIFEST_VERSION,
            "manifest_id": MANIFEST_ID,
            "manifest_sha256": MANIFEST_SHA256,
            "before_hashes": before_hashes,
        },
    }


class FDECommunityActionRuntime(CoreActionRuntime):
    """The CORE receipt state machine bound to the FDE-only native helper."""

    @classmethod
    def from_package(cls) -> "FDECommunityActionRuntime":
        package = Path(__file__).resolve().parents[1]
        helper = package / "skills" / "core-review-approval" / "scripts" / "fde-community-action.py"
        validator = package / "skills" / "core-review-approval" / "scripts" / "validate-approval.py"
        try:
            from hermes_constants import get_hermes_home  # type: ignore[reportMissingImports]
            home = Path(get_hermes_home())
        except Exception:
            home = Path(os.getenv("HERMES_HOME", str(Path.home() / ".hermes"))).expanduser()
        return cls(
            receipt_root=home / "state" / "donggu-obsidian" / "fde-community-receipts",
            helper_path=helper,
            validator_path=validator,
        )

    @staticmethod
    def _validate_result_hashes(result: Dict[str, Any]) -> Dict[str, Dict[str, Optional[str]]]:
        paths = result.get("paths")
        hashes = result.get("hashes")
        if paths != list(TARGET_PATHS) or not isinstance(hashes, dict) or set(hashes) != set(TARGET_PATHS):
            raise CoreRuntimeError("FDE Community helper returned an invalid fixed path set")
        for path in TARGET_PATHS:
            item = hashes.get(path)
            if not isinstance(item, dict) or set(item) != {"before", "after"}:
                raise CoreRuntimeError("FDE Community helper returned an invalid hash result")
            if item["before"] is not None and not _valid_hash(item["before"]):
                raise CoreRuntimeError("FDE Community helper returned an invalid before hash")
            if not _valid_hash(item["after"]):
                raise CoreRuntimeError("FDE Community helper returned an invalid after hash")
        return hashes

    @staticmethod
    def _validate_receipt_path(rel: str) -> str:
        if not isinstance(rel, str) or rel not in TARGET_PATHS:
            raise CoreRuntimeError("FDE Community receipt contains an invalid path")
        return rel

    @staticmethod
    def _ack_helper_flags(receipt: Dict[str, Any]) -> tuple[str, ...]:
        transaction = receipt.get("transaction_sha256")
        if not isinstance(transaction, str) or not _valid_hash(transaction):
            raise CoreRuntimeError("FDE Community receipt transaction binding is invalid")
        return (
            "--ack-candidate",
            str(receipt["candidate_code"]),
            "--ack-transaction",
            transaction,
        )

    def plan_fde_community(
        self,
        vault_root: Path,
        *,
        session_id: str,
        plan_message_id: int,
        latest_user_text: str,
    ) -> Dict[str, Any]:
        envelope = build_fde_community_envelope(vault_root)
        result = self.plan(
            vault_root,
            envelope,
            session_id=session_id,
            plan_message_id=plan_message_id,
            latest_user_text=latest_user_text,
        )
        result.update({
            "manifest_id": MANIFEST_ID,
            "created": len(NEW_PATHS),
            "modified": len(LEGACY_PATHS),
            "moved": 0,
            "deleted": 0,
        })
        return result
