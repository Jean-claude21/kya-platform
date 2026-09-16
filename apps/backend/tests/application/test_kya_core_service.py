"""The application boundary preserves scope and transaction context."""

from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID

import pytest

from kya_platform.application.core import ClientRecord, CommandMetadata, CoreService
from kya_platform.domain.core import (
    ClientAccount,
    ClientStatus,
    Party,
    PartyKind,
    Project,
    ProjectStatus,
)
from kya_platform.domain.organization import DateRange, OrganizationalUnit, OrganizationalUnitType

UNIT = UUID("01993410-0000-7000-8000-000000000001")
ACTOR = UUID("01993410-0000-7000-8000-000000000002")
CORRELATION = UUID("01993410-0000-7000-8000-000000000003")


class RecordingRepository:
    def __init__(self) -> None:
        self.command: tuple[str, UUID, UUID] | None = None
        self.calls: list[str] = []

    async def list_unit_types(self) -> Sequence[OrganizationalUnitType]:
        self.calls.append("list_unit_types")
        return ()

    async def get_unit(self, key: str) -> OrganizationalUnit | None:
        self.calls.append("get_unit")
        return None

    async def list_child_units(
        self, parent_key: str, *, at: datetime, limit: int
    ) -> Sequence[OrganizationalUnit]:
        self.calls.append("list_child_units")
        return ()

    async def create_child_unit(
        self,
        parent_key: str,
        unit: OrganizationalUnit,
        *,
        command: CommandMetadata,
    ) -> OrganizationalUnit:
        self.calls.append("create_child_unit")
        self.command = (parent_key, command.actor_id, command.correlation_id)
        return unit

    async def list_clients(self, owner_unit_key: str, *, limit: int) -> Sequence[ClientRecord]:
        self.calls.append("list_clients")
        return ()

    async def get_client(self, owner_unit_key: str, client_id: UUID) -> ClientRecord | None:
        self.calls.append("get_client")
        return None

    async def create_client(
        self,
        owner_unit_key: str,
        record: ClientRecord,
        *,
        command: CommandMetadata,
    ) -> ClientRecord:
        self.calls.append("create_client")
        self.command = (owner_unit_key, command.actor_id, command.correlation_id)
        return record

    async def list_projects(self, owner_unit_key: str, *, limit: int) -> Sequence[Project]:
        self.calls.append("list_projects")
        return ()

    async def get_project(self, owner_unit_key: str, project_id: UUID) -> Project | None:
        self.calls.append("get_project")
        return None

    async def create_project(
        self,
        owner_unit_key: str,
        project: Project,
        *,
        command: CommandMetadata,
    ) -> Project:
        self.calls.append("create_project")
        self.command = (owner_unit_key, command.actor_id, command.correlation_id)
        return project


@pytest.mark.asyncio
@pytest.mark.unit
async def test_client_command_keeps_actor_scope_and_correlation() -> None:
    repository = RecordingRepository()
    service = CoreService(repository)
    period = DateRange(datetime(2026, 9, 1, tzinfo=UTC))
    party = Party(UUID(int=10), PartyKind.ORGANIZATION, "Client SA")
    record = ClientRecord(
        party,
        ClientAccount(UUID(int=11), "client-sa", party.id, UNIT, ClientStatus.ACTIVE, period),
    )

    created = await service.create_client(
        "direction-dss",
        record,
        command=CommandMetadata(
            ACTOR,
            CORRELATION,
            "client-command-0001",
            "a" * 64,
            datetime(2026, 9, 8, tzinfo=UTC),
        ),
    )

    assert created == record
    assert repository.command == ("direction-dss", ACTOR, CORRELATION)


@pytest.mark.asyncio
@pytest.mark.unit
async def test_service_delegates_every_core_use_case() -> None:
    repository = RecordingRepository()
    service = CoreService(repository)
    period = DateRange(datetime(2026, 9, 1, tzinfo=UTC))
    unit = OrganizationalUnit(UNIT, "direction-dss", "direction", "DSS", period)
    party = Party(UUID(int=10), PartyKind.ORGANIZATION, "Client SA")
    record = ClientRecord(
        party,
        ClientAccount(UUID(int=11), "client-sa", party.id, UNIT, ClientStatus.ACTIVE, period),
    )
    project = Project(
        UUID(int=12), "solar-one", "Solar One", UNIT, ProjectStatus.PLANNED, validity=period
    )
    command = CommandMetadata(
        ACTOR,
        CORRELATION,
        "core-command-0001",
        "a" * 64,
        datetime(2026, 9, 8, tzinfo=UTC),
    )

    assert await service.get_unit(unit.key) is None
    assert await service.list_unit_types() == ()
    assert await service.list_child_units(unit.key, at=period.valid_from, limit=10) == ()
    assert await service.create_child_unit("group", unit, command=command) == unit
    assert await service.list_clients(unit.key, limit=10) == ()
    assert await service.get_client(unit.key, record.account.id) is None
    assert await service.create_client(unit.key, record, command=command) == record
    assert await service.list_projects(unit.key, limit=10) == ()
    assert await service.get_project(unit.key, project.id) is None
    assert await service.create_project(unit.key, project, command=command) == project
    assert repository.calls == [
        "get_unit",
        "list_unit_types",
        "list_child_units",
        "create_child_unit",
        "list_clients",
        "get_client",
        "create_client",
        "list_projects",
        "get_project",
        "create_project",
    ]


@pytest.mark.unit
def test_command_metadata_rejects_unsafe_idempotency_contracts() -> None:
    expiry = datetime(2026, 9, 8, tzinfo=UTC)
    with pytest.raises(ValueError, match="16 to 200"):
        CommandMetadata(ACTOR, CORRELATION, "short", "a" * 64, expiry)
    with pytest.raises(ValueError, match="SHA-256"):
        CommandMetadata(ACTOR, CORRELATION, "core-command-0001", "bad", expiry)
    with pytest.raises(ValueError, match="timezone"):
        CommandMetadata(
            ACTOR,
            CORRELATION,
            "core-command-0001",
            "a" * 64,
            datetime(2026, 9, 8),
        )
