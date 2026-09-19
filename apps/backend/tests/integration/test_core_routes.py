"""KYA Core API checks authorization before scoped master-data access."""

from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from kya_platform.application.core import (
    ClientRecord,
    CommandMetadata,
    CoreConflictError,
    CoreReferenceError,
    EmployeeRecord,
)
from kya_platform.auth import AuthenticatedIdentity
from kya_platform.authorization import AuthorizationDecision, CheckRequest, ListObjectsRequest
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
from kya_platform.domain.organization import DateRange, OrganizationalUnit, OrganizationalUnitType

ALICE = UUID("01993420-0000-7000-8000-000000000001")
CVSI = UUID("01993420-0000-7000-8000-000000000002")
CLIENT = UUID("01993420-0000-7000-8000-000000000003")
PROJECT = UUID("01993420-0000-7000-8000-000000000004")
EMPLOYEE = UUID("01993420-0000-7000-8000-000000000005")


class Verifier:
    async def verify(self, token: str) -> AuthenticatedIdentity:
        return AuthenticatedIdentity("https://auth.example.neon.tech", "alice", {})


class Mapping:
    async def resolve_principal_id(self, identity: AuthenticatedIdentity) -> UUID | None:
        return ALICE


class Policy:
    def __init__(self, allowed: bool) -> None:
        self.allowed = allowed
        self.checks: list[CheckRequest] = []

    async def check(self, request: CheckRequest) -> AuthorizationDecision:
        self.checks.append(request)
        return AuthorizationDecision(self.allowed, "core-model")

    async def list_objects(self, request: ListObjectsRequest) -> Sequence[str]:
        return ()


class CoreStub:
    def __init__(self) -> None:
        period = DateRange(datetime(2026, 9, 1, tzinfo=UTC))
        self.unit = OrganizationalUnit(CVSI, "direction-cvsi", "direction", "CVSI", period)
        party = Party(UUID(int=20), PartyKind.ORGANIZATION, "Client Démo")
        self.client = ClientRecord(
            party,
            ClientAccount(CLIENT, "client-demo", party.id, CVSI, ClientStatus.ACTIVE, period),
        )
        self.client_reads = 0
        self.created_clients: list[ClientRecord] = []
        self.project = Project(
            PROJECT,
            "centrale-solaire",
            "Centrale solaire",
            CVSI,
            ProjectStatus.ACTIVE,
            period,
            client_id=CLIENT,
        )
        self.created_units: list[OrganizationalUnit] = []
        self.created_projects: list[Project] = []
        self.write_error: Exception | None = None
        employee_party = Party(UUID(int=30), PartyKind.PERSON, "Afi Mensah")
        self.employee = EmployeeRecord(
            employee_party,
            PersonProfile(employee_party.id, "Afi", "Mensah"),
            WorkRelationship(
                EMPLOYEE,
                employee_party.id,
                CVSI,
                WorkRelationshipKind.EMPLOYEE,
                period,
                personnel_number="EMP-42",
            ),
        )
        self.created_employees: list[EmployeeRecord] = []

    async def list_unit_types(self) -> Sequence[OrganizationalUnitType]:
        return (
            OrganizationalUnitType("group", "Groupe"),
            OrganizationalUnitType("entity", "Filiale", frozenset({"group"})),
            OrganizationalUnitType("agency", "Agence", frozenset({"group", "entity"})),
        )

    async def get_unit(self, key: str) -> OrganizationalUnit | None:
        return self.unit if key == self.unit.key else None

    async def list_child_units(
        self, parent_key: str, *, at: datetime, limit: int
    ) -> Sequence[OrganizationalUnit]:
        return (self.unit,) if parent_key == "groupe-kya" else ()

    async def create_child_unit(
        self,
        parent_key: str,
        unit: OrganizationalUnit,
        *,
        command: CommandMetadata,
    ) -> OrganizationalUnit:
        if self.write_error:
            raise self.write_error
        self.created_units.append(unit)
        return unit

    async def list_clients(self, owner_unit_key: str, *, limit: int) -> Sequence[ClientRecord]:
        self.client_reads += 1
        return (self.client,) if owner_unit_key == self.unit.key else ()

    async def get_client(self, owner_unit_key: str, client_id: UUID) -> ClientRecord | None:
        self.client_reads += 1
        if owner_unit_key == self.unit.key and client_id == CLIENT:
            return self.client
        return None

    async def create_client(
        self,
        owner_unit_key: str,
        record: ClientRecord,
        *,
        command: CommandMetadata,
    ) -> ClientRecord:
        if self.write_error:
            raise self.write_error
        self.created_clients.append(record)
        return record

    async def list_projects(self, owner_unit_key: str, *, limit: int) -> Sequence[Project]:
        return (self.project,) if owner_unit_key == self.unit.key else ()

    async def get_project(self, owner_unit_key: str, project_id: UUID) -> Project | None:
        if owner_unit_key == self.unit.key and project_id == PROJECT:
            return self.project
        return None

    async def create_project(
        self,
        owner_unit_key: str,
        project: Project,
        *,
        command: CommandMetadata,
    ) -> Project:
        if self.write_error:
            raise self.write_error
        self.created_projects.append(project)
        return project

    async def list_employees(
        self, employer_unit_key: str, *, limit: int
    ) -> Sequence[EmployeeRecord]:
        return (self.employee,) if employer_unit_key == self.unit.key else ()

    async def get_employee(
        self, employer_unit_key: str, work_relationship_id: UUID
    ) -> EmployeeRecord | None:
        if employer_unit_key == self.unit.key and work_relationship_id == EMPLOYEE:
            return self.employee
        return None

    async def create_employee(
        self,
        employer_unit_key: str,
        record: EmployeeRecord,
        *,
        command: CommandMetadata,
    ) -> EmployeeRecord:
        if self.write_error:
            raise self.write_error
        self.created_employees.append(record)
        return record


def configured(app: FastAPI, policy: Policy, core: CoreStub) -> TestClient:
    app.state.token_verifier = Verifier()
    app.state.identity_mapping = Mapping()
    app.state.authorization = policy
    app.state.core_service = core
    return TestClient(app)


def headers() -> dict[str, str]:
    return {
        "Authorization": "Bearer valid",
        "X-KYA-Unit-ID": "direction-cvsi",
        "Idempotency-Key": "core-test-command-0001",
    }


@pytest.mark.integration
def test_denial_happens_before_client_data_is_loaded(app: FastAPI) -> None:
    core = CoreStub()
    with configured(app, Policy(False), core) as client:
        response = client.get(
            f"/api/v1/core/organization/direction-cvsi/clients/{CLIENT}", headers=headers()
        )

    assert response.status_code == 403
    assert core.client_reads == 0
    assert "Client Démo" not in response.text


@pytest.mark.integration
def test_authorized_client_read_stays_inside_explicit_unit_scope(app: FastAPI) -> None:
    policy = Policy(True)
    core = CoreStub()
    with configured(app, policy, core) as client:
        response = client.get(
            f"/api/v1/core/organization/direction-cvsi/clients/{CLIENT}", headers=headers()
        )

    assert response.status_code == 200
    assert response.json()["display_name"] == "Client Démo"
    assert policy.checks[0].object == "org_unit:direction-cvsi"


@pytest.mark.integration
def test_manager_can_create_client_without_supplying_internal_ids(app: FastAPI) -> None:
    core = CoreStub()
    with configured(app, Policy(True), core) as client:
        response = client.post(
            "/api/v1/core/organization/direction-cvsi/clients",
            headers=headers(),
            json={
                "key": "nouveau-client",
                "party_kind": "organization",
                "display_name": "Nouveau Client SA",
                "status": "prospect",
                "valid_from": "2026-09-07T00:00:00Z",
            },
        )

    assert response.status_code == 201
    assert response.json()["owner_unit_id"] == str(CVSI)
    assert core.created_clients[0].party.display_name == "Nouveau Client SA"


@pytest.mark.integration
def test_write_requires_an_idempotency_key(app: FastAPI) -> None:
    core = CoreStub()
    request_headers = headers()
    request_headers.pop("Idempotency-Key")
    with configured(app, Policy(True), core) as client:
        response = client.post(
            "/api/v1/core/organization/direction-cvsi/clients",
            headers=request_headers,
            json={
                "key": "nouveau-client",
                "party_kind": "organization",
                "display_name": "Nouveau Client SA",
                "valid_from": "2026-09-07T00:00:00Z",
            },
        )

    assert response.status_code == 422
    assert not core.created_clients


@pytest.mark.integration
def test_invalid_naive_business_period_is_rejected_by_contract(app: FastAPI) -> None:
    core = CoreStub()
    with configured(app, Policy(True), core) as client:
        response = client.post(
            "/api/v1/core/organization/direction-cvsi/clients",
            headers=headers(),
            json={
                "key": "client-naive",
                "party_kind": "organization",
                "display_name": "Client Naive",
                "valid_from": "2026-09-07T00:00:00",
            },
        )

    assert response.status_code == 422
    assert not core.created_clients


@pytest.mark.integration
def test_organization_read_list_and_create_contracts(app: FastAPI) -> None:
    core = CoreStub()
    with configured(app, Policy(True), core) as client:
        unit = client.get("/api/v1/core/organization/direction-cvsi", headers=headers())
        missing = client.get("/api/v1/core/organization/inconnue", headers=headers())
        children = client.get(
            "/api/v1/core/organization/groupe-kya/children?limit=10", headers=headers()
        )
        unit_types = client.get(
            "/api/v1/core/organization/groupe-kya/unit-types", headers=headers()
        )
        created = client.post(
            "/api/v1/core/organization/groupe-kya/children",
            headers=headers(),
            json={
                "key": "agence-lome",
                "type_key": "agency",
                "name": "Agence Lomé",
                "valid_from": "2026-09-07T00:00:00Z",
            },
        )

    assert unit.status_code == 200
    assert missing.status_code == 404
    assert children.json()["items"][0]["key"] == "direction-cvsi"
    assert unit_types.json()["items"][1]["label"] == "Filiale"
    assert created.status_code == 201
    assert core.created_units[0].key == "agence-lome"


@pytest.mark.integration
def test_client_lists_and_not_found_are_explicit(app: FastAPI) -> None:
    core = CoreStub()
    with configured(app, Policy(True), core) as client:
        listed = client.get(
            "/api/v1/core/organization/direction-cvsi/clients?limit=10", headers=headers()
        )
        missing = client.get(
            f"/api/v1/core/organization/direction-cvsi/clients/{UUID(int=999)}",
            headers=headers(),
        )

    assert listed.json()["items"][0]["id"] == str(CLIENT)
    assert missing.status_code == 404


@pytest.mark.integration
def test_project_read_list_and_create_contracts(app: FastAPI) -> None:
    core = CoreStub()
    with configured(app, Policy(True), core) as client:
        listed = client.get("/api/v1/core/organization/direction-cvsi/projects", headers=headers())
        found = client.get(
            f"/api/v1/core/organization/direction-cvsi/projects/{PROJECT}", headers=headers()
        )
        missing = client.get(
            f"/api/v1/core/organization/direction-cvsi/projects/{UUID(int=999)}",
            headers=headers(),
        )
        created = client.post(
            "/api/v1/core/organization/direction-cvsi/projects",
            headers=headers(),
            json={
                "key": "audit-energie",
                "name": "Audit énergétique",
                "client_id": str(CLIENT),
                "valid_from": "2026-09-07T00:00:00Z",
            },
        )

    assert listed.json()["items"][0]["id"] == str(PROJECT)
    assert found.status_code == 200
    assert missing.status_code == 404
    assert created.status_code == 201
    assert core.created_projects[0].key == "audit-energie"


@pytest.mark.integration
@pytest.mark.parametrize(
    ("error", "expected_status"),
    [(CoreConflictError("duplicate"), 409), (CoreReferenceError("invalid"), 422)],
)
def test_write_failures_have_stable_http_semantics(
    app: FastAPI, error: Exception, expected_status: int
) -> None:
    core = CoreStub()
    core.write_error = error
    with configured(app, Policy(True), core) as client:
        response = client.post(
            "/api/v1/core/organization/direction-cvsi/projects",
            headers=headers(),
            json={
                "key": "audit-energie",
                "name": "Audit énergétique",
                "valid_from": "2026-09-07T00:00:00Z",
            },
        )

    assert response.status_code == expected_status


@pytest.mark.integration
def test_core_unavailable_is_reported_without_fallback(app: FastAPI) -> None:
    app.state.token_verifier = Verifier()
    app.state.identity_mapping = Mapping()
    app.state.authorization = Policy(True)
    app.state.core_service = None
    with TestClient(app) as client:
        response = client.get("/api/v1/core/organization/direction-cvsi", headers=headers())

    assert response.status_code == 503


@pytest.mark.integration
def test_employee_read_list_and_create_contracts(app: FastAPI) -> None:
    core = CoreStub()
    with configured(app, Policy(True), core) as client:
        listed = client.get("/api/v1/core/organization/direction-cvsi/employees", headers=headers())
        found = client.get(
            f"/api/v1/core/organization/direction-cvsi/employees/{EMPLOYEE}", headers=headers()
        )
        missing = client.get(
            f"/api/v1/core/organization/direction-cvsi/employees/{UUID(int=999)}",
            headers=headers(),
        )
        created = client.post(
            "/api/v1/core/organization/direction-cvsi/employees",
            headers=headers(),
            json={
                "given_name": "Koffi",
                "family_name": "Adjo",
                "valid_from": "2026-09-07T00:00:00Z",
            },
        )

    assert listed.json()["items"][0]["id"] == str(EMPLOYEE)
    assert found.status_code == 200
    assert found.json()["given_name"] == "Afi"
    assert missing.status_code == 404
    assert created.status_code == 201
    assert core.created_employees[0].profile.given_name == "Koffi"
    assert core.created_employees[0].relationship.employer_unit_id == CVSI
