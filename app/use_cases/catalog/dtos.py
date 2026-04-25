from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID
from app.domain.catalog.attribute import AttrType, AttributeDefinition
from app.domain.catalog.resource_type import ResourceType


@dataclass(frozen=True, slots=True)
class AttributeDefinitionDto:
    key: str
    label: str
    data_type: str
    required: bool
    enum_values: list[str] | None

    @classmethod
    def from_vo(cls, a: AttributeDefinition) -> "AttributeDefinitionDto":
        return cls(
            key=a.key.value,
            label=a.label.value,
            data_type=a.data_type.value,
            required=a.required,
            enum_values=[v.value for v in a.enum_values] if a.enum_values else None,
        )


@dataclass(frozen=True, slots=True)
class ResourceTypeDto:
    id: UUID
    slug: str
    name: str
    description: str
    attribute_schema: list[AttributeDefinitionDto]
    is_active: bool
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_entity(cls, rt: ResourceType) -> "ResourceTypeDto":
        return cls(
            id=rt.id,
            slug=rt.slug.value,
            name=rt.name.value,
            description=rt.description.value,
            attribute_schema=[AttributeDefinitionDto.from_vo(a) for a in rt.attribute_schema],
            is_active=rt.is_active,
            created_at=rt.created_at,
            updated_at=rt.updated_at,
        )
