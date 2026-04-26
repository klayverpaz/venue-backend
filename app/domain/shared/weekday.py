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
