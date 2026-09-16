from dataclasses import dataclass
from uuid import UUID

import pytest

from kya_platform.auth.identity import AuthenticatedIdentity
from kya_platform.auth.neon_jwt import InvalidTokenError
from kya_platform.mcp.registry.oauth import NeonMcpTokenVerifier


@dataclass
class IdentityVerifier:
    identity: AuthenticatedIdentity | None

    async def verify(self, token: str) -> AuthenticatedIdentity:
        if self.identity is None:
            raise InvalidTokenError("invalid authentication token")
        return self.identity


@dataclass
class IdentityMapping:
    principal_id: UUID | None

    async def resolve_principal_id(self, identity: AuthenticatedIdentity) -> UUID | None:
        assert identity.subject == "alice"
        return self.principal_id


ALICE_ID = UUID("11111111-1111-4111-8111-111111111111")


@pytest.mark.asyncio
async def test_neon_identity_becomes_scoped_mcp_access_token() -> None:
    verifier = NeonMcpTokenVerifier(
        IdentityVerifier(
            AuthenticatedIdentity(
                issuer="https://auth.example.test",
                subject="alice",
                claims={
                    "iss": "https://auth.example.test",
                    "sub": "alice",
                    "azp": "codex-desktop",
                    "scope": "catalog:read catalog:install catalog:read",
                    "active_unit": "dss",
                    "exp": 1_800_000_000,
                    "private_profile": "must-not-propagate",
                },
            )
        ),
        IdentityMapping(ALICE_ID),
    )

    access = await verifier.verify_token("opaque-token")

    assert access is not None
    assert access.subject == str(ALICE_ID)
    assert access.client_id == "codex-desktop"
    assert access.scopes == ["catalog:install", "catalog:read"]
    assert access.claims == {
        "iss": "https://auth.example.test",
        "active_unit": "dss",
    }


@pytest.mark.asyncio
async def test_invalid_neon_token_is_rejected_without_detail() -> None:
    access = await NeonMcpTokenVerifier(
        IdentityVerifier(None), IdentityMapping(ALICE_ID)
    ).verify_token("bad-token")

    assert access is None


@pytest.mark.asyncio
async def test_deprovisioned_identity_is_rejected_at_mcp_boundary() -> None:
    identity = AuthenticatedIdentity(
        issuer="https://auth.example.test",
        subject="alice",
        claims={"exp": 1_800_000_000},
    )

    access = await NeonMcpTokenVerifier(
        IdentityVerifier(identity), IdentityMapping(None)
    ).verify_token("still-cryptographically-valid")

    assert access is None
