"""Versioned deterministic chunking for captured public web pages."""

from hashlib import sha256
from uuid import UUID, uuid7

from kya_platform.connectors.web_capture.contracts import CaptureBundle
from kya_platform.domain.content import ContentChunk, ContentDocument

CHUNKER_VERSION = "web-lines-1.0"
MAX_CHUNK_CHARS = 3_600


def _chunks(text: str) -> tuple[ContentChunk, ...]:
    paragraphs = [line.strip() for line in text.splitlines() if line.strip()]
    ranges: list[tuple[int, int]] = []
    cursor = 0
    chunk_start = 0
    chunk_end = 0
    for paragraph in paragraphs:
        start = text.find(paragraph, cursor)
        end = start + len(paragraph)
        cursor = end
        if chunk_end > chunk_start and end - chunk_start > MAX_CHUNK_CHARS:
            ranges.append((chunk_start, chunk_end))
            chunk_start = start
        elif chunk_end == chunk_start:
            chunk_start = start
        chunk_end = end
    if chunk_end > chunk_start:
        ranges.append((chunk_start, chunk_end))
    return tuple(
        ContentChunk(
            id=uuid7(),
            ordinal=ordinal,
            text=content,
            char_start=start,
            char_end=end,
            digest=sha256(content.encode()).hexdigest(),
        )
        for ordinal, (start, end) in enumerate(ranges)
        if (content := text[start:end])
    )


def project_capture_content(
    snapshot_id: UUID, bundle: CaptureBundle
) -> tuple[ContentDocument, ...]:
    return tuple(
        ContentDocument(
            id=uuid7(),
            snapshot_id=snapshot_id,
            ordinal=ordinal,
            source_uri=page.url,
            canonical_uri=page.canonical_url,
            title=page.title,
            language=page.language,
            body_digest=page.body_sha256,
            content_trust=page.content_trust,
            chunks=_chunks(page.text),
        )
        for ordinal, page in enumerate(bundle.pages)
    )


__all__ = ["CHUNKER_VERSION", "MAX_CHUNK_CHARS", "project_capture_content"]
