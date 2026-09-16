"""Security tests for the Neon Auth JWT/JWKS boundary."""

from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt import PyJWK

from kya_platform.auth import InvalidTokenError, NeonJwtVerifier

ISSUER = "https://auth.preview.example"
AUDIENCE = "kya-platform"


class StaticSigningKeys:
    def __init__(self, signing_key: PyJWK) -> None:
        self.signing_key = signing_key

    async def resolve(self, token: str) -> PyJWK:
        assert token
        return self.signing_key


@pytest.fixture
def rsa_keys() -> tuple[Any, PyJWK]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_jwk = jwt.algorithms.RSAAlgorithm.to_jwk(private_key.public_key(), as_dict=True)
    public_jwk.update({"kid": "test-key", "alg": "RS256", "use": "sig"})
    return private_key, PyJWK.from_dict(public_jwk)


def make_token(private_key: Any, **overrides: Any) -> str:
    now = datetime.now(UTC)
    claims: dict[str, Any] = {
        "iss": ISSUER,
        "sub": "neon-user-123",
        "aud": AUDIENCE,
        "iat": now,
        "exp": now + timedelta(minutes=5),
    }
    claims.update(overrides)
    return jwt.encode(claims, private_key, algorithm="RS256", headers={"kid": "test-key"})


@pytest.mark.security
async def test_accepts_a_strictly_valid_token(rsa_keys: tuple[Any, PyJWK]) -> None:
    private_key, public_key = rsa_keys
    verifier = NeonJwtVerifier(
        issuer=ISSUER,
        audience=AUDIENCE,
        signing_keys=StaticSigningKeys(public_key),
    )

    identity = await verifier.verify(make_token(private_key))

    assert identity.issuer == ISSUER
    assert identity.subject == "neon-user-123"
    with pytest.raises(TypeError):
        identity.claims["sub"] = "tampered"  # type: ignore[index]


@pytest.mark.security
async def test_accepts_neon_token_without_audience_when_not_configured(
    rsa_keys: tuple[Any, PyJWK],
) -> None:
    private_key, public_key = rsa_keys
    verifier = NeonJwtVerifier(
        issuer=ISSUER,
        audience=None,
        signing_keys=StaticSigningKeys(public_key),
    )

    identity = await verifier.verify(make_token(private_key, aud=None))

    assert identity.subject == "neon-user-123"


@pytest.mark.security
@pytest.mark.parametrize(
    "claim_overrides",
    [
        {"aud": "another-api"},
        {"iss": "https://attacker.example"},
        {"exp": datetime.now(UTC) - timedelta(minutes=1)},
        {"sub": ""},
    ],
)
async def test_rejects_invalid_identity_claims(
    rsa_keys: tuple[Any, PyJWK], claim_overrides: dict[str, Any]
) -> None:
    private_key, public_key = rsa_keys
    verifier = NeonJwtVerifier(
        issuer=ISSUER,
        audience=AUDIENCE,
        signing_keys=StaticSigningKeys(public_key),
        leeway_seconds=0,
    )

    with pytest.raises(InvalidTokenError, match="invalid authentication token"):
        await verifier.verify(make_token(private_key, **claim_overrides))


@pytest.mark.security
async def test_rejects_tokens_missing_required_claims(rsa_keys: tuple[Any, PyJWK]) -> None:
    private_key, public_key = rsa_keys
    now = datetime.now(UTC)
    token = jwt.encode(
        {"iss": ISSUER, "sub": "neon-user-123", "iat": now, "aud": AUDIENCE},
        private_key,
        algorithm="RS256",
        headers={"kid": "test-key"},
    )
    verifier = NeonJwtVerifier(
        issuer=ISSUER,
        audience=AUDIENCE,
        signing_keys=StaticSigningKeys(public_key),
    )

    with pytest.raises(InvalidTokenError):
        await verifier.verify(token)


@pytest.mark.security
async def test_rejects_empty_token(rsa_keys: tuple[Any, PyJWK]) -> None:
    _, public_key = rsa_keys
    verifier = NeonJwtVerifier(
        issuer=ISSUER,
        audience=AUDIENCE,
        signing_keys=StaticSigningKeys(public_key),
    )

    with pytest.raises(InvalidTokenError):
        await verifier.verify("")
