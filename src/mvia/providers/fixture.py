from pathlib import Path

from pydantic import ValidationError

from mvia.errors import ConfigurationError
from mvia.models import Inventory, ProviderConfig, ProviderName, Resource, load_yaml
from mvia.providers.base import Provider


class FixtureProvider(Provider):
    def __init__(self, name: ProviderName, config: ProviderConfig) -> None:
        self.name, self.config = name, config

    def discover(self) -> list[Resource]:
        if self.config.fixture is None:
            raise ConfigurationError(f"offline provider {self.name} requires fixture")
        path = Path(self.config.fixture)
        try:
            inventory = Inventory.model_validate(load_yaml(path))
        except ValidationError as exc:
            raise ConfigurationError(f"invalid fixture {path}: {exc}") from exc
        wrong = [item for item in inventory.resources if item.provider != self.name]
        if wrong:
            raise ConfigurationError(f"fixture {path} contains resources for another provider")
        return inventory.resources
