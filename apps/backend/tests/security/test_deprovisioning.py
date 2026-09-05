"""One deprovisioning decision revokes API and MCP access immediately."""

from dataclasses import dataclass
from uuid import UUID

import pytest

from kya_platform.auth import AuthenticatedIdentity
from kya_platform.mcp.registry.oauth import NeonMcpTokenVerifier

ALICE_ID = UUID("11111111-1111-4111-8111-111111111111")
IDENTITY = AuthenticatedIdentity(
    issuer="https://auth.example.test",
    subject="alice",
    claims={"iss": "https://auth.example.test", "sub": "alice", "exp": 1_800_000_000},
)


class AcceptingVerifier:
    async def verify(self, token: str) -> AuthenticatedIdentity:
        assert token
        return IDENTITY


@dataclass
class RevocableMapping:
    is_active: bool = True

    async def resolve_principal_id(self, identity: AuthenticatedIdentity) -> UUID | None:
        assert identity == IDENTITY
        return ALICE_ID if self.is_active else None

    def deprovision(self) -> None:
        self.is_active = False


@pytest.mark.security
async def test_same_valid_token_is_rejected_after_deprovisioning() -> None:
    mapping = RevocableMapping()
    verifier = NeonMcpTokenVerifier(AcceptingVerifier(), mapping)

    before = await verifier.verify_token("valid-neon-token")
    mapping.deprovision()
    after = await verifier.verify_token("valid-neon-token")

    assert before is not None
    assert before.subject == str(ALICE_ID)
    assert after is None
