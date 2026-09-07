"""Persistent OAuth broker state; raw credentials are never stored."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, LargeBinary, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from kya_platform.infrastructure.database.base import Base, new_id


class OAuthClient(Base):
    __tablename__ = "client"
    __table_args__ = ({"schema": "oauth"},)

    client_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    client_metadata: Mapped[dict[str, object]] = mapped_column("metadata", JSONB, nullable=False)
    encrypted_secret: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class OAuthGrant(Base):
    __tablename__ = "grant"
    __table_args__ = (
        Index("ix_oauth_grant_request_digest", "request_digest", unique=True),
        Index("ix_oauth_grant_code_digest", "code_digest", unique=True),
        {"schema": "oauth"},
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    request_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    code_digest: Mapped[str | None] = mapped_column(String(64), nullable=True)
    client_id: Mapped[str] = mapped_column(
        ForeignKey("oauth.client.client_id", ondelete="CASCADE"), nullable=False
    )
    redirect_uri: Mapped[str] = mapped_column(Text, nullable=False)
    redirect_uri_explicit: Mapped[bool] = mapped_column(Boolean, nullable=False)
    code_challenge: Mapped[str] = mapped_column(String(128), nullable=False)
    scopes: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    state: Mapped[str | None] = mapped_column(Text, nullable=True)
    resource: Mapped[str] = mapped_column(Text, nullable=False)
    principal_id: Mapped[UUID | None] = mapped_column(nullable=True)
    active_unit_id: Mapped[str | None] = mapped_column(String(512), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    denied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class OAuthTokenRecord(Base):
    __tablename__ = "token"
    __table_args__ = (
        Index("ix_oauth_token_digest", "token_digest", unique=True),
        Index("ix_oauth_token_grant", "grant_id"),
        {"schema": "oauth"},
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    token_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    grant_id: Mapped[UUID] = mapped_column(
        ForeignKey("oauth.grant.id", ondelete="CASCADE"), nullable=False
    )
    client_id: Mapped[str] = mapped_column(String(128), nullable=False)
    principal_id: Mapped[UUID] = mapped_column(nullable=False)
    active_unit_id: Mapped[str] = mapped_column(String(512), nullable=False)
    scopes: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    resource: Mapped[str] = mapped_column(Text, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


__all__ = ["OAuthClient", "OAuthGrant", "OAuthTokenRecord"]
