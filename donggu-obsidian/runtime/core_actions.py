"""Safe runtime bridge to the existing crash-atomic CORE action helper."""
from __future__ import annotations

import hashlib
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import re
import secrets
import stat
import subprocess
import sys
import tempfile
import time
from typing import Any, Callable, Dict, Optional


class CoreRuntimeError(Exception):
    pass


class CoreApprovalError(CoreRuntimeError):
    pass


class CoreReceiptError(CoreRuntimeError):
    pass


class CoreHelperError(CoreRuntimeError):
    pass


_RECEIPT_RE = re.compile(r"^[A-Za-z0-9_-]{20,80}$")
_MAX_ENVELOPE = 1_000_000


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


class CoreReceiptStore:
    def __init__(self, root: Path, ttl_seconds: int = 900):
        self.root = Path(root).expanduser()
        self.ttl_seconds = int(ttl_seconds)
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        try:
            os.chmod(self.root, 0o700)
        except OSError:
            pass

    def _path(self, receipt_id: str) -> Path:
        if not isinstance(receipt_id, str) or _RECEIPT_RE.fullmatch(receipt_id) is None:
            raise CoreReceiptError("invalid receipt id")
        return self.root / (receipt_id + ".json")

    @contextmanager
    def _lock(self, receipt_id: str):
        lock_path = self.root / (self._path(receipt_id).stem + ".lock")
        fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
        with os.fdopen(fd, "a+b", closefd=True) as stream:
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)

    def _write(self, receipt: Dict[str, Any]) -> None:
        target = self._path(str(receipt["receipt_id"]))
        fd, temp_name = tempfile.mkstemp(prefix=".core-receipt-", dir=str(self.root))
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "wb", closefd=True) as stream:
                stream.write(_canonical(receipt))
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp_name, target)
            os.chmod(target, 0o600)
        except Exception:
            try:
                os.close(fd)
            except OSError:
                pass
            try:
                os.unlink(temp_name)
            except OSError:
                pass
            raise

    def issue(self, data: Dict[str, Any]) -> Dict[str, Any]:
        now = int(time.time())
        receipt = {
            **data,
            "receipt_id": secrets.token_urlsafe(24),
            "state": "planned",
            "created_at": now,
            "expires_at": now + self.ttl_seconds,
        }
        self._write(receipt)
        return receipt

    def load(self, receipt_id: str, *, require_state: Optional[str] = None) -> Dict[str, Any]:
        path = self._path(receipt_id)
        try:
            if stat.S_ISLNK(path.lstat().st_mode):
                raise CoreReceiptError("invalid receipt file")
            receipt = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            raise CoreReceiptError("receipt not found or invalid") from None
        if receipt.get("receipt_id") != receipt_id:
            raise CoreReceiptError("receipt binding mismatch")
        if int(receipt.get("expires_at", 0)) < int(time.time()) and receipt.get("state") == "planned":
            raise CoreReceiptError("receipt expired")
        if require_state is not None and receipt.get("state") != require_state:
            raise CoreReceiptError("receipt is not available for this operation")
        return receipt

    def transition(self, receipt: Dict[str, Any], state: str, **updates: Any) -> Dict[str, Any]:
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
        **updates: Any,
    ) -> Dict[str, Any]:
        with self._lock(receipt_id):
            receipt = self.load(receipt_id, require_state=expected_state)
            if validator is not None:
                validator(receipt)
            return self.transition(receipt, next_state, **updates)


def _checked_vault_root(value: Path) -> tuple[Path, tuple[int, int]]:
    raw = os.path.expanduser(str(value))
    if not raw:
        raise CoreHelperError("Vault root is required")
    root = Path(os.path.abspath(raw))
    try:
        final = root.lstat()
    except OSError:
        raise CoreHelperError("Vault root is not available") from None
    if stat.S_ISLNK(final.st_mode):
        raise CoreHelperError("Vault root must not be a symlink")
    if not stat.S_ISDIR(final.st_mode):
        raise CoreHelperError("Vault root must be a directory")
    return root, (final.st_dev, final.st_ino)


def _validated_hashes(result: Dict[str, Any]) -> Dict[str, Dict[str, Optional[str]]]:
    paths = result.get("paths")
    hashes = result.get("hashes")
    if not isinstance(paths, list) or paths != sorted(set(paths)) or not isinstance(hashes, dict) or set(hashes) != set(paths):
        raise CoreHelperError("CORE helper returned an invalid path/hash result")
    for rel in paths:
        item = hashes.get(rel)
        if not isinstance(rel, str) or not isinstance(item, dict) or set(item) != {"before", "after"}:
            raise CoreHelperError("CORE helper returned an invalid hash result")
        before, after = item.get("before"), item.get("after")
        if before is not None and (not isinstance(before, str) or re.fullmatch(r"[0-9a-f]{64}", before) is None):
            raise CoreHelperError("CORE helper returned an invalid before hash")
        if not isinstance(after, str) or re.fullmatch(r"[0-9a-f]{64}", after) is None:
            raise CoreHelperError("CORE helper returned an invalid after hash")
    return hashes


_RECEIPT_BINDING_FIELDS = (
    "vault_root",
    "vault_device",
    "vault_inode",
    "envelope",
    "envelope_sha256",
    "candidate_code",
    "hashes",
)


def _receipt_binding_sha256(receipt: Dict[str, Any]) -> str:
    return _sha256({field: receipt.get(field) for field in _RECEIPT_BINDING_FIELDS})


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
        home = Path(os.getenv("HERMES_HOME", str(Path.home() / ".hermes"))).expanduser()
        return cls(
            receipt_root=home / "state" / "donggu-obsidian" / "receipts",
            helper_path=helper,
        )

    def _run(self, vault_root: Path, envelope: Optional[Dict[str, Any]], *flags: str) -> tuple[int, Dict[str, Any]]:
        root = Path(vault_root)
        data = b"" if envelope is None else _canonical(envelope)
        if len(data) > _MAX_ENVELOPE:
            raise CoreHelperError("CORE action envelope is too large")
        try:
            proc = subprocess.run(
                [sys.executable, str(self.helper_path), "--vault-root", str(root), *flags],
                input=data,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=self.timeout,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            raise CoreHelperError("CORE action helper could not complete") from None
        payload: Dict[str, Any] = {}
        if proc.stdout:
            try:
                decoded = json.loads(proc.stdout)
                if isinstance(decoded, dict):
                    payload = decoded
            except (ValueError, UnicodeError):
                payload = {}
        return proc.returncode, payload

    def _validate_approval(self, text: str, expected_candidate: str) -> None:
        if not isinstance(text, str) or not text.strip():
            raise CoreApprovalError("explicit approval text is required")
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
            raise CoreApprovalError("approval must exactly match the receipt candidate and decision 승인")

    def plan(self, vault_root: Path, envelope: Any) -> Dict[str, Any]:
        if not isinstance(envelope, dict):
            raise CoreHelperError("CORE action envelope must be an object")
        root, root_identity = _checked_vault_root(vault_root)
        code, result = self._run(root, envelope, "--dry-run")
        if code != 0 or result.get("status") != "planned":
            raise CoreHelperError(f"CORE action validation failed (exit {code})")
        hashes = _validated_hashes(result)
        envelope_sha256 = _sha256(envelope)
        receipt_data = {
            "vault_root": str(root),
            "vault_device": root_identity[0],
            "vault_inode": root_identity[1],
            "envelope": envelope,
            "envelope_sha256": envelope_sha256,
            "candidate_code": envelope.get("candidate_code"),
            "hashes": hashes,
        }
        receipt_data["receipt_sha256"] = _receipt_binding_sha256(receipt_data)
        receipt = self.store.issue(receipt_data)
        return {
            "status": "planned",
            "receipt_id": receipt["receipt_id"],
            "expires_at": receipt["expires_at"],
            "candidate_code": envelope.get("candidate_code"),
            "envelope_sha256": envelope_sha256,
            "paths": result.get("paths", []),
            "hashes": hashes,
        }

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
            journal = {"state": "unknown", "candidate_code": None}
        journal_state = journal.get("state")
        if journal_state == "committed":
            status = "reconciliation_required"
        elif journal_state == "prepared":
            status = "manual_recovery_required"
        elif journal_state == "rolled_back":
            status = "cleanup_retry_required"
        elif journal_state == "no_transaction" and exit_code == 3:
            status = "rolled_back"
        elif journal_state == "no_transaction" and exit_code in {2, 4, 70}:
            status = "safe_to_release"
        elif journal_state == "no_transaction":
            status = "failed"
        else:
            status = "outcome_unknown"
        result = {
            "status": status,
            "operation_completed": False,
            "helper_status": helper_status,
            "receipt_id": receipt["receipt_id"],
            "candidate_code": receipt.get("candidate_code"),
            "journal_state": journal_state,
            "journal_candidate_code": journal.get("candidate_code"),
            "exit_code": exit_code,
            "hashes": receipt.get("hashes"),
        }
        self.store.transition(receipt, status, result=result)
        return result

    def apply(self, receipt_id: str, *, approval_text: str) -> Dict[str, Any]:
        observed = self.store.load(receipt_id, require_state="planned")
        candidate_code = observed.get("candidate_code")
        if not isinstance(candidate_code, str):
            raise CoreReceiptError("receipt has no candidate code")
        self._validate_approval(approval_text, candidate_code)

        def validate(receipt: Dict[str, Any]) -> None:
            expected_binding = receipt.get("receipt_sha256")
            actual_binding = _receipt_binding_sha256(receipt)
            if not isinstance(expected_binding, str) or not secrets.compare_digest(expected_binding, actual_binding):
                raise CoreReceiptError("receipt plan binding mismatch")
            if receipt.get("candidate_code") != candidate_code:
                raise CoreReceiptError("receipt candidate binding mismatch")
            if receipt.get("envelope_sha256") != _sha256(receipt.get("envelope")):
                raise CoreReceiptError("receipt envelope binding mismatch")
            root, identity = _checked_vault_root(Path(receipt["vault_root"]))
            if str(root) != receipt.get("vault_root") or list(identity) != [receipt.get("vault_device"), receipt.get("vault_inode")]:
                raise CoreReceiptError("Vault root identity changed after preview")

        receipt = self.store.claim(
            receipt_id,
            "planned",
            "applying",
            validator=validate,
            approval_sha256=hashlib.sha256(approval_text.strip().encode("utf-8")).hexdigest(),
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
                    and hashes == receipt.get("hashes")
                )
            except CoreHelperError:
                valid = False
                hashes = receipt.get("hashes")
            if valid:
                result = {
                    "status": "vault_committed_reconciliation_required",
                    "operation_completed": False,
                    "helper_status": "applied",
                    "journal_state": "committed",
                    "receipt_id": receipt_id,
                    "candidate_code": helper_result.get("candidate_code"),
                    "paths": helper_result.get("paths", []),
                    "hashes": hashes,
                    "next_action": "complete the candidate in the DB, verify after hashes, then acknowledge the committed journal",
                }
                self.store.transition(receipt, "reconciliation_required", result=result, envelope=None)
                return result
        return self._classify_apply_outcome(
            receipt,
            exit_code=code,
            helper_status=helper_result.get("status"),
        )

    def recovery_status(self, vault_root: Path) -> Dict[str, Any]:
        root, _identity = _checked_vault_root(vault_root)
        code, result = self._run(root, None, "--recovery-status")
        if code != 0 or set(result) != {"state", "candidate_code"}:
            raise CoreHelperError(f"CORE recovery status failed (exit {code})")
        state = result.get("state")
        candidate = result.get("candidate_code")
        if state not in {"no_transaction", "prepared", "rolled_back", "committed"}:
            raise CoreHelperError("CORE recovery status returned an invalid state")
        if (state == "no_transaction") != (candidate is None):
            raise CoreHelperError("CORE recovery status candidate binding is invalid")
        return {"state": state, "candidate_code": candidate}
