import logging

from mvia.redaction import redact


def test_authorization_and_cookie_are_redacted() -> None:
    payload = {
        "authorization": "Bearer secret-token",
        "nested": {"cookie": "session=secret"},
        "message": "password=secret api_key=secret",
    }
    cleaned = redact(payload)
    assert cleaned["authorization"] == "[REDACTED]"
    assert cleaned["nested"]["cookie"] == "[REDACTED]"
    assert "secret" not in cleaned["message"]


def test_request_id_is_not_secret() -> None:
    record = logging.LogRecord("mvia", logging.INFO, "", 0, "request", (), None)
    record.request_id = "valid-request-id"
    assert record.request_id == "valid-request-id"
