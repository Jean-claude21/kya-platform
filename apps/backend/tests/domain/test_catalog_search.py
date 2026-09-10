"""Catalog discovery is permission-first, never filter-after-fetch."""

from collections.abc import Sequence

import pytest

from kya_platform.application.catalog import (
    CatalogBrowseQuery,
    CatalogBrowseService,
    CatalogItem,
    CatalogSearchService,
    CatalogSummary,
)
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


@pytest.mark.asyncio
@pytest.mark.unit
async def test_browse_supports_empty_query_without_bypassing_authorization() -> None:
    class Catalog:
        allowed_ids: tuple[str, ...] | None = None

        async def browse(
            self, *, query: CatalogBrowseQuery, allowed_ids: tuple[str, ...]
        ) -> Sequence[CatalogSummary]:
            self.allowed_ids = allowed_ids
            assert query.query == ""
            return (
                CatalogSummary(
                    id="skill-visible",
                    public_id="kya:skill:document-standard",
                    name="Standard documentaire KYA",
                    artifact_type="skill",
                    summary=None,
                    latest_version="1.0.0",
                    lifecycle="published",
                    owner_workspace_id="workspace-id",
                ),
            )

    catalog = Catalog()
    service = CatalogBrowseService(authorization=Policy(), catalog=catalog)

    results = await service.browse(
        user="user:alice",
        query=CatalogBrowseQuery(),
        context={},
        contextual_tuples=(),
    )

    assert catalog.allowed_ids == ("skill-visible",)
    assert results[0].public_id == "kya:skill:document-standard"


@pytest.mark.asyncio
@pytest.mark.unit
async def test_browse_rejects_an_item_outside_the_authorized_set() -> None:
    class Catalog:
        async def browse(
            self, *, query: CatalogBrowseQuery, allowed_ids: tuple[str, ...]
        ) -> Sequence[CatalogSummary]:
            return (
                CatalogSummary(
                    id="hidden",
                    public_id="kya:skill:hidden",
                    name="Hidden",
                    artifact_type="skill",
                    summary=None,
                    latest_version="1.0.0",
                    lifecycle="published",
                    owner_workspace_id="workspace-id",
                ),
            )

    service = CatalogBrowseService(authorization=Policy(), catalog=Catalog())

    with pytest.raises(RuntimeError, match="unauthorized"):
        await service.browse(
            user="user:alice",
            query=CatalogBrowseQuery(),
            context={},
            contextual_tuples=(),
        )
