"""KYA Intelligence MCP tools expose governed evidence, not model conclusions."""

from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import UUID

import pytest
from mcp import Client
from mcp.server.auth.provider import AccessToken

from kya_platform.application.data import CommandMetadata
from kya_platform.authorization import AuthorizationDecision, CheckRequest, ListObjectsRequest
from kya_platform.authorization.service import AuthorizationService
from kya_platform.domain.intelligence import IntelligenceSignal, IntelligenceWatch, WatchEvaluation
from kya_platform.mcp.registry.server import create_registry_server

ACTOR = UUID("019934e1-0000-7000-8000-000000000001")
UNIT = UUID("019934e1-0000-7000-8000-000000000002")
WATCH = UUID("019934e1-0000-7000-8000-000000000003")
SIGNAL = UUID("019934e1-0000-7000-8000-000000000004")
CHUNK = UUID("019934e1-0000-7000-8000-000000000005")
SNAPSHOT = UUID("019934e1-0000-7000-8000-000000000006")
NOW = datetime(2026, 9, 8, 18, tzinfo=UTC)


class Policy:
    async def check(self, request: CheckRequest) -> AuthorizationDecision:
        return AuthorizationDecision(True, "intelligence-mcp-test")

    async def list_objects(self, request: ListObjectsRequest) -> tuple[str, ...]:
        return ()


class TokenVerifier:
    async def verify_token(self, token: str) -> AccessToken | None:
        return None


@dataclass
class Audit:
    events: list[dict[str, object]] = field(default_factory=list)

    async def ensure_available(self) -> None:
        return None

    async def record(self, **event: object) -> None:
        self.events.append(event)


class IntelligenceBackend:
    def __init__(self) -> None:
        self.watch = IntelligenceWatch(
            WATCH, "solar-market", "Marché solaire", "solaire", UNIT, ACTOR
        )
        self.signal = IntelligenceSignal(
            SIGNAL,
            WATCH,
            CHUNK,
            SNAPSHOT,
            f"kya:snapshot:{SNAPSHOT}:chunk:{CHUNK}",
            "https://kya-energy.com/solutions",
            "Solutions solaires autonomes",
            NOW,
            "a" * 64,
            "b" * 64,
            "Solutions KYA",
        )
        self.commands: list[CommandMetadata] = []

    async def resolve_unit_id(self, unit_key: str) -> UUID | None:
        return UNIT if unit_key == "group" else None

    async def create_watch(
        self, unit_key: str, watch: IntelligenceWatch, *, command: CommandMetadata
    ) -> IntelligenceWatch:
        self.commands.append(command)
        return watch

    async def list_watches(self, unit_key: str, *, limit: int) -> tuple[IntelligenceWatch, ...]:
        return (self.watch,)

    async def evaluate_watch(
        self, unit_key: str, watch_key: str, *, limit: int, command: CommandMetadata
    ) -> WatchEvaluation:
        self.commands.append(command)
        return WatchEvaluation(self.watch, (self.signal,), 1)

    async def list_signals(
        self, unit_key: str, watch_key: str, *, only_open: bool, limit: int
    ) -> tuple[IntelligenceSignal, ...]:
        return (self.signal,)

    async def acknowledge_signal(
        self,
        unit_key: str,
        signal_id: UUID,
        *,
        expected_revision: int,
        acknowledged_at: datetime,
        command: CommandMetadata,
    ) -> IntelligenceSignal:
        self.commands.append(command)
        return replace(
            self.signal,
            status=self.signal.status.ACKNOWLEDGED,
            acknowledged_by=ACTOR,
            acknowledged_at=acknowledged_at,
            revision=expected_revision + 1,
        )


def token(*scopes: str) -> AccessToken:
    return AccessToken(
        token="opaque",
        client_id="claude",
        subject=str(ACTOR),
        scopes=list(scopes),
        claims={"active_unit": "group", "iss": "https://auth.example.test"},
    )


def server(backend: IntelligenceBackend, audit: Audit):
    access_token = token("data:read", "data:ingest")
    return create_registry_server(
        backend=AsyncMock(),
        authorization=AuthorizationService(Policy()),
        token_verifier=TokenVerifier(),
        issuer_url="https://auth.example.test",
        resource_url="https://mcp.example.test/mcp",
        access_token_provider=lambda: access_token,
        data_backend=AsyncMock(),
        data_audit=audit,
        intelligence_backend=backend,
    )


@pytest.mark.asyncio
async def test_intelligence_tools_create_evaluate_and_return_citations() -> None:
    backend = IntelligenceBackend()
    audit = Audit()
    async with Client(server(backend, audit)) as client:
        listed = await client.list_tools()
        watches = await client.call_tool("list_intelligence_watches", {"limit": 10})
        created = await client.call_tool(
            "create_intelligence_watch",
            {
                "definition": {"key": "solar-market", "name": "Marché solaire", "query": "solaire"},
                "idempotency_key": "create-solar-watch-0001",
                "confirmation": {"confirmed": True},
            },
        )
        evaluated = await client.call_tool(
            "evaluate_intelligence_watch",
            {
                "watch_key": "solar-market",
                "idempotency_key": "evaluate-solar-watch-0001",
                "confirmation": {"confirmed": True},
            },
        )
        signals = await client.call_tool("list_intelligence_signals", {"watch_key": "solar-market"})
        acknowledged = await client.call_tool(
            "acknowledge_intelligence_signal",
            {
                "signal_id": str(SIGNAL),
                "expected_revision": 1,
                "idempotency_key": "acknowledge-signal-0001",
                "confirmation": {"confirmed": True},
            },
        )

    names = {item.name for item in listed.tools}
    assert {
        "create_intelligence_watch",
        "evaluate_intelligence_watch",
        "list_intelligence_signals",
    } <= names
    assert created.structured_content["query"] == "solaire"
    assert watches.structured_content["items"][0]["key"] == "solar-market"
    assert evaluated.structured_content["created_count"] == 1
    assert signals.structured_content["items"][0]["citation_id"].startswith("kya:snapshot:")
    assert "model" not in str(signals.structured_content).lower()
    assert acknowledged.structured_content["status"] == "acknowledged"
    assert backend.commands[0].actor_id == ACTOR
    assert audit.events[-1]["outcome"] == "succeeded"
