from pathlib import Path

from mvia.models import AppConfig, Inventory
from mvia.providers import create_provider


def discover(config: AppConfig, *, config_dir: Path) -> Inventory:
    resources = []
    for name, provider_config in sorted(config.providers.items()):
        if not provider_config.enabled:
            continue
        if provider_config.fixture and not provider_config.fixture.is_absolute():
            provider_config = provider_config.model_copy(
                update={"fixture": config_dir / provider_config.fixture}
            )
        provider = create_provider(name, provider_config, offline=config.mode == "offline")
        resources.extend(provider.discover())
    return Inventory(resources=resources).sorted()
