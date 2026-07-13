#!/usr/bin/env python3
"""Render one bounded public preview from an exact candidate and native plan."""

import hashlib
import json
from pathlib import PurePosixPath
import re
import sys
from typing import Dict, List, Optional, TextIO, Tuple


MAX_STDIN_BYTES = 1024 * 1024
MAX_FRAGMENT = 500
MAX_CONTENT = 1800
ALLOWED_ROOTS = {"10_Sources", "20_Core", "40_Snippets", "50_Channel_Packs", "60_MOCs"}
INPUT_KEYS = {"candidate", "plan"}
CANDIDATE_KEYS = {
    "candidate_code", "candidate_type", "source_note_path", "source_sha256",
    "target_note_paths", "claim", "relationship", "rationale",
    "proposed_changes", "risk",
}
PLAN_KEYS = {
    "status", "receipt_id", "expires_at", "candidate_code",
    "envelope_sha256", "paths", "hashes",
}
REPLACE_KEYS = {"op", "schema_version", "old", "new"}
CREATE_KEYS = {
    "op", "schema_version", "template_version", "core_path", "moc_path",
    "moc_sha256", "trace_field",
}
HASH_ENTRY_KEYS = {"before", "after"}
HASH_RE = re.compile(r"^[0-9a-f]{64}$")
CODE_RE = re.compile(r"^CR-[0-9]{8}-[0-9]{6}$")
RECEIPT_RE = re.compile(r"^[A-Za-z0-9_-]{20,80}$")
WIKILINK_RE = re.compile(r"\[\[([^\[\]]+)\]\]")
EMAIL_RE = re.compile(
    r"(?i)\b[a-z0-9.!#$%&'*+/=?^_`{|}~-]+@"
    r"(?:[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?\.)+[a-z]{2,63}\b"
)
URI_RE = re.compile(
    r"(?i)(?:[a-z][a-z0-9+.-]*://|(?:mailto|data|tel|urn|file|git|ssh|s3):|www\.)\S+"
)
BEARER_RE = re.compile(r"(?i)\bbearer\s+[a-z0-9._~+/=-]+")
SECRET_RE = re.compile(
    r"(?i)\b(?:api[_-]?key|token|password|passwd|secret|client[_-]?secret|"
    r"access[_-]?token|refresh[_-]?token|private[_-]?key|authorization)\b\s*[:=]"
)
ABSOLUTE_RE = re.compile(
    r"(?i)(?:^|[\s('`\"])(?:/(?:Users|home|tmp|private|var|etc)/|[a-z]:[\\/]|\\\\)"
)
PHONE_RE = re.compile(r"(?<![0-9])(?:\+?[0-9][0-9 .()-]{7,}[0-9])(?![0-9])")
MENTION_RE = re.compile(r"<@!?[0-9]+>")
FORBIDDEN_TERMS = ("drift", "recommend_only", "unsupported apply")


class ValidationError(Exception):
    pass


def reject_duplicate_keys(pairs: List[Tuple[str, object]]) -> Dict[str, object]:
    value: Dict[str, object] = {}
    for key, item in pairs:
        if key in value:
            raise ValidationError()
        value[key] = item
    return value


def exact_object(value: object, keys: set) -> Dict[str, object]:
    if not isinstance(value, dict) or set(value) != keys:
        raise ValidationError()
    return value


def validate_hash(value: object) -> str:
    if not isinstance(value, str) or HASH_RE.fullmatch(value) is None:
        raise ValidationError()
    return value


def private_text(value: str) -> bool:
    folded = value.casefold()
    return (
        EMAIL_RE.search(value) is not None
        or URI_RE.search(value) is not None
        or BEARER_RE.search(value) is not None
        or SECRET_RE.search(value) is not None
        or ABSOLUTE_RE.search(value) is not None
        or PHONE_RE.search(value) is not None
        or MENTION_RE.search(value) is not None
        or any(term in folded for term in FORBIDDEN_TERMS)
    )


def safe_text(
    value: object,
    *,
    max_chars: int = MAX_FRAGMENT,
    allow_empty: bool = False,
    allow_none: bool = False,
) -> Optional[str]:
    if value is None and allow_none:
        return None
    if not isinstance(value, str):
        raise ValidationError()
    try:
        value.encode("utf-8")
    except UnicodeError:
        raise ValidationError() from None
    # Privacy is checked before the length boundary so a secret beyond the
    # visible limit can never be turned into an apparently safe partial field.
    if private_text(value):
        raise ValidationError()
    if (not allow_empty and not value) or len(value) > max_chars:
        raise ValidationError()
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise ValidationError()
    return value


def safe_path(value: object, expected_root: Optional[str] = None) -> str:
    text = safe_text(value)
    assert text is not None
    if "\\" in text or any(char in text for char in "\r\n\t[]#|^\""):
        raise ValidationError()
    path = PurePosixPath(text)
    if path.is_absolute() or str(path) != text or path.suffix != ".md":
        raise ValidationError()
    if len(path.parts) < 2 or path.parts[0] not in ALLOWED_ROOTS:
        raise ValidationError()
    if expected_root is not None and path.parts[0] != expected_root:
        raise ValidationError()
    if any(part in {"", ".", "..", "00_Inbox"} or part.startswith(".env") for part in path.parts):
        raise ValidationError()
    return text


def canonical_link_target(raw: str) -> str:
    target = raw.split("|", 1)[0].split("#", 1)[0]
    if target.endswith(".md"):
        target = target[:-3]
    return safe_path(target + ".md")


def canonical_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    except (RecursionError, TypeError, UnicodeError, ValueError):
        raise ValidationError() from None


def parse(stdin: TextIO) -> Dict[str, object]:
    raw = stdin.read(MAX_STDIN_BYTES + 1)
    try:
        if len(raw.encode("utf-8")) > MAX_STDIN_BYTES:
            raise ValidationError()
        value = json.loads(raw, object_pairs_hook=reject_duplicate_keys)
    except (RecursionError, TypeError, UnicodeError, ValueError):
        raise ValidationError() from None
    return exact_object(value, INPUT_KEYS)


def validate_candidate(value: object) -> Tuple[Dict[str, object], Dict[str, object]]:
    candidate = exact_object(value, CANDIDATE_KEYS)
    code = candidate["candidate_code"]
    if not isinstance(code, str) or CODE_RE.fullmatch(code) is None:
        raise ValidationError()
    candidate_type = safe_text(candidate["candidate_type"], max_chars=64)
    source = safe_path(candidate["source_note_path"])
    validate_hash(candidate["source_sha256"])
    safe_text(candidate["claim"], allow_none=True)
    safe_text(candidate["relationship"], max_chars=32)
    safe_text(candidate["rationale"], max_chars=2000)
    safe_text(candidate["risk"], max_chars=16)

    targets = candidate["target_note_paths"]
    if (
        not isinstance(targets, list)
        or not 1 <= len(targets) <= 20
        or any(not isinstance(item, str) for item in targets)
    ):
        raise ValidationError()
    checked_targets = [safe_path(item) for item in targets]
    if checked_targets != sorted(set(checked_targets)):
        raise ValidationError()

    changes = candidate["proposed_changes"]
    if not isinstance(changes, list) or len(changes) != 1:
        raise ValidationError()
    action = changes[0]
    if not isinstance(action, dict):
        raise ValidationError()
    op = action.get("op")

    if op == "replace":
        exact_object(action, REPLACE_KEYS)
        if candidate_type not in {"fix_link", "link_existing"}:
            raise ValidationError()
        if type(action["schema_version"]) is not int or action["schema_version"] != 1:
            raise ValidationError()
        old = safe_text(action["old"])
        new = safe_text(action["new"])
        if old is None or new is None:
            raise ValidationError()
        if old == new:
            raise ValidationError()
        links = [canonical_link_target(match.group(1)) for match in WIKILINK_RE.finditer(new)]
        if links != checked_targets or len(links) != len(set(links)):
            raise ValidationError()
    elif op == "create_core_with_backlink":
        exact_object(action, CREATE_KEYS)
        if candidate_type != "new_core" or PurePosixPath(source).parts[0] not in {"10_Sources", "50_Channel_Packs"}:
            raise ValidationError()
        for field in ("schema_version", "template_version"):
            if type(action[field]) is not int or action[field] != 1:
                raise ValidationError()
        claim = safe_text(candidate["claim"])
        if claim is None:
            raise ValidationError()
        core_path = safe_path(action["core_path"], "20_Core")
        moc_path = safe_path(action["moc_path"], "60_MOCs")
        validate_hash(action["moc_sha256"])
        trace_field = safe_text(action["trace_field"], max_chars=32)
        expected_trace = "extracted_to" if source.startswith("10_Sources/") else "decomposed_to"
        if trace_field != expected_trace or checked_targets != sorted([core_path, moc_path]):
            raise ValidationError()
    else:
        raise ValidationError()
    return candidate, action


def expected_envelope(candidate: Dict[str, object], action: Dict[str, object]) -> Dict[str, object]:
    return {
        "schema_version": 1,
        "candidate_code": candidate["candidate_code"],
        "candidate_type": candidate["candidate_type"],
        "source_note_path": candidate["source_note_path"],
        "source_sha256": candidate["source_sha256"],
        "claim": candidate["claim"],
        "target_note_paths": candidate["target_note_paths"],
        "action": action,
    }


def validate_plan(
    value: object, candidate: Dict[str, object], action: Dict[str, object]
) -> Dict[str, object]:
    plan = exact_object(value, PLAN_KEYS)
    if plan["status"] != "planned" or plan["candidate_code"] != candidate["candidate_code"]:
        raise ValidationError()
    if not isinstance(plan["receipt_id"], str) or RECEIPT_RE.fullmatch(plan["receipt_id"]) is None:
        raise ValidationError()
    if isinstance(plan["expires_at"], bool) or not isinstance(plan["expires_at"], int) or plan["expires_at"] <= 0:
        raise ValidationError()
    envelope_sha = validate_hash(plan["envelope_sha256"])
    actual_envelope_sha = hashlib.sha256(canonical_bytes(expected_envelope(candidate, action))).hexdigest()
    if envelope_sha != actual_envelope_sha:
        raise ValidationError()

    paths = plan["paths"]
    if not isinstance(paths, list) or not 1 <= len(paths) <= 3:
        raise ValidationError()
    checked_paths = [safe_path(path) for path in paths]
    if checked_paths != sorted(set(checked_paths)):
        raise ValidationError()
    hashes = plan["hashes"]
    if not isinstance(hashes, dict) or set(hashes) != set(checked_paths):
        raise ValidationError()
    for path in checked_paths:
        entry = exact_object(hashes[path], HASH_ENTRY_KEYS)
        if entry["before"] is not None:
            validate_hash(entry["before"])
        validate_hash(entry["after"])

    source = str(candidate["source_note_path"])
    source_sha = str(candidate["source_sha256"])
    if hashes.get(source, {}).get("before") != source_sha:
        raise ValidationError()
    if action["op"] == "replace":
        if checked_paths != [source] or hashes[source]["after"] == source_sha:
            raise ValidationError()
    else:
        core = str(action["core_path"])
        moc = str(action["moc_path"])
        if checked_paths != sorted([source, core, moc]):
            raise ValidationError()
        if hashes[core]["before"] is not None or hashes[moc]["before"] != action["moc_sha256"]:
            raise ValidationError()
        if hashes[source]["after"] == source_sha or hashes[moc]["after"] == action["moc_sha256"]:
            raise ValidationError()
    return plan


def render_content(candidate: Dict[str, object], action: Dict[str, object]) -> str:
    if action["op"] == "replace":
        content = "\n".join((
            "수정안을 준비했습니다.",
            "",
            "변경할 파일",
            str(candidate["source_note_path"]),
            "",
            "변경 전",
            str(action["old"]),
            "",
            "변경 후",
            str(action["new"]),
            "",
            "영향 범위",
            "- 변경 위치 1곳",
            "- 대상 노트 존재: 확인됨",
            "- 다른 본문과 링크는 변경하지 않음",
            "",
            "검증",
            "- 원본 문서가 점검 이후 바뀌지 않음",
            "- 변경 파일 1개",
            "- 아직 Vault 변경 0건",
            "",
            "적용하려면 “적용해줘”라고 답해주세요.",
            "이번에는 하지 않으려면 “넘겨줘”라고 답해주세요.",
        ))
    else:
        content = "\n".join((
            "수정안을 준비했습니다.",
            "",
            "새 CORE 파일",
            str(action["core_path"]),
            "",
            "한 줄 주장",
            str(candidate["claim"]),
            "",
            "원본 backlink 필드",
            str(action["trace_field"]),
            "",
            "연결할 MOC",
            str(action["moc_path"]),
            "",
            "영향 범위",
            "- 새 CORE 1개 생성",
            "- 원본과 MOC에 연결 추가",
            "",
            "검증",
            "- 원본 문서와 MOC가 점검 이후 바뀌지 않음",
            "- 아직 Vault 변경 0건",
            "",
            "적용하려면 “적용해줘”라고 답해주세요.",
            "이번에는 하지 않으려면 “넘겨줘”라고 답해주세요.",
        ))
    if len(content) > MAX_CONTENT or private_text(content):
        raise ValidationError()
    return content


def render(value: Dict[str, object]) -> Dict[str, str]:
    candidate, action = validate_candidate(value["candidate"])
    plan = validate_plan(value["plan"], candidate, action)
    binding = {
        "candidate_code": candidate["candidate_code"],
        "source_sha256": candidate["source_sha256"],
        "envelope_sha256": plan["envelope_sha256"],
        "paths": plan["paths"],
        "hashes": plan["hashes"],
    }
    preview_hash = hashlib.sha256(canonical_bytes(binding)).hexdigest()
    return {
        "content": render_content(candidate, action),
        "preview_hash": preview_hash,
        "candidate_code": str(candidate["candidate_code"]),
    }


def main() -> int:
    try:
        result = render(parse(sys.stdin))
        output = json.dumps(result, ensure_ascii=False, separators=(",", ":"))
        output.encode("utf-8")
        print(output)
        return 0
    except (BrokenPipeError, OSError, ValidationError):
        try:
            print("preview rendering failed", file=sys.stderr)
        except (BrokenPipeError, OSError):
            pass
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
