from __future__ import annotations
from dataclasses import dataclass
from typing import Self
from zoneinfo import ZoneInfo, available_timezones
from app.domain.shared.result import Result
from app.domain.shared.value_object import BaseValueObject

# Cache the set once at import time. Stable per Python install.
_AVAILABLE = frozenset(available_timezones())


@dataclass(frozen=True, slots=True)
class IanaTimezone(BaseValueObject):
    IANA_TIMEZONE_CANNOT_BE_EMPTY = "IanaTimezoneCannotBeEmpty"
    IANA_TIMEZONE_UNKNOWN = "IanaTimezoneUnknown"

    value: str

    @classmethod
    def create(cls, raw) -> Result[Self]:
        if raw is None or not isinstance(raw, str):
            return Result.failure(cls.IANA_TIMEZONE_CANNOT_BE_EMPTY)
        s = raw.strip()
        if not s:
            return Result.failure(cls.IANA_TIMEZONE_CANNOT_BE_EMPTY)
        if s not in _AVAILABLE:
            return Result.failure(cls.IANA_TIMEZONE_UNKNOWN)
        return Result.success(cls(value=s))

    def to_zoneinfo(self) -> ZoneInfo:
        return ZoneInfo(self.value)

    def __str__(self) -> str:
        return self.value
