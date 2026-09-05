"""Validated, secret-safe application configuration."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


_BACKEND_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    """Runtime settings that are safe to expose through health metadata."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="KYA_",
        extra="ignore",
    )

    app_name: str = "KYA Platform API"
    environment: Literal["local", "preview", "test", "production"] = "local"
    version: str = "0.0.1"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    database_url: SecretStr | None = None
    database_migration_url: SecretStr | None = None
    neon_auth_issuer: str | None = None
    neon_auth_jwks_url: str | None = None
    neon_auth_audience: str = "kya-platform"
    infisical_api_url: str | None = None
    infisical_client_id: str | None = None
    infisical_client_secret: SecretStr | None = None
    infisical_project_id: str | None = None
    infisical_environment: Literal["dev", "staging", "prod"] = "staging"
    infisical_secret_path: str = "/"  # noqa: S105 -- path, not credential material
    infisical_organization_slug: str | None = None
    infisical_maximum_token_ttl_seconds: int = 900
    deployment_provider: Literal["mock", "dokploy", "coolify"] = "mock"
    neon_project_id: str | None = None
    neon_api_key: SecretStr | None = None
    dokploy_api_url: str | None = None
    dokploy_api_token: SecretStr | None = None
    dokploy_project_id: str | None = None
    dokploy_preview_app_id: str | None = None
    dokploy_staging_app_id: str | None = None
    dokploy_production_app_id: str | None = None
    coolify_api_url: str | None = None
    coolify_api_token: SecretStr | None = None
    coolify_project_uuid: str | None = None
    coolify_server_uuid: str | None = None
    coolify_web_application_name: str = "kya-platform-web"
    coolify_backend_application_name: str = "kya-platform-backend"

    @model_validator(mode="after")
    def validate_infisical_configuration(self) -> Settings:
        required = (
            self.infisical_api_url,
            self.infisical_client_id,
            self.infisical_client_secret,
            self.infisical_project_id,
        )
        if any(item is not None for item in required) and not all(required):
            raise ValueError("Infisical configuration must be complete")
        if not self.infisical_secret_path.startswith("/"):
            raise ValueError("Infisical secret path must start with /")
        if not 1 <= self.infisical_maximum_token_ttl_seconds <= 7_200:
            raise ValueError("Infisical maximum token TTL must be between 1 and 7200 seconds")
        return self

    @property
    def has_infisical_configuration(self) -> bool:
        return self.infisical_api_url is not None


@lru_cache
def get_settings() -> Settings:
    """Return one immutable configuration view per process."""

    return Settings(_env_file=_BACKEND_ENV_FILE)
