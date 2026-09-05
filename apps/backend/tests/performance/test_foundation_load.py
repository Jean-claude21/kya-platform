"""Bounded load gates for the in-process foundation hot paths."""

import asyncio
from collections.abc import Awaitable, Callable, Sequence
from time import perf_counter
from uuid import uuid4

import httpx
import pytest

from kya_platform.application.catalog import CatalogItem, CatalogSearchService
from kya_platform.authorization import (
    AuthorizationDecision,
    CheckRequest,
    ListObjectsRequest,
)
from kya_platform.authorization.service import AuthorizationService
from kya_platform.config import Settings
from kya_platform.main import create_app
from kya_platform.mcp.registry import Confirmation, RequestInstallInput


def percentile(values: Sequence[float], quantile: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(len(ordered) * quantile))]


async def timed[T](operation: Callable[[], Awaitable[T]]) -> tuple[T, float]:
    started_at = perf_counter()
    result = await operation()
    return result, perf_counter() - started_at


class FastPolicy:
    async def check(self, request: CheckRequest) -> AuthorizationDecision:
        return AuthorizationDecision(allowed=True, model_id="load-test-model")

    async def list_objects(self, request: ListObjectsRequest) -> tuple[str, ...]:
        return tuple(f"artifact:skill-{index}" for index in range(50))


class FastIndex:
    async def search(
        self, *, query: str, allowed_ids: tuple[str, ...], limit: int
    ) -> tuple[CatalogItem, ...]:
        return tuple(
            CatalogItem(item_id, f"Skill {item_id}", "skill", "1.0.0", "compatible")
            for item_id in allowed_ids[:limit]
        )


@pytest.mark.performance
@pytest.mark.asyncio
async def test_authorization_and_catalog_p95_stay_within_contract() -> None:
    policy = FastPolicy()
    authorization = AuthorizationService(policy)
    catalog = CatalogSearchService(authorization=policy, search_index=FastIndex())
    check = CheckRequest(user="user:alice", relation="can_view", object="artifact:skill-1")

    authorization_results = await asyncio.gather(
        *(timed(lambda: authorization.explain(check, correlation_id=uuid4())) for _ in range(500))
    )
    catalog_results = await asyncio.gather(
        *(
            timed(
                lambda: catalog.search(
                    user="user:alice",
                    query="skill",
                    context={},
                    contextual_tuples=(),
                )
            )
            for _ in range(250)
        )
    )

    assert percentile([latency for _, latency in authorization_results], 0.95) < 0.100
    assert percentile([latency for _, latency in catalog_results], 0.95) < 0.500


@pytest.mark.performance
@pytest.mark.asyncio
async def test_health_api_p95_stays_below_half_a_second() -> None:
    app = create_app(Settings(environment="test"))
    transport = httpx.ASGITransport(app=app)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            results = await asyncio.gather(
                *(timed(lambda: client.get("/api/v1/health/ready")) for _ in range(200))
            )

    assert all(response.status_code == 200 for response, _ in results)
    assert percentile([latency for _, latency in results], 0.95) < 0.500


@pytest.mark.performance
def test_mcp_install_contract_handles_burst_without_relaxing_validation() -> None:
    started_at = perf_counter()
    requests = [
        RequestInstallInput(
            release_id=uuid4(),
            target="workspace:dss",
            idempotency_key=f"load-install-{index:06d}",
            confirmation=Confirmation(confirmed=True),
        )
        for index in range(2_000)
    ]
    elapsed = perf_counter() - started_at

    assert len(requests) == 2_000
    assert elapsed < 2.0
