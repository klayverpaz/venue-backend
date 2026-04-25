from __future__ import annotations
from dataclasses import dataclass
from datetime import time
from typing import Self
from app.domain.shared.result import Result
from app.domain.shared.value_object import BaseValueObject


@dataclass(frozen=True, slots=True)
class TimeWindow(BaseValueObject):
    TIME_WINDOW_INVALID_TYPE = "TimeWindowInvalidType"
    TIME_WINDOW_START_MUST_BE_BEFORE_END = "TimeWindowStartMustBeBeforeEnd"

    start: time
    end: time

    @classmethod
    def create(cls, start, end) -> Result[Self]:
        if not isinstance(start, time) or not isinstance(end, time):
            return Result.failure(cls.TIME_WINDOW_INVALID_TYPE)
        if start >= end:
            return Result.failure(cls.TIME_WINDOW_START_MUST_BE_BEFORE_END)
        return Result.success(cls(start=start, end=end))

    def duration_minutes(self) -> int:
        return (self.end.hour - self.start.hour) * 60 + (self.end.minute - self.start.minute)
