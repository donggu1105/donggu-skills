#!/usr/bin/env python3
"""stdin/stdout JSON bridge for Claude Code and manual operations."""
from __future__ import annotations

import json
import sys
from typing import Any, Dict

try:
    from .publishing import PublishingError, PublishingRuntime
except ImportError:
    from publishing import PublishingError, PublishingRuntime


def execute(request: Dict[str, Any], runtime: PublishingRuntime) -> Dict[str, Any]:
    action = request.get("action")
    if action == "preview":
        return runtime.preview(
            channel=str(request.get("channel") or ""), operation=str(request.get("operation") or ""),
            payload=request.get("payload"), topic=str(request.get("topic") or ""), note_path=str(request.get("note_path") or ""),
        )
    if action == "approve":
        return runtime.approve(
            str(request.get("receipt_id") or ""), approval_text=str(request.get("approval_text") or ""),
        )
    if action == "confirm_maily":
        return runtime.confirm_irreversible(
            str(request.get("receipt_id") or ""), confirmation_text=str(request.get("confirmation_text") or ""),
        )
    if action == "dispatch":
        return runtime.dispatch(str(request.get("receipt_id") or ""))
    if action == "status":
        return runtime.receipt_status(str(request.get("receipt_id") or ""))
    raise PublishingError("action must be preview, approve, confirm_maily, dispatch, or status")


def main() -> int:
    try:
        raw = sys.stdin.buffer.read(1_000_001)
        if len(raw) > 1_000_000:
            raise PublishingError("request is too large")
        request = json.loads(raw or b"{}")
        if not isinstance(request, dict):
            raise PublishingError("request must be a JSON object")
        result = execute(request, PublishingRuntime.from_env())
        print(json.dumps({"success": True, **result}, ensure_ascii=False))
        return 0
    except (PublishingError, ValueError, UnicodeError) as exc:
        print(json.dumps({"success": False, "error": str(exc)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
