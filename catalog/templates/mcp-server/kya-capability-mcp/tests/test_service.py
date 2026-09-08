import pytest
from kya_capability_mcp.contracts import CapabilityRecord
from kya_capability_mcp.service import CapabilityService


class StubBackend:
    async def find_authorized_records(self, query: str) -> list[CapabilityRecord]:
        return [CapabilityRecord(record_id="record-1", title=query)]


@pytest.mark.asyncio
async def test_normalizes_query_and_returns_typed_records() -> None:
    result = await CapabilityService(StubBackend()).find_records("  solar   market ")

    assert result.query == "solar market"
    assert result.items[0].record_id == "record-1"
