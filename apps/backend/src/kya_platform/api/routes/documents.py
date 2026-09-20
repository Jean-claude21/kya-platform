"""Authorized Business API for the native KYA document runtime.

References into KYA Core are resolved live, only after checking the binding's
required permission, and only the declared snapshot fields are ever copied
into a governed reference. Workflow transitions are always evaluated and
committed server-side; no client ever changes state directly.
"""

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID, uuid7

from fastapi import APIRouter, Depends, Header, Request, status
from pydantic import BaseModel, Field

from kya_platform.api.security import AuthorizedPrincipal, active_principal
from kya_platform.application.core import CoreService
from kya_platform.application.documents import (
    DocumentConflictError,
    DocumentNotFoundError,
    DocumentService,
)
from kya_platform.application.documents.runtime import (
    DocumentValidationError,
    ReferenceResolutionRequest,
    ReferenceResolver,
    ResolvedReference,
    TransitionAuthorizationRequest,
    TransitionAuthorizer,
    TransitionDeniedError,
    plan_transition,
    resolve_references,
)
from kya_platform.authorization import AuthorizationPort, CheckRequest, active_unit_context
from kya_platform.contracts.document_type import DocumentTypeDefinition
from kya_platform.domain.documents import (
    DocumentRecord,
    DocumentRevision,
    DocumentValue,
    canonical_digest,
)
from kya_platform.observability import ApiError

router = APIRouter(prefix="/documents", tags=["documents"])


class CreateRecordRequest(BaseModel):
    definition_id: str = Field(alias="definitionId")
    definition_version: str = Field(alias="definitionVersion")
    owner_scope: str = Field(alias="ownerScope")
    payload: dict[str, DocumentValue]

    model_config = {"populate_by_name": True}


class RecordResponse(BaseModel):
    id: UUID
    definition_id: UUID
    owner_scope: str
    state: str
    current_revision: int
    payload: dict[str, DocumentValue]
    created_at: datetime
    updated_at: datetime


class TransitionRequest(BaseModel):
    transition_key: str = Field(alias="transitionKey")
    payload: dict[str, DocumentValue]

    model_config = {"populate_by_name": True}


class EvidenceResponse(BaseModel):
    id: UUID
    revision: int
    kind: str
    actor_id: UUID | None
    occurred_at: datetime


class HistoryResponse(BaseModel):
    items: list[EvidenceResponse]


def _dependencies(
    request: Request,
) -> tuple[DocumentService, CoreService, AuthorizationPort]:
    documents: DocumentService | None = getattr(request.app.state, "document_service", None)
    core: CoreService | None = getattr(request.app.state, "core_service", None)
    authorization: AuthorizationPort | None = getattr(request.app.state, "authorization", None)
    if documents is None or core is None or authorization is None:
        raise ApiError(
            503,
            "document_runtime_unavailable",
            "Moteur documentaire indisponible",
            "Le moteur natif de documents n'est pas configuré.",
        )
    return documents, core, authorization


class CoreReferenceResolver(ReferenceResolver):
    """Resolve governed references against KYA Core after a permission check."""

    def __init__(self, *, core: CoreService, authorization: AuthorizationPort) -> None:
        self._core = core
        self._authorization = authorization

    async def resolve(self, request: ReferenceResolutionRequest) -> ResolvedReference | None:
        context, contextual_tuples = active_unit_context(
            user_id=str(request.actor_id),
            unit_id=request.owner_scope.split(":", 1)[-1],
            current_time=datetime.now(UTC),
        )
        decision = await self._authorization.check(
            CheckRequest(
                user=f"user:{request.actor_id}",
                relation="can_view",
                object=f"org_unit:{request.owner_scope.split(':', 1)[-1]}",
                context=context,
                contextual_tuples=contextual_tuples,
            )
        )
        if not decision.allowed:
            return None
        unit_key = request.owner_scope.split(":", 1)[-1]
        snapshot = await self._snapshot(
            request.binding.resource_type, unit_key, request.reference_id
        )
        if snapshot is None:
            return None
        return ResolvedReference(request.reference_id, snapshot)

    async def _snapshot(
        self, resource_type: str, unit_key: str, reference_id: str
    ) -> dict[str, DocumentValue] | None:
        try:
            identifier = UUID(reference_id)
        except ValueError:
            return None
        if resource_type == "client":
            client = await self._core.get_client(unit_key, identifier)
            if client is None:
                return None
            return {
                "name": client.party.display_name,
                "account_number": client.account.key,
            }
        if resource_type == "person":
            employee = await self._core.get_employee(unit_key, identifier)
            if employee is None:
                return None
            return {
                "display_name": f"{employee.profile.given_name} {employee.profile.family_name}",
                "employee_number": employee.relationship.personnel_number or "",
                "organizational_unit": unit_key,
            }
        if resource_type == "project":
            project = await self._core.get_project(unit_key, identifier)
            if project is None:
                return None
            return {"name": project.name, "key": project.key}
        return None


class CoreTransitionAuthorizer(TransitionAuthorizer):
    """Authorize a transition using the same OpenFGA relation as the rest of the platform."""

    def __init__(self, authorization: AuthorizationPort) -> None:
        self._authorization = authorization

    async def authorize(self, request: TransitionAuthorizationRequest) -> bool:
        permission_relation = {
            "view": "can_view",
            "use": "can_view",
            "create": "can_submit",
            "edit": "can_submit",
            "administer": "can_manage",
            "publish": "can_approve",
            "share": "can_manage",
        }[request.permission.value]
        context, contextual_tuples = active_unit_context(
            user_id=str(request.actor_id),
            unit_id=request.owner_scope.split(":", 1)[-1],
            current_time=datetime.now(UTC),
        )
        decision = await self._authorization.check(
            CheckRequest(
                user=f"user:{request.actor_id}",
                relation=permission_relation,
                object=f"org_unit:{request.owner_scope.split(':', 1)[-1]}",
                context=context,
                contextual_tuples=contextual_tuples,
            )
        )
        return decision.allowed


def _record_response(record: DocumentRecord, revision: DocumentRevision) -> RecordResponse:
    return RecordResponse(
        id=record.id,
        definition_id=record.definition_id,
        owner_scope=record.owner_scope,
        state=record.state,
        current_revision=record.current_revision,
        payload=dict(revision.payload),
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


@router.post("/records", response_model=RecordResponse, status_code=status.HTTP_201_CREATED)
async def create_record(
    payload: CreateRecordRequest,
    request: Request,
    principal: Annotated[AuthorizedPrincipal, Depends(active_principal)],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=16, max_length=200)],
) -> RecordResponse:
    del idempotency_key
    documents, core, authorization = _dependencies(request)
    definition = await documents.get_definition(payload.definition_id, payload.definition_version)
    if definition is None:
        raise ApiError(
            404,
            "document_definition_not_found",
            "Type de document introuvable",
            "Ce type de document n'est pas publié dans cette version.",
        )
    schema = DocumentTypeDefinition.model_validate(definition.definition)
    try:
        resolved = await resolve_references(
            schema,
            payload.payload,
            resolver=CoreReferenceResolver(core=core, authorization=authorization),
            actor_id=principal.principal_id,
            owner_scope=payload.owner_scope,
        )
    except DocumentValidationError as error:
        raise ApiError(422, "document_payload_invalid", "Données invalides", str(error)) from error

    now = datetime.now(UTC)
    record_id = uuid7()
    record = DocumentRecord(
        id=record_id,
        definition_id=definition.id,
        owner_scope=payload.owner_scope,
        state=schema.workflow.initial_state,
        current_revision=1,
        created_by=principal.principal_id,
        created_at=now,
        updated_at=now,
    )
    revision = DocumentRevision(
        record_id=record_id,
        revision=1,
        payload=resolved,
        digest=canonical_digest(resolved),
        authored_by=principal.principal_id,
        created_at=now,
    )
    try:
        created = await documents.create(
            record=record,
            revision=revision,
            definition_public_id=payload.definition_id,
            definition_version=payload.definition_version,
        )
    except (DocumentNotFoundError, DocumentConflictError) as error:
        raise _translate_write_error(error) from error
    return _record_response(created, revision)


@router.get("/records/{record_id}", response_model=RecordResponse)
async def get_record(
    record_id: UUID,
    owner_scope: str,
    request: Request,
    principal: Annotated[AuthorizedPrincipal, Depends(active_principal)],
) -> RecordResponse:
    del principal
    documents, _core, _authorization = _dependencies(request)
    current = await documents.get(record_id, owner_scope=owner_scope)
    if current is None:
        raise ApiError(
            404,
            "document_record_not_found",
            "Enregistrement introuvable",
            "Cet enregistrement n'existe pas dans ce périmètre.",
        )
    record, revision = current
    return _record_response(record, revision)


@router.get("/records/{record_id}/history", response_model=HistoryResponse)
async def get_history(
    record_id: UUID,
    owner_scope: str,
    request: Request,
    principal: Annotated[AuthorizedPrincipal, Depends(active_principal)],
) -> HistoryResponse:
    del principal
    documents, _core, _authorization = _dependencies(request)
    events = await documents.history(record_id, owner_scope=owner_scope)
    return HistoryResponse(
        items=[
            EvidenceResponse(
                id=event.id,
                revision=event.revision,
                kind=event.kind.value,
                actor_id=event.actor_id,
                occurred_at=event.occurred_at,
            )
            for event in events
        ]
    )


@router.post("/records/{record_id}/transitions", response_model=RecordResponse)
async def execute_transition(
    record_id: UUID,
    owner_scope: str,
    payload: TransitionRequest,
    request: Request,
    principal: Annotated[AuthorizedPrincipal, Depends(active_principal)],
) -> RecordResponse:
    documents, _core, authorization = _dependencies(request)
    current = await documents.get(record_id, owner_scope=owner_scope)
    if current is None:
        raise ApiError(
            404,
            "document_record_not_found",
            "Enregistrement introuvable",
            "Cet enregistrement n'existe pas dans ce périmètre.",
        )
    record, revision = current
    definition = await documents.get_definition_by_internal_id(record.definition_id)
    if definition is None:
        raise ApiError(
            404,
            "document_definition_not_found",
            "Type de document introuvable",
            "La définition de ce document n'est plus disponible.",
        )
    schema = DocumentTypeDefinition.model_validate(definition.definition)
    correlation_id = UUID(request.state.correlation_id)
    try:
        merged_payload = {**revision.payload, **payload.payload}
        declared_fields = {field.key for field in schema.record_schema.fields}
        unknown_fields = set(payload.payload) - declared_fields
        if unknown_fields:
            raise DocumentValidationError(f"undeclared fields: {', '.join(sorted(unknown_fields))}")
        plan = await plan_transition(
            schema,
            record_id=record_id,
            current_state=record.state,
            current_revision=record.current_revision,
            payload=merged_payload,
            transition_key=payload.transition_key,
            actor_id=principal.principal_id,
            owner_scope=owner_scope,
            occurred_at=datetime.now(UTC),
            correlation_id=correlation_id,
            authorizer=CoreTransitionAuthorizer(authorization),
        )
    except DocumentValidationError as error:
        raise ApiError(422, "document_payload_invalid", "Données invalides", str(error)) from error
    except TransitionDeniedError as error:
        raise ApiError(403, "transition_denied", "Transition refusée", str(error)) from error
    updated = await documents.transition(
        plan, owner_scope=owner_scope, correlation_id=correlation_id
    )
    return _record_response(updated, plan.revision)


def _translate_write_error(error: Exception) -> ApiError:
    if isinstance(error, DocumentConflictError):
        return ApiError(409, "document_conflict", "Conflit de document", str(error))
    return ApiError(404, "document_reference_invalid", "Référence invalide", str(error))


__all__ = ["router"]
