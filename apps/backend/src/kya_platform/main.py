"""FastAPI application factory and process entry point."""

import base64
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager
from typing import cast

import httpx
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from mcp.server.auth.provider import ProviderTokenVerifier
from mcp.server.auth.routes import create_auth_routes
from mcp.server.auth.settings import AuthSettings, ClientRegistrationOptions, RevocationOptions
from mcp.server.transport_security import TransportSecuritySettings
from pydantic import SecretStr
from starlette.routing import Route
from starlette.types import ASGIApp, Receive, Scope, Send

from kya_platform.api.router import api_router
from kya_platform.api.security import configure_security_runtime
from kya_platform.application.artifact_registry import ArtifactRegistryService
from kya_platform.application.audit import AuditQueryService, AuditWriter
from kya_platform.application.publication import (
    PublicationService,
    PublicationUnitOfWorkFactory,
)
from kya_platform.application.publication.integrity import Ed25519ArtifactSigner
from kya_platform.authorization import AuthorizationService
from kya_platform.bootstrap import BootstrapService
from kya_platform.config import Settings, get_settings
from kya_platform.infrastructure.database.artifact_registry import SqlAlchemyArtifactRegistry
from kya_platform.infrastructure.database.audit import SqlAlchemyAuditRepository
from kya_platform.infrastructure.database.bootstrap import SqlAlchemyBootstrapClaimRepository
from kya_platform.infrastructure.database.identity import SqlAlchemyIdentityMapping
from kya_platform.infrastructure.database.oauth_broker import VALID_SCOPES, OAuthBroker
from kya_platform.infrastructure.database.publication import (
    SqlAlchemyAttestationRepository,
    SqlAlchemyPublicationUnitOfWork,
)
from kya_platform.infrastructure.database.registry_mcp import SqlAlchemyRegistryMcpBackend
from kya_platform.infrastructure.database.session import create_engine, create_session_factory
from kya_platform.infrastructure.infisical import (
    HttpxInfisicalTransport,
    InfisicalMachineIdentityAdapter,
    InfisicalSecretResolver,
)
from kya_platform.infrastructure.openfga import OpenFgaHttpAdapter
from kya_platform.mcp.bootstrap import create_bootstrap_server
from kya_platform.mcp.registry.runtime import (
    StateAuthorizationPort,
    StateRegistryBackend,
)
from kya_platform.mcp.registry.server import create_registry_server
from kya_platform.observability import (
    CorrelationMiddleware,
    configure_logging,
    install_error_handlers,
)
from kya_platform.observability.telemetry import TelemetryRuntime


class CanonicalMcpEndpoint:
    """Serve the exact connector URL without relying on redirect support."""

    def __init__(self, app: ASGIApp, mount_path: str) -> None:
        self._app = app
        self._mount_path = mount_path

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        inner_scope = dict(scope)
        inner_scope["root_path"] = f"{scope.get('root_path', '')}{self._mount_path}"
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
    registry_mcp_app: ASGIApp | None = None
    database_engine = None
    session_factory = None
    oauth_broker: OAuthBroker | None = None
    if resolved_settings.database_url is not None:
        database_engine = create_engine(resolved_settings.database_url)
        session_factory = create_session_factory(database_engine)
        if resolved_settings.oauth_broker_enabled:
            key = resolved_settings.oauth_client_secret_key
            if key is None:
                raise RuntimeError("validated OAuth broker key is missing")
            oauth_broker = OAuthBroker(
                session_factory,
                issuer_url=resolved_settings.oauth_issuer_url,
                resource_url=resolved_settings.registry_mcp_resource_url,
                consent_url=resolved_settings.oauth_consent_url,
                client_secret_key=key.get_secret_value(),
                access_token_ttl_seconds=resolved_settings.oauth_access_token_ttl_seconds,
                refresh_token_ttl_seconds=resolved_settings.oauth_refresh_token_ttl_seconds,
            )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        infisical_http_client: httpx.AsyncClient | None = None
        openfga_http_client: httpx.AsyncClient | None = None
        if session_factory is not None:
            audit_repository = SqlAlchemyAuditRepository(session_factory)
            app.state.audit_queries = AuditQueryService(audit_repository)
            app.state.audit_writer = AuditWriter(audit_repository)
            app.state.identity_mapping = SqlAlchemyIdentityMapping(session_factory)
            app.state.bootstrap_claims = SqlAlchemyBootstrapClaimRepository(session_factory)
            app.state.artifact_registry = ArtifactRegistryService(
                SqlAlchemyArtifactRegistry(session_factory)
            )
            app.state.registry_mcp_backend = SqlAlchemyRegistryMcpBackend(session_factory)
            signing_key = resolved_settings.artifact_signing_private_key
            if signing_key is not None:
                encoded = signing_key.get_secret_value()
                raw_key = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
                signer = Ed25519ArtifactSigner.from_private_key_bytes(
                    resolved_settings.artifact_signing_key_id,
                    raw_key,
                )
                app.state.publication_service = PublicationService(
                    cast(
                        PublicationUnitOfWorkFactory,
                        lambda: SqlAlchemyPublicationUnitOfWork(session_factory, signer),
                    )
                )
                app.state.attestation_repository = SqlAlchemyAttestationRepository(session_factory)
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
            async with AsyncExitStack() as stack:
                await stack.enter_async_context(
                    bootstrap_mcp_app.router.lifespan_context(bootstrap_mcp_app)
                )
                if registry_mcp_app is not None:
                    await stack.enter_async_context(
                        registry_mcp_app.router.lifespan_context(registry_mcp_app)  # type: ignore[attr-defined]
                    )
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
    application.state.publication_service = None
    application.state.attestation_repository = None
    application.state.registry_mcp_backend = None
    application.state.oauth_broker = oauth_broker
    configure_security_runtime(application.state, resolved_settings)
    if resolved_settings.has_registry_mcp_configuration:
        authorization_server_url = resolved_settings.registry_mcp_authorization_server_url
        if oauth_broker is None or authorization_server_url is None:
            raise RuntimeError("validated Registry MCP authentication is incomplete")
        registry_mcp = create_registry_server(
            backend=StateRegistryBackend(application.state),
            authorization=AuthorizationService(StateAuthorizationPort(application.state)),
            token_verifier=ProviderTokenVerifier(oauth_broker),
            issuer_url=authorization_server_url,
            resource_url=resolved_settings.registry_mcp_resource_url,
        )
        registry_mcp_app = registry_mcp.streamable_http_app(
            streamable_http_path="/",
            json_response=True,
            stateless_http=True,
            transport_security=TransportSecuritySettings(
                enable_dns_rebinding_protection=True,
                allowed_hosts=list(resolved_settings.mcp_allowed_hosts),
                allowed_origins=list(resolved_settings.mcp_allowed_origins),
            ),
        )
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
    if oauth_broker is not None:
        oauth_issuer = AuthSettings(
            issuer_url=resolved_settings.oauth_issuer_url,
            resource_server_url=None,
        ).issuer_url
        application.router.routes.extend(
            create_auth_routes(
                provider=oauth_broker,
                issuer_url=oauth_issuer,
                service_documentation_url=None,
                client_registration_options=ClientRegistrationOptions(
                    enabled=True,
                    valid_scopes=sorted(VALID_SCOPES),
                    default_scopes=["catalog:read"],
                ),
                revocation_options=RevocationOptions(enabled=True),
            )
        )
    application.router.routes.append(
        Route(
            "/mcp",
            CanonicalMcpEndpoint(bootstrap_mcp_app, "/mcp"),
            include_in_schema=False,
        )
    )
    application.mount("/mcp", bootstrap_mcp_app)
    if registry_mcp_app is not None:
        metadata_path = "/.well-known/oauth-protected-resource/registry/mcp"
        application.router.routes.append(
            Route(metadata_path, registry_mcp_app, include_in_schema=False)
        )
        application.router.routes.append(
            Route(
                "/registry/mcp",
                CanonicalMcpEndpoint(registry_mcp_app, "/registry/mcp"),
                include_in_schema=False,
            )
        )
        application.router.routes.append(
            Route(
                "/registry/mcp/",
                CanonicalMcpEndpoint(registry_mcp_app, "/registry/mcp"),
                include_in_schema=False,
            )
        )
    return application


app = create_app()


def run() -> None:
    """Run the local development server."""

    uvicorn.run("kya_platform.main:app", host="0.0.0.0", port=8000, reload=False)  # noqa: S104


__all__ = ["app", "create_app", "run"]
