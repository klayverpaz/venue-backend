from __future__ import annotations
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.domain.bookings.booking import Booking
from app.domain.bookings.booking_status import BookingStatus
from app.domain.notifications.service import NotifKind
from app.domain.shared.value_objects.date_time_range import DateTimeRange
from app.domain.shared.value_objects.money import Money
from app.use_cases.bookings.commands.expire_pending_bookings import (
    ExpirePendingBookingsCommand,
    ExpirePendingBookingsHandler,
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


def _pending(*, resource_id, customer_id, slot_offset_hours: int) -> Booking:
    start = _now() + timedelta(hours=slot_offset_hours)
    end = start + timedelta(hours=1)
    return Booking.create_pending(
        resource_id=resource_id, customer_id=customer_id,
        slot_range=DateTimeRange.create(start_at=start, end_at=end).value,
        total_price_cents=Money.create(8000).value,
        customer_note=None,
        now=_now() - timedelta(days=1),
    )


async def test_expires_only_pendings_in_past():
    repo = InMemoryBookingRepository()
    notifs = FakeNotificationService()
    res_id = uuid4()
    past = _pending(resource_id=res_id, customer_id=uuid4(), slot_offset_hours=-2)
    future = _pending(resource_id=res_id, customer_id=uuid4(), slot_offset_hours=10)
    await repo.add(past)
    await repo.add(future)

    handler = ExpirePendingBookingsHandler(bookings=repo, notifications=notifs, clock=_now)
    r = await handler.handle(ExpirePendingBookingsCommand())
    assert r.is_success
    assert r.value == 1
    assert (await repo.get_by_id(past.id)).value.status is BookingStatus.EXPIRED
    assert (await repo.get_by_id(future.id)).value.status is BookingStatus.PENDING


async def test_already_expired_skipped_on_re_run():
    repo = InMemoryBookingRepository()
    notifs = FakeNotificationService()
    res_id = uuid4()
    past = _pending(resource_id=res_id, customer_id=uuid4(), slot_offset_hours=-2)
    await repo.add(past)
    handler = ExpirePendingBookingsHandler(bookings=repo, notifications=notifs, clock=_now)
    r1 = await handler.handle(ExpirePendingBookingsCommand())
    assert r1.value == 1
    # Second run: nothing more PENDING in past.
    r2 = await handler.handle(ExpirePendingBookingsCommand())
    assert r2.value == 0


async def test_each_expired_gets_rejected_notification():
    repo = InMemoryBookingRepository()
    notifs = FakeNotificationService()
    res_id = uuid4()
    cust_a = uuid4()
    cust_b = uuid4()
    await repo.add(_pending(resource_id=res_id, customer_id=cust_a, slot_offset_hours=-3))
    await repo.add(_pending(resource_id=res_id, customer_id=cust_b, slot_offset_hours=-2))
    handler = ExpirePendingBookingsHandler(bookings=repo, notifications=notifs, clock=_now)
    r = await handler.handle(ExpirePendingBookingsCommand())
    assert r.value == 2
    rejected = [c for c in notifs.calls if c[1] is NotifKind.BOOKING_REJECTED]
    assert len(rejected) == 2
    recipients = {c[0] for c in rejected}
    assert recipients == {cust_a, cust_b}
    for c in rejected:
        assert c[2]["reason"] == "slot_start_passed_with_no_decision"
