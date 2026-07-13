#!/usr/bin/env python3
"""Render one bounded public preview from an exact candidate and native plan."""

import hashlib
import json
import math
from pathlib import PurePosixPath
import re
import sys
from typing import Dict, List, Optional, TextIO, Tuple
import unicodedata


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
EMAIL_RE = re.compile(
    r"(?i)\b[a-z0-9.!#$%&'*+/=?^_`{|}~-]+@"
    r"(?:[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?\.)+[a-z]{2,63}\b"
)
URI_RE = re.compile(
    r"(?i)(?:[a-z][a-z0-9+.-]*://|(?:mailto|data|tel|urn|file|git|ssh|s3):|www\.)\S+"
)
BEARER_RE = re.compile(r"(?i)\bbearer\s+[a-z0-9._~+/=-]+")
SECRET_TERM_RE = re.compile(
    r"(?i)(?<![A-Za-z0-9])(?:api[ _-]?key|token|password|passwd|secret|"
    r"client[ _-]?secret|access[ _-]?(?:key|token)|refresh[ _-]?token|"
    r"private[ _-]?keys?|authorization|credentials?)(?![A-Za-z0-9])"
)
PEM_RE = re.compile(
    r"(?i)-----(?:BEGIN|END) [A-Z0-9 ]*(?:PRIVATE KEY|CERTIFICATE)-----"
)
AWS_KEY_RE = re.compile(r"(?<![A-Z0-9])(?:AKIA|ASIA)[A-Z0-9]{16}(?![A-Z0-9])")
JWT_RE = re.compile(
    r"(?<![A-Za-z0-9_-])eyJ[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{2,}\."
    r"[A-Za-z0-9_-]*(?![A-Za-z0-9_-])"
)
PROVIDER_KEY_RE = re.compile(
    r"(?i)(?<![A-Za-z0-9])(?:sk-(?:proj-|live-|test-)?[A-Za-z0-9_-]{16,}|"
    r"gh[pousr]_[A-Za-z0-9]{20,}|xox[baprs]-[A-Za-z0-9-]{16,}|"
    r"AIza[A-Za-z0-9_-]{20,}|hf_[A-Za-z0-9]{20,}|glpat-[A-Za-z0-9_-]{16,}|"
    r"npm_[A-Za-z0-9]{20,})"
)
CREDENTIAL_RUN_RE = re.compile(r"(?<![A-Za-z0-9_+/=-])[A-Za-z0-9_+/=-]{24,}(?![A-Za-z0-9_+/=-])")
PHONE_RE = re.compile(r"(?<![0-9])(?:\+?[0-9][0-9 .()-]{7,}[0-9])(?![0-9])")
FORBIDDEN_TERMS = ("drift", "recommend_only", "unsupported apply")
FORBIDDEN_UNICODE_CATEGORIES = {"Cc", "Cf", "Cs", "Co", "Cn", "Zl", "Zp"}
DISPLAY_PUNCTUATION = frozenset(" -(),.:'")
PATH_PUNCTUATION = frozenset(" -(),.")


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


def credential_like_run(value: str) -> bool:
    for match in CREDENTIAL_RUN_RE.finditer(value):
        run = match.group(0)
        classes = sum((
            any(char.islower() for char in run),
            any(char.isupper() for char in run),
            any(char.isdigit() for char in run),
            any(char in "_+/=-" for char in run),
        ))
        if classes < 3:
            continue
        entropy = -sum(
            (run.count(char) / len(run)) * math.log2(run.count(char) / len(run))
            for char in set(run)
        )
        if entropy >= 3.5:
            return True
    return False


def sensitive_text(value: str) -> bool:
    folded = value.casefold()
    return (
        "@" in value
        or EMAIL_RE.search(value) is not None
        or URI_RE.search(value) is not None
        or BEARER_RE.search(value) is not None
        or SECRET_TERM_RE.search(value) is not None
        or PEM_RE.search(value) is not None
        or AWS_KEY_RE.search(value) is not None
        or JWT_RE.search(value) is not None
        or PROVIDER_KEY_RE.search(value) is not None
        or credential_like_run(value)
        or PHONE_RE.search(value) is not None
        or any(term in folded for term in FORBIDDEN_TERMS)
    )


def validate_unicode(value: str) -> None:
    try:
        value.encode("utf-8")
    except UnicodeError:
        raise ValidationError() from None
    if unicodedata.normalize("NFC", value) != value:
        raise ValidationError()
    if any(unicodedata.category(char) in FORBIDDEN_UNICODE_CATEGORIES for char in value):
        raise ValidationError()


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
    validate_unicode(value)
    # Privacy is checked before the length boundary so a secret beyond the
    # visible limit can never be turned into an apparently safe partial field.
    if sensitive_text(value):
        raise ValidationError()
    if (not allow_empty and not value) or len(value) > max_chars:
        raise ValidationError()
    return value


def ordinary_display_char(char: str) -> bool:
    if char in DISPLAY_PUNCTUATION:
        return True
    category = unicodedata.category(char)
    if category.startswith("N"):
        return True
    if not category.startswith("L"):
        return False
    if char.isascii():
        return char.isalpha()
    name = unicodedata.name(char, "")
    return "HANGUL" in name or "LATIN" in name


def safe_display_text(value: object, *, max_chars: int = MAX_FRAGMENT) -> str:
    text = safe_text(value, max_chars=max_chars)
    assert text is not None
    if text != text.strip(" ") or not all(ordinary_display_char(char) for char in text):
        raise ValidationError()
    return text


def safe_path_segment(segment: str) -> None:
    if (
        not segment
        or segment != segment.strip(" ")
        or segment.startswith(".")
        or segment.endswith(".")
        or segment in {".", "..", "00_Inbox"}
    ):
        raise ValidationError()
    for char in segment:
        if char in PATH_PUNCTUATION:
            continue
        category = unicodedata.category(char)
        if category.startswith("N"):
            continue
        if category.startswith("L"):
            name = unicodedata.name(char, "")
            if (char.isascii() and char.isalpha()) or "HANGUL" in name or "LATIN" in name:
                continue
        raise ValidationError()


def safe_path(value: object, expected_root: Optional[str] = None) -> str:
    text = safe_text(value)
    assert text is not None
    if text.startswith(("/", "~")) or "\\" in text:
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
    for part in path.parts[1:-1]:
        safe_path_segment(part)
    safe_path_segment(path.stem)
    return text


def validate_wikilink(value: object, *, require_qualified: bool) -> Tuple[str, str]:
    text = safe_text(value)
    assert text is not None
    if (
        not (text.startswith("[[") and text.endswith("]]"))
        or text.count("[[") != 1
        or text.count("]]") != 1
    ):
        raise ValidationError()
    inner = text[2:-2]
    if not inner or any(char in inner for char in "[]\n\r\t") or inner.count("|") > 1:
        raise ValidationError()
    if "|" in inner:
        target_and_fragment, alias = inner.split("|", 1)
    else:
        target_and_fragment, alias = inner, None
    if target_and_fragment.count("#") > 1:
        raise ValidationError()
    if "#" in target_and_fragment:
        target, fragment = target_and_fragment.split("#", 1)
    else:
        target, fragment = target_and_fragment, None
    if not target:
        raise ValidationError()
    if "/" in target:
        target_path = target if target.endswith(".md") else target + ".md"
        canonical = safe_path(target_path)
    else:
        if require_qualified:
            raise ValidationError()
        title = target[:-3] if target.endswith(".md") else target
        safe_display_text(title, max_chars=200)
        canonical = title + ".md"
    if fragment is not None:
        safe_display_text(fragment, max_chars=120)
    if alias is not None:
        safe_display_text(alias, max_chars=120)
    return text, canonical


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
        old, _old_target = validate_wikilink(action["old"], require_qualified=False)
        new, new_target = validate_wikilink(action["new"], require_qualified=True)
        if old == new:
            raise ValidationError()
        if [new_target] != checked_targets:
            raise ValidationError()
    elif op == "create_core_with_backlink":
        exact_object(action, CREATE_KEYS)
        if candidate_type != "new_core" or PurePosixPath(source).parts[0] not in {"10_Sources", "50_Channel_Packs"}:
            raise ValidationError()
        for field in ("schema_version", "template_version"):
            if type(action[field]) is not int or action[field] != 1:
                raise ValidationError()
        claim = safe_display_text(candidate["claim"])
        core_path = safe_path(action["core_path"], "20_Core")
        moc_path = safe_path(action["moc_path"], "60_MOCs")
        validate_hash(action["moc_sha256"])
        trace_field = action["trace_field"]
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


def render_content(
    candidate: Dict[str, object], action: Dict[str, object], receipt_id: str
) -> str:
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
    if len(content) > MAX_CONTENT or receipt_id in content or sensitive_text(content):
        raise ValidationError()
    if any(
        char != "\n" and unicodedata.category(char) in FORBIDDEN_UNICODE_CATEGORIES
        for char in content
    ):
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
        "content": render_content(candidate, action, str(plan["receipt_id"])),
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
