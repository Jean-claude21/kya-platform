"""Late-bound adapters shared by the FastAPI and Registry MCP lifecycles."""

from collections.abc import Sequence
from typing import Any
from uuid import UUID

from mcp.server.mcpserver.exceptions import ToolError
from starlette.datastructures import State

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

    async def get_artifact(self, *args: Any, **kwargs: Any):  # type: ignore[no-untyped-def]
        return await self._backend().get_artifact(*args, **kwargs)

    async def list_updates(self, *args: Any, **kwargs: Any):  # type: ignore[no-untyped-def]
        return await self._backend().list_updates(*args, **kwargs)

    async def request_install(self, *args: Any, **kwargs: Any):  # type: ignore[no-untyped-def]
        return await self._backend().request_install(*args, **kwargs)

    async def request_update(self, *args: Any, **kwargs: Any):  # type: ignore[no-untyped-def]
        return await self._backend().request_update(*args, **kwargs)

    async def get_operation(self, *args: Any, **kwargs: Any):  # type: ignore[no-untyped-def]
        return await self._backend().get_operation(*args, **kwargs)

    async def publish_candidate(self, *args: Any, **kwargs: Any):  # type: ignore[no-untyped-def]
        return await self._backend().publish_candidate(*args, **kwargs)


__all__ = ["StateAuthorizationPort", "StateIdentityMapping", "StateRegistryBackend"]
