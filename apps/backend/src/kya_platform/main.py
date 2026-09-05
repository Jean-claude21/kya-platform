"""FastAPI application factory and process entry point."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
import uvicorn
from fastapi import FastAPI
from pydantic import SecretStr

from kya_platform.api.router import api_router
from kya_platform.api.security import configure_security_runtime
from kya_platform.application.audit import AuditQueryService, AuditWriter
from kya_platform.config import Settings, get_settings
from kya_platform.infrastructure.database.audit import SqlAlchemyAuditRepository
from kya_platform.infrastructure.database.session import create_engine, create_session_factory
from kya_platform.infrastructure.infisical import (
    HttpxInfisicalTransport,
    InfisicalMachineIdentityAdapter,
    InfisicalSecretResolver,
)
from kya_platform.observability import (
    CorrelationMiddleware,
    configure_logging,
    install_error_handlers,
)
from kya_platform.observability.telemetry import TelemetryRuntime


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build an isolated application instance for runtime or tests."""

    resolved_settings = settings or get_settings()
    configure_logging(resolved_settings.log_level)
    telemetry = TelemetryRuntime.create(resolved_settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        infisical_http_client: httpx.AsyncClient | None = None
        database_engine = None
        if resolved_settings.database_url is not None:
            database_engine = create_engine(resolved_settings.database_url)
            audit_repository = SqlAlchemyAuditRepository(create_session_factory(database_engine))
            app.state.audit_queries = AuditQueryService(audit_repository)
            app.state.audit_writer = AuditWriter(audit_repository)
        app.state.infisical_secret_resolver = None
        if resolved_settings.has_infisical_configuration:
            api_url = resolved_settings.infisical_api_url
            client_id = resolved_settings.infisical_client_id
            client_secret = resolved_settings.infisical_client_secret
            project_id = resolved_settings.infisical_project_id
            if api_url is None or client_id is None or client_secret is None or project_id is None:
                raise RuntimeError("validated Infisical configuration is incomplete")
            infisical_http_client = httpx.AsyncClient(timeout=10.0)
            transport = HttpxInfisicalTransport(infisical_http_client)
            authentication = InfisicalMachineIdentityAdapter(
                transport,
                api_url,
                client_id,
                SecretStr(client_secret.get_secret_value()),
                resolved_settings.infisical_organization_slug,
                resolved_settings.infisical_maximum_token_ttl_seconds,
            )
            app.state.infisical_secret_resolver = InfisicalSecretResolver(
                transport,
                authentication,
                project_id,
                resolved_settings.infisical_environment,
                resolved_settings.infisical_secret_path,
            )
        app.state.is_ready = True
        try:
            yield
        finally:
            app.state.is_ready = False
            if infisical_http_client is not None:
                await infisical_http_client.aclose()
            if database_engine is not None:
                await database_engine.dispose()
            telemetry.shutdown()

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
    application.state.audit_queries = None
    application.state.audit_writer = None
    configure_security_runtime(application.state, resolved_settings)
    application.add_middleware(
        CorrelationMiddleware,
        tracer=telemetry.tracer,
        meter=telemetry.meter,
    )
    install_error_handlers(application)
    application.include_router(api_router, prefix="/api/v1")
    return application


app = create_app()


def run() -> None:
    """Run the local development server."""

    uvicorn.run("kya_platform.main:app", host="0.0.0.0", port=8000, reload=False)  # noqa: S104


__all__ = ["app", "create_app", "run"]
