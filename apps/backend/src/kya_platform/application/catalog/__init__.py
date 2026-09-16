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


@dataclass(frozen=True, slots=True)
class CatalogBrowseQuery:
    query: str = ""
    artifact_types: tuple[str, ...] = ()
    owner_workspace_id: str | None = None
    limit: int = 20


@dataclass(frozen=True, slots=True)
class CatalogSummary:
    id: str
    public_id: str
    name: str
    artifact_type: str
    summary: str | None
    latest_version: str
    lifecycle: str
    owner_workspace_id: str
    visibility: str | None = None
    visibility_scope_unit_id: str | None = None


@dataclass(frozen=True, slots=True)
class CatalogDiscoverableSummary:
    """A reduced, non-actionable shape for artifacts marked discoverable by their owner.

    Never includes file contents, manifests, versions, digests, or an installation path.
    """

    public_id: str
    name: str
    artifact_type: str
    summary: str | None
    owner_workspace_name: str
    installable: bool = False


@dataclass(frozen=True, slots=True)
class CatalogDetail:
    id: str
    public_id: str
    name: str
    artifact_type: str
    summary: str | None
    latest_version: str
    versions: tuple[str, ...]
    lifecycle: str
    owner_workspace_id: str
    installable: bool
    risk: str
    source_repository: str
    content_digest: str


class CatalogBrowsePort(Protocol):
    async def browse(
        self, *, query: CatalogBrowseQuery, allowed_ids: tuple[str, ...]
    ) -> Sequence[CatalogSummary]:
        """Browse only inside an authorization-filtered identifier set."""


class CatalogDiscoveryPort(Protocol):
    async def browse_discoverable(
        self, *, query: CatalogBrowseQuery, excluded_ids: tuple[str, ...]
    ) -> Sequence[CatalogDiscoverableSummary]:
        """Browse artifacts marked discoverable by their owner, outside the excluded set.

        excluded_ids are identifiers the caller already has full can_view access to; they are
        never repeated in this reduced, non-actionable list.
        """


class CatalogDetailPort(Protocol):
    async def resolve_artifact_id(self, public_id: str) -> object | None:
        """Resolve a public identifier without disclosing metadata."""

    async def describe(self, *, public_id: str, version: str | None = None) -> CatalogDetail | None:
        """Return authorized metadata for one capability."""


class CatalogBrowseService:
    def __init__(
        self,
        *,
        authorization: AuthorizationPort,
        catalog: CatalogBrowsePort,
        discovery: CatalogDiscoveryPort | None = None,
    ) -> None:
        self._authorization = authorization
        self._catalog = catalog
        self._discovery = discovery

    async def browse(
        self,
        *,
        user: str,
        query: CatalogBrowseQuery,
        context: Mapping[str, JsonValue],
        contextual_tuples: Sequence[ContextualTuple],
    ) -> tuple[CatalogSummary, ...]:
        normalized_query = query.query.strip()
        if normalized_query and len(normalized_query) < 2:
            raise ValueError("catalog query must be empty or contain at least two characters")
        if not 1 <= query.limit <= 100:
            raise ValueError("catalog browse limit must be between 1 and 100")
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
        results = await self._catalog.browse(
            query=CatalogBrowseQuery(
                query=normalized_query,
                artifact_types=query.artifact_types,
                owner_workspace_id=query.owner_workspace_id,
                limit=query.limit,
            ),
            allowed_ids=allowed_ids,
        )
        if any(item.id not in allowed_ids for item in results):
            raise RuntimeError("catalog returned an unauthorized artifact")
        return tuple(results)

    async def browse_with_discoverable(
        self,
        *,
        user: str,
        query: CatalogBrowseQuery,
        context: Mapping[str, JsonValue],
        contextual_tuples: Sequence[ContextualTuple],
    ) -> tuple[tuple[CatalogSummary, ...], tuple[CatalogDiscoverableSummary, ...]]:
        """Return fully accessible results, plus a reduced discoverable-only tail.

        The discoverable tail never repeats an identifier already in the accessible set, and
        never discloses file contents, versions, digests, or an installation path.
        """

        accessible = await self.browse(
            user=user, query=query, context=context, contextual_tuples=contextual_tuples
        )
        if self._discovery is None:
            return accessible, ()
        excluded_ids = tuple(item.id for item in accessible)
        discoverable = await self._discovery.browse_discoverable(
            query=query, excluded_ids=excluded_ids
        )
        if any(item.public_id in excluded_ids for item in discoverable):
            raise RuntimeError("discovery returned an identifier already fully accessible")
        return accessible, tuple(discoverable)


class CatalogDetailService:
    def __init__(self, *, authorization: AuthorizationPort, catalog: CatalogDetailPort) -> None:
        self._authorization = authorization
        self._catalog = catalog

    async def get(
        self,
        *,
        user: str,
        public_id: str,
        version: str | None,
        context: Mapping[str, JsonValue],
        contextual_tuples: Sequence[ContextualTuple],
    ) -> CatalogDetail | None:
        internal_id = await self._catalog.resolve_artifact_id(public_id)
        if internal_id is None:
            return None
        allowed_ids = await AuthorizationService(self._authorization).list_authorized_objects(
            ListObjectsRequest(
                user=user,
                relation="can_view",
                object_type="artifact",
                context=context,
                contextual_tuples=contextual_tuples,
            )
        )
        if str(internal_id) not in allowed_ids:
            return None
        detail = await self._catalog.describe(public_id=public_id, version=version)
        if detail is None or detail.id != str(internal_id):
            return None
        return detail


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


__all__ = [
    "CatalogBrowsePort",
    "CatalogBrowseQuery",
    "CatalogBrowseService",
    "CatalogDetail",
    "CatalogDetailPort",
    "CatalogDetailService",
    "CatalogDiscoverableSummary",
    "CatalogDiscoveryPort",
    "CatalogItem",
    "CatalogSearchPort",
    "CatalogSearchService",
    "CatalogSummary",
]
