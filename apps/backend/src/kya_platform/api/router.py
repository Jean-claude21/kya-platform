"""Versioned API router composition."""

from fastapi import APIRouter

from kya_platform.api.routes.health import router as health_router

api_router = APIRouter()
api_router.include_router(health_router)

__all__ = ["api_router"]
