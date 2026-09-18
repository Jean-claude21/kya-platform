"""Permission-filtered registry of launchable KYA applications."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol

from kya_platform.application.reliability import JsonValue
from kya_platform.authorization import (
    AuthorizationPort,
    AuthorizationService,
    ContextualTuple,
    ListObjectsRequest,
)


@dataclass(frozen=True, slots=True)
class RegisteredApplication:
    artifact_id: str
    internal_id: str
    name: str
    summary: str | None
    version: str
    lifecycle: str
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
    features: tuple[str, ...]


class ApplicationRegistryPort(Protocol):
    async def list_applications(
        self, *, allowed_ids: tuple[str, ...]
    ) -> Sequence[RegisteredApplication]:
        """Return only published applications inside the preauthorized identifier set."""


class ApplicationRegistryService:
    def __init__(
        self, *, authorization: AuthorizationPort, applications: ApplicationRegistryPort
    ) -> None:
        self._authorization = authorization
        self._applications = applications

    async def list(
        self,
        *,
        user: str,
        context: Mapping[str, JsonValue],
        contextual_tuples: Sequence[ContextualTuple],
    ) -> tuple[RegisteredApplication, ...]:
        allowed_ids = await AuthorizationService(self._authorization).list_authorized_objects(
            ListObjectsRequest(
                user=user,
                relation="can_view",
                object_type="artifact",
                context=context,
                contextual_tuples=contextual_tuples,
            )
        )
        if not allowed_ids:
            return ()
        applications = await self._applications.list_applications(allowed_ids=allowed_ids)
        if any(application.internal_id not in allowed_ids for application in applications):
            raise RuntimeError("application registry returned an unauthorized artifact")
        return tuple(applications)


__all__ = [
    "ApplicationRegistryPort",
    "ApplicationRegistryService",
    "RegisteredApplication",
]
