"""Dedicated runtime for the governed KYA web capture worker."""

import asyncio
from datetime import UTC, datetime

import httpx
from pydantic import SecretStr

from kya_platform.application.data import DataService
from kya_platform.config import Settings, get_settings
from kya_platform.connectors.web_capture import WebCaptureConnector
from kya_platform.connectors.web_capture.client import HttpResourceFetcher
from kya_platform.connectors.web_capture.storage import S3ImmutableObjectStore, S3StorageConfig
from kya_platform.infrastructure.database.data import SqlAlchemyDataRepository
from kya_platform.infrastructure.database.session import create_engine, create_session_factory
from kya_platform.infrastructure.infisical import (
    HttpxInfisicalTransport,
    InfisicalMachineIdentityAdapter,
    InfisicalSecretResolver,
)
from kya_platform.infrastructure.workers import DatabaseOutboxQueue
from kya_platform.workers.runner import WorkerRunner
from kya_platform.workers.web_capture import WebCaptureWorker

_STORAGE_SECRET_KEYS = (
    "KYA_OBJECT_STORAGE_ENDPOINT_URL",
    "KYA_OBJECT_STORAGE_REGION",
    "KYA_OBJECT_STORAGE_BUCKET",
    "KYA_OBJECT_STORAGE_ACCESS_KEY_ID",
    "KYA_OBJECT_STORAGE_SECRET_ACCESS_KEY",
)


async def _resolve_storage_config(
    settings: Settings, resolver: InfisicalSecretResolver | None = None
) -> S3StorageConfig:
    inline = (
        settings.object_storage_endpoint_url,
        settings.object_storage_region,
        settings.object_storage_bucket,
        settings.object_storage_access_key_id,
        settings.object_storage_secret_access_key,
    )
    if all(inline):
        assert settings.object_storage_endpoint_url is not None
        assert settings.object_storage_region is not None
        assert settings.object_storage_bucket is not None
        assert settings.object_storage_access_key_id is not None
        assert settings.object_storage_secret_access_key is not None
        return S3StorageConfig(
            settings.object_storage_endpoint_url,
            settings.object_storage_region,
            settings.object_storage_bucket,
            settings.object_storage_access_key_id,
            settings.object_storage_secret_access_key,
        )

    client: httpx.AsyncClient | None = None
    if resolver is None:
        if not settings.has_infisical_configuration:
            raise RuntimeError("object storage configuration is unavailable")
        assert settings.infisical_api_url is not None
        assert settings.infisical_client_id is not None
        assert settings.infisical_client_secret is not None
        assert settings.infisical_project_id is not None
        client = httpx.AsyncClient(timeout=10.0)
        transport = HttpxInfisicalTransport(client)
        resolver = InfisicalSecretResolver(
            transport,
            InfisicalMachineIdentityAdapter(
                transport,
                settings.infisical_api_url,
                settings.infisical_client_id,
                settings.infisical_client_secret,
                settings.infisical_organization_slug,
                settings.infisical_maximum_token_ttl_seconds,
            ),
            settings.infisical_project_id,
            settings.infisical_environment,
            settings.infisical_secret_path,
        )
    try:
        instant = datetime.now(UTC)
        resolved = await asyncio.gather(
            *(resolver.resolve(key, at=instant) for key in _STORAGE_SECRET_KEYS)
        )
    finally:
        if client is not None:
            await client.aclose()
    values = {item.key_name: item.value.get_secret_value() for item in resolved}
    return S3StorageConfig(
        values["KYA_OBJECT_STORAGE_ENDPOINT_URL"],
        values["KYA_OBJECT_STORAGE_REGION"],
        values["KYA_OBJECT_STORAGE_BUCKET"],
        SecretStr(values["KYA_OBJECT_STORAGE_ACCESS_KEY_ID"]),
        SecretStr(values["KYA_OBJECT_STORAGE_SECRET_ACCESS_KEY"]),
    )


async def serve() -> None:
    settings = get_settings()
    if not settings.has_web_capture_configuration:
        raise RuntimeError("web capture worker configuration is incomplete")
    assert settings.database_url is not None
    storage_config = await _resolve_storage_config(settings)
    engine = create_engine(settings.database_url)
    sessions = create_session_factory(engine)
    data = DataService(SqlAlchemyDataRepository(sessions))
    handler = WebCaptureWorker(
        data=data,
        connector=WebCaptureConnector(HttpResourceFetcher()),
        storage=S3ImmutableObjectStore(storage_config),
    )
    runner = WorkerRunner(
        queue=DatabaseOutboxQueue(sessions, topics=frozenset({"kya.data.run.started.v1"})),
        handlers={"kya.data.run.started.v1": handler.handle},
        owner="web-capture-worker",
        batch_size=5,
    )
    try:
        await runner.run_forever(asyncio.Event())
    finally:
        await engine.dispose()


def run() -> None:
    asyncio.run(serve())


__all__ = ["run", "serve"]
