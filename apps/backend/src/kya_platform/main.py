"""FastAPI application factory and process entry point."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from kya_platform.api.router import api_router
from kya_platform.config import Settings, get_settings
from kya_platform.observability import (
    CorrelationMiddleware,
    configure_logging,
    install_error_handlers,
)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build an isolated application instance for runtime or tests."""

    resolved_settings = settings or get_settings()
    configure_logging(resolved_settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.is_ready = True
        yield
        app.state.is_ready = False

    application = FastAPI(
        title=resolved_settings.app_name,
        version=resolved_settings.version,
        docs_url="/api/docs" if resolved_settings.environment != "production" else None,
        redoc_url=None,
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )
    application.state.settings = resolved_settings
    application.state.is_ready = False
    application.add_middleware(CorrelationMiddleware)
    install_error_handlers(application)
    application.include_router(api_router, prefix="/api/v1")
    return application


app = create_app()


def run() -> None:
    """Run the local development server."""

    uvicorn.run("kya_platform.main:app", host="0.0.0.0", port=8000, reload=False)  # noqa: S104


__all__ = ["app", "create_app", "run"]
