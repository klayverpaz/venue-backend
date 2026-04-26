from __future__ import annotations
from dataclasses import dataclass
from typing import Self

from app.domain.shared.field_error import FieldError
from app.domain.shared.result import Result
from app.domain.shared.value_object import BaseValueObject
from app.domain.shared.value_objects.attribute_key import AttributeKey
from app.domain.shared.value_objects.short_description import ShortDescription
from app.domain.shared.value_objects.short_name import ShortName


@dataclass(frozen=True, slots=True)
class CustomAttribute(BaseValueObject):
    """Owner-defined freeform attribute on a Resource.

    Values are always strings (ShortDescription). Owners who want typed/
    filterable attributes request the admin to add them to
    ResourceType.attribute_schema (which becomes Resource.base_attributes).
    """

    key: AttributeKey
    label: ShortName
    value: ShortDescription

    @classmethod
    def create(cls, *, key: str, label: str, value: str) -> Result[Self]:
        errors: list[FieldError] = []

        key_r = AttributeKey.create(key)
        if key_r.is_failure:
            errors.append(FieldError(code=key_r.error, field="key"))

        label_r = ShortName.create(label)
        if label_r.is_failure:
            errors.append(FieldError(code=label_r.error, field="label"))

        value_r = ShortDescription.create(value)
        if value_r.is_failure:
            errors.append(FieldError(code=value_r.error, field="value"))

        if errors:
            return Result.failure_many(errors)

        return Result.success(cls(
            key=key_r.value,
            label=label_r.value,
            value=value_r.value,
        ))
