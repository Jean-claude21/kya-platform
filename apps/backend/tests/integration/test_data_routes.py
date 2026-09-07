"""Data API authorization, canonicalization and server-owned lifecycle tests."""

from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from kya_platform.application.data import CommandMetadata, RunCompletion
from kya_platform.auth import AuthenticatedIdentity
from kya_platform.authorization import AuthorizationDecision, CheckRequest, ListObjectsRequest
from kya_platform.domain.data import (
    DataAsset,
    DataContract,
    DataPipeline,
    DataSnapshot,
    DataSource,
    DataSourceKind,
    DataStatus,
    IngestionRun,
    RunStatus,
    StorageObject,
)
from kya_platform.domain.organization import DateRange, OrganizationalUnit

ALICE = UUID("01993470-0000-7000-8000-000000000001")
UNIT = UUID("01993470-0000-7000-8000-000000000002")
PIPELINE = UUID("01993470-0000-7000-8000-000000000003")
RUN = UUID("01993470-0000-7000-8000-000000000004")
STARTED_AT = datetime(2026, 9, 7, 13, tzinfo=UTC)


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
        return AuthorizationDecision(self.allowed, "data-model")

    async def list_objects(self, request: ListObjectsRequest) -> Sequence[str]:
        return ()


class CoreStub:
    async def get_unit(self, key: str) -> OrganizationalUnit | None:
        if key != "direction-cvsi":
            return None
        return OrganizationalUnit(
            UNIT,
            "direction-cvsi",
            "direction",
            "CVSI",
            DateRange(datetime(2026, 1, 1, tzinfo=UTC)),
        )


class DataStub:
    def __init__(self) -> None:
        self.source_reads = 0
        self.created_source: DataSource | None = None
        self.contract: DataContract | None = None
        self.completion: RunCompletion | None = None
        self.failed: IngestionRun | None = None
        self.started = IngestionRun(RUN, PIPELINE, ALICE, RunStatus.STARTED, STARTED_AT)
        self.snapshots: tuple[DataSnapshot, ...] = ()

    async def list_sources(self, unit_key: str, *, limit: int) -> Sequence[DataSource]:
        self.source_reads += 1
        return ()

    async def create_source(
        self, unit_key: str, source: DataSource, *, command: CommandMetadata
    ) -> DataSource:
        self.created_source = source
        return source

    async def list_assets(self, unit_key: str, *, limit: int) -> Sequence[DataAsset]:
        return ()

    async def create_asset(
        self, unit_key: str, asset: DataAsset, *, command: CommandMetadata
    ) -> DataAsset:
        return asset

    async def publish_contract(
        self, unit_key: str, contract: DataContract, *, command: CommandMetadata
    ) -> DataContract:
        self.contract = contract
        return contract

    async def create_pipeline(
        self, unit_key: str, pipeline: DataPipeline, *, command: CommandMetadata
    ) -> DataPipeline:
        return pipeline

    async def start_run(
        self, unit_key: str, run: IngestionRun, *, command: CommandMetadata
    ) -> IngestionRun:
        return run

    async def get_run(self, unit_key: str, run_id: UUID) -> IngestionRun | None:
        return self.started if run_id == RUN else None

    async def complete_run(
        self, unit_key: str, completion: RunCompletion, *, command: CommandMetadata
    ) -> RunCompletion:
        self.completion = completion
        return completion

    async def fail_run(
        self, unit_key: str, run: IngestionRun, *, command: CommandMetadata
    ) -> IngestionRun:
        self.failed = run
        return run

    async def list_snapshots(
        self, unit_key: str, asset_key: str, *, limit: int
    ) -> Sequence[DataSnapshot]:
        return self.snapshots


def configured(app: FastAPI, policy: Policy, data: DataStub) -> TestClient:
    app.state.token_verifier = Verifier()
    app.state.identity_mapping = Mapping()
    app.state.authorization = policy
    app.state.core_service = CoreStub()
    app.state.data_service = data
    return TestClient(app)


def headers() -> dict[str, str]:
    return {
        "Authorization": "Bearer valid",
        "X-KYA-Unit-ID": "direction-cvsi",
        "Idempotency-Key": "data-test-command-0001",
    }


@pytest.mark.integration
def test_denial_precedes_data_access(app: FastAPI) -> None:
    data = DataStub()
    with configured(app, Policy(False), data) as client:
        response = client.get("/api/v1/data/organization/direction-cvsi/sources", headers=headers())

    assert response.status_code == 403
    assert data.source_reads == 0


@pytest.mark.integration
def test_source_is_created_in_the_authorized_unit(app: FastAPI) -> None:
    data = DataStub()
    with configured(app, Policy(True), data) as client:
        response = client.post(
            "/api/v1/data/organization/direction-cvsi/sources",
            headers=headers(),
            json={
                "key": "market-api",
                "name": "API prix de marché",
                "kind": DataSourceKind.API,
                "secret_reference": "infisical:data/market-api",
                "status": DataStatus.ACTIVE,
            },
        )

    assert response.status_code == 201
    assert response.json()["owner_unit_id"] == str(UNIT)
    assert response.json()["has_credentials"] is True
    assert "secret_reference" not in response.json()
    assert data.created_source is not None
    assert data.created_source.secret_reference == "infisical:data/market-api"


@pytest.mark.integration
def test_contract_digest_is_canonical_and_server_generated(app: FastAPI) -> None:
    data = DataStub()
    asset_id = UUID("01993470-0000-7000-8000-000000000010")
    with configured(app, Policy(True), data) as client:
        response = client.post(
            f"/api/v1/data/organization/direction-cvsi/assets/{asset_id}/contracts",
            headers=headers(),
            json={
                "version": "1.0.0",
                "schema_document": {"type": "object", "required": ["price"]},
                "quality_rules": [
                    {
                        "key": "price-required",
                        "kind": "not-null",
                        "expression": "price IS NOT NULL",
                    }
                ],
                "freshness_minutes": 60,
            },
        )

    assert response.status_code == 201
    assert data.contract is not None
    assert len(data.contract.digest) == 64
    assert data.contract.quality_rules[0].key == "price-required"


@pytest.mark.integration
def test_completion_uses_persisted_run_state_instead_of_client_claims(app: FastAPI) -> None:
    data = DataStub()
    asset_id = UUID("01993470-0000-7000-8000-000000000011")
    contract_id = UUID("01993470-0000-7000-8000-000000000012")
    with configured(app, Policy(True), data) as client:
        response = client.post(
            f"/api/v1/data/organization/direction-cvsi/runs/{RUN}/complete",
            headers=headers(),
            json={
                "asset_id": str(asset_id),
                "contract_id": str(contract_id),
                "storage": {
                    "provider": "neon",
                    "container": "kya-data",
                    "object_key": "raw/market/2026-09-07.json",
                },
                "content_digest": "a" * 64,
                "media_type": "application/json",
                "observed_at": "2026-09-07T13:01:00Z",
            },
        )

    assert response.status_code == 200
    assert data.completion is not None
    assert data.completion.run.pipeline_id == PIPELINE
    assert data.completion.run.started_at == STARTED_AT
    assert data.completion.run.status is RunStatus.COMPLETED


@pytest.mark.integration
def test_asset_pipeline_and_run_commands_form_a_worker_protocol(app: FastAPI) -> None:
    data = DataStub()
    source_id = UUID("01993470-0000-7000-8000-000000000020")
    asset_id = UUID("01993470-0000-7000-8000-000000000021")
    connector_version_id = UUID("01993470-0000-7000-8000-000000000022")
    with configured(app, Policy(True), data) as client:
        asset_response = client.post(
            "/api/v1/data/organization/direction-cvsi/assets",
            headers=headers(),
            json={
                "key": "market-prices-raw",
                "name": "Prix bruts",
                "layer": "raw",
                "classification": "internal",
                "status": "active",
            },
        )
        created_asset_id = asset_response.json()["id"]
        pipeline_response = client.post(
            "/api/v1/data/organization/direction-cvsi/pipelines",
            headers={**headers(), "Idempotency-Key": "data-test-command-0002"},
            json={
                "key": "collect-market-prices",
                "name": "Collecte prix",
                "source_id": str(source_id),
                "connector_version_id": str(connector_version_id),
                "output_asset_id": created_asset_id,
                "status": "active",
            },
        )
        run_response = client.post(
            f"/api/v1/data/organization/direction-cvsi/pipelines/{PIPELINE}/runs",
            headers={**headers(), "Idempotency-Key": "data-test-command-0003"},
        )

    assert asset_response.status_code == 201
    assert UUID(created_asset_id) != asset_id
    assert pipeline_response.status_code == 201
    assert pipeline_response.json()["connector_version_id"] == str(connector_version_id)
    assert run_response.status_code == 201
    assert run_response.json()["status"] == "started"


@pytest.mark.integration
def test_failure_is_server_timestamped_from_persisted_run(app: FastAPI) -> None:
    data = DataStub()
    with configured(app, Policy(True), data) as client:
        response = client.post(
            f"/api/v1/data/organization/direction-cvsi/runs/{RUN}/fail",
            headers=headers(),
            json={"error_code": "source-timeout"},
        )

    assert response.status_code == 200
    assert data.failed is not None
    assert data.failed.status is RunStatus.FAILED
    assert data.failed.started_at == STARTED_AT
    assert data.failed.error_code == "source-timeout"


@pytest.mark.integration
def test_lists_snapshot_metadata_without_a_signed_url(app: FastAPI) -> None:
    data = DataStub()
    asset_id = UUID("01993470-0000-7000-8000-000000000030")
    contract_id = UUID("01993470-0000-7000-8000-000000000031")
    data.snapshots = (
        DataSnapshot(
            UUID("01993470-0000-7000-8000-000000000032"),
            asset_id,
            RUN,
            contract_id,
            StorageObject("neon", "kya-data", "raw/market.json", "v1"),
            "d" * 64,
            "application/json",
            STARTED_AT,
            12,
            640,
        ),
    )
    with configured(app, Policy(True), data) as client:
        source_response = client.get(
            "/api/v1/data/organization/direction-cvsi/sources", headers=headers()
        )
        asset_response = client.get(
            "/api/v1/data/organization/direction-cvsi/assets", headers=headers()
        )
        response = client.get(
            "/api/v1/data/organization/direction-cvsi/assets/market-prices-raw/snapshots",
            headers=headers(),
        )

    assert source_response.status_code == 200
    assert asset_response.status_code == 200
    assert response.status_code == 200
    assert response.json()["items"][0]["storage"]["object_key"] == "raw/market.json"
    assert "http" not in response.text


@pytest.mark.integration
def test_unknown_run_returns_not_found_before_terminal_command(app: FastAPI) -> None:
    data = DataStub()
    unknown = UUID("01993470-0000-7000-8000-000000000099")
    with configured(app, Policy(True), data) as client:
        complete = client.post(
            f"/api/v1/data/organization/direction-cvsi/runs/{unknown}/complete",
            headers=headers(),
            json={
                "asset_id": str(unknown),
                "contract_id": str(unknown),
                "storage": {
                    "provider": "neon",
                    "container": "kya-data",
                    "object_key": "raw/unknown.json",
                },
                "content_digest": "e" * 64,
                "media_type": "application/json",
                "observed_at": "2026-09-07T13:01:00Z",
            },
        )
        failed = client.post(
            f"/api/v1/data/organization/direction-cvsi/runs/{unknown}/fail",
            headers=headers(),
            json={"error_code": "not-found"},
        )

    assert complete.status_code == 404
    assert failed.status_code == 404
