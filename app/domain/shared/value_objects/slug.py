from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Self
from app.domain.shared.result import Result
from app.domain.shared.value_object import BaseValueObject

_SLUG_RE = re.compile(r"^[a-z][a-z0-9-]*[a-z0-9]$")
_DOUBLE_DASH_RE = re.compile(r"--")


@dataclass(frozen=True, slots=True)
class Slug(BaseValueObject):
    SLUG_CANNOT_BE_EMPTY = "SlugCannotBeEmpty"
    SLUG_INVALID_FORMAT = "SlugInvalidFormat"
    SLUG_CANNOT_BE_GREATER_THAN_MAX_LENGTH = "SlugCannotBeGreaterThanMaxLength"
    MIN_LENGTH = 2
    MAX_LENGTH = 80

    value: str

    @classmethod
    def create(cls, raw) -> Result[Self]:
        err = cls._validate(raw)
        if err:
            return Result.failure(err)
        return Result.success(cls(value=raw.strip().lower()))

    @classmethod
    def create_if_not_empty(cls, raw) -> Result[Self | None]:
        if raw is None or (isinstance(raw, str) and not raw.strip()):
            return Result.success(None)
        return cls.create(raw)

    @staticmethod
    def _validate(raw) -> str:
        if raw is None or not isinstance(raw, str):
            return Slug.SLUG_CANNOT_BE_EMPTY
        s = raw.strip().lower()
        if not s:
            return Slug.SLUG_CANNOT_BE_EMPTY
        if len(s) > Slug.MAX_LENGTH:
            return Slug.SLUG_CANNOT_BE_GREATER_THAN_MAX_LENGTH
        if len(s) < Slug.MIN_LENGTH:
            return Slug.SLUG_INVALID_FORMAT
        if _DOUBLE_DASH_RE.search(s):
            return Slug.SLUG_INVALID_FORMAT
        if not _SLUG_RE.match(s):
            return Slug.SLUG_INVALID_FORMAT
        return ""

    def __str__(self) -> str:
        return self.value
