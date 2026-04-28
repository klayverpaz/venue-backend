from __future__ import annotations
from datetime import datetime, time, timedelta, timezone
from uuid import uuid4

import pytest

from app.domain.bookings.booking_status import BookingStatus
from app.domain.notifications.service import NotifKind
from app.domain.resources.pricing_rule import PricingRule
from app.domain.resources.resource import Resource
from app.domain.resources.weekly_schedule import WeeklySchedule
from app.domain.shared.value_objects.money import Money
from app.domain.shared.value_objects.time_window import TimeWindow
from app.domain.shared.weekday import Weekday
from app.domain.subscriptions.owner_subscription import OwnerSubscription
from app.domain.subscriptions.sub_status import SubStatus
from app.use_cases.bookings.commands.request_booking import (
    RequestBookingCommand,
    RequestBookingHandler,
)
from tests.unit.use_cases.bookings.fakes.in_memory_booking_repository import (
    InMemoryBookingRepository,
)
from tests.unit.use_cases.subscriptions.fakes.fake_notification_service import (
    FakeNotificationService,
)


pytestmark = pytest.mark.asyncio


def _now() -> datetime:
    # 2026-04-27 12:00 UTC = 09:00 São Paulo on a Monday.
    return datetime(2026, 4, 27, 12, 0, 0, tzinfo=timezone.utc)


def _w(sh: int, eh: int) -> TimeWindow:
    return TimeWindow.create(time(sh, 0), time(eh, 0)).value


def _build_resource(
    *, owner_id, is_published: bool = True, deleted: bool = False,
) -> Resource:
    operating = {
        wd: [_w(6, 22)]
        for wd in Weekday
    }
    schedule = WeeklySchedule.create(
        slot_duration_minutes=60,
        days=operating,
    ).value
    r = Resource.create(
        owner_id=owner_id, resource_type_id=uuid4(),
        slug="campo", name="Campo", description="",
        city="SP", region="SP", timezone="America/Sao_Paulo",
        slot_duration_minutes=60, base_price_cents=8000,
        customer_cancellation_cutoff_hours=24,
        operating_hours=schedule,
        pricing_rules=[], custom_attributes=[], base_attributes={},
    ).value
    if is_published:
        r.publish()
    if deleted:
        r.soft_delete(now=_now() - timedelta(days=1))
    return r


def _local_slot(*, day: int = 28, hour_local: int = 14, hours: int = 1) -> tuple[datetime, datetime]:
    """Build a (start_utc, end_utc) tuple anchored at hour_local in São Paulo."""
    start_utc = datetime(2026, 4, day, hour_local + 3, 0, 0, tzinfo=timezone.utc)
    end_utc = start_utc + timedelta(hours=hours)
    return start_utc, end_utc


class _FakeResourceRepo:
    """Mimics IResourceRepository.get_by_id which returns Resource | None."""

    def __init__(self, resources: list[Resource]):
        self._by_id = {r.id: r for r in resources}

    async def get_by_id(self, rid):
        return self._by_id.get(rid)


class _FakeSubRepo:
    def __init__(self, sub: OwnerSubscription | None):
        self._sub = sub

    async def get_by_owner_id(self, owner_id):
        return self._sub if self._sub and self._sub.owner_id == owner_id else None


def _make_active_sub(owner_id) -> OwnerSubscription:
    return OwnerSubscription.create_trialing(
        owner_id=owner_id, trial_duration_days=3, now=_now(),
    ).value


def _make_inactive_sub(owner_id) -> OwnerSubscription:
    sub = _make_active_sub(owner_id)
    sub.transition_to(SubStatus.INACTIVE, now=_now(), trial_duration_days=3)
    return sub


async def _build_handler(
    *,
    resource: Resource,
    sub: OwnerSubscription | None = None,
) -> tuple[RequestBookingHandler, InMemoryBookingRepository, FakeNotificationService]:
    bookings = InMemoryBookingRepository()
    notifs = FakeNotificationService()
    handler = RequestBookingHandler(
        bookings=bookings,
        resources=_FakeResourceRepo([resource]),
        subscriptions=_FakeSubRepo(sub or _make_active_sub(resource.owner_id)),
        notifications=notifs,
        clock=_now,
    )
    return handler, bookings, notifs


async def test_happy_path_creates_pending_and_notifies_owner():
    owner_id = uuid4()
    res = _build_resource(owner_id=owner_id)
    handler, bookings, notifs = await _build_handler(resource=res)
    start, end = _local_slot(day=28, hour_local=14, hours=2)
    cmd = RequestBookingCommand(
        actor_id=uuid4(), resource_id=res.id,
        slot_start_at=start, slot_end_at=end, customer_note=None,
    )
    r = await handler.handle(cmd)
    assert r.is_success, r.error
    dto = r.value
    assert dto.status == "PENDING"
    assert dto.total_price_cents == 16000  # 2 slots × 8000
    assert len(bookings._rows) == 1
    # Owner notified.
    assert any(
        c[1] is NotifKind.BOOKING_REQUESTED and c[0] == owner_id
        for c in notifs.calls
    )


async def test_resource_not_found_returns_404():
    res = _build_resource(owner_id=uuid4())
    handler, _, _ = await _build_handler(resource=res)
    start, end = _local_slot()
    cmd = RequestBookingCommand(
        actor_id=uuid4(), resource_id=uuid4(),
        slot_start_at=start, slot_end_at=end, customer_note=None,
    )
    r = await handler.handle(cmd)
    assert r.is_failure
    assert r.error == "ResourceNotFound"
    assert r.status_code == 404


async def test_unpublished_resource_returns_404_resource_not_published():
    res = _build_resource(owner_id=uuid4(), is_published=False)
    handler, _, _ = await _build_handler(resource=res)
    start, end = _local_slot()
    cmd = RequestBookingCommand(
        actor_id=uuid4(), resource_id=res.id,
        slot_start_at=start, slot_end_at=end, customer_note=None,
    )
    r = await handler.handle(cmd)
    assert r.is_failure
    assert r.error == "ResourceNotPublished"


async def test_inactive_owner_subscription_returns_404_resource_not_published():
    owner_id = uuid4()
    res = _build_resource(owner_id=owner_id)
    handler, _, _ = await _build_handler(
        resource=res, sub=_make_inactive_sub(owner_id),
    )
    start, end = _local_slot()
    cmd = RequestBookingCommand(
        actor_id=uuid4(), resource_id=res.id,
        slot_start_at=start, slot_end_at=end, customer_note=None,
    )
    r = await handler.handle(cmd)
    assert r.is_failure
    # Same code as unpublished — don't reveal owner state to the customer.
    assert r.error == "ResourceNotPublished"


async def test_slot_in_past_returns_422():
    res = _build_resource(owner_id=uuid4())
    handler, _, _ = await _build_handler(resource=res)
    start = _now() - timedelta(hours=1)
    end = _now()
    cmd = RequestBookingCommand(
        actor_id=uuid4(), resource_id=res.id,
        slot_start_at=start, slot_end_at=end, customer_note=None,
    )
    r = await handler.handle(cmd)
    assert r.is_failure
    assert r.error == "BookingSlotInPast"


async def test_slot_not_aligned_returns_422():
    res = _build_resource(owner_id=uuid4())  # 60-min slots
    handler, _, _ = await _build_handler(resource=res)
    start, _ = _local_slot(day=28, hour_local=14)
    # Off-grid: 14:30-15:30 local.
    bad_start = start + timedelta(minutes=30)
    bad_end = bad_start + timedelta(hours=1)
    cmd = RequestBookingCommand(
        actor_id=uuid4(), resource_id=res.id,
        slot_start_at=bad_start, slot_end_at=bad_end, customer_note=None,
    )
    r = await handler.handle(cmd)
    assert r.is_failure
    assert r.error == "BookingSlotNotAligned"


async def test_slot_outside_operating_hours_returns_422():
    res = _build_resource(owner_id=uuid4())  # 06:00-22:00
    handler, _, _ = await _build_handler(resource=res)
    # 02:00-03:00 local — closed.
    start, end = _local_slot(day=28, hour_local=2, hours=1)
    cmd = RequestBookingCommand(
        actor_id=uuid4(), resource_id=res.id,
        slot_start_at=start, slot_end_at=end, customer_note=None,
    )
    r = await handler.handle(cmd)
    assert r.is_failure
    assert r.error == "BookingOutsideOperatingHours"


async def test_natural_dedup_returns_409():
    res = _build_resource(owner_id=uuid4())
    handler, _, _ = await _build_handler(resource=res)
    customer_id = uuid4()
    start, end = _local_slot(day=28, hour_local=14, hours=2)
    cmd = RequestBookingCommand(
        actor_id=customer_id, resource_id=res.id,
        slot_start_at=start, slot_end_at=end, customer_note=None,
    )
    first = await handler.handle(cmd)
    assert first.is_success
    # Same customer requests same slot again.
    second = await handler.handle(cmd)
    assert second.is_failure
    assert second.error == "BookingAlreadyExists"
    assert second.status_code == 409


async def test_two_customers_same_slot_both_pend():
    res = _build_resource(owner_id=uuid4())
    handler, bookings, _ = await _build_handler(resource=res)
    start, end = _local_slot(day=28, hour_local=14, hours=2)
    cmd1 = RequestBookingCommand(
        actor_id=uuid4(), resource_id=res.id,
        slot_start_at=start, slot_end_at=end, customer_note=None,
    )
    cmd2 = RequestBookingCommand(
        actor_id=uuid4(), resource_id=res.id,
        slot_start_at=start, slot_end_at=end, customer_note=None,
    )
    r1 = await handler.handle(cmd1)
    r2 = await handler.handle(cmd2)
    assert r1.is_success and r2.is_success
    assert len(bookings._rows) == 2


async def test_pricing_rule_applied():
    owner_id = uuid4()
    res = _build_resource(owner_id=owner_id)
    rule = PricingRule.create(
        weekdays={Weekday.TUESDAY},
        window=_w(14, 16),
        price=Money.create(20000).value,
    ).value
    res.replace_pricing_rules([rule])
    handler, _, _ = await _build_handler(resource=res)
    # 2026-04-28 is a Tuesday. 14:00-16:00 local = rule.
    start, end = _local_slot(day=28, hour_local=14, hours=2)
    cmd = RequestBookingCommand(
        actor_id=uuid4(), resource_id=res.id,
        slot_start_at=start, slot_end_at=end, customer_note=None,
    )
    r = await handler.handle(cmd)
    assert r.is_success
    assert r.value.total_price_cents == 40000  # 2 × 20000
