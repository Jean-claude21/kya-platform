from dataclasses import asdict
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from kya_platform.domain.organization import DateRange
from kya_platform.infrastructure.frappe import (
    FrappeAuthorityDeclaration,
    FrappeRegistryAdapter,
)


@pytest.mark.unit
def test_frappe_adapter_registers_references_without_business_rows() -> None:
    system_id = uuid4()
    registry = FrappeRegistryAdapter(
        system_id=system_id,
        base_url="https://erp.kya.energy/",
        business_owner="Direction Services Conseils",
    ).registry(
        (
            FrappeAuthorityDeclaration(
                uuid4(),
                "clients",
                "group:kya",
                DateRange(datetime(2026, 9, 1, tzinfo=UTC)),
            ),
        )
    )

    assert registry.systems[0].interfaces[0].contract_uri == ("https://erp.kya.energy/api/resource")
    assert registry.authorities[0].system_id == system_id
    serialized = repr(asdict(registry))
    assert "api_secret" not in serialized
    assert "records" not in serialized
    assert "clients-read" in serialized


@pytest.mark.unit
def test_frappe_adapter_rejects_plain_http_outside_local_development() -> None:
    with pytest.raises(ValueError, match="HTTPS"):
        FrappeRegistryAdapter(
            system_id=uuid4(),
            base_url="http://erp.kya.energy",
            business_owner="DSC",
        )


@pytest.mark.unit
def test_frappe_adapter_allows_local_http_for_development() -> None:
    adapter = FrappeRegistryAdapter(
        system_id=uuid4(),
        base_url="http://localhost:8000/",
        business_owner="DSC",
    )

    assert adapter.base_url == "http://localhost:8000"
