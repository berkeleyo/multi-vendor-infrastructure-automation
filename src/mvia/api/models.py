"""Versioned API request and error models."""

from pydantic import BaseModel, ConfigDict, Field


class ErrorDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    request_id: str


class ErrorEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    error: ErrorDetail


class HealthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str = "healthy"
    service: str = "multi-vendor-infrastructure-automation"
    version: str = "0.2.0"


class ProviderCapability(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    capabilities: list[str]


class ProviderCapabilitiesResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    providers: list[ProviderCapability]


class DriftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    desired: dict[str, object]
    discovered: dict[str, object] | None = None


class DiscoveryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    config: dict[str, object] = Field(default_factory=dict)
