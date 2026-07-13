#!/usr/bin/env python3
"""Validate one exact thread-bound CORE conversation command from stdin."""

import json
import re
import sys
from typing import Dict, List, TextIO, Tuple


MAX_STDIN_BYTES = 64 * 1024
CHANNEL_ID = "1526033497100390641"
USER_ID = "736583402244931584"
INPUT_KEYS = {"message", "thread_id", "channel_id", "user_id", "message_id"}
COMMANDS = {
    "수정안 보여줘": "preview",
    "적용해줘": "apply",
    "넘겨줘": "hold",
    "거절할게": "reject",
}
DECIMAL_ID = re.compile(r"^[1-9][0-9]*$")


class ValidationError(Exception):
    pass


def reject_duplicate_keys(pairs: List[Tuple[str, object]]) -> Dict[str, object]:
    value: Dict[str, object] = {}
    for key, item in pairs:
        if key in value:
            raise ValidationError()
        value[key] = item
    return value


def parse(stdin: TextIO) -> Dict[str, str]:
    raw = stdin.read(MAX_STDIN_BYTES + 1)
    try:
        if len(raw.encode("utf-8")) > MAX_STDIN_BYTES:
            raise ValidationError()
        value = json.loads(raw, object_pairs_hook=reject_duplicate_keys)
    except (RecursionError, TypeError, UnicodeError, ValueError):
        raise ValidationError() from None

    if not isinstance(value, dict) or set(value) != INPUT_KEYS:
        raise ValidationError()
    if any(not isinstance(value[key], str) for key in INPUT_KEYS):
        raise ValidationError()

    message = value["message"]
    if len(message) >= 64 or "\n" in message or "\r" in message:
        raise ValidationError()
    command = COMMANDS.get(message)
    if command is None:
        raise ValidationError()

    for key in ("thread_id", "channel_id", "user_id", "message_id"):
        if DECIMAL_ID.fullmatch(value[key]) is None:
            raise ValidationError()
    if value["channel_id"] != CHANNEL_ID or value["user_id"] != USER_ID:
        raise ValidationError()

    return {
        "command": command,
        "thread_id": value["thread_id"],
        "channel_id": value["channel_id"],
        "user_id": value["user_id"],
        "message_id": value["message_id"],
    }


def main() -> int:
    try:
        result = parse(sys.stdin)
        output = json.dumps(result, ensure_ascii=False, separators=(",", ":"))
        output.encode("utf-8")
        print(output)
        return 0
    except (BrokenPipeError, OSError, ValidationError):
        try:
            print("invalid conversation command", file=sys.stderr)
        except (BrokenPipeError, OSError):
            pass
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
