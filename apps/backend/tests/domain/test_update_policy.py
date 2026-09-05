"""Update policy separates security, compatible and breaking changes."""

import pytest

from kya_platform.domain.distribution import (
    ChangeKind,
    UpdateDecision,
    UpdatePolicy,
    assess_update,
)


@pytest.mark.unit
@pytest.mark.parametrize(
    ("kind", "is_compatible", "expected"),
    [
        (ChangeKind.SECURITY, True, UpdateDecision.EXPEDITED_APPROVAL),
        (ChangeKind.PATCH, True, UpdateDecision.PROPOSE),
        (ChangeKind.MINOR, True, UpdateDecision.REQUIRE_APPROVAL),
        (ChangeKind.MAJOR, True, UpdateDecision.REQUIRE_APPROVAL),
        (ChangeKind.PATCH, False, UpdateDecision.BLOCK),
    ],
)
def test_update_policy(kind: ChangeKind, is_compatible: bool, expected: UpdateDecision) -> None:
    assert assess_update(UpdatePolicy(), kind=kind, is_compatible=is_compatible) is expected


@pytest.mark.unit
def test_policy_can_require_approval_for_every_non_security_update() -> None:
    policy = UpdatePolicy(automatically_propose_patches=False)

    assert (
        assess_update(policy, kind=ChangeKind.PATCH, is_compatible=True)
        is UpdateDecision.REQUIRE_APPROVAL
    )
