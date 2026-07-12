#!/usr/bin/env python3
"""Validate one exact CORE review decision from stdin."""

import json
import re
import sys

PATTERN = re.compile(r"^\s*(CR-\d{8}-\d{6})\s+(승인|보류|거절)\s*$")


def main() -> int:
    text = sys.stdin.read()
    if len(text) > 4096:
        print("invalid approval command", file=sys.stderr)
        return 2
    match = PATTERN.fullmatch(text)
    if match is None:
        print("invalid approval command", file=sys.stderr)
        return 2
    print(
        json.dumps(
            {"candidate_code": match.group(1), "decision": match.group(2)},
            ensure_ascii=False,
            separators=(",", ":"),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
