"""Authorized Business API for canonical KYA master data."""

from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID, uuid7

from fastapi import APIRouter, Depends, Header, Query, Request, status
from pydantic import BaseModel, Field, model_validator

from kya_platform.api.security import AuthorizedPrincipal, require_permission
from kya_platform.application.core import (
    ClientRecord,
    CommandMetadata,
    CoreConflictError,
    CoreReferenceError,
    CoreService,
    EmployeeRecord,
)
from kya_platform.application.reliability import canonical_request_hash
from kya_platform.domain.core import (
    ClientAccount,
    ClientStatus,
    Party,
    PartyKind,
    PersonProfile,
    Project,
    ProjectStatus,
    WorkRelationship,
    WorkRelationshipKind,
)
from kya_platform.domain.organization import DateRange, OrganizationalUnit, OrganizationalUnitType
from kya_platform.observability import ApiError

router = APIRouter(prefix="/core", tags=["kya-core"])
_KEY_PATTERN = r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$"

view_unit = require_permission(
    relation="can_view", object_type="org_unit", object_parameter="unit_key"
)
manage_unit = require_permission(
    relation="can_manage", object_type="org_unit", object_parameter="unit_key"
)


class PeriodRequest(BaseModel):
    valid_from: datetime
    valid_until: datetime | None = None

    @model_validator(mode="after")
    def validate_period(self) -> PeriodRequest:
        DateRange(self.valid_from, self.valid_until)
        return self


class UnitCreateRequest(PeriodRequest):
    key: str = Field(pattern=_KEY_PATTERN, max_length=120)
    type_key: str = Field(pattern=_KEY_PATTERN, max_length=80)
    name: str = Field(min_length=1, max_length=240)


class UnitResponse(BaseModel):
    id: UUID
    key: str
    type_key: str
    name: str
    valid_from: datetime
    valid_until: datetime | None


class UnitListResponse(BaseModel):
    items: list[UnitResponse]


class UnitTypeResponse(BaseModel):
    key: str
    label: str
    allowed_parent_types: list[str]
    is_temporary: bool


class UnitTypeListResponse(BaseModel):
    items: list[UnitTypeResponse]


class ClientCreateRequest(PeriodRequest):
    key: str = Field(pattern=_KEY_PATTERN, max_length=120)
    party_kind: PartyKind
    display_name: str = Field(min_length=1, max_length=240)
    status: ClientStatus = ClientStatus.ACTIVE


class ClientResponse(BaseModel):
    id: UUID
    key: str
    party_id: UUID
    party_kind: PartyKind
    display_name: str
    owner_unit_id: UUID
    status: ClientStatus
    valid_from: datetime
    valid_until: datetime | None
    version: int


class ClientListResponse(BaseModel):
    items: list[ClientResponse]


class ProjectCreateRequest(PeriodRequest):
    key: str = Field(pattern=_KEY_PATTERN, max_length=120)
    name: str = Field(min_length=1, max_length=240)
    status: ProjectStatus = ProjectStatus.PLANNED
    client_id: UUID | None = None


class ProjectResponse(BaseModel):
    id: UUID
    key: str
    name: str
    owner_unit_id: UUID
    client_id: UUID | None
    status: ProjectStatus
    valid_from: datetime
    valid_until: datetime | None
    version: int


class ProjectListResponse(BaseModel):
    items: list[ProjectResponse]


class EmployeeCreateRequest(PeriodRequest):
    given_name: str = Field(min_length=1, max_length=120)
    family_name: str = Field(min_length=1, max_length=120)
    preferred_name: str | None = Field(default=None, max_length=120)
    kind: WorkRelationshipKind = WorkRelationshipKind.EMPLOYEE
    personnel_number: str | None = Field(default=None, max_length=80)


class EmployeeResponse(BaseModel):
    id: UUID
    party_id: UUID
    given_name: str
    family_name: str
    preferred_name: str | None
    employer_unit_id: UUID
    kind: WorkRelationshipKind
    personnel_number: str | None
    valid_from: datetime
    valid_until: datetime | None


class EmployeeListResponse(BaseModel):
    items: list[EmployeeResponse]


def _service(request: Request) -> CoreService:
    service: CoreService | None = getattr(request.app.state, "core_service", None)
    if service is None:
        raise ApiError(
            503,
            "core_service_unavailable",
            "KYA Core indisponible",
            "Le service de données maîtresses n'est pas configuré.",
        )
    return service


def _unit_response(unit: OrganizationalUnit) -> UnitResponse:
    return UnitResponse(
        id=unit.id,
        key=unit.key,
        type_key=unit.type_key,
        name=unit.name,
        valid_from=unit.validity.valid_from,
        valid_until=unit.validity.valid_until,
    )


def _unit_type_response(unit_type: OrganizationalUnitType) -> UnitTypeResponse:
    return UnitTypeResponse(
        key=unit_type.key,
        label=unit_type.label,
        allowed_parent_types=sorted(unit_type.allowed_parent_types),
        is_temporary=unit_type.is_temporary,
    )


def _client_response(record: ClientRecord) -> ClientResponse:
    return ClientResponse(
        id=record.account.id,
        key=record.account.key,
        party_id=record.party.id,
        party_kind=record.party.kind,
        display_name=record.party.display_name,
        owner_unit_id=record.account.owner_unit_id,
        status=record.account.status,
        valid_from=record.account.validity.valid_from,
        valid_until=record.account.validity.valid_until,
        version=record.account.version,
    )


def _project_response(project: Project) -> ProjectResponse:
    return ProjectResponse(
        id=project.id,
        key=project.key,
        name=project.name,
        owner_unit_id=project.owner_unit_id,
        client_id=project.client_id,
        status=project.status,
        valid_from=project.validity.valid_from,
        valid_until=project.validity.valid_until,
        version=project.version,
    )


def _employee_response(record: EmployeeRecord) -> EmployeeResponse:
    return EmployeeResponse(
        id=record.relationship.id,
        party_id=record.party.id,
        given_name=record.profile.given_name,
        family_name=record.profile.family_name,
        preferred_name=record.profile.preferred_name,
        employer_unit_id=record.relationship.employer_unit_id,
        kind=record.relationship.kind,
        personnel_number=record.relationship.personnel_number,
        valid_from=record.relationship.validity.valid_from,
        valid_until=record.relationship.validity.valid_until,
    )


async def _required_unit(service: CoreService, unit_key: str) -> OrganizationalUnit:
    unit = await service.get_unit(unit_key)
    if unit is None:
        raise ApiError(404, "core_unit_not_found", "Unité introuvable", "Cette unité n'existe pas.")
    return unit


def _translate_write_error(error: Exception) -> ApiError:
    if isinstance(error, CoreConflictError):
        return ApiError(409, "core_conflict", "Conflit de référentiel", str(error))
    return ApiError(422, "core_reference_invalid", "Référence invalide", str(error))


def _command(
    request: Request,
    principal: AuthorizedPrincipal,
    idempotency_key: str,
    payload: BaseModel,
) -> CommandMetadata:
    return CommandMetadata(
        actor_id=principal.principal_id,
        correlation_id=UUID(request.state.correlation_id),
        idempotency_key=idempotency_key,
        request_hash=canonical_request_hash(payload.model_dump(mode="json")),
        expires_at=datetime.now(UTC) + timedelta(hours=24),
    )


@router.get("/organization/{unit_key}", response_model=UnitResponse)
async def get_unit(
    unit_key: str,
    request: Request,
    _principal: Annotated[AuthorizedPrincipal, Depends(view_unit)],
) -> UnitResponse:
    return _unit_response(await _required_unit(_service(request), unit_key))


@router.get("/organization/{unit_key}/unit-types", response_model=UnitTypeListResponse)
async def list_unit_types(
    unit_key: str,
    request: Request,
    _principal: Annotated[AuthorizedPrincipal, Depends(view_unit)],
) -> UnitTypeListResponse:
    records = await _service(request).list_unit_types()
    return UnitTypeListResponse(items=[_unit_type_response(item) for item in records])


@router.get("/organization/{unit_key}/children", response_model=UnitListResponse)
async def list_child_units(
    unit_key: str,
    request: Request,
    _principal: Annotated[AuthorizedPrincipal, Depends(view_unit)],
    at: datetime | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> UnitListResponse:
    records = await _service(request).list_child_units(
        unit_key, at=at or datetime.now(UTC), limit=limit
    )
    return UnitListResponse(items=[_unit_response(item) for item in records])


@router.post(
    "/organization/{unit_key}/children",
    response_model=UnitResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_child_unit(
    unit_key: str,
    payload: UnitCreateRequest,
    request: Request,
    principal: Annotated[AuthorizedPrincipal, Depends(manage_unit)],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=16, max_length=200)],
) -> UnitResponse:
    unit = OrganizationalUnit(
        uuid7(),
        payload.key,
        payload.type_key,
        payload.name,
        DateRange(payload.valid_from, payload.valid_until),
    )
    try:
        created = await _service(request).create_child_unit(
            unit_key,
            unit,
            command=_command(request, principal, idempotency_key, payload),
        )
    except (CoreConflictError, CoreReferenceError) as error:
        raise _translate_write_error(error) from error
    return _unit_response(created)


@router.get("/organization/{unit_key}/clients", response_model=ClientListResponse)
async def list_clients(
    unit_key: str,
    request: Request,
    _principal: Annotated[AuthorizedPrincipal, Depends(view_unit)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> ClientListResponse:
    records = await _service(request).list_clients(unit_key, limit=limit)
    return ClientListResponse(items=[_client_response(item) for item in records])


@router.get("/organization/{unit_key}/clients/{client_id}", response_model=ClientResponse)
async def get_client(
    unit_key: str,
    client_id: UUID,
    request: Request,
    _principal: Annotated[AuthorizedPrincipal, Depends(view_unit)],
) -> ClientResponse:
    record = await _service(request).get_client(unit_key, client_id)
    if record is None:
        raise ApiError(
            404,
            "core_client_not_found",
            "Client introuvable",
            "Ce client n'existe pas dans ce périmètre.",
        )
    return _client_response(record)


@router.post(
    "/organization/{unit_key}/clients",
    response_model=ClientResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_client(
    unit_key: str,
    payload: ClientCreateRequest,
    request: Request,
    principal: Annotated[AuthorizedPrincipal, Depends(manage_unit)],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=16, max_length=200)],
) -> ClientResponse:
    owner = await _required_unit(_service(request), unit_key)
    party = Party(uuid7(), payload.party_kind, payload.display_name)
    record = ClientRecord(
        party=party,
        account=ClientAccount(
            uuid7(),
            payload.key,
            party.id,
            owner.id,
            payload.status,
            DateRange(payload.valid_from, payload.valid_until),
        ),
    )
    try:
        created = await _service(request).create_client(
            unit_key,
            record,
            command=_command(request, principal, idempotency_key, payload),
        )
    except (CoreConflictError, CoreReferenceError) as error:
        raise _translate_write_error(error) from error
    return _client_response(created)


@router.get("/organization/{unit_key}/projects", response_model=ProjectListResponse)
async def list_projects(
    unit_key: str,
    request: Request,
    _principal: Annotated[AuthorizedPrincipal, Depends(view_unit)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> ProjectListResponse:
    records = await _service(request).list_projects(unit_key, limit=limit)
    return ProjectListResponse(items=[_project_response(item) for item in records])


@router.get("/organization/{unit_key}/projects/{project_id}", response_model=ProjectResponse)
async def get_project(
    unit_key: str,
    project_id: UUID,
    request: Request,
    _principal: Annotated[AuthorizedPrincipal, Depends(view_unit)],
) -> ProjectResponse:
    project = await _service(request).get_project(unit_key, project_id)
    if project is None:
        raise ApiError(
            404,
            "core_project_not_found",
            "Projet introuvable",
            "Ce projet n'existe pas dans ce périmètre.",
        )
    return _project_response(project)


@router.post(
    "/organization/{unit_key}/projects",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_project(
    unit_key: str,
    payload: ProjectCreateRequest,
    request: Request,
    principal: Annotated[AuthorizedPrincipal, Depends(manage_unit)],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=16, max_length=200)],
) -> ProjectResponse:
    owner = await _required_unit(_service(request), unit_key)
    project = Project(
        uuid7(),
        payload.key,
        payload.name,
        owner.id,
        payload.status,
        DateRange(payload.valid_from, payload.valid_until),
        client_id=payload.client_id,
    )
    try:
        created = await _service(request).create_project(
            unit_key,
            project,
            command=_command(request, principal, idempotency_key, payload),
        )
    except (CoreConflictError, CoreReferenceError) as error:
        raise _translate_write_error(error) from error
    return _project_response(created)


@router.get("/organization/{unit_key}/employees", response_model=EmployeeListResponse)
async def list_employees(
    unit_key: str,
    request: Request,
    _principal: Annotated[AuthorizedPrincipal, Depends(view_unit)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> EmployeeListResponse:
    records = await _service(request).list_employees(unit_key, limit=limit)
    return EmployeeListResponse(items=[_employee_response(item) for item in records])


@router.get(
    "/organization/{unit_key}/employees/{work_relationship_id}", response_model=EmployeeResponse
)
async def get_employee(
    unit_key: str,
    work_relationship_id: UUID,
    request: Request,
    _principal: Annotated[AuthorizedPrincipal, Depends(view_unit)],
) -> EmployeeResponse:
    record = await _service(request).get_employee(unit_key, work_relationship_id)
    if record is None:
        raise ApiError(
            404,
            "core_employee_not_found",
            "Employé introuvable",
            "Cet employé n'existe pas dans ce périmètre.",
        )
    return _employee_response(record)


@router.post(
    "/organization/{unit_key}/employees",
    response_model=EmployeeResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_employee(
    unit_key: str,
    payload: EmployeeCreateRequest,
    request: Request,
    principal: Annotated[AuthorizedPrincipal, Depends(manage_unit)],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=16, max_length=200)],
) -> EmployeeResponse:
    owner = await _required_unit(_service(request), unit_key)
    party = Party(uuid7(), PartyKind.PERSON, f"{payload.given_name} {payload.family_name}")
    record = EmployeeRecord(
        party=party,
        profile=PersonProfile(
            party_id=party.id,
            given_name=payload.given_name,
            family_name=payload.family_name,
            preferred_name=payload.preferred_name,
        ),
        relationship=WorkRelationship(
            id=uuid7(),
            person_id=party.id,
            employer_unit_id=owner.id,
            kind=payload.kind,
            validity=DateRange(payload.valid_from, payload.valid_until),
            personnel_number=payload.personnel_number,
        ),
    )
    try:
        created = await _service(request).create_employee(
            unit_key,
            record,
            command=_command(request, principal, idempotency_key, payload),
        )
    except (CoreConflictError, CoreReferenceError) as error:
        raise _translate_write_error(error) from error
    return _employee_response(created)


__all__ = ["router"]
