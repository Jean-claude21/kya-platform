"""Provider-neutral OpenFGA-shaped authorization boundary."""

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from kya_platform.application.reliability import JsonValue

_RELATION = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_OBJECT = re.compile(r"^[a-z][a-z0-9_]{0,63}:[^\s:#]{1,255}$")
_USERSET = re.compile(r"^[a-z][a-z0-9_]{0,63}:[^\s:#]{1,255}(?:#[a-z][a-z0-9_]{0,63})?$")


def _validate_relation(value: str) -> None:
    if _RELATION.fullmatch(value) is None:
        raise ValueError(f"invalid authorization relation: {value!r}")


def _validate_object(value: str) -> None:
    if _OBJECT.fullmatch(value) is None:
        raise ValueError(f"invalid authorization object: {value!r}")


def _validate_user(value: str) -> None:
    if _USERSET.fullmatch(value) is None:
        raise ValueError(f"invalid authorization user: {value!r}")


@dataclass(frozen=True, slots=True)
class ContextualTuple:
    """Ephemeral relationship valid only for the current check."""

    user: str
    relation: str
    object: str

    def __post_init__(self) -> None:
        _validate_user(self.user)
        _validate_relation(self.relation)
        _validate_object(self.object)


@dataclass(frozen=True, slots=True)
class CheckRequest:
    """One permission decision pinned to a request context."""

    user: str
    relation: str
    object: str
    context: Mapping[str, JsonValue] = field(default_factory=dict)
    contextual_tuples: Sequence[ContextualTuple] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        _validate_user(self.user)
        _validate_relation(self.relation)
        _validate_object(self.object)


@dataclass(frozen=True, slots=True)
class ListObjectsRequest:
    """Permission-filtered object discovery request."""

    user: str
    relation: str
    object_type: str
    context: Mapping[str, JsonValue] = field(default_factory=dict)
    contextual_tuples: Sequence[ContextualTuple] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        _validate_user(self.user)
        _validate_relation(self.relation)
        if _RELATION.fullmatch(self.object_type) is None:
            raise ValueError(f"invalid authorization object type: {self.object_type!r}")


@dataclass(frozen=True, slots=True)
class AuthorizationDecision:
    """Auditable result from one immutable authorization model version."""

    allowed: bool
    model_id: str

    def __post_init__(self) -> None:
        if not self.model_id:
            raise ValueError("authorization model_id is required")


class AuthorizationPort(Protocol):
    async def check(self, request: CheckRequest) -> AuthorizationDecision:
        """Evaluate one permission using a pinned model version."""

    async def list_objects(self, request: ListObjectsRequest) -> Sequence[str]:
        """Return only objects disclosed by the requested permission."""


class AuthorizationDeniedError(PermissionError):
    """The active principal is not allowed to perform the requested action."""


def active_unit_context(
    *, user_id: str, unit_id: str, current_time: datetime
) -> tuple[Mapping[str, JsonValue], tuple[ContextualTuple, ...]]:
    """Build the non-persistent context required by the KYA model."""

    principal = f"user:{user_id}"
    unit = f"org_unit:{unit_id}"
    return (
        {"current_time": current_time.isoformat()},
        (ContextualTuple(user=principal, relation="user_in_context", object=unit),),
    )


async def require_authorized(port: AuthorizationPort, request: CheckRequest) -> None:
    """Fail closed while leaving HTTP translation to the API layer."""

    decision = await port.check(request)
    if not decision.allowed:
        raise AuthorizationDeniedError("authorization denied")


__all__ = [
    "AuthorizationDecision",
    "AuthorizationDeniedError",
    "AuthorizationPort",
    "CheckRequest",
    "ContextualTuple",
    "ListObjectsRequest",
    "active_unit_context",
    "require_authorized",
]
