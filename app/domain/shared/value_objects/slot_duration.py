from __future__ import annotations
from dataclasses import dataclass
from typing import ClassVar, Self
from app.domain.shared.result import Result
from app.domain.shared.value_object import BaseValueObject


@dataclass(frozen=True, slots=True)
class SlotDuration(BaseValueObject):
    SLOT_DURATION_INVALID_TYPE = "SlotDurationInvalidType"
    SLOT_DURATION_NOT_ALLOWED = "SlotDurationNotAllowed"
    ALLOWED: ClassVar[frozenset[int]] = frozenset({30, 45, 60, 90, 120})

    minutes: int

    @classmethod
    def create(cls, raw) -> Result[Self]:
        if isinstance(raw, bool) or not isinstance(raw, int):
            return Result.failure(cls.SLOT_DURATION_INVALID_TYPE)
        if raw not in cls.ALLOWED:
            return Result.failure(cls.SLOT_DURATION_NOT_ALLOWED)
        return Result.success(cls(minutes=raw))
