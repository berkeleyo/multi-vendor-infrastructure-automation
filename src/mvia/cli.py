"""Dependency-light command-line interface with stable JSON envelopes."""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Never

from mvia import __version__
from mvia.application import ApplicationService
from mvia.errors import MviaError
from mvia.redaction import redact


class JsonArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> Never:
        raise MviaError(f"invalid command arguments: {message}")


def emit(payload: Any) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))


def parser() -> argparse.ArgumentParser:
    root = JsonArgumentParser(
        prog="mvia", description="Read-only multi-vendor inventory and drift CLI"
    )
    root.add_argument("--version", action="version", version=__version__)
    commands = root.add_subparsers(dest="command", required=True)
    for name in ("validate", "discover"):
        command = commands.add_parser(name)
        command.add_argument("--config", type=Path, required=True)
    drift = commands.add_parser("drift")
    drift.add_argument("--config", type=Path, required=True)
    drift.add_argument("--desired", type=Path, required=True)
    return root


def run(argv: list[str] | None = None) -> int:
    try:
        args = parser().parse_args(argv)
        service = ApplicationService()
        config = service.validate_config(args.config)
        if args.command == "validate":
            emit(
                {
                    "ok": True,
                    "command": "validate",
                    "providers": sorted(config.providers),
                    "mode": config.mode,
                }
            )
            return 0
        if args.command == "discover":
            actual = service.discover(args.config)
            emit({"ok": True, "command": "discover", "data": actual.model_dump(mode="json")})
            return 0
        report = service.drift(args.config, args.desired)
        emit({"ok": True, "command": "drift", "data": report.model_dump(mode="json")})
        return 0 if report.in_sync else 2
    except MviaError as exc:
        emit({"ok": False, "error": {"type": type(exc).__name__, "message": redact(str(exc))}})
        return 1


def main() -> None:
    sys.exit(run())


if __name__ == "__main__":
    main()
