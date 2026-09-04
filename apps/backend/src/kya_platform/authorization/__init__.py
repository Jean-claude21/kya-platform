"""Fine-grained authorization contracts."""

from kya_platform.authorization.model import (
    AuthorizationDecision,
    AuthorizationDeniedError,
    AuthorizationPort,
    CheckRequest,
    ContextualTuple,
    ListObjectsRequest,
    active_unit_context,
    require_authorized,
)
from kya_platform.authorization.service import (
    AuthorizationService,
    DecisionEvidence,
    PolicyResponseError,
)

__all__ = [
    "AuthorizationDecision",
    "AuthorizationDeniedError",
    "AuthorizationPort",
    "AuthorizationService",
    "CheckRequest",
    "ContextualTuple",
    "DecisionEvidence",
    "ListObjectsRequest",
    "PolicyResponseError",
    "active_unit_context",
    "require_authorized",
]
