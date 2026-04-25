from __future__ import annotations
from dataclasses import dataclass
from typing import Self
from app.domain.shared.result import Result
from app.domain.shared.value_object import BaseValueObject


@dataclass(frozen=True, slots=True)
class CancellationCutoff(BaseValueObject):
    CANCELLATION_CUTOFF_INVALID_TYPE = "CancellationCutoffInvalidType"
    CANCELLATION_CUTOFF_OUT_OF_RANGE = "CancellationCutoffOutOfRange"
    MIN_HOURS = 0
    MAX_HOURS = 168  # 1 week

    hours: int

    @classmethod
    def create(cls, raw) -> Result[Self]:
        if isinstance(raw, bool) or not isinstance(raw, int):
            return Result.failure(cls.CANCELLATION_CUTOFF_INVALID_TYPE)
        if not (cls.MIN_HOURS <= raw <= cls.MAX_HOURS):
            return Result.failure(cls.CANCELLATION_CUTOFF_OUT_OF_RANGE)
        return Result.success(cls(hours=raw))
