"""Versioned API router composition."""

from fastapi import APIRouter

from kya_platform.api.routes.account import router as account_router
from kya_platform.api.routes.artifacts import router as artifacts_router
from kya_platform.api.routes.audit import router as audit_router
from kya_platform.api.routes.bootstrap import router as bootstrap_router
from kya_platform.api.routes.core import router as core_router
from kya_platform.api.routes.data import router as data_router
from kya_platform.api.routes.health import router as health_router
from kya_platform.api.routes.mcp_profiles import router as mcp_profiles_router
from kya_platform.api.routes.oauth import router as oauth_router
from kya_platform.api.routes.publications import attestation_router
from kya_platform.api.routes.publications import router as publications_router
from kya_platform.api.routes.secrets import router as secrets_router
from kya_platform.api.routes.source_lifecycle import router as source_lifecycle_router
from kya_platform.api.routes.systems import router as systems_router
from kya_platform.api.routes.workspaces import router as workspaces_router

api_router = APIRouter()
api_router.include_router(account_router)
api_router.include_router(artifacts_router)
api_router.include_router(bootstrap_router)
api_router.include_router(core_router)
api_router.include_router(data_router)
api_router.include_router(health_router)
api_router.include_router(mcp_profiles_router)
api_router.include_router(oauth_router)
api_router.include_router(audit_router)
api_router.include_router(publications_router)
api_router.include_router(attestation_router)
api_router.include_router(secrets_router)
api_router.include_router(source_lifecycle_router)
api_router.include_router(systems_router)
api_router.include_router(workspaces_router)

__all__ = ["api_router"]
