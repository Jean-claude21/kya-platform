"""Builtin release downloads are stable and independently verifiable."""

import hashlib

from fastapi.testclient import TestClient


def test_design_system_release_is_downloadable_with_immutable_headers(
    client: TestClient,
) -> None:
    response = client.get("/api/v1/releases/kya-design-system/0.1.1/package")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    assert response.headers["cache-control"] == "public, max-age=31536000, immutable"
    assert response.headers["digest"] == (
        "sha-256=0d85fbe28422c84b33daa5ef397b4b8e3a5c3469c265ad10c5ab5d01dba471a6"
    )
    assert hashlib.sha256(response.content).hexdigest() == response.headers["digest"].removeprefix(
        "sha-256="
    )


def test_current_design_system_release_is_downloadable(client: TestClient) -> None:
    response = client.get("/api/v1/releases/kya-design-system/0.1.2/package")

    assert response.status_code == 200
    assert response.headers["digest"] == (
        "sha-256=3bad82faf929f0f55aa15234df82807f0d70a5c5742406b08c6770b803c3db08"
    )
    assert response.headers["content-disposition"] == (
        'attachment; filename="kya-design-system-0.1.2.zip"'
    )


def test_unknown_builtin_release_is_not_disclosed(client: TestClient) -> None:
    response = client.get("/api/v1/releases/kya-design-system/9.9.9/package")

    assert response.status_code == 404
