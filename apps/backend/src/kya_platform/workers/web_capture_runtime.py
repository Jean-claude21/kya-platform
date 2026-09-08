"""Dedicated runtime for the governed KYA web capture worker."""

import asyncio

from kya_platform.application.data import DataService
from kya_platform.config import get_settings
from kya_platform.connectors.web_capture import WebCaptureConnector
from kya_platform.connectors.web_capture.client import HttpResourceFetcher
from kya_platform.connectors.web_capture.storage import S3ImmutableObjectStore, S3StorageConfig
from kya_platform.infrastructure.database.data import SqlAlchemyDataRepository
from kya_platform.infrastructure.database.session import create_engine, create_session_factory
from kya_platform.infrastructure.workers import DatabaseOutboxQueue
from kya_platform.workers.runner import WorkerRunner
from kya_platform.workers.web_capture import WebCaptureWorker


async def serve() -> None:
    settings = get_settings()
    if not settings.has_web_capture_configuration:
        raise RuntimeError("web capture worker configuration is incomplete")
    assert settings.database_url is not None
    assert settings.object_storage_endpoint_url is not None
    assert settings.object_storage_region is not None
    assert settings.object_storage_bucket is not None
    assert settings.object_storage_access_key_id is not None
    assert settings.object_storage_secret_access_key is not None
    engine = create_engine(settings.database_url)
    sessions = create_session_factory(engine)
    data = DataService(SqlAlchemyDataRepository(sessions))
    handler = WebCaptureWorker(
        data=data,
        connector=WebCaptureConnector(HttpResourceFetcher()),
        storage=S3ImmutableObjectStore(
            S3StorageConfig(
                endpoint_url=settings.object_storage_endpoint_url,
                region=settings.object_storage_region,
                bucket=settings.object_storage_bucket,
                access_key_id=settings.object_storage_access_key_id,
                secret_access_key=settings.object_storage_secret_access_key,
            )
        ),
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
