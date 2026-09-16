"""One-time bootstrap remains secure, idempotent and recoverable."""

from uuid import UUID

import pytest
from pydantic import SecretStr

from kya_platform.bootstrap import (
    BootstrapAlreadyClaimedError,
    BootstrapClaim,
    BootstrapRejectedError,
    BootstrapService,
    BootstrapUnavailableError,
    owner_fingerprint,
)

OWNER_ID = UUID("01991fb0-6c00-7000-8000-000000000001")
OTHER_ID = UUID("01991fb0-6c00-7000-8000-000000000002")
CODE_HASH = "3538b4902a9fad43d80819555b9849c471a422489a4f4d7eb532217195e9293d"


class MemoryClaims:
    def __init__(self, claim: BootstrapClaim | None = None) -> None:
        self.claim = claim

    async def get(self) -> BootstrapClaim | None:
        return self.claim

    async def reserve(self, claim: BootstrapClaim) -> BootstrapClaim:
        if self.claim is None:
            self.claim = claim
        return self.claim

    async def complete(self, principal_id: UUID) -> BootstrapClaim:
        assert self.claim is not None
        assert self.claim.principal_id == principal_id
        self.claim = BootstrapClaim(principal_id, self.claim.owner_fingerprint, "complete")
        return self.claim


class RecordingGrant:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.grants: list[UUID] = []

    async def grant_platform_owner(self, principal_id: UUID) -> None:
        self.grants.append(principal_id)
        if self.fail:
            raise RuntimeError("provider unavailable")


def service(repository: MemoryClaims, grant: RecordingGrant) -> BootstrapService:
    return BootstrapService(
        repository=repository,
        grant=grant,
        owner_email="owner@kya-energy.com",
        claim_code_hash=SecretStr(CODE_HASH),
    )


@pytest.mark.unit
def test_active_bootstrap_requires_paired_secrets_and_authorization() -> None:
    with pytest.raises(ValueError, match="configured together"):
        BootstrapService(
            repository=MemoryClaims(),
            grant=RecordingGrant(),
            owner_email="owner@kya-energy.com",
        )
    with pytest.raises(ValueError, match="authorization grant"):
        BootstrapService(
            repository=MemoryClaims(),
            grant=None,
            owner_email="owner@kya-energy.com",
            claim_code_hash=SecretStr(CODE_HASH),
        )


@pytest.mark.unit
async def test_owner_claim_grants_and_closes_initialization() -> None:
    repository = MemoryClaims()
    grant = RecordingGrant()

    claim = await service(repository, grant).claim(
        principal_id=OWNER_ID,
        email="OWNER@kya-energy.com",
        claim_code=SecretStr("one-time-code"),
    )

    assert claim.state == "complete"
    assert grant.grants == [OWNER_ID]


@pytest.mark.unit
@pytest.mark.parametrize(
    ("email", "code"),
    [("other@kya-energy.com", "one-time-code"), ("owner@kya-energy.com", "wrong")],
)
async def test_owner_claim_rejects_wrong_email_or_code(email: str, code: str) -> None:
    with pytest.raises(BootstrapRejectedError):
        await service(MemoryClaims(), RecordingGrant()).claim(
            principal_id=OWNER_ID,
            email=email,
            claim_code=SecretStr(code),
        )


@pytest.mark.unit
async def test_reserved_claim_can_retry_after_openfga_failure() -> None:
    repository = MemoryClaims()
    failing = RecordingGrant(fail=True)
    with pytest.raises(RuntimeError, match="provider unavailable"):
        await service(repository, failing).claim(
            principal_id=OWNER_ID,
            email="owner@kya-energy.com",
            claim_code=SecretStr("one-time-code"),
        )

    retry = RecordingGrant()
    claim = await service(repository, retry).claim(
        principal_id=OWNER_ID,
        email="owner@kya-energy.com",
        claim_code=SecretStr("one-time-code"),
    )
    assert claim.state == "complete"
    assert retry.grants == [OWNER_ID]


@pytest.mark.unit
async def test_claim_cannot_move_to_another_principal() -> None:
    repository = MemoryClaims(
        BootstrapClaim(OTHER_ID, owner_fingerprint("owner@kya-energy.com"), "complete")
    )
    with pytest.raises(BootstrapAlreadyClaimedError):
        await service(repository, RecordingGrant()).claim(
            principal_id=OWNER_ID,
            email="owner@kya-energy.com",
            claim_code=SecretStr("one-time-code"),
        )


@pytest.mark.unit
async def test_completed_claim_is_idempotent_for_same_owner() -> None:
    completed = BootstrapClaim(OWNER_ID, owner_fingerprint("owner@kya-energy.com"), "complete")
    grant = RecordingGrant()
    result = await service(MemoryClaims(completed), grant).claim(
        principal_id=OWNER_ID,
        email="owner@kya-energy.com",
        claim_code=SecretStr("one-time-code"),
    )

    assert result is completed
    assert grant.grants == []


@pytest.mark.unit
async def test_sealed_bootstrap_reports_durable_completion_without_secrets() -> None:
    completed = BootstrapClaim(OWNER_ID, owner_fingerprint("owner@kya-energy.com"), "complete")
    sealed = BootstrapService(repository=MemoryClaims(completed), grant=None)

    assert await sealed.status(email="anyone@kya-energy.com") == ("complete", False)
    with pytest.raises(BootstrapAlreadyClaimedError):
        await sealed.claim(
            principal_id=OWNER_ID,
            email="owner@kya-energy.com",
            claim_code=SecretStr("one-time-code"),
        )


@pytest.mark.unit
async def test_sealed_bootstrap_fails_closed_without_completed_claim() -> None:
    sealed = BootstrapService(repository=MemoryClaims(), grant=None)

    with pytest.raises(BootstrapUnavailableError):
        await sealed.status(email="owner@kya-energy.com")
    with pytest.raises(BootstrapUnavailableError):
        await sealed.claim(
            principal_id=OWNER_ID,
            email="owner@kya-energy.com",
            claim_code=SecretStr("one-time-code"),
        )
