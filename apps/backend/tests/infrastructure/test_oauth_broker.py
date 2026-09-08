"""OAuth broker tests cover secrecy, consent, one-time grants and token binding."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any
from uuid import UUID

import pytest
from cryptography.fernet import Fernet
from mcp.server.auth.provider import AuthorizationParams, AuthorizeError, TokenError
from mcp.shared.auth import OAuthClientInformationFull

from kya_platform.infrastructure.database.models import OAuthClient, OAuthGrant, OAuthTokenRecord
from kya_platform.infrastructure.database.oauth_broker import (
    BrokerAuthorizationCode,
    OAuthBroker,
)

RESOURCE = "https://mcp.example.test/registry/mcp"
ISSUER = "https://api.example.test"
PRINCIPAL = UUID("01991fb0-6c00-7000-8000-000000000030")


class Result:
    def __init__(self, *, row: object | None = None, rowcount: int = 1) -> None:
        self.row = row
        self.rowcount = rowcount

    def one_or_none(self) -> object | None:
        return self.row


class Session:
    def __init__(self) -> None:
        self.get_result: object | None = None
        self.scalar_result: object | None = None
        self.execute_result = Result()
        self.added: list[object] = []

    async def get(self, model: object, key: object) -> object | None:
        del model, key
        return self.get_result

    async def scalar(self, statement: object) -> object | None:
        del statement
        return self.scalar_result

    async def execute(self, statement: object) -> Result:
        del statement
        return self.execute_result

    def add(self, value: object) -> None:
        self.added.append(value)


class Context:
    def __init__(self, session: Session) -> None:
        self.session = session

    async def __aenter__(self) -> Session:
        return self.session

    async def __aexit__(self, *args: object) -> None:
        del args


class Sessions:
    def __init__(self, session: Session) -> None:
        self.session = session

    def __call__(self) -> Context:
        return Context(self.session)

    def begin(self) -> Context:
        return Context(self.session)


def broker(session: Session) -> OAuthBroker:
    return OAuthBroker(
        Sessions(session),  # type: ignore[arg-type]
        issuer_url=ISSUER,
        resource_url=RESOURCE,
        consent_url="https://app.example.test/oauth/consent",
        client_secret_key=Fernet.generate_key().decode(),
    )


@pytest.mark.asyncio
async def test_reads_latest_live_connector_scopes_without_token_material() -> None:
    session = Session()
    session.scalar_result = ["catalog:read", "data:read"]

    scopes = await broker(session).get_active_grant_scopes(
        principal_id=PRINCIPAL,
        active_unit_id="direction-cvsi",
        client_id="claude",
    )

    assert scopes == frozenset({"catalog:read", "data:read"})


@pytest.mark.asyncio
async def test_missing_live_connector_grant_returns_none() -> None:
    assert (
        await broker(Session()).get_active_grant_scopes(
            principal_id=PRINCIPAL,
            active_unit_id="direction-cvsi",
            client_id="claude",
        )
        is None
    )


def client(secret: str = "client-credential") -> OAuthClientInformationFull:  # noqa: S107
    return OAuthClientInformationFull(
        client_id="client-1",
        client_secret=secret,
        client_name="Claude",
        redirect_uris=["https://client.example/callback"],
        token_endpoint_auth_method="client_secret_post",
        scope="catalog:read catalog:install",
    )


def grant(*, code: str | None = None) -> OAuthGrant:
    now = datetime.now(UTC)
    return OAuthGrant(
        id=UUID("01991fb0-6c00-7000-8000-000000000031"),
        request_digest="a" * 64,
        code_digest=code,
        client_id="client-1",
        redirect_uri="https://client.example/callback",
        redirect_uri_explicit=True,
        code_challenge="challenge",
        scopes=["catalog:read"],
        state="state-1",
        resource=RESOURCE,
        principal_id=PRINCIPAL,
        active_unit_id="group",
        expires_at=now + timedelta(minutes=5),
        approved_at=now,
    )


@pytest.mark.unit
def test_broker_rejects_invalid_encryption_key() -> None:
    with pytest.raises(ValueError, match="Fernet"):
        OAuthBroker(
            Sessions(Session()),  # type: ignore[arg-type]
            issuer_url=ISSUER,
            resource_url=RESOURCE,
            consent_url="https://app.example.test/oauth/consent",
            client_secret_key="invalid",
        )


@pytest.mark.asyncio
async def test_client_secret_is_encrypted_and_restored() -> None:
    session = Session()
    subject = broker(session)
    await subject.register_client(client())
    stored = session.added[0]
    assert isinstance(stored, OAuthClient)
    assert stored.encrypted_secret != b"client-credential"
    assert "client_secret" not in stored.client_metadata

    session.get_result = stored
    restored = await subject.get_client("client-1")
    assert restored is not None
    assert restored.client_secret == "client-credential"


@pytest.mark.asyncio
async def test_authorization_is_resource_bound_and_creates_opaque_consent() -> None:
    session = Session()
    subject = broker(session)
    params = AuthorizationParams(
        state="state-1",
        scopes=["catalog:read"],
        code_challenge="challenge",
        redirect_uri="https://client.example/callback",
        redirect_uri_provided_explicitly=True,
        resource=RESOURCE,
    )

    redirect = await subject.authorize(client(), params)
    assert redirect.startswith("https://app.example.test/oauth/consent?request=")
    stored = session.added[0]
    assert isinstance(stored, OAuthGrant)
    assert "request=" not in stored.request_digest
    assert stored.resource == RESOURCE

    with pytest.raises(AuthorizeError) as error:
        await subject.authorize(client(), params.model_copy(update={"resource": "https://evil"}))
    assert error.value.error == "invalid_target"


@pytest.mark.asyncio
async def test_consent_approval_returns_code_without_leaking_it_to_storage() -> None:
    session = Session()
    row = grant()
    row.approved_at = None
    row.principal_id = None
    row.active_unit_id = None
    session.scalar_result = row
    subject = broker(session)

    redirect = await subject.approve(
        "opaque-request", principal_id=PRINCIPAL, active_unit_id="group"
    )
    assert redirect is not None
    assert "code=" in redirect and "iss=https%3A%2F%2Fapi.example.test" in redirect
    assert row.code_digest is not None and row.code_digest not in redirect
    assert row.principal_id == PRINCIPAL


@pytest.mark.asyncio
async def test_consent_can_be_inspected_and_denied() -> None:
    session = Session()
    row = grant()
    row.approved_at = None
    registered = OAuthClient(
        client_id="client-1",
        client_metadata={"client_name": "ChatGPT"},
        encrypted_secret=None,
    )
    session.execute_result = Result(row=(row, registered))
    subject = broker(session)

    consent = await subject.get_consent_request("opaque-request")
    assert consent is not None
    assert consent.client_name == "ChatGPT"
    assert consent.scopes == ("catalog:read",)

    session.scalar_result = row
    redirect = await subject.deny("opaque-request")
    assert redirect is not None
    assert "error=access_denied" in redirect
    assert row.denied_at is not None


@pytest.mark.asyncio
async def test_approved_code_loads_with_bound_principal_and_context() -> None:
    session = Session()
    session.scalar_result = grant(code="digest")
    authorization_code = await broker(session).load_authorization_code(client(), "raw-code")

    assert authorization_code is not None
    assert authorization_code.principal_id == PRINCIPAL
    assert authorization_code.active_unit_id == "group"
    assert authorization_code.resource == RESOURCE


@pytest.mark.asyncio
async def test_code_exchange_issues_pair_and_access_token_carries_context(monkeypatch: Any) -> None:
    session = Session()
    subject = broker(session)
    authorization_code = BrokerAuthorizationCode(
        code="raw-code",
        scopes=["catalog:read"],
        expires_at=(datetime.now(UTC) + timedelta(minutes=5)).timestamp(),
        client_id="client-1",
        code_challenge="challenge",
        redirect_uri="https://client.example/callback",
        redirect_uri_provided_explicitly=True,
        resource=RESOURCE,
        subject=str(PRINCIPAL),
        grant_id=UUID("01991fb0-6c00-7000-8000-000000000031"),
        principal_id=PRINCIPAL,
        active_unit_id="group",
    )
    tokens = await subject.exchange_authorization_code(client(), authorization_code)
    assert tokens.refresh_token and tokens.access_token
    assert len(session.added) == 2
    assert all(isinstance(item, OAuthTokenRecord) for item in session.added)
    assert all(tokens.access_token != item.token_digest for item in session.added)

    access_row = session.added[0]
    monkeypatch.setattr(subject, "_load_token", lambda *args, **kwargs: _async_value(access_row))
    access = await subject.load_access_token(tokens.access_token)
    assert access is not None
    assert access.subject == str(PRINCIPAL)
    assert access.claims == {"iss": ISSUER, "active_unit": "group"}


@pytest.mark.asyncio
async def test_refresh_rotates_and_revocation_closes_the_token_family(monkeypatch: Any) -> None:
    session = Session()
    subject = broker(session)
    row = OAuthTokenRecord(
        token_digest="digest",
        kind="refresh",
        grant_id=UUID("01991fb0-6c00-7000-8000-000000000031"),
        client_id="client-1",
        principal_id=PRINCIPAL,
        active_unit_id="group",
        scopes=["catalog:read"],
        resource=RESOURCE,
        expires_at=datetime.now(UTC) + timedelta(days=1),
    )
    monkeypatch.setattr(subject, "_load_token", lambda *args, **kwargs: _async_value(row))

    loaded = await subject.load_refresh_token(client(), "raw-refresh")
    assert loaded is not None
    tokens = await subject.exchange_refresh_token(client(), loaded, ["catalog:read"])
    assert tokens.refresh_token is not None
    assert len(session.added) == 2

    await subject.revoke_token(loaded)
    assert session.execute_result.rowcount == 1


async def _async_value(value: object) -> object:
    return value


@pytest.mark.asyncio
async def test_code_replay_and_identity_assertion_fail_closed() -> None:
    session = Session()
    session.execute_result = Result(rowcount=0)
    subject = broker(session)
    authorization_code = SimpleNamespace(grant_id=UUID(int=1))
    with pytest.raises(TokenError):
        await subject.exchange_authorization_code(client(), authorization_code)  # type: ignore[arg-type]
    with pytest.raises(TokenError, match="Identity assertion"):
        await subject.exchange_identity_assertion(client(), SimpleNamespace())  # type: ignore[arg-type]
