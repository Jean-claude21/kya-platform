"""Versioned business-record schema shared by forms, workflows and applications."""

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from kya_platform.contracts.artifact_manifest import CapabilityPermission


class StrictRecordContract(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class RecordFieldType(StrEnum):
    TEXT = "text"
    LONG_TEXT = "long-text"
    INTEGER = "integer"
    DECIMAL = "decimal"
    BOOLEAN = "boolean"
    DATE = "date"
    DATETIME = "datetime"
    CHOICE = "choice"
    RELATION = "relation"
    ATTACHMENT = "attachment"
    JSON = "json"


class RelationCardinality(StrEnum):
    ONE_TO_ONE = "one-to-one"
    MANY_TO_ONE = "many-to-one"
    ONE_TO_MANY = "one-to-many"
    MANY_TO_MANY = "many-to-many"


class RelationDefinition(StrictRecordContract):
    target_schema_id: str = Field(
        alias="targetSchemaId", pattern=r"^kya:data-schema:[a-z0-9][a-z0-9-]*$"
    )
    cardinality: RelationCardinality


class AttachmentPolicy(StrictRecordContract):
    max_files: int = Field(default=1, alias="maxFiles", ge=1, le=50)
    max_bytes_per_file: int = Field(alias="maxBytesPerFile", ge=1, le=104_857_600)
    allowed_media_types: tuple[str, ...] = Field(
        alias="allowedMediaTypes", min_length=1, max_length=32
    )

    @field_validator("allowed_media_types")
    @classmethod
    def unique_media_types(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if len(values) != len(set(values)):
            raise ValueError("attachment media types must be unique")
        if any("/" not in value or value == "*/*" for value in values):
            raise ValueError("attachment media types must be explicit")
        return values


class RecordField(StrictRecordContract):
    key: str = Field(pattern=r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$")
    label: str = Field(min_length=1, max_length=120)
    field_type: RecordFieldType = Field(alias="type")
    required: bool = False
    multiple: bool = False
    choices: tuple[str, ...] = Field(default=(), max_length=200)
    relation: RelationDefinition | None = None
    attachment: AttachmentPolicy | None = None

    @model_validator(mode="after")
    def validate_type_configuration(self) -> RecordField:
        if self.field_type is RecordFieldType.CHOICE and not self.choices:
            raise ValueError("choice fields require choices")
        if self.field_type is not RecordFieldType.CHOICE and self.choices:
            raise ValueError("only choice fields may declare choices")
        if self.field_type is RecordFieldType.RELATION and self.relation is None:
            raise ValueError("relation fields require a relation definition")
        if self.field_type is not RecordFieldType.RELATION and self.relation is not None:
            raise ValueError("only relation fields may declare a relation")
        if self.field_type is RecordFieldType.ATTACHMENT and self.attachment is None:
            raise ValueError("attachment fields require an attachment policy")
        if self.field_type is not RecordFieldType.ATTACHMENT and self.attachment is not None:
            raise ValueError("only attachment fields may declare an attachment policy")
        if len(self.choices) != len(set(self.choices)):
            raise ValueError("field choices must be unique")
        return self


class RecordAccessPolicy(StrictRecordContract):
    enforcement: Literal["schema", "record"] = "schema"
    permissions: tuple[CapabilityPermission, ...] = Field(min_length=1)

    @field_validator("permissions")
    @classmethod
    def unique_permissions(
        cls, permissions: tuple[CapabilityPermission, ...]
    ) -> tuple[CapabilityPermission, ...]:
        if len(permissions) != len(set(permissions)):
            raise ValueError("record permissions must be unique")
        return permissions


class RetentionPolicy(StrictRecordContract):
    retain_days: int = Field(alias="retainDays", ge=1)
    soft_delete_days: int = Field(default=30, alias="softDeleteDays", ge=0)
    legal_hold_supported: bool = Field(default=False, alias="legalHoldSupported")


class RecordSchema(StrictRecordContract):
    """Immutable schema version; records reference its exact id and version."""

    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        json_schema_extra={"$id": "https://schemas.kya.energy/platform/record-schema/v1"},
    )

    schema_version: Literal["1"] = Field(alias="schemaVersion")
    schema_id: str = Field(alias="id", pattern=r"^kya:data-schema:[a-z0-9][a-z0-9-]*$")
    version: str = Field(pattern=r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
    name: str = Field(min_length=2, max_length=120)
    owner_scope: str = Field(alias="ownerScope", min_length=1, max_length=255)
    fields: tuple[RecordField, ...] = Field(min_length=1, max_length=500)
    access: RecordAccessPolicy
    retention: RetentionPolicy

    @field_validator("fields")
    @classmethod
    def unique_fields(cls, fields: tuple[RecordField, ...]) -> tuple[RecordField, ...]:
        keys = [field.key for field in fields]
        if len(keys) != len(set(keys)):
            raise ValueError("record field keys must be unique")
        return fields


__all__ = [
    "AttachmentPolicy",
    "RecordAccessPolicy",
    "RecordField",
    "RecordFieldType",
    "RecordSchema",
    "RelationCardinality",
    "RelationDefinition",
    "RetentionPolicy",
]
