"""Audit evidence is immutable, secret-safe and filtered before disclosure."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from kya_platform.application.audit import (
    AuditEvent,
    AuditQuery,
    AuditQueryService,
    AuditWriter,
    InMemoryAuditRepository,
)

NOW = datetime(2026, 9, 5, 9, tzinfo=UTC)
ACTOR = UUID("01991a00-0000-7000-8000-000000000001")
CORRELATION = UUID("01991a00-0000-7000-8000-000000000002")


def event(*, scope: str = "workspace:platform", minutes: int = 0) -> AuditEvent:
    return AuditEvent(
        id=UUID(f"01991a00-0000-7000-8000-{minutes + 10:012d}"),
        occurred_at=NOW + timedelta(minutes=minutes),
        actor_id=ACTOR,
        actor_context={"active_unit": "direction-cvsi", "session": "neon-auth"},
        action="artifact.publish",
        target_type="artifact",
        target_id="kya:skill:document-standard",
        scope=scope,
        environment="test",
        decision="allowed",
        outcome="succeeded",
        correlation_id=CORRELATION,
        metadata={"version": "1.0.0"},
        protected_content={"review_note": "Validation métier complète"},
    )


@pytest.mark.asyncio
async def test_writer_creates_deeply_immutable_append_only_evidence() -> None:
    repository = InMemoryAuditRepository()
    writer = AuditWriter(repository)
    source = {"checks": ["manifest", "owners"]}

    recorded = await writer.append(event().with_metadata(source))
    source["checks"].append("mutated-after-write")

    assert recorded.metadata["checks"] == ("manifest", "owners")
    with pytest.raises(TypeError):
        recorded.metadata["checks"] = ("changed",)  # type: ignore[index]
    assert not hasattr(repository, "update")
    assert not hasattr(repository, "delete")


@pytest.mark.asyncio
async def test_writer_redacts_sensitive_values_recursively_before_persistence() -> None:
    repository = InMemoryAuditRepository()
    writer = AuditWriter(repository)
    unsafe = event().with_metadata(
        {
            "authorization": "Bearer should-never-survive",
            "nested": {"client_secret": "unsafe", "safe": "retained"},
            "items": [{"api_key": "unsafe-too"}],
        }
    )

    recorded = await writer.append(unsafe)
    serialized = repr(recorded)

    assert "should-never-survive" not in serialized
    assert "unsafe" not in serialized
    assert recorded.metadata["authorization"] == "[REDACTED]"
    assert recorded.metadata["nested"]["safe"] == "retained"  # type: ignore[index]


@pytest.mark.asyncio
async def test_query_is_scoped_and_orders_the_timeline_deterministically() -> None:
    repository = InMemoryAuditRepository()
    writer = AuditWriter(repository)
    await writer.append(event(scope="workspace:other", minutes=3))
    await writer.append(event(minutes=2))
    await writer.append(event(minutes=1))

    results = await AuditQueryService(repository).list_events(
        AuditQuery(scope="workspace:platform", limit=20),
        may_view_protected_content=False,
    )

    assert [item.event.occurred_at for item in results] == [
        NOW + timedelta(minutes=2),
        NOW + timedelta(minutes=1),
    ]
    assert all(item.event.scope == "workspace:platform" for item in results)
    assert all(item.protected_content is None for item in results)


@pytest.mark.asyncio
async def test_protected_content_requires_a_separate_explicit_mandate() -> None:
    repository = InMemoryAuditRepository()
    await AuditWriter(repository).append(event())
    service = AuditQueryService(repository)
    query = AuditQuery(scope="workspace:platform")

    metadata_only = await service.list_events(query, may_view_protected_content=False)
    full_view = await service.list_events(query, may_view_protected_content=True)

    assert metadata_only[0].protected_content is None
    assert full_view[0].protected_content == {"review_note": "Validation métier complète"}


def test_query_rejects_unbounded_or_non_workspace_scopes() -> None:
    with pytest.raises(ValueError, match="workspace"):
        AuditQuery(scope="group:all")
    with pytest.raises(ValueError, match="between 1 and 200"):
        AuditQuery(scope="workspace:platform", limit=201)
