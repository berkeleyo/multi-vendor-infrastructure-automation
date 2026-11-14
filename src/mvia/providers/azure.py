from typing import Any

from mvia.errors import ConfigurationError, ProviderError
from mvia.models import ProviderConfig, ProviderName, Resource
from mvia.providers.base import Provider


class AzureProvider(Provider):
    """Discover virtual networks and their subnets through Azure Resource Manager."""

    def __init__(self, config: ProviderConfig, client: Any = None) -> None:
        if not config.subscription_id:
            raise ConfigurationError("Azure live mode requires subscription_id")
        if client is None:
            try:
                from azure.identity import DefaultAzureCredential
                from azure.mgmt.network import NetworkManagementClient
            except ImportError as exc:
                raise ConfigurationError("install the 'azure' extra for Azure live mode") from exc
            client = NetworkManagementClient(
                DefaultAzureCredential(),
                config.subscription_id,
                connection_timeout=10,
                read_timeout=30,
                retry_total=3,
            )
        self.client = client

    def discover(self) -> list[Resource]:
        resources: list[Resource] = []
        try:
            for vnet in self.client.virtual_networks.list_all():
                prefixes = list(getattr(vnet.address_space, "address_prefixes", []) or [])
                resources.append(
                    Resource(
                        provider=ProviderName.AZURE,
                        kind="virtual_network",
                        id=vnet.id,
                        name=vnet.name,
                        location=vnet.location,
                        attributes={
                            "address_prefixes": sorted(prefixes),
                            "resource_group": vnet.id.split("/")[4],
                        },
                    )
                )
                for subnet in vnet.subnets or []:
                    subnet_prefixes = list(getattr(subnet, "address_prefixes", []) or [])
                    if getattr(subnet, "address_prefix", None):
                        subnet_prefixes.append(subnet.address_prefix)
                    resources.append(
                        Resource(
                            provider=ProviderName.AZURE,
                            kind="subnet",
                            id=subnet.id,
                            name=subnet.name,
                            location=vnet.location,
                            attributes={
                                "address_prefixes": sorted(set(subnet_prefixes)),
                                "virtual_network_id": vnet.id,
                            },
                        )
                    )
        except Exception as exc:
            raise ProviderError(f"Azure discovery failed: {type(exc).__name__}") from exc
        return resources
