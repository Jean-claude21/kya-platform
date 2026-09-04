"""Catalog discovery is permission-first, never filter-after-fetch."""

from collections.abc import Sequence

import pytest

from kya_platform.application.catalog import CatalogItem, CatalogSearchService
from kya_platform.authorization import AuthorizationDecision, CheckRequest, ListObjectsRequest


class Policy:
    async def check(self, request: CheckRequest) -> AuthorizationDecision:
        return AuthorizationDecision(False, "01MODEL")

    async def list_objects(self, request: ListObjectsRequest) -> Sequence[str]:
        return ("artifact:skill-visible",)


class SearchIndex:
    def __init__(self) -> None:
        self.allowed_ids: tuple[str, ...] | None = None

    async def search(
        self, *, query: str, allowed_ids: tuple[str, ...], limit: int
    ) -> Sequence[CatalogItem]:
        self.allowed_ids = allowed_ids
        return (
            CatalogItem(
                id="skill-visible",
                name="Format documentaire KYA",
                artifact_type="skill",
                version="1.0.0",
                compatibility="compatible",
            ),
        )


@pytest.mark.asyncio
@pytest.mark.unit
async def test_search_index_receives_only_pre_authorized_artifact_ids() -> None:
    index = SearchIndex()
    service = CatalogSearchService(authorization=Policy(), search_index=index)

    results = await service.search(
        user="user:alice",
        query="document",
        context={},
        contextual_tuples=(),
    )

    assert index.allowed_ids == ("skill-visible",)
    assert [item.id for item in results] == ["skill-visible"]


@pytest.mark.asyncio
@pytest.mark.unit
async def test_empty_authorized_set_skips_the_search_index() -> None:
    class EmptyPolicy(Policy):
        async def list_objects(self, request: ListObjectsRequest) -> Sequence[str]:
            return ()

    index = SearchIndex()
    service = CatalogSearchService(authorization=EmptyPolicy(), search_index=index)

    assert (
        await service.search(user="user:bob", query="secret", context={}, contextual_tuples=())
        == ()
    )
    assert index.allowed_ids is None
