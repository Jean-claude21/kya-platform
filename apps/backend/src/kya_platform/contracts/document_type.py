"""Portable definition of a governed KYA business document type."""

from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from kya_platform.contracts.artifact_manifest import CapabilityPermission
from kya_platform.contracts.record_schema import RecordSchema

_KEY_PATTERN = r"^[a-z][a-z0-9]*(?:[_-][a-z0-9]+)*$"
_EVENT_PATTERN = r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$"
_DOCUMENT_TYPE_ID_PATTERN = r"^kya:document-type:[a-z0-9][a-z0-9-]*$"
_ARTIFACT_ID_PATTERN = r"^kya:[a-z0-9-]+:[a-z0-9][a-z0-9-]*$"
_SEMVER_PATTERN = r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$"

NonEmptyText = Annotated[str, Field(min_length=1)]
ScalarValue = str | int | float | bool | None


class StrictDocumentContract(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class ReferenceConsistency(StrEnum):
    LIVE = "live"
    SNAPSHOT = "snapshot"
    LIVE_WITH_SNAPSHOT = "live-with-snapshot"


class ReferenceBinding(StrictDocumentContract):
    """Governed lookup into another KYA capability without copying its authority."""

    field: str = Field(pattern=_KEY_PATTERN)
    provider_artifact_id: str = Field(alias="providerArtifactId", pattern=_ARTIFACT_ID_PATTERN)
    resource_type: str = Field(alias="resourceType", pattern=_KEY_PATTERN)
    value_field: str = Field(alias="valueField", pattern=_KEY_PATTERN)
    display_fields: tuple[str, ...] = Field(alias="displayFields", min_length=1, max_length=20)
    search_fields: tuple[str, ...] = Field(default=(), alias="searchFields", max_length=20)
    snapshot_fields: tuple[str, ...] = Field(default=(), alias="snapshotFields", max_length=50)
    consistency: ReferenceConsistency = ReferenceConsistency.LIVE_WITH_SNAPSHOT
    required_permission: NonEmptyText = Field(alias="requiredPermission")

    @field_validator("display_fields", "search_fields", "snapshot_fields")
    @classmethod
    def validate_unique_fields(cls, fields: tuple[str, ...]) -> tuple[str, ...]:
        if len(fields) != len(set(fields)):
            raise ValueError("reference fields must be unique")
        return fields

    @model_validator(mode="after")
    def validate_snapshot_configuration(self) -> Self:
        if self.consistency is ReferenceConsistency.LIVE and self.snapshot_fields:
            raise ValueError("live references cannot declare snapshot fields")
        if self.consistency is not ReferenceConsistency.LIVE and not self.snapshot_fields:
            raise ValueError("snapshot references require snapshot fields")
        return self


class ConditionOperator(StrEnum):
    EQUALS = "equals"
    NOT_EQUALS = "not-equals"
    GREATER_THAN = "greater-than"
    GREATER_THAN_OR_EQUAL = "greater-than-or-equal"
    LESS_THAN = "less-than"
    LESS_THAN_OR_EQUAL = "less-than-or-equal"
    IN = "in"
    NOT_IN = "not-in"
    IS_SET = "is-set"


class ConditionClause(StrictDocumentContract):
    field: str = Field(pattern=_KEY_PATTERN)
    operator: ConditionOperator
    value: ScalarValue | tuple[ScalarValue, ...] = None

    @model_validator(mode="after")
    def validate_value(self) -> Self:
        if self.operator is ConditionOperator.IS_SET and self.value is not None:
            raise ValueError("is-set conditions cannot declare a value")
        if self.operator in {ConditionOperator.IN, ConditionOperator.NOT_IN}:
            if not isinstance(self.value, tuple) or not self.value:
                raise ValueError("membership conditions require a non-empty value list")
        if self.operator not in {
            ConditionOperator.IS_SET,
            ConditionOperator.IN,
            ConditionOperator.NOT_IN,
        } and isinstance(self.value, tuple):
            raise ValueError("comparison conditions require one scalar value")
        return self


class ActorSelectorKind(StrEnum):
    ACTOR = "actor"
    ROLE = "role"
    RECORD_FIELD = "record-field"
    PERMISSION = "permission"
    MANAGER_OF_FIELD = "manager-of-field"


class ActorSelector(StrictDocumentContract):
    kind: ActorSelectorKind
    value: NonEmptyText


class WorkflowStateCategory(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    COMPLETED = "completed"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class WorkflowState(StrictDocumentContract):
    key: str = Field(pattern=_KEY_PATTERN)
    name: str = Field(min_length=2, max_length=120)
    category: WorkflowStateCategory
    terminal: bool = False

    @model_validator(mode="after")
    def validate_terminal_category(self) -> Self:
        terminal_categories = {
            WorkflowStateCategory.COMPLETED,
            WorkflowStateCategory.REJECTED,
            WorkflowStateCategory.CANCELLED,
        }
        if self.terminal != (self.category in terminal_categories):
            raise ValueError("terminal workflow states require a terminal category")
        return self


class WorkflowTransition(StrictDocumentContract):
    key: str = Field(pattern=_KEY_PATTERN)
    name: str = Field(min_length=2, max_length=120)
    from_state: str = Field(alias="fromState", pattern=_KEY_PATTERN)
    to_state: str = Field(alias="toState", pattern=_KEY_PATTERN)
    permission: CapabilityPermission
    actors: tuple[ActorSelector, ...] = Field(min_length=1, max_length=20)
    conditions: tuple[ConditionClause, ...] = Field(default=(), max_length=50)


class WorkflowDefinition(StrictDocumentContract):
    initial_state: str = Field(alias="initialState", pattern=_KEY_PATTERN)
    states: tuple[WorkflowState, ...] = Field(min_length=2, max_length=100)
    transitions: tuple[WorkflowTransition, ...] = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def validate_graph(self) -> Self:
        state_keys = [state.key for state in self.states]
        transition_keys = [transition.key for transition in self.transitions]
        if len(state_keys) != len(set(state_keys)):
            raise ValueError("workflow state keys must be unique")
        if len(transition_keys) != len(set(transition_keys)):
            raise ValueError("workflow transition keys must be unique")
        if self.initial_state not in state_keys:
            raise ValueError("workflow initial state must exist")
        if next(state for state in self.states if state.key == self.initial_state).terminal:
            raise ValueError("workflow initial state cannot be terminal")
        for transition in self.transitions:
            if transition.from_state not in state_keys or transition.to_state not in state_keys:
                raise ValueError("workflow transitions must reference declared states")
            if transition.from_state == transition.to_state:
                raise ValueError("workflow transitions must change state")
            source = next(state for state in self.states if state.key == transition.from_state)
            if source.terminal:
                raise ValueError("terminal workflow states cannot have outgoing transitions")
        return self


class SignatureMode(StrEnum):
    INTERNAL_APPROVAL = "internal-approval"
    ELECTRONIC = "electronic"


class SignaturePolicy(StrictDocumentContract):
    key: str = Field(pattern=_KEY_PATTERN)
    transition_key: str = Field(alias="transitionKey", pattern=_KEY_PATTERN)
    mode: SignatureMode = SignatureMode.INTERNAL_APPROVAL
    signers: tuple[ActorSelector, ...] = Field(min_length=1, max_length=20)
    minimum_signatures: int = Field(alias="minimumSignatures", ge=1, le=100)
    bind_attachments: bool = Field(default=True, alias="bindAttachments")


class NotificationChannel(StrEnum):
    IN_APP = "in-app"
    EMAIL = "email"
    TEAMS = "teams"
    SMS = "sms"


class NotificationPolicy(StrictDocumentContract):
    key: str = Field(pattern=_KEY_PATTERN)
    event: str = Field(pattern=_EVENT_PATTERN)
    recipients: tuple[ActorSelector, ...] = Field(min_length=1, max_length=50)
    channels: tuple[NotificationChannel, ...] = Field(min_length=1, max_length=10)
    template: str = Field(min_length=1, max_length=200)
    delay_minutes: int = Field(default=0, alias="delayMinutes", ge=0, le=525_600)

    @field_validator("channels")
    @classmethod
    def validate_unique_channels(
        cls, channels: tuple[NotificationChannel, ...]
    ) -> tuple[NotificationChannel, ...]:
        if len(channels) != len(set(channels)):
            raise ValueError("notification channels must be unique")
        return channels


class ViewType(StrEnum):
    FORM = "form"
    DETAIL = "detail"
    TABLE = "table"
    BOARD = "board"
    CALENDAR = "calendar"
    TIMELINE = "timeline"
    DASHBOARD = "dashboard"
    PRINT = "print"


class ViewDefinition(StrictDocumentContract):
    key: str = Field(pattern=_KEY_PATTERN)
    name: str = Field(min_length=2, max_length=120)
    view_type: ViewType = Field(alias="type")
    fields: tuple[str, ...] = Field(min_length=1, max_length=100)
    title_field: str | None = Field(default=None, alias="titleField", pattern=_KEY_PATTERN)
    group_by: str | None = Field(default=None, alias="groupBy", pattern=_KEY_PATTERN)
    date_field: str | None = Field(default=None, alias="dateField", pattern=_KEY_PATTERN)
    default: bool = False

    @field_validator("fields")
    @classmethod
    def validate_unique_fields(cls, fields: tuple[str, ...]) -> tuple[str, ...]:
        if len(fields) != len(set(fields)):
            raise ValueError("view fields must be unique")
        return fields

    @model_validator(mode="after")
    def validate_view_configuration(self) -> Self:
        if self.view_type is ViewType.CALENDAR and self.date_field is None:
            raise ValueError("calendar views require a date field")
        if self.view_type is ViewType.BOARD and self.group_by is None:
            raise ValueError("board views require a group-by field")
        return self


class MetricAggregation(StrEnum):
    COUNT = "count"
    SUM = "sum"
    AVERAGE = "average"
    MINIMUM = "minimum"
    MAXIMUM = "maximum"


class MetricDefinition(StrictDocumentContract):
    key: str = Field(pattern=_KEY_PATTERN)
    name: str = Field(min_length=2, max_length=120)
    aggregation: MetricAggregation
    field: str | None = Field(default=None, pattern=_KEY_PATTERN)
    group_by: tuple[str, ...] = Field(default=(), alias="groupBy", max_length=10)
    filters: tuple[ConditionClause, ...] = Field(default=(), max_length=50)

    @model_validator(mode="after")
    def validate_aggregation(self) -> Self:
        if self.aggregation is MetricAggregation.COUNT and self.field is not None:
            raise ValueError("count metrics cannot declare a value field")
        if self.aggregation is not MetricAggregation.COUNT and self.field is None:
            raise ValueError("numeric metrics require a value field")
        return self


class IdentityMode(StrEnum):
    IDENTIFIED = "identified"
    PSEUDONYMOUS = "pseudonymous"
    ANONYMOUS = "anonymous"


class DocumentPrivacyPolicy(StrictDocumentContract):
    identity_mode: IdentityMode = Field(default=IdentityMode.IDENTIFIED, alias="identityMode")
    separate_identity_store: bool = Field(default=False, alias="separateIdentityStore")
    minimum_aggregate_size: int = Field(default=1, alias="minimumAggregateSize", ge=1)
    allow_individual_reporting: bool = Field(default=True, alias="allowIndividualReporting")
    sensitive_fields: tuple[str, ...] = Field(default=(), alias="sensitiveFields")

    @field_validator("sensitive_fields")
    @classmethod
    def validate_unique_sensitive_fields(cls, fields: tuple[str, ...]) -> tuple[str, ...]:
        if len(fields) != len(set(fields)):
            raise ValueError("sensitive fields must be unique")
        return fields

    @model_validator(mode="after")
    def protect_anonymous_responses(self) -> Self:
        if self.identity_mode is IdentityMode.ANONYMOUS:
            if self.minimum_aggregate_size < 3:
                raise ValueError("anonymous documents require an aggregation threshold of three")
            if self.allow_individual_reporting:
                raise ValueError("anonymous documents cannot allow individual reporting")
        return self


class DocumentTypeDefinition(StrictDocumentContract):
    """Immutable, runtime-neutral business process definition."""

    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        json_schema_extra={"$id": "https://schemas.kya.energy/platform/document-type/v1"},
    )

    schema_version: Literal["1"] = Field(alias="schemaVersion")
    document_type_id: str = Field(alias="id", pattern=_DOCUMENT_TYPE_ID_PATTERN)
    version: str = Field(pattern=_SEMVER_PATTERN)
    name: str = Field(min_length=2, max_length=120)
    record_schema: RecordSchema = Field(alias="recordSchema")
    references: tuple[ReferenceBinding, ...] = Field(default=(), max_length=100)
    workflow: WorkflowDefinition
    privacy: DocumentPrivacyPolicy = Field(default_factory=DocumentPrivacyPolicy)
    signatures: tuple[SignaturePolicy, ...] = Field(default=(), max_length=100)
    notifications: tuple[NotificationPolicy, ...] = Field(default=(), max_length=200)
    views: tuple[ViewDefinition, ...] = Field(min_length=1, max_length=100)
    metrics: tuple[MetricDefinition, ...] = Field(default=(), max_length=100)

    @model_validator(mode="after")
    def validate_cross_references(self) -> Self:
        field_keys = {field.key for field in self.record_schema.fields}
        transition_keys = {transition.key for transition in self.workflow.transitions}
        collections = {
            "reference": [reference.field for reference in self.references],
            "signature": [signature.key for signature in self.signatures],
            "notification": [notification.key for notification in self.notifications],
            "view": [view.key for view in self.views],
            "metric": [metric.key for metric in self.metrics],
        }
        for label, keys in collections.items():
            if len(keys) != len(set(keys)):
                raise ValueError(f"{label} keys must be unique")
        if any(reference.field not in field_keys for reference in self.references):
            raise ValueError("reference bindings must target declared record fields")
        if any(signature.transition_key not in transition_keys for signature in self.signatures):
            raise ValueError("signature policies must target declared transitions")
        for view in self.views:
            used_fields = set(view.fields) | {
                value
                for value in (view.title_field, view.group_by, view.date_field)
                if value is not None
            }
            if not used_fields <= field_keys:
                raise ValueError("views must reference declared record fields")
        for metric in self.metrics:
            used_fields = set(metric.group_by)
            if metric.field is not None:
                used_fields.add(metric.field)
            used_fields.update(condition.field for condition in metric.filters)
            if not used_fields <= field_keys:
                raise ValueError("metrics must reference declared record fields")
            if metric.field is not None:
                record_field = next(
                    field for field in self.record_schema.fields if field.key == metric.field
                )
                if record_field.field_type.value not in {"integer", "decimal"}:
                    raise ValueError("numeric metrics must target numeric record fields")
        for transition in self.workflow.transitions:
            if any(condition.field not in field_keys for condition in transition.conditions):
                raise ValueError("workflow conditions must reference declared record fields")
        default_views = [view for view in self.views if view.default]
        if len(default_views) != 1:
            raise ValueError("document types require exactly one default view")
        if not set(self.privacy.sensitive_fields) <= field_keys:
            raise ValueError("privacy policies must reference declared record fields")
        return self


__all__ = [
    "ActorSelector",
    "ActorSelectorKind",
    "ConditionClause",
    "ConditionOperator",
    "DocumentPrivacyPolicy",
    "DocumentTypeDefinition",
    "IdentityMode",
    "MetricAggregation",
    "MetricDefinition",
    "NotificationChannel",
    "NotificationPolicy",
    "ReferenceBinding",
    "ReferenceConsistency",
    "SignatureMode",
    "SignaturePolicy",
    "ViewDefinition",
    "ViewType",
    "WorkflowDefinition",
    "WorkflowState",
    "WorkflowStateCategory",
    "WorkflowTransition",
]
