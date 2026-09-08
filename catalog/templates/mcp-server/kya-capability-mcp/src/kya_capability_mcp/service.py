"""Business-facing port and deterministic application service."""

from typing import Protocol

from kya_capability_mcp.contracts import CapabilityRecord, CapabilityResult


class CapabilityBackend(Protocol):
    async def find_authorized_records(self, query: str) -> list[CapabilityRecord]: ...


class CapabilityService:
    def __init__(self, backend: CapabilityBackend) -> None:
        self._backend = backend

    async def find_records(self, query: str) -> CapabilityResult:
        normalized = " ".join(query.split())
        if len(normalized) < 2:
            raise ValueError("query must contain at least two characters")
        items = await self._backend.find_authorized_records(normalized)
        return CapabilityResult(query=normalized, items=items)


class DemoCapabilityBackend:
    """Replace with a Business API adapter carrying the verified KYA context."""

    async def find_authorized_records(self, query: str) -> list[CapabilityRecord]:
        return []
