from __future__ import annotations
from dataclasses import dataclass
from typing import Self

from app.domain.shared.field_error import FieldError
from app.domain.shared.result import Result
from app.domain.shared.value_object import BaseValueObject
from app.domain.shared.value_objects.time_window import TimeWindow
from app.domain.shared.weekday import Weekday


@dataclass(frozen=True, slots=True)
class WeeklySchedule(BaseValueObject):
    """Operating hours per weekday. 0..N TimeWindow per day; ordered, non-
    overlapping, slot-grid-aligned. Closed days are an empty tuple.

    Built via WeeklySchedule.create(slot_duration_minutes=..., days={...}). The
    factory takes a dict of Weekday → list[TimeWindow] for ergonomics; the
    storage shape is seven explicit tuple fields.
    """

    WINDOWS_NOT_ORDERED = "WeeklyScheduleWindowsNotOrdered"
    WINDOWS_OVERLAP = "WeeklyScheduleWindowsOverlap"
    WINDOW_NOT_ALIGNED_TO_SLOT_GRID = "WeeklyScheduleWindowNotAlignedToSlotGrid"

    monday: tuple[TimeWindow, ...] = ()
    tuesday: tuple[TimeWindow, ...] = ()
    wednesday: tuple[TimeWindow, ...] = ()
    thursday: tuple[TimeWindow, ...] = ()
    friday: tuple[TimeWindow, ...] = ()
    saturday: tuple[TimeWindow, ...] = ()
    sunday: tuple[TimeWindow, ...] = ()

    @classmethod
    def create(
        cls,
        *,
        slot_duration_minutes: int,
        days: dict[Weekday, list[TimeWindow]],
    ) -> Result[Self]:
        errors: list[FieldError] = []
        per_day: dict[Weekday, tuple[TimeWindow, ...]] = {}

        for wd in Weekday:
            windows = days.get(wd, [])
            field_prefix = f"days.{wd.value.lower()}"

            for idx, w in enumerate(windows):
                # Alignment check (independent per window).
                start_minutes = w.start.hour * 60 + w.start.minute
                duration = w.duration_minutes()
                if (start_minutes % slot_duration_minutes) != 0 or (duration % slot_duration_minutes) != 0:
                    errors.append(FieldError(
                        code=cls.WINDOW_NOT_ALIGNED_TO_SLOT_GRID,
                        field=f"{field_prefix}[{idx}]",
                    ))

                # Ordering + overlap (compare with previous window).
                if idx > 0:
                    prev = windows[idx - 1]
                    if w.start < prev.start:
                        errors.append(FieldError(
                            code=cls.WINDOWS_NOT_ORDERED,
                            field=f"{field_prefix}[{idx}]",
                        ))
                    elif w.start < prev.end:
                        # prev.start <= w.start < prev.end → overlap
                        errors.append(FieldError(
                            code=cls.WINDOWS_OVERLAP,
                            field=f"{field_prefix}[{idx}]",
                        ))

            per_day[wd] = tuple(windows)

        if errors:
            return Result.failure_many(errors)

        return Result.success(cls(
            monday=per_day[Weekday.MONDAY],
            tuesday=per_day[Weekday.TUESDAY],
            wednesday=per_day[Weekday.WEDNESDAY],
            thursday=per_day[Weekday.THURSDAY],
            friday=per_day[Weekday.FRIDAY],
            saturday=per_day[Weekday.SATURDAY],
            sunday=per_day[Weekday.SUNDAY],
        ))

    def for_weekday(self, day: Weekday) -> tuple[TimeWindow, ...]:
        return getattr(self, day.value.lower())
