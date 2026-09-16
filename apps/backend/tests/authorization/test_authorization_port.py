"""Tests for the provider-neutral authorization boundary."""

from collections.abc import Sequence
from datetime import UTC, datetime

import pytest

from kya_platform.authorization import (
    AuthorizationDecision,
    AuthorizationDeniedError,
    CheckRequest,
    ListObjectsRequest,
    active_unit_context,
    require_authorized,
)


class StubAuthorization:
    def __init__(self, allowed: bool) -> None:
        self.allowed = allowed
        self.requests: list[CheckRequest] = []

    async def check(self, request: CheckRequest) -> AuthorizationDecision:
        self.requests.append(request)
        return AuthorizationDecision(allowed=self.allowed, model_id="01MODEL")

    async def list_objects(self, request: ListObjectsRequest) -> Sequence[str]:
        return ("workspace:platform",) if self.allowed else ()


@pytest.mark.unit
def test_active_unit_is_ephemeral_context_not_persisted_state() -> None:
    current_time = datetime(2026, 9, 4, 8, 30, tzinfo=UTC)

    context, tuples = active_unit_context(
        user_id="alice", unit_id="direction-cvsi", current_time=current_time
    )

    assert context == {"current_time": "2026-09-04T08:30:00+00:00"}
    assert tuples[0].user == "user:alice"
    assert tuples[0].relation == "user_in_context"
    assert tuples[0].object == "org_unit:direction-cvsi"


@pytest.mark.unit
async def test_require_authorized_allows_positive_decision() -> None:
    port = StubAuthorization(allowed=True)
    request = CheckRequest(user="user:alice", relation="can_manage", object="workspace:platform")

    await require_authorized(port, request)

    assert port.requests == [request]


@pytest.mark.security
async def test_require_authorized_fails_closed() -> None:
    port = StubAuthorization(allowed=False)
    request = CheckRequest(user="user:sam", relation="can_edit", object="workspace:platform")

    with pytest.raises(AuthorizationDeniedError):
        await require_authorized(port, request)


@pytest.mark.security
@pytest.mark.parametrize(
    ("user", "relation", "object_name"),
    [
        ("alice", "can_view", "workspace:platform"),
        ("user:alice", "CAN_VIEW", "workspace:platform"),
        ("user:alice", "can_view", "workspace:platform#owner"),
    ],
)
def test_rejects_malformed_authorization_identifiers(
    user: str, relation: str, object_name: str
) -> None:
    with pytest.raises(ValueError):
        CheckRequest(user=user, relation=relation, object=object_name)


@pytest.mark.unit
async def test_list_objects_port_is_permission_filtered() -> None:
    port = StubAuthorization(allowed=True)
    request = ListObjectsRequest(user="user:alice", relation="can_view", object_type="workspace")

    objects = await port.list_objects(request)

    assert objects == ("workspace:platform",)
