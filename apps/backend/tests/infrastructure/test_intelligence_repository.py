"""Intelligence persistence is scoped, idempotent and evidence preserving."""

from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Self
from uuid import UUID

import pytest

from kya_platform.application.data import CommandMetadata
from kya_platform.domain.content import ContentSearchHit
from kya_platform.domain.intelligence import IntelligenceWatch, SignalStatus
from kya_platform.infrastructure.database.intelligence import SqlAlchemyIntelligenceRepository
from kya_platform.infrastructure.database.models import (
    AuditEvent,
    IdempotencyRecord,
    IntelligenceSignalRow,
    IntelligenceWatchRow,
    OutboxEvent,
)

UNIT = UUID("019934e2-0000-7000-8000-000000000001")
ACTOR = UUID("019934e2-0000-7000-8000-000000000002")
WATCH = UUID("019934e2-0000-7000-8000-000000000003")
SIGNAL = UUID("019934e2-0000-7000-8000-000000000004")
CHUNK = UUID("019934e2-0000-7000-8000-000000000005")
SNAPSHOT = UUID("019934e2-0000-7000-8000-000000000006")
NOW = datetime(2026, 9, 8, 18, tzinfo=UTC)


class ScalarRows:
    def __init__(self, values: Iterable[object]) -> None:
        self.values = tuple(values)

    def __iter__(self) -> Iterable[object]:
        return iter(self.values)


class ExecuteResult:
    def __init__(self, value: object | None) -> None:
        self.value = value

    def scalar_one_or_none(self) -> object | None:
        return self.value


class Session:
    def __init__(
        self,
        *,
        scalar_values: list[object | None] | None = None,
        scalar_rows: list[list[object]] | None = None,
        get_values: list[object | None] | None = None,
        execute_values: list[object | None] | None = None,
    ) -> None:
        self.scalar_values = scalar_values or []
        self.scalar_rows = scalar_rows or []
        self.get_values = get_values or []
        self.execute_values = execute_values or []
        self.added: list[object] = []

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    def begin(self) -> Self:
        return self

    async def scalar(self, statement: object) -> object | None:
        return self.scalar_values.pop(0)

    async def scalars(self, statement: object) -> ScalarRows:
        return ScalarRows(self.scalar_rows.pop(0))

    async def get(self, model: object, identity: object, **kwargs: object) -> object | None:
        return self.get_values.pop(0)

    async def execute(self, statement: object) -> ExecuteResult:
        return ExecuteResult(self.execute_values.pop(0))

    async def flush(self) -> None:
        for item in self.added:
            if isinstance(item, IntelligenceWatchRow):
                item.created_at = item.created_at or NOW
                item.updated_at = item.updated_at or NOW

    def add(self, value: object) -> None:
        self.added.append(value)

    def add_all(self, values: list[object]) -> None:
        self.added.extend(values)


class Sessions:
    def __init__(self, session: Session) -> None:
        self.session = session

    def __call__(self) -> Session:
        return self.session


def repository(session: Session) -> SqlAlchemyIntelligenceRepository:
    return SqlAlchemyIntelligenceRepository(Sessions(session))  # type: ignore[arg-type]


def command(key: str = "intelligence-command-0001") -> CommandMetadata:
    return CommandMetadata(ACTOR, ACTOR, key, "a" * 64, NOW.replace(day=9))


def watch_row() -> IntelligenceWatchRow:
    return IntelligenceWatchRow(
        id=WATCH,
        key="solar-market",
        name="Marché solaire",
        query="solaire",
        owner_unit_id=UNIT,
        created_by=ACTOR,
        asset_keys=["public-web"],
        status="active",
        revision=1,
        created_at=NOW,
        updated_at=NOW,
    )


def signal_row(*, status: str = "open", revision: int = 1) -> IntelligenceSignalRow:
    return IntelligenceSignalRow(
        id=SIGNAL,
        watch_id=WATCH,
        chunk_id=CHUNK,
        snapshot_id=SNAPSHOT,
        citation_id=f"kya:snapshot:{SNAPSHOT}:chunk:{CHUNK}",
        source_uri="https://kya-energy.com/solutions",
        title="Solutions KYA",
        excerpt="Solutions solaires autonomes",
        observed_at=NOW,
        snapshot_digest="b" * 64,
        page_digest="c" * 64,
        status=status,
        revision=revision,
    )


def hit() -> ContentSearchHit:
    text = "Solutions solaires autonomes"
    return ContentSearchHit(
        CHUNK,
        SNAPSHOT,
        "public-web",
        "https://kya-energy.com/solutions",
        "Solutions KYA",
        NOW,
        "b" * 64,
        "c" * 64,
        0,
        0,
        len(text),
        text,
        0.8,
        "untrusted_external_content",
    )


@pytest.mark.asyncio
@pytest.mark.unit
async def test_create_and_read_watch_are_unit_scoped_and_evidential() -> None:
    session = Session(scalar_values=[UNIT, None])
    item = IntelligenceWatch(
        WATCH, "solar-market", "Marché solaire", "solaire", UNIT, ACTOR, ("public-web",)
    )
    created = await repository(session).create_watch("group", item, command=command())

    assert created.key == "solar-market"
    assert any(isinstance(value, IdempotencyRecord) for value in session.added)
    assert any(isinstance(value, OutboxEvent) for value in session.added)
    assert any(isinstance(value, AuditEvent) for value in session.added)

    loaded = await repository(Session(scalar_values=[UNIT, watch_row()])).get_watch(
        "group", "solar-market"
    )
    assert loaded is not None and loaded.asset_keys == ("public-web",)

    listed = await repository(
        Session(scalar_values=[UNIT], scalar_rows=[[watch_row()]])
    ).list_watches("group", limit=10)
    assert [watch.key for watch in listed] == ["solar-market"]


@pytest.mark.asyncio
@pytest.mark.unit
async def test_record_signals_deduplicates_and_replays_without_model_output() -> None:
    session = Session(
        scalar_values=[UNIT, None],
        get_values=[watch_row()],
        execute_values=[signal_row()],
    )
    watch = IntelligenceWatch(
        WATCH, "solar-market", "Marché solaire", "solaire", UNIT, ACTOR, ("public-web",)
    )
    created = await repository(session).record_signals("group", watch, (hit(),), command=command())

    assert len(created) == 1
    assert created[0].citation_id.startswith("kya:snapshot:")
    assert any(isinstance(value, IdempotencyRecord) for value in session.added)
    event = next(value for value in session.added if isinstance(value, OutboxEvent))
    assert event.payload["created_count"] == 1

    replay_record = IdempotencyRecord(
        scope=f"intelligence:watch:evaluate:{WATCH}:{ACTOR}",
        idempotency_key="intelligence-command-0001",
        request_hash="a" * 64,
        response_status=200,
        response_body={"ids": [str(SIGNAL)]},
        expires_at=NOW.replace(day=9),
    )
    replayed = await repository(
        Session(
            scalar_values=[UNIT, replay_record],
            scalar_rows=[[signal_row()]],
            get_values=[watch_row()],
        )
    ).record_signals("group", watch, (hit(),), command=command())
    assert len(replayed) == 1


@pytest.mark.asyncio
@pytest.mark.unit
async def test_list_and_acknowledge_signals_preserve_evidence() -> None:
    listed = await repository(
        Session(scalar_values=[UNIT], scalar_rows=[[signal_row()]])
    ).list_signals("group", "solar-market", only_open=True, limit=10)
    assert listed[0].status is SignalStatus.OPEN

    row = signal_row()
    session = Session(scalar_values=[UNIT, row, None])
    acknowledged = await repository(session).acknowledge_signal(
        "group",
        SIGNAL,
        expected_revision=1,
        acknowledged_at=NOW,
        command=command(),
    )
    assert acknowledged.status is SignalStatus.ACKNOWLEDGED
    assert acknowledged.revision == 2
    assert acknowledged.citation_id == f"kya:snapshot:{SNAPSHOT}:chunk:{CHUNK}"
    assert any(isinstance(value, AuditEvent) for value in session.added)


@pytest.mark.asyncio
@pytest.mark.unit
async def test_unknown_unit_returns_empty_reads() -> None:
    assert await repository(Session(scalar_values=[None])).get_watch("missing", "solar") is None
    assert await repository(Session(scalar_values=[None])).list_watches("missing", limit=10) == ()
    assert (
        await repository(Session(scalar_values=[None])).list_signals(
            "missing", "solar", only_open=True, limit=10
        )
        == ()
    )
