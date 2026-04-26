from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Self
from app.domain.shared.field_error import FieldError
from app.domain.shared.result import Result
from app.domain.shared.value_object import BaseValueObject
from app.domain.shared.value_objects.attribute_key import AttributeKey
from app.domain.shared.value_objects.short_name import ShortName


class AttrType(str, Enum):
    STRING = "string"
    INT = "int"
    BOOL = "bool"
    ENUM = "enum"


@dataclass(frozen=True, slots=True)
class AttributeDefinition(BaseValueObject):
    ENUM_TYPE_REQUIRES_VALUES = "EnumTypeRequiresValues"
    NON_ENUM_TYPE_CANNOT_HAVE_VALUES = "NonEnumTypeCannotHaveValues"

    key: AttributeKey
    label: ShortName
    data_type: AttrType
    required: bool
    # tuple instead of list so the VO stays hashable + frozen-friendly.
    enum_values: tuple[ShortName, ...] | None

    @classmethod
    def create(
        cls,
        *,
        key: str,
        label: str,
        data_type: AttrType,
        required: bool = False,
        enum_values: list[str] | None = None,
    ) -> Result[Self]:
        errors: list[FieldError] = []

        key_r = AttributeKey.create(key)
        if key_r.is_failure:
            errors.append(FieldError(code=key_r.error, field="key"))

        label_r = ShortName.create(label)
        if label_r.is_failure:
            errors.append(FieldError(code=label_r.error, field="label"))

        enum_vos: tuple[ShortName, ...] | None = None
        if data_type == AttrType.ENUM:
            if not enum_values:
                errors.append(FieldError(
                    code=cls.ENUM_TYPE_REQUIRES_VALUES,
                    field="enum_values",
                ))
            else:
                vos: list[ShortName] = []
                per_value_errors: list[FieldError] = []
                for idx, raw in enumerate(enum_values):
                    r = ShortName.create(raw)
                    if r.is_failure:
                        per_value_errors.append(FieldError(
                            code=r.error,
                            field=f"enum_values[{idx}]",
                        ))
                    else:
                        vos.append(r.value)
                if per_value_errors:
                    errors.extend(per_value_errors)
                else:
                    enum_vos = tuple(vos)
        else:
            if enum_values:
                errors.append(FieldError(
                    code=cls.NON_ENUM_TYPE_CANNOT_HAVE_VALUES,
                    field="enum_values",
                ))

        if errors:
            return Result.failure_many(errors)

        return Result.success(cls(
            key=key_r.value,
            label=label_r.value,
            data_type=data_type,
            required=required,
            enum_values=enum_vos,
        ))
