"""Dependency-light command-line interface with stable JSON envelopes."""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Never

from mvia import __version__
from mvia.drift import compare
from mvia.errors import ConfigurationError, MviaError
from mvia.models import ProviderName, load_config, load_inventory
from mvia.redaction import redact
from mvia.service import discover


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
    verify = commands.add_parser("verify-live", help="Opt-in, read-only provider smoke test")
    verify.add_argument("--config", type=Path, required=True)
    verify.add_argument("--provider", type=ProviderName, choices=list(ProviderName), required=True)
    verify.add_argument("--confirm-read-only", action="store_true")
    drift = commands.add_parser("drift")
    drift.add_argument("--config", type=Path, required=True)
    drift.add_argument("--desired", type=Path, required=True)
    return root


def run(argv: list[str] | None = None) -> int:
    try:
        args = parser().parse_args(argv)
        config = load_config(args.config)
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
        if args.command == "verify-live":
            if not args.confirm_read_only:
                raise ConfigurationError("verify-live requires --confirm-read-only")
            if config.mode != "live":
                raise ConfigurationError(
                    "verify-live requires mode: live; fixtures are not evidence"
                )
            selected = config.providers.get(args.provider)
            if selected is None or not selected.enabled:
                raise ConfigurationError("selected live provider must be configured and enabled")
            if selected.fixture is not None:
                raise ConfigurationError("verify-live cannot use a fixture")
            if not selected.verify_tls:
                raise ConfigurationError("verify-live requires TLS verification")
            if args.provider is ProviderName.CLOUDFLARE and not selected.zone_ids:
                raise ConfigurationError("Cloudflare verification requires explicit zone_ids")
            scoped = config.model_copy(update={"providers": {args.provider: selected}})
            actual = discover(scoped, config_dir=args.config.resolve().parent)
            counts: dict[str, int] = {}
            for item in actual.resources:
                counts[item.kind] = counts.get(item.kind, 0) + 1
            emit(
                {
                    "ok": True,
                    "command": "verify-live",
                    "mode": "live",
                    "provider": args.provider.value,
                    "status": "read_only_discovery_completed",
                    "resource_counts": dict(sorted(counts.items())),
                    "note": "Live API read completed; permissions and scope require operator review.",
                }
            )
            return 0
        actual = discover(config, config_dir=args.config.resolve().parent)
        if args.command == "discover":
            emit({"ok": True, "command": "discover", "data": actual.model_dump(mode="json")})
            return 0
        report = compare(load_inventory(args.desired), actual)
        emit({"ok": True, "command": "drift", "data": report.model_dump(mode="json")})
        return 0 if report.in_sync else 2
    except MviaError as exc:
        emit({"ok": False, "error": {"type": type(exc).__name__, "message": redact(str(exc))}})
        return 1


def main() -> None:
    sys.exit(run())


if __name__ == "__main__":
    main()
