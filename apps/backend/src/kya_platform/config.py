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
    otel_exporter_otlp_endpoint: str | None = None
    otel_exporter_otlp_headers: SecretStr | None = None
    otel_metric_export_interval_millis: int = 60_000
    database_url: SecretStr | None = None
    database_migration_url: SecretStr | None = None
    neon_auth_issuer: str | None = None
    neon_auth_jwks_url: str | None = None
    neon_auth_audience: str | None = None
    cors_allowed_origins: tuple[str, ...] = ()
    mcp_allowed_hosts: tuple[str, ...] = ("127.0.0.1:*", "localhost:*")
    mcp_allowed_origins: tuple[str, ...] = ()
    registry_mcp_enabled: bool = False
    registry_mcp_authorization_server_url: str | None = None
    registry_mcp_resource_url: str = "https://mcp.kya-platform.vttlife.com/registry/mcp"
    oauth_broker_enabled: bool = False
    oauth_issuer_url: str = "https://api.kya-platform.vttlife.com"
    oauth_consent_url: str = "https://kya-platform.vttlife.com/oauth/consent"
    oauth_client_secret_key: SecretStr | None = None
    oauth_access_token_ttl_seconds: int = 900
    oauth_refresh_token_ttl_seconds: int = 2_592_000
    openfga_api_url: str | None = None
    openfga_api_token: SecretStr | None = None
    openfga_store_id: str | None = None
    openfga_model_id: str | None = None
    bootstrap_owner_email: str | None = None
    bootstrap_claim_code_hash: SecretStr | None = None
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
        if self.otel_exporter_otlp_endpoint is not None:
            endpoint = self.otel_exporter_otlp_endpoint.rstrip("/")
            if not endpoint.startswith(("http://", "https://")):
                raise ValueError("OTLP endpoint must be an absolute HTTP URL")
            self.otel_exporter_otlp_endpoint = endpoint
        if not 1_000 <= self.otel_metric_export_interval_millis <= 3_600_000:
            raise ValueError("OTLP metric export interval must be between 1000 and 3600000 ms")
        openfga = (
            self.openfga_api_url,
            self.openfga_api_token,
            self.openfga_store_id,
            self.openfga_model_id,
        )
        if any(item is not None for item in openfga) and not all(openfga):
            raise ValueError("OpenFGA configuration must be complete")
        if self.openfga_api_url is not None:
            self.openfga_api_url = self.openfga_api_url.rstrip("/")
        self.registry_mcp_resource_url = self.registry_mcp_resource_url.rstrip("/")
        if not self.registry_mcp_resource_url.startswith("https://"):
            raise ValueError("Registry MCP resource URL must use HTTPS")
        if self.registry_mcp_authorization_server_url is not None:
            self.registry_mcp_authorization_server_url = (
                self.registry_mcp_authorization_server_url.rstrip("/")
            )
            if not self.registry_mcp_authorization_server_url.startswith("https://"):
                raise ValueError("Registry MCP authorization server URL must use HTTPS")
        self.oauth_issuer_url = self.oauth_issuer_url.rstrip("/")
        if not self.oauth_issuer_url.startswith("https://"):
            raise ValueError("OAuth issuer URL must use HTTPS")
        if not self.oauth_consent_url.startswith("https://"):
            raise ValueError("OAuth consent URL must use HTTPS")
        if not 300 <= self.oauth_access_token_ttl_seconds <= 3_600:
            raise ValueError("OAuth access token TTL must be between 300 and 3600 seconds")
        if not 3_600 <= self.oauth_refresh_token_ttl_seconds <= 7_776_000:
            raise ValueError("OAuth refresh token TTL must be between 3600 and 7776000 seconds")
        if self.oauth_broker_enabled and (
            self.database_url is None or self.oauth_client_secret_key is None
        ):
            raise ValueError("Enabled OAuth broker requires database and encryption key")
        if self.registry_mcp_enabled:
            registry_requirements = (
                self.database_url,
                self.oauth_broker_enabled,
                self.oauth_client_secret_key,
                self.registry_mcp_authorization_server_url,
                self.neon_auth_issuer,
                self.neon_auth_jwks_url,
                self.neon_auth_audience,
                self.openfga_api_url,
                self.openfga_api_token,
                self.openfga_store_id,
                self.openfga_model_id,
            )
            if not all(registry_requirements):
                raise ValueError("Enabled Registry MCP configuration must be complete")
            if self.registry_mcp_authorization_server_url != self.oauth_issuer_url:
                raise ValueError("Registry MCP authorization server must be the KYA OAuth issuer")
        bootstrap = (self.bootstrap_owner_email, self.bootstrap_claim_code_hash)
        if any(item is not None for item in bootstrap) and not all(bootstrap):
            raise ValueError("Bootstrap owner configuration must be complete")
        if self.bootstrap_owner_email is not None:
            self.bootstrap_owner_email = self.bootstrap_owner_email.strip().casefold()
            if "@" not in self.bootstrap_owner_email:
                raise ValueError("Bootstrap owner email must be valid")
        if self.bootstrap_claim_code_hash is not None:
            digest = self.bootstrap_claim_code_hash.get_secret_value()
            if len(digest) != 64 or any(
                character not in "0123456789abcdef" for character in digest
            ):
                raise ValueError("Bootstrap claim code hash must be a SHA-256 hex digest")
        return self

    @property
    def has_bootstrap_configuration(self) -> bool:
        return self.bootstrap_owner_email is not None

    @property
    def has_infisical_configuration(self) -> bool:
        return self.infisical_api_url is not None

    @property
    def has_registry_mcp_configuration(self) -> bool:
        """Enable the protected Registry only when every fail-closed dependency exists."""

        return self.registry_mcp_enabled and all(
            (
                self.database_url,
                self.oauth_broker_enabled,
                self.oauth_client_secret_key,
                self.registry_mcp_authorization_server_url,
                self.neon_auth_jwks_url,
                self.neon_auth_audience,
                self.openfga_api_url,
                self.openfga_api_token,
                self.openfga_store_id,
                self.openfga_model_id,
            )
        )


@lru_cache
def get_settings() -> Settings:
    """Return one immutable configuration view per process."""

    return Settings(_env_file=_BACKEND_ENV_FILE)
