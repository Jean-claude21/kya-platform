"""Contract tests for correlation, typed errors and secret-safe logs."""

import json
import logging
from uuid import UUID

import pytest
from fastapi import FastAPI, Query
from fastapi.testclient import TestClient
from pydantic import SecretStr

from kya_platform.observability import ApiError, current_correlation_id
from kya_platform.observability.logging import REDACTED, SafeJsonFormatter, redact


@pytest.mark.contract
def test_generates_and_returns_a_correlation_id(client: TestClient) -> None:
    response = client.get("/api/v1/health/live")

    correlation_id = response.headers["X-Correlation-ID"]
    assert str(UUID(correlation_id)) == correlation_id


@pytest.mark.contract
def test_preserves_a_valid_correlation_id(client: TestClient) -> None:
    supplied = "019914b2-1a40-7000-8000-000000000021"

    response = client.get("/api/v1/health/live", headers={"X-Correlation-ID": supplied})

    assert response.headers["X-Correlation-ID"] == supplied


@pytest.mark.security
def test_replaces_an_untrusted_correlation_id(client: TestClient) -> None:
    response = client.get(
        "/api/v1/health/live",
        headers={"X-Correlation-ID": "injected\nlog-line"},
    )

    assert response.headers["X-Correlation-ID"] != "injected\nlog-line"
    assert str(UUID(response.headers["X-Correlation-ID"])) == response.headers["X-Correlation-ID"]


@pytest.mark.contract
def test_expected_api_error_uses_problem_details(app: FastAPI) -> None:
    async def denied() -> None:
        raise ApiError(403, "workspace_denied", "Accès refusé", "Cet espace n'est pas accessible.")

    app.add_api_route("/api/v1/test-denied", denied)
    with TestClient(app) as client:
        response = client.get("/api/v1/test-denied")

    assert response.status_code == 403
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json() == {
        "type": "https://errors.kya-energy.com/workspace_denied",
        "title": "Accès refusé",
        "status": 403,
        "detail": "Cet espace n'est pas accessible.",
        "instance": "/api/v1/test-denied",
        "code": "workspace_denied",
        "correlation_id": response.headers["X-Correlation-ID"],
    }


@pytest.mark.contract
def test_not_found_is_a_typed_problem(client: TestClient) -> None:
    response = client.get("/api/v1/missing")

    assert response.status_code == 404
    assert response.json()["code"] == "http_404"
    assert response.json()["correlation_id"] == response.headers["X-Correlation-ID"]


@pytest.mark.contract
def test_validation_failure_does_not_echo_input(app: FastAPI) -> None:
    async def validated(value: int = Query()) -> dict[str, int]:
        return {"value": value}

    app.add_api_route("/api/v1/test-validation", validated)
    with TestClient(app) as client:
        response = client.get("/api/v1/test-validation", params={"value": "secret-input"})

    assert response.status_code == 422
    assert response.json()["code"] == "request_validation_failed"
    assert "secret-input" not in response.text


@pytest.mark.security
def test_unexpected_failure_is_generic_to_the_caller(app: FastAPI) -> None:
    async def crashes() -> None:
        raise RuntimeError("database_url=postgresql://user:password@host/database")

    app.add_api_route("/api/v1/test-crash", crashes)
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/api/v1/test-crash")

    assert response.status_code == 500
    assert response.json()["code"] == "internal_error"
    assert "password" not in response.text


@pytest.mark.security
def test_redacts_nested_secrets_and_credentials() -> None:
    raw = {
        "authorization": "Bearer should-never-appear",
        "nested": {
            "client_secret": "secret-value",
            "message": "password=hunter2 token:abc123",
            "database": "postgresql://user:password@db.example/kya",
        },
        "secret_object": SecretStr("hidden"),
    }

    safe = redact(raw)

    serialized = json.dumps(safe)
    assert "should-never-appear" not in serialized
    assert "secret-value" not in serialized
    assert "hunter2" not in serialized
    assert "abc123" not in serialized
    assert "postgresql://user:password@" not in serialized
    assert serialized.count(REDACTED) >= 5


@pytest.mark.security
def test_json_formatter_redacts_message_and_extra_fields() -> None:
    formatter = SafeJsonFormatter()
    record = logging.LogRecord(
        name="test",
        level=logging.ERROR,
        pathname=__file__,
        lineno=1,
        msg="Authorization: Bearer abc.def password=hunter2",
        args=(),
        exc_info=None,
    )
    record.api_key = "live-key"

    formatted = formatter.format(record)

    assert "abc.def" not in formatted
    assert "hunter2" not in formatted
    assert "live-key" not in formatted
    assert json.loads(formatted)["api_key"] == REDACTED


@pytest.mark.unit
def test_correlation_context_is_cleared_after_request(client: TestClient) -> None:
    client.get("/api/v1/health/live")

    assert current_correlation_id() is None
