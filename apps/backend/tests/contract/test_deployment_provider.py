from uuid import uuid4

import pytest

from kya_platform.infrastructure.deployment import (
    CoolifyAdapter,
    DeploymentRequest,
    DokployAdapter,
)


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", [DokployAdapter(), CoolifyAdapter()])
async def test_provider_conformance(provider: object) -> None:
    request = DeploymentRequest("hub", "abc123", "preview")
    record = await provider.deploy(request)  # type: ignore[attr-defined]
    assert record.status == "deployed"
    assert record.provider in {"dokploy", "coolify"}
    assert (await provider.rollback(record.id)).status == "rolled_back"  # type: ignore[attr-defined]


def test_request_rejects_unknown_environment() -> None:
    with pytest.raises(ValueError):
        DeploymentRequest("hub", str(uuid4()), "qa")
