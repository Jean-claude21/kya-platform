"""PostgreSQL full-text projection for public, governed snapshot content."""

from collections.abc import Sequence
from typing import Any, cast
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from kya_platform.domain.content import ContentSearchHit
from kya_platform.infrastructure.database.models import (
    CoreOrganizationalUnit,
    DataAssetRow,
    DataContentChunkRow,
    DataContentDocumentRow,
    DataSnapshotRow,
)


def _hit(row: Any, *, score: float) -> ContentSearchHit:
    chunk, document, snapshot, asset = row[:4]
    return ContentSearchHit(
        chunk_id=chunk.id,
        snapshot_id=snapshot.id,
        asset_key=asset.key,
        source_uri=document.canonical_uri or document.source_uri,
        title=document.title,
        observed_at=snapshot.observed_at,
        snapshot_digest=snapshot.content_digest,
        page_digest=document.body_digest,
        chunk_ordinal=chunk.ordinal,
        char_start=chunk.char_start,
        char_end=chunk.char_end,
        text=chunk.text,
        score=score,
        content_trust=document.content_trust,
    )


class SqlAlchemyContentRepository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    @staticmethod
    def _base(unit_key: str):  # type: ignore[no-untyped-def]
        return (
            select(
                DataContentChunkRow,
                DataContentDocumentRow,
                DataSnapshotRow,
                DataAssetRow,
            )
            .join(
                DataContentDocumentRow,
                DataContentDocumentRow.id == DataContentChunkRow.document_id,
            )
            .join(DataSnapshotRow, DataSnapshotRow.id == DataContentDocumentRow.snapshot_id)
            .join(DataAssetRow, DataAssetRow.id == DataSnapshotRow.asset_id)
            .join(CoreOrganizationalUnit, CoreOrganizationalUnit.id == DataAssetRow.owner_unit_id)
            .where(
                CoreOrganizationalUnit.key == unit_key,
                DataAssetRow.classification == "public",
                DataAssetRow.status == "active",
            )
        )

    async def search_public_content(
        self,
        unit_key: str,
        query: str,
        *,
        asset_keys: tuple[str, ...],
        limit: int,
    ) -> Sequence[ContentSearchHit]:
        normalized = query.strip()
        if not normalized:
            return ()
        search_query = func.websearch_to_tsquery("simple", normalized)
        rank = func.ts_rank_cd(DataContentChunkRow.search_vector, search_query).label("rank")
        statement = (
            self._base(unit_key)
            .add_columns(rank)
            .where(DataContentChunkRow.search_vector.op("@@")(search_query))
        )
        if asset_keys:
            statement = statement.where(DataAssetRow.key.in_(asset_keys))
        statement = statement.order_by(rank.desc(), DataContentChunkRow.id).limit(limit)
        async with self._sessions() as session:
            rows = (await session.execute(statement)).all()
        return tuple(_hit(row, score=float(cast(float, row[4]))) for row in rows)

    async def get_public_excerpt(self, unit_key: str, chunk_id: UUID) -> ContentSearchHit | None:
        statement = self._base(unit_key).where(DataContentChunkRow.id == chunk_id)
        async with self._sessions() as session:
            row = (await session.execute(statement)).first()
        return _hit(row, score=1.0) if row is not None else None


__all__ = ["SqlAlchemyContentRepository"]
