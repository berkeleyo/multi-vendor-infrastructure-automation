import os

from mvia.errors import ConfigurationError, ProviderError
from mvia.http import ApiClient
from mvia.models import ProviderConfig, ProviderName, Resource
from mvia.providers.base import Provider


class CloudflareProvider(Provider):
    """Discover zones and DNS records using Cloudflare API v4."""

    def __init__(self, config: ProviderConfig, api: ApiClient | None = None) -> None:
        token = os.getenv("CLOUDFLARE_API_TOKEN")
        if api is None and not token:
            raise ConfigurationError("CLOUDFLARE_API_TOKEN is required for Cloudflare live mode")
        self.api = api or ApiClient(
            base_url=config.base_url or "https://api.cloudflare.com/client/v4",
            headers={"Authorization": f"Bearer {token}"},
            verify=config.verify_tls,
        )
        self.zone_ids = config.zone_ids

    def discover(self) -> list[Resource]:
        try:
            resources: list[Resource] = []
            zones = list(self.api.cloudflare_pages("/zones"))
            selected = [zone for zone in zones if not self.zone_ids or zone["id"] in self.zone_ids]
            if set(self.zone_ids).difference(zone["id"] for zone in selected):
                raise ProviderError("one or more requested Cloudflare zones were not returned")
            for zone in selected:
                resources.append(
                    Resource(
                        provider=ProviderName.CLOUDFLARE,
                        kind="zone",
                        id=zone["id"],
                        name=zone["name"],
                        attributes={
                            "status": zone.get("status"),
                            "paused": zone.get("paused", False),
                        },
                    )
                )
                for record in self.api.cloudflare_pages(f"/zones/{zone['id']}/dns_records"):
                    resources.append(
                        Resource(
                            provider=ProviderName.CLOUDFLARE,
                            kind="dns_record",
                            id=record["id"],
                            name=record["name"],
                            attributes={
                                "zone_id": zone["id"],
                                "type": record["type"],
                                "content": record["content"],
                                "proxied": record.get("proxied", False),
                                "ttl": record.get("ttl"),
                            },
                        )
                    )
            return resources
        except ProviderError:
            raise
        except Exception as exc:
            raise ProviderError(f"Cloudflare discovery failed: {type(exc).__name__}") from exc
