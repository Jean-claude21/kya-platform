"""Data MCP exposes bounded, role-filtered and auditable capabilities."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import pytest
from mcp import Client
from mcp.server.auth.provider import AccessToken

from kya_platform.application.data import CommandMetadata, SnapshotLineage
from kya_platform.authorization import AuthorizationDecision, CheckRequest, ListObjectsRequest
from kya_platform.authorization.service import AuthorizationService
from kya_platform.domain.data import (
    DataAsset,
    DataAssetLayer,
    DataClassification,
    DataContract,
    DataPipeline,
    DataSnapshot,
    DataStatus,
    IngestionRun,
    QualityRule,
    StorageObject,
)
from kya_platform.mcp.data.contracts import DATA_TOOLS
from kya_platform.mcp.registry.server import create_registry_server

UNIT = UUID("01993480-0000-7000-8000-000000000001")
ACTOR = UUID("01993480-0000-7000-8000-000000000002")
ASSET = UUID("01993480-0000-7000-8000-000000000003")
CONTRACT = UUID("01993480-0000-7000-8000-000000000004")
PIPELINE = UUID("01993480-0000-7000-8000-000000000005")
SNAPSHOT = UUID("01993480-0000-7000-8000-000000000006")
NOW = datetime(2026, 9, 7, 16, tzinfo=UTC)


@dataclass
class Policy:
    allowed: bool
    checks: list[CheckRequest] = field(default_factory=list)

    async def check(self, request: CheckRequest) -> AuthorizationDecision:
        self.checks.append(request)
        return AuthorizationDecision(self.allowed, "data-mcp-test")

    async def list_objects(self, request: ListObjectsRequest) -> tuple[str, ...]:
        del request
        return ()


class TokenVerifier:
    async def verify_token(self, token: str) -> AccessToken | None:
        del token
        return None


class RegistryBackend:
    async def __getattr__(self, name: str) -> Any:
        raise AssertionError(f"unexpected Registry call: {name}")


@dataclass
class Audit:
    is_available: bool = True
    events: list[dict[str, object]] = field(default_factory=list)

    async def ensure_available(self) -> None:
        if not self.is_available:
            raise RuntimeError("audit unavailable")

    async def record(self, **event: object) -> None:
        self.events.append(event)


class DataBackend:
    def __init__(self) -> None:
        self.commands: list[CommandMetadata] = []
        self.asset = DataAsset(
            ASSET,
            "market-prices",
            "Prix du marché",
            UNIT,
            DataAssetLayer.CURATED,
            DataClassification.INTERNAL,
            DataStatus.ACTIVE,
        )
        self.pipeline = DataPipeline(
            PIPELINE,
            "collect-market-prices",
            "Collecte des prix",
            UNIT,
            UUID("01993480-0000-7000-8000-000000000010"),
            UUID("01993480-0000-7000-8000-000000000011"),
            ASSET,
            DataStatus.ACTIVE,
        )

    async def search_assets(self, unit: str, query: str, *, limit: int) -> tuple[DataAsset, ...]:
        assert unit == "direction-cvsi"
        assert query == "marché"
        assert limit == 3
        return (self.asset,)

    async def get_asset(self, unit: str, key: str) -> DataAsset | None:
        return self.asset if unit == "direction-cvsi" and key == self.asset.key else None

    async def get_contract(
        self, unit: str, key: str, *, version: str | None = None
    ) -> DataContract | None:
        if unit != "direction-cvsi" or key != self.asset.key:
            return None
        return DataContract(
            CONTRACT,
            ASSET,
            version or "1.0.0",
            {"type": "object", "required": ["price"]},
            "b" * 64,
            (QualityRule("price-required", "not-null", "price IS NOT NULL"),),
            60,
            30,
        )

    async def list_snapshots(self, unit: str, key: str, *, limit: int) -> tuple[DataSnapshot, ...]:
        assert unit == "direction-cvsi"
        assert key == self.asset.key
        assert limit == 3
        return (
            DataSnapshot(
                SNAPSHOT,
                ASSET,
                UUID("01993480-0000-7000-8000-000000000020"),
                CONTRACT,
                StorageObject("s3", "private", "secret/internal/path.json", "v1"),
                "c" * 64,
                "application/json",
                NOW,
                42,
                2048,
            ),
        )

    async def trace_lineage(self, unit: str, snapshot_id: UUID) -> SnapshotLineage | None:
        if unit != "direction-cvsi" or snapshot_id != SNAPSHOT:
            return None
        return SnapshotLineage(SNAPSHOT, (UUID(int=1),), (UUID(int=2),))

    async def get_pipeline(self, unit: str, key: str) -> DataPipeline | None:
        return self.pipeline if unit == "direction-cvsi" and key == self.pipeline.key else None

    async def start_run(
        self, unit: str, run: IngestionRun, *, command: CommandMetadata
    ) -> IngestionRun:
        assert unit == "direction-cvsi"
        self.commands.append(command)
        return run


def token(*scopes: str) -> AccessToken:
    return AccessToken(
        token="opaque",
        client_id="claude",
        subject=str(ACTOR),
        scopes=list(scopes),
        claims={"active_unit": "direction-cvsi", "iss": "https://auth.example.test"},
    )


def server(*, policy: Policy, backend: DataBackend, audit: Audit, access_token: AccessToken):
    return create_registry_server(
        backend=RegistryBackend(),  # type: ignore[arg-type]
        authorization=AuthorizationService(policy),
        token_verifier=TokenVerifier(),
        issuer_url="https://auth.example.test",
        resource_url="https://mcp.example.test/mcp",
        access_token_provider=lambda: access_token,
        data_backend=backend,
        data_audit=audit,
    )


@pytest.mark.asyncio
async def test_read_tools_are_advertised_only_when_unit_is_visible() -> None:
    allowed_server = server(
        policy=Policy(True),
        backend=DataBackend(),
        audit=Audit(),
        access_token=token("data:read"),
    )
    async with Client(allowed_server) as client:
        listed = await client.list_tools()
    assert {item.name for item in listed.tools} >= {
        item.name for item in DATA_TOOLS if item.oauth_scope == "data:read"
    }

    denied_server = server(
        policy=Policy(False),
        backend=DataBackend(),
        audit=Audit(),
        access_token=token("data:read"),
    )
    async with Client(denied_server) as client:
        denied = await client.list_tools()
    assert {item.name for item in denied.tools}.isdisjoint({item.name for item in DATA_TOOLS})


@pytest.mark.asyncio
async def test_discovery_is_scoped_structured_and_audited() -> None:
    policy = Policy(True)
    audit = Audit()
    data_server = server(
        policy=policy,
        backend=DataBackend(),
        audit=audit,
        access_token=token("data:read"),
    )
    async with Client(data_server) as client:
        result = await client.call_tool("discover_data_assets", {"query": "marché", "limit": 2})

    assert result.is_error is False
    assert result.structured_content["items"][0]["key"] == "market-prices"
    assert result.structured_content["active_unit"] == "direction-cvsi"
    assert policy.checks[-1].object == "org_unit:direction-cvsi"
    assert audit.events[-1]["decision"] == "allowed"
    assert audit.events[-1]["outcome"] == "succeeded"


@pytest.mark.asyncio
async def test_snapshot_metadata_never_discloses_storage_reference() -> None:
    data_server = server(
        policy=Policy(True),
        backend=DataBackend(),
        audit=Audit(),
        access_token=token("data:read"),
    )
    async with Client(data_server) as client:
        result = await client.call_tool(
            "list_data_snapshots", {"asset_key": "market-prices", "limit": 2}
        )

    serialized = str(result.structured_content)
    assert result.is_error is False
    assert "secret/internal/path.json" not in serialized
    assert "storage" not in serialized
    assert result.structured_content["items"][0]["row_count"] == 42


@pytest.mark.asyncio
async def test_asset_contract_and_lineage_are_structured_and_correlated() -> None:
    audit = Audit()
    data_server = server(
        policy=Policy(True),
        backend=DataBackend(),
        audit=audit,
        access_token=token("data:read"),
    )
    async with Client(data_server) as client:
        asset = await client.call_tool("get_data_asset", {"asset_key": "market-prices"})
        contract = await client.call_tool(
            "get_data_contract", {"asset_key": "market-prices", "version": "1.0.0"}
        )
        lineage = await client.call_tool("trace_data_lineage", {"snapshot_id": str(SNAPSHOT)})

    assert asset.structured_content["classification"] == "internal"
    assert contract.structured_content["quality_rules"][0]["key"] == "price-required"
    assert lineage.structured_content["input_snapshot_ids"] == [str(UUID(int=1))]
    assert len({event["correlation_id"] for event in audit.events}) == 3


@pytest.mark.asyncio
async def test_missing_resource_returns_stable_error_and_failed_audit() -> None:
    audit = Audit()
    backend = DataBackend()
    backend.asset = DataAsset(
        ASSET,
        "other-asset",
        "Autre actif",
        UNIT,
        DataAssetLayer.RAW,
        DataClassification.INTERNAL,
    )
    data_server = server(
        policy=Policy(True),
        backend=backend,
        audit=audit,
        access_token=token("data:read"),
    )
    async with Client(data_server) as client:
        result = await client.call_tool("get_data_asset", {"asset_key": "missing"})

    assert result.is_error is True
    assert "data_asset_not_found" in result.content[0].text
    assert audit.events[-1]["decision"] == "allowed"
    assert audit.events[-1]["outcome"] == "failed"


@pytest.mark.asyncio
async def test_controlled_ingestion_requires_scope_confirmation_and_idempotency() -> None:
    backend = DataBackend()
    audit = Audit()
    data_server = server(
        policy=Policy(True),
        backend=backend,
        audit=audit,
        access_token=token("data:ingest"),
    )
    async with Client(data_server) as client:
        listed = await client.list_tools()
        result = await client.call_tool(
            "start_ingestion",
            {
                "pipeline_key": "collect-market-prices",
                "idempotency_key": "collect-market-20260907",
                "confirmation": {"confirmed": True},
            },
        )

    assert "start_ingestion" in {item.name for item in listed.tools}
    assert result.is_error is False
    assert result.structured_content["status"] == "started"
    assert backend.commands[0].actor_id == ACTOR
    assert backend.commands[0].idempotency_key == "collect-market-20260907"
    assert audit.events[-1]["target_type"] == "data_pipeline"


@pytest.mark.asyncio
async def test_denied_call_is_recorded_without_calling_data_backend() -> None:
    audit = Audit()
    data_server = server(
        policy=Policy(False),
        backend=DataBackend(),
        audit=audit,
        access_token=token("data:read"),
    )
    async with Client(data_server) as client:
        result = await client.call_tool("get_data_asset", {"asset_key": "market-prices"})

    assert result.is_error is True
    assert "not_authorized" in result.content[0].text
    assert audit.events[-1]["decision"] == "denied"
    assert audit.events[-1]["outcome"] == "rejected"
