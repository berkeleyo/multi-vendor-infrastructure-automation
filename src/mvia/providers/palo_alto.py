import os
from typing import Any

from defusedxml import ElementTree as ET  # type: ignore[import-untyped]

from mvia.errors import ConfigurationError, ProviderError
from mvia.http import ApiClient
from mvia.models import ProviderConfig, ProviderName, Resource
from mvia.providers.base import Provider


class PaloAltoProvider(Provider):
    """Read shared address objects with the PAN-OS XML API (no commit or config writes)."""

    def __init__(self, config: ProviderConfig, client: Any = None) -> None:
        key = os.getenv("PANOS_API_KEY")
        if not config.base_url:
            raise ConfigurationError("Palo Alto live mode requires base_url")
        if client is None and not key:
            raise ConfigurationError("PANOS_API_KEY is required for Palo Alto live mode")
        self.client = client or ApiClient(
            base_url=config.base_url,
            headers={"X-PAN-KEY": key or ""},
            verify=config.verify_tls,
        )

    def discover(self) -> list[Resource]:
        xpath = "/config/shared/address"
        try:
            xml = self.client.get_text(
                "/api/", params={"type": "config", "action": "get", "xpath": xpath}
            )
            root = ET.fromstring(xml)
            if root.get("status") != "success":
                raise ProviderError("PAN-OS API returned an unsuccessful status")
            resources = []
            for entry in root.findall("./result/address/entry"):
                value_node = next(
                    (
                        entry.find(tag)
                        for tag in ("ip-netmask", "ip-range", "fqdn")
                        if entry.find(tag) is not None
                    ),
                    None,
                )
                if value_node is None or value_node.text is None:
                    continue
                resources.append(
                    Resource(
                        provider=ProviderName.PALO_ALTO,
                        kind="address_object",
                        id=entry.get("name", "unknown"),
                        name=entry.get("name", "unknown"),
                        attributes={
                            "value": value_node.text,
                            "value_type": value_node.tag,
                            "description": entry.findtext("description"),
                        },
                    )
                )
            return resources
        except ProviderError:
            raise
        except ET.ParseError as exc:
            raise ProviderError(f"Palo Alto discovery failed: {type(exc).__name__}") from exc
        except Exception as exc:
            raise ProviderError(f"Palo Alto discovery failed: {type(exc).__name__}") from exc
