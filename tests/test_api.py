from pathlib import Path

from fastapi.testclient import TestClient

from mvia.api.app import app


def test_health_and_provider_capabilities() -> None:
    client = TestClient(app)
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "healthy"

    providers = client.get("/api/v1/providers")
    assert providers.status_code == 200
    assert {item["name"] for item in providers.json()["providers"]} == {
        "aws",
        "azure",
        "cloudflare",
        "palo_alto",
    }


def test_fixture_discovery_and_drift() -> None:
    client = TestClient(app)
    discovery = client.post("/api/v1/discovery")
    assert discovery.status_code == 200
    assert len(discovery.json()["resources"]) == 6

    drift = client.post("/api/v1/drift")
    assert drift.status_code == 200
    assert drift.json()["in_sync"] is True


def test_fixture_routes_ignore_process_cwd(tmp_path: Path) -> None:
    import os

    client = TestClient(app)
    previous = os.getcwd()
    try:
        os.chdir(tmp_path)
        assert client.post("/api/v1/discovery").status_code == 200
        assert client.post("/api/v1/drift").status_code == 200
    finally:
        os.chdir(previous)


def test_request_id_is_preserved_and_returned() -> None:
    client = TestClient(app)
    response = client.post("/api/v1/discovery", headers={"X-Correlation-ID": "valid-request-id"})
    assert response.headers["X-Request-ID"] == "valid-request-id"


def test_invalid_correlation_id_is_replaced() -> None:
    client = TestClient(app)
    response = client.post("/api/v1/discovery", headers={"X-Correlation-ID": "x" * 300})
    assert len(response.headers["X-Request-ID"]) == 32
