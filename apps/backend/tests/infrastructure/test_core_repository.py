"""KYA Core persistence is scoped, transactional and replay-safe."""

from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Self
from uuid import UUID

import pytest

from kya_platform.application.core import (
    ClientRecord,
    CommandMetadata,
    CoreConflictError,
    EmployeeRecord,
)
from kya_platform.domain.core import (
    ClientAccount,
    ClientStatus,
    Party,
    PartyKind,
    PersonProfile,
    Project,
    ProjectStatus,
    WorkRelationship,
    WorkRelationshipKind,
)
from kya_platform.domain.organization import DateRange, OrganizationalUnit
from kya_platform.infrastructure.database.core import SqlAlchemyCoreRepository
from kya_platform.infrastructure.database.models import (
    CoreClientAccount,
    CoreOrganizationalUnit,
    CoreOrganizationalUnitType,
    CoreParty,
    CorePersonProfile,
    CoreProject,
    CoreWorkRelationship,
    IdempotencyRecord,
    OutboxEvent,
)

ENTITY = UUID("01993430-0000-7000-8000-000000000001")
ACTOR = UUID("01993430-0000-7000-8000-000000000002")
UNIT = UUID("01993430-0000-7000-8000-000000000004")
PERIOD = DateRange(datetime(2026, 9, 1, tzinfo=UTC))


class SessionStub:
    def __init__(self, record: IdempotencyRecord | None = None) -> None:
        self.record = record
        self.added: object | None = None

    async def scalar(self, statement: object) -> IdempotencyRecord | None:
        return self.record

    def add(self, value: object) -> None:
        self.added = value


class ScalarRows:
    def __init__(self, rows: Iterable[object]) -> None:
        self.rows = list(rows)

    def __iter__(self) -> Iterable[object]:
        return iter(self.rows)


class ExecuteRows(ScalarRows):
    def first(self) -> object | None:
        return self.rows[0] if self.rows else None


class RepositorySession:
    def __init__(
        self,
        *,
        scalar_values: list[object | None] | None = None,
        scalar_rows: list[list[object]] | None = None,
        execute_rows: list[list[object]] | None = None,
        get_values: list[object | None] | None = None,
    ) -> None:
        self.scalar_values = scalar_values or []
        self.scalar_rows = scalar_rows or []
        self.execute_rows = execute_rows or []
        self.get_values = get_values or []
        self.added: list[object] = []

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    def begin(self) -> Self:
        return self

    async def scalar(self, statement: object) -> object | None:
        del statement
        return self.scalar_values.pop(0)

    async def scalars(self, statement: object) -> ScalarRows:
        del statement
        return ScalarRows(self.scalar_rows.pop(0))

    async def execute(self, statement: object) -> ExecuteRows:
        del statement
        return ExecuteRows(self.execute_rows.pop(0))

    async def get(self, model: object, identity: object) -> object | None:
        del model, identity
        return self.get_values.pop(0)

    def add(self, value: object) -> None:
        self.added.append(value)

    def add_all(self, values: list[object]) -> None:
        self.added.extend(values)


class Sessions:
    def __init__(self, session: RepositorySession) -> None:
        self.session = session

    def __call__(self) -> RepositorySession:
        return self.session


def unit_row() -> CoreOrganizationalUnit:
    return CoreOrganizationalUnit(
        id=UNIT,
        key="direction-cvsi",
        type_key="direction",
        name="CVSI",
        status="active",
        valid_from=PERIOD.valid_from,
        valid_until=None,
        version=1,
        created_by=ACTOR,
    )


def client_rows() -> tuple[CoreParty, CoreClientAccount]:
    party = CoreParty(
        id=UUID(int=20),
        kind="organization",
        display_name="Client Démo",
        status="active",
        version=1,
        created_by=ACTOR,
    )
    account = CoreClientAccount(
        id=ENTITY,
        key="client-demo",
        party_id=party.id,
        owner_unit_id=UNIT,
        status="active",
        valid_from=PERIOD.valid_from,
        valid_until=None,
        version=1,
        created_by=ACTOR,
    )
    return party, account


def project_row() -> CoreProject:
    return CoreProject(
        id=UUID(int=30),
        key="solar-one",
        name="Solar One",
        owner_unit_id=UNIT,
        client_id=ENTITY,
        status="active",
        valid_from=PERIOD.valid_from,
        valid_until=None,
        version=1,
        created_by=ACTOR,
    )


def employee_rows() -> tuple[CoreParty, CorePersonProfile, CoreWorkRelationship]:
    party = CoreParty(
        id=UUID(int=50),
        kind="person",
        display_name="Afi Mensah",
        status="active",
        version=1,
        created_by=ACTOR,
    )
    profile = CorePersonProfile(
        party_id=party.id,
        given_name="Afi",
        family_name="Mensah",
        preferred_name=None,
    )
    relationship = CoreWorkRelationship(
        id=ENTITY,
        person_id=party.id,
        employer_unit_id=UNIT,
        principal_id=None,
        kind="employee",
        personnel_number="EMP-42",
        valid_from=PERIOD.valid_from,
        valid_until=None,
        created_by=ACTOR,
    )
    return party, profile, relationship


def command(request_hash: str = "a" * 64) -> CommandMetadata:
    return CommandMetadata(
        ACTOR,
        UUID("01993430-0000-7000-8000-000000000003"),
        "core-command-000001",
        request_hash,
        datetime(2026, 9, 8, tzinfo=UTC),
    )


@pytest.mark.asyncio
@pytest.mark.unit
async def test_matching_idempotency_record_returns_original_entity() -> None:
    row = IdempotencyRecord(
        scope="core:client:create:scope:actor",
        idempotency_key=command().idempotency_key,
        request_hash="a" * 64,
        response_status=201,
        response_body={"id": str(ENTITY)},
        expires_at=datetime(2026, 9, 8, tzinfo=UTC),
    )

    replay = await SqlAlchemyCoreRepository._replay_id(SessionStub(row), row.scope, command())  # type: ignore[arg-type]

    assert replay == ENTITY


@pytest.mark.asyncio
@pytest.mark.unit
async def test_reused_key_with_different_payload_is_rejected() -> None:
    row = IdempotencyRecord(
        scope="core:client:create:scope:actor",
        idempotency_key=command().idempotency_key,
        request_hash="b" * 64,
        response_status=201,
        response_body={"id": str(ENTITY)},
        expires_at=datetime(2026, 9, 8, tzinfo=UTC),
    )

    with pytest.raises(CoreConflictError, match="another request"):
        await SqlAlchemyCoreRepository._replay_id(SessionStub(row), row.scope, command())  # type: ignore[arg-type]


@pytest.mark.unit
def test_idempotency_evidence_contains_only_the_stable_result_identifier() -> None:
    session = SessionStub()

    SqlAlchemyCoreRepository._remember(  # type: ignore[arg-type]
        session, "core:client:create:scope:actor", command(), ENTITY
    )

    assert isinstance(session.added, IdempotencyRecord)
    assert session.added.response_body == {"id": str(ENTITY)}


@pytest.mark.asyncio
@pytest.mark.unit
async def test_scoped_read_models_are_reconstructed_from_database_rows() -> None:
    row = unit_row()
    repository = SqlAlchemyCoreRepository(
        Sessions(
            RepositorySession(
                scalar_values=[row, UNIT, UNIT, UNIT, UNIT],
                scalar_rows=[[row], [project_row()]],
                execute_rows=[[client_rows()], [client_rows()]],
            )
        )  # type: ignore[arg-type]
    )

    unit = await repository.get_unit("direction-cvsi")
    children = await repository.list_child_units("groupe-kya", at=PERIOD.valid_from, limit=10)
    clients = await repository.list_clients("direction-cvsi", limit=10)
    client = await repository.get_client("direction-cvsi", ENTITY)
    projects = await repository.list_projects("direction-cvsi", limit=10)

    assert unit is not None and unit.name == "CVSI"
    assert children[0].id == UNIT
    assert clients[0].party.display_name == "Client Démo"
    assert client is not None and client.account.id == ENTITY
    assert projects[0].key == "solar-one"


@pytest.mark.asyncio
@pytest.mark.unit
async def test_absent_scope_returns_empty_results_without_data_leakage() -> None:
    repository = SqlAlchemyCoreRepository(
        Sessions(RepositorySession(scalar_values=[None, None, None, None, None]))  # type: ignore[arg-type]
    )

    assert await repository.get_unit("missing") is None
    assert await repository.list_child_units("missing", at=PERIOD.valid_from, limit=10) == ()
    assert await repository.list_clients("missing", limit=10) == ()
    assert await repository.get_client("missing", ENTITY) is None
    assert await repository.list_projects("missing", limit=10) == ()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_creating_a_client_persists_master_data_outbox_and_replay_evidence() -> None:
    session = RepositorySession(scalar_values=[UNIT, None])
    repository = SqlAlchemyCoreRepository(Sessions(session))  # type: ignore[arg-type]
    party = Party(UUID(int=20), PartyKind.ORGANIZATION, "Client Démo")
    record = ClientRecord(
        party,
        ClientAccount(ENTITY, "client-demo", party.id, UNIT, ClientStatus.ACTIVE, PERIOD),
    )

    created = await repository.create_client("direction-cvsi", record, command=command())

    assert created == record
    assert any(isinstance(row, CoreParty) for row in session.added)
    assert any(isinstance(row, CoreClientAccount) for row in session.added)
    assert any(isinstance(row, OutboxEvent) for row in session.added)
    assert any(isinstance(row, IdempotencyRecord) for row in session.added)


@pytest.mark.asyncio
@pytest.mark.unit
async def test_creating_unit_and_project_emit_transactional_events() -> None:
    parent = unit_row()
    unit_type = CoreOrganizationalUnitType(
        key="team",
        label="Équipe",
        allowed_parent_types=["direction"],
        is_temporary=False,
        status="active",
    )
    child = OrganizationalUnit(UUID(int=40), "equipe-data", "team", "Data", PERIOD)
    unit_session = RepositorySession(scalar_values=[parent, None], get_values=[unit_type])
    unit_repository = SqlAlchemyCoreRepository(Sessions(unit_session))  # type: ignore[arg-type]

    assert (
        await unit_repository.create_child_unit("direction-cvsi", child, command=command()) == child
    )
    assert len(unit_session.added) == 4

    project = Project(
        UUID(int=30),
        "solar-one",
        "Solar One",
        UNIT,
        ProjectStatus.ACTIVE,
        PERIOD,
    )
    project_session = RepositorySession(scalar_values=[UNIT, None])
    project_repository = SqlAlchemyCoreRepository(Sessions(project_session))  # type: ignore[arg-type]

    assert (
        await project_repository.create_project("direction-cvsi", project, command=command())
        == project
    )
    assert any(isinstance(row, CoreProject) for row in project_session.added)
    assert any(isinstance(row, OutboxEvent) for row in project_session.added)


@pytest.mark.asyncio
@pytest.mark.unit
async def test_scoped_employee_reads_are_reconstructed_from_database_rows() -> None:
    repository = SqlAlchemyCoreRepository(
        Sessions(
            RepositorySession(
                scalar_values=[UNIT, UNIT],
                execute_rows=[[employee_rows()], [employee_rows()]],
            )
        )  # type: ignore[arg-type]
    )

    employees = await repository.list_employees("direction-cvsi", limit=10)
    employee = await repository.get_employee("direction-cvsi", ENTITY)

    assert employees[0].profile.given_name == "Afi"
    assert employee is not None and employee.relationship.id == ENTITY


@pytest.mark.asyncio
@pytest.mark.unit
async def test_creating_an_employee_persists_party_profile_relationship_and_evidence() -> None:
    session = RepositorySession(scalar_values=[UNIT, None])
    repository = SqlAlchemyCoreRepository(Sessions(session))  # type: ignore[arg-type]
    party = Party(UUID(int=50), PartyKind.PERSON, "Afi Mensah")
    record = EmployeeRecord(
        party,
        PersonProfile(party.id, "Afi", "Mensah"),
        WorkRelationship(
            ENTITY, party.id, UNIT, WorkRelationshipKind.EMPLOYEE, PERIOD, personnel_number="EMP-42"
        ),
    )

    created = await repository.create_employee("direction-cvsi", record, command=command())

    assert created == record
    assert any(isinstance(row, CoreParty) for row in session.added)
    assert any(isinstance(row, CorePersonProfile) for row in session.added)
    assert any(isinstance(row, CoreWorkRelationship) for row in session.added)
    assert any(isinstance(row, OutboxEvent) for row in session.added)
    assert any(isinstance(row, IdempotencyRecord) for row in session.added)
