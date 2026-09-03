"""Validated, secret-safe application configuration."""

from functools import lru_cache
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


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


@lru_cache
def get_settings() -> Settings:
    """Return one immutable configuration view per process."""

    return Settings()
