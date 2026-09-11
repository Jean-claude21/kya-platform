"""Secret reference persistence never stores or discloses credential values."""

from datetime import UTC, datetime
from typing import Self
from uuid import UUID

import pytest

from kya_platform.infrastructure.database.models import SecretReferenceRow
from kya_platform.infrastructure.database.secrets import SqlAlchemySecretReferenceRepository
from kya_platform.secrets import SecretKind, SecretReference, SecretStatus

REFERENCE_ID = UUID("019a1000-0000-7000-8000-000000000001")
CREATED_AT = datetime(2026, 9, 4, tzinfo=UTC)


def row() -> SecretReferenceRow:
    return SecretReferenceRow(
        id=REFERENCE_ID,
        kind="service",
        provider="infisical",
        locator="kya/preview/DOKPLOY_TOKEN",
        key_name="DOKPLOY_TOKEN",
        owner_scope="workspace:platform",
        purpose="Déployer une preview",
        environment="preview",
        status="active",
        created_at=CREATED_AT,
        rotated_at=None,
        expires_at=None,
    )


def reference() -> SecretReference:
    return SecretReference(
        id=REFERENCE_ID,
        kind=SecretKind.SERVICE,
        provider="infisical",
        locator="kya/preview/DOKPLOY_TOKEN",
        key_name="DOKPLOY_TOKEN",
        owner_scope="workspace:platform",
        purpose="Déployer une preview",
        environment="preview",
        status=SecretStatus.ACTIVE,
        created_at=CREATED_AT,
    )


class ScalarsResult:
    def __init__(self, values: list[object]) -> None:
        self.values = values

    def __iter__(self) -> object:
        return iter(self.values)


class Session:
    def __init__(
        self,
        *,
        scalar_values: list[object] | None = None,
        scalars_values: list[list[object]] | None = None,
        get_values: list[object] | None = None,
    ) -> None:
        self.scalar_values = scalar_values or []
        self.scalars_values = scalars_values or []
        self.get_values = get_values or []
        self.added: list[object] = []
        self.committed = False

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def scalar(self, statement: object) -> object:
        return self.scalar_values.pop(0)

    async def scalars(self, statement: object) -> ScalarsResult:
        return ScalarsResult(self.scalars_values.pop(0))

    async def get(self, model: object, identifier: object) -> object:
        return self.get_values.pop(0)

    def add(self, value: object) -> None:
        self.added.append(value)

    async def commit(self) -> None:
        self.committed = True


class Sessions:
    def __init__(self, session: Session) -> None:
        self.session = session

    def __call__(self) -> Session:
        return self.session


@pytest.mark.asyncio
async def test_get_returns_none_for_an_unknown_id() -> None:
    session = Session(scalar_values=[None])
    repository = SqlAlchemySecretReferenceRepository(Sessions(session))

    result = await repository.get(REFERENCE_ID)

    assert result is None


@pytest.mark.asyncio
async def test_get_maps_a_persisted_row_without_a_value_field() -> None:
    session = Session(scalar_values=[row()])
    repository = SqlAlchemySecretReferenceRepository(Sessions(session))

    result = await repository.get(REFERENCE_ID)

    assert result is not None
    assert result.locator == "kya/preview/DOKPLOY_TOKEN"
    assert not hasattr(result, "value")


@pytest.mark.asyncio
async def test_list_by_ids_returns_empty_without_querying_for_an_empty_request() -> None:
    session = Session()
    repository = SqlAlchemySecretReferenceRepository(Sessions(session))

    result = await repository.list_by_ids(())

    assert result == ()


@pytest.mark.asyncio
async def test_list_by_ids_preserves_the_authorized_id_order() -> None:
    other = SecretReferenceRow(
        id=UUID("019a1000-0000-7000-8000-000000000002"),
        kind="service",
        provider="infisical",
        locator="kya/preview/OTHER",
        key_name="OTHER",
        owner_scope="workspace:platform",
        purpose="Autre usage",
        environment="preview",
        status="active",
        created_at=CREATED_AT,
    )
    session = Session(scalars_values=[[other, row()]])
    repository = SqlAlchemySecretReferenceRepository(Sessions(session))

    result = await repository.list_by_ids((REFERENCE_ID, other.id))

    assert [item.id for item in result] == [REFERENCE_ID, other.id]


@pytest.mark.asyncio
async def test_register_inserts_a_new_reference_and_commits() -> None:
    session = Session(get_values=[None])
    repository = SqlAlchemySecretReferenceRepository(Sessions(session))

    await repository.register(reference())

    assert session.committed is True
    assert len(session.added) == 1
    added = session.added[0]
    assert isinstance(added, SecretReferenceRow)
    assert added.locator == "kya/preview/DOKPLOY_TOKEN"
    assert added.status == "active"


@pytest.mark.asyncio
async def test_register_updates_an_existing_reference_in_place() -> None:
    existing = row()
    session = Session(get_values=[existing])
    repository = SqlAlchemySecretReferenceRepository(Sessions(session))
    updated = reference().model_copy(update={"purpose": "Nouvelle finalité"})

    await repository.register(updated)

    assert session.committed is True
    assert session.added == []
    assert existing.purpose == "Nouvelle finalité"


@pytest.mark.asyncio
async def test_revoke_flips_status_without_deleting_the_row() -> None:
    existing = row()
    session = Session(get_values=[existing])
    repository = SqlAlchemySecretReferenceRepository(Sessions(session))

    await repository.revoke(REFERENCE_ID)

    assert existing.status == "revoked"
    assert session.committed is True


@pytest.mark.asyncio
async def test_revoke_is_a_no_op_for_an_unknown_id() -> None:
    session = Session(get_values=[None])
    repository = SqlAlchemySecretReferenceRepository(Sessions(session))

    await repository.revoke(REFERENCE_ID)

    assert session.committed is False
