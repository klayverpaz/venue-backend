from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Self
from app.domain.shared.result import Result
from app.domain.shared.value_object import BaseValueObject


@dataclass(frozen=True, slots=True)
class DateTimeRange(BaseValueObject):
    DATE_TIME_RANGE_INVALID_TYPE = "DateTimeRangeInvalidType"
    DATE_TIME_RANGE_NOT_TZ_AWARE = "DateTimeRangeNotTzAware"
    DATE_TIME_RANGE_NOT_UTC = "DateTimeRangeNotUtc"
    DATE_TIME_RANGE_START_MUST_BE_BEFORE_END = "DateTimeRangeStartMustBeBeforeEnd"

    start_at: datetime
    end_at: datetime

    @classmethod
    def create(cls, start_at, end_at) -> Result[Self]:
        if not isinstance(start_at, datetime) or not isinstance(end_at, datetime):
            return Result.failure(cls.DATE_TIME_RANGE_INVALID_TYPE)
        if start_at.tzinfo is None or end_at.tzinfo is None:
            return Result.failure(cls.DATE_TIME_RANGE_NOT_TZ_AWARE)
        if start_at.utcoffset() != timedelta(0) or end_at.utcoffset() != timedelta(0):
            return Result.failure(cls.DATE_TIME_RANGE_NOT_UTC)
        if start_at >= end_at:
            return Result.failure(cls.DATE_TIME_RANGE_START_MUST_BE_BEFORE_END)
        return Result.success(cls(start_at=start_at, end_at=end_at))

    def duration_minutes(self) -> int:
        delta = self.end_at - self.start_at
        return int(delta.total_seconds() // 60)

    def overlaps(self, other: "DateTimeRange") -> bool:
        # Half-open interval [start_at, end_at): touching does NOT overlap.
        return self.start_at < other.end_at and other.start_at < self.end_at
