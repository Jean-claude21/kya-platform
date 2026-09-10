"""Neon adapter for workspace boundaries and dated memberships."""

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from kya_platform.domain.organization import DateRange
from kya_platform.domain.workspaces import (
    AccessLevel,
    Workspace,
    WorkspaceKind,
    WorkspaceMembership,
)
from kya_platform.infrastructure.database.models import (
    WorkspaceLinkedUnitRow,
    WorkspaceMembershipRow,
    WorkspaceRow,
)


def _workspace(row: WorkspaceRow, linked_unit_ids: frozenset[UUID]) -> Workspace:
    return Workspace(
        id=row.id,
        key=row.key,
        name=row.name,
        kind=WorkspaceKind(row.kind),
        validity=DateRange(row.valid_from, row.valid_until),
        owner_unit_id=row.owner_unit_id,
        linked_unit_ids=linked_unit_ids,
        classification=row.classification,
    )


class SqlAlchemyWorkspaceRepository:
    """Implements both the workspace query and command ports against Neon."""

    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def get(self, workspace_key: str) -> Workspace | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(WorkspaceRow).where(WorkspaceRow.key == workspace_key)
            )
            if row is None:
                return None
            linked = await session.scalars(
                select(WorkspaceLinkedUnitRow.unit_id).where(
                    WorkspaceLinkedUnitRow.workspace_id == row.id
                )
            )
            return _workspace(row, frozenset(linked))

    async def list_by_keys(self, workspace_keys: Sequence[str]) -> Sequence[Workspace]:
        if not workspace_keys:
            return ()
        async with self._sessions() as session:
            rows = await session.scalars(
                select(WorkspaceRow).where(WorkspaceRow.key.in_(tuple(workspace_keys)))
            )
            materialized = list(rows)
            if not materialized:
                return ()
            linked_rows = await session.execute(
                select(WorkspaceLinkedUnitRow.workspace_id, WorkspaceLinkedUnitRow.unit_id).where(
                    WorkspaceLinkedUnitRow.workspace_id.in_(row.id for row in materialized)
                )
            )
            linked_by_workspace: dict[UUID, set[UUID]] = {}
            for workspace_id, unit_id in linked_rows:
                linked_by_workspace.setdefault(workspace_id, set()).add(unit_id)
            by_key = {row.key: row for row in materialized}
            return tuple(
                _workspace(by_key[key], frozenset(linked_by_workspace.get(by_key[key].id, ())))
                for key in workspace_keys
                if key in by_key
            )

    async def list_memberships(self, workspace_id: UUID) -> Sequence[WorkspaceMembership]:
        async with self._sessions() as session:
            rows = await session.scalars(
                select(WorkspaceMembershipRow)
                .where(WorkspaceMembershipRow.workspace_id == workspace_id)
                .order_by(WorkspaceMembershipRow.valid_from.desc())
            )
            return tuple(
                WorkspaceMembership(
                    workspace_id=row.workspace_id,
                    principal_id=row.principal_id,
                    level=AccessLevel(row.level),
                    validity=DateRange(row.valid_from, row.valid_until),
                    delegated_by=row.delegated_by,
                )
                for row in rows
            )

    async def add_membership(
        self, membership: WorkspaceMembership, *, actor_id: UUID
    ) -> WorkspaceMembership:
        async with self._sessions() as session:
            row = WorkspaceMembershipRow(
                workspace_id=membership.workspace_id,
                principal_id=membership.principal_id,
                level=membership.level.value,
                valid_from=membership.validity.valid_from,
                valid_until=membership.validity.valid_until,
                delegated_by=membership.delegated_by,
            )
            session.add(row)
            await session.commit()
        return membership


__all__ = ["SqlAlchemyWorkspaceRepository"]

