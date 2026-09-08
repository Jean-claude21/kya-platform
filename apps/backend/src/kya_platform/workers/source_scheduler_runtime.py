"""Dedicated process entry point for durable source scheduling."""

import asyncio

from kya_platform.application.source_lifecycle import SourceLifecycleService
from kya_platform.config import get_settings
from kya_platform.infrastructure.database.session import create_engine, create_session_factory
from kya_platform.infrastructure.database.source_lifecycle import (
    SqlAlchemySourceLifecycleRepository,
)
from kya_platform.workers.source_scheduler import SourceScheduler


async def serve() -> None:
    settings = get_settings()
    if settings.database_url is None:
        raise RuntimeError("source scheduler database configuration is incomplete")
    engine = create_engine(settings.database_url)
    sessions = create_session_factory(engine)
    scheduler = SourceScheduler(
        SourceLifecycleService(SqlAlchemySourceLifecycleRepository(sessions))
    )
    try:
        await scheduler.run_forever(asyncio.Event())
    finally:
        await engine.dispose()


def run() -> None:
    asyncio.run(serve())


__all__ = ["run", "serve"]
