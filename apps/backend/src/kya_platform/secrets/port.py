"""Provider-neutral catalog port for secret references."""

from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

from kya_platform.secrets.model import SecretReference


class SecretReferencePort(Protocol):
    async def get(self, reference_id: UUID) -> SecretReference | None:
        """Return governance metadata without resolving the secret value."""

    async def list_for_scope(self, owner_scope: str) -> Sequence[SecretReference]:
        """List only references visible in one authorized scope."""

    async def register(self, reference: SecretReference) -> None:
        """Register an opaque provider locator."""

    async def revoke(self, reference_id: UUID) -> None:
        """Disable future use without disclosing or deleting audit metadata."""


__all__ = ["SecretReferencePort"]
