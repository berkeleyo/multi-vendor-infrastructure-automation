from pathlib import Path
from types import SimpleNamespace

import dns.resolver
import pytest

from mvia.api.app import app
from mvia.application import ApplicationService
from mvia.diagnostics.dns import DNSDiagnostic
from mvia.diagnostics.models import DNSRequest, TLSRequest
from mvia.diagnostics.tls import TLSDiagnostic
from mvia.errors import ConfigurationError


def test_dns_success_and_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    diagnostic = DNSDiagnostic()

    class Answer:
        rrset = SimpleNamespace(ttl=60)

        def __iter__(self) -> object:
            return iter(["192.0.2.10"])

    answer = Answer()

    def resolve(*args: object, **kwargs: object) -> object:
        return answer

    monkeypatch.setattr(diagnostic.resolver, "resolve", resolve)
    monkeypatch.setattr("mvia.diagnostics.dns.resolve_public_addresses", lambda _: ["192.0.2.10"])
    result = diagnostic.run(DNSRequest(hostname="service.example", record_types=["A"]))
    assert result.status.value == "ok"
    assert result.records[0].value == "192.0.2.10"


def test_dns_nxdomain_and_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    diagnostic = DNSDiagnostic()

    def no_domain(*args: object, **kwargs: object) -> object:
        raise dns.resolver.NXDOMAIN()

    monkeypatch.setattr(diagnostic.resolver, "resolve", no_domain)
    monkeypatch.setattr("mvia.diagnostics.dns.resolve_public_addresses", lambda _: ["192.0.2.10"])
    result = diagnostic.run(DNSRequest(hostname="service.example", record_types=["A", "AAAA"]))
    assert result.status.value == "error"
    assert len(result.errors) == 2


def test_tls_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("mvia.diagnostics.tls.resolve_public_addresses", lambda _: ["192.0.2.10"])

    def timeout(*args: object, **kwargs: object) -> object:
        raise TimeoutError()

    monkeypatch.setattr("mvia.diagnostics.tls.socket.create_connection", timeout)
    result = TLSDiagnostic(timeout=0.1).run(TLSRequest(hostname="service.example", port=443))
    assert result.handshake_success is False
    assert "timeout" in result.errors[0].lower()


def test_application_service_validation_and_drift() -> None:
    root = Path(__file__).parents[1]
    service = ApplicationService()
    config = service.validate_config(root / "examples/offline.yaml")
    assert len(config.providers) == 4
    inventory = service.discover(root / "examples/offline.yaml")
    assert len(inventory.resources) == 6
    report = service.drift(root / "examples/offline.yaml", root / "examples/desired.yaml")
    assert report.in_sync is True


def test_service_missing_config_is_configuration_error(tmp_path: Path) -> None:
    missing = tmp_path / "does-not-exist-mvia.yaml"
    with pytest.raises(ConfigurationError):
        ApplicationService().validate_config(missing)


def test_api_malformed_dns_request_returns_422() -> None:
    from fastapi.testclient import TestClient

    client = TestClient(app)
    response = client.post(
        "/api/v1/diagnostics/dns", json={"hostname": "bad host", "record_types": ["A"]}
    )
    assert response.status_code == 422


def test_api_http_request_with_unsupported_scheme_returns_error() -> None:
    from fastapi.testclient import TestClient

    client = TestClient(app)
    response = client.post("/api/v1/diagnostics/http", json={"url": "file:///tmp/test"})
    assert response.status_code == 422
    assert response.headers["X-Request-ID"]
