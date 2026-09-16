"""Deterministic, citation-ready projection of captured pages."""

from hashlib import sha256
from uuid import UUID

from kya_platform.connectors.web_capture.content import project_capture_content
from kya_platform.connectors.web_capture.contracts import CaptureBundle, CapturedPage

SNAPSHOT = UUID("019934a0-0000-7000-8000-000000000001")


def page(*, text: str, trust: str = "untrusted_external_content") -> CapturedPage:
    return CapturedPage(
        url="https://kya-energy.com/fr/solutions",
        status_code=200,
        media_type="text/html",
        body_sha256="a" * 64,
        content_trust=trust,
        html="<main>Solutions KYA</main>",
        title="Solutions KYA",
        language="fr",
        canonical_url="https://kya-energy.com/fr/solutions",
        headings=("Solutions",),
        text=text,
        internal_links=(),
    )


def test_projection_preserves_exact_offsets_digests_and_trust_boundary() -> None:
    text = "Solutions solaires\n\nLampadaires intelligents"
    bundle = CaptureBundle("1.0.0", "https://kya-energy.com/fr", (page(text=text),))

    (document,) = project_capture_content(SNAPSHOT, bundle)
    (chunk,) = document.chunks

    assert document.snapshot_id == SNAPSHOT
    assert document.content_trust == "untrusted_external_content"
    assert chunk.text == text
    assert text[chunk.char_start : chunk.char_end] == chunk.text
    assert chunk.digest == sha256(chunk.text.encode()).hexdigest()


def test_projection_splits_large_content_on_paragraph_boundaries() -> None:
    first = "A" * 2_000
    second = "B" * 2_000
    text = f"{first}\n{second}"
    bundle = CaptureBundle("1.0.0", "https://kya-energy.com/fr", (page(text=text),))

    chunks = project_capture_content(SNAPSHOT, bundle)[0].chunks

    assert [chunk.text for chunk in chunks] == [first, second]
    assert [chunk.ordinal for chunk in chunks] == [0, 1]
