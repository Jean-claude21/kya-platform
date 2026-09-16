"""Use cases and ports for KYA Core master data."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from kya_platform.domain.core import ClientAccount, Party, Project
from kya_platform.domain.organization import OrganizationalUnit, OrganizationalUnitType


class CoreConflictError(RuntimeError):
    """A stable key or external business invariant already exists."""


class CoreReferenceError(RuntimeError):
    """A referenced master-data record is absent or outside the scope."""


@dataclass(frozen=True, slots=True)
class CommandMetadata:
    actor_id: UUID
    correlation_id: UUID
    idempotency_key: str
    request_hash: str
    expires_at: datetime

    def __post_init__(self) -> None:
        if not 16 <= len(self.idempotency_key) <= 200:
            raise ValueError("idempotency key must contain 16 to 200 characters")
        if len(self.request_hash) != 64:
            raise ValueError("request hash must be a SHA-256 hexadecimal digest")
        if self.expires_at.tzinfo is None or self.expires_at.utcoffset() is None:
            raise ValueError("idempotency expiry must include a timezone")


@dataclass(frozen=True, slots=True)
class ClientRecord:
    party: Party
    account: ClientAccount


class CoreRepository(Protocol):
    async def list_unit_types(self) -> Sequence[OrganizationalUnitType]: ...

    async def get_unit(self, key: str) -> OrganizationalUnit | None: ...

    async def list_child_units(
        self, parent_key: str, *, at: datetime, limit: int
    ) -> Sequence[OrganizationalUnit]: ...

    async def create_child_unit(
        self,
        parent_key: str,
        unit: OrganizationalUnit,
        *,
        command: CommandMetadata,
    ) -> OrganizationalUnit: ...

    async def list_clients(self, owner_unit_key: str, *, limit: int) -> Sequence[ClientRecord]: ...

    async def get_client(self, owner_unit_key: str, client_id: UUID) -> ClientRecord | None: ...

    async def create_client(
        self,
        owner_unit_key: str,
        record: ClientRecord,
        *,
        command: CommandMetadata,
    ) -> ClientRecord: ...

    async def list_projects(self, owner_unit_key: str, *, limit: int) -> Sequence[Project]: ...

    async def get_project(self, owner_unit_key: str, project_id: UUID) -> Project | None: ...

    async def create_project(
        self,
        owner_unit_key: str,
        project: Project,
        *,
        command: CommandMetadata,
    ) -> Project: ...


class CoreService:
    """Thin orchestration boundary shared by HTTP, MCP and future adapters."""

    def __init__(self, repository: CoreRepository) -> None:
        self._repository = repository

    async def list_unit_types(self) -> Sequence[OrganizationalUnitType]:
        return await self._repository.list_unit_types()

    async def get_unit(self, key: str) -> OrganizationalUnit | None:
        return await self._repository.get_unit(key)

    async def list_child_units(
        self, parent_key: str, *, at: datetime, limit: int
    ) -> Sequence[OrganizationalUnit]:
        return await self._repository.list_child_units(parent_key, at=at, limit=limit)

    async def create_child_unit(
        self,
        parent_key: str,
        unit: OrganizationalUnit,
        *,
        command: CommandMetadata,
    ) -> OrganizationalUnit:
        return await self._repository.create_child_unit(parent_key, unit, command=command)

    async def list_clients(self, owner_unit_key: str, *, limit: int) -> Sequence[ClientRecord]:
        return await self._repository.list_clients(owner_unit_key, limit=limit)

    async def get_client(self, owner_unit_key: str, client_id: UUID) -> ClientRecord | None:
        return await self._repository.get_client(owner_unit_key, client_id)

    async def create_client(
        self,
        owner_unit_key: str,
        record: ClientRecord,
        *,
        command: CommandMetadata,
    ) -> ClientRecord:
        return await self._repository.create_client(owner_unit_key, record, command=command)

    async def list_projects(self, owner_unit_key: str, *, limit: int) -> Sequence[Project]:
        return await self._repository.list_projects(owner_unit_key, limit=limit)

    async def get_project(self, owner_unit_key: str, project_id: UUID) -> Project | None:
        return await self._repository.get_project(owner_unit_key, project_id)

    async def create_project(
        self,
        owner_unit_key: str,
        project: Project,
        *,
        command: CommandMetadata,
    ) -> Project:
        return await self._repository.create_project(owner_unit_key, project, command=command)


__all__ = [
    "ClientRecord",
    "CommandMetadata",
    "CoreConflictError",
    "CoreReferenceError",
    "CoreRepository",
    "CoreService",
]
