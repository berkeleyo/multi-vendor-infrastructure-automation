import httpx
import pytest
from pydantic import ValidationError

from mvia.diagnostics.http import HTTPDiagnostic
from mvia.diagnostics.models import DNSRequest, HTTPRequest, TLSRequest
from mvia.diagnostics.safety import is_blocked_ip, validate_hostname, validate_url


@pytest.mark.parametrize(
    "address",
    [
        "127.0.0.1",
        "10.0.0.1",
        "172.16.0.1",
        "192.168.0.1",
        "169.254.169.254",
        "::1",
        "fc00::1",
        "fe80::1",
    ],
)
def test_ssrf_ip_blocks(address: str) -> None:
    assert is_blocked_ip(address)


def test_malformed_hostname_is_rejected() -> None:
    with pytest.raises(ValueError):
        validate_hostname("bad host")


def test_ip_literal_url_is_rejected() -> None:
    with pytest.raises(ValueError):
        validate_url("https://127.0.0.1/health")


def test_http_diagnostic_filters_sensitive_headers(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={
                "Content-Type": "text/plain",
                "Set-Cookie": "secret=value",
                "Authorization": "Bearer secret",
                "Cache-Control": "no-store",
            },
        )

    monkeypatch.setattr(
        "mvia.diagnostics.safety.socket.getaddrinfo",
        lambda *args, **kwargs: [(2, 1, 6, "", ("8.8.8.8", 0))],
    )

    diagnostic = HTTPDiagnostic(client=httpx.Client(transport=httpx.MockTransport(handler)))
    result = diagnostic.run(HTTPRequest(url="https://service.example/health"))
    assert result.http_status == 200
    assert "set-cookie" not in result.headers
    assert "authorization" not in result.headers
    assert "content-type" in result.headers


def test_http_redirect_limit_is_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"Location": "https://service.example/next"})

    monkeypatch.setattr(
        "mvia.diagnostics.safety.socket.getaddrinfo",
        lambda *args, **kwargs: [(2, 1, 6, "", ("8.8.8.8", 0))],
    )

    diagnostic = HTTPDiagnostic(
        redirect_limit=1, client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    result = diagnostic.run(HTTPRequest(url="https://service.example/start"))
    assert result.errors == ["redirect limit exceeded"]


def test_diagnostic_request_models_reject_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        DNSRequest(hostname="service.example", record_types=["A"], allow_private=True)
    with pytest.raises(ValidationError):
        TLSRequest(hostname="service.example", port=70000)
