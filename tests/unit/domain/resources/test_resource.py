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


def _w_min(sh: int, sm: int, eh: int, em: int) -> TimeWindow:
    return TimeWindow.create(time(sh, sm), time(eh, em)).value


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


# --- cross-rule pricing checks ---

def test_create_rejects_overlapping_pricing_rules():
    rule_a = PricingRule.create(
        weekdays=[Weekday.FRIDAY], window=_w(18, 22), price=_money(12000),
    ).value
    rule_b = PricingRule.create(
        weekdays=[Weekday.FRIDAY], window=_w(20, 23), price=_money(15000),
    ).value
    r = Resource.create(**_valid_kwargs(
        operating_hours=_ws(days={Weekday.FRIDAY: [_w(8, 23)]}),
        pricing_rules=[rule_a, rule_b],
    ))
    assert r.is_failure
    codes = {(e.field, e.code) for e in r.details}
    assert ("pricing_rules[1]", Resource.PRICING_RULES_OVERLAP) in codes


def test_create_rejects_pricing_rule_misaligned():
    rule = PricingRule.create(
        weekdays=[Weekday.FRIDAY], window=_w_min(18, 30, 22, 0), price=_money(12000),
    ).value
    r = Resource.create(**_valid_kwargs(
        operating_hours=_ws(days={Weekday.FRIDAY: [_w(8, 23)]}),
        pricing_rules=[rule],
    ))
    assert r.is_failure
    codes = {(e.field, e.code) for e in r.details}
    assert ("pricing_rules[0]", Resource.PRICING_RULE_NOT_ALIGNED_TO_SLOT_GRID) in codes


def test_create_rejects_pricing_rule_outside_operating_hours():
    rule = PricingRule.create(
        weekdays=[Weekday.FRIDAY], window=_w(2, 4), price=_money(12000),
    ).value
    r = Resource.create(**_valid_kwargs(
        operating_hours=_ws(days={Weekday.FRIDAY: [_w(18, 23)]}),
        pricing_rules=[rule],
    ))
    assert r.is_failure
    codes = {(e.field, e.code) for e in r.details}
    assert ("pricing_rules[0]", Resource.PRICING_RULE_OUTSIDE_OPERATING_HOURS) in codes


def test_create_rejects_duplicate_custom_attribute_keys():
    a = CustomAttribute.create(key="wifi", label="Wi-Fi", value="sim").value
    b = CustomAttribute.create(key="wifi", label="Wi-Fi 5G", value="sim").value
    r = Resource.create(**_valid_kwargs(custom_attributes=[a, b]))
    assert r.is_failure
    codes = {(e.field, e.code) for e in r.details}
    assert ("custom_attributes[1]", Resource.DUPLICATE_CUSTOM_ATTRIBUTE_KEY) in codes


def test_create_rejects_custom_attribute_key_conflicting_with_base():
    a = CustomAttribute.create(key="wifi", label="Wi-Fi", value="sim").value
    r = Resource.create(**_valid_kwargs(
        base_attributes={"wifi": True},
        custom_attributes=[a],
    ))
    assert r.is_failure
    codes = {(e.field, e.code) for e in r.details}
    assert ("custom_attributes[0]", Resource.CUSTOM_ATTRIBUTE_KEY_CONFLICTS_WITH_BASE) in codes
