import json
from pathlib import Path

import pytest

from mvia.cli import run
from mvia.drift import compare
from mvia.errors import ConfigurationError
from mvia.models import Inventory, ProviderName, Resource, load_inventory
from mvia.redaction import redact

ROOT = Path(__file__).parents[1]


def test_offline_discovery_is_deterministic(capsys: pytest.CaptureFixture[str]) -> None:
    args = ["discover", "--config", str(ROOT / "examples/offline.yaml")]
    assert run(args) == 0
    first = capsys.readouterr().out
    assert run(args) == 0
    assert capsys.readouterr().out == first
    payload = json.loads(first)
    assert payload["ok"] is True
    assert len(payload["data"]["resources"]) == 6


def test_drift_in_sync(capsys: pytest.CaptureFixture[str]) -> None:
    assert (
        run(
            [
                "drift",
                "--config",
                str(ROOT / "examples/offline.yaml"),
                "--desired",
                str(ROOT / "examples/desired.yaml"),
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["data"]["in_sync"] is True


def test_drift_changed_and_missing() -> None:
    a = Resource(provider=ProviderName.AWS, kind="vpc", id="vpc-1", name="a")
    b = Resource(provider=ProviderName.AWS, kind="vpc", id="vpc-1", name="b")
    c = Resource(provider=ProviderName.AWS, kind="vpc", id="vpc-2", name="c")
    report = compare(Inventory(resources=[a, c]), Inventory(resources=[b]))
    assert [item.status for item in report.items] == ["changed", "missing"]
    assert report.items[0].differences == ["name"]


def test_invalid_configuration_returns_json(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config = tmp_path / "bad.yaml"
    config.write_text("version: 2\nproviders: {}\n", encoding="utf-8")
    assert run(["validate", "--config", str(config)]) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["error"]["type"] == "ConfigurationError"


def test_redaction_is_recursive() -> None:
    assert redact({"authorization": "Bearer bad", "nested": [{"api_key": "bad"}], "safe": 1}) == {
        "authorization": "[REDACTED]",
        "nested": [{"api_key": "[REDACTED]"}],
        "safe": 1,
    }


def test_redaction_cleans_unstructured_strings() -> None:
    message = "Authorization: Bearer abc.def api_key=super-secret password: bad"
    cleaned = redact(message)
    assert "abc.def" not in cleaned
    assert "super-secret" not in cleaned
    assert "password: bad" not in cleaned


def test_missing_arguments_are_structured_json(capsys: pytest.CaptureFixture[str]) -> None:
    assert run(["discover"]) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert payload["error"]["type"] == "MviaError"


def test_drift_exit_two_and_unexpected_resource(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    desired = tmp_path / "empty.yaml"
    desired.write_text("schema_version: 1\nresources: []\n", encoding="utf-8")
    assert (
        run(
            [
                "drift",
                "--config",
                str(ROOT / "examples/offline.yaml"),
                "--desired",
                str(desired),
            ]
        )
        == 2
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["data"]["summary"]["unexpected"] == 6


def test_duplicate_inventory_identities_are_rejected(tmp_path: Path) -> None:
    inventory = tmp_path / "duplicate.yaml"
    inventory.write_text(
        """schema_version: 1
resources:
  - {provider: aws, kind: vpc, id: vpc-1, name: one}
  - {provider: aws, kind: vpc, id: vpc-1, name: two}
""",
        encoding="utf-8",
    )
    with pytest.raises(ConfigurationError, match="identities must be unique"):
        load_inventory(inventory)


def test_validation_error_does_not_echo_secret(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config = tmp_path / "secret.yaml"
    config.write_text(
        "version: 1\nproviders:\n  aws:\n    api_key: do-not-echo-this\n",
        encoding="utf-8",
    )
    assert run(["validate", "--config", str(config)]) == 1
    assert "do-not-echo-this" not in capsys.readouterr().out


def test_missing_fixture_is_explicit_json(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config = tmp_path / "offline.yaml"
    config.write_text("version: 1\nproviders:\n  aws: {}\n", encoding="utf-8")
    assert run(["discover", "--config", str(config)]) == 1
    payload = json.loads(capsys.readouterr().out)
    assert "requires fixture" in payload["error"]["message"]
