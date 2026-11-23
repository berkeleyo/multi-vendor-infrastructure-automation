"""Application/service-layer orchestration shared by CLI and REST interfaces."""

from __future__ import annotations

from pathlib import Path

from mvia.drift import compare
from mvia.models import AppConfig, DriftReport, Inventory, load_config, load_inventory
from mvia.providers import create_provider
from mvia.providers.base import Provider


class ApplicationService:
    """Stable orchestration boundary around existing discovery and drift engines."""

    def validate_config(self, path: Path) -> AppConfig:
        return load_config(path)

    def discover(self, path: Path) -> Inventory:
        config = load_config(path)
        return discover_inventory(config, config_dir=path.resolve().parent)

    def drift(self, config_path: Path, desired_path: Path) -> DriftReport:
        config = load_config(config_path)
        actual = discover_inventory(config, config_dir=config_path.resolve().parent)
        desired = load_inventory(desired_path)
        return compare(desired, actual)

    def discover_config(self, config: AppConfig, *, config_dir: Path | None = None) -> Inventory:
        return discover_inventory(config, config_dir=config_dir or Path.cwd())


def discover_inventory(config: AppConfig, *, config_dir: Path) -> Inventory:
    """Preserve existing discovery behavior in a reusable application operation."""
    resources = []
    for name, provider_config in sorted(config.providers.items(), key=lambda item: item[0].value):
        if not provider_config.enabled:
            continue
        resolved = provider_config
        if provider_config.fixture and not provider_config.fixture.is_absolute():
            resolved = provider_config.model_copy(
                update={"fixture": config_dir / provider_config.fixture}
            )
        provider: Provider = create_provider(name, resolved, offline=config.mode == "offline")
        resources.extend(provider.discover())
    return Inventory(resources=resources).sorted()


def discover_fixture(
    config_path: Path, desired_path: Path | None = None
) -> DriftReport | Inventory:
    """Small compatibility helper for interface integration tests."""
    service = ApplicationService()
    if desired_path is not None:
        return service.drift(config_path, desired_path)
    return service.discover(config_path)
