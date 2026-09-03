"""Immutable identity established by a verified authentication token."""

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any


@dataclass(frozen=True, slots=True)
class AuthenticatedIdentity:
    """Stable external identity; permissions are deliberately not embedded here."""

    issuer: str
    subject: str
    claims: Mapping[str, Any]

    def __post_init__(self) -> None:
        if not self.issuer or not self.subject:
            raise ValueError("issuer and subject must be non-empty")
        object.__setattr__(self, "claims", MappingProxyType(dict(self.claims)))
