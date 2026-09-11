"""Negative workspace journeys prove filtering and direct-access denial."""

from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from kya_platform.auth import AuthenticatedIdentity
from kya_platform.authorization import AuthorizationDecision, CheckRequest, ListObjectsRequest
from kya_platform.domain.organization import DateRange
from kya_platform.domain.workspaces import (
    AccessLevel,
    Workspace,
    WorkspaceKind,
    WorkspaceMembership,
)

ALICE = UUID("019914b2-1a40-7000-8000-000000000031")
CVSI = UUID("019914b2-1a40-7000-8000-000000000043")
PLATFORM = UUID("019914b2-1a40-7000-8000-000000000071")


class AcceptingVerifier:
    async def verify(self, token: str) -> AuthenticatedIdentity:
        return AuthenticatedIdentity("https://auth.example.neon.tech", "alice", {})


class AliceMapping:
    async def resolve_principal_id(self, identity: AuthenticatedIdentity) -> UUID | None:
        return ALICE


class ContextPolicy:
    """A deterministic stand-in for the tested OpenFGA matrix."""

    def __init__(self, *, direct_allowed: bool, listed: Sequence[str] = ()) -> None:
        self.direct_allowed = direct_allowed
        self.listed = listed
        self.checks: list[CheckRequest] = []

    async def check(self, request: CheckRequest) -> AuthorizationDecision:
        self.checks.append(request)
        active_units = {item.object for item in request.contextual_tuples}
        allowed = self.direct_allowed and "org_unit:direction-cvsi" in active_units
        return AuthorizationDecision(allowed=allowed, model_id="01MODEL")

    async def list_objects(self, request: ListObjectsRequest) -> Sequence[str]:
        active_units = {item.object for item in request.contextual_tuples}
        if "org_unit:direction-cvsi" not in active_units:
            return ()
        return self.listed


class WorkspaceQueries:
    def __init__(self) -> None:
        self.records = {
            "platform": Workspace(
                PLATFORM,
                "platform",
                "KYA Platform",
                WorkspaceKind.TEAM,
                DateRange(datetime(2026, 9, 1, tzinfo=UTC)),
                CVSI,
                frozenset({CVSI}),
            ),
            "restricted": Workspace(
                UUID("019914b2-1a40-7000-8000-000000000072"),
                "restricted",
                "Direction générale",
                WorkspaceKind.RESTRICTED,
                DateRange(datetime(2026, 9, 1, tzinfo=UTC)),
            ),
        }
        self.memberships: dict[UUID, tuple[WorkspaceMembership, ...]] = {}

    async def get(self, workspace_key: str) -> Workspace | None:
        return self.records.get(workspace_key)

    async def list_by_keys(self, workspace_keys: Sequence[str]) -> Sequence[Workspace]:
        return tuple(self.records[key] for key in workspace_keys if key in self.records)

    async def list_memberships(self, workspace_id: UUID) -> Sequence[WorkspaceMembership]:
        return self.memberships.get(workspace_id, ())


class WorkspaceCommands:
    def __init__(self) -> None:
        self.created: list[tuple[WorkspaceMembership, UUID]] = []

    async def add_membership(
        self, membership: WorkspaceMembership, *, actor_id: UUID
    ) -> WorkspaceMembership:
        self.created.append((membership, actor_id))
        return membership


def configure(
    app: FastAPI, policy: ContextPolicy, commands: WorkspaceCommands | None = None
) -> TestClient:
    app.state.token_verifier = AcceptingVerifier()
    app.state.identity_mapping = AliceMapping()
    app.state.authorization = policy
    app.state.workspace_queries = WorkspaceQueries()
    app.state.workspace_commands = commands
    return TestClient(app)


def headers(unit: str = "direction-cvsi") -> dict[str, str]:
    return {"Authorization": "Bearer valid", "X-KYA-Unit-ID": unit}


@pytest.mark.integration
def test_direct_workspace_access_is_denied_without_disclosing_resource(app: FastAPI) -> None:
    with configure(app, ContextPolicy(direct_allowed=False)) as client:
        response = client.get("/api/v1/workspaces/restricted", headers=headers())

    assert response.status_code == 403
    assert response.json()["code"] == "permission_denied"
    assert "Direction générale" not in response.text


@pytest.mark.integration
def test_workspace_list_is_filtered_before_records_are_loaded(app: FastAPI) -> None:
    policy = ContextPolicy(direct_allowed=True, listed=("workspace:platform",))
    with configure(app, policy) as client:
        response = client.get("/api/v1/workspaces", headers=headers())

    assert response.status_code == 200
    assert [item["key"] for item in response.json()["items"]] == ["platform"]
    assert "restricted" not in response.text


@pytest.mark.integration
def test_wrong_active_context_returns_an_empty_list_and_denies_direct_access(app: FastAPI) -> None:
    policy = ContextPolicy(direct_allowed=True, listed=("workspace:platform",))
    with configure(app, policy) as client:
        listed = client.get("/api/v1/workspaces", headers=headers("direction-communication"))
        direct = client.get(
            "/api/v1/workspaces/platform", headers=headers("direction-communication")
        )

    assert listed.status_code == 200
    assert listed.json() == {"items": []}
    assert direct.status_code == 403


@pytest.mark.integration
def test_membership_mutation_requires_manage_permission(app: FastAPI) -> None:
    with configure(app, ContextPolicy(direct_allowed=False)) as client:
        response = client.post(
            "/api/v1/workspaces/platform/memberships",
            headers=headers(),
            json={
                "principal_id": str(ALICE),
                "level": "viewer",
                "valid_from": "2026-09-01T00:00:00Z",
            },
        )

    assert response.status_code == 403
    assert response.json()["code"] == "permission_denied"
    assert "principal_id" not in response.text


@pytest.mark.integration
def test_manager_can_add_a_dated_membership(app: FastAPI) -> None:
    commands = WorkspaceCommands()
    with configure(app, ContextPolicy(direct_allowed=True), commands) as client:
        response = client.post(
            "/api/v1/workspaces/platform/memberships",
            headers=headers(),
            json={
                "principal_id": str(ALICE),
                "level": "viewer",
                "valid_from": "2026-09-01T00:00:00Z",
                "valid_until": "2026-10-01T00:00:00Z",
            },
        )

    assert response.status_code == 201
    assert response.json()["workspace_id"] == str(PLATFORM)
    assert commands.created[0][1] == ALICE


@pytest.mark.integration
def test_authorized_unknown_workspace_has_a_stable_not_found_response(app: FastAPI) -> None:
    with configure(app, ContextPolicy(direct_allowed=True)) as client:
        response = client.get("/api/v1/workspaces/unknown", headers=headers())

    assert response.status_code == 404
    assert response.json()["code"] == "workspace_not_found"


@pytest.mark.integration
def test_memberships_require_can_view_and_are_denied_without_disclosure(app: FastAPI) -> None:
    with configure(app, ContextPolicy(direct_allowed=False)) as client:
        response = client.get("/api/v1/workspaces/platform/memberships", headers=headers())

    assert response.status_code == 403
    assert response.json()["code"] == "permission_denied"


@pytest.mark.integration
def test_memberships_are_listed_for_an_authorized_viewer(app: FastAPI) -> None:
    queries = WorkspaceQueries()
    queries.memberships[PLATFORM] = (
        WorkspaceMembership(
            workspace_id=PLATFORM,
            principal_id=ALICE,
            level=AccessLevel.VIEWER,
            validity=DateRange(datetime(2026, 9, 1, tzinfo=UTC)),
        ),
    )
    app.state.token_verifier = AcceptingVerifier()
    app.state.identity_mapping = AliceMapping()
    app.state.authorization = ContextPolicy(direct_allowed=True)
    app.state.workspace_queries = queries
    app.state.workspace_commands = None
    with TestClient(app) as client:
        response = client.get("/api/v1/workspaces/platform/memberships", headers=headers())

    assert response.status_code == 200
    assert response.json() == {
        "items": [
            {
                "workspace_id": str(PLATFORM),
                "principal_id": str(ALICE),
                "level": "viewer",
                "valid_from": "2026-09-01T00:00:00Z",
                "valid_until": None,
            }
        ]
    }
