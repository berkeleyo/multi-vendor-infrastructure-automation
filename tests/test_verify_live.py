"""Guardrails for opt-in live discovery; all provider calls remain mocked here."""

import json
from pathlib import Path

import pytest

from mvia.cli import run
from mvia.models import Inventory, ProviderName, Resource


def test_verify_live_requires_opt_in_and_rejects_fixtures(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "config.yaml"
    path.write_text(
        "version: 1\nmode: offline\nproviders:\n  aws:\n    region: eu-west-2\n",
        encoding="utf-8",
    )
    assert run(["verify-live", "--config", str(path), "--provider", "aws"]) == 1
    assert "confirm-read-only" in capsys.readouterr().out
    assert run(
        ["verify-live", "--config", str(path), "--provider", "aws", "--confirm-read-only"]
    ) == 1
    assert "requires mode: live" in capsys.readouterr().out


def test_verify_live_scopes_provider_and_redacts_inventory(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "config.yaml"
    path.write_text(
        "version: 1\nmode: live\nproviders:\n  aws:\n    region: eu-west-2\n"
        "  azure:\n    subscription_id: example\n",
        encoding="utf-8",
    )

    def fake_discover(config: object, *, config_dir: Path) -> Inventory:
        assert list(config.providers) == [ProviderName.AWS]  # type: ignore[attr-defined]
        return Inventory(
            resources=[
                Resource(
                    provider=ProviderName.AWS, kind="vpc", id="secret-resource-id", name="private"
                )
            ]
        )

    monkeypatch.setattr("mvia.cli.discover", fake_discover)
    assert run(
        ["verify-live", "--config", str(path), "--provider", "aws", "--confirm-read-only"]
    ) == 0
    output = capsys.readouterr().out
    payload = json.loads(output)
    assert payload["resource_counts"] == {"vpc": 1}
    assert payload["status"] == "read_only_discovery_completed"
    assert "secret-resource-id" not in output
    assert "azure" not in output


@pytest.mark.parametrize(
    ("provider_yaml", "provider", "failure"),
    [
        ("cloudflare: {}\n", "cloudflare", "explicit zone_ids"),
        ("aws:\n    region: eu-west-2\n    verify_tls: false\n", "aws", "TLS verification"),
        ("aws:\n    region: eu-west-2\n    fixture: data.yaml\n", "aws", "cannot use a fixture"),
        ("azure:\n    enabled: false\n", "azure", "configured and enabled"),
    ],
)
def test_verify_live_rejects_unsafe_scope(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    provider_yaml: str,
    provider: str,
    failure: str,
) -> None:
    path = tmp_path / "config.yaml"
    path.write_text("version: 1\nmode: live\nproviders:\n  " + provider_yaml, encoding="utf-8")
    assert run(
        ["verify-live", "--config", str(path), "--provider", provider, "--confirm-read-only"]
    ) == 1
    assert failure in capsys.readouterr().out
