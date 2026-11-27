from collections.abc import Iterator
from unittest.mock import MagicMock

import httpx
import pytest
from pydantic import ValidationError

from mvia.diagnostics.http import HTTPDiagnostic
from mvia.diagnostics.models import DNSRequest, HTTPRequest, TLSRequest
from mvia.diagnostics.safety import is_blocked_ip, validate_hostname, validate_url
from mvia.diagnostics.tls import TLSDiagnostic


@pytest.mark.parametrize(
    "address",
    [
        "127.0.0.1",
        "10.0.0.1",
        "172.16.0.1",
        "192.168.0.1",
        "100.64.0.1",
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


def test_http_connects_to_validated_address_and_keeps_host_and_sni(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    names: list[str] = []

    def resolve(host: str) -> list[str]:
        names.append(host)
        return ["2606:4700:4700::1111"]

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "2606:4700:4700::1111"
        assert request.url.port == 8443
        assert request.headers["Host"] == f"{names[-1]}:8443"
        assert request.extensions["sni_hostname"] == names[-1]
        if request.url.path == "/start":
            return httpx.Response(302, headers={"Location": "https://other.example:8443/end"})
        return httpx.Response(200)

    monkeypatch.setattr("mvia.diagnostics.http.resolve_public_addresses", resolve)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = HTTPDiagnostic(client=client).run(
            HTTPRequest(url="https://service.example:8443/start")
        )
    assert names == ["service.example", "other.example"]
    assert result.final_url == "https://other.example:8443/end"
    assert result.http_status == 200


def test_http_closes_stream_at_size_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    class Stream(httpx.SyncByteStream):
        closed = False

        def __iter__(self) -> Iterator[bytes]:
            yield b"abcd"
            yield b"efgh"
            pytest.fail("body was read after reaching the size limit")

        def close(self) -> None:
            self.closed = True

    stream = Stream()
    monkeypatch.setattr("mvia.diagnostics.http.resolve_public_addresses", lambda _: ["8.8.8.8"])
    with httpx.Client(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, stream=stream))
    ) as client:
        result = HTTPDiagnostic(response_size_limit=5, client=client).run(
            HTTPRequest(url="https://service.example", method="GET")
        )
    assert result.errors == ["response exceeds maximum size"]
    assert stream.closed


def test_tls_verified_handshake_uses_address_and_reports_certificate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connect = MagicMock()
    context = MagicMock()
    peer = context.wrap_socket.return_value.__enter__.return_value
    peer.getpeercert.return_value = {"subjectAltName": (("DNS", "service.example"),)}
    peer.version.return_value = "TLSv1.3"
    peer.cipher.return_value = ("TLS_AES_256_GCM_SHA384", "TLSv1.3", 256)
    monkeypatch.setattr("mvia.diagnostics.tls.resolve_public_addresses", lambda _: ["8.8.8.8"])
    monkeypatch.setattr("mvia.diagnostics.tls.socket.create_connection", connect)
    monkeypatch.setattr("mvia.diagnostics.tls.ssl.create_default_context", lambda: context)

    result = TLSDiagnostic().run(TLSRequest(hostname="service.example"))

    assert connect.call_args.args == (("8.8.8.8", 443),)
    assert context.wrap_socket.call_args.kwargs["server_hostname"] == "service.example"
    assert result.handshake_success and result.hostname_valid
    assert result.chain_validation == "valid"
    assert result.san == ["service.example"]
