"""The audit API filters workspaces and protected content before serialization."""

from datetime import UTC, datetime
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from kya_platform.application.audit import (
    AuditEvent,
    AuditQueryService,
    AuditWriter,
    InMemoryAuditRepository,
)
from kya_platform.auth import AuthenticatedIdentity
from kya_platform.authorization import AuthorizationDecision, CheckRequest, ListObjectsRequest

ALICE = UUID("01991a00-0000-7000-8000-000000000021")
EVENT_ID = UUID("01991a00-0000-7000-8000-000000000022")
CORRELATION = UUID("01991a00-0000-7000-8000-000000000023")


class AcceptingVerifier:
    async def verify(self, token: str) -> AuthenticatedIdentity:
        return AuthenticatedIdentity("https://auth.example.neon.tech", "alice", {})


class AliceMapping:
    async def resolve_principal_id(self, identity: AuthenticatedIdentity) -> UUID | None:
        return ALICE


class AuditPolicy:
    def __init__(self, *, may_audit: bool, may_view_content: bool = False) -> None:
        self.may_audit = may_audit
        self.may_view_content = may_view_content
        self.checks: list[CheckRequest] = []

    async def check(self, request: CheckRequest) -> AuthorizationDecision:
        self.checks.append(request)
        allowed = (
            self.may_view_content
            if request.relation == "can_view_audit_content"
            else self.may_audit
        )
        return AuthorizationDecision(allowed=allowed, model_id="01AUDITMODEL")

    async def list_objects(self, request: ListObjectsRequest) -> tuple[str, ...]:
        return ()


async def audit_service() -> AuditQueryService:
    repository = InMemoryAuditRepository()
    await AuditWriter(repository).append(
        AuditEvent(
            id=EVENT_ID,
            occurred_at=datetime(2026, 9, 5, 9, tzinfo=UTC),
            actor_id=ALICE,
            actor_context={"active_unit": "direction-cvsi"},
            action="artifact.publish",
            target_type="artifact",
            target_id="kya:skill:document-standard",
            scope="workspace:platform",
            environment="test",
            decision="allowed",
            outcome="succeeded",
            correlation_id=CORRELATION,
            metadata={"version": "1.0.0"},
            protected_content={"review_note": "Confidentiel Direction"},
        )
    )
    return AuditQueryService(repository)


async def configure(app: FastAPI, policy: AuditPolicy) -> TestClient:
    app.state.token_verifier = AcceptingVerifier()
    app.state.identity_mapping = AliceMapping()
    app.state.authorization = policy
    app.state.audit_queries = await audit_service()
    return TestClient(app)


def headers() -> dict[str, str]:
    return {"Authorization": "Bearer valid", "X-KYA-Unit-ID": "direction-cvsi"}


@pytest.mark.integration
@pytest.mark.asyncio
async def test_auditor_receives_metadata_without_protected_content(app: FastAPI) -> None:
    policy = AuditPolicy(may_audit=True)
    with await configure(app, policy) as client:
        response = client.get("/api/v1/audit/workspaces/platform/events", headers=headers())

    assert response.status_code == 200
    assert response.json()["content_mode"] == "metadata_only"
    assert response.json()["items"][0]["protected_content"] is None
    assert "Confidentiel Direction" not in response.text
    assert policy.checks[0].object == "workspace:platform"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_technical_admin_cannot_escalate_to_business_content(app: FastAPI) -> None:
    with await configure(app, AuditPolicy(may_audit=True, may_view_content=False)) as client:
        response = client.get(
            "/api/v1/audit/workspaces/platform/events?include_protected_content=true",
            headers=headers(),
        )

    assert response.status_code == 403
    assert response.json()["code"] == "audit_content_permission_denied"
    assert "Confidentiel Direction" not in response.text


@pytest.mark.integration
@pytest.mark.asyncio
async def test_business_auditor_with_both_mandates_can_view_content(app: FastAPI) -> None:
    policy = AuditPolicy(may_audit=True, may_view_content=True)
    with await configure(app, policy) as client:
        response = client.get(
            "/api/v1/audit/workspaces/platform/events?include_protected_content=true",
            headers=headers(),
        )

    assert response.status_code == 200
    assert response.json()["content_mode"] == "protected"
    assert response.json()["items"][0]["protected_content"] == {
        "review_note": "Confidentiel Direction"
    }


@pytest.mark.integration
@pytest.mark.asyncio
async def test_unmandated_workspace_is_denied_before_audit_repository_query(app: FastAPI) -> None:
    with await configure(app, AuditPolicy(may_audit=False)) as client:
        response = client.get(
            "/api/v1/audit/workspaces/direction-generale/events", headers=headers()
        )

    assert response.status_code == 403
    assert response.json()["code"] == "permission_denied"
    assert str(EVENT_ID) not in response.text
