"""Rights-filtered catalog discovery."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol

from kya_platform.application.reliability import JsonValue
from kya_platform.authorization import (
    AuthorizationPort,
    AuthorizationService,
    ContextualTuple,
    ListObjectsRequest,
)


@dataclass(frozen=True, slots=True)
class CatalogItem:
    id: str
    name: str
    artifact_type: str
    version: str
    compatibility: str


class CatalogSearchPort(Protocol):
    async def search(
        self, *, query: str, allowed_ids: tuple[str, ...], limit: int
    ) -> Sequence[CatalogItem]:
        """Search only inside an authorization-filtered identifier set."""


class CatalogSearchService:
    def __init__(
        self, *, authorization: AuthorizationPort, search_index: CatalogSearchPort
    ) -> None:
        self._authorization = authorization
        self._search_index = search_index

    async def search(
        self,
        *,
        user: str,
        query: str,
        context: Mapping[str, JsonValue],
        contextual_tuples: Sequence[ContextualTuple],
        limit: int = 20,
    ) -> tuple[CatalogItem, ...]:
        normalized_query = query.strip()
        if len(normalized_query) < 2:
            raise ValueError("catalog query must contain at least two characters")
        if not 1 <= limit <= 100:
            raise ValueError("catalog search limit must be between 1 and 100")
        allowed_ids = await AuthorizationService(self._authorization).list_authorized_objects(
            ListObjectsRequest(
                user=user,
                relation="can_view",
                object_type="artifact",
                context=context,
                contextual_tuples=contextual_tuples,
            )
        )
        if not allowed_ids:
            return ()
        results = await self._search_index.search(
            query=normalized_query, allowed_ids=allowed_ids, limit=limit
        )
        if any(item.id not in allowed_ids for item in results):
            raise RuntimeError("search index returned an unauthorized artifact")
        return tuple(results)


__all__ = ["CatalogItem", "CatalogSearchPort", "CatalogSearchService"]
