from __future__ import annotations
from datetime import datetime, time, timedelta, timezone
from uuid import uuid4

import pytest

from app.domain.bookings.booking import Booking
from app.domain.bookings.booking_status import BookingStatus
from app.domain.notifications.service import NotifKind
from app.domain.resources.resource import Resource
from app.domain.resources.weekly_schedule import WeeklySchedule
from app.domain.shared.value_objects.date_time_range import DateTimeRange
from app.domain.shared.value_objects.money import Money
from app.domain.shared.value_objects.time_window import TimeWindow
from app.domain.shared.weekday import Weekday
from app.domain.subscriptions.owner_subscription import OwnerSubscription
from app.domain.subscriptions.sub_status import SubStatus
from app.use_cases.bookings.commands.approve_booking import (
    ApproveBookingCommand,
    ApproveBookingHandler,
)
from tests.unit.use_cases.bookings.fakes.in_memory_booking_repository import (
    InMemoryBookingRepository,
)
from tests.unit.use_cases.bookings.fakes.fake_booking_lock_service import (
    FakeBookingLockService,
)
from tests.unit.use_cases.subscriptions.fakes.fake_notification_service import (
    FakeNotificationService,
)


pytestmark = pytest.mark.asyncio


def _now() -> datetime:
    return datetime(2026, 4, 27, 12, 0, 0, tzinfo=timezone.utc)


def _w(sh: int, eh: int) -> TimeWindow:
    return TimeWindow.create(time(sh, 0), time(eh, 0)).value


def _build_resource(*, owner_id) -> Resource:
    operating = {wd: [_w(6, 22)] for wd in Weekday}
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
    r.publish()
    return r


def _build_pending(*, resource_id, customer_id, days_ahead=1, hours=1) -> Booking:
    sr = DateTimeRange.create(
        start_at=_now() + timedelta(days=days_ahead),
        end_at=_now() + timedelta(days=days_ahead, hours=hours),
    ).value
    return Booking.create_pending(
        resource_id=resource_id, customer_id=customer_id, slot_range=sr,
        total_price_cents=Money.create(8000).value, customer_note=None, now=_now(),
    )


class _FakeResourceRepo:
    """Mimics IResourceRepository.get_by_id which returns Resource | None."""

    def __init__(self, resources):
        self._by_id = {r.id: r for r in resources}

    async def get_by_id(self, rid):
        return self._by_id.get(rid)


class _FakeSubRepo:
    def __init__(self, sub):
        self._sub = sub

    async def get_by_owner_id(self, owner_id):
        return self._sub if (self._sub and self._sub.owner_id == owner_id) else None


def _active(owner_id):
    sub = OwnerSubscription.create_trialing(
        owner_id=owner_id, trial_duration_days=3, now=_now(),
    ).value
    return sub


def _inactive(owner_id):
    sub = _active(owner_id)
    sub.transition_to(SubStatus.INACTIVE, now=_now(), trial_duration_days=3)
    return sub


async def _build_handler(*, resource, sub=None):
    bookings = InMemoryBookingRepository()
    notifs = FakeNotificationService()
    handler = ApproveBookingHandler(
        bookings=bookings,
        resources=_FakeResourceRepo([resource]),
        subscriptions=_FakeSubRepo(sub or _active(resource.owner_id)),
        notifications=notifs,
        lock=FakeBookingLockService(),
    )
    return handler, bookings, notifs


async def test_approves_pending_and_notifies_customer():
    owner_id = uuid4()
    res = _build_resource(owner_id=owner_id)
    customer_id = uuid4()
    booking = _build_pending(resource_id=res.id, customer_id=customer_id)
    handler, bookings, notifs = await _build_handler(resource=res)
    await bookings.add(booking)

    cmd = ApproveBookingCommand(actor_id=owner_id, booking_id=booking.id)
    r = await handler.handle(cmd)
    assert r.is_success
    assert r.value.status == "APPROVED"
    refetched = (await bookings.get_by_id(booking.id)).value
    assert refetched.status is BookingStatus.APPROVED
    assert any(
        c[1] is NotifKind.BOOKING_APPROVED and c[0] == customer_id
        for c in notifs.calls
    )


async def test_auto_rejects_overlapping_pendings():
    owner_id = uuid4()
    res = _build_resource(owner_id=owner_id)
    cust_a, cust_b, cust_c = uuid4(), uuid4(), uuid4()
    target = _build_pending(resource_id=res.id, customer_id=cust_a, days_ahead=1, hours=2)
    overlap1 = Booking.create_pending(
        resource_id=res.id, customer_id=cust_b,
        slot_range=DateTimeRange.create(
            start_at=target.slot_range.start_at + timedelta(minutes=30),
            end_at=target.slot_range.end_at + timedelta(minutes=30),
        ).value,
        total_price_cents=Money.create(8000).value,
        customer_note=None, now=_now(),
    )
    disjoint = _build_pending(resource_id=res.id, customer_id=cust_c, days_ahead=5)
    handler, bookings, notifs = await _build_handler(resource=res)
    await bookings.add(target)
    await bookings.add(overlap1)
    await bookings.add(disjoint)

    cmd = ApproveBookingCommand(actor_id=owner_id, booking_id=target.id)
    r = await handler.handle(cmd)
    assert r.is_success
    assert (await bookings.get_by_id(target.id)).value.status is BookingStatus.APPROVED
    assert (await bookings.get_by_id(overlap1.id)).value.status is BookingStatus.REJECTED
    assert (await bookings.get_by_id(disjoint.id)).value.status is BookingStatus.PENDING

    # Approved customer + 1 rejected competitor get notified.
    rejection_notifs = [c for c in notifs.calls if c[1] is NotifKind.BOOKING_REJECTED]
    assert len(rejection_notifs) == 1
    assert rejection_notifs[0][0] == cust_b
    assert rejection_notifs[0][2]["reason"] == "auto_rejected_competing_request"


async def test_inactive_owner_returns_403():
    owner_id = uuid4()
    res = _build_resource(owner_id=owner_id)
    booking = _build_pending(resource_id=res.id, customer_id=uuid4())
    handler, bookings, _ = await _build_handler(
        resource=res, sub=_inactive(owner_id),
    )
    await bookings.add(booking)
    cmd = ApproveBookingCommand(actor_id=owner_id, booking_id=booking.id)
    r = await handler.handle(cmd)
    assert r.is_failure
    assert r.error == "OwnerSubscriptionInactive"
    assert r.status_code == 403


async def test_non_owner_returns_404():
    owner_id = uuid4()
    res = _build_resource(owner_id=owner_id)
    booking = _build_pending(resource_id=res.id, customer_id=uuid4())
    handler, bookings, _ = await _build_handler(resource=res)
    await bookings.add(booking)
    cmd = ApproveBookingCommand(actor_id=uuid4(), booking_id=booking.id)
    r = await handler.handle(cmd)
    assert r.is_failure
    assert r.error == "BookingNotFound"
    assert r.status_code == 404


async def test_already_approved_returns_409():
    owner_id = uuid4()
    res = _build_resource(owner_id=owner_id)
    booking = _build_pending(resource_id=res.id, customer_id=uuid4())
    booking.approve(actor_id=owner_id, now=_now())
    handler, bookings, _ = await _build_handler(resource=res)
    await bookings.add(booking)
    cmd = ApproveBookingCommand(actor_id=owner_id, booking_id=booking.id)
    r = await handler.handle(cmd)
    assert r.is_failure
    assert r.error == "BookingInvalidStateTransition"
    assert r.status_code == 409


async def test_unknown_booking_returns_404():
    res = _build_resource(owner_id=uuid4())
    handler, _, _ = await _build_handler(resource=res)
    cmd = ApproveBookingCommand(actor_id=uuid4(), booking_id=uuid4())
    r = await handler.handle(cmd)
    assert r.is_failure
    assert r.error == "BookingNotFound"
