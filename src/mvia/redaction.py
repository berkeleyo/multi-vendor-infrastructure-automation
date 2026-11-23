"""Recursive secret redaction for safe structured errors."""

import re
from typing import Any

SENSITIVE = (
    "authorization",
    "cookie",
    "set-cookie",
    "token",
    "secret",
    "password",
    "api_key",
    "apikey",
    "x-api-key",
)


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: "[REDACTED]" if any(term in key.lower() for term in SENSITIVE) else redact(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, str):
        value = re.sub(r"(?i)bearer\s+[a-z0-9._~+/=-]+", "Bearer [REDACTED]", value)
        return re.sub(
            r"(?i)(token|secret|password|api[_-]?key)(\s*[:=]\s*)([^\s,;]+)",
            r"\1\2[REDACTED]",
            value,
        )
    return value
