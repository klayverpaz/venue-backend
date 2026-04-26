from __future__ import annotations
from datetime import datetime, time, timezone
from uuid import uuid4

from app.domain.resources.custom_attribute import CustomAttribute
from app.domain.resources.pricing_rule import PricingRule
from app.domain.resources.resource import Resource
from app.domain.resources.weekly_schedule import WeeklySchedule
from app.domain.shared.value_objects.money import Money
from app.domain.shared.value_objects.time_window import TimeWindow
from app.domain.shared.weekday import Weekday


def _w(sh: int, eh: int) -> TimeWindow:
    return TimeWindow.create(time(sh, 0), time(eh, 0)).value


def _money(cents: int) -> Money:
    return Money.create(cents).value


def _ws(slot=60, days=None) -> WeeklySchedule:
    return WeeklySchedule.create(
        slot_duration_minutes=slot,
        days=days or {Weekday.MONDAY: [_w(8, 22)]},
    ).value


def _valid_kwargs(**overrides):
    base = dict(
        owner_id=uuid4(),
        resource_type_id=uuid4(),
        slug="arena-zona-leste",
        name="Arena Zona Leste",
        description="Campo society",
        city="São Paulo",
        region="SP",
        timezone="America/Sao_Paulo",
        slot_duration_minutes=60,
        operating_hours=_ws(),
        base_price_cents=8000,
        customer_cancellation_cutoff_hours=24,
        base_attributes={},
        pricing_rules=[],
        custom_attributes=[],
        is_published=False,
    )
    base.update(overrides)
    return base


# --- happy path ---

def test_create_happy_path():
    r = Resource.create(**_valid_kwargs())
    assert r.is_success
    res = r.value
    assert res.slug.value == "arena-zona-leste"
    assert res.name.value == "Arena Zona Leste"
    assert res.timezone.value == "America/Sao_Paulo"
    assert res.slot_duration_minutes.minutes == 60
    assert res.base_price_cents.cents == 8000
    assert res.is_published is False
    assert res.deleted_at is None
    assert res.pricing_rules == ()
    assert res.custom_attributes == ()


# --- aggregated scalar VO failures ---

def test_create_aggregates_scalar_vo_errors():
    r = Resource.create(**_valid_kwargs(
        slug="UPPER!!!",        # SlugInvalidFormat
        name="",                # NameCannotBeEmpty
        timezone="Mars/Olympus",  # IanaTimezoneUnknown
        base_price_cents=-100,   # MoneyCannotBeNegative
    ))
    assert r.is_failure
    fields = {e.field for e in r.details}
    assert "slug" in fields
    assert "name" in fields
    assert "timezone" in fields
    assert "base_price_cents" in fields
