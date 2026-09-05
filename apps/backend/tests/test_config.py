"""Runtime configuration is complete and secret-safe."""

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr, ValidationError

from kya_platform.config import Settings
from kya_platform.main import create_app


@pytest.mark.unit
def test_complete_infisical_configuration_is_accepted() -> None:
    settings = Settings(
        infisical_api_url="https://app.infisical.com",
        infisical_client_id="client",
        infisical_client_secret=SecretStr("secret"),
        infisical_project_id="project",
        infisical_environment="staging",
        infisical_secret_path="/",
    )

    assert settings.has_infisical_configuration
    assert "secret" not in repr(settings.infisical_client_secret)


@pytest.mark.unit
def test_partial_infisical_configuration_is_rejected() -> None:
    with pytest.raises(ValidationError, match="must be complete"):
        Settings(_env_file=None, infisical_api_url="https://app.infisical.com")


@pytest.mark.unit
def test_fastapi_lifecycle_wires_configured_infisical_resolver() -> None:
    settings = Settings(
        environment="test",
        infisical_api_url="https://app.infisical.com",
        infisical_client_id="client",
        infisical_client_secret=SecretStr("secret"),
        infisical_project_id="project",
    )
    app = create_app(settings)

    with TestClient(app):
        assert app.state.infisical_secret_resolver is not None

    assert not app.state.is_ready
