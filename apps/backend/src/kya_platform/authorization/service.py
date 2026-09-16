"""Safe explanation and disclosure-filtered authorization services."""

from dataclasses import dataclass
from uuid import UUID

from kya_platform.authorization.model import AuthorizationPort, CheckRequest, ListObjectsRequest


class PolicyResponseError(RuntimeError):
    """The policy provider returned data outside the requested boundary."""


@dataclass(frozen=True, slots=True)
class DecisionEvidence:
    correlation_id: UUID
    user: str
    relation: str
    object: str
    allowed: bool
    model_id: str
    reason_code: str
    context_keys: tuple[str, ...]


class AuthorizationService:
    def __init__(self, policy: AuthorizationPort) -> None:
        self._policy = policy

    async def explain(self, request: CheckRequest, *, correlation_id: UUID) -> DecisionEvidence:
        """Return attributable evidence without copying sensitive context values."""

        decision = await self._policy.check(request)
        reason_code = (
            "policy_permission_matched" if decision.allowed else "no_applicable_permission"
        )
        return DecisionEvidence(
            correlation_id=correlation_id,
            user=request.user,
            relation=request.relation,
            object=request.object,
            allowed=decision.allowed,
            model_id=decision.model_id,
            reason_code=reason_code,
            context_keys=tuple(sorted(request.context)),
        )

    async def list_authorized_objects(self, request: ListObjectsRequest) -> tuple[str, ...]:
        """Return stable identifiers only after the policy engine filters disclosure."""

        prefix = f"{request.object_type}:"
        objects = await self._policy.list_objects(request)
        if any(not item.startswith(prefix) for item in objects):
            raise PolicyResponseError("policy returned an unexpected object type")
        return tuple(sorted({item.removeprefix(prefix) for item in objects}))


__all__ = ["AuthorizationService", "DecisionEvidence", "PolicyResponseError"]
