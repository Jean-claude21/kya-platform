"""Use cases for safe content projection and bounded retrieval."""

from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

from kya_platform.domain.content import ContentDocument, ContentSearchHit


class ContentRepository(Protocol):
    async def search_public_content(
        self,
        unit_key: str,
        query: str,
        *,
        asset_keys: tuple[str, ...],
        limit: int,
    ) -> Sequence[ContentSearchHit]: ...

    async def get_public_excerpt(
        self, unit_key: str, chunk_id: UUID
    ) -> ContentSearchHit | None: ...


class ContentService:
    def __init__(self, repository: ContentRepository) -> None:
        self._repository = repository

    async def search_public_content(
        self,
        unit_key: str,
        query: str,
        *,
        asset_keys: tuple[str, ...] = (),
        limit: int = 10,
    ) -> Sequence[ContentSearchHit]:
        return await self._repository.search_public_content(
            unit_key, query, asset_keys=asset_keys, limit=limit
        )

    async def get_public_excerpt(self, unit_key: str, chunk_id: UUID) -> ContentSearchHit | None:
        return await self._repository.get_public_excerpt(unit_key, chunk_id)


__all__ = ["ContentDocument", "ContentRepository", "ContentService"]
