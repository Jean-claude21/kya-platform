"""Orchestrator health probes."""

from typing import Literal

from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel

router = APIRouter(prefix="/health", tags=["health"])


class HealthResponse(BaseModel):
    """Stable health probe contract."""

    status: Literal["ok", "not_ready"]
    service: str
    version: str
    environment: str


def _health_payload(request: Request, health_status: Literal["ok", "not_ready"]) -> dict[str, str]:
    settings = request.app.state.settings
    return {
        "status": health_status,
        "service": settings.app_name,
        "version": settings.version,
        "environment": settings.environment,
    }


@router.get("/live", response_model=HealthResponse)
async def liveness(request: Request) -> dict[str, str]:
    """Report that the process can serve requests."""

    return _health_payload(request, "ok")


@router.get("/ready", response_model=HealthResponse)
async def readiness(request: Request) -> HealthResponse | JSONResponse:
    """Report whether startup dependencies have completed."""

    if not request.app.state.is_ready:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=_health_payload(request, "not_ready"),
        )

    return HealthResponse(**_health_payload(request, "ok"))


__all__ = ["router"]
