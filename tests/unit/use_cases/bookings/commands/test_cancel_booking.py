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
from app.use_cases.bookings.commands.cancel_booking import (
    CancelBookingCommand,
    CancelBookingHandler,
)
from tests.unit.use_cases.bookings.fakes.in_memory_booking_repository import (
    InMemoryBookingRepository,
)
from tests.unit.use_cases.subscriptions.fakes.fake_notification_service import (
    FakeNotificationService,
)


pytestmark = pytest.mark.asyncio


def _now() -> datetime:
    return datetime(2026, 4, 27, 12, 0, 0, tzinfo=timezone.utc)


def _w(sh: int, eh: int) -> TimeWindow:
    return TimeWindow.create(time(sh, 0), time(eh, 0)).value


def _build_resource(*, owner_id, cutoff_hours: int = 24) -> Resource:
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
        customer_cancellation_cutoff_hours=cutoff_hours,
        operating_hours=schedule, pricing_rules=[],
        custom_attributes=[], base_attributes={},
    ).value
    r.publish()
    return r


def _build_pending(*, resource_id, customer_id, days_ahead=2) -> Booking:
    sr = DateTimeRange.create(
        start_at=_now() + timedelta(days=days_ahead),
        end_at=_now() + timedelta(days=days_ahead, hours=1),
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


async def _build_handler(*, resource):
    bookings = InMemoryBookingRepository()
    notifs = FakeNotificationService()
    return (
        CancelBookingHandler(
            bookings=bookings,
            resources=_FakeResourceRepo([resource]),
            notifications=notifs,
        ),
        bookings, notifs,
    )


async def test_customer_cancels_pending_within_cutoff_notifies_owner():
    owner_id = uuid4()
    res = _build_resource(owner_id=owner_id, cutoff_hours=24)
    customer_id = uuid4()
    b = _build_pending(resource_id=res.id, customer_id=customer_id, days_ahead=2)
    handler, bookings, notifs = await _build_handler(resource=res)
    await bookings.add(b)
    cmd = CancelBookingCommand(
        actor_id=customer_id, booking_id=b.id, reason=None,
    )
    r = await handler.handle(cmd)
    assert r.is_success
    assert r.value.status == "CANCELLED"
    # Owner gets the cancellation notification.
    assert any(
        c[0] == owner_id and c[1] is NotifKind.BOOKING_CANCELLED
        for c in notifs.calls
    )


async def test_customer_cancels_past_cutoff_returns_403():
    owner_id = uuid4()
    res = _build_resource(owner_id=owner_id, cutoff_hours=24)
    customer_id = uuid4()
    # Booking starts in 10 hours (past 24h cutoff).
    sr = DateTimeRange.create(
        start_at=_now() + timedelta(hours=10),
        end_at=_now() + timedelta(hours=11),
    ).value
    b = Booking.create_pending(
        resource_id=res.id, customer_id=customer_id, slot_range=sr,
        total_price_cents=Money.create(8000).value, customer_note=None, now=_now(),
    )
    handler, bookings, _ = await _build_handler(resource=res)
    await bookings.add(b)
    cmd = CancelBookingCommand(
        actor_id=customer_id, booking_id=b.id, reason=None,
    )
    r = await handler.handle(cmd)
    assert r.is_failure
    assert r.error == "BookingCancellationPastCutoff"
    assert r.status_code == 403


async def test_owner_cancels_approved_anytime_no_cutoff():
    owner_id = uuid4()
    res = _build_resource(owner_id=owner_id, cutoff_hours=24)
    customer_id = uuid4()
    sr = DateTimeRange.create(
        start_at=_now() + timedelta(hours=10),
        end_at=_now() + timedelta(hours=11),
    ).value
    b = Booking.create_pending(
        resource_id=res.id, customer_id=customer_id, slot_range=sr,
        total_price_cents=Money.create(8000).value, customer_note=None, now=_now(),
    )
    b.approve(actor_id=owner_id, now=_now())
    handler, bookings, notifs = await _build_handler(resource=res)
    await bookings.add(b)
    cmd = CancelBookingCommand(
        actor_id=owner_id, booking_id=b.id, reason="storm",
    )
    r = await handler.handle(cmd)
    assert r.is_success
    assert r.value.status == "CANCELLED"
    # Customer gets notified; payload has cancelled_by=owner.
    cancelled = [c for c in notifs.calls if c[1] is NotifKind.BOOKING_CANCELLED]
    assert len(cancelled) == 1
    assert cancelled[0][0] == customer_id
    assert cancelled[0][2]["cancelled_by"] == "owner"


async def test_third_party_cannot_cancel_returns_404():
    owner_id = uuid4()
    res = _build_resource(owner_id=owner_id)
    b = _build_pending(resource_id=res.id, customer_id=uuid4())
    handler, bookings, _ = await _build_handler(resource=res)
    await bookings.add(b)
    cmd = CancelBookingCommand(
        actor_id=uuid4(), booking_id=b.id, reason=None,
    )
    r = await handler.handle(cmd)
    assert r.is_failure
    assert r.error == "BookingNotFound"


async def test_double_cancel_returns_409():
    owner_id = uuid4()
    res = _build_resource(owner_id=owner_id)
    customer_id = uuid4()
    b = _build_pending(resource_id=res.id, customer_id=customer_id)
    from app.domain.accounts.role import Role
    b.cancel(actor_id=customer_id, actor_role=Role.CUSTOMER, now=_now())
    handler, bookings, _ = await _build_handler(resource=res)
    await bookings.add(b)
    cmd = CancelBookingCommand(
        actor_id=customer_id, booking_id=b.id, reason=None,
    )
    r = await handler.handle(cmd)
    assert r.is_failure
    assert r.error == "BookingInvalidStateTransition"
