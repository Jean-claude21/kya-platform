"""Transactional Neon adapter for KYA Core master data."""

from collections.abc import Sequence
from datetime import datetime
from typing import cast
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from kya_platform.application.core import (
    ClientRecord,
    CommandMetadata,
    CoreConflictError,
    CoreReferenceError,
)
from kya_platform.domain.core import (
    ClientAccount,
    ClientStatus,
    Party,
    PartyKind,
    Project,
    ProjectStatus,
    RecordStatus,
)
from kya_platform.domain.organization import DateRange, OrganizationalUnit
from kya_platform.infrastructure.database.models import (
    CoreClientAccount,
    CoreOrganizationalUnit,
    CoreOrganizationalUnitRelation,
    CoreOrganizationalUnitType,
    CoreParty,
    CoreProject,
    IdempotencyRecord,
    OutboxEvent,
)


def _unit(row: CoreOrganizationalUnit) -> OrganizationalUnit:
    return OrganizationalUnit(
        row.id,
        row.key,
        row.type_key,
        row.name,
        DateRange(row.valid_from, row.valid_until),
    )


def _client(party: CoreParty, account: CoreClientAccount) -> ClientRecord:
    return ClientRecord(
        Party(
            id=party.id,
            kind=PartyKind(party.kind),
            display_name=party.display_name,
            status=RecordStatus(party.status),
            version=party.version,
        ),
        ClientAccount(
            id=account.id,
            key=account.key,
            party_id=account.party_id,
            owner_unit_id=account.owner_unit_id,
            status=ClientStatus(account.status),
            validity=DateRange(account.valid_from, account.valid_until),
            version=account.version,
        ),
    )


def _project(row: CoreProject) -> Project:
    return Project(
        id=row.id,
        key=row.key,
        name=row.name,
        owner_unit_id=row.owner_unit_id,
        status=ProjectStatus(row.status),
        validity=DateRange(row.valid_from, row.valid_until),
        client_id=row.client_id,
        version=row.version,
    )


def _event(
    topic: str,
    aggregate_type: str,
    aggregate_id: UUID,
    scope_unit_id: UUID,
    actor_id: UUID,
    correlation_id: UUID,
) -> OutboxEvent:
    return OutboxEvent(
        topic=topic,
        aggregate_type=aggregate_type,
        aggregate_id=str(aggregate_id),
        correlation_id=correlation_id,
        payload={
            "schema_version": "1",
            "aggregate_id": str(aggregate_id),
            "scope_unit_id": str(scope_unit_id),
            "actor_id": str(actor_id),
        },
    )


class SqlAlchemyCoreRepository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def get_unit(self, key: str) -> OrganizationalUnit | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(CoreOrganizationalUnit).where(CoreOrganizationalUnit.key == key)
            )
            return _unit(row) if row is not None else None

    async def list_child_units(
        self, parent_key: str, *, at: datetime, limit: int
    ) -> Sequence[OrganizationalUnit]:
        async with self._sessions() as session:
            parent_id = await session.scalar(
                select(CoreOrganizationalUnit.id).where(CoreOrganizationalUnit.key == parent_key)
            )
            if parent_id is None:
                return ()
            result = await session.scalars(
                select(CoreOrganizationalUnit)
                .join(
                    CoreOrganizationalUnitRelation,
                    CoreOrganizationalUnitRelation.child_unit_id == CoreOrganizationalUnit.id,
                )
                .where(
                    CoreOrganizationalUnitRelation.parent_unit_id == parent_id,
                    CoreOrganizationalUnitRelation.kind == "hierarchical",
                    CoreOrganizationalUnitRelation.valid_from <= at,
                    or_(
                        CoreOrganizationalUnitRelation.valid_until.is_(None),
                        CoreOrganizationalUnitRelation.valid_until > at,
                    ),
                )
                .order_by(CoreOrganizationalUnit.name, CoreOrganizationalUnit.id)
                .limit(limit)
            )
            return tuple(_unit(row) for row in result)

    async def create_child_unit(
        self,
        parent_key: str,
        unit: OrganizationalUnit,
        *,
        command: CommandMetadata,
    ) -> OrganizationalUnit:
        try:
            async with self._sessions() as session, session.begin():
                parent = await session.scalar(
                    select(CoreOrganizationalUnit).where(CoreOrganizationalUnit.key == parent_key)
                )
                unit_type = await session.get(CoreOrganizationalUnitType, unit.type_key)
                if parent is None or unit_type is None:
                    raise CoreReferenceError("parent unit or child unit type does not exist")
                if parent.type_key not in unit_type.allowed_parent_types:
                    raise CoreReferenceError("unit type does not accept the selected parent type")
                scope = f"core:unit:create:{parent.id}:{command.actor_id}"
                replay_id = await self._replay_id(session, scope, command)
                if replay_id is not None:
                    existing = await session.get(CoreOrganizationalUnit, replay_id)
                    if existing is None:
                        raise CoreReferenceError("idempotent unit result is no longer available")
                    return _unit(existing)
                row = CoreOrganizationalUnit(
                    id=unit.id,
                    key=unit.key,
                    type_key=unit.type_key,
                    name=unit.name,
                    status="active",
                    valid_from=unit.validity.valid_from,
                    valid_until=unit.validity.valid_until,
                    created_by=command.actor_id,
                )
                relation = CoreOrganizationalUnitRelation(
                    parent_unit_id=parent.id,
                    child_unit_id=unit.id,
                    kind="hierarchical",
                    valid_from=unit.validity.valid_from,
                    valid_until=unit.validity.valid_until,
                    created_by=command.actor_id,
                )
                session.add_all(
                    [
                        row,
                        relation,
                        _event(
                            "kya.core.organization_unit.created.v1",
                            "organizational_unit",
                            unit.id,
                            parent.id,
                            command.actor_id,
                            command.correlation_id,
                        ),
                    ]
                )
                self._remember(session, scope, command, unit.id)
        except IntegrityError as error:
            raise CoreConflictError("organizational unit key or relation already exists") from error
        return unit

    async def list_clients(self, owner_unit_key: str, *, limit: int) -> Sequence[ClientRecord]:
        async with self._sessions() as session:
            owner_id = await self._unit_id(session, owner_unit_key)
            if owner_id is None:
                return ()
            rows = await session.execute(
                select(CoreParty, CoreClientAccount)
                .join(CoreClientAccount, CoreClientAccount.party_id == CoreParty.id)
                .where(CoreClientAccount.owner_unit_id == owner_id)
                .order_by(CoreParty.display_name, CoreClientAccount.id)
                .limit(limit)
            )
            return tuple(_client(party, account) for party, account in rows)

    async def get_client(self, owner_unit_key: str, client_id: UUID) -> ClientRecord | None:
        async with self._sessions() as session:
            owner_id = await self._unit_id(session, owner_unit_key)
            if owner_id is None:
                return None
            row = (
                await session.execute(
                    select(CoreParty, CoreClientAccount)
                    .join(CoreClientAccount, CoreClientAccount.party_id == CoreParty.id)
                    .where(
                        CoreClientAccount.id == client_id,
                        CoreClientAccount.owner_unit_id == owner_id,
                    )
                )
            ).first()
            return _client(*row) if row is not None else None

    async def create_client(
        self,
        owner_unit_key: str,
        record: ClientRecord,
        *,
        command: CommandMetadata,
    ) -> ClientRecord:
        try:
            async with self._sessions() as session, session.begin():
                owner_id = await self._required_unit_id(session, owner_unit_key)
                scope = f"core:client:create:{owner_id}:{command.actor_id}"
                replay_id = await self._replay_id(session, scope, command)
                if replay_id is not None:
                    replay = (
                        await session.execute(
                            select(CoreParty, CoreClientAccount)
                            .join(CoreClientAccount, CoreClientAccount.party_id == CoreParty.id)
                            .where(
                                CoreClientAccount.id == replay_id,
                                CoreClientAccount.owner_unit_id == owner_id,
                            )
                        )
                    ).first()
                    if replay is None:
                        raise CoreReferenceError("idempotent client result is no longer available")
                    return _client(*replay)
                if record.account.owner_unit_id != owner_id:
                    raise CoreReferenceError("client owner does not match the authorized scope")
                party = CoreParty(
                    id=record.party.id,
                    kind=record.party.kind.value,
                    display_name=record.party.display_name,
                    status=record.party.status.value,
                    version=record.party.version,
                    created_by=command.actor_id,
                )
                account = CoreClientAccount(
                    id=record.account.id,
                    key=record.account.key,
                    party_id=record.party.id,
                    owner_unit_id=owner_id,
                    status=record.account.status.value,
                    valid_from=record.account.validity.valid_from,
                    valid_until=record.account.validity.valid_until,
                    version=record.account.version,
                    created_by=command.actor_id,
                )
                session.add_all(
                    [
                        party,
                        account,
                        _event(
                            "kya.core.client.created.v1",
                            "client",
                            record.account.id,
                            owner_id,
                            command.actor_id,
                            command.correlation_id,
                        ),
                    ]
                )
                self._remember(session, scope, command, record.account.id)
        except IntegrityError as error:
            raise CoreConflictError("client key or party already exists") from error
        return record

    async def list_projects(self, owner_unit_key: str, *, limit: int) -> Sequence[Project]:
        async with self._sessions() as session:
            owner_id = await self._unit_id(session, owner_unit_key)
            if owner_id is None:
                return ()
            result = await session.scalars(
                select(CoreProject)
                .where(CoreProject.owner_unit_id == owner_id)
                .order_by(CoreProject.name, CoreProject.id)
                .limit(limit)
            )
            return tuple(_project(row) for row in result)

    async def get_project(self, owner_unit_key: str, project_id: UUID) -> Project | None:
        async with self._sessions() as session:
            owner_id = await self._unit_id(session, owner_unit_key)
            if owner_id is None:
                return None
            row = await session.scalar(
                select(CoreProject).where(
                    CoreProject.id == project_id,
                    CoreProject.owner_unit_id == owner_id,
                )
            )
            return _project(row) if row is not None else None

    async def create_project(
        self,
        owner_unit_key: str,
        project: Project,
        *,
        command: CommandMetadata,
    ) -> Project:
        try:
            async with self._sessions() as session, session.begin():
                owner_id = await self._required_unit_id(session, owner_unit_key)
                scope = f"core:project:create:{owner_id}:{command.actor_id}"
                replay_id = await self._replay_id(session, scope, command)
                if replay_id is not None:
                    existing = await session.get(CoreProject, replay_id)
                    if existing is None or existing.owner_unit_id != owner_id:
                        raise CoreReferenceError("idempotent project result is no longer available")
                    return _project(existing)
                if project.owner_unit_id != owner_id:
                    raise CoreReferenceError("project owner does not match the authorized scope")
                if project.client_id is not None:
                    client_owner = await session.scalar(
                        select(CoreClientAccount.owner_unit_id).where(
                            CoreClientAccount.id == project.client_id
                        )
                    )
                    if client_owner != owner_id:
                        raise CoreReferenceError(
                            "project client is absent from the authorized scope"
                        )
                row = CoreProject(
                    id=project.id,
                    key=project.key,
                    name=project.name,
                    owner_unit_id=owner_id,
                    client_id=project.client_id,
                    status=project.status.value,
                    valid_from=project.validity.valid_from,
                    valid_until=project.validity.valid_until,
                    version=project.version,
                    created_by=command.actor_id,
                )
                session.add_all(
                    [
                        row,
                        _event(
                            "kya.core.project.created.v1",
                            "project",
                            project.id,
                            owner_id,
                            command.actor_id,
                            command.correlation_id,
                        ),
                    ]
                )
                self._remember(session, scope, command, project.id)
        except IntegrityError as error:
            raise CoreConflictError("project key already exists") from error
        return project

    @staticmethod
    async def _unit_id(session: AsyncSession, key: str) -> UUID | None:
        return cast(
            UUID | None,
            await session.scalar(
                select(CoreOrganizationalUnit.id).where(CoreOrganizationalUnit.key == key)
            ),
        )

    @classmethod
    async def _required_unit_id(cls, session: AsyncSession, key: str) -> UUID:
        unit_id = await cls._unit_id(session, key)
        if unit_id is None:
            raise CoreReferenceError("organizational unit does not exist")
        return unit_id

    @staticmethod
    async def _replay_id(
        session: AsyncSession, scope: str, command: CommandMetadata
    ) -> UUID | None:
        record = await session.scalar(
            select(IdempotencyRecord).where(
                IdempotencyRecord.scope == scope,
                IdempotencyRecord.idempotency_key == command.idempotency_key,
            )
        )
        if record is None:
            return None
        if record.request_hash != command.request_hash:
            raise CoreConflictError("idempotency key already belongs to another request")
        entity_id = record.response_body.get("id")
        if not isinstance(entity_id, str):
            raise CoreReferenceError("idempotent result is invalid")
        try:
            return UUID(entity_id)
        except ValueError as error:
            raise CoreReferenceError("idempotent result is invalid") from error

    @staticmethod
    def _remember(
        session: AsyncSession, scope: str, command: CommandMetadata, entity_id: UUID
    ) -> None:
        session.add(
            IdempotencyRecord(
                scope=scope,
                idempotency_key=command.idempotency_key,
                request_hash=command.request_hash,
                response_status=201,
                response_body={"id": str(entity_id)},
                expires_at=command.expires_at,
            )
        )


__all__ = ["SqlAlchemyCoreRepository"]
