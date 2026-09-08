"""Source-flow API is authorized, atomic at its boundary and secret-free."""

from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from kya_platform.application.data import CommandMetadata
from kya_platform.auth import AuthenticatedIdentity
from kya_platform.authorization import AuthorizationDecision, CheckRequest, ListObjectsRequest
from kya_platform.domain.data import DataPipeline, DataStatus
from kya_platform.domain.organization import DateRange, OrganizationalUnit
from kya_platform.domain.source_lifecycle import (
    IngestionSchedule,
    SourceFlow,
    SourceFlowDraft,
    SourceFlowHealth,
)

ACTOR = UUID("019934b0-0000-7000-8000-000000000001")
UNIT = UUID("019934b0-0000-7000-8000-000000000002")
CONNECTOR_VERSION = UUID("019934b0-0000-7000-8000-000000000003")
NOW = datetime(2026, 9, 8, 14, tzinfo=UTC)


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
        return AuthorizationDecision(self.allowed, "source-flow-model")

    async def list_objects(self, request: ListObjectsRequest) -> Sequence[str]:
        return ()


class Core:
    async def get_unit(self, key: str) -> OrganizationalUnit | None:
        if key != "group":
            return None
        return OrganizationalUnit(UNIT, "group", "group", "KYA", DateRange(NOW))


class Lifecycle:
    def __init__(self) -> None:
        self.draft: SourceFlowDraft | None = None
        self.flow: SourceFlow | None = None

    async def configure(
        self,
        unit_key: str,
        draft: SourceFlowDraft,
        *,
        schedule: IngestionSchedule | None,
        command: CommandMetadata,
    ) -> SourceFlow:
        self.draft = draft
        pipeline = DataPipeline(
            draft.pipeline.id,
            draft.pipeline.key,
            draft.pipeline.name,
            draft.pipeline.owner_unit_id,
            draft.pipeline.source_id,
            CONNECTOR_VERSION,
            draft.pipeline.output_asset_id,
            draft.pipeline.status,
        )
        bound_schedule = (
            IngestionSchedule(
                schedule.id,
                pipeline.id,
                schedule.interval_minutes,
                schedule.next_run_at,
                schedule.enabled,
            )
            if schedule is not None
            else None
        )
        self.flow = SourceFlow(
            pipeline.key,
            draft.source,
            draft.asset,
            draft.contract,
            pipeline,
            1,
            bound_schedule,
        )
        return self.flow

    async def get_health(self, unit_key: str, flow_key: str) -> SourceFlowHealth | None:
        return SourceFlowHealth(self.flow) if self.flow is not None else None

    async def transition(
        self,
        unit_key: str,
        flow_key: str,
        status: DataStatus,
        *,
        expected_revision: int,
        command: CommandMetadata,
    ) -> SourceFlow:
        assert self.flow is not None
        source = self.flow.source.__class__(
            self.flow.source.id,
            self.flow.source.key,
            self.flow.source.name,
            self.flow.source.kind,
            self.flow.source.owner_unit_id,
            self.flow.source.system_artifact_id,
            self.flow.source.secret_reference,
            status,
            self.flow.source.configuration,
        )
        asset = self.flow.asset.__class__(
            self.flow.asset.id,
            self.flow.asset.key,
            self.flow.asset.name,
            self.flow.asset.owner_unit_id,
            self.flow.asset.layer,
            self.flow.asset.classification,
            status,
        )
        pipeline = self.flow.pipeline.__class__(
            self.flow.pipeline.id,
            self.flow.pipeline.key,
            self.flow.pipeline.name,
            self.flow.pipeline.owner_unit_id,
            self.flow.pipeline.source_id,
            self.flow.pipeline.connector_version_id,
            self.flow.pipeline.output_asset_id,
            status,
        )
        self.flow = SourceFlow(
            flow_key,
            source,
            asset,
            self.flow.contract,
            pipeline,
            expected_revision + 1,
            self.flow.schedule,
        )
        return self.flow

    async def put_schedule(
        self,
        unit_key: str,
        flow_key: str,
        schedule: IngestionSchedule,
        *,
        expected_revision: int,
        command: CommandMetadata,
    ) -> SourceFlow:
        assert self.flow is not None
        bound = IngestionSchedule(
            schedule.id,
            self.flow.pipeline.id,
            schedule.interval_minutes,
            schedule.next_run_at,
            schedule.enabled,
            1,
        )
        self.flow = SourceFlow(
            flow_key,
            self.flow.source,
            self.flow.asset,
            self.flow.contract,
            self.flow.pipeline,
            expected_revision + 1,
            bound,
        )
        return self.flow


def configured(app: FastAPI, lifecycle: Lifecycle, *, allowed: bool = True) -> TestClient:
    app.state.token_verifier = Verifier()
    app.state.identity_mapping = Mapping()
    app.state.authorization = Policy(allowed)
    app.state.core_service = Core()
    app.state.source_lifecycle_service = lifecycle
    return TestClient(app)


def headers(**extra: str) -> dict[str, str]:
    return {
        "Authorization": "Bearer valid",
        "X-KYA-Unit-ID": "group",
        "Idempotency-Key": "source-flow-test-command-0001",
        **extra,
    }


def payload() -> dict[str, object]:
    return {
        "key": "kya-public-web",
        "name": "Site public KYA",
        "source": {
            "kind": "web",
            "configuration": {
                "seed_url": "https://kya-energy.com/fr",
                "allowed_hosts": ["kya-energy.com"],
            },
            "secret_reference": "infisical:data/kya-web",
        },
        "connector": {"key": "kya-owned-web-connector", "version": "0.1.0"},
        "asset": {"layer": "raw", "classification": "public"},
        "contract": {"version": "1.0.0", "schema_document": {"type": "object"}},
        "schedule": {
            "interval_minutes": 1440,
            "next_run_at": "2026-09-09T06:00:00Z",
        },
    }


@pytest.mark.integration
def test_configures_complete_flow_without_exposing_secret_reference(app: FastAPI) -> None:
    lifecycle = Lifecycle()
    with configured(app, lifecycle) as client:
        response = client.post(
            "/api/v1/data/organization/group/flows", headers=headers(), json=payload()
        )

    assert response.status_code == 201
    assert response.json()["source_key"] == "kya-public-web-source"
    assert response.json()["asset_key"] == "kya-public-web-raw"
    assert response.json()["connector_version_id"] == str(CONNECTOR_VERSION)
    assert response.json()["has_credentials"] is True
    assert "secret_reference" not in response.text
    assert lifecycle.draft is not None
    assert lifecycle.draft.connector_key == "kya-owned-web-connector"


@pytest.mark.integration
def test_reads_health_and_pauses_with_optimistic_revision(app: FastAPI) -> None:
    lifecycle = Lifecycle()
    with configured(app, lifecycle) as client:
        created = client.post(
            "/api/v1/data/organization/group/flows", headers=headers(), json=payload()
        )
        health = client.get(
            "/api/v1/data/organization/group/flows/kya-public-web", headers=headers()
        )
        paused = client.post(
            "/api/v1/data/organization/group/flows/kya-public-web/pause",
            headers=headers(**{"If-Match": str(created.json()["revision"])}),
        )

    assert health.status_code == 200
    assert health.json()["flow"]["schedule"]["interval_minutes"] == 1440
    assert paused.status_code == 200
    assert paused.json()["status"] == "paused"
    assert paused.json()["revision"] == 2


@pytest.mark.integration
def test_authorization_denial_precedes_lifecycle_access(app: FastAPI) -> None:
    lifecycle = Lifecycle()
    with configured(app, lifecycle, allowed=False) as client:
        response = client.post(
            "/api/v1/data/organization/group/flows", headers=headers(), json=payload()
        )

    assert response.status_code == 403
    assert lifecycle.draft is None


@pytest.mark.integration
def test_replaces_schedule_without_internal_pipeline_identifier(app: FastAPI) -> None:
    lifecycle = Lifecycle()
    with configured(app, lifecycle) as client:
        created = client.post(
            "/api/v1/data/organization/group/flows", headers=headers(), json=payload()
        )
        response = client.put(
            "/api/v1/data/organization/group/flows/kya-public-web/schedule",
            headers=headers(**{"If-Match": str(created.json()["revision"])}),
            json={
                "interval_minutes": 60,
                "next_run_at": "2026-09-08T16:00:00Z",
                "enabled": False,
            },
        )

    assert response.status_code == 200
    assert response.json()["revision"] == 2
    assert response.json()["schedule"]["interval_minutes"] == 60
    assert response.json()["schedule"]["enabled"] is False
