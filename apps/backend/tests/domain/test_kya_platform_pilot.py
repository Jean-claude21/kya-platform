"""The first real registered system owns only KYA Platform data."""

from datetime import UTC, datetime

from kya_platform.domain.systems.pilots import KYA_PLATFORM_SYSTEM_ID, kya_platform_pilot

EFFECTIVE_AT = datetime(2026, 9, 5, tzinfo=UTC)


def test_kya_platform_is_initial_real_data_authority() -> None:
    registry = kya_platform_pilot(effective_at=EFFECTIVE_AT)

    authority = registry.authority_for(
        "artifact-metadata",
        "group:kya",
        at=datetime(2026, 9, 6, tzinfo=UTC),
    )

    assert authority.id == KYA_PLATFORM_SYSTEM_ID
    assert authority.key == "kya-platform"
    assert authority.environments == frozenset({"preview"})
    assert authority.interfaces[0].contract_uri == "/api/openapi.json"
    assert all(item.category_key != "clients" for item in registry.authorities)
