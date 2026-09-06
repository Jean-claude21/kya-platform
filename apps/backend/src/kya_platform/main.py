"""FastAPI application factory and process entry point."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from mcp.server.transport_security import TransportSecuritySettings
from pydantic import SecretStr
from starlette.routing import Route
from starlette.types import ASGIApp, Receive, Scope, Send

from kya_platform.api.router import api_router
from kya_platform.api.security import configure_security_runtime
from kya_platform.application.artifact_registry import ArtifactRegistryService
from kya_platform.application.audit import AuditQueryService, AuditWriter
from kya_platform.bootstrap import BootstrapService
from kya_platform.config import Settings, get_settings
from kya_platform.infrastructure.database.artifact_registry import SqlAlchemyArtifactRegistry
from kya_platform.infrastructure.database.audit import SqlAlchemyAuditRepository
from kya_platform.infrastructure.database.bootstrap import SqlAlchemyBootstrapClaimRepository
from kya_platform.infrastructure.database.identity import SqlAlchemyIdentityMapping
from kya_platform.infrastructure.database.session import create_engine, create_session_factory
from kya_platform.infrastructure.infisical import (
    HttpxInfisicalTransport,
    InfisicalMachineIdentityAdapter,
    InfisicalSecretResolver,
)
from kya_platform.infrastructure.openfga import OpenFgaHttpAdapter
from kya_platform.mcp.bootstrap import create_bootstrap_server
from kya_platform.observability import (
    CorrelationMiddleware,
    configure_logging,
    install_error_handlers,
)
from kya_platform.observability.telemetry import TelemetryRuntime


class CanonicalMcpEndpoint:
    """Serve the exact connector URL without relying on redirect support."""

    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        inner_scope = dict(scope)
        inner_scope["root_path"] = f"{scope.get('root_path', '')}/mcp"
        inner_scope["path"] = "/"
        inner_scope["raw_path"] = b"/"
        await self._app(inner_scope, receive, send)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build an isolated application instance for runtime or tests."""

    resolved_settings = settings or get_settings()
    configure_logging(resolved_settings.log_level)
    telemetry = TelemetryRuntime.create(resolved_settings)
    bootstrap_mcp = create_bootstrap_server(environment=resolved_settings.environment)
    bootstrap_mcp_app = bootstrap_mcp.streamable_http_app(
        streamable_http_path="/",
        json_response=True,
        stateless_http=True,
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=list(resolved_settings.mcp_allowed_hosts),
            allowed_origins=list(resolved_settings.mcp_allowed_origins),
        ),
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        infisical_http_client: httpx.AsyncClient | None = None
        openfga_http_client: httpx.AsyncClient | None = None
        database_engine = None
        if resolved_settings.database_url is not None:
            database_engine = create_engine(resolved_settings.database_url)
            session_factory = create_session_factory(database_engine)
            audit_repository = SqlAlchemyAuditRepository(session_factory)
            app.state.audit_queries = AuditQueryService(audit_repository)
            app.state.audit_writer = AuditWriter(audit_repository)
            app.state.identity_mapping = SqlAlchemyIdentityMapping(session_factory)
            app.state.bootstrap_claims = SqlAlchemyBootstrapClaimRepository(session_factory)
            app.state.artifact_registry = ArtifactRegistryService(
                SqlAlchemyArtifactRegistry(session_factory)
            )
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
        if resolved_settings.openfga_api_url is not None:
            api_token = resolved_settings.openfga_api_token
            store_id = resolved_settings.openfga_store_id
            model_id = resolved_settings.openfga_model_id
            if api_token is None or store_id is None or model_id is None:
                raise RuntimeError("validated OpenFGA configuration is incomplete")
            openfga_http_client = httpx.AsyncClient(timeout=5.0)
            app.state.authorization = OpenFgaHttpAdapter(
                openfga_http_client,
                api_url=resolved_settings.openfga_api_url,
                api_token=api_token,
                store_id=store_id,
                model_id=model_id,
            )
        claims = app.state.bootstrap_claims
        authorization = app.state.authorization
        if resolved_settings.has_bootstrap_configuration and (
            claims is None or authorization is None
        ):
            raise RuntimeError("bootstrap requires database and OpenFGA configuration")
        if claims is not None:
            app.state.bootstrap_service = BootstrapService(
                repository=claims,
                grant=authorization,
                owner_email=resolved_settings.bootstrap_owner_email,
                claim_code_hash=resolved_settings.bootstrap_claim_code_hash,
            )

        # The MCP SDK's HTTP manager is deliberately single-start. Unit/integration
        # tests reuse one FastAPI instance across several TestClient lifespans, so
        # they exercise the server in-process instead of starting that manager.
        @asynccontextmanager
        async def mcp_lifespan() -> AsyncIterator[None]:
            if resolved_settings.environment == "test":
                yield
                return
            async with bootstrap_mcp_app.router.lifespan_context(bootstrap_mcp_app):
                yield

        async with mcp_lifespan():
            app.state.is_ready = True
            try:
                yield
            finally:
                app.state.is_ready = False
                if infisical_http_client is not None:
                    await infisical_http_client.aclose()
                if openfga_http_client is not None:
                    await openfga_http_client.aclose()
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
    application.state.bootstrap_claims = None
    application.state.bootstrap_service = None
    application.state.artifact_registry = None
    configure_security_runtime(application.state, resolved_settings)
    if resolved_settings.cors_allowed_origins:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=list(resolved_settings.cors_allowed_origins),
            allow_credentials=False,
            allow_methods=["GET", "POST", "OPTIONS"],
            allow_headers=["Authorization", "Content-Type", "X-KYA-Unit-ID"],
        )
    application.add_middleware(
        CorrelationMiddleware,
        tracer=telemetry.tracer,
        meter=telemetry.meter,
    )
    install_error_handlers(application)
    application.include_router(api_router, prefix="/api/v1")
    application.router.routes.append(
        Route("/mcp", CanonicalMcpEndpoint(bootstrap_mcp_app), include_in_schema=False)
    )
    application.mount("/mcp", bootstrap_mcp_app)
    return application


app = create_app()


def run() -> None:
    """Run the local development server."""

    uvicorn.run("kya_platform.main:app", host="0.0.0.0", port=8000, reload=False)  # noqa: S104


__all__ = ["app", "create_app", "run"]
