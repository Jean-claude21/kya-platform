"""Provider boundary: credentials remain references resolved by the runtime."""

from collections.abc import AsyncIterator, Mapping
from typing import Protocol


class SourceRecord(Mapping[str, object], Protocol):
    """A normalized record with no secret material."""


class SourceConnector(Protocol):
    async def health(self) -> bool:
        """Check reachability without returning credentials or source content."""

    def read(self, *, cursor: str | None = None) -> AsyncIterator[SourceRecord]:
        """Stream normalized records using an opaque resumable cursor."""
