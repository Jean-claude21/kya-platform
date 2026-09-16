from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from kya_platform.auth import AuthenticatedIdentity
from kya_platform.authorization import AuthorizationDecision, CheckRequest, ListObjectsRequest
from kya_platform.domain.organization import DateRange
from kya_platform.domain.systems import (
    ApprovedInterface,
    AvailabilityLevel,
    DataAuthority,
    InterfaceKind,
    RegisteredSystem,
    SystemStatus,
)

ALICE = UUID("019914b2-1a40-7000-8000-000000000031")


class AcceptingVerifier:
    async def verify(self, token: str) -> AuthenticatedIdentity:
        return AuthenticatedIdentity("https://auth.example.neon.tech", "alice", {})


class AliceMapping:
    async def resolve_principal_id(self, identity: AuthenticatedIdentity) -> UUID | None:
        return ALICE


class SystemPolicy:
    def __init__(self, *, allowed: bool, listed: tuple[str, ...] = ()) -> None:
        self.allowed = allowed
        self.listed = listed

    async def check(self, request: CheckRequest) -> AuthorizationDecision:
        return AuthorizationDecision(self.allowed, "01MODEL")

    async def list_objects(self, request: ListObjectsRequest) -> tuple[str, ...]:
        return self.listed


def registered_system(key: str) -> RegisteredSystem:
    return RegisteredSystem(
        uuid4(),
        key,
        key.upper(),
        "DSC",
        "CVSI",
        SystemStatus.ACTIVE,
        frozenset({"production"}),
        (
            ApprovedInterface(
                "REST",
                InterfaceKind.REST_API,
                "https://erp.kya.energy/api/resource",
                True,
            ),
            ApprovedInterface(
                "Interface en évaluation",
                InterfaceKind.WEBHOOK,
                "catalog://not-approved",
                False,
            ),
        ),
        AvailabilityLevel.BUSINESS_HOURS,
    )


class SystemQueries:
    def __init__(self) -> None:
        self.frappe = registered_system("frappe-erpnext")
        self.hidden = registered_system("hidden-system")
        self.loaded_keys: tuple[str, ...] | None = None
        self.authority = DataAuthority(
            uuid4(),
            "clients",
            self.frappe.id,
            "group:kya",
            DateRange(datetime(2026, 9, 1, tzinfo=UTC)),
        )

    async def get(self, system_key: str) -> RegisteredSystem | None:
        return {self.frappe.key: self.frappe, self.hidden.key: self.hidden}.get(system_key)

    async def list_by_keys(self, system_keys: tuple[str, ...]) -> tuple[RegisteredSystem, ...]:
        self.loaded_keys = system_keys
        return tuple(system for system in (self.frappe, self.hidden) if system.key in system_keys)

    async def resolve_authority(
        self, category_key: str, scope: str, at: datetime
    ) -> tuple[DataAuthority, RegisteredSystem] | None:
        if category_key == "clients" and scope == "group:kya":
            return self.authority, self.frappe
        return None


def configure(app: FastAPI, policy: SystemPolicy, queries: SystemQueries) -> TestClient:
    app.state.token_verifier = AcceptingVerifier()
    app.state.identity_mapping = AliceMapping()
    app.state.authorization = policy
    app.state.system_queries = queries
    return TestClient(app)


def headers() -> dict[str, str]:
    return {"Authorization": "Bearer valid", "X-KYA-Unit-ID": "direction-cvsi"}


@pytest.mark.integration
def test_system_list_filters_identifiers_before_loading_records(app: FastAPI) -> None:
    queries = SystemQueries()
    policy = SystemPolicy(allowed=True, listed=("system:frappe-erpnext",))

    with configure(app, policy, queries) as client:
        response = client.get("/api/v1/systems", headers=headers())

    assert response.status_code == 200
    assert queries.loaded_keys == ("frappe-erpnext",)
    assert [item["key"] for item in response.json()["items"]] == ["frappe-erpnext"]
    assert "hidden-system" not in response.text


@pytest.mark.integration
def test_system_response_exposes_only_approved_interfaces(app: FastAPI) -> None:
    queries = SystemQueries()

    with configure(app, SystemPolicy(allowed=True), queries) as client:
        response = client.get("/api/v1/systems/frappe-erpnext", headers=headers())

    assert response.status_code == 200
    assert [item["name"] for item in response.json()["interfaces"]] == ["REST"]
    assert "not-approved" not in response.text


@pytest.mark.integration
def test_authority_resolution_is_permission_protected(app: FastAPI) -> None:
    queries = SystemQueries()
    path = "/api/v1/systems/authorities/clients/resolve?scope=group:kya"

    with configure(app, SystemPolicy(allowed=False), queries) as client:
        denied = client.get(path, headers=headers())
    with configure(app, SystemPolicy(allowed=True), queries) as client:
        allowed = client.get(path, headers=headers())

    assert denied.status_code == 403
    assert allowed.status_code == 200
    assert allowed.json()["system"]["key"] == "frappe-erpnext"
    assert allowed.json()["category_key"] == "clients"
