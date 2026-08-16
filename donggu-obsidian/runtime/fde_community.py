"""Receipt-backed runtime for the fixed FDE Community separation action."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
import fcntl
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
    CoreHelperError,
    CoreReceiptError,
    CoreRuntimeError,
    _sha256,
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

    @contextmanager
    def _vault_writer_lock(self, vault_root: Path):
        root, _identity = _checked_vault_root(vault_root)
        root_fd = _open_root_descriptor(root)
        try:
            try:
                fcntl.flock(root_fd, fcntl.LOCK_EX)
            except OSError:
                raise CoreReceiptError("FDE Community Vault writer fence is unavailable") from None
            yield
        finally:
            try:
                fcntl.flock(root_fd, fcntl.LOCK_UN)
            except OSError:
                pass
            os.close(root_fd)

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
        if result.get("status") == "applied":
            FDECommunityActionRuntime._validated_tree_identity(result.get("tree_identity"))
        return hashes

    @staticmethod
    def _validated_tree_identity(value: Any) -> list[int]:
        if (
            not isinstance(value, list)
            or len(value) != 2
            or any(isinstance(item, bool) or not isinstance(item, int) or item < 0 for item in value)
        ):
            raise CoreRuntimeError("FDE Community tree identity is unavailable")
        return [int(value[0]), int(value[1])]

    @staticmethod
    def _tree_identity_binding(receipt: Dict[str, Any], identity: list[int]) -> str:
        return _sha256({
            "receipt_sha256": receipt.get("receipt_sha256"),
            "tree_identity": identity,
        })

    @classmethod
    def _journal_matches(cls, receipt: Dict[str, Any], journal: Dict[str, Any]) -> bool:
        if not super()._journal_matches(receipt, journal):
            return False
        if receipt.get("state") in {"reconciliation_required", "acknowledging", "completed"}:
            try:
                expected = cls._validated_tree_identity(receipt.get("tree_identity"))
                journal_identity = cls._validated_tree_identity(journal.get("tree_identity"))
                current_identity = cls._validated_tree_identity(journal.get("current_tree_identity"))
            except CoreRuntimeError:
                return False
            return expected == journal_identity == current_identity
        return True

    @classmethod
    def _validate_tree_readback_context(cls, receipt: Dict[str, Any], journal: Dict[str, Any]) -> None:
        try:
            expected = cls._validated_tree_identity(receipt.get("tree_identity"))
            journal_identity = cls._validated_tree_identity(journal.get("tree_identity"))
            current_identity = cls._validated_tree_identity(journal.get("current_tree_identity"))
        except CoreRuntimeError:
            raise CoreReceiptError("FDE Community tree identity is unavailable") from None
        if expected != journal_identity or expected != current_identity:
            raise CoreReceiptError("FDE Community tree identity changed")
        expected_binding = cls._tree_identity_binding(receipt, expected)
        if receipt.get("tree_identity_binding_sha256") != expected_binding:
            raise CoreReceiptError("FDE Community tree identity binding mismatch")

    @classmethod
    def _validate_live_tree_identity(cls, receipt: Dict[str, Any]) -> None:
        expected = cls._validated_tree_identity(receipt.get("tree_identity"))
        root, identity = _checked_vault_root(Path(receipt["vault_root"]))
        if identity != (receipt.get("vault_device"), receipt.get("vault_inode")):
            raise CoreReceiptError("Vault root identity changed after preview")
        root_fd = -1
        tree_fd = -1
        try:
            root_fd = _open_root_descriptor(root)
            root_info = os.fstat(root_fd)
            if (root_info.st_dev, root_info.st_ino) != identity:
                raise CoreReceiptError("Vault root identity changed during FDE tree check")
            tree_fd = os.open(
                "FDE Community",
                os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0),
                dir_fd=root_fd,
            )
            tree_info = os.fstat(tree_fd)
            if not stat.S_ISDIR(tree_info.st_mode) or [int(tree_info.st_dev), int(tree_info.st_ino)] != expected:
                raise CoreReceiptError("FDE Community tree identity changed")
            final_root = os.fstat(root_fd)
            if (final_root.st_dev, final_root.st_ino) != identity:
                raise CoreReceiptError("Vault root identity changed during FDE tree check")
        except CoreRuntimeError:
            raise
        except OSError:
            raise CoreReceiptError("FDE Community tree identity could not be checked") from None
        finally:
            if tree_fd >= 0:
                os.close(tree_fd)
            if root_fd >= 0:
                os.close(root_fd)

    def _validate_readback_context(self, receipt: Dict[str, Any], journal: Dict[str, Any]) -> None:
        self._validate_tree_readback_context(receipt, journal)

    def _validate_readback_context_after_hashes(self, receipt: Dict[str, Any]) -> None:
        try:
            journal = self.recovery_status(Path(receipt["vault_root"]))
        except CoreRuntimeError:
            raise CoreReceiptError("FDE Community tree identity could not be rechecked") from None
        self._validate_tree_readback_context(receipt, journal)
        self._validate_live_tree_identity(receipt)

    def _validate_ack_context_before_completion(self, receipt: Dict[str, Any]) -> None:
        try:
            journal = self.recovery_status(Path(receipt["vault_root"]))
        except CoreRuntimeError:
            raise CoreReceiptError("FDE Community ack journal evidence could not be checked") from None
        evidence = receipt.get("ack_journal_evidence")
        if journal.get("state") == "no_transaction":
            if not isinstance(evidence, dict):
                raise CoreReceiptError("FDE Community ack journal evidence is missing")
            try:
                expected_tree = self._validated_tree_identity(receipt.get("tree_identity"))
                evidence_tree = self._validated_tree_identity(evidence.get("tree_identity"))
                evidence_current = self._validated_tree_identity(evidence.get("current_tree_identity"))
            except CoreRuntimeError:
                raise CoreReceiptError("FDE Community ack journal evidence is invalid") from None
            if (
                evidence.get("state") != "committed"
                or evidence.get("candidate_code") != receipt.get("candidate_code")
                or evidence.get("transaction_sha256") != receipt.get("transaction_sha256")
                or evidence_tree != expected_tree
                or evidence_current != expected_tree
            ):
                raise CoreReceiptError("FDE Community ack journal evidence binding mismatch")
            if receipt.get("tree_identity_binding_sha256") != self._tree_identity_binding(receipt, expected_tree):
                raise CoreReceiptError("FDE Community tree identity binding mismatch")
        elif journal.get("state") == "committed":
            self._validate_tree_readback_context(receipt, journal)
            current_evidence = self._ack_journal_evidence(journal)
            if evidence != current_evidence:
                raise CoreReceiptError("FDE Community ack journal evidence changed")
        else:
            raise CoreReceiptError("FDE Community ack journal state is unknown")
        self._validate_live_tree_identity(receipt)

    def _finalize_ack_after_completion(self, receipt: Dict[str, Any]) -> None:
        try:
            journal = self.recovery_status(Path(receipt["vault_root"]))
        except CoreRuntimeError:
            raise CoreRuntimeError("FDE Community ack cleanup status is unavailable") from None
        if journal.get("state") == "no_transaction":
            self._validate_ack_context_before_completion(receipt)
            return
        if journal.get("state") != "committed" or not self._journal_matches(receipt, journal):
            raise CoreRuntimeError("FDE Community ack cleanup journal binding changed")
        try:
            code, payload = self._run(
                Path(receipt["vault_root"]), None,
                *self._ack_helper_flags(receipt),
            )
        except CoreHelperError:
            raise CoreRuntimeError("FDE Community ack cleanup helper failed") from None
        if code != 0 or payload != {
            "status": "acknowledged",
            "state": "committed",
            "candidate_code": receipt.get("candidate_code"),
        }:
            raise CoreRuntimeError("FDE Community ack cleanup was not confirmed")
        try:
            after = self.recovery_status(Path(receipt["vault_root"]))
        except CoreRuntimeError:
            raise CoreRuntimeError("FDE Community ack cleanup read-back failed") from None
        if after.get("state") != "no_transaction":
            raise CoreRuntimeError("FDE Community ack journal was not removed")
        self._validate_ack_context_before_completion(receipt)

    def _committed_result(
        self,
        receipt: Dict[str, Any],
        *,
        helper_status: Any,
        exit_code: int,
    ) -> Dict[str, Any]:
        def ambiguous(reason: str) -> Dict[str, Any]:
            result = {
                "status": "ambiguous",
                "operation_completed": False,
                "receipt_id": receipt["receipt_id"],
                "exit_code": exit_code,
                "helper_status": helper_status,
                "reason": reason,
            }
            current = self.store.load(receipt["receipt_id"])
            if current.get("state") != "ambiguous":
                self.store.transition(current, "ambiguous", result=result)
            return result

        with self._vault_writer_lock(Path(receipt["vault_root"])):
            try:
                journal = self.recovery_status(Path(receipt["vault_root"]))
                identity = self._validated_tree_identity(journal.get("current_tree_identity"))
                journal_identity = self._validated_tree_identity(journal.get("tree_identity"))
                if journal.get("state") != "committed" or identity != journal_identity:
                    raise CoreRuntimeError()
            except (CoreRuntimeError, CoreReceiptError, KeyError):
                return ambiguous("fde_tree_identity_unavailable")
            result = {
                "status": "vault_committed_reconciliation_required",
                "operation_completed": False,
                "helper_status": helper_status,
                "journal_state": "committed",
                "receipt_id": receipt["receipt_id"],
                "candidate_code": receipt.get("candidate_code"),
                "paths": receipt.get("paths", []),
                "hashes": receipt.get("hashes"),
                "tree_identity": identity,
                "exit_code": exit_code,
                "next_action": "verify actual after hashes, complete the DB row, then acknowledge the journal",
            }
            binding = self._tree_identity_binding(receipt, identity)
            transitioned = self.store.transition(
                receipt,
                "reconciliation_required",
                result=result,
                tree_identity=identity,
                tree_identity_binding_sha256=binding,
                envelope=None,
            )
            try:
                after = self.recovery_status(Path(receipt["vault_root"]))
                after_identity = self._validated_tree_identity(after.get("current_tree_identity"))
                after_journal_identity = self._validated_tree_identity(after.get("tree_identity"))
                if (
                    after.get("state") != "committed"
                    or after_identity != identity
                    or after_journal_identity != identity
                    or transitioned.get("tree_identity") != identity
                ):
                    raise CoreRuntimeError()
            except (CoreRuntimeError, CoreReceiptError, KeyError):
                return ambiguous("fde_tree_identity_changed_after_receipt_write")
            return result

    def ack(self, receipt_id: str, *, completion_nonce: str) -> Dict[str, Any]:
        receipt = self.store.load(receipt_id)
        if receipt.get("state") in {"reconciliation_required", "acknowledging"}:
            try:
                identity = self._validated_tree_identity(receipt.get("tree_identity"))
                if receipt.get("tree_identity_binding_sha256") != self._tree_identity_binding(receipt, identity):
                    raise CoreReceiptError("FDE Community tree identity binding mismatch")
            except CoreRuntimeError:
                raise CoreReceiptError("FDE Community tree identity binding is unavailable") from None
        return super().ack(receipt_id, completion_nonce=completion_nonce)

    def recovery_status(self, vault_root: Path) -> Dict[str, Any]:
        root, _identity = _checked_vault_root(vault_root)
        code, result = self._run(root, None, "--recovery-status")
        expected_keys = {
            "state", "candidate_code", "transaction_sha256",
            "tree_identity", "current_tree_identity",
        }
        if code != 0 or set(result) != expected_keys:
            raise CoreHelperError(f"FDE Community recovery status failed (exit {code})")
        state = result.get("state")
        candidate = result.get("candidate_code")
        transaction = result.get("transaction_sha256")
        if state not in {"no_transaction", "prepared", "rolled_back", "committed"}:
            raise CoreHelperError("FDE Community recovery status returned an invalid state")
        if (state == "no_transaction") != (candidate is None):
            raise CoreHelperError("FDE Community recovery status candidate binding is invalid")
        if state == "no_transaction":
            if transaction is not None or result.get("tree_identity") is not None or result.get("current_tree_identity") is not None:
                raise CoreHelperError("FDE Community recovery status empty binding is invalid")
            return {
                "state": state,
                "candidate_code": candidate,
                "transaction_sha256": transaction,
                "tree_identity": None,
                "current_tree_identity": None,
            }
        if not _valid_hash(transaction):
            raise CoreHelperError("FDE Community recovery status transaction binding is invalid")
        try:
            tree_identity = self._validated_tree_identity(result.get("tree_identity"))
            current = result.get("current_tree_identity")
            current_identity = None if current is None else self._validated_tree_identity(current)
        except CoreRuntimeError:
            raise CoreHelperError("FDE Community recovery status tree binding is invalid") from None
        return {
            "state": state,
            "candidate_code": candidate,
            "transaction_sha256": transaction,
            "tree_identity": tree_identity,
            "current_tree_identity": current_identity,
        }

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

    def _ack_prepare_helper_flags(self, receipt: Dict[str, Any]) -> tuple[str, ...]:
        return (*self._ack_helper_flags(receipt), "--ack-retain-journal")

    def _ack_journal_evidence(self, journal: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if journal.get("state") != "committed":
            raise CoreRuntimeError("FDE Community ack requires a committed journal")
        try:
            tree_identity = self._validated_tree_identity(journal.get("tree_identity"))
            current_identity = self._validated_tree_identity(journal.get("current_tree_identity"))
        except CoreRuntimeError:
            raise CoreRuntimeError("FDE Community ack journal tree evidence is invalid") from None
        transaction = journal.get("transaction_sha256")
        candidate = journal.get("candidate_code")
        if not isinstance(candidate, str) or not isinstance(transaction, str) or not _valid_hash(transaction):
            raise CoreRuntimeError("FDE Community ack journal evidence is invalid")
        if tree_identity != current_identity:
            raise CoreRuntimeError("FDE Community ack journal tree identity changed")
        return {
            "state": "committed",
            "candidate_code": candidate,
            "transaction_sha256": transaction,
            "tree_identity": tree_identity,
            "current_tree_identity": current_identity,
        }

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
