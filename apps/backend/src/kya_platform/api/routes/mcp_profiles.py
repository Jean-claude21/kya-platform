"""User-facing MCP tool profile inspection and restrictive preferences."""

from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Annotated, Protocol
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request
from pydantic import BaseModel, Field

from kya_platform.api.security import AuthorizedPrincipal, active_principal
from kya_platform.application.mcp_profiles import (
    McpPreferenceCommand,
    McpPreferenceService,
    McpProfileConflictError,
    McpProfileReferenceError,
    UserToolPreferenceKey,
)
from kya_platform.application.mcp_profiles.runtime import (
    McpToolProfileRuntime,
    ToolProfileRequest,
)
from kya_platform.application.reliability import JsonValue, canonical_request_hash
from kya_platform.observability import ApiError

router = APIRouter(prefix="/mcp", tags=["mcp-profiles"])


class ConnectorGrantQuery(Protocol):
    async def get_active_grant_scopes(
        self,
        *,
        principal_id: object,
        active_unit_id: str,
        client_id: str,
    ) -> frozenset[str] | None: ...


class EffectiveProfileResponse(BaseModel):
    client_id: str
    active_unit_key: str
    tool_keys: list[str]
    revision: str
    shadow_diverged: bool


class PreferenceRequest(BaseModel):
    expected_revision: int = Field(ge=0)
    client_id: str = Field(default="", max_length=128)


class PreferenceResponse(BaseModel):
    tool_key: str
    state: str
    revision: int


def _runtime(request: Request) -> McpToolProfileRuntime:
    runtime: McpToolProfileRuntime | None = request.app.state.mcp_tool_profile_runtime
    if runtime is None:
        raise ApiError(
            503,
            "mcp_profiles_unavailable",
            "Profils MCP indisponibles",
            "Le calcul gouverné des outils n'est pas activé.",
        )
    return runtime


def _preferences(request: Request) -> McpPreferenceService:
    service: McpPreferenceService | None = request.app.state.mcp_preference_service
    if service is None:
        raise ApiError(
            503,
            "mcp_profiles_unavailable",
            "Profils MCP indisponibles",
            "Les préférences MCP ne sont pas configurées.",
        )
    return service


def _command(
    request: Request,
    principal: AuthorizedPrincipal,
    idempotency_key: str,
    payload: Mapping[str, JsonValue],
) -> McpPreferenceCommand:
    return McpPreferenceCommand(
        actor_id=principal.principal_id,
        correlation_id=UUID(request.state.correlation_id),
        idempotency_key=idempotency_key,
        request_hash=canonical_request_hash(payload),
        expires_at=datetime.now(UTC) + timedelta(hours=24),
        environment=request.app.state.settings.environment,
    )


@router.get("/me/effective-profile", response_model=EffectiveProfileResponse)
async def effective_profile(
    request: Request,
    client_id: Annotated[str, Query(min_length=1, max_length=128)],
    principal: Annotated[AuthorizedPrincipal, Depends(active_principal)],
) -> EffectiveProfileResponse:
    """Inspect the effective set for an existing live MCP connector grant."""

    broker: ConnectorGrantQuery | None = request.app.state.oauth_broker
    if broker is None:
        raise ApiError(
            503,
            "oauth_broker_unavailable",
            "Connecteurs indisponibles",
            "Le courtier OAuth MCP n'est pas configuré.",
        )
    scopes = await broker.get_active_grant_scopes(
        principal_id=principal.principal_id,
        active_unit_id=principal.active_unit_id,
        client_id=client_id,
    )
    if scopes is None:
        raise ApiError(
            404,
            "mcp_connector_not_found",
            "Connecteur introuvable",
            "Aucune autorisation MCP active ne correspond à ce client et cette unité.",
        )
    decision = await _runtime(request).resolve(
        ToolProfileRequest(
            principal.principal_id,
            principal.active_unit_id,
            client_id,
            scopes,
        )
    )
    return EffectiveProfileResponse(
        client_id=client_id,
        active_unit_key=principal.active_unit_id,
        tool_keys=list(decision.effective_tool_keys),
        revision=decision.revision,
        shadow_diverged=decision.diverged,
    )


@router.put(
    "/me/tool-preferences/{tool_key}",
    response_model=PreferenceResponse,
)
async def disable_tool(
    tool_key: str,
    payload: PreferenceRequest,
    request: Request,
    principal: Annotated[AuthorizedPrincipal, Depends(active_principal)],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=16, max_length=200)],
) -> PreferenceResponse:
    """Disable one inherited tool globally or for a selected OAuth client."""

    key = UserToolPreferenceKey(
        principal.principal_id,
        principal.active_unit_id,
        payload.client_id,
        tool_key,
    )
    try:
        revision = await _preferences(request).disable_tool(
            key,
            command=_command(
                request,
                principal,
                idempotency_key,
                {
                    "action": "disable",
                    "tool_key": tool_key,
                    "client_id": payload.client_id,
                    "expected_revision": payload.expected_revision,
                },
            ),
            expected_revision=payload.expected_revision,
        )
    except McpProfileConflictError as error:
        raise ApiError(409, "revision_conflict", "Conflit de révision", str(error)) from error
    except McpProfileReferenceError as error:
        raise ApiError(404, "mcp_tool_not_found", "Outil introuvable", str(error)) from error
    return PreferenceResponse(tool_key=tool_key, state="disabled", revision=revision)


@router.delete("/me/tool-preferences/{tool_key}", status_code=204)
async def inherit_tool(
    tool_key: str,
    request: Request,
    principal: Annotated[AuthorizedPrincipal, Depends(active_principal)],
    expected_revision: Annotated[int, Query(ge=1)],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=16, max_length=200)],
    client_id: Annotated[str, Query(max_length=128)] = "",
) -> None:
    """Delete a restrictive preference and return to inherited behavior."""

    key = UserToolPreferenceKey(
        principal.principal_id,
        principal.active_unit_id,
        client_id,
        tool_key,
    )
    try:
        await _preferences(request).inherit_tool(
            key,
            command=_command(
                request,
                principal,
                idempotency_key,
                {
                    "action": "inherit",
                    "tool_key": tool_key,
                    "client_id": client_id,
                    "expected_revision": expected_revision,
                },
            ),
            expected_revision=expected_revision,
        )
    except McpProfileConflictError as error:
        raise ApiError(409, "revision_conflict", "Conflit de révision", str(error)) from error
    except McpProfileReferenceError as error:
        raise ApiError(404, "mcp_tool_not_found", "Outil introuvable", str(error)) from error


__all__ = ["router"]
