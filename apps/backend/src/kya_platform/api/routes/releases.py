"""Public, content-addressed download endpoints for signed builtin releases."""

from fastapi import APIRouter, Response

from kya_platform.infrastructure.database.builtin_artifacts import (
    _ARCHIVE_DIGEST,
    design_system_archive_bytes,
)

router = APIRouter(prefix="/releases", tags=["releases"])


@router.get("/kya-design-system/0.1.1/package", response_class=Response)
async def download_design_system_release() -> Response:
    """Return the immutable signed package; authorization still gates its discovery."""

    return Response(
        content=design_system_archive_bytes(),
        media_type="application/zip",
        headers={
            "Cache-Control": "public, max-age=31536000, immutable",
            "Digest": f"sha-256={_ARCHIVE_DIGEST}",
            "Content-Disposition": 'attachment; filename="kya-design-system-0.1.1.zip"',
        },
    )


__all__ = ["router"]
