from __future__ import annotations
from datetime import time

from app.domain.resources.pricing_rule import PricingRule
from app.domain.shared.value_objects.money import Money
from app.domain.shared.value_objects.time_window import TimeWindow
from app.domain.shared.weekday import Weekday


def _money(cents: int) -> Money:
    r = Money.create(cents)
    assert r.is_success
    return r.value


def _window(start_h: int, end_h: int) -> TimeWindow:
    r = TimeWindow.create(time(start_h, 0), time(end_h, 0))
    assert r.is_success
    return r.value


def test_create_happy_path():
    r = PricingRule.create(
        weekdays=[Weekday.FRIDAY, Weekday.SATURDAY],
        window=_window(18, 23),
        price=_money(12000),
    )
    assert r.is_success
    rule = r.value
    assert rule.weekdays == frozenset({Weekday.FRIDAY, Weekday.SATURDAY})
    assert rule.window.start == time(18, 0)
    assert rule.price.cents == 12000


def test_create_rejects_empty_weekdays():
    r = PricingRule.create(
        weekdays=[],
        window=_window(18, 23),
        price=_money(12000),
    )
    assert r.is_failure
    assert r.error == PricingRule.EMPTY_WEEKDAYS


def test_equality_by_value():
    a = PricingRule.create(weekdays=[Weekday.MONDAY], window=_window(9, 17), price=_money(5000)).value
    b = PricingRule.create(weekdays=[Weekday.MONDAY], window=_window(9, 17), price=_money(5000)).value
    assert a == b
    assert hash(a) == hash(b)
