"""Authorized Business API for governed data acquisition and evidence."""

from datetime import UTC, datetime, timedelta
from typing import Annotated, Any, cast
from uuid import UUID, uuid7

from fastapi import APIRouter, Depends, Header, Query, Request, status
from pydantic import BaseModel, Field

from kya_platform.api.security import AuthorizedPrincipal, require_permission
from kya_platform.application.core import CoreService
from kya_platform.application.data import (
    CommandMetadata,
    DataConflictError,
    DataReferenceError,
    DataService,
    DataStateError,
    RunCompletion,
)
from kya_platform.application.reliability import JsonValue, canonical_request_hash
from kya_platform.domain.data import (
    DataAsset,
    DataAssetLayer,
    DataClassification,
    DataContract,
    DataPipeline,
    DataSnapshot,
    DataSource,
    DataSourceKind,
    DataStatus,
    IngestionRun,
    QualityResult,
    QualityRule,
    QualityStatus,
    RunStatus,
    StorageObject,
)
from kya_platform.observability import ApiError

router = APIRouter(prefix="/data/organization/{unit_key}", tags=["data-foundation"])
_KEY_PATTERN = r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$"
view_unit = require_permission(
    relation="can_view", object_type="org_unit", object_parameter="unit_key"
)
manage_unit = require_permission(
    relation="can_manage", object_type="org_unit", object_parameter="unit_key"
)


class SourceCreateRequest(BaseModel):
    key: str = Field(pattern=_KEY_PATTERN, max_length=120)
    name: str = Field(min_length=1, max_length=240)
    kind: DataSourceKind
    system_artifact_id: UUID | None = None
    secret_reference: str | None = Field(default=None, max_length=500)
    status: DataStatus = DataStatus.DRAFT
    configuration: dict[str, Any] = Field(default_factory=dict)


class SourceResponse(BaseModel):
    id: UUID
    key: str
    name: str
    kind: DataSourceKind
    owner_unit_id: UUID
    system_artifact_id: UUID | None
    has_credentials: bool
    status: DataStatus
    configuration: dict[str, Any]


class SourceListResponse(BaseModel):
    items: list[SourceResponse]


class AssetCreateRequest(BaseModel):
    key: str = Field(pattern=_KEY_PATTERN, max_length=120)
    name: str = Field(min_length=1, max_length=240)
    layer: DataAssetLayer
    classification: DataClassification
    status: DataStatus = DataStatus.DRAFT


class AssetResponse(BaseModel):
    id: UUID
    key: str
    name: str
    owner_unit_id: UUID
    layer: DataAssetLayer
    classification: DataClassification
    status: DataStatus


class AssetListResponse(BaseModel):
    items: list[AssetResponse]


class QualityRuleRequest(BaseModel):
    key: str = Field(pattern=_KEY_PATTERN, max_length=120)
    kind: str = Field(min_length=1, max_length=120)
    expression: str = Field(min_length=1, max_length=4000)
    severity: str = Field(default="error", pattern=r"^(warning|error)$")


class ContractCreateRequest(BaseModel):
    version: str = Field(pattern=r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
    schema_document: dict[str, Any]
    quality_rules: list[QualityRuleRequest] = Field(default_factory=list, max_length=100)
    freshness_minutes: int | None = Field(default=None, ge=1)
    retention_days: int | None = Field(default=None, ge=1)


class ContractResponse(BaseModel):
    id: UUID
    asset_id: UUID
    version: str
    digest: str
    freshness_minutes: int | None
    retention_days: int | None


class PipelineCreateRequest(BaseModel):
    key: str = Field(pattern=_KEY_PATTERN, max_length=120)
    name: str = Field(min_length=1, max_length=240)
    source_id: UUID
    connector_version_id: UUID
    output_asset_id: UUID
    status: DataStatus = DataStatus.DRAFT


class PipelineResponse(BaseModel):
    id: UUID
    key: str
    name: str
    owner_unit_id: UUID
    source_id: UUID
    connector_version_id: UUID
    output_asset_id: UUID
    status: DataStatus


class RunResponse(BaseModel):
    id: UUID
    pipeline_id: UUID
    triggered_by: UUID
    status: RunStatus
    started_at: datetime
    completed_at: datetime | None
    error_code: str | None


class QualityResultRequest(BaseModel):
    rule_key: str = Field(pattern=_KEY_PATTERN, max_length=120)
    status: QualityStatus
    observed: dict[str, Any] | None = None


class StorageObjectRequest(BaseModel):
    provider: str = Field(min_length=1, max_length=80)
    container: str = Field(min_length=1, max_length=240)
    object_key: str = Field(min_length=1, max_length=800)
    version_id: str | None = Field(default=None, max_length=240)


class CompleteRunRequest(BaseModel):
    asset_id: UUID
    contract_id: UUID
    storage: StorageObjectRequest
    content_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    media_type: str = Field(min_length=1, max_length=160)
    observed_at: datetime
    row_count: int | None = Field(default=None, ge=0)
    byte_size: int | None = Field(default=None, ge=0)
    quality_results: list[QualityResultRequest] = Field(default_factory=list, max_length=100)
    input_snapshot_ids: list[UUID] = Field(default_factory=list, max_length=100)


class FailRunRequest(BaseModel):
    error_code: str = Field(pattern=_KEY_PATTERN, max_length=120)


class SnapshotResponse(BaseModel):
    id: UUID
    asset_id: UUID
    run_id: UUID
    contract_id: UUID
    storage: StorageObjectRequest
    content_digest: str
    media_type: str
    observed_at: datetime
    row_count: int | None
    byte_size: int | None


class SnapshotListResponse(BaseModel):
    items: list[SnapshotResponse]


def _service(request: Request) -> DataService:
    service: DataService | None = getattr(request.app.state, "data_service", None)
    if service is None:
        raise ApiError(
            503,
            "data_service_unavailable",
            "Fondation Data indisponible",
            "Le service de données gouvernées n'est pas configuré.",
        )
    return service


async def _unit_id(request: Request, unit_key: str) -> UUID:
    core: CoreService | None = getattr(request.app.state, "core_service", None)
    if core is None:
        raise ApiError(503, "core_service_unavailable", "KYA Core indisponible", "")
    unit = await core.get_unit(unit_key)
    if unit is None:
        raise ApiError(404, "core_unit_not_found", "Unité introuvable", "Cette unité n'existe pas.")
    return unit.id


def _command(
    request: Request,
    principal: AuthorizedPrincipal,
    idempotency_key: str,
    payload: BaseModel | dict[str, object],
) -> CommandMetadata:
    body = payload.model_dump(mode="json") if isinstance(payload, BaseModel) else payload
    return CommandMetadata(
        actor_id=principal.principal_id,
        correlation_id=UUID(request.state.correlation_id),
        idempotency_key=idempotency_key,
        request_hash=canonical_request_hash(cast(JsonValue, body)),
        expires_at=datetime.now(UTC) + timedelta(hours=24),
    )


def _translate(error: Exception) -> ApiError:
    if isinstance(error, DataConflictError):
        return ApiError(409, "data_conflict", "Conflit de données", str(error))
    if isinstance(error, DataStateError):
        return ApiError(409, "data_invalid_state", "État incompatible", str(error))
    return ApiError(422, "data_reference_invalid", "Référence invalide", str(error))


def _source_response(item: DataSource) -> SourceResponse:
    return SourceResponse(
        id=item.id,
        key=item.key,
        name=item.name,
        kind=item.kind,
        owner_unit_id=item.owner_unit_id,
        system_artifact_id=item.system_artifact_id,
        has_credentials=item.secret_reference is not None,
        status=item.status,
        configuration=item.configuration,
    )


def _asset_response(item: DataAsset) -> AssetResponse:
    return AssetResponse(**{name: getattr(item, name) for name in AssetResponse.model_fields})


def _pipeline_response(item: DataPipeline) -> PipelineResponse:
    return PipelineResponse(**{name: getattr(item, name) for name in PipelineResponse.model_fields})


def _run_response(item: IngestionRun) -> RunResponse:
    return RunResponse(**{name: getattr(item, name) for name in RunResponse.model_fields})


def _snapshot_response(item: DataSnapshot) -> SnapshotResponse:
    return SnapshotResponse(
        id=item.id,
        asset_id=item.asset_id,
        run_id=item.run_id,
        contract_id=item.contract_id,
        storage=StorageObjectRequest(
            provider=item.storage.provider,
            container=item.storage.container,
            object_key=item.storage.object_key,
            version_id=item.storage.version_id,
        ),
        content_digest=item.content_digest,
        media_type=item.media_type,
        observed_at=item.observed_at,
        row_count=item.row_count,
        byte_size=item.byte_size,
    )


@router.get("/sources", response_model=SourceListResponse)
async def list_sources(
    unit_key: str,
    request: Request,
    _principal: Annotated[AuthorizedPrincipal, Depends(view_unit)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> SourceListResponse:
    return SourceListResponse(
        items=[
            _source_response(item)
            for item in await _service(request).list_sources(unit_key, limit=limit)
        ]
    )


@router.post("/sources", response_model=SourceResponse, status_code=status.HTTP_201_CREATED)
async def create_source(
    unit_key: str,
    payload: SourceCreateRequest,
    request: Request,
    principal: Annotated[AuthorizedPrincipal, Depends(manage_unit)],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=16, max_length=200)],
) -> SourceResponse:
    source = DataSource(
        uuid7(),
        payload.key,
        payload.name,
        payload.kind,
        await _unit_id(request, unit_key),
        payload.system_artifact_id,
        payload.secret_reference,
        payload.status,
        payload.configuration,
    )
    try:
        result = await _service(request).create_source(
            unit_key, source, command=_command(request, principal, idempotency_key, payload)
        )
    except (DataConflictError, DataReferenceError, DataStateError) as error:
        raise _translate(error) from error
    return _source_response(result)


@router.get("/assets", response_model=AssetListResponse)
async def list_assets(
    unit_key: str,
    request: Request,
    _principal: Annotated[AuthorizedPrincipal, Depends(view_unit)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> AssetListResponse:
    return AssetListResponse(
        items=[
            _asset_response(item)
            for item in await _service(request).list_assets(unit_key, limit=limit)
        ]
    )


@router.post("/assets", response_model=AssetResponse, status_code=status.HTTP_201_CREATED)
async def create_asset(
    unit_key: str,
    payload: AssetCreateRequest,
    request: Request,
    principal: Annotated[AuthorizedPrincipal, Depends(manage_unit)],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=16, max_length=200)],
) -> AssetResponse:
    asset = DataAsset(
        uuid7(),
        payload.key,
        payload.name,
        await _unit_id(request, unit_key),
        payload.layer,
        payload.classification,
        payload.status,
    )
    try:
        result = await _service(request).create_asset(
            unit_key, asset, command=_command(request, principal, idempotency_key, payload)
        )
    except (DataConflictError, DataReferenceError, DataStateError) as error:
        raise _translate(error) from error
    return _asset_response(result)


@router.post(
    "/assets/{asset_id}/contracts",
    response_model=ContractResponse,
    status_code=status.HTTP_201_CREATED,
)
async def publish_contract(
    unit_key: str,
    asset_id: UUID,
    payload: ContractCreateRequest,
    request: Request,
    principal: Annotated[AuthorizedPrincipal, Depends(manage_unit)],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=16, max_length=200)],
) -> ContractResponse:
    content = payload.model_dump(mode="json")
    contract = DataContract(
        uuid7(),
        asset_id,
        payload.version,
        payload.schema_document,
        canonical_request_hash(content),
        tuple(QualityRule(**item.model_dump()) for item in payload.quality_rules),
        payload.freshness_minutes,
        payload.retention_days,
    )
    try:
        result = await _service(request).publish_contract(
            unit_key, contract, command=_command(request, principal, idempotency_key, payload)
        )
    except (DataConflictError, DataReferenceError, DataStateError) as error:
        raise _translate(error) from error
    return ContractResponse(
        id=result.id,
        asset_id=result.asset_id,
        version=result.version,
        digest=result.digest,
        freshness_minutes=result.freshness_minutes,
        retention_days=result.retention_days,
    )


@router.post("/pipelines", response_model=PipelineResponse, status_code=status.HTTP_201_CREATED)
async def create_pipeline(
    unit_key: str,
    payload: PipelineCreateRequest,
    request: Request,
    principal: Annotated[AuthorizedPrincipal, Depends(manage_unit)],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=16, max_length=200)],
) -> PipelineResponse:
    pipeline = DataPipeline(
        uuid7(),
        payload.key,
        payload.name,
        await _unit_id(request, unit_key),
        payload.source_id,
        payload.connector_version_id,
        payload.output_asset_id,
        payload.status,
    )
    try:
        result = await _service(request).create_pipeline(
            unit_key, pipeline, command=_command(request, principal, idempotency_key, payload)
        )
    except (DataConflictError, DataReferenceError, DataStateError) as error:
        raise _translate(error) from error
    return _pipeline_response(result)


@router.post(
    "/pipelines/{pipeline_id}/runs", response_model=RunResponse, status_code=status.HTTP_201_CREATED
)
async def start_run(
    unit_key: str,
    pipeline_id: UUID,
    request: Request,
    principal: Annotated[AuthorizedPrincipal, Depends(manage_unit)],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=16, max_length=200)],
) -> RunResponse:
    run = IngestionRun(
        uuid7(), pipeline_id, principal.principal_id, RunStatus.STARTED, datetime.now(UTC)
    )
    try:
        result = await _service(request).start_run(
            unit_key,
            run,
            command=_command(
                request, principal, idempotency_key, {"pipeline_id": str(pipeline_id)}
            ),
        )
    except (DataConflictError, DataReferenceError, DataStateError) as error:
        raise _translate(error) from error
    return _run_response(result)


@router.post("/runs/{run_id}/complete", response_model=SnapshotResponse)
async def complete_run(
    unit_key: str,
    run_id: UUID,
    payload: CompleteRunRequest,
    request: Request,
    principal: Annotated[AuthorizedPrincipal, Depends(manage_unit)],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=16, max_length=200)],
) -> SnapshotResponse:
    started = await _service(request).get_run(unit_key, run_id)
    if started is None:
        raise ApiError(404, "data_run_not_found", "Exécution introuvable", "")
    try:
        run = started.complete(datetime.now(UTC))
    except ValueError as error:
        raise _translate(DataStateError(str(error))) from error
    snapshot = DataSnapshot(
        uuid7(),
        payload.asset_id,
        run_id,
        payload.contract_id,
        StorageObject(**payload.storage.model_dump()),
        payload.content_digest,
        payload.media_type,
        payload.observed_at,
        payload.row_count,
        payload.byte_size,
    )
    completion = RunCompletion(
        run,
        snapshot,
        tuple(QualityResult(**item.model_dump()) for item in payload.quality_results),
        tuple(payload.input_snapshot_ids),
    )
    try:
        result = await _service(request).complete_run(
            unit_key, completion, command=_command(request, principal, idempotency_key, payload)
        )
    except (DataConflictError, DataReferenceError, DataStateError) as error:
        raise _translate(error) from error
    return _snapshot_response(result.snapshot)


@router.post("/runs/{run_id}/fail", response_model=RunResponse)
async def fail_run(
    unit_key: str,
    run_id: UUID,
    payload: FailRunRequest,
    request: Request,
    principal: Annotated[AuthorizedPrincipal, Depends(manage_unit)],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=16, max_length=200)],
) -> RunResponse:
    started = await _service(request).get_run(unit_key, run_id)
    if started is None:
        raise ApiError(404, "data_run_not_found", "Exécution introuvable", "")
    try:
        run = started.fail(datetime.now(UTC), payload.error_code)
    except ValueError as error:
        raise _translate(DataStateError(str(error))) from error
    try:
        result = await _service(request).fail_run(
            unit_key, run, command=_command(request, principal, idempotency_key, payload)
        )
    except (DataConflictError, DataReferenceError, DataStateError) as error:
        raise _translate(error) from error
    return _run_response(result)


@router.get("/assets/{asset_key}/snapshots", response_model=SnapshotListResponse)
async def list_snapshots(
    unit_key: str,
    asset_key: str,
    request: Request,
    _principal: Annotated[AuthorizedPrincipal, Depends(view_unit)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> SnapshotListResponse:
    records = await _service(request).list_snapshots(unit_key, asset_key, limit=limit)
    return SnapshotListResponse(items=[_snapshot_response(item) for item in records])


__all__ = ["router"]
