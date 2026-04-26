from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable, Self
from app.domain.catalog.attribute import AttrType, AttributeDefinition
from app.domain.shared.entity import BaseEntity
from app.domain.shared.field_error import FieldError
from app.domain.shared.result import Result
from app.domain.shared.value_objects.name import Name
from app.domain.shared.value_objects.short_description import ShortDescription
from app.domain.shared.value_objects.slug import Slug


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(slots=True, kw_only=True)
class ResourceType(BaseEntity):
    DUPLICATE_ATTRIBUTE_KEY = "DuplicateAttributeKey"
    REQUIRED_ATTRIBUTE_MISSING = "RequiredAttributeMissing"
    UNKNOWN_ATTRIBUTE_KEY = "UnknownAttributeKey"
    ATTRIBUTE_TYPE_MISMATCH = "AttributeTypeMismatch"
    ATTRIBUTE_ENUM_VALUE_NOT_ALLOWED = "AttributeEnumValueNotAllowed"

    slug: Slug
    name: Name
    description: ShortDescription
    is_active: bool = True
    _attribute_schema: list[AttributeDefinition] = field(default_factory=list, repr=False)

    @classmethod
    def create(
        cls,
        *,
        slug: str,
        name: str,
        description: str,
        attribute_schema: Iterable[AttributeDefinition],
        is_active: bool = True,
    ) -> Result[Self]:
        errors: list[FieldError] = []

        slug_r = Slug.create(slug)
        if slug_r.is_failure:
            errors.append(FieldError(code=slug_r.error, field="slug"))

        name_r = Name.create(name)
        if name_r.is_failure:
            errors.append(FieldError(code=name_r.error, field="name"))

        desc_r = ShortDescription.create(description)
        if desc_r.is_failure:
            errors.append(FieldError(code=desc_r.error, field="description"))

        schema_list = list(attribute_schema)
        if cls._has_duplicate_keys(schema_list):
            errors.append(FieldError(code=cls.DUPLICATE_ATTRIBUTE_KEY, field="attribute_schema"))

        if errors:
            return Result.failure_many(errors)

        return Result.success(cls(
            slug=slug_r.value,
            name=name_r.value,
            description=desc_r.value,
            is_active=is_active,
            _attribute_schema=schema_list,
        ))

    @property
    def attribute_schema(self) -> tuple[AttributeDefinition, ...]:
        return tuple(self._attribute_schema)

    def update_metadata(
        self, *, name: str | None = None, description: str | None = None,
    ) -> Result[None]:
        """Updates name and/or description from raw input.

        VO validation failures are entity-level invariants ("name is always a
        valid Name"), so this returns Result[None] per spec §4.4. Aggregates
        failures across both fields via failure_many. No-op when both args
        are None.
        """
        if name is None and description is None:
            return Result.success(None)

        errors: list[FieldError] = []
        new_name = self.name
        new_desc = self.description

        if name is not None:
            r = Name.create(name)
            if r.is_failure:
                errors.append(FieldError(code=r.error, field="name"))
            else:
                new_name = r.value

        if description is not None:
            r = ShortDescription.create(description)
            if r.is_failure:
                errors.append(FieldError(code=r.error, field="description"))
            else:
                new_desc = r.value

        if errors:
            return Result.failure_many(errors)

        self.name = new_name
        self.description = new_desc
        self.updated_at = _utcnow()
        return Result.success(None)

    def replace_attribute_schema(self, definitions: Iterable[AttributeDefinition]) -> Result[None]:
        """Wholesale replacement. Enforces unique-key invariant — returns Result[None].

        Emits via failure_many for envelope-shape consistency with
        ResourceType.create, even though only one rule can fail here.
        """
        defs = list(definitions)
        if self._has_duplicate_keys(defs):
            return Result.failure_many([
                FieldError(code=self.DUPLICATE_ATTRIBUTE_KEY, field="attribute_schema"),
            ])
        self._attribute_schema = defs
        self.updated_at = _utcnow()
        return Result.success(None)

    def activate(self) -> None:
        self.is_active = True
        self.updated_at = _utcnow()

    def deactivate(self) -> None:
        self.is_active = False
        self.updated_at = _utcnow()

    def validate_attributes(self, values: dict[str, Any]) -> Result[None]:
        """Validate a dict of raw values against this type's attribute_schema.

        Used by future Plan 06 Resource.create() to validate Resource.base_attributes
        before persistence. Returns aggregated errors as Result.failure_many of
        FieldError, one per failing attribute key.
        """
        errors: list[FieldError] = []
        defs_by_key = {d.key.value: d for d in self._attribute_schema}

        # Required attributes must be present.
        for d in self._attribute_schema:
            if d.required and d.key.value not in values:
                errors.append(FieldError(
                    code=self.REQUIRED_ATTRIBUTE_MISSING,
                    field=d.key.value,
                ))

        for key, value in values.items():
            d = defs_by_key.get(key)
            if d is None:
                errors.append(FieldError(code=self.UNKNOWN_ATTRIBUTE_KEY, field=key))
                continue

            if d.data_type == AttrType.STRING:
                if not isinstance(value, str):
                    errors.append(FieldError(code=self.ATTRIBUTE_TYPE_MISMATCH, field=key))
            elif d.data_type == AttrType.INT:
                # bool is a subclass of int; reject explicitly.
                if isinstance(value, bool) or not isinstance(value, int):
                    errors.append(FieldError(code=self.ATTRIBUTE_TYPE_MISMATCH, field=key))
            elif d.data_type == AttrType.BOOL:
                if not isinstance(value, bool):
                    errors.append(FieldError(code=self.ATTRIBUTE_TYPE_MISMATCH, field=key))
            elif d.data_type == AttrType.ENUM:
                allowed = {v.value for v in (d.enum_values or ())}
                if not isinstance(value, str) or value not in allowed:
                    errors.append(FieldError(
                        code=self.ATTRIBUTE_ENUM_VALUE_NOT_ALLOWED,
                        field=key,
                    ))

        if errors:
            return Result.failure_many(errors)
        return Result.success(None)

    @staticmethod
    def _has_duplicate_keys(definitions: list[AttributeDefinition]) -> bool:
        keys = [d.key.value for d in definitions]
        return len(keys) != len(set(keys))
