from __future__ import annotations
from dataclasses import dataclass
from typing import Self
from app.domain.shared.result import Result
from app.domain.shared.value_object import BaseValueObject


@dataclass(frozen=True, slots=True)
class Name(BaseValueObject):
    NAME_CANNOT_BE_EMPTY = "NameCannotBeEmpty"
    NAME_CANNOT_BE_GREATER_THAN_MAX_LENGTH = "NameCannotBeGreaterThanMaxLength"
    NAME_CONTAINS_INVALID_CHARACTERS = "NameContainsInvalidCharacters"
    MAX_LENGTH = 500

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
            return Name.NAME_CANNOT_BE_EMPTY
        s = raw.strip()
        if not s:
            return Name.NAME_CANNOT_BE_EMPTY
        if len(s) > Name.MAX_LENGTH:
            return Name.NAME_CANNOT_BE_GREATER_THAN_MAX_LENGTH
        for ch in s:
            if ord(ch) < 0x20:
                return Name.NAME_CONTAINS_INVALID_CHARACTERS
        return ""

    def __str__(self) -> str:
        return self.value
