#!/usr/bin/env python3
"""Thin manual CLI for the shared Life OS runtime."""
from __future__ import annotations

import argparse
from datetime import date
import importlib.util
import json
import os
from pathlib import Path
import sys
import uuid
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


RUNTIME_PATH = Path(__file__).resolve().parents[3] / "runtime" / "life_os.py"


def _load_runtime_module():
    spec = importlib.util.spec_from_file_location("donggu_life_os_shared_runtime", RUNTIME_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load shared runtime: {RUNTIME_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_runtime_module = _load_runtime_module()
LifeOSError = _runtime_module.LifeOSError
LifeOSRuntime = _runtime_module.LifeOSRuntime


def _default_state_root() -> str:
    configured = os.environ.get("DONGGU_LIFE_OS_STATE_ROOT")
    if configured:
        return configured
    xdg_state = os.environ.get("XDG_STATE_HOME")
    base = Path(xdg_state).expanduser() if xdg_state else Path.home() / ".local/state"
    return str(base / "donggu-life-os")


def _optional_date(value: str | None) -> date | None:
    return date.fromisoformat(value) if value else None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="life-os")
    parser.add_argument(
        "--vault-root",
        default=os.environ.get("DONGGU_LIFE_OS_VAULT_ROOT"),
        help="absolute Obsidian Vault root (or DONGGU_LIFE_OS_VAULT_ROOT)",
    )
    parser.add_argument("--state-root", default=_default_state_root())
    parser.add_argument(
        "--timezone", default=os.environ.get("DONGGU_LIFE_OS_TIMEZONE", "Asia/Seoul")
    )
    commands = parser.add_subparsers(dest="command", required=True)

    status = commands.add_parser("status")
    status.add_argument("--date")

    start = commands.add_parser("start")
    start.add_argument("--date")
    start.add_argument("--resume", action="store_true")

    record = commands.add_parser("record")
    record.add_argument(
        "operation", choices=("answer", "skip", "pause", "resume", "capture", "free_record")
    )
    record.add_argument("--date")
    record.add_argument("--message-key")
    record.add_argument("--attachment", action="append", default=[])
    record.add_argument("--follow-up-question")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.vault_root:
        parser.error("--vault-root or DONGGU_LIFE_OS_VAULT_ROOT is required")
    try:
        runtime = LifeOSRuntime(
            vault_root=Path(args.vault_root).expanduser(),
            state_root=Path(args.state_root).expanduser(),
            timezone=ZoneInfo(args.timezone),
        )
        if args.command == "status":
            result = runtime.status(_optional_date(args.date))
        elif args.command == "start":
            result = runtime.start_daily(_optional_date(args.date), resume=args.resume)
        else:
            text = sys.stdin.read()
            result = runtime.record(
                args.operation,
                message_text=text,
                message_key=args.message_key or f"manual:{uuid.uuid4().hex}",
                attachment_paths=tuple(Path(value) for value in args.attachment),
                follow_up_question=args.follow_up_question,
                target_date=_optional_date(args.date),
            )
    except (LifeOSError, ValueError, ZoneInfoNotFoundError) as exc:
        print(f"life-os: error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
