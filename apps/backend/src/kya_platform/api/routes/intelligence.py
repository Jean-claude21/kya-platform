"""Authorized HTTP surface for KYA Intelligence watchlists."""

from datetime import UTC, datetime, timedelta
from typing import Annotated, cast
from uuid import UUID, uuid7

from fastapi import APIRouter, Depends, Header, Query, Request, status
from pydantic import BaseModel, Field

from kya_platform.api.security import AuthorizedPrincipal, require_permission
from kya_platform.application.core import CoreService
from kya_platform.application.data import CommandMetadata
from kya_platform.application.intelligence import (
    IntelligenceConflictError,
    IntelligenceReferenceError,
    IntelligenceService,
    IntelligenceStateError,
)
from kya_platform.application.reliability import JsonValue, canonical_request_hash
from kya_platform.domain.intelligence import IntelligenceSignal, IntelligenceWatch
from kya_platform.observability import ApiError

router = APIRouter(prefix="/intelligence/organization/{unit_key}", tags=["intelligence"])
view_unit = require_permission(
    relation="can_view", object_type="org_unit", object_parameter="unit_key"
)
manage_unit = require_permission(
    relation="can_manage", object_type="org_unit", object_parameter="unit_key"
)
_KEY_PATTERN = r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$"


class WatchCreateRequest(BaseModel):
    key: str = Field(pattern=_KEY_PATTERN, max_length=120)
    name: str = Field(min_length=1, max_length=240)
    query: str = Field(min_length=2, max_length=200)
    asset_keys: list[str] = Field(default_factory=list, max_length=50)


class WatchResponse(BaseModel):
    id: UUID
    key: str
    name: str
    query: str
    asset_keys: list[str]
    status: str
    revision: int
    created_by: UUID
    created_at: datetime | None
    updated_at: datetime | None


class WatchListResponse(BaseModel):
    items: list[WatchResponse]


class SignalResponse(BaseModel):
    id: UUID
    watch_id: UUID
    citation_id: str
    source_uri: str
    title: str | None
    excerpt: str
    observed_at: datetime
    snapshot_digest: str
    page_digest: str
    status: str
    revision: int
    acknowledged_by: UUID | None
    acknowledged_at: datetime | None


class SignalListResponse(BaseModel):
    items: list[SignalResponse]


class EvaluationResponse(BaseModel):
    watch: WatchResponse
    matched_count: int
    created_count: int
    created_signals: list[SignalResponse]


def _service(request: Request) -> IntelligenceService:
    service: IntelligenceService | None = getattr(request.app.state, "intelligence_service", None)
    if service is None:
        raise ApiError(503, "intelligence_unavailable", "KYA Intelligence indisponible", "")
    return service


async def _unit_id(request: Request, unit_key: str) -> UUID:
    core: CoreService | None = getattr(request.app.state, "core_service", None)
    if core is None:
        raise ApiError(503, "core_service_unavailable", "KYA Core indisponible", "")
    unit = await core.get_unit(unit_key)
    if unit is None:
        raise ApiError(404, "core_unit_not_found", "Unité introuvable", "")
    return unit.id


def _command(
    request: Request,
    principal: AuthorizedPrincipal,
    idempotency_key: str,
    payload: BaseModel | dict[str, object],
) -> CommandMetadata:
    body = payload.model_dump(mode="json") if isinstance(payload, BaseModel) else payload
    return CommandMetadata(
        principal.principal_id,
        UUID(request.state.correlation_id),
        idempotency_key,
        canonical_request_hash(cast(JsonValue, body)),
        datetime.now(UTC) + timedelta(hours=24),
    )


def _watch_response(item: IntelligenceWatch) -> WatchResponse:
    return WatchResponse(
        id=item.id,
        key=item.key,
        name=item.name,
        query=item.query,
        asset_keys=list(item.asset_keys),
        status=item.status.value,
        revision=item.revision,
        created_by=item.created_by,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def _signal_response(item: IntelligenceSignal) -> SignalResponse:
    return SignalResponse(
        id=item.id,
        watch_id=item.watch_id,
        citation_id=item.citation_id,
        source_uri=item.source_uri,
        title=item.title,
        excerpt=item.excerpt,
        observed_at=item.observed_at,
        snapshot_digest=item.snapshot_digest,
        page_digest=item.page_digest,
        status=item.status.value,
        revision=item.revision,
        acknowledged_by=item.acknowledged_by,
        acknowledged_at=item.acknowledged_at,
    )


def _translate(error: Exception) -> ApiError:
    if isinstance(error, IntelligenceConflictError):
        return ApiError(409, "intelligence_conflict", "Conflit de veille", str(error))
    if isinstance(error, IntelligenceStateError):
        return ApiError(409, "intelligence_invalid_state", "État incompatible", str(error))
    return ApiError(404, "intelligence_reference_not_found", "Référence introuvable", str(error))


@router.post("/watches", response_model=WatchResponse, status_code=status.HTTP_201_CREATED)
async def create_watch(
    unit_key: str,
    payload: WatchCreateRequest,
    request: Request,
    principal: Annotated[AuthorizedPrincipal, Depends(manage_unit)],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=16, max_length=200)],
) -> WatchResponse:
    unit_id = await _unit_id(request, unit_key)
    try:
        watch = IntelligenceWatch(
            uuid7(),
            payload.key,
            payload.name,
            payload.query,
            unit_id,
            principal.principal_id,
            tuple(payload.asset_keys),
        )
        created = await _service(request).create_watch(
            unit_key, watch, command=_command(request, principal, idempotency_key, payload)
        )
    except ValueError as error:
        raise ApiError(422, "intelligence_watch_invalid", "Veille invalide", str(error)) from error
    except (IntelligenceConflictError, IntelligenceReferenceError) as error:
        raise _translate(error) from error
    return _watch_response(created)


@router.get("/watches", response_model=WatchListResponse)
async def list_watches(
    unit_key: str,
    request: Request,
    _principal: Annotated[AuthorizedPrincipal, Depends(view_unit)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> WatchListResponse:
    items = await _service(request).list_watches(unit_key, limit=limit)
    return WatchListResponse(items=[_watch_response(item) for item in items])


@router.post("/watches/{watch_key}/evaluate", response_model=EvaluationResponse)
async def evaluate_watch(
    unit_key: str,
    watch_key: str,
    request: Request,
    principal: Annotated[AuthorizedPrincipal, Depends(manage_unit)],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=16, max_length=200)],
    limit: Annotated[int, Query(ge=1, le=50)] = 50,
) -> EvaluationResponse:
    try:
        result = await _service(request).evaluate_watch(
            unit_key,
            watch_key,
            limit=limit,
            command=_command(
                request, principal, idempotency_key, {"watch_key": watch_key, "limit": limit}
            ),
        )
    except (IntelligenceConflictError, IntelligenceReferenceError, IntelligenceStateError) as error:
        raise _translate(error) from error
    return EvaluationResponse(
        watch=_watch_response(result.watch),
        matched_count=result.matched_count,
        created_count=len(result.created_signals),
        created_signals=[_signal_response(item) for item in result.created_signals],
    )


@router.get("/watches/{watch_key}/signals", response_model=SignalListResponse)
async def list_signals(
    unit_key: str,
    watch_key: str,
    request: Request,
    _principal: Annotated[AuthorizedPrincipal, Depends(view_unit)],
    only_open: bool = True,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> SignalListResponse:
    items = await _service(request).list_signals(
        unit_key, watch_key, only_open=only_open, limit=limit
    )
    return SignalListResponse(items=[_signal_response(item) for item in items])


@router.post("/signals/{signal_id}/acknowledge", response_model=SignalResponse)
async def acknowledge_signal(
    unit_key: str,
    signal_id: UUID,
    request: Request,
    principal: Annotated[AuthorizedPrincipal, Depends(manage_unit)],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=16, max_length=200)],
    expected_revision: Annotated[int, Header(alias="If-Match", ge=1)],
) -> SignalResponse:
    try:
        item = await _service(request).acknowledge_signal(
            unit_key,
            signal_id,
            expected_revision=expected_revision,
            acknowledged_at=datetime.now(UTC),
            command=_command(
                request,
                principal,
                idempotency_key,
                {"signal_id": str(signal_id), "expected_revision": expected_revision},
            ),
        )
    except (IntelligenceConflictError, IntelligenceReferenceError, IntelligenceStateError) as error:
        raise _translate(error) from error
    return _signal_response(item)


__all__ = ["router"]
