from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Self
from app.domain.shared.result import Result
from app.domain.shared.value_object import BaseValueObject

_KEY_RE = re.compile(r"^[a-z][a-z0-9_]*$")


@dataclass(frozen=True, slots=True)
class AttributeKey(BaseValueObject):
    ATTRIBUTE_KEY_CANNOT_BE_EMPTY = "AttributeKeyCannotBeEmpty"
    ATTRIBUTE_KEY_INVALID_FORMAT = "AttributeKeyInvalidFormat"
    ATTRIBUTE_KEY_CANNOT_BE_GREATER_THAN_MAX_LENGTH = "AttributeKeyCannotBeGreaterThanMaxLength"
    MAX_LENGTH = 50

    value: str

    @classmethod
    def create(cls, raw) -> Result[Self]:
        err = cls._validate(raw)
        if err:
            return Result.failure(err)
        return Result.success(cls(value=raw.strip()))

    @classmethod
    def create_if_not_empty(cls, raw) -> Result[Self | None]:
        if raw is None or (isinstance(raw, str) and not raw.strip()):
            return Result.success(None)
        return cls.create(raw)

    @staticmethod
    def _validate(raw) -> str:
        if raw is None or not isinstance(raw, str):
            return AttributeKey.ATTRIBUTE_KEY_CANNOT_BE_EMPTY
        s = raw.strip()
        if not s:
            return AttributeKey.ATTRIBUTE_KEY_CANNOT_BE_EMPTY
        if len(s) > AttributeKey.MAX_LENGTH:
            return AttributeKey.ATTRIBUTE_KEY_CANNOT_BE_GREATER_THAN_MAX_LENGTH
        if not _KEY_RE.match(s):
            return AttributeKey.ATTRIBUTE_KEY_INVALID_FORMAT
        return ""

    def __str__(self) -> str:
        return self.value
