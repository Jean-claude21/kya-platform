"""KYA Core keeps real-world identity, work status and master data distinct."""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from kya_platform.domain.core import (
    ClientAccount,
    ClientStatus,
    ExternalReference,
    Party,
    PartyKind,
    PersonProfile,
    Project,
    ProjectStatus,
    Site,
    WorkRelationship,
    WorkRelationshipKind,
)
from kya_platform.domain.organization import DateRange

PERSON = UUID("01993400-0000-7000-8000-000000000001")
PARTY = UUID("01993400-0000-7000-8000-000000000002")
UNIT = UUID("01993400-0000-7000-8000-000000000003")
CLIENT = UUID("01993400-0000-7000-8000-000000000004")


def validity() -> DateRange:
    return DateRange(datetime(2026, 9, 1, tzinfo=UTC))


@pytest.mark.unit
def test_internship_is_a_temporal_relationship_not_a_person_kind() -> None:
    person = Party(PERSON, PartyKind.PERSON, "Afi Mensah")
    profile = PersonProfile(PERSON, "Afi", "Mensah")
    internship = WorkRelationship(
        UUID("01993400-0000-7000-8000-000000000010"),
        person.id,
        UNIT,
        WorkRelationshipKind.INTERN,
        validity(),
    )

    assert person.kind is PartyKind.PERSON
    assert profile.party_id == person.id
    assert internship.kind is WorkRelationshipKind.INTERN
    assert internship.principal_id is None


@pytest.mark.unit
def test_client_wraps_a_party_without_using_name_as_identity() -> None:
    party = Party(PARTY, PartyKind.ORGANIZATION, "Client Énergie SA")
    client = ClientAccount(
        CLIENT,
        "client-energie",
        party.id,
        UNIT,
        ClientStatus.ACTIVE,
        validity(),
    )

    assert client.party_id == party.id
    assert client.key != party.display_name


@pytest.mark.unit
def test_project_and_site_validate_stable_keys_and_country_codes() -> None:
    project = Project(
        UUID("01993400-0000-7000-8000-000000000020"),
        "solaire-lome",
        "Projet solaire Lomé",
        UNIT,
        ProjectStatus.PLANNED,
        validity(),
        client_id=CLIENT,
    )
    site = Site(
        UUID("01993400-0000-7000-8000-000000000021"),
        "site-lome-port",
        "Site du port",
        UNIT,
        PARTY,
        "TG",
    )

    assert project.client_id == CLIENT
    assert site.country_code == "TG"
    with pytest.raises(ValueError, match="ISO"):
        Site(site.id, site.key, site.name, UNIT, PARTY, "togo")


@pytest.mark.unit
def test_external_reference_is_only_a_mapping_not_an_authority() -> None:
    reference = ExternalReference(
        UUID("01993400-0000-7000-8000-000000000030"),
        "frappe-production",
        "client",
        CLIENT,
        "Customer",
        "CUST-00042",
    )

    assert reference.entity_id == CLIENT
    assert not hasattr(reference, "permissions")
    assert not hasattr(reference, "credentials")


@pytest.mark.unit
def test_keys_and_versions_fail_early() -> None:
    with pytest.raises(ValueError, match="kebab-case"):
        ClientAccount(CLIENT, "Client 42", PARTY, UNIT, ClientStatus.ACTIVE, validity())
    with pytest.raises(ValueError, match="positive"):
        Party(PARTY, PartyKind.ORGANIZATION, "Client", version=0)
