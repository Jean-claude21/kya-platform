"""The SQL adapter maps immutable domain events without exposing mutation operations."""

from datetime import UTC, datetime
from typing import Any, Self
from uuid import UUID

import pytest

from kya_platform.application.audit import AuditEvent, AuditQuery
from kya_platform.infrastructure.database.audit import SqlAlchemyAuditRepository
from kya_platform.infrastructure.database.models import AuditEvent as AuditEventRow

ACTOR = UUID("01991a00-0000-7000-8000-000000000031")
EVENT_ID = UUID("01991a00-0000-7000-8000-000000000032")
CORRELATION = UUID("01991a00-0000-7000-8000-000000000033")


def audit_event() -> AuditEvent:
    return AuditEvent(
        id=EVENT_ID,
        occurred_at=datetime(2026, 9, 5, 10, tzinfo=UTC),
        actor_id=ACTOR,
        actor_context={"active_unit": "direction-cvsi"},
        action="artifact.publish",
        target_type="artifact",
        target_id="kya:skill:document-standard",
        scope="workspace:platform",
        environment="test",
        decision="allowed",
        outcome="succeeded",
        correlation_id=CORRELATION,
        metadata={"checks": ("manifest", "owners")},
        protected_content={"review_note": "Validation métier"},
    )


class FakeScalarResult:
    def __init__(self, rows: list[AuditEventRow]) -> None:
        self._rows = rows

    def all(self) -> list[AuditEventRow]:
        return self._rows


class FakeResult:
    def __init__(self, rows: list[AuditEventRow]) -> None:
        self._rows = rows

    def scalars(self) -> FakeScalarResult:
        return FakeScalarResult(self._rows)


class FakeSession:
    def __init__(self, rows: list[AuditEventRow]) -> None:
        self.rows = rows
        self.commits = 0
        self.statement: Any = None

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    def add(self, row: AuditEventRow) -> None:
        self.rows.append(row)

    async def commit(self) -> None:
        self.commits += 1

    async def execute(self, statement: Any) -> FakeResult:
        self.statement = statement
        return FakeResult(self.rows)


class FakeSessions:
    def __init__(self) -> None:
        self.session = FakeSession([])

    def __call__(self) -> FakeSession:
        return self.session


@pytest.mark.asyncio
async def test_append_serializes_nested_immutable_values_and_commits_once() -> None:
    sessions = FakeSessions()
    repository = SqlAlchemyAuditRepository(sessions)  # type: ignore[arg-type]

    await repository.append(audit_event())

    row = sessions.session.rows[0]
    assert row.event_metadata["checks"] == ["manifest", "owners"]
    assert row.event_metadata["_actor_context"]["active_unit"] == "direction-cvsi"
    assert row.event_metadata["_protected_content"]["review_note"] == "Validation métier"
    assert sessions.session.commits == 1
    assert not hasattr(repository, "update")


@pytest.mark.asyncio
async def test_scoped_query_reconstructs_separated_content() -> None:
    sessions = FakeSessions()
    repository = SqlAlchemyAuditRepository(sessions)  # type: ignore[arg-type]
    await repository.append(audit_event())

    records = await repository.list_events(
        AuditQuery(
            scope="workspace:platform",
            target_type="artifact",
            target_id="kya:skill:document-standard",
            correlation_id=CORRELATION,
            limit=25,
        )
    )

    assert records[0].actor_context["active_unit"] == "direction-cvsi"
    assert records[0].metadata == {"checks": ("manifest", "owners")}
    assert records[0].protected_content == {"review_note": "Validation métier"}
    assert "workspace:platform" in sessions.session.statement.compile().params.values()
