"""Intelligence orchestration remains deterministic and transport-independent."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import UUID

import pytest

from kya_platform.application.content import ContentService
from kya_platform.application.data import CommandMetadata
from kya_platform.application.intelligence import (
    IntelligenceReferenceError,
    IntelligenceService,
    IntelligenceStateError,
)
from kya_platform.domain.intelligence import IntelligenceWatch, WatchStatus

IDENTIFIER = UUID("019934e0-0000-7000-8000-000000000001")
NOW = datetime(2026, 9, 8, 18, tzinfo=UTC)
COMMAND = CommandMetadata(IDENTIFIER, IDENTIFIER, "intelligence-command", "a" * 64, NOW)


@pytest.mark.asyncio
@pytest.mark.unit
async def test_evaluation_uses_governed_content_and_records_only_evidence() -> None:
    repository = AsyncMock()
    content_repository = AsyncMock()
    watch = IntelligenceWatch(
        IDENTIFIER,
        "solar-market",
        "Marché solaire",
        "solaire",
        IDENTIFIER,
        IDENTIFIER,
        ("public-web",),
    )
    repository.get_watch.return_value = watch
    content_repository.search_public_content.return_value = ("hit",)
    repository.record_signals.return_value = ()
    service = IntelligenceService(repository, ContentService(content_repository))

    result = await service.evaluate_watch("group", "solar-market", limit=10, command=COMMAND)

    assert result.matched_count == 1
    assert result.created_signals == ()
    content_repository.search_public_content.assert_awaited_once_with(
        "group", "solaire", asset_keys=("public-web",), limit=10
    )
    repository.record_signals.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_evaluation_rejects_missing_or_paused_watch() -> None:
    repository = AsyncMock()
    service = IntelligenceService(repository, ContentService(AsyncMock()))
    repository.get_watch.return_value = None
    with pytest.raises(IntelligenceReferenceError, match="does not exist"):
        await service.evaluate_watch("group", "missing", limit=10, command=COMMAND)

    repository.get_watch.return_value = IntelligenceWatch(
        IDENTIFIER,
        "paused",
        "Paused",
        "solaire",
        IDENTIFIER,
        IDENTIFIER,
        status=WatchStatus.PAUSED,
    )
    with pytest.raises(IntelligenceStateError, match="paused"):
        await service.evaluate_watch("group", "paused", limit=10, command=COMMAND)


@pytest.mark.asyncio
@pytest.mark.unit
async def test_limits_are_bounded() -> None:
    service = IntelligenceService(AsyncMock(), ContentService(AsyncMock()))
    with pytest.raises(ValueError, match="between 1 and 50"):
        await service.evaluate_watch("group", "solar", limit=51, command=COMMAND)
    with pytest.raises(ValueError, match="between 1 and 100"):
        await service.list_watches("group", limit=0)
    with pytest.raises(ValueError, match="between 1 and 100"):
        await service.list_signals("group", "solar", limit=0)


@pytest.mark.asyncio
@pytest.mark.unit
async def test_commands_and_reads_delegate_to_repository() -> None:
    repository = AsyncMock()
    repository.create_watch.return_value = "created"
    repository.list_watches.return_value = ()
    repository.list_signals.return_value = ()
    repository.acknowledge_signal.return_value = "acknowledged"
    service = IntelligenceService(repository, ContentService(AsyncMock()))
    watch = IntelligenceWatch(IDENTIFIER, "solar", "Solar", "solaire", IDENTIFIER, IDENTIFIER)

    assert await service.create_watch("group", watch, command=COMMAND) == "created"
    assert await service.list_watches("group") == ()
    assert await service.list_signals("group", "solar") == ()
    assert (
        await service.acknowledge_signal(
            "group",
            IDENTIFIER,
            expected_revision=1,
            acknowledged_at=NOW,
            command=COMMAND,
        )
        == "acknowledged"
    )
