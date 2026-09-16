"""Runtime configuration is complete and secret-safe."""

import base64
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr, ValidationError

from kya_platform.application.mcp_profiles import McpProfileService
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


@pytest.mark.unit
def test_settings_normalize_otlp_endpoint() -> None:
    settings = Settings(_env_file=None, otel_exporter_otlp_endpoint="https://collector.example/")

    assert settings.otel_exporter_otlp_endpoint == "https://collector.example"


@pytest.mark.unit
def test_settings_reject_non_http_otlp_endpoint() -> None:
    with pytest.raises(ValidationError, match="absolute HTTP URL"):
        Settings(_env_file=None, otel_exporter_otlp_endpoint="collector.internal:4318")


@pytest.mark.unit
def test_bootstrap_configuration_requires_owner_and_sha256_hash() -> None:
    with pytest.raises(ValidationError, match="must be complete"):
        Settings(_env_file=None, bootstrap_owner_email="owner@kya-energy.com")

    with pytest.raises(ValidationError, match="SHA-256"):
        Settings(
            _env_file=None,
            bootstrap_owner_email="owner@kya-energy.com",
            bootstrap_claim_code_hash=SecretStr("not-a-digest"),
        )


@pytest.mark.unit
def test_complete_bootstrap_configuration_is_enabled_and_normalized() -> None:
    settings = Settings(
        _env_file=None,
        bootstrap_owner_email=" Owner@KYA-Energy.com ",
        bootstrap_claim_code_hash=SecretStr("a" * 64),
    )

    assert settings.has_bootstrap_configuration
    assert settings.bootstrap_owner_email == "owner@kya-energy.com"


@pytest.mark.unit
def test_artifact_signing_key_requires_32_base64url_bytes() -> None:
    encoded = base64.urlsafe_b64encode(b"s" * 32).rstrip(b"=").decode()

    settings = Settings(
        _env_file=None,
        artifact_signing_key_id="kya-dev-2026",
        artifact_signing_private_key=SecretStr(encoded),
    )

    assert settings.artifact_signing_private_key is not None
    with pytest.raises(ValidationError, match="encode 32 bytes"):
        Settings(_env_file=None, artifact_signing_private_key=SecretStr("c2hvcnQ"))
    with pytest.raises(ValidationError, match="key id"):
        Settings(_env_file=None, artifact_signing_key_id="invalid/key")


@pytest.mark.unit
def test_github_app_private_key_must_be_base64_encoded_pem() -> None:
    pem = "-----BEGIN RSA PRIVATE KEY-----\r\nfake\r\n-----END RSA PRIVATE KEY-----\r\n"
    encoded = base64.b64encode(pem.encode()).decode()

    settings = Settings(
        _env_file=None,
        github_app_id="123",
        github_app_installation_id="456",
        github_app_private_key=SecretStr(encoded),
        github_proposal_repository="kya-energy/kya-platform",
    )

    assert settings.has_github_proposal_configuration
    assert settings.github_app_private_key is not None
    assert settings.github_app_private_key.get_secret_value() == pem
    with pytest.raises(ValidationError, match="base64-encoded PEM"):
        Settings(
            _env_file=None,
            github_app_id="123",
            github_app_installation_id="456",
            github_app_private_key=SecretStr("not-base64!!"),
            github_proposal_repository="kya-energy/kya-platform",
        )
    with pytest.raises(ValidationError, match="decode to PEM"):
        Settings(
            _env_file=None,
            github_app_id="123",
            github_app_installation_id="456",
            github_app_private_key=SecretStr(base64.b64encode(b"not a key").decode()),
            github_proposal_repository="kya-energy/kya-platform",
        )


@pytest.mark.unit
def test_partial_github_app_configuration_is_rejected() -> None:
    with pytest.raises(ValidationError, match="must be complete"):
        Settings(_env_file=None, github_app_id="123")


@pytest.mark.unit
def test_database_and_signing_key_enable_governed_publication_runtime() -> None:
    encoded = base64.urlsafe_b64encode(b"s" * 32).rstrip(b"=").decode()
    settings = Settings(
        _env_file=None,
        environment="test",
        database_url=SecretStr("postgresql://user:password@db.example/neondb"),
        artifact_signing_private_key=SecretStr(encoded),
    )
    app = create_app(settings)

    with TestClient(app):
        assert app.state.publication_service is not None
        assert app.state.attestation_repository is not None


@pytest.mark.unit
def test_preview_startup_synchronizes_system_mcp_profiles(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    synchronize = AsyncMock()
    monkeypatch.setattr(McpProfileService, "synchronize", synchronize)
    settings = Settings(
        _env_file=None,
        environment="preview",
        database_url=SecretStr("postgresql://user:password@db.example/neondb"),
    )

    with TestClient(create_app(settings)):
        synchronize.assert_awaited_once()
