"""Runtime service settings, using environment variables only."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Settings:
    log_level: str = "INFO"
    environment: str = "development"
    diagnostic_timeout: float = 3.0
    diagnostic_redirect_limit: int = 3
    diagnostic_response_size_limit: int = 262144
    allow_private_diagnostics: bool = False

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            log_level=os.getenv("MVIA_LOG_LEVEL", "INFO").upper(),
            environment=os.getenv("MVIA_ENVIRONMENT", "development")[:100],
            diagnostic_timeout=_bounded_float("MVIA_DIAGNOSTIC_TIMEOUT", 3.0, 0.1, 30.0),
            diagnostic_redirect_limit=_bounded_int("MVIA_DIAGNOSTIC_REDIRECT_LIMIT", 3, 0, 5),
            diagnostic_response_size_limit=_bounded_int(
                "MVIA_DIAGNOSTIC_RESPONSE_SIZE_LIMIT", 262144, 1024, 1048576
            ),
            allow_private_diagnostics=os.getenv("MVIA_ALLOW_PRIVATE_DIAGNOSTICS", "false").lower()
            in {"1", "true", "yes"},
        )


def _bounded_float(name: str, default: float, minimum: float, maximum: float) -> float:
    try:
        value = float(os.getenv(name, str(default)))
    except ValueError:
        return default
    return min(max(value, minimum), maximum)


def _bounded_int(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        return default
    return min(max(value, minimum), maximum)
