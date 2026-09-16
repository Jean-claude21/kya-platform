"""Intelligence API keeps authorization and evidence boundaries explicit."""

from collections.abc import Sequence
from dataclasses import replace
from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from kya_platform.application.data import CommandMetadata
from kya_platform.application.intelligence import IntelligenceReferenceError
from kya_platform.auth import AuthenticatedIdentity
from kya_platform.authorization import AuthorizationDecision, CheckRequest, ListObjectsRequest
from kya_platform.domain.intelligence import IntelligenceSignal, IntelligenceWatch, WatchEvaluation
from kya_platform.domain.organization import DateRange, OrganizationalUnit

ACTOR = UUID("019934e0-0000-7000-8000-000000000001")
UNIT = UUID("019934e0-0000-7000-8000-000000000002")
WATCH = UUID("019934e0-0000-7000-8000-000000000003")
SIGNAL = UUID("019934e0-0000-7000-8000-000000000004")
CHUNK = UUID("019934e0-0000-7000-8000-000000000005")
SNAPSHOT = UUID("019934e0-0000-7000-8000-000000000006")
NOW = datetime(2026, 9, 8, 18, tzinfo=UTC)


class Verifier:
    async def verify(self, token: str) -> AuthenticatedIdentity:
        return AuthenticatedIdentity("https://auth.example", "actor", {})


class Mapping:
    async def resolve_principal_id(self, identity: AuthenticatedIdentity) -> UUID | None:
        return ACTOR


class Policy:
    def __init__(self, allowed: bool = True) -> None:
        self.allowed = allowed

    async def check(self, request: CheckRequest) -> AuthorizationDecision:
        return AuthorizationDecision(self.allowed, "intelligence-test")

    async def list_objects(self, request: ListObjectsRequest) -> Sequence[str]:
        return ()


class Core:
    async def get_unit(self, key: str) -> OrganizationalUnit | None:
        return (
            OrganizationalUnit(UNIT, "group", "group", "KYA", DateRange(NOW))
            if key == "group"
            else None
        )


class Intelligence:
    def __init__(self) -> None:
        self.watch: IntelligenceWatch | None = None

    async def create_watch(
        self, unit_key: str, watch: IntelligenceWatch, *, command: CommandMetadata
    ) -> IntelligenceWatch:
        self.watch = IntelligenceWatch(
            watch.id,
            watch.key,
            watch.name,
            watch.query,
            watch.owner_unit_id,
            watch.created_by,
            watch.asset_keys,
            created_at=NOW,
            updated_at=NOW,
        )
        return self.watch

    async def list_watches(
        self, unit_key: str, *, limit: int = 20
    ) -> tuple[IntelligenceWatch, ...]:
        return (self.watch,) if self.watch else ()

    async def evaluate_watch(
        self, unit_key: str, watch_key: str, *, limit: int, command: CommandMetadata
    ) -> WatchEvaluation:
        assert self.watch is not None
        signal = IntelligenceSignal(
            SIGNAL,
            WATCH,
            CHUNK,
            SNAPSHOT,
            f"kya:snapshot:{SNAPSHOT}:chunk:{CHUNK}",
            "https://kya-energy.com/solutions",
            "Solaire photovoltaïque",
            NOW,
            "a" * 64,
            "b" * 64,
            "Solutions KYA",
        )
        return WatchEvaluation(self.watch, (signal,), 1)

    async def list_signals(
        self, unit_key: str, watch_key: str, *, only_open: bool = True, limit: int = 20
    ) -> tuple[IntelligenceSignal, ...]:
        if self.watch is None:
            return ()
        return (
            IntelligenceSignal(
                SIGNAL,
                WATCH,
                CHUNK,
                SNAPSHOT,
                f"kya:snapshot:{SNAPSHOT}:chunk:{CHUNK}",
                "https://kya-energy.com/solutions",
                "Solaire photovoltaïque",
                NOW,
                "a" * 64,
                "b" * 64,
            ),
        )

    async def acknowledge_signal(
        self,
        unit_key: str,
        signal_id: UUID,
        *,
        expected_revision: int,
        acknowledged_at: datetime,
        command: CommandMetadata,
    ) -> IntelligenceSignal:
        signal = (await self.list_signals(unit_key, "solar-market"))[0]
        return replace(
            signal,
            status=signal.status.ACKNOWLEDGED,
            acknowledged_by=ACTOR,
            acknowledged_at=acknowledged_at,
            revision=expected_revision + 1,
        )


def configured(app: FastAPI, intelligence: Intelligence, *, allowed: bool = True) -> TestClient:
    app.state.token_verifier = Verifier()
    app.state.identity_mapping = Mapping()
    app.state.authorization = Policy(allowed)
    app.state.core_service = Core()
    app.state.intelligence_service = intelligence
    return TestClient(app)


def headers() -> dict[str, str]:
    return {
        "Authorization": "Bearer valid",
        "X-KYA-Unit-ID": "group",
        "Idempotency-Key": "intelligence-test-command-0001",
    }


@pytest.mark.integration
def test_creates_and_evaluates_watch_with_citable_signal(app: FastAPI) -> None:
    intelligence = Intelligence()
    with configured(app, intelligence) as client:
        created = client.post(
            "/api/v1/intelligence/organization/group/watches",
            headers=headers(),
            json={"key": "solar-market", "name": "Marché solaire", "query": "solaire"},
        )
        evaluated = client.post(
            "/api/v1/intelligence/organization/group/watches/solar-market/evaluate",
            headers=headers(),
        )

    assert created.status_code == 201
    assert evaluated.status_code == 200
    assert evaluated.json()["created_count"] == 1
    assert evaluated.json()["created_signals"][0]["source_uri"].startswith("https://")
    assert evaluated.json()["created_signals"][0]["citation_id"].startswith("kya:snapshot:")


@pytest.mark.integration
def test_denial_precedes_intelligence_mutation(app: FastAPI) -> None:
    intelligence = Intelligence()
    with configured(app, intelligence, allowed=False) as client:
        response = client.post(
            "/api/v1/intelligence/organization/group/watches",
            headers=headers(),
            json={"key": "solar-market", "name": "Marché solaire", "query": "solaire"},
        )
    assert response.status_code == 403
    assert intelligence.watch is None


@pytest.mark.integration
def test_lists_and_acknowledges_signals_without_changing_evidence(app: FastAPI) -> None:
    intelligence = Intelligence()
    with configured(app, intelligence) as client:
        client.post(
            "/api/v1/intelligence/organization/group/watches",
            headers=headers(),
            json={"key": "solar-market", "name": "Marché solaire", "query": "solaire"},
        )
        watches = client.get("/api/v1/intelligence/organization/group/watches", headers=headers())
        signals = client.get(
            "/api/v1/intelligence/organization/group/watches/solar-market/signals",
            headers=headers(),
        )
        acknowledged = client.post(
            f"/api/v1/intelligence/organization/group/signals/{SIGNAL}/acknowledge",
            headers={**headers(), "If-Match": "1"},
        )

    assert watches.json()["items"][0]["query"] == "solaire"
    assert signals.json()["items"][0]["citation_id"].startswith("kya:snapshot:")
    assert acknowledged.json()["status"] == "acknowledged"
    assert acknowledged.json()["revision"] == 2


@pytest.mark.integration
def test_translates_invalid_watch_and_missing_evaluation(app: FastAPI) -> None:
    intelligence = Intelligence()
    intelligence.create_watch = AsyncMock(side_effect=ValueError("invalid watch"))  # type: ignore[method-assign]
    with configured(app, intelligence) as client:
        invalid = client.post(
            "/api/v1/intelligence/organization/group/watches",
            headers=headers(),
            json={"key": "solar-market", "name": "Marché solaire", "query": "solaire"},
        )

    assert invalid.status_code == 422

    intelligence.evaluate_watch = AsyncMock(  # type: ignore[method-assign]
        side_effect=IntelligenceReferenceError("watch does not exist")
    )
    with configured(app, intelligence) as client:
        missing = client.post(
            "/api/v1/intelligence/organization/group/watches/missing/evaluate",
            headers=headers(),
        )

    assert missing.status_code == 404
