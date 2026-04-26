from __future__ import annotations
from datetime import datetime, time, timezone
from uuid import uuid4

from app.domain.resources.custom_attribute import CustomAttribute
from app.domain.resources.pricing_rule import PricingRule
from app.domain.resources.resource import Resource
from app.domain.resources.weekly_schedule import WeeklySchedule
from app.domain.shared.value_objects.cancellation_cutoff import CancellationCutoff
from app.domain.shared.value_objects.money import Money
from app.domain.shared.value_objects.slot_duration import SlotDuration
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


def test_update_metadata_partial():
    res = Resource.create(**_valid_kwargs()).value
    r = res.update_metadata(name="Novo Nome", city="Rio de Janeiro")
    assert r.is_success
    assert res.name.value == "Novo Nome"
    assert res.city.value == "Rio de Janeiro"


def test_update_metadata_aggregates_failures():
    res = Resource.create(**_valid_kwargs()).value
    r = res.update_metadata(name="", city="")
    assert r.is_failure
    fields = {e.field for e in r.details}
    assert "name" in fields
    assert "city" in fields


def test_replace_operating_hours_revalidates_pricing_rules():
    rule = PricingRule.create(
        weekdays=[Weekday.MONDAY], window=_w(18, 22), price=_money(10000),
    ).value
    res = Resource.create(**_valid_kwargs(
        operating_hours=_ws(days={Weekday.MONDAY: [_w(8, 23)]}),
        pricing_rules=[rule],
    )).value

    new_hours = WeeklySchedule.create(
        slot_duration_minutes=60,
        days={Weekday.MONDAY: [_w(8, 12)]},  # rule no longer fits
    ).value
    r = res.replace_operating_hours(new_hours)
    assert r.is_failure
    codes = {e.code for e in r.details}
    assert Resource.PRICING_RULE_OUTSIDE_OPERATING_HOURS in codes


def test_replace_pricing_rules_overlaps():
    res = Resource.create(**_valid_kwargs(
        operating_hours=_ws(days={Weekday.MONDAY: [_w(8, 23)]}),
    )).value
    a = PricingRule.create(weekdays=[Weekday.MONDAY], window=_w(8, 14), price=_money(5000)).value
    b = PricingRule.create(weekdays=[Weekday.MONDAY], window=_w(13, 22), price=_money(10000)).value
    r = res.replace_pricing_rules([a, b])
    assert r.is_failure
    codes = {e.code for e in r.details}
    assert Resource.PRICING_RULES_OVERLAP in codes


def test_replace_base_attributes_conflict_with_custom():
    custom = CustomAttribute.create(key="wifi", label="Wi-Fi", value="sim").value
    res = Resource.create(**_valid_kwargs(custom_attributes=[custom])).value
    r = res.replace_base_attributes({"wifi": True})
    assert r.is_failure
    codes = {e.code for e in r.details}
    assert Resource.CUSTOM_ATTRIBUTE_KEY_CONFLICTS_WITH_BASE in codes


def test_replace_custom_attributes_disjoint_with_base():
    res = Resource.create(**_valid_kwargs(base_attributes={"wifi": True})).value
    custom = CustomAttribute.create(key="wifi", label="Wi-Fi", value="sim").value
    r = res.replace_custom_attributes([custom])
    assert r.is_failure
    codes = {e.code for e in r.details}
    assert Resource.CUSTOM_ATTRIBUTE_KEY_CONFLICTS_WITH_BASE in codes


def test_set_base_price_no_invariant():
    res = Resource.create(**_valid_kwargs()).value
    res.set_base_price(_money(15000))
    assert res.base_price_cents.cents == 15000


def test_set_cancellation_cutoff_no_invariant():
    res = Resource.create(**_valid_kwargs()).value
    new_cutoff = CancellationCutoff.create(48).value
    res.set_cancellation_cutoff(new_cutoff)
    assert res.customer_cancellation_cutoff_hours.hours == 48


def test_set_slot_duration_revalidates_hours_and_rules():
    rule = PricingRule.create(
        weekdays=[Weekday.MONDAY], window=_w(8, 12), price=_money(8000),
    ).value
    res = Resource.create(**_valid_kwargs(
        operating_hours=_ws(slot=60, days={Weekday.MONDAY: [_w(8, 22)]}),
        pricing_rules=[rule],
    )).value

    new_dur = SlotDuration.create(45).value  # neither hours nor rule align
    r = res.set_slot_duration(new_dur)
    assert r.is_failure


def test_publish_unpublish_toggle():
    res = Resource.create(**_valid_kwargs()).value
    assert res.is_published is False
    res.publish()
    assert res.is_published is True
    res.unpublish()
    assert res.is_published is False


def test_soft_delete_sets_deleted_at():
    res = Resource.create(**_valid_kwargs()).value
    now = datetime(2026, 4, 26, 12, 0, 0, tzinfo=timezone.utc)
    r = res.soft_delete(now=now)
    assert r.is_success
    assert res.deleted_at == now
    assert res.is_deleted() is True


def test_soft_delete_already_deleted_returns_failure():
    res = Resource.create(**_valid_kwargs()).value
    now = datetime(2026, 4, 26, 12, 0, 0, tzinfo=timezone.utc)
    res.soft_delete(now=now)
    r = res.soft_delete(now=now)
    assert r.is_failure
    assert r.error == Resource.RESOURCE_ALREADY_DELETED


def test_soft_delete_naive_datetime_rejected():
    res = Resource.create(**_valid_kwargs()).value
    naive = datetime(2026, 4, 26, 12, 0, 0)
    r = res.soft_delete(now=naive)
    assert r.is_failure
    assert r.error == Resource.DELETED_AT_NOT_TZ_AWARE


from datetime import timedelta
from zoneinfo import ZoneInfo

from app.domain.shared.value_objects.date_time_range import DateTimeRange


def _utc(year, month, day, hour=0, minute=0):
    return datetime(year, month, day, hour, minute, tzinfo=timezone.utc)


def test_compute_price_falls_back_to_base():
    # No pricing rules → every slot uses base_price_cents.
    res = Resource.create(**_valid_kwargs(
        operating_hours=_ws(days={Weekday.MONDAY: [_w(8, 22)]}),
        base_price_cents=8000,
    )).value
    # Monday 2026-04-27 in São Paulo, 09:00-11:00 local = 12:00-14:00 UTC.
    sao_paulo = ZoneInfo("America/Sao_Paulo")
    start_local = datetime(2026, 4, 27, 9, 0, tzinfo=sao_paulo)
    end_local = datetime(2026, 4, 27, 11, 0, tzinfo=sao_paulo)
    rng = DateTimeRange.create(start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)).value
    total = res.compute_price(rng)
    assert total.cents == 8000 * 2  # 2 slots × R$ 80


def test_compute_price_uses_matching_rule():
    rule = PricingRule.create(
        weekdays=[Weekday.MONDAY],
        window=_w(18, 22),
        price=_money(12000),
    ).value
    res = Resource.create(**_valid_kwargs(
        operating_hours=_ws(days={Weekday.MONDAY: [_w(8, 22)]}),
        base_price_cents=8000,
        pricing_rules=[rule],
    )).value
    # Monday local 18:00-20:00 → 2 slots × R$ 120
    sao_paulo = ZoneInfo("America/Sao_Paulo")
    start_local = datetime(2026, 4, 27, 18, 0, tzinfo=sao_paulo)
    end_local = datetime(2026, 4, 27, 20, 0, tzinfo=sao_paulo)
    rng = DateTimeRange.create(start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)).value
    total = res.compute_price(rng)
    assert total.cents == 12000 * 2


def test_compute_price_mixed_rule_and_fallback():
    rule = PricingRule.create(
        weekdays=[Weekday.MONDAY],
        window=_w(18, 22),
        price=_money(12000),
    ).value
    res = Resource.create(**_valid_kwargs(
        operating_hours=_ws(days={Weekday.MONDAY: [_w(8, 22)]}),
        base_price_cents=8000,
        pricing_rules=[rule],
    )).value
    # Monday local 17:00-19:00 → slot 17 falls outside rule (rule starts 18) → base; slot 18 → rule.
    sao_paulo = ZoneInfo("America/Sao_Paulo")
    start_local = datetime(2026, 4, 27, 17, 0, tzinfo=sao_paulo)
    end_local = datetime(2026, 4, 27, 19, 0, tzinfo=sao_paulo)
    rng = DateTimeRange.create(start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)).value
    total = res.compute_price(rng)
    assert total.cents == 8000 + 12000
