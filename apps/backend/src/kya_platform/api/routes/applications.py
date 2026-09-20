"""Governed discovery and launch metadata for KYA applications."""

import asyncio
from datetime import UTC, datetime
from typing import Annotated, Protocol

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from kya_platform.api.security import AuthorizedPrincipal, active_principal
from kya_platform.application.applications import (
    ApplicationRegistryPort,
    ApplicationRegistryService,
    RegisteredApplication,
)
from kya_platform.authorization import AuthorizationPort, CheckRequest, active_unit_context
from kya_platform.observability import ApiError

router = APIRouter(prefix="/applications", tags=["applications"])


class ApplicationFeatureResponse(BaseModel):
    key: str


class ApplicationSummaryResponse(BaseModel):
    artifact_id: str
    name: str
    summary: str | None
    version: str
    lifecycle: str
    enabled: bool
    owner_workspace_id: str
    launch_url: str
    launch_mode: str
    icon_url: str | None
    health_url: str | None
    required_sdk: str | None
    visibility: str
    default_scope: str
    allowed_scopes: tuple[str, ...]
    declared_permissions: tuple[str, ...]
    effective_permissions: tuple[str, ...]
    features: tuple[str, ...]


class ApplicationListResponse(BaseModel):
    items: tuple[ApplicationSummaryResponse, ...]
    active_unit: str


class ApplicationBackend(ApplicationRegistryPort, Protocol):
    pass


def _dependencies(request: Request) -> tuple[AuthorizationPort, ApplicationBackend]:
    authorization: AuthorizationPort | None = request.app.state.authorization
    applications: ApplicationBackend | None = request.app.state.registry_mcp_backend
    if authorization is None or applications is None:
        raise ApiError(
            503,
            "application_registry_unavailable",
            "Applications indisponibles",
            "Le registre d'applications n'est pas configuré.",
        )
    return authorization, applications


async def _effective_permissions(
    *,
    authorization: AuthorizationPort,
    principal: AuthorizedPrincipal,
    application: RegisteredApplication,
) -> tuple[str, ...]:
    context, contextual_tuples = active_unit_context(
        user_id=str(principal.principal_id),
        unit_id=principal.active_unit_id,
        current_time=datetime.now(UTC),
    )
    relation_by_permission = {
        "view": ("can_view", f"artifact:{application.internal_id}"),
        "use": ("can_view", f"artifact:{application.internal_id}"),
        "create": ("can_submit", f"artifact:{application.internal_id}"),
        "edit": ("can_submit", f"artifact:{application.internal_id}"),
        "administer": ("can_manage", f"workspace:{application.owner_workspace_id}"),
        "publish": ("can_approve", f"artifact:{application.internal_id}"),
        "share": ("can_manage", f"workspace:{application.owner_workspace_id}"),
    }
    declared = tuple(
        permission
        for permission in application.declared_permissions
        if permission in relation_by_permission
    )
    decisions = await asyncio.gather(
        *(
            authorization.check(
                CheckRequest(
                    user=f"user:{principal.principal_id}",
                    relation=relation_by_permission[permission][0],
                    object=relation_by_permission[permission][1],
                    context=context,
                    contextual_tuples=contextual_tuples,
                )
            )
            for permission in declared
        )
    )
    return tuple(
        permission
        for permission, decision in zip(declared, decisions, strict=True)
        if decision.allowed
    )


async def _list_authorized(
    request: Request, principal: AuthorizedPrincipal
) -> tuple[RegisteredApplication, ...]:
    authorization, applications = _dependencies(request)
    context, contextual_tuples = active_unit_context(
        user_id=str(principal.principal_id),
        unit_id=principal.active_unit_id,
        current_time=datetime.now(UTC),
    )
    return await ApplicationRegistryService(
        authorization=authorization, applications=applications
    ).list(
        user=f"user:{principal.principal_id}",
        context=context,
        contextual_tuples=contextual_tuples,
    )


async def _response(
    *,
    authorization: AuthorizationPort,
    principal: AuthorizedPrincipal,
    application: RegisteredApplication,
) -> ApplicationSummaryResponse:
    effective_permissions = await _effective_permissions(
        authorization=authorization,
        principal=principal,
        application=application,
    )
    return ApplicationSummaryResponse(
        artifact_id=application.artifact_id,
        name=application.name,
        summary=application.summary,
        version=application.version,
        lifecycle=application.lifecycle,
        enabled=application.lifecycle == "published" and "use" in effective_permissions,
        owner_workspace_id=application.owner_workspace_id,
        launch_url=application.launch_url,
        launch_mode=application.launch_mode,
        icon_url=application.icon_url,
        health_url=application.health_url,
        required_sdk=application.required_sdk,
        visibility=application.visibility,
        default_scope=application.default_scope,
        allowed_scopes=application.allowed_scopes,
        declared_permissions=application.declared_permissions,
        effective_permissions=effective_permissions,
        features=application.features,
    )


@router.get("", response_model=ApplicationListResponse)
async def list_applications(
    request: Request,
    principal: Annotated[AuthorizedPrincipal, Depends(active_principal)],
) -> ApplicationListResponse:
    """List launchable applications after policy filtering in the active unit."""

    authorization, _applications = _dependencies(request)
    registered = await _list_authorized(request, principal)
    items = await asyncio.gather(
        *(
            _response(
                authorization=authorization,
                principal=principal,
                application=application,
            )
            for application in registered
        )
    )
    return ApplicationListResponse(items=tuple(items), active_unit=principal.active_unit_id)


@router.get("/{artifact_id:path}", response_model=ApplicationSummaryResponse)
async def get_application(
    artifact_id: str,
    request: Request,
    principal: Annotated[AuthorizedPrincipal, Depends(active_principal)],
) -> ApplicationSummaryResponse:
    """Return one application without disclosing whether an unauthorized app exists."""

    authorization, _applications = _dependencies(request)
    registered = await _list_authorized(request, principal)
    application = next((item for item in registered if item.artifact_id == artifact_id), None)
    if application is None:
        raise ApiError(
            404,
            "application_not_found",
            "Application introuvable",
            "Cette application n'existe pas ou n'est pas accessible dans l'unité active.",
        )
    return await _response(
        authorization=authorization,
        principal=principal,
        application=application,
    )


__all__ = ["router"]
