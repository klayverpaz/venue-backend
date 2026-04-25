from __future__ import annotations
from datetime import datetime
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field
from app.use_cases.catalog.dtos import ResourceTypeDto


_DataType = Literal["string", "int", "bool", "enum"]


class AttributeDefinitionPayload(BaseModel):
    """Wire format for an attribute definition. VOs own length validation;
    no max_length on key/label here."""
    model_config = ConfigDict(extra="forbid")

    key: str
    label: str
    data_type: _DataType
    required: bool = False
    enum_values: list[str] | None = None


class CreateResourceTypeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slug: str
    name: str
    description: str = ""
    attribute_schema: list[AttributeDefinitionPayload] = Field(default_factory=list)
    is_active: bool = True


class UpdateResourceTypeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    description: str | None = None
    attribute_schema: list[AttributeDefinitionPayload] | None = None
    is_active: bool | None = None


class AttributeDefinitionResponse(BaseModel):
    key: str
    label: str
    data_type: _DataType
    required: bool
    enum_values: list[str] | None = None


class ResourceTypeResponse(BaseModel):
    id: UUID
    slug: str
    name: str
    description: str
    attribute_schema: list[AttributeDefinitionResponse]
    is_active: bool
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_dto(cls, dto: ResourceTypeDto) -> "ResourceTypeResponse":
        return cls(
            id=dto.id,
            slug=dto.slug,
            name=dto.name,
            description=dto.description,
            attribute_schema=[
                AttributeDefinitionResponse(
                    key=a.key, label=a.label, data_type=a.data_type,  # type: ignore[arg-type]
                    required=a.required, enum_values=a.enum_values,
                )
                for a in dto.attribute_schema
            ],
            is_active=dto.is_active,
            created_at=dto.created_at,
            updated_at=dto.updated_at,
        )


class ResourceTypeListResponse(BaseModel):
    items: list[ResourceTypeResponse]
    limit: int
    offset: int
