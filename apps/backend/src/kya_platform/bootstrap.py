"""One-time, recoverable platform-owner initialization."""

from dataclasses import dataclass
from hashlib import sha256
from hmac import compare_digest
from typing import Literal, Protocol
from uuid import UUID

from pydantic import SecretStr

BootstrapState = Literal["pending", "reserved", "complete"]


@dataclass(frozen=True, slots=True)
class BootstrapClaim:
    principal_id: UUID
    owner_fingerprint: str
    state: BootstrapState


class BootstrapClaimRepository(Protocol):
    async def get(self) -> BootstrapClaim | None: ...

    async def reserve(self, claim: BootstrapClaim) -> BootstrapClaim: ...

    async def complete(self, principal_id: UUID) -> BootstrapClaim: ...


class PlatformOwnerGrant(Protocol):
    async def grant_platform_owner(self, principal_id: UUID) -> None: ...


class BootstrapRejectedError(PermissionError):
    """The submitted claim does not match the configured owner contract."""


class BootstrapAlreadyClaimedError(RuntimeError):
    """Another principal already owns the platform."""


def owner_fingerprint(email: str) -> str:
    return sha256(email.strip().casefold().encode()).hexdigest()


class BootstrapService:
    """Grant the first owner exactly once, with retry after provider failure."""

    def __init__(
        self,
        *,
        repository: BootstrapClaimRepository,
        grant: PlatformOwnerGrant,
        owner_email: str,
        claim_code_hash: SecretStr,
    ) -> None:
        self._repository = repository
        self._grant = grant
        self._owner_fingerprint = owner_fingerprint(owner_email)
        self._claim_code_hash = claim_code_hash

    async def status(self, *, email: str | None) -> tuple[BootstrapState, bool]:
        existing = await self._repository.get()
        state: BootstrapState = existing.state if existing is not None else "pending"
        return state, email is not None and owner_fingerprint(email) == self._owner_fingerprint

    async def claim(
        self, *, principal_id: UUID, email: str | None, claim_code: SecretStr
    ) -> BootstrapClaim:
        supplied_hash = sha256(claim_code.get_secret_value().encode()).hexdigest()
        expected_hash = self._claim_code_hash.get_secret_value()
        email_matches = email is not None and compare_digest(
            owner_fingerprint(email), self._owner_fingerprint
        )
        if not email_matches or not compare_digest(supplied_hash, expected_hash):
            raise BootstrapRejectedError("bootstrap claim rejected")

        reserved = await self._repository.reserve(
            BootstrapClaim(principal_id, self._owner_fingerprint, "reserved")
        )
        if reserved.principal_id != principal_id:
            raise BootstrapAlreadyClaimedError("platform owner already claimed")
        if reserved.state == "complete":
            return reserved

        await self._grant.grant_platform_owner(principal_id)
        return await self._repository.complete(principal_id)


__all__ = [
    "BootstrapAlreadyClaimedError",
    "BootstrapClaim",
    "BootstrapClaimRepository",
    "BootstrapRejectedError",
    "BootstrapService",
    "BootstrapState",
    "PlatformOwnerGrant",
    "owner_fingerprint",
]
