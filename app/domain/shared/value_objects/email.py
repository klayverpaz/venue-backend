from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Self
from app.domain.shared.result import Result
from app.domain.shared.value_object import BaseValueObject

_EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")


@dataclass(frozen=True, slots=True)
class Email(BaseValueObject):
    EMAIL_CANNOT_BE_EMPTY = "EmailCannotBeEmpty"
    EMAIL_INVALID_FORMAT = "EmailInvalidFormat"
    EMAIL_CANNOT_BE_GREATER_THAN_MAX_LENGTH = "EmailCannotBeGreaterThanMaxLength"
    MAX_LENGTH = 254

    value: str  # always lowercase, no surrounding whitespace

    @classmethod
    def create(cls, raw) -> Result[Self]:
        err = cls._validate(raw)
        if err:
            return Result.failure(err)
        normalized = raw.strip().lower()
        return Result.success(cls(value=normalized))

    @classmethod
    def create_if_not_empty(cls, raw) -> Result[Self | None]:
        if raw is None or (isinstance(raw, str) and not raw.strip()):
            return Result.success(None)
        return cls.create(raw)

    @staticmethod
    def _validate(raw) -> str:
        if raw is None or not isinstance(raw, str):
            return Email.EMAIL_CANNOT_BE_EMPTY
        normalized = raw.strip().lower()
        if not normalized:
            return Email.EMAIL_CANNOT_BE_EMPTY
        if len(normalized) > Email.MAX_LENGTH:
            return Email.EMAIL_CANNOT_BE_GREATER_THAN_MAX_LENGTH
        if not _EMAIL_RE.match(normalized):
            return Email.EMAIL_INVALID_FORMAT
        return ""

    def __str__(self) -> str:
        return self.value
