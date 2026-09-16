"""Health contract tests."""

import pytest
from fastapi.testclient import TestClient


@pytest.mark.unit
@pytest.mark.parametrize("path", ["/api/v1/health/live", "/api/v1/health/ready"])
def test_health_probe_returns_stable_metadata(client: TestClient, path: str) -> None:
    response = client.get(path)

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "KYA Platform API",
        "version": "test-version",
        "environment": "test",
    }


@pytest.mark.contract
def test_openapi_exposes_versioned_health_routes(client: TestClient) -> None:
    response = client.get("/api/openapi.json")

    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/api/v1/health/live" in paths
    assert "/api/v1/health/ready" in paths


@pytest.mark.unit
def test_unknown_route_is_not_found(client: TestClient) -> None:
    response = client.get("/api/v1/unknown")

    assert response.status_code == 404
