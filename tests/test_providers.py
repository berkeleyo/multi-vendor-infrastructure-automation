from types import SimpleNamespace
from typing import Any

import httpx
import pytest

from mvia.errors import ConfigurationError, ProviderError
from mvia.http import ApiClient
from mvia.models import ProviderConfig
from mvia.providers.aws import AwsProvider
from mvia.providers.azure import AzureProvider
from mvia.providers.cloudflare import CloudflareProvider
from mvia.providers.palo_alto import PaloAltoProvider


class Paginator:
    def __init__(self, pages: list[dict[str, Any]]) -> None:
        self.pages = pages

    def paginate(self) -> list[dict[str, Any]]:
        return self.pages


class AwsClient:
    def get_paginator(self, name: str) -> Paginator:
        if name == "describe_vpcs":
            return Paginator(
                [
                    {
                        "Vpcs": [
                            {
                                "VpcId": "vpc-1",
                                "CidrBlock": "10.0.0.0/16",
                                "State": "available",
                                "Tags": [{"Key": "Name", "Value": "main"}],
                            }
                        ]
                    }
                ]
            )
        return Paginator(
            [
                {
                    "Subnets": [
                        {
                            "SubnetId": "subnet-1",
                            "VpcId": "vpc-1",
                            "CidrBlock": "10.0.1.0/24",
                            "AvailabilityZone": "eu-west-2a",
                        }
                    ]
                }
            ]
        )


def test_aws_normalization() -> None:
    result = AwsProvider(ProviderConfig(region="eu-west-2"), AwsClient()).discover()
    assert [(item.kind, item.name) for item in result] == [("vpc", "main"), ("subnet", "subnet-1")]


def test_aws_missing_region_and_api_error() -> None:
    with pytest.raises(ConfigurationError, match="requires region"):
        AwsProvider(ProviderConfig(), AwsClient())
    broken = SimpleNamespace(get_paginator=lambda _: (_ for _ in ()).throw(TimeoutError()))
    with pytest.raises(ProviderError, match="TimeoutError"):
        AwsProvider(ProviderConfig(region="eu-west-2"), broken).discover()


def test_azure_normalization() -> None:
    subnet = SimpleNamespace(
        id="/subscriptions/s/resourceGroups/g/providers/Microsoft.Network/virtualNetworks/v/subnets/s",
        name="s",
        address_prefix="10.0.1.0/24",
        address_prefixes=None,
    )
    vnet = SimpleNamespace(
        id="/subscriptions/s/resourceGroups/g/providers/Microsoft.Network/virtualNetworks/v",
        name="v",
        location="uksouth",
        address_space=SimpleNamespace(address_prefixes=["10.0.0.0/16"]),
        subnets=[subnet],
    )
    client = SimpleNamespace(virtual_networks=SimpleNamespace(list_all=lambda: [vnet]))
    result = AzureProvider(ProviderConfig(subscription_id="s"), client).discover()
    assert result[1].attributes["address_prefixes"] == ["10.0.1.0/24"]


def test_azure_missing_subscription_and_malformed_id() -> None:
    with pytest.raises(ConfigurationError, match="subscription_id"):
        AzureProvider(ProviderConfig(), SimpleNamespace())
    vnet = SimpleNamespace(
        id="malformed",
        name="v",
        location="uksouth",
        address_space=SimpleNamespace(address_prefixes=[]),
        subnets=[],
    )
    client = SimpleNamespace(virtual_networks=SimpleNamespace(list_all=lambda: [vnet]))
    with pytest.raises(ProviderError, match="IndexError"):
        AzureProvider(ProviderConfig(subscription_id="s"), client).discover()


class CloudflareApi:
    def cloudflare_pages(self, path: str, params: Any = None) -> Any:
        if path == "/zones":
            return iter([{"id": "z1", "name": "portfolio.example", "status": "active"}])
        return iter(
            [{"id": "d1", "name": "www.portfolio.example", "type": "A", "content": "192.0.2.1"}]
        )


def test_cloudflare_normalization() -> None:
    result = CloudflareProvider(ProviderConfig(), CloudflareApi()).discover()  # type: ignore[arg-type]
    assert [item.kind for item in result] == ["zone", "dns_record"]


def test_cloudflare_requires_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CLOUDFLARE_API_TOKEN", raising=False)
    with pytest.raises(ConfigurationError, match="CLOUDFLARE_API_TOKEN"):
        CloudflareProvider(ProviderConfig())


def test_cloudflare_malformed_resource_is_provider_error() -> None:
    api = SimpleNamespace(cloudflare_pages=lambda *args: iter([{"name": "missing-id"}]))
    with pytest.raises(ProviderError, match="KeyError"):
        CloudflareProvider(ProviderConfig(), api).discover()  # type: ignore[arg-type]


def test_http_pagination_and_rate_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(429, headers={"Retry-After": "0"})
        page = int(request.url.params["page"])
        return httpx.Response(
            200,
            json={"success": True, "result": [{"page": page}], "result_info": {"total_pages": 2}},
        )

    api = ApiClient(base_url="https://api.example", headers={}, retries=1)
    api.client = httpx.Client(
        base_url="https://api.example", transport=httpx.MockTransport(handler)
    )
    assert list(api.cloudflare_pages("/items")) == [{"page": 1}, {"page": 2}]


def test_http_timeout_retries_then_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("mvia.http.time.sleep", lambda _: None)
    calls = 0

    def timeout(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.ReadTimeout("slow")

    api = ApiClient(base_url="https://api.example", headers={}, retries=2)
    api.client = httpx.Client(transport=httpx.MockTransport(timeout))
    with pytest.raises(ProviderError, match="after 3 attempts: ReadTimeout"):
        api.get_json("https://api.example/slow")
    assert calls == 3


@pytest.mark.parametrize(
    ("response", "message"),
    [
        (httpx.Response(200, text="not-json"), "malformed JSON"),
        (httpx.Response(200, json=[]), "non-object"),
    ],
)
def test_http_rejects_malformed_json(response: httpx.Response, message: str) -> None:
    api = ApiClient(base_url="https://api.example", headers={}, retries=0)
    api.client = httpx.Client(transport=httpx.MockTransport(lambda request: response))
    with pytest.raises(ProviderError, match=message):
        api.get_json("https://api.example/data")


@pytest.mark.parametrize(
    "payload",
    [
        {"success": False, "result": []},
        {"success": True, "result": {}},
        {"success": True, "result": [], "result_info": []},
        {"success": True, "result": [], "result_info": {"total_pages": "bad"}},
    ],
)
def test_cloudflare_pagination_rejects_malformed_payload(payload: dict[str, Any]) -> None:
    api = ApiClient(base_url="https://api.example", headers={}, retries=0)
    api.client = httpx.Client(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json=payload))
    )
    with pytest.raises(ProviderError):
        list(api.cloudflare_pages("https://api.example/data"))


def test_http_explicit_failure() -> None:
    api = ApiClient(base_url="https://api.example", headers={}, retries=0)
    api.client = httpx.Client(
        base_url="https://api.example", transport=httpx.MockTransport(lambda _: httpx.Response(503))
    )
    with pytest.raises(ProviderError, match="after 1 attempts"):
        api.get_json("/bad")


def test_http_does_not_retry_authentication_failure() -> None:
    calls = 0

    def unauthorized(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(401)

    api = ApiClient(base_url="https://api.example", headers={}, retries=3)
    api.client = httpx.Client(transport=httpx.MockTransport(unauthorized))
    with pytest.raises(ProviderError, match="after 1 attempts"):
        api.get_json("https://api.example/private")
    assert calls == 1


def test_panos_xml_normalization() -> None:
    xml = '<response status="success"><result><address><entry name="web"><ip-netmask>192.0.2.4</ip-netmask><description>web</description></entry></address></result></response>'
    client = SimpleNamespace(get_text=lambda *args, **kwargs: xml)
    result = PaloAltoProvider(ProviderConfig(base_url="https://fw.example"), client).discover()
    assert result[0].attributes["value_type"] == "ip-netmask"


def test_panos_requires_url_and_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PANOS_API_KEY", raising=False)
    with pytest.raises(ConfigurationError, match="base_url"):
        PaloAltoProvider(ProviderConfig())
    with pytest.raises(ConfigurationError, match="PANOS_API_KEY"):
        PaloAltoProvider(ProviderConfig(base_url="https://fw.example"))


@pytest.mark.parametrize(
    ("xml", "message"),
    [
        ("<not-closed>", "ParseError"),
        ('<response status="error"><msg>denied</msg></response>', "unsuccessful"),
    ],
)
def test_panos_rejects_bad_xml_and_api_error(xml: str, message: str) -> None:
    client = SimpleNamespace(get_text=lambda *args, **kwargs: xml)
    with pytest.raises(ProviderError, match=message):
        PaloAltoProvider(ProviderConfig(base_url="https://fw.example"), client).discover()


def test_panos_uses_header_authentication(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PANOS_API_KEY", "sensitive-key")
    provider = PaloAltoProvider(ProviderConfig(base_url="https://fw.example"))
    assert provider.client.client.headers["X-PAN-KEY"] == "sensitive-key"
