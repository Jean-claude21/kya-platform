"""Deterministic, citation-ready projections of governed snapshot content."""

from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from uuid import UUID


@dataclass(frozen=True, slots=True)
class ContentChunk:
    id: UUID
    ordinal: int
    text: str
    char_start: int
    char_end: int
    digest: str

    def __post_init__(self) -> None:
        if self.ordinal < 0 or self.char_start < 0 or self.char_end <= self.char_start:
            raise ValueError("content chunk position is invalid")
        if self.char_end - self.char_start != len(self.text):
            raise ValueError("content chunk offsets must match its exact text")
        if sha256(self.text.encode()).hexdigest() != self.digest:
            raise ValueError("content chunk digest does not match its text")


@dataclass(frozen=True, slots=True)
class ContentDocument:
    id: UUID
    snapshot_id: UUID
    ordinal: int
    source_uri: str
    canonical_uri: str | None
    title: str | None
    language: str | None
    body_digest: str
    content_trust: str
    chunks: tuple[ContentChunk, ...]

    def __post_init__(self) -> None:
        if self.ordinal < 0 or not self.source_uri.startswith("https://"):
            raise ValueError("content document source is invalid")
        if self.canonical_uri is not None and not self.canonical_uri.startswith("https://"):
            raise ValueError("content document canonical URI is invalid")
        if self.content_trust != "untrusted_external_content":
            raise ValueError("external content must remain explicitly untrusted")
        ordinals = [chunk.ordinal for chunk in self.chunks]
        if ordinals != list(range(len(self.chunks))):
            raise ValueError("content chunk ordinals must be contiguous")


@dataclass(frozen=True, slots=True)
class ContentSearchHit:
    chunk_id: UUID
    snapshot_id: UUID
    asset_key: str
    source_uri: str
    title: str | None
    observed_at: datetime
    snapshot_digest: str
    page_digest: str
    chunk_ordinal: int
    char_start: int
    char_end: int
    text: str
    score: float
    content_trust: str

    @property
    def citation_id(self) -> str:
        return f"kya:snapshot:{self.snapshot_id}:chunk:{self.chunk_id}"


__all__ = ["ContentChunk", "ContentDocument", "ContentSearchHit"]
