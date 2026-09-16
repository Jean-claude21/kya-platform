"""Persistent OAuth 2.1 broker for remote KYA MCP clients."""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import cast
from urllib.parse import urlencode
from uuid import UUID

from cryptography.fernet import Fernet, InvalidToken
from mcp.server.auth.provider import (
    AccessToken,
    AuthorizationCode,
    AuthorizationParams,
    AuthorizeError,
    IdentityAssertionParams,
    RefreshToken,
    RegistrationError,
    TokenError,
    construct_redirect_uri,
)
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from kya_platform.infrastructure.database.models import OAuthClient, OAuthGrant, OAuthTokenRecord

VALID_SCOPES = frozenset(
    {
        "catalog:read",
        "catalog:install",
        "catalog:publish",
        "data:read",
        "data:ingest",
        "data:content:read",
    }
)


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _opaque_token() -> str:
    return secrets.token_urlsafe(32)


@dataclass(frozen=True, slots=True)
class ConsentRequest:
    client_name: str
    scopes: tuple[str, ...]
    resource: str
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class ActiveConnectorGrant:
    client_id: str
    client_name: str
    scopes: tuple[str, ...]
    connected_at: datetime
    expires_at: datetime


class BrokerAuthorizationCode(AuthorizationCode):
    grant_id: UUID
    principal_id: UUID
    active_unit_id: str


class BrokerRefreshToken(RefreshToken):
    grant_id: UUID
    principal_id: UUID
    active_unit_id: str
    resource: str


class BrokerAccessToken(AccessToken):
    grant_id: UUID


class OAuthBroker:
    """MCP SDK provider backed by Neon Postgres and Neon Auth consent."""

    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        *,
        issuer_url: str,
        resource_url: str,
        consent_url: str,
        client_secret_key: str,
        access_token_ttl_seconds: int = 900,
        refresh_token_ttl_seconds: int = 2_592_000,
        authorization_request_ttl_seconds: int = 600,
        authorization_code_ttl_seconds: int = 300,
    ) -> None:
        self._sessions = sessions
        self._issuer_url = issuer_url.rstrip("/")
        self._resource_url = resource_url.rstrip("/")
        self._consent_url = consent_url
        try:
            self._cipher = Fernet(client_secret_key.encode())
        except (ValueError, TypeError) as error:
            raise ValueError("OAuth client secret key must be a valid Fernet key") from error
        self._access_ttl = timedelta(seconds=access_token_ttl_seconds)
        self._refresh_ttl = timedelta(seconds=refresh_token_ttl_seconds)
        self._request_ttl = timedelta(seconds=authorization_request_ttl_seconds)
        self._code_ttl = timedelta(seconds=authorization_code_ttl_seconds)

    async def get_client(self, client_id: str) -> OAuthClientInformationFull | None:
        async with self._sessions() as session:
            row = await session.get(OAuthClient, client_id)
        if row is None:
            return None
        metadata = dict(row.client_metadata)
        metadata["client_id"] = row.client_id
        if row.encrypted_secret is not None:
            try:
                metadata["client_secret"] = self._cipher.decrypt(row.encrypted_secret).decode()
            except InvalidToken:
                return None
        return OAuthClientInformationFull.model_validate(metadata)

    async def get_active_grant_scopes(
        self,
        *,
        principal_id: UUID,
        active_unit_id: str,
        client_id: str,
    ) -> frozenset[str] | None:
        """Return the latest live connector grant without disclosing any token."""

        async with self._sessions() as session:
            scopes = await session.scalar(
                select(OAuthTokenRecord.scopes)
                .where(
                    OAuthTokenRecord.principal_id == principal_id,
                    OAuthTokenRecord.active_unit_id == active_unit_id,
                    OAuthTokenRecord.client_id == client_id,
                    OAuthTokenRecord.kind == "refresh",
                    OAuthTokenRecord.revoked_at.is_(None),
                    OAuthTokenRecord.expires_at > datetime.now(UTC),
                )
                .order_by(OAuthTokenRecord.created_at.desc())
                .limit(1)
            )
            return frozenset(scopes) if scopes is not None else None

    async def list_active_connectors(
        self,
        *,
        principal_id: UUID,
        active_unit_id: str,
    ) -> tuple[ActiveConnectorGrant, ...]:
        """Return the latest live grant for each client without exposing credentials."""

        now = datetime.now(UTC)
        async with self._sessions() as session:
            rows = await session.execute(
                select(
                    OAuthTokenRecord.client_id,
                    OAuthClient.client_metadata,
                    OAuthTokenRecord.scopes,
                    OAuthTokenRecord.created_at,
                    OAuthTokenRecord.expires_at,
                )
                .join(OAuthClient, OAuthClient.client_id == OAuthTokenRecord.client_id)
                .where(
                    OAuthTokenRecord.principal_id == principal_id,
                    OAuthTokenRecord.active_unit_id == active_unit_id,
                    OAuthTokenRecord.kind == "refresh",
                    OAuthTokenRecord.revoked_at.is_(None),
                    OAuthTokenRecord.expires_at > now,
                )
                .order_by(
                    OAuthTokenRecord.client_id,
                    OAuthTokenRecord.created_at.desc(),
                )
            )

        connectors: list[ActiveConnectorGrant] = []
        seen_clients: set[str] = set()
        for client_id, metadata, scopes, connected_at, expires_at in rows:
            if client_id in seen_clients:
                continue
            seen_clients.add(client_id)
            connectors.append(
                ActiveConnectorGrant(
                    client_id=client_id,
                    client_name=str(metadata.get("client_name") or client_id),
                    scopes=tuple(sorted(scopes)),
                    connected_at=connected_at,
                    expires_at=expires_at,
                )
            )
        return tuple(sorted(connectors, key=lambda item: item.client_name.casefold()))

    async def register_client(self, client_info: OAuthClientInformationFull) -> None:
        scopes = set((client_info.scope or "").split())
        if not scopes.issubset(VALID_SCOPES):
            raise RegistrationError("invalid_client_metadata", "Unsupported KYA scope")
        metadata = client_info.model_dump(mode="json", exclude={"client_id", "client_secret"})
        encrypted = (
            self._cipher.encrypt(client_info.client_secret.encode())
            if client_info.client_secret
            else None
        )
        async with self._sessions.begin() as session:
            if await session.get(OAuthClient, client_info.client_id) is not None:
                raise RegistrationError("invalid_client_metadata", "Client ID already exists")
            session.add(
                OAuthClient(
                    client_id=client_info.client_id,
                    client_metadata=metadata,
                    encrypted_secret=encrypted,
                )
            )

    async def authorize(
        self, client: OAuthClientInformationFull, params: AuthorizationParams
    ) -> str:
        if params.resource != self._resource_url:
            raise AuthorizeError("invalid_target", "Use the canonical KYA Registry resource")
        scopes = tuple(params.scopes or ("catalog:read",))
        if not scopes or not set(scopes).issubset(VALID_SCOPES):
            raise AuthorizeError("invalid_scope", "Unsupported KYA scope")
        handle = _opaque_token()
        now = datetime.now(UTC)
        async with self._sessions.begin() as session:
            session.add(
                OAuthGrant(
                    request_digest=_digest(handle),
                    client_id=client.client_id,
                    redirect_uri=str(params.redirect_uri),
                    redirect_uri_explicit=params.redirect_uri_provided_explicitly,
                    code_challenge=params.code_challenge,
                    scopes=list(scopes),
                    state=params.state,
                    resource=self._resource_url,
                    expires_at=now + self._request_ttl,
                )
            )
        separator = "&" if "?" in self._consent_url else "?"
        return f"{self._consent_url}{separator}{urlencode({'request': handle})}"

    async def get_consent_request(self, handle: str) -> ConsentRequest | None:
        now = datetime.now(UTC)
        async with self._sessions() as session:
            statement = (
                select(OAuthGrant, OAuthClient)
                .join(OAuthClient, OAuthClient.client_id == OAuthGrant.client_id)
                .where(
                    OAuthGrant.request_digest == _digest(handle),
                    OAuthGrant.approved_at.is_(None),
                    OAuthGrant.denied_at.is_(None),
                    OAuthGrant.expires_at > now,
                )
            )
            result = (await session.execute(statement)).one_or_none()
        if result is None:
            return None
        grant, client = result
        return ConsentRequest(
            client_name=str(client.client_metadata.get("client_name") or "Client MCP"),
            scopes=tuple(grant.scopes),
            resource=grant.resource,
            expires_at=grant.expires_at,
        )

    async def approve(self, handle: str, *, principal_id: UUID, active_unit_id: str) -> str | None:
        now = datetime.now(UTC)
        code = _opaque_token()
        async with self._sessions.begin() as session:
            statement = (
                select(OAuthGrant)
                .where(
                    OAuthGrant.request_digest == _digest(handle),
                    OAuthGrant.approved_at.is_(None),
                    OAuthGrant.denied_at.is_(None),
                    OAuthGrant.expires_at > now,
                )
                .with_for_update()
            )
            grant = await session.scalar(statement)
            if grant is None:
                return None
            grant.code_digest = _digest(code)
            grant.principal_id = principal_id
            grant.active_unit_id = active_unit_id
            grant.approved_at = now
            grant.expires_at = now + self._code_ttl
            redirect_uri, state = grant.redirect_uri, grant.state
        return construct_redirect_uri(redirect_uri, code=code, state=state, iss=self._issuer_url)

    async def deny(self, handle: str) -> str | None:
        now = datetime.now(UTC)
        async with self._sessions.begin() as session:
            statement = (
                select(OAuthGrant)
                .where(
                    OAuthGrant.request_digest == _digest(handle),
                    OAuthGrant.approved_at.is_(None),
                    OAuthGrant.denied_at.is_(None),
                    OAuthGrant.expires_at > now,
                )
                .with_for_update()
            )
            grant = await session.scalar(statement)
            if grant is None:
                return None
            grant.denied_at = now
            redirect_uri, state = grant.redirect_uri, grant.state
        return construct_redirect_uri(
            redirect_uri,
            error="access_denied",
            state=state,
            iss=self._issuer_url,
        )

    async def load_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: str
    ) -> BrokerAuthorizationCode | None:
        now = datetime.now(UTC)
        async with self._sessions() as session:
            statement = select(OAuthGrant).where(
                OAuthGrant.code_digest == _digest(authorization_code),
                OAuthGrant.client_id == client.client_id,
                OAuthGrant.approved_at.is_not(None),
                OAuthGrant.denied_at.is_(None),
                OAuthGrant.consumed_at.is_(None),
                OAuthGrant.expires_at > now,
            )
            grant = await session.scalar(statement)
        if grant is None or grant.principal_id is None or grant.active_unit_id is None:
            return None
        return BrokerAuthorizationCode(
            code=authorization_code,
            scopes=grant.scopes,
            expires_at=grant.expires_at.timestamp(),
            client_id=grant.client_id,
            code_challenge=grant.code_challenge,
            redirect_uri=grant.redirect_uri,
            redirect_uri_provided_explicitly=grant.redirect_uri_explicit,
            resource=grant.resource,
            subject=str(grant.principal_id),
            grant_id=grant.id,
            principal_id=grant.principal_id,
            active_unit_id=grant.active_unit_id,
        )

    async def exchange_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: AuthorizationCode
    ) -> OAuthToken:
        if not isinstance(authorization_code, BrokerAuthorizationCode):
            raise TokenError("invalid_grant", "Unknown authorization code")
        now = datetime.now(UTC)
        access, refresh = _opaque_token(), _opaque_token()
        async with self._sessions.begin() as session:
            result = await session.execute(
                update(OAuthGrant)
                .where(
                    OAuthGrant.id == authorization_code.grant_id,
                    OAuthGrant.client_id == client.client_id,
                    OAuthGrant.consumed_at.is_(None),
                    OAuthGrant.expires_at > now,
                )
                .values(consumed_at=now)
            )
            if result.rowcount != 1:  # type: ignore[attr-defined]
                raise TokenError("invalid_grant", "Authorization code already used")
            self._add_token_pair(
                session,
                grant_id=authorization_code.grant_id,
                client_id=client.client_id,
                principal_id=authorization_code.principal_id,
                active_unit_id=authorization_code.active_unit_id,
                scopes=authorization_code.scopes,
                resource=cast(str, authorization_code.resource),
                access=access,
                refresh=refresh,
                now=now,
            )
        return self._oauth_token(access, refresh, authorization_code.scopes)

    async def load_refresh_token(
        self, client: OAuthClientInformationFull, refresh_token: str
    ) -> BrokerRefreshToken | None:
        row = await self._load_token(refresh_token, kind="refresh", client_id=client.client_id)
        if row is None:
            return None
        return BrokerRefreshToken(
            token=refresh_token,
            client_id=row.client_id,
            scopes=row.scopes,
            expires_at=int(row.expires_at.timestamp()),
            subject=str(row.principal_id),
            grant_id=row.grant_id,
            principal_id=row.principal_id,
            active_unit_id=row.active_unit_id,
            resource=row.resource,
        )

    async def exchange_refresh_token(
        self,
        client: OAuthClientInformationFull,
        refresh_token: RefreshToken,
        scopes: list[str],
    ) -> OAuthToken:
        if not isinstance(refresh_token, BrokerRefreshToken):
            raise TokenError("invalid_grant", "Unknown refresh token")
        if not set(scopes).issubset(refresh_token.scopes):
            raise TokenError("invalid_scope", "Scopes cannot be expanded during refresh")
        now = datetime.now(UTC)
        access, refresh = _opaque_token(), _opaque_token()
        async with self._sessions.begin() as session:
            result = await session.execute(
                update(OAuthTokenRecord)
                .where(
                    OAuthTokenRecord.token_digest == _digest(refresh_token.token),
                    OAuthTokenRecord.kind == "refresh",
                    OAuthTokenRecord.client_id == client.client_id,
                    OAuthTokenRecord.revoked_at.is_(None),
                    OAuthTokenRecord.expires_at > now,
                )
                .values(revoked_at=now)
            )
            if result.rowcount != 1:  # type: ignore[attr-defined]
                raise TokenError("invalid_grant", "Refresh token already used")
            self._add_token_pair(
                session,
                grant_id=refresh_token.grant_id,
                client_id=client.client_id,
                principal_id=refresh_token.principal_id,
                active_unit_id=refresh_token.active_unit_id,
                scopes=scopes,
                resource=refresh_token.resource,
                access=access,
                refresh=refresh,
                now=now,
            )
        return self._oauth_token(access, refresh, scopes)

    async def load_access_token(self, token: str) -> BrokerAccessToken | None:
        row = await self._load_token(token, kind="access")
        if row is None or row.resource != self._resource_url:
            return None
        return BrokerAccessToken(
            token=token,
            client_id=row.client_id,
            scopes=row.scopes,
            expires_at=int(row.expires_at.timestamp()),
            resource=row.resource,
            subject=str(row.principal_id),
            claims={"iss": self._issuer_url, "active_unit": row.active_unit_id},
            grant_id=row.grant_id,
        )

    async def revoke_token(self, token: AccessToken | RefreshToken) -> None:
        grant_id = getattr(token, "grant_id", None)
        if not isinstance(grant_id, UUID):
            return
        async with self._sessions.begin() as session:
            await session.execute(
                update(OAuthTokenRecord)
                .where(OAuthTokenRecord.grant_id == grant_id, OAuthTokenRecord.revoked_at.is_(None))
                .values(revoked_at=datetime.now(UTC))
            )

    async def exchange_identity_assertion(
        self,
        client: OAuthClientInformationFull,
        params: IdentityAssertionParams,
    ) -> OAuthToken:
        del client, params
        raise TokenError(
            "unsupported_grant_type",
            "Identity assertion exchange is not enabled",
        )

    async def _load_token(
        self, raw_token: str, *, kind: str, client_id: str | None = None
    ) -> OAuthTokenRecord | None:
        now = datetime.now(UTC)
        conditions = [
            OAuthTokenRecord.token_digest == _digest(raw_token),
            OAuthTokenRecord.kind == kind,
            OAuthTokenRecord.revoked_at.is_(None),
            OAuthTokenRecord.expires_at > now,
        ]
        if client_id is not None:
            conditions.append(OAuthTokenRecord.client_id == client_id)
        async with self._sessions() as session:
            return cast(
                OAuthTokenRecord | None,
                await session.scalar(select(OAuthTokenRecord).where(*conditions)),
            )

    def _add_token_pair(
        self,
        session: AsyncSession,
        *,
        grant_id: UUID,
        client_id: str,
        principal_id: UUID,
        active_unit_id: str,
        scopes: list[str],
        resource: str,
        access: str,
        refresh: str,
        now: datetime,
    ) -> None:
        common = {
            "grant_id": grant_id,
            "client_id": client_id,
            "principal_id": principal_id,
            "active_unit_id": active_unit_id,
            "scopes": scopes,
            "resource": resource,
        }
        session.add(
            OAuthTokenRecord(
                **common,
                token_digest=_digest(access),
                kind="access",
                expires_at=now + self._access_ttl,
            )
        )
        session.add(
            OAuthTokenRecord(
                **common,
                token_digest=_digest(refresh),
                kind="refresh",
                expires_at=now + self._refresh_ttl,
            )
        )

    def _oauth_token(self, access: str, refresh: str, scopes: list[str]) -> OAuthToken:
        return OAuthToken(
            access_token=access,
            expires_in=int(self._access_ttl.total_seconds()),
            scope=" ".join(scopes),
            refresh_token=refresh,
        )


__all__ = ["VALID_SCOPES", "ActiveConnectorGrant", "ConsentRequest", "OAuthBroker"]
