from typing import Any

from mvia.errors import ConfigurationError, ProviderError
from mvia.models import ProviderConfig, ProviderName, Resource
from mvia.providers.base import Provider


class AwsProvider(Provider):
    """Discover VPCs and subnets via EC2 Describe APIs; never mutates resources."""

    def __init__(self, config: ProviderConfig, client: Any = None) -> None:
        if not config.region:
            raise ConfigurationError("AWS live mode requires region")
        if client is None:
            try:
                import boto3
                from botocore.config import Config
            except ImportError as exc:
                raise ConfigurationError("install the 'aws' extra for AWS live mode") from exc
            client = boto3.client(
                "ec2",
                region_name=config.region,
                config=Config(
                    connect_timeout=10,
                    read_timeout=30,
                    retries={"max_attempts": 4, "mode": "standard"},
                ),
            )
        self.client, self.region = client, config.region

    @staticmethod
    def _name(tags: list[dict[str, str]], fallback: str) -> str:
        return next((tag["Value"] for tag in tags if tag.get("Key") == "Name"), fallback)

    def discover(self) -> list[Resource]:
        resources: list[Resource] = []
        try:
            for page in self.client.get_paginator("describe_vpcs").paginate():
                for item in page.get("Vpcs", []):
                    rid = item["VpcId"]
                    resources.append(
                        Resource(
                            provider=ProviderName.AWS,
                            kind="vpc",
                            id=rid,
                            name=self._name(item.get("Tags", []), rid),
                            location=self.region,
                            attributes={
                                "cidr": item["CidrBlock"],
                                "is_default": item.get("IsDefault", False),
                                "state": item.get("State"),
                            },
                        )
                    )
            for page in self.client.get_paginator("describe_subnets").paginate():
                for item in page.get("Subnets", []):
                    rid = item["SubnetId"]
                    resources.append(
                        Resource(
                            provider=ProviderName.AWS,
                            kind="subnet",
                            id=rid,
                            name=self._name(item.get("Tags", []), rid),
                            location=item.get("AvailabilityZone", self.region),
                            attributes={
                                "cidr": item["CidrBlock"],
                                "vpc_id": item["VpcId"],
                                "available_ip_count": item.get("AvailableIpAddressCount"),
                            },
                        )
                    )
        except Exception as exc:
            raise ProviderError(f"AWS discovery failed: {type(exc).__name__}") from exc
        return resources
