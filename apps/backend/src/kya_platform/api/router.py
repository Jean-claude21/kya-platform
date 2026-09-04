"""Versioned API router composition."""

from fastapi import APIRouter

from kya_platform.api.routes.health import router as health_router
from kya_platform.api.routes.publications import router as publications_router
from kya_platform.api.routes.workspaces import router as workspaces_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(publications_router)
api_router.include_router(workspaces_router)

__all__ = ["api_router"]
