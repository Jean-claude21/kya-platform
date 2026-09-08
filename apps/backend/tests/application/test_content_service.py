"""Governed content application boundary tests."""

from dataclasses import replace
from datetime import UTC, datetime
from hashlib import sha256
from uuid import UUID

import pytest

from kya_platform.application.content import ContentService
from kya_platform.domain.content import ContentChunk, ContentDocument, ContentSearchHit

DOCUMENT = UUID("019934b0-0000-7000-8000-000000000001")
SNAPSHOT = UUID("019934b0-0000-7000-8000-000000000002")
CHUNK = UUID("019934b0-0000-7000-8000-000000000003")


def chunk(text: str = "Solaire") -> ContentChunk:
    return ContentChunk(CHUNK, 0, text, 0, len(text), sha256(text.encode()).hexdigest())


def hit() -> ContentSearchHit:
    return ContentSearchHit(
        CHUNK,
        SNAPSHOT,
        "site-kya",
        "https://kya-energy.com/fr",
        "KYA",
        datetime(2026, 9, 8, tzinfo=UTC),
        "a" * 64,
        "b" * 64,
        0,
        0,
        7,
        "Solaire",
        0.9,
        "untrusted_external_content",
    )


class Repository:
    searches: list[tuple[str, str, tuple[str, ...], int]]

    def __init__(self) -> None:
        self.searches = []

    async def search_public_content(
        self,
        unit_key: str,
        query: str,
        *,
        asset_keys: tuple[str, ...],
        limit: int,
    ) -> tuple[ContentSearchHit, ...]:
        self.searches.append((unit_key, query, asset_keys, limit))
        return (hit(),)

    async def get_public_excerpt(self, unit_key: str, chunk_id: UUID) -> ContentSearchHit | None:
        return hit() if unit_key == "direction-cvsi" and chunk_id == CHUNK else None


@pytest.mark.asyncio
async def test_content_service_delegates_bounded_public_queries() -> None:
    repository = Repository()
    service = ContentService(repository)

    results = await service.search_public_content(
        "direction-cvsi", "solaire", asset_keys=("site-kya",), limit=3
    )
    excerpt = await service.get_public_excerpt("direction-cvsi", CHUNK)

    assert results[0].citation_id.endswith(str(CHUNK))
    assert excerpt == results[0]
    assert repository.searches == [("direction-cvsi", "solaire", ("site-kya",), 3)]


@pytest.mark.parametrize(
    "invalid",
    [
        lambda value: replace(value, char_end=6),
        lambda value: replace(value, digest="0" * 64),
        lambda value: replace(value, ordinal=-1),
    ],
)
def test_content_chunk_rejects_unverifiable_evidence(invalid: object) -> None:
    with pytest.raises(ValueError):
        invalid(chunk())  # type: ignore[operator]


@pytest.mark.parametrize(
    ("source", "canonical", "trust", "chunks"),
    [
        ("http://kya-energy.com/fr", None, "untrusted_external_content", (chunk(),)),
        (
            "https://kya-energy.com/fr",
            "http://kya-energy.com/fr",
            "untrusted_external_content",
            (chunk(),),
        ),
        ("https://kya-energy.com/fr", None, "trusted", (chunk(),)),
        (
            "https://kya-energy.com/fr",
            None,
            "untrusted_external_content",
            (replace(chunk(), ordinal=1),),
        ),
    ],
)
def test_content_document_rejects_unsafe_evidence(
    source: str,
    canonical: str | None,
    trust: str,
    chunks: tuple[ContentChunk, ...],
) -> None:
    with pytest.raises(ValueError):
        ContentDocument(
            DOCUMENT,
            SNAPSHOT,
            0,
            source,
            canonical,
            None,
            "fr",
            "a" * 64,
            trust,
            chunks,
        )
