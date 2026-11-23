"""Typed provider-neutral network diagnostic models."""

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class DiagnosticStatus(StrEnum):
    OK = "ok"
    WARNING = "warning"
    ERROR = "error"


def _default_record_types() -> list[Literal["A", "AAAA", "CNAME", "MX", "TXT", "NS"]]:
    result: list[Literal["A", "AAAA", "CNAME", "MX", "TXT", "NS"]] = [
        "A",
        "AAAA",
        "CNAME",
    ]
    return result


class DNSRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hostname: str = Field(min_length=1, max_length=253)
    record_types: list[Literal["A", "AAAA", "CNAME", "MX", "TXT", "NS"]] = Field(
        default_factory=_default_record_types
    )


class DNSRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    record_type: str
    value: str
    ttl: int | None = None


class DNSResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hostname: str
    status: DiagnosticStatus
    records: list[DNSRecord] = Field(default_factory=list)
    duration_ms: float
    errors: list[str] = Field(default_factory=list)


class TLSRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hostname: str = Field(min_length=1, max_length=253)
    port: int = Field(default=443, ge=1, le=65535)


class TLSResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hostname: str
    port: int
    status: DiagnosticStatus
    handshake_success: bool
    tls_version: str | None = None
    cipher: str | None = None
    subject: dict[str, object] | None = None
    issuer: dict[str, object] | None = None
    san: list[str] = Field(default_factory=list)
    not_before: str | None = None
    not_after: str | None = None
    days_remaining: int | None = None
    hostname_valid: bool | None = None
    chain_validation: Literal["valid", "invalid", "unknown"] = "unknown"
    duration_ms: float
    errors: list[str] = Field(default_factory=list)


class HTTPRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str = Field(min_length=1, max_length=2048)
    method: Literal["HEAD", "GET"] = "HEAD"


class HTTPResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str
    final_url: str | None = None
    status: DiagnosticStatus
    http_status: int | None = None
    method: str
    total_duration_ms: float
    redirect_count: int = 0
    headers: dict[str, str] = Field(default_factory=dict)
    content_type: str | None = None
    tls_used: bool
    errors: list[str] = Field(default_factory=list)
