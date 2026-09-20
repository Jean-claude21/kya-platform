"""The document runtime API enforces governed references, workflow and scope."""

from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from kya_platform.application.core import EmployeeRecord
from kya_platform.application.documents import DocumentConflictError, DocumentNotFoundError
from kya_platform.application.documents.runtime import TransitionPlan
from kya_platform.auth import AuthenticatedIdentity
from kya_platform.authorization import AuthorizationDecision, CheckRequest, ListObjectsRequest
from kya_platform.domain.core import (
    ClientAccount,
    ClientStatus,
    Party,
    PartyKind,
    PersonProfile,
    WorkRelationship,
    WorkRelationshipKind,
)
from kya_platform.domain.documents import (
    DocumentDefinition,
    DocumentEvidence,
    DocumentRecord,
    DocumentRevision,
    canonical_digest,
)
from kya_platform.domain.organization import DateRange

ALICE = UUID("01993440-0000-7000-8000-000000000001")
DEFINITION_ID = UUID("01993440-0000-7000-8000-000000000002")
RECORD_ID = UUID("01993440-0000-7000-8000-000000000003")
EMPLOYEE_ID = UUID("01993440-0000-7000-8000-000000000004")
CLIENT_ID = UUID("01993440-0000-7000-8000-000000000005")
NOW = datetime(2026, 9, 19, 11, tzinfo=UTC)

DEFINITION_PATH = (
    Path(__file__).parents[4]
    / "specs"
    / "020-native-document-runtime"
    / "examples"
    / "mission-request.document-type.json"
)


class Verifier:
    async def verify(self, token: str) -> AuthenticatedIdentity:
        return AuthenticatedIdentity("https://auth.example.neon.tech", "alice", {})


class Mapping:
    async def resolve_principal_id(self, identity: AuthenticatedIdentity) -> UUID | None:
        return ALICE


class Policy:
    def __init__(self, allowed: bool = True) -> None:
        self.allowed = allowed
        self.checks: list[CheckRequest] = []

    async def check(self, request: CheckRequest) -> AuthorizationDecision:
        self.checks.append(request)
        return AuthorizationDecision(self.allowed, "documents-model")

    async def list_objects(self, request: ListObjectsRequest) -> tuple[str, ...]:
        return ()


class CoreStub:
    def __init__(self) -> None:
        employee_party = Party(UUID(int=90), PartyKind.PERSON, "Afi Mensah")
        self.employee = EmployeeRecord(
            employee_party,
            PersonProfile(employee_party.id, "Afi", "Mensah"),
            WorkRelationship(
                EMPLOYEE_ID,
                employee_party.id,
                UUID(int=1),
                WorkRelationshipKind.EMPLOYEE,
                DateRange(NOW),
                personnel_number="EMP-42",
            ),
        )
        client_party = Party(UUID(int=91), PartyKind.ORGANIZATION, "Solar Client")
        self.client = type(
            "ClientRecord",
            (),
            {
                "party": client_party,
                "account": ClientAccount(
                    CLIENT_ID,
                    "solar-client",
                    client_party.id,
                    UUID(int=1),
                    ClientStatus.ACTIVE,
                    DateRange(NOW),
                ),
            },
        )()

    async def get_employee(self, unit_key: str, work_relationship_id: UUID):
        return self.employee if work_relationship_id == EMPLOYEE_ID else None

    async def get_client(self, unit_key: str, client_id: UUID):
        return self.client if client_id == CLIENT_ID else None

    async def get_project(self, unit_key: str, project_id: UUID):
        return None


def definition() -> DocumentDefinition:
    payload = DEFINITION_PATH.read_text(encoding="utf-8")
    import json

    document = json.loads(payload)
    return DocumentDefinition(
        id=DEFINITION_ID,
        public_id=document["id"],
        version=document["version"],
        owner_scope="workspace:operations",
        release_id=UUID(int=1),
        definition=document,
        digest=canonical_digest(document),
        published_by=ALICE,
        published_at=NOW,
    )


class DocumentServiceStub:
    def __init__(self) -> None:
        self.records: dict[UUID, tuple[DocumentRecord, DocumentRevision]] = {}
        self.evidence: list[DocumentEvidence] = []
        self.write_error: Exception | None = None

    async def get_definition(self, public_id: str, version: str) -> DocumentDefinition | None:
        candidate = definition()
        return (
            candidate if public_id == candidate.public_id and version == candidate.version else None
        )

    async def get_definition_by_internal_id(self, definition_id: UUID) -> DocumentDefinition | None:
        return definition() if definition_id == DEFINITION_ID else None

    async def create(
        self,
        *,
        record: DocumentRecord,
        revision: DocumentRevision,
        definition_public_id: str,
        definition_version: str,
    ) -> DocumentRecord:
        if self.write_error:
            raise self.write_error
        self.records[record.id] = (record, revision)
        return record

    async def get(
        self, record_id: UUID, *, owner_scope: str
    ) -> tuple[DocumentRecord, DocumentRevision] | None:
        current = self.records.get(record_id)
        if current is None or current[0].owner_scope != owner_scope:
            return None
        return current

    async def history(self, record_id: UUID, *, owner_scope: str) -> tuple[DocumentEvidence, ...]:
        return tuple(self.evidence)

    async def transition(
        self, plan: TransitionPlan, *, owner_scope: str, correlation_id: UUID
    ) -> DocumentRecord:
        record, _revision = self.records[plan.revision.record_id]
        updated = DocumentRecord(
            id=record.id,
            definition_id=record.definition_id,
            owner_scope=record.owner_scope,
            state=plan.to_state,
            current_revision=plan.revision.revision,
            created_by=record.created_by,
            created_at=record.created_at,
            updated_at=plan.revision.created_at,
        )
        self.records[record.id] = (updated, plan.revision)
        self.evidence.append(plan.evidence)
        return updated


def configured(
    app: FastAPI, policy: Policy, documents: DocumentServiceStub, core: CoreStub
) -> TestClient:
    app.state.token_verifier = Verifier()
    app.state.identity_mapping = Mapping()
    app.state.authorization = policy
    app.state.document_service = documents
    app.state.core_service = core
    return TestClient(app)


def headers() -> dict[str, str]:
    return {
        "Authorization": "Bearer valid",
        "X-KYA-Unit-ID": "operations",
        "Idempotency-Key": "documents-test-command-01",
    }


def mission_payload() -> dict[str, object]:
    return {
        "requester": str(EMPLOYEE_ID),
        "client": str(CLIENT_ID),
        "destination": "Kara",
        "purpose": "Site inspection",
        "start_at": "2026-09-22T08:00:00Z",
        "end_at": "2026-09-24T18:00:00Z",
    }


@pytest.mark.integration
def test_create_record_resolves_references_and_persists_the_first_revision(app: FastAPI) -> None:
    documents = DocumentServiceStub()
    with configured(app, Policy(True), documents, CoreStub()) as client:
        response = client.post(
            "/api/v1/documents/records",
            headers=headers(),
            json={
                "definitionId": "kya:document-type:mission-request",
                "definitionVersion": "0.1.0",
                "ownerScope": "workspace:operations",
                "payload": mission_payload(),
            },
        )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["state"] == "draft"

    assert response.status_code == 201, response.text
    assert body["payload"]["requester"]["snapshot"]["display_name"] == "Afi Mensah"
    assert body["payload"]["client"]["snapshot"]["name"] == "Solar Client"


@pytest.mark.integration
def test_create_record_fails_closed_when_reference_is_unauthorized(app: FastAPI) -> None:
    documents = DocumentServiceStub()
    with configured(app, Policy(False), documents, CoreStub()) as client:
        response = client.post(
            "/api/v1/documents/records",
            headers=headers(),
            json={
                "definitionId": "kya:document-type:mission-request",
                "definitionVersion": "0.1.0",
                "ownerScope": "workspace:operations",
                "payload": mission_payload(),
            },
        )

    assert response.status_code == 422
    assert not documents.records


@pytest.mark.integration
def test_create_record_reports_unknown_definition(app: FastAPI) -> None:
    documents = DocumentServiceStub()
    with configured(app, Policy(True), documents, CoreStub()) as client:
        response = client.post(
            "/api/v1/documents/records",
            headers=headers(),
            json={
                "definitionId": "kya:document-type:unknown",
                "definitionVersion": "0.1.0",
                "ownerScope": "workspace:operations",
                "payload": {},
            },
        )

    assert response.status_code == 404


@pytest.mark.integration
def test_get_record_hides_records_outside_scope(app: FastAPI) -> None:
    documents = DocumentServiceStub()
    now = NOW
    record = DocumentRecord(
        id=RECORD_ID,
        definition_id=DEFINITION_ID,
        owner_scope="workspace:operations",
        state="draft",
        current_revision=1,
        created_by=ALICE,
        created_at=now,
        updated_at=now,
    )
    payload = {"purpose": "Site inspection"}
    revision = DocumentRevision(RECORD_ID, 1, payload, canonical_digest(payload), ALICE, now)
    documents.records[RECORD_ID] = (record, revision)
    with configured(app, Policy(True), documents, CoreStub()) as client:
        found = client.get(
            f"/api/v1/documents/records/{RECORD_ID}",
            params={"owner_scope": "workspace:operations"},
            headers=headers(),
        )
        missing = client.get(
            f"/api/v1/documents/records/{RECORD_ID}",
            params={"owner_scope": "workspace:other"},
            headers=headers(),
        )

    assert found.status_code == 200
    assert missing.status_code == 404


@pytest.mark.integration
def test_transition_moves_a_record_through_its_workflow(app: FastAPI) -> None:
    documents = DocumentServiceStub()
    with configured(app, Policy(True), documents, CoreStub()) as client:
        created = client.post(
            "/api/v1/documents/records",
            headers=headers(),
            json={
                "definitionId": "kya:document-type:mission-request",
                "definitionVersion": "0.1.0",
                "ownerScope": "workspace:operations",
                "payload": mission_payload(),
            },
        ).json()
        response = client.post(
            f"/api/v1/documents/records/{created['id']}/transitions",
            params={"owner_scope": "workspace:operations"},
            headers=headers(),
            json={"transitionKey": "submit", "payload": {}},
        )
        history = client.get(
            f"/api/v1/documents/records/{created['id']}/history",
            params={"owner_scope": "workspace:operations"},
            headers=headers(),
        )

    assert response.status_code == 200
    assert response.json()["state"] == "submitted"
    assert history.json()["items"][0]["kind"] == "transition"


@pytest.mark.integration
def test_transition_is_denied_when_the_actor_lacks_permission(app: FastAPI) -> None:
    documents = DocumentServiceStub()
    policy = Policy(True)
    with configured(app, policy, documents, CoreStub()) as client:
        created = client.post(
            "/api/v1/documents/records",
            headers=headers(),
            json={
                "definitionId": "kya:document-type:mission-request",
                "definitionVersion": "0.1.0",
                "ownerScope": "workspace:operations",
                "payload": mission_payload(),
            },
        ).json()
        policy.allowed = False
        response = client.post(
            f"/api/v1/documents/records/{created['id']}/transitions",
            params={"owner_scope": "workspace:operations"},
            headers=headers(),
            json={"transitionKey": "submit", "payload": {}},
        )

    assert response.status_code == 403


@pytest.mark.integration
def test_transition_rejects_invalid_payload_and_unknown_record(app: FastAPI) -> None:
    documents = DocumentServiceStub()
    with configured(app, Policy(True), documents, CoreStub()) as client:
        missing = client.post(
            f"/api/v1/documents/records/{RECORD_ID}/transitions",
            params={"owner_scope": "workspace:operations"},
            headers=headers(),
            json={"transitionKey": "submit", "payload": {}},
        )
        created = client.post(
            "/api/v1/documents/records",
            headers=headers(),
            json={
                "definitionId": "kya:document-type:mission-request",
                "definitionVersion": "0.1.0",
                "ownerScope": "workspace:operations",
                "payload": mission_payload(),
            },
        ).json()
        invalid = client.post(
            f"/api/v1/documents/records/{created['id']}/transitions",
            params={"owner_scope": "workspace:operations"},
            headers=headers(),
            json={"transitionKey": "submit", "payload": {"hidden_admin": True}},
        )

    assert missing.status_code == 404
    assert invalid.status_code == 422


@pytest.mark.integration
@pytest.mark.parametrize(
    ("error", "expected_status"),
    [(DocumentConflictError("duplicate"), 409), (DocumentNotFoundError("missing"), 404)],
)
def test_create_record_write_failures_have_stable_http_semantics(
    app: FastAPI, error: Exception, expected_status: int
) -> None:
    documents = DocumentServiceStub()
    documents.write_error = error
    with configured(app, Policy(True), documents, CoreStub()) as client:
        response = client.post(
            "/api/v1/documents/records",
            headers=headers(),
            json={
                "definitionId": "kya:document-type:mission-request",
                "definitionVersion": "0.1.0",
                "ownerScope": "workspace:operations",
                "payload": mission_payload(),
            },
        )

    assert response.status_code == expected_status


@pytest.mark.integration
def test_document_runtime_unavailable_is_reported_without_fallback(app: FastAPI) -> None:
    app.state.token_verifier = Verifier()
    app.state.identity_mapping = Mapping()
    app.state.authorization = Policy(True)
    app.state.document_service = None
    app.state.core_service = None
    with TestClient(app) as client:
        response = client.get(
            f"/api/v1/documents/records/{RECORD_ID}",
            params={"owner_scope": "workspace:operations"},
            headers=headers(),
        )

    assert response.status_code == 503
