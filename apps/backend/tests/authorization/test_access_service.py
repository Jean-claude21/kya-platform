"""Authorization orchestration must explain checks and filter before disclosure."""

from collections.abc import Sequence
from uuid import UUID

import pytest

from kya_platform.authorization import (
    AuthorizationDecision,
    AuthorizationService,
    CheckRequest,
    ListObjectsRequest,
    PolicyResponseError,
)


class StubPolicy:
    def __init__(
        self,
        *,
        allowed: bool = True,
        objects: Sequence[str] = (),
    ) -> None:
        self.allowed = allowed
        self.objects = objects

    async def check(self, request: CheckRequest) -> AuthorizationDecision:
        return AuthorizationDecision(allowed=self.allowed, model_id="01MODEL")

    async def list_objects(self, request: ListObjectsRequest) -> Sequence[str]:
        return self.objects


@pytest.mark.asyncio
@pytest.mark.unit
async def test_explanation_is_stable_safe_and_pinned_to_policy_model() -> None:
    service = AuthorizationService(StubPolicy(allowed=False))
    request = CheckRequest(
        user="user:alice",
        relation="can_manage",
        object="workspace:platform",
        context={"current_time": "2026-09-15T12:00:00+00:00", "secret": "must-not-escape"},
    )

    evidence = await service.explain(
        request,
        correlation_id=UUID("019914b2-1a40-7000-8000-000000000091"),
    )

    assert not evidence.allowed
    assert evidence.model_id == "01MODEL"
    assert evidence.reason_code == "no_applicable_permission"
    assert evidence.context_keys == ("current_time", "secret")
    assert "must-not-escape" not in repr(evidence)


@pytest.mark.asyncio
@pytest.mark.unit
async def test_list_objects_returns_only_valid_deduplicated_requested_type() -> None:
    service = AuthorizationService(
        StubPolicy(objects=("workspace:platform", "workspace:communication", "workspace:platform"))
    )

    objects = await service.list_authorized_objects(
        ListObjectsRequest(user="user:alice", relation="can_view", object_type="workspace")
    )

    assert objects == ("communication", "platform")


@pytest.mark.asyncio
@pytest.mark.unit
async def test_list_objects_fails_closed_on_wrong_policy_object_type() -> None:
    service = AuthorizationService(StubPolicy(objects=("artifact:hidden",)))

    with pytest.raises(PolicyResponseError, match="unexpected object type"):
        await service.list_authorized_objects(
            ListObjectsRequest(user="user:alice", relation="can_view", object_type="workspace")
        )
