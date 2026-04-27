from __future__ import annotations
from enum import Enum


class Weekday(str, Enum):
    """Days of the week. str-Enum so JSON serializes to the value directly.

    Used by WeeklySchedule and PricingRule (resources feature). Lives in
    app/domain/shared/ rather than value_objects/ because it's a primitive
    enum, not a wrapped value with create()/validation.
    """

    MONDAY = "MONDAY"
    TUESDAY = "TUESDAY"
    WEDNESDAY = "WEDNESDAY"
    THURSDAY = "THURSDAY"
    FRIDAY = "FRIDAY"
    SATURDAY = "SATURDAY"
    SUNDAY = "SUNDAY"

    @classmethod
    def from_iso(cls, iso_weekday: int) -> "Weekday":
        """Maps Python's datetime.isoweekday() (1=Monday … 7=Sunday) to Weekday."""
        try:
            return _ISO_TO_WEEKDAY[iso_weekday]
        except KeyError as exc:
            raise ValueError(
                f"iso_weekday must be in [1, 7]; got {iso_weekday}",
            ) from exc


_ISO_TO_WEEKDAY: dict[int, Weekday] = {
    1: Weekday.MONDAY,
    2: Weekday.TUESDAY,
    3: Weekday.WEDNESDAY,
    4: Weekday.THURSDAY,
    5: Weekday.FRIDAY,
    6: Weekday.SATURDAY,
    7: Weekday.SUNDAY,
}
