"""Late-bound adapters shared by the FastAPI and Registry MCP lifecycles."""

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid7

from mcp.server.mcpserver.exceptions import ToolError
from starlette.datastructures import State

from kya_platform.application.audit import AuditEvent, AuditWriter
from kya_platform.application.content import ContentService
from kya_platform.application.data import DataService
from kya_platform.auth import AuthenticatedIdentity, IdentityMappingPort
from kya_platform.authorization import (
    AuthorizationDecision,
    AuthorizationPort,
    CheckRequest,
    ListObjectsRequest,
)
from kya_platform.mcp.registry.server import RegistryBackend


class StateIdentityMapping:
    """Resolve identities through the database adapter installed at startup."""

    def __init__(self, state: State) -> None:
        self._state = state

    async def resolve_principal_id(self, identity: AuthenticatedIdentity) -> UUID | None:
        mapping: IdentityMappingPort | None = self._state.identity_mapping
        if mapping is None:
            return None
        return await mapping.resolve_principal_id(identity)


class StateAuthorizationPort:
    """Fail closed until OpenFGA is installed in application state."""

    def __init__(self, state: State) -> None:
        self._state = state

    async def check(self, request: CheckRequest) -> AuthorizationDecision:
        authorization: AuthorizationPort | None = self._state.authorization
        if authorization is None:
            return AuthorizationDecision(allowed=False, model_id="unavailable")
        return await authorization.check(request)

    async def list_objects(self, request: ListObjectsRequest) -> Sequence[str]:
        authorization: AuthorizationPort | None = self._state.authorization
        if authorization is None:
            return ()
        return await authorization.list_objects(request)


class StateRegistryBackend:
    """Delegate to Neon only after the lifespan has installed the repository."""

    def __init__(self, state: State) -> None:
        self._state = state

    def _backend(self) -> RegistryBackend:
        backend: RegistryBackend | None = self._state.registry_mcp_backend
        if backend is None:
            raise ToolError("registry_unavailable")
        return backend

    async def search_catalog(self, *args: Any, **kwargs: Any):  # type: ignore[no-untyped-def]
        return await self._backend().search_catalog(*args, **kwargs)

    async def resolve_artifact_id(self, *args: Any, **kwargs: Any):  # type: ignore[no-untyped-def]
        return await self._backend().resolve_artifact_id(*args, **kwargs)

    async def resolve_installation_workspace(self, *args: Any, **kwargs: Any):  # type: ignore[no-untyped-def]
        return await self._backend().resolve_installation_workspace(*args, **kwargs)

    async def resolve_operation_workspace(self, *args: Any, **kwargs: Any):  # type: ignore[no-untyped-def]
        return await self._backend().resolve_operation_workspace(*args, **kwargs)

    async def get_artifact(self, *args: Any, **kwargs: Any):  # type: ignore[no-untyped-def]
        return await self._backend().get_artifact(*args, **kwargs)

    async def list_updates(self, *args: Any, **kwargs: Any):  # type: ignore[no-untyped-def]
        return await self._backend().list_updates(*args, **kwargs)

    async def request_install(self, *args: Any, **kwargs: Any):  # type: ignore[no-untyped-def]
        return await self._backend().request_install(*args, **kwargs)

    async def confirm_installation(self, *args: Any, **kwargs: Any):  # type: ignore[no-untyped-def]
        return await self._backend().confirm_installation(*args, **kwargs)

    async def request_update(self, *args: Any, **kwargs: Any):  # type: ignore[no-untyped-def]
        return await self._backend().request_update(*args, **kwargs)

    async def confirm_update(self, *args: Any, **kwargs: Any):  # type: ignore[no-untyped-def]
        return await self._backend().confirm_update(*args, **kwargs)

    async def manage_installation(self, *args: Any, **kwargs: Any):  # type: ignore[no-untyped-def]
        return await self._backend().manage_installation(*args, **kwargs)

    async def get_operation(self, *args: Any, **kwargs: Any):  # type: ignore[no-untyped-def]
        return await self._backend().get_operation(*args, **kwargs)

    async def publish_candidate(self, *args: Any, **kwargs: Any):  # type: ignore[no-untyped-def]
        return await self._backend().publish_candidate(*args, **kwargs)


class StateDataMcpBackend:
    """Expose only the shared application service installed during lifespan."""

    def __init__(self, state: State) -> None:
        self._state = state

    def _backend(self) -> DataService:
        backend: DataService | None = self._state.data_service
        if backend is None:
            raise ToolError("data_service_unavailable")
        return backend

    def _content(self) -> ContentService:
        backend: ContentService | None = self._state.content_service
        if backend is None:
            raise ToolError("content_service_unavailable")
        return backend

    async def search_assets(self, *args: Any, **kwargs: Any):  # type: ignore[no-untyped-def]
        return await self._backend().search_assets(*args, **kwargs)

    async def get_asset(self, *args: Any, **kwargs: Any):  # type: ignore[no-untyped-def]
        return await self._backend().get_asset(*args, **kwargs)

    async def get_contract(self, *args: Any, **kwargs: Any):  # type: ignore[no-untyped-def]
        return await self._backend().get_contract(*args, **kwargs)

    async def list_snapshots(self, *args: Any, **kwargs: Any):  # type: ignore[no-untyped-def]
        return await self._backend().list_snapshots(*args, **kwargs)

    async def trace_lineage(self, *args: Any, **kwargs: Any):  # type: ignore[no-untyped-def]
        return await self._backend().trace_lineage(*args, **kwargs)

    async def get_pipeline(self, *args: Any, **kwargs: Any):  # type: ignore[no-untyped-def]
        return await self._backend().get_pipeline(*args, **kwargs)

    async def get_run_report(self, *args: Any, **kwargs: Any):  # type: ignore[no-untyped-def]
        return await self._backend().get_run_report(*args, **kwargs)

    async def search_public_content(self, *args: Any, **kwargs: Any):  # type: ignore[no-untyped-def]
        return await self._content().search_public_content(*args, **kwargs)

    async def get_public_excerpt(self, *args: Any, **kwargs: Any):  # type: ignore[no-untyped-def]
        return await self._content().get_public_excerpt(*args, **kwargs)

    async def start_run(self, *args: Any, **kwargs: Any):  # type: ignore[no-untyped-def]
        return await self._backend().start_run(*args, **kwargs)


class StateDataMcpAuditSink:
    """Record MCP decisions in the existing append-only audit trail."""

    def __init__(self, state: State) -> None:
        self._state = state

    def _writer(self) -> AuditWriter:
        writer: AuditWriter | None = self._state.audit_writer
        if writer is None:
            raise ToolError("audit_unavailable")
        return writer

    async def ensure_available(self) -> None:
        self._writer()

    async def record(
        self,
        *,
        actor_id: UUID,
        active_unit: str,
        tool_name: str,
        target_type: str,
        target_id: str,
        decision: str,
        outcome: str,
        correlation_id: UUID,
    ) -> None:
        settings = self._state.settings
        await self._writer().append(
            AuditEvent(
                id=uuid7(),
                occurred_at=datetime.now(UTC),
                actor_id=actor_id,
                actor_context={"active_unit": active_unit, "transport": "mcp"},
                action=f"mcp.{tool_name}",
                target_type=target_type,
                target_id=target_id,
                scope=f"workspace:{active_unit}",
                environment=settings.environment,
                decision=decision,
                outcome=outcome,
                correlation_id=correlation_id,
                metadata={"protocol": "2026-07-28"},
            )
        )


__all__ = [
    "StateAuthorizationPort",
    "StateDataMcpAuditSink",
    "StateDataMcpBackend",
    "StateIdentityMapping",
    "StateRegistryBackend",
]
