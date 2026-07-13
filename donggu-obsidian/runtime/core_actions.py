"""Minimal native receipt runtime for the crash-atomic CORE action helper."""
from __future__ import annotations

from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import secrets
import stat
import subprocess
import sys
import tempfile
import time
from typing import Any, Callable, Dict, Optional


class CoreRuntimeError(Exception):
    """Base error returned by the native CORE tools."""


class CoreApprovalError(CoreRuntimeError):
    """The trusted persisted user command did not authorize apply."""


class CoreReceiptError(CoreRuntimeError):
    """The local receipt cannot perform the requested transition."""


class CoreHelperError(CoreRuntimeError):
    """The crash-atomic helper failed its bounded contract."""


_RECEIPT_RE = re.compile(r"^[A-Za-z0-9_-]{20,80}$")
_HASH_RE = re.compile(r"^[0-9a-f]{64}$")
_MAX_ENVELOPE = 1_000_000
_MAX_RECEIPT = 1_100_000
_MAX_READBACK_FILE = 8 * 1024 * 1024
_MAX_STATUS_BYTES = 4096
_MAX_RECEIPT_TTL = 900
_ALLOWED_RECEIPT_STATES = {
    "planned", "applying", "reconciliation_required", "completed", "revoked", "ambiguous",
}
_TERMINAL_APPLY_STATES = {"reconciliation_required", "completed", "revoked", "ambiguous"}
_ALLOWED_VAULT_ROOTS = {"10_Sources", "20_Core", "40_Snippets", "50_Channel_Packs", "60_MOCs"}
_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)
_DIRECTORY = getattr(os, "O_DIRECTORY", 0)
_NONBLOCK = getattr(os, "O_NONBLOCK", 0)


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _transaction_sha256(candidate_code: Any, hashes: Any) -> str:
    return _sha256({"candidate_code": candidate_code, "hashes": hashes})


def _valid_hash(value: Any) -> bool:
    return isinstance(value, str) and _HASH_RE.fullmatch(value) is not None


class CoreReceiptStore:
    """Profile-local, one-time receipt files with atomic state transitions."""

    def __init__(self, root: Path, ttl_seconds: int = 900):
        self.root = Path(root).expanduser()
        self.ttl_seconds = min(max(int(ttl_seconds), 1), _MAX_RECEIPT_TTL)
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        try:
            info = self.root.lstat()
            if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
                raise CoreReceiptError("receipt store is unavailable")
            os.chmod(self.root, 0o700)
        except OSError:
            raise CoreReceiptError("receipt store is unavailable") from None

    def _path(self, receipt_id: str) -> Path:
        if not isinstance(receipt_id, str) or _RECEIPT_RE.fullmatch(receipt_id) is None:
            raise CoreReceiptError("invalid receipt id")
        return self.root / f"{receipt_id}.json"

    @contextmanager
    def _lock(self, receipt_id: str):
        lock_path = self.root / f"{self._path(receipt_id).stem}.lock"
        flags = os.O_CREAT | os.O_RDWR | _NOFOLLOW
        try:
            descriptor = os.open(lock_path, flags, 0o600)
        except OSError:
            raise CoreReceiptError("receipt lock is unavailable") from None
        with os.fdopen(descriptor, "a+b", closefd=True) as stream:
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)

    def _write(self, receipt: Dict[str, Any]) -> None:
        target = self._path(str(receipt.get("receipt_id") or ""))
        data = _canonical(receipt)
        if len(data) > _MAX_RECEIPT:
            raise CoreReceiptError("receipt is too large")
        descriptor, temp_name = tempfile.mkstemp(prefix=".core-receipt-", dir=str(self.root))
        try:
            os.fchmod(descriptor, 0o600)
            stream = os.fdopen(descriptor, "wb", closefd=True)
            descriptor = -1
            with stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp_name, target)
            os.chmod(target, 0o600)
            root_fd = os.open(self.root, os.O_RDONLY | _DIRECTORY | _NOFOLLOW)
            try:
                os.fsync(root_fd)
            finally:
                os.close(root_fd)
        except Exception:
            if descriptor >= 0:
                try:
                    os.close(descriptor)
                except OSError:
                    pass
            try:
                os.unlink(temp_name)
            except OSError:
                pass
            raise

    def issue(self, data: Dict[str, Any], *, expires_at: int) -> Dict[str, Any]:
        now = int(time.time())
        if isinstance(expires_at, bool) or not isinstance(expires_at, int):
            raise CoreReceiptError("receipt expiry is invalid")
        if expires_at <= now or expires_at > now + _MAX_RECEIPT_TTL:
            raise CoreReceiptError("receipt expiry is invalid")
        receipt = {
            **data,
            "receipt_id": secrets.token_urlsafe(24),
            "state": "planned",
            "created_at": now,
            "expires_at": expires_at,
        }
        self._write(receipt)
        return receipt

    def load(
        self,
        receipt_id: str,
        *,
        require_state: Optional[str] = None,
        enforce_expiry: bool = False,
    ) -> Dict[str, Any]:
        path = self._path(receipt_id)
        descriptor = -1
        try:
            descriptor = os.open(path, os.O_RDONLY | _NOFOLLOW | _NONBLOCK)
            info = os.fstat(descriptor)
            if not stat.S_ISREG(info.st_mode) or info.st_size > _MAX_RECEIPT:
                raise CoreReceiptError("receipt not found or invalid")
            chunks = []
            total = 0
            while True:
                chunk = os.read(descriptor, min(131072, _MAX_RECEIPT + 1 - total))
                if not chunk:
                    break
                chunks.append(chunk)
                total += len(chunk)
                if total > _MAX_RECEIPT:
                    raise CoreReceiptError("receipt not found or invalid")
            receipt = json.loads(b"".join(chunks).decode("utf-8"))
        except CoreReceiptError:
            raise
        except (OSError, ValueError, TypeError, UnicodeError):
            raise CoreReceiptError("receipt not found or invalid") from None
        finally:
            if descriptor >= 0:
                os.close(descriptor)
        if not isinstance(receipt, dict) or receipt.get("receipt_id") != receipt_id:
            raise CoreReceiptError("receipt binding mismatch")
        if receipt.get("state") not in _ALLOWED_RECEIPT_STATES:
            raise CoreReceiptError("receipt state is invalid")
        expires_at = receipt.get("expires_at")
        if isinstance(expires_at, bool) or not isinstance(expires_at, int):
            raise CoreReceiptError("receipt expiry is invalid")
        if enforce_expiry and int(time.time()) >= expires_at:
            raise CoreReceiptError("receipt expired")
        if require_state is not None and receipt.get("state") != require_state:
            raise CoreReceiptError("receipt is not available for this operation")
        return receipt

    def transition(self, receipt: Dict[str, Any], state: str, **updates: Any) -> Dict[str, Any]:
        if state not in _ALLOWED_RECEIPT_STATES:
            raise CoreReceiptError("receipt state is invalid")
        next_receipt = {**receipt, **updates, "state": state, "updated_at": int(time.time())}
        self._write(next_receipt)
        return next_receipt

    def claim(
        self,
        receipt_id: str,
        expected_state: str,
        next_state: str,
        *,
        validator: Optional[Callable[[Dict[str, Any]], None]] = None,
        enforce_expiry: bool = False,
        **updates: Any,
    ) -> Dict[str, Any]:
        with self._lock(receipt_id):
            receipt = self.load(
                receipt_id, require_state=expected_state, enforce_expiry=enforce_expiry,
            )
            if validator is not None:
                validator(receipt)
            return self.transition(receipt, next_state, **updates)


def _checked_vault_root(value: Path) -> tuple[Path, tuple[int, int]]:
    raw = os.path.expanduser(str(value))
    if not raw:
        raise CoreHelperError("Vault root is required")
    root = Path(os.path.abspath(raw))
    if len(root.parts) > 1 and root.parts[1] == "var" and os.path.realpath("/var") == "/private/var":
        root = Path("/private/var", *root.parts[2:])
    current = Path(root.anchor)
    try:
        for part in root.parts[1:]:
            current = current / part
            component = current.lstat()
            if stat.S_ISLNK(component.st_mode):
                raise CoreHelperError("Vault root path must not contain symlinks")
            if current != root and not stat.S_ISDIR(component.st_mode):
                raise CoreHelperError("Vault root path has a non-directory component")
        final = root.lstat()
    except CoreHelperError:
        raise
    except OSError:
        raise CoreHelperError("Vault root is not available") from None
    if not stat.S_ISDIR(final.st_mode):
        raise CoreHelperError("Vault root must be a directory")
    return root, (final.st_dev, final.st_ino)


def _validated_relative_path(value: Any) -> str:
    if not isinstance(value, str) or not value or len(value.encode("utf-8")) > 4096 or "\\" in value:
        raise CoreHelperError("CORE helper returned an invalid path")
    path = PurePosixPath(value)
    if path.is_absolute() or str(path) != value or len(path.parts) < 2:
        raise CoreHelperError("CORE helper returned an invalid path")
    if path.parts[0] not in _ALLOWED_VAULT_ROOTS or any(part in {"", ".", ".."} for part in path.parts):
        raise CoreHelperError("CORE helper returned an invalid path")
    return value


def _validated_hashes(result: Dict[str, Any]) -> Dict[str, Dict[str, Optional[str]]]:
    paths = result.get("paths")
    hashes = result.get("hashes")
    if (
        not isinstance(paths, list)
        or paths != sorted(set(paths))
        or len(paths) > 3
        or not isinstance(hashes, dict)
        or set(hashes) != set(paths)
    ):
        raise CoreHelperError("CORE helper returned an invalid path/hash result")
    for raw_rel in paths:
        rel = _validated_relative_path(raw_rel)
        item = hashes.get(rel)
        if not isinstance(item, dict) or set(item) != {"before", "after"}:
            raise CoreHelperError("CORE helper returned an invalid hash result")
        before, after = item.get("before"), item.get("after")
        if before is not None and not _valid_hash(before):
            raise CoreHelperError("CORE helper returned an invalid before hash")
        if not _valid_hash(after):
            raise CoreHelperError("CORE helper returned an invalid after hash")
    return hashes


def _receipt_binding_sha256(receipt: Dict[str, Any]) -> str:
    fields = (
        "vault_root", "vault_device", "vault_inode", "envelope", "envelope_sha256",
        "candidate_code", "source_sha256", "paths", "hashes", "transaction_sha256", "expires_at",
    )
    return _sha256({field: receipt.get(field) for field in fields})


def _open_root_descriptor(root: Path) -> int:
    descriptor = -1
    try:
        descriptor = os.open(root.anchor, os.O_RDONLY | _DIRECTORY | _NOFOLLOW)
        for part in root.parts[1:]:
            next_fd = os.open(part, os.O_RDONLY | _DIRECTORY | _NOFOLLOW, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = next_fd
        if not stat.S_ISDIR(os.fstat(descriptor).st_mode):
            raise OSError()
        return descriptor
    except OSError:
        if descriptor >= 0:
            os.close(descriptor)
        raise CoreReceiptError("Vault read-back is unavailable") from None


def _descriptor_hash(root_fd: int, rel: str) -> str:
    parts = PurePosixPath(_validated_relative_path(rel)).parts
    parent_fd = os.dup(root_fd)
    file_fd = -1
    try:
        for component in parts[:-1]:
            next_fd = os.open(component, os.O_RDONLY | _DIRECTORY | _NOFOLLOW, dir_fd=parent_fd)
            os.close(parent_fd)
            parent_fd = next_fd
        file_fd = os.open(parts[-1], os.O_RDONLY | _NOFOLLOW | _NONBLOCK, dir_fd=parent_fd)
        before = os.fstat(file_fd)
        if not stat.S_ISREG(before.st_mode) or before.st_size > _MAX_READBACK_FILE:
            raise OSError()
        digest = hashlib.sha256()
        total = 0
        while True:
            chunk = os.read(file_fd, min(1024 * 1024, _MAX_READBACK_FILE + 1 - total))
            if not chunk:
                break
            total += len(chunk)
            if total > _MAX_READBACK_FILE:
                raise OSError()
            digest.update(chunk)
        after = os.fstat(file_fd)
        if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
            after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns
        ):
            raise OSError()
        return digest.hexdigest()
    except (OSError, CoreHelperError):
        raise CoreReceiptError("Vault read-back failed") from None
    finally:
        if file_fd >= 0:
            os.close(file_fd)
        os.close(parent_fd)


class CoreActionRuntime:
    def __init__(
        self,
        *,
        receipt_root: Path,
        helper_path: Path,
        validator_path: Optional[Path] = None,
        receipt_ttl_seconds: int = 900,
        timeout: int = 60,
    ):
        self.store = CoreReceiptStore(receipt_root, receipt_ttl_seconds)
        self.helper_path = Path(helper_path).resolve()
        self.validator_path = Path(validator_path or self.helper_path.with_name("validate-approval.py")).resolve()
        self.timeout = int(timeout)
        if not self.helper_path.is_file() or not self.validator_path.is_file():
            raise CoreHelperError("CORE action helper or approval validator is not available")

    @classmethod
    def from_package(cls) -> "CoreActionRuntime":
        package = Path(__file__).resolve().parents[1]
        helper = package / "skills" / "core-review-approval" / "scripts" / "apply-action.py"
        try:
            from hermes_constants import get_hermes_home
            home = Path(get_hermes_home())
        except Exception:
            home = Path(os.getenv("HERMES_HOME", str(Path.home() / ".hermes"))).expanduser()
        return cls(
            receipt_root=home / "state" / "donggu-obsidian" / "receipts",
            helper_path=helper,
        )

    def _run(self, vault_root: Path, envelope: Optional[Dict[str, Any]], *flags: str) -> tuple[int, Dict[str, Any]]:
        data = b"" if envelope is None else _canonical(envelope)
        if len(data) > _MAX_ENVELOPE:
            raise CoreHelperError("CORE action envelope is too large")
        try:
            proc = subprocess.run(
                [sys.executable, str(self.helper_path), "--vault-root", str(vault_root), *flags],
                input=data,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=self.timeout,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            raise CoreHelperError("CORE action helper could not complete") from None
        payload: Dict[str, Any] = {}
        if proc.stdout and len(proc.stdout) <= _MAX_RECEIPT:
            try:
                decoded = json.loads(proc.stdout)
                if isinstance(decoded, dict):
                    payload = decoded
            except (ValueError, UnicodeError):
                pass
        return proc.returncode, payload

    def _validate_approval(self, text: str, expected_candidate: str) -> None:
        try:
            proc = subprocess.run(
                [sys.executable, str(self.validator_path)],
                input=text.encode("utf-8"),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=5,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            raise CoreApprovalError("approval validator could not complete") from None
        try:
            result = json.loads(proc.stdout) if proc.returncode == 0 else None
        except (ValueError, UnicodeError):
            result = None
        if (
            proc.returncode != 0
            or not isinstance(result, dict)
            or set(result) != {"candidate_code", "decision"}
            or result.get("candidate_code") != expected_candidate
            or result.get("decision") != "승인"
        ):
            raise CoreApprovalError("private legacy approval derivation failed")

    def _validate_receipt_binding(self, receipt: Dict[str, Any]) -> None:
        envelope = receipt.get("envelope")
        if not isinstance(envelope, dict):
            raise CoreReceiptError("receipt envelope is unavailable")
        if receipt.get("envelope_sha256") != _sha256(envelope):
            raise CoreReceiptError("receipt envelope binding mismatch")
        if receipt.get("candidate_code") != envelope.get("candidate_code"):
            raise CoreReceiptError("receipt candidate binding mismatch")
        root, identity = _checked_vault_root(Path(str(receipt.get("vault_root") or "")))
        if (
            str(root) != receipt.get("vault_root")
            or identity != (receipt.get("vault_device"), receipt.get("vault_inode"))
        ):
            raise CoreReceiptError("Vault root identity changed after preview")
        expected = receipt.get("receipt_sha256")
        if not _valid_hash(expected) or not secrets.compare_digest(expected, _receipt_binding_sha256(receipt)):
            raise CoreReceiptError("receipt plan binding mismatch")

    def plan(self, vault_root: Path, envelope: Any, **_legacy_context: Any) -> Dict[str, Any]:
        # Older renderer fixtures pass trusted session metadata. The minimal
        # receipt deliberately does not persist or authorize from those values.
        if not isinstance(envelope, dict):
            raise CoreHelperError("CORE action envelope must be an object")
        root, identity = _checked_vault_root(vault_root)
        code, result = self._run(root, envelope, "--dry-run")
        if code != 0 or result.get("status") != "planned":
            raise CoreHelperError(f"CORE action validation failed (exit {code})")
        hashes = _validated_hashes(result)
        candidate_code = envelope.get("candidate_code")
        envelope_sha256 = _sha256(envelope)
        now = int(time.time())
        expires_at = now + self.store.ttl_seconds
        receipt_data = {
            "vault_root": str(root),
            "vault_device": identity[0],
            "vault_inode": identity[1],
            "envelope": envelope,
            "envelope_sha256": envelope_sha256,
            "candidate_code": candidate_code,
            "source_sha256": envelope.get("source_sha256"),
            "paths": result.get("paths", []),
            "hashes": hashes,
            "transaction_sha256": _transaction_sha256(candidate_code, hashes),
            "expires_at": expires_at,
        }
        receipt_data["receipt_sha256"] = _receipt_binding_sha256(receipt_data)
        receipt = self.store.issue(receipt_data, expires_at=expires_at)
        return {
            "status": "planned",
            "receipt_id": receipt["receipt_id"],
            "expires_at": expires_at,
            "candidate_code": candidate_code,
            "envelope_sha256": envelope_sha256,
            "paths": receipt["paths"],
            "hashes": hashes,
        }

    def receipt_status(self, receipt_id: str) -> Dict[str, Any]:
        receipt = self.store.load(receipt_id)
        result = {
            "state": receipt["state"],
            "receipt_id": receipt["receipt_id"],
            "candidate_code": receipt.get("candidate_code"),
            "source_sha256": receipt.get("source_sha256"),
            "envelope_sha256": receipt.get("envelope_sha256"),
            "paths": receipt.get("paths"),
            "hashes": receipt.get("hashes"),
            "expires_at": receipt.get("expires_at"),
        }
        if len(_canonical(result)) > _MAX_STATUS_BYTES:
            raise CoreReceiptError("receipt status is too large")
        return result

    @staticmethod
    def _stored_result(receipt: Dict[str, Any]) -> Dict[str, Any]:
        result = receipt.get("result")
        if not isinstance(result, dict):
            raise CoreReceiptError("receipt result is unavailable")
        return result

    @staticmethod
    def _journal_matches(receipt: Dict[str, Any], journal: Dict[str, Any]) -> bool:
        return (
            journal.get("state") == "committed"
            and journal.get("candidate_code") == receipt.get("candidate_code")
            and journal.get("transaction_sha256") == receipt.get("transaction_sha256")
        )

    def _committed_result(
        self,
        receipt: Dict[str, Any],
        *,
        helper_status: Any,
        exit_code: int,
    ) -> Dict[str, Any]:
        result = {
            "status": "vault_committed_reconciliation_required",
            "operation_completed": False,
            "helper_status": helper_status,
            "journal_state": "committed",
            "receipt_id": receipt["receipt_id"],
            "candidate_code": receipt.get("candidate_code"),
            "paths": receipt.get("paths", []),
            "hashes": receipt.get("hashes"),
            "exit_code": exit_code,
            "next_action": "verify actual after hashes, complete the DB row, then acknowledge the journal",
        }
        self.store.transition(receipt, "reconciliation_required", result=result, envelope=None)
        return result

    def _classify_apply_outcome(
        self,
        receipt: Dict[str, Any],
        *,
        exit_code: int,
        helper_status: Any = None,
    ) -> Dict[str, Any]:
        try:
            journal = self.recovery_status(Path(receipt["vault_root"]))
        except CoreHelperError:
            journal = {"state": "unknown", "candidate_code": None, "transaction_sha256": None}
        if self._journal_matches(receipt, journal):
            return self._committed_result(
                receipt, helper_status=helper_status, exit_code=exit_code,
            )
        clean = journal.get("state") == "no_transaction"
        if clean and exit_code in {2, 3, 70}:
            result = {
                "status": "revoked",
                "operation_completed": False,
                "receipt_id": receipt["receipt_id"],
                "exit_code": exit_code,
                "reason": "helper_rejected_before_mutation" if exit_code != 3 else "rollback_verified",
            }
            self.store.transition(receipt, "revoked", result=result, envelope=None)
            return result
        result = {
            "status": "ambiguous",
            "operation_completed": False,
            "receipt_id": receipt["receipt_id"],
            "exit_code": exit_code,
            "helper_status": helper_status,
            "journal_state": journal.get("state"),
        }
        self.store.transition(receipt, "ambiguous", result=result)
        return result

    def apply(self, receipt_id: str, *, latest_user_text: str) -> Dict[str, Any]:
        if latest_user_text != "적용해줘":
            raise CoreApprovalError("latest persisted user text must exactly equal 적용해줘")
        observed = self.store.load(receipt_id)
        if observed.get("state") in _TERMINAL_APPLY_STATES:
            return self._stored_result(observed)
        if observed.get("state") != "planned":
            raise CoreReceiptError("receipt is not available for apply")
        candidate_code = observed.get("candidate_code")
        if not isinstance(candidate_code, str):
            raise CoreReceiptError("receipt has no candidate code")
        private_legacy_approval = f"{candidate_code} 승인"
        self._validate_approval(private_legacy_approval, candidate_code)
        receipt = self.store.claim(
            receipt_id,
            "planned",
            "applying",
            validator=self._validate_receipt_binding,
            enforce_expiry=True,
            approval_command="적용해줘",
        )
        try:
            code, helper_result = self._run(Path(receipt["vault_root"]), receipt["envelope"])
        except CoreHelperError:
            return self._classify_apply_outcome(receipt, exit_code=-1)
        if code == 0 and helper_result.get("status") == "applied":
            try:
                hashes = _validated_hashes(helper_result)
                valid = (
                    helper_result.get("candidate_code") == receipt.get("candidate_code")
                    and helper_result.get("state") == "committed"
                    and helper_result.get("paths") == receipt.get("paths")
                    and hashes == receipt.get("hashes")
                )
            except CoreHelperError:
                valid = False
            if valid:
                return self._committed_result(
                    receipt, helper_status="applied", exit_code=0,
                )
        return self._classify_apply_outcome(
            receipt, exit_code=code, helper_status=helper_result.get("status"),
        )

    def _mark_ambiguous(self, receipt: Dict[str, Any], reason: str) -> None:
        result = {
            "status": "ambiguous",
            "operation_completed": False,
            "receipt_id": receipt["receipt_id"],
            "reason": reason,
        }
        with self.store._lock(receipt["receipt_id"]):
            current = self.store.load(receipt["receipt_id"])
            if current.get("state") == "reconciliation_required":
                self.store.transition(current, "ambiguous", result=result)

    def readback(self, receipt_id: str) -> Dict[str, Any]:
        receipt = self.store.load(receipt_id)
        if receipt.get("state") == "completed":
            result = receipt.get("readback_result")
            if isinstance(result, dict):
                return result
        if receipt.get("state") != "reconciliation_required":
            raise CoreReceiptError("receipt is not available for read-back")
        journal = self.recovery_status(Path(receipt["vault_root"]))
        if not self._journal_matches(receipt, journal):
            self._mark_ambiguous(receipt, "journal_binding_mismatch")
            raise CoreReceiptError("committed journal does not match receipt")
        root, identity = _checked_vault_root(Path(receipt["vault_root"]))
        if identity != (receipt.get("vault_device"), receipt.get("vault_inode")):
            self._mark_ambiguous(receipt, "vault_identity_changed")
            raise CoreReceiptError("Vault root identity changed after preview")
        root_fd = _open_root_descriptor(root)
        try:
            actual = {}
            for rel in receipt.get("paths", []):
                actual[rel] = _descriptor_hash(root_fd, rel)
            current_identity = os.fstat(root_fd)
            if (current_identity.st_dev, current_identity.st_ino) != identity:
                raise CoreReceiptError("Vault root identity changed during read-back")
        except CoreReceiptError:
            self._mark_ambiguous(receipt, "after_hash_readback_failed")
            raise
        finally:
            os.close(root_fd)
        expected = receipt.get("hashes")
        if not isinstance(expected, dict) or any(
            actual.get(rel) != values.get("after")
            for rel, values in expected.items()
            if isinstance(values, dict)
        ) or set(actual) != set(expected):
            self._mark_ambiguous(receipt, "after_hash_mismatch")
            raise CoreReceiptError("actual after hashes do not match receipt")
        hashes = {
            rel: {"before": expected[rel]["before"], "after": actual[rel]}
            for rel in sorted(actual)
        }
        result = {
            "status": "readback_verified",
            "operation_completed": False,
            "receipt_id": receipt_id,
            "candidate_code": receipt.get("candidate_code"),
            "hashes": hashes,
        }
        with self.store._lock(receipt_id):
            current = self.store.load(receipt_id, require_state="reconciliation_required")
            self.store.transition(
                current,
                "reconciliation_required",
                readback_verified=True,
                readback_sha256=_sha256(hashes),
                readback_result=result,
            )
        return result

    def revoke(self, receipt_id: str) -> Dict[str, Any]:
        with self.store._lock(receipt_id):
            receipt = self.store.load(receipt_id)
            if receipt.get("state") == "revoked":
                return self._stored_result(receipt)
            if receipt.get("state") != "planned":
                raise CoreReceiptError("only a planned receipt can be revoked")
            result = {
                "status": "revoked",
                "operation_completed": False,
                "receipt_id": receipt_id,
            }
            self.store.transition(receipt, "revoked", result=result, envelope=None)
            return result

    def ack(self, receipt_id: str) -> Dict[str, Any]:
        receipt = self.store.load(receipt_id)
        if receipt.get("state") == "completed":
            return self._stored_result(receipt)
        if receipt.get("state") != "reconciliation_required" or receipt.get("readback_verified") is not True:
            raise CoreReceiptError("ack requires verified local reconciliation")
        journal = self.recovery_status(Path(receipt["vault_root"]))
        if not self._journal_matches(receipt, journal):
            self._mark_ambiguous(receipt, "journal_binding_mismatch")
            raise CoreReceiptError("committed journal does not match receipt")
        try:
            code, payload = self._run(
                Path(receipt["vault_root"]), None, "--ack-candidate", str(receipt["candidate_code"]),
            )
        except CoreHelperError:
            code, payload = -1, {}
        if (
            code == 0
            and payload == {
                "status": "acknowledged",
                "state": "committed",
                "candidate_code": receipt.get("candidate_code"),
            }
        ):
            result = {
                "status": "completed",
                "operation_completed": True,
                "receipt_id": receipt_id,
                "candidate_code": receipt.get("candidate_code"),
                "hashes": receipt.get("hashes"),
            }
            with self.store._lock(receipt_id):
                current = self.store.load(receipt_id, require_state="reconciliation_required")
                self.store.transition(current, "completed", result=result, envelope=None)
            return result
        if code == 6:
            result = {
                "status": "cleanup_retry_required",
                "operation_completed": False,
                "receipt_id": receipt_id,
                "exit_code": 6,
            }
            with self.store._lock(receipt_id):
                current = self.store.load(receipt_id, require_state="reconciliation_required")
                self.store.transition(current, "reconciliation_required", ack_result=result)
            return result
        if code == 70:
            result = {
                "status": "ack_retry_required",
                "operation_completed": False,
                "receipt_id": receipt_id,
                "exit_code": 70,
            }
            with self.store._lock(receipt_id):
                current = self.store.load(receipt_id, require_state="reconciliation_required")
                self.store.transition(current, "reconciliation_required", ack_result=result)
            return result
        result = {
            "status": "ambiguous",
            "operation_completed": False,
            "receipt_id": receipt_id,
            "exit_code": code,
        }
        with self.store._lock(receipt_id):
            current = self.store.load(receipt_id, require_state="reconciliation_required")
            self.store.transition(current, "ambiguous", result=result)
        return result

    def recovery_status(self, vault_root: Path) -> Dict[str, Any]:
        root, _identity = _checked_vault_root(vault_root)
        code, result = self._run(root, None, "--recovery-status")
        if code != 0 or set(result) != {"state", "candidate_code", "transaction_sha256"}:
            raise CoreHelperError(f"CORE recovery status failed (exit {code})")
        state = result.get("state")
        candidate = result.get("candidate_code")
        transaction_sha256 = result.get("transaction_sha256")
        if state not in {"no_transaction", "prepared", "rolled_back", "committed"}:
            raise CoreHelperError("CORE recovery status returned an invalid state")
        if (state == "no_transaction") != (candidate is None):
            raise CoreHelperError("CORE recovery status candidate binding is invalid")
        if state == "no_transaction":
            if transaction_sha256 is not None:
                raise CoreHelperError("CORE recovery status transaction binding is invalid")
        elif not _valid_hash(transaction_sha256):
            raise CoreHelperError("CORE recovery status transaction binding is invalid")
        return {
            "state": state,
            "candidate_code": candidate,
            "transaction_sha256": transaction_sha256,
        }
