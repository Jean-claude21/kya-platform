"""Browser mutation requests must survive the CORS preflight."""

import pytest
from fastapi.testclient import TestClient

from kya_platform.config import Settings
from kya_platform.main import create_app

WEB_ORIGIN = "https://kya-platform.vttlife.com"


@pytest.mark.security
def test_browser_preflight_allows_governed_mutation_headers() -> None:
    app = create_app(
        Settings(
            _env_file=None,
            environment="test",
            cors_allowed_origins=(WEB_ORIGIN,),
        )
    )

    with TestClient(app) as client:
        response = client.options(
            "/api/v1/proposals/019914b2-1a40-7000-8000-0000000000c1/approvals",
            headers={
                "Origin": WEB_ORIGIN,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": (
                    "authorization,content-type,idempotency-key,x-kya-unit-id,x-kya-workspace-id"
                ),
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == WEB_ORIGIN
    allowed_headers = response.headers["access-control-allow-headers"].lower()
    for header in (
        "authorization",
        "content-type",
        "idempotency-key",
        "x-kya-unit-id",
        "x-kya-workspace-id",
    ):
        assert header in allowed_headers
