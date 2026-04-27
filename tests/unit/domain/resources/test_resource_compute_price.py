from __future__ import annotations
from datetime import datetime, time, timedelta, timezone
from uuid import uuid4

from app.domain.resources.pricing_rule import PricingRule
from app.domain.resources.resource import Resource
from app.domain.resources.weekly_schedule import WeeklySchedule
from app.domain.shared.value_objects.date_time_range import DateTimeRange
from app.domain.shared.value_objects.money import Money
from app.domain.shared.value_objects.time_window import TimeWindow
from app.domain.shared.weekday import Weekday


def _money(cents: int) -> Money:
    r = Money.create(cents)
    assert r.is_success, r.error
    return r.value


def _window(start_h: int, end_h: int) -> TimeWindow:
    r = TimeWindow.create(time(start_h, 0), time(end_h, 0))
    assert r.is_success, r.error
    return r.value


def _full_week_schedule(slot: int = 60) -> WeeklySchedule:
    """All 7 days open 06:00–22:00."""
    r = WeeklySchedule.create(
        slot_duration_minutes=slot,
        days={wd: [_window(6, 22)] for wd in Weekday},
    )
    assert r.is_success, r.error or r.details
    return r.value


def _build_resource(
    *,
    base_price_cents: int = 5000,
    pricing_rules: list[PricingRule] | None = None,
    timezone_value: str = "America/Sao_Paulo",
    slot_duration_minutes: int = 60,
) -> Resource:
    r = Resource.create(
        owner_id=uuid4(),
        resource_type_id=uuid4(),
        slug="campo",
        name="Campo da Vila",
        description="",
        city="São Paulo",
        region="SP",
        timezone=timezone_value,
        slot_duration_minutes=slot_duration_minutes,
        base_price_cents=base_price_cents,
        customer_cancellation_cutoff_hours=24,
        operating_hours=_full_week_schedule(slot_duration_minutes),
        pricing_rules=pricing_rules or [],
        custom_attributes=[],
        base_attributes={},
    )
    assert r.is_success, r.error or r.details
    return r.value


def _slot_range_local(*, year=2026, month=4, day=27, hour=14, hours=1) -> DateTimeRange:
    """Build a slot in São Paulo local time (UTC-3) → UTC."""
    # São Paulo is UTC-3 in April (no DST in Brazil since 2019).
    start_utc = datetime(year, month, day, hour + 3, 0, 0, tzinfo=timezone.utc)
    end_utc = start_utc + timedelta(hours=hours)
    return DateTimeRange.create(start_at=start_utc, end_at=end_utc).value


def test_compute_price_falls_back_to_base_when_no_rule():
    r = _build_resource(base_price_cents=5000, pricing_rules=[])
    sr = _slot_range_local(hours=2)
    price = r.compute_price(sr)
    assert price.cents == 10000  # 2 slots × 5000


def test_compute_price_uses_matching_rule():
    rule = PricingRule.create(
        weekdays={Weekday.MONDAY},
        window=_window(18, 22),
        price=_money(12000),
    ).value
    r = _build_resource(base_price_cents=5000, pricing_rules=[rule])
    # 2026-04-27 is a Monday. Slot 18:00-20:00 local matches the rule.
    sr = _slot_range_local(day=27, hour=18, hours=2)
    price = r.compute_price(sr)
    assert price.cents == 24000  # 2 slots × 12000


def test_compute_price_mixes_rule_and_fallback():
    rule = PricingRule.create(
        weekdays={Weekday.MONDAY},
        window=_window(18, 20),
        price=_money(12000),
    ).value
    r = _build_resource(base_price_cents=5000, pricing_rules=[rule])
    # 17:00-19:00: 1 slot at base, 1 slot at rule.
    sr = _slot_range_local(day=27, hour=17, hours=2)
    price = r.compute_price(sr)
    assert price.cents == 5000 + 12000


def test_compute_price_different_weekdays_different_rules():
    monday_rule = PricingRule.create(
        weekdays={Weekday.MONDAY},
        window=_window(6, 22),
        price=_money(8000),
    ).value
    saturday_rule = PricingRule.create(
        weekdays={Weekday.SATURDAY},
        window=_window(6, 22),
        price=_money(15000),
    ).value
    r = _build_resource(
        base_price_cents=5000,
        pricing_rules=[monday_rule, saturday_rule],
    )
    # Monday 14:00-15:00 = 8000.
    monday = _slot_range_local(day=27, hour=14, hours=1)
    assert r.compute_price(monday).cents == 8000
    # Saturday 2026-04-25 14:00-15:00 = 15000.
    saturday = _slot_range_local(day=25, hour=14, hours=1)
    assert r.compute_price(saturday).cents == 15000


def test_compute_price_30min_slot_duration():
    r2 = _build_resource(base_price_cents=2000, slot_duration_minutes=30)
    sr = _slot_range_local(day=27, hour=14, hours=2)  # 4 slots of 30min
    assert r2.compute_price(sr).cents == 8000
