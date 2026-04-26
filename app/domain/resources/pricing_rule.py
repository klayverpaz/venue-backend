from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable, Self

from app.domain.shared.result import Result
from app.domain.shared.value_object import BaseValueObject
from app.domain.shared.value_objects.money import Money
from app.domain.shared.value_objects.time_window import TimeWindow
from app.domain.shared.weekday import Weekday


@dataclass(frozen=True, slots=True)
class PricingRule(BaseValueObject):
    """A price applied to slots matching a weekday set inside a time window.

    Cross-rule validation (overlap, alignment to slot grid, containment in
    operating hours) is done at the Resource aggregate level — it requires
    slot_duration_minutes and operating_hours that PricingRule alone does not
    have.
    """

    EMPTY_WEEKDAYS = "PricingRuleEmptyWeekdays"

    weekdays: frozenset[Weekday]
    window: TimeWindow
    price: Money

    @classmethod
    def create(
        cls,
        *,
        weekdays: Iterable[Weekday],
        window: TimeWindow,
        price: Money,
    ) -> Result[Self]:
        ws = frozenset(weekdays)
        if not ws:
            return Result.failure(cls.EMPTY_WEEKDAYS)
        return Result.success(cls(weekdays=ws, window=window, price=price))
