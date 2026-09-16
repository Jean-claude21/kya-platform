"""Authorized API for autonomous source-flow configuration and operation."""

from datetime import UTC, datetime, timedelta
from typing import Annotated, Any, cast
from uuid import UUID, uuid7

from fastapi import APIRouter, Depends, Header, Request, status
from pydantic import BaseModel, Field, field_validator

from kya_platform.api.security import AuthorizedPrincipal, require_permission
from kya_platform.application.core import CoreService
from kya_platform.application.data import CommandMetadata
from kya_platform.application.reliability import JsonValue, canonical_request_hash
from kya_platform.application.source_lifecycle import (
    SourceFlowConflictError,
    SourceFlowReferenceError,
    SourceFlowStateError,
    SourceLifecycleService,
)
from kya_platform.domain.data import (
    DataAsset,
    DataAssetLayer,
    DataClassification,
    DataContract,
    DataPipeline,
    DataSource,
    DataSourceKind,
    DataStatus,
    QualityRule,
)
from kya_platform.domain.source_lifecycle import IngestionSchedule, SourceFlow, SourceFlowDraft
from kya_platform.observability import ApiError

router = APIRouter(prefix="/data/organization/{unit_key}/flows", tags=["source-lifecycle"])
_KEY_PATTERN = r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$"
view_unit = require_permission(
    relation="can_view", object_type="org_unit", object_parameter="unit_key"
)
manage_unit = require_permission(
    relation="can_manage", object_type="org_unit", object_parameter="unit_key"
)


class ConnectorReference(BaseModel):
    key: str = Field(pattern=_KEY_PATTERN, max_length=120)
    version: str = Field(pattern=r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")


class SourceDefinition(BaseModel):
    kind: DataSourceKind
    configuration: dict[str, Any] = Field(default_factory=dict)
    secret_reference: str | None = Field(default=None, max_length=500)


class AssetDefinition(BaseModel):
    layer: DataAssetLayer = DataAssetLayer.RAW
    classification: DataClassification = DataClassification.INTERNAL


class QualityRuleDefinition(BaseModel):
    key: str = Field(pattern=_KEY_PATTERN, max_length=120)
    kind: str = Field(min_length=1, max_length=120)
    expression: str = Field(min_length=1, max_length=4000)
    severity: str = Field(default="error", pattern=r"^(warning|error)$")


class ContractDefinition(BaseModel):
    version: str = Field(
        default="1.0.0", pattern=r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$"
    )
    schema_document: dict[str, Any]
    quality_rules: list[QualityRuleDefinition] = Field(default_factory=list, max_length=100)
    freshness_minutes: int | None = Field(default=None, ge=1)
    retention_days: int | None = Field(default=None, ge=1)


class ScheduleDefinition(BaseModel):
    interval_minutes: int = Field(ge=15, le=43_200)
    next_run_at: datetime
    enabled: bool = True

    @field_validator("next_run_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("next_run_at must include a timezone")
        return value


class SourceFlowCreateRequest(BaseModel):
    key: str = Field(pattern=_KEY_PATTERN, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    source: SourceDefinition
    connector: ConnectorReference
    asset: AssetDefinition = Field(default_factory=AssetDefinition)
    contract: ContractDefinition
    schedule: ScheduleDefinition | None = None
    activate: bool = True


class SourceFlowScheduleRequest(ScheduleDefinition):
    pass


class ScheduleResponse(BaseModel):
    id: UUID
    interval_minutes: int
    next_run_at: datetime
    enabled: bool
    revision: int
    last_claimed_at: datetime | None


class SourceFlowResponse(BaseModel):
    key: str
    name: str
    status: DataStatus
    revision: int
    source_id: UUID
    source_key: str
    source_kind: DataSourceKind
    has_credentials: bool
    asset_id: UUID
    asset_key: str
    classification: DataClassification
    contract_id: UUID
    contract_version: str
    pipeline_id: UUID
    connector_version_id: UUID
    schedule: ScheduleResponse | None


class RunHealthResponse(BaseModel):
    id: UUID
    status: str
    started_at: datetime
    completed_at: datetime | None
    error_code: str | None


class SourceFlowHealthResponse(BaseModel):
    flow: SourceFlowResponse
    latest_run: RunHealthResponse | None
    latest_snapshot_id: UUID | None
    latest_snapshot_observed_at: datetime | None
    quality_status: str | None


def _service(request: Request) -> SourceLifecycleService:
    service: SourceLifecycleService | None = getattr(
        request.app.state, "source_lifecycle_service", None
    )
    if service is None:
        raise ApiError(503, "source_lifecycle_unavailable", "Cycle de vie indisponible", "")
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


def _translate(error: Exception) -> ApiError:
    if isinstance(error, SourceFlowConflictError):
        return ApiError(409, "source_flow_conflict", "Conflit de flux", str(error))
    if isinstance(error, SourceFlowStateError):
        return ApiError(409, "source_flow_invalid_state", "État incompatible", str(error))
    return ApiError(422, "source_flow_reference_invalid", "Référence invalide", str(error))


def _flow_response(flow: SourceFlow) -> SourceFlowResponse:
    schedule = flow.schedule
    return SourceFlowResponse(
        key=flow.key,
        name=flow.pipeline.name,
        status=flow.status,
        revision=flow.revision,
        source_id=flow.source.id,
        source_key=flow.source.key,
        source_kind=flow.source.kind,
        has_credentials=flow.source.secret_reference is not None,
        asset_id=flow.asset.id,
        asset_key=flow.asset.key,
        classification=flow.asset.classification,
        contract_id=flow.contract.id,
        contract_version=flow.contract.version,
        pipeline_id=flow.pipeline.id,
        connector_version_id=flow.pipeline.connector_version_id,
        schedule=ScheduleResponse(
            id=schedule.id,
            interval_minutes=schedule.interval_minutes,
            next_run_at=schedule.next_run_at,
            enabled=schedule.enabled,
            revision=schedule.revision,
            last_claimed_at=schedule.last_claimed_at,
        )
        if schedule is not None
        else None,
    )


@router.post("", response_model=SourceFlowResponse, status_code=status.HTTP_201_CREATED)
async def configure_source_flow(
    unit_key: str,
    payload: SourceFlowCreateRequest,
    request: Request,
    principal: Annotated[AuthorizedPrincipal, Depends(manage_unit)],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=16, max_length=200)],
) -> SourceFlowResponse:
    owner = await _unit_id(request, unit_key)
    lifecycle_status = DataStatus.ACTIVE if payload.activate else DataStatus.DRAFT
    try:
        source = DataSource(
            uuid7(),
            f"{payload.key}-source",
            f"{payload.name} — source",
            payload.source.kind,
            owner,
            secret_reference=payload.source.secret_reference,
            status=lifecycle_status,
            configuration=payload.source.configuration,
        )
        asset = DataAsset(
            uuid7(),
            f"{payload.key}-raw",
            f"{payload.name} — données brutes",
            owner,
            payload.asset.layer,
            payload.asset.classification,
            lifecycle_status,
        )
        contract_body = payload.contract.model_dump(mode="json")
        contract = DataContract(
            uuid7(),
            asset.id,
            payload.contract.version,
            payload.contract.schema_document,
            canonical_request_hash(cast(JsonValue, contract_body)),
            tuple(QualityRule(**item.model_dump()) for item in payload.contract.quality_rules),
            payload.contract.freshness_minutes,
            payload.contract.retention_days,
        )
        pipeline = DataPipeline(
            uuid7(),
            payload.key,
            payload.name,
            owner,
            source.id,
            UUID(int=0),
            asset.id,
            lifecycle_status,
        )
        schedule = (
            IngestionSchedule(
                uuid7(),
                pipeline.id,
                payload.schedule.interval_minutes,
                payload.schedule.next_run_at,
                payload.schedule.enabled,
            )
            if payload.schedule is not None
            else None
        )
        draft = SourceFlowDraft(
            source,
            asset,
            contract,
            pipeline,
            payload.connector.key,
            payload.connector.version,
        )
        flow = await _service(request).configure(
            unit_key,
            draft,
            schedule=schedule,
            command=_command(request, principal, idempotency_key, payload),
        )
    except ValueError as error:
        raise ApiError(422, "source_flow_invalid", "Flux invalide", str(error)) from error
    except (SourceFlowConflictError, SourceFlowReferenceError, SourceFlowStateError) as error:
        raise _translate(error) from error
    return _flow_response(flow)


@router.get("/{flow_key}", response_model=SourceFlowHealthResponse)
async def get_source_flow_health(
    unit_key: str,
    flow_key: str,
    request: Request,
    _principal: Annotated[AuthorizedPrincipal, Depends(view_unit)],
) -> SourceFlowHealthResponse:
    health = await _service(request).get_health(unit_key, flow_key)
    if health is None:
        raise ApiError(404, "source_flow_not_found", "Flux introuvable", "")
    run = health.latest_run
    return SourceFlowHealthResponse(
        flow=_flow_response(health.flow),
        latest_run=RunHealthResponse(
            id=run.id,
            status=run.status.value,
            started_at=run.started_at,
            completed_at=run.completed_at,
            error_code=run.error_code,
        )
        if run is not None
        else None,
        latest_snapshot_id=health.latest_snapshot_id,
        latest_snapshot_observed_at=health.latest_snapshot_observed_at,
        quality_status=health.quality_status,
    )


async def _transition(
    unit_key: str,
    flow_key: str,
    target: DataStatus,
    request: Request,
    principal: AuthorizedPrincipal,
    idempotency_key: str,
    expected_revision: int,
) -> SourceFlowResponse:
    try:
        flow = await _service(request).transition(
            unit_key,
            flow_key,
            target,
            expected_revision=expected_revision,
            command=_command(
                request,
                principal,
                idempotency_key,
                {"flow_key": flow_key, "status": target.value},
            ),
        )
    except (SourceFlowConflictError, SourceFlowReferenceError, SourceFlowStateError) as error:
        raise _translate(error) from error
    return _flow_response(flow)


@router.post("/{flow_key}/pause", response_model=SourceFlowResponse)
async def pause_source_flow(
    unit_key: str,
    flow_key: str,
    request: Request,
    principal: Annotated[AuthorizedPrincipal, Depends(manage_unit)],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=16, max_length=200)],
    expected_revision: Annotated[int, Header(alias="If-Match", ge=1)],
) -> SourceFlowResponse:
    return await _transition(
        unit_key,
        flow_key,
        DataStatus.PAUSED,
        request,
        principal,
        idempotency_key,
        expected_revision,
    )


@router.post("/{flow_key}/activate", response_model=SourceFlowResponse)
async def activate_source_flow(
    unit_key: str,
    flow_key: str,
    request: Request,
    principal: Annotated[AuthorizedPrincipal, Depends(manage_unit)],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=16, max_length=200)],
    expected_revision: Annotated[int, Header(alias="If-Match", ge=1)],
) -> SourceFlowResponse:
    return await _transition(
        unit_key,
        flow_key,
        DataStatus.ACTIVE,
        request,
        principal,
        idempotency_key,
        expected_revision,
    )


@router.put("/{flow_key}/schedule", response_model=SourceFlowResponse)
async def put_source_flow_schedule(
    unit_key: str,
    flow_key: str,
    payload: SourceFlowScheduleRequest,
    request: Request,
    principal: Annotated[AuthorizedPrincipal, Depends(manage_unit)],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=16, max_length=200)],
    expected_revision: Annotated[int, Header(alias="If-Match", ge=1)],
) -> SourceFlowResponse:
    schedule = IngestionSchedule(
        uuid7(), UUID(int=0), payload.interval_minutes, payload.next_run_at, payload.enabled
    )
    try:
        flow = await _service(request).put_schedule(
            unit_key,
            flow_key,
            schedule,
            expected_revision=expected_revision,
            command=_command(request, principal, idempotency_key, payload),
        )
    except (SourceFlowConflictError, SourceFlowReferenceError, SourceFlowStateError) as error:
        raise _translate(error) from error
    return _flow_response(flow)


__all__ = ["router"]
