"""Typed configuration and normalized inventory models."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from mvia.errors import ConfigurationError


class ProviderName(StrEnum):
    AWS = "aws"
    AZURE = "azure"
    CLOUDFLARE = "cloudflare"
    PALO_ALTO = "palo_alto"


class Resource(BaseModel):
    """Provider-neutral, deterministically comparable resource."""

    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    provider: ProviderName
    kind: str = Field(min_length=1)
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    location: str | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)


class ProviderConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    enabled: bool = True
    fixture: Path | None = None
    region: str | None = None
    subscription_id: str | None = None
    account_id: str | None = None
    zone_ids: list[str] = Field(default_factory=list)
    base_url: str | None = None
    verify_tls: bool = True

    @field_validator("base_url")
    @classmethod
    def require_https(cls, value: str | None) -> str | None:
        if value is not None and not value.startswith("https://"):
            raise ValueError("base_url must use https://")
        return value


class AppConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    version: Literal[1]
    mode: Literal["offline", "live"] = "offline"
    providers: dict[ProviderName, ProviderConfig]

    @field_validator("providers")
    @classmethod
    def require_provider(
        cls, value: dict[ProviderName, ProviderConfig]
    ) -> dict[ProviderName, ProviderConfig]:
        if not value:
            raise ValueError("at least one provider is required")
        return value


class Inventory(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    schema_version: Literal[1] = 1
    resources: list[Resource]

    @model_validator(mode="after")
    def unique_resource_keys(self) -> Inventory:
        keys = [(item.provider, item.kind, item.id) for item in self.resources]
        if len(keys) != len(set(keys)):
            raise ValueError("resource identities must be unique by provider, kind and id")
        return self

    def sorted(self) -> Inventory:
        return Inventory(resources=sorted(self.resources, key=lambda r: (r.provider, r.kind, r.id)))


class DriftItem(BaseModel):
    status: Literal["missing", "unexpected", "changed"]
    key: str
    desired: Resource | None = None
    actual: Resource | None = None
    differences: list[str] = Field(default_factory=list)


class DriftReport(BaseModel):
    schema_version: Literal[1] = 1
    in_sync: bool
    summary: dict[str, int]
    items: list[DriftItem]


def load_yaml(path: Path) -> Any:
    try:
        with path.open(encoding="utf-8") as stream:
            return yaml.safe_load(stream)
    except (OSError, yaml.YAMLError) as exc:
        raise ConfigurationError(f"cannot read YAML {path}: {exc}") from exc


def load_config(path: Path) -> AppConfig:
    try:
        return AppConfig.model_validate(load_yaml(path))
    except ValidationError as exc:
        raise ConfigurationError(f"invalid configuration {path}: {exc}") from exc


def load_inventory(path: Path) -> Inventory:
    try:
        return Inventory.model_validate(load_yaml(path))
    except ValidationError as exc:
        raise ConfigurationError(f"invalid inventory {path}: {exc}") from exc
