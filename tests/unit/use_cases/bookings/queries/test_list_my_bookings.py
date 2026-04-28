from __future__ import annotations
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.domain.bookings.booking import Booking
from app.domain.bookings.booking_status import BookingStatus
from app.domain.shared.value_objects.date_time_range import DateTimeRange
from app.domain.shared.value_objects.money import Money
from app.use_cases.bookings.queries.list_my_bookings import (
    ListMyBookingsHandler,
    ListMyBookingsQuery,
)
from tests.unit.use_cases.bookings.fakes.in_memory_booking_repository import (
    InMemoryBookingRepository,
)


pytestmark = pytest.mark.asyncio


def _now() -> datetime:
    return datetime(2026, 4, 27, 12, 0, 0, tzinfo=timezone.utc)


def _booking(*, customer_id, status: BookingStatus = BookingStatus.PENDING) -> Booking:
    sr = DateTimeRange.create(
        start_at=_now() + timedelta(days=1),
        end_at=_now() + timedelta(days=1, hours=1),
    ).value
    b = Booking.create_pending(
        resource_id=uuid4(), customer_id=customer_id, slot_range=sr,
        total_price_cents=Money.create(8000).value,
        customer_note=None, now=_now(),
    )
    if status is BookingStatus.APPROVED:
        b.approve(actor_id=uuid4(), now=_now())
    elif status is BookingStatus.CANCELLED:
        from app.domain.accounts.role import Role
        b.cancel(actor_id=customer_id, actor_role=Role.CUSTOMER, now=_now())
    return b


async def test_returns_only_my_bookings():
    repo = InMemoryBookingRepository()
    me = uuid4()
    other = uuid4()
    mine = _booking(customer_id=me)
    theirs = _booking(customer_id=other)
    await repo.add(mine)
    await repo.add(theirs)
    handler = ListMyBookingsHandler(bookings=repo)

    r = await handler.handle(ListMyBookingsQuery(actor_id=me))
    assert r.is_success
    ids = [b.id for b in r.value.items]
    assert ids == [mine.id]


async def test_filters_by_status():
    repo = InMemoryBookingRepository()
    me = uuid4()
    p = _booking(customer_id=me, status=BookingStatus.PENDING)
    a = _booking(customer_id=me, status=BookingStatus.APPROVED)
    await repo.add(p)
    await repo.add(a)
    handler = ListMyBookingsHandler(bookings=repo)
    r = await handler.handle(ListMyBookingsQuery(
        actor_id=me, status=BookingStatus.APPROVED,
    ))
    assert r.is_success
    assert [b.id for b in r.value.items] == [a.id]


async def test_clamps_page_size_to_100():
    repo = InMemoryBookingRepository()
    me = uuid4()
    for _ in range(5):
        await repo.add(_booking(customer_id=me))
    handler = ListMyBookingsHandler(bookings=repo)
    r = await handler.handle(ListMyBookingsQuery(actor_id=me, page_size=500))
    assert r.is_success
    assert r.value.page_size == 100


async def test_clamps_page_min_1():
    repo = InMemoryBookingRepository()
    handler = ListMyBookingsHandler(bookings=repo)
    r = await handler.handle(ListMyBookingsQuery(actor_id=uuid4(), page=0))
    assert r.is_success
    assert r.value.page == 1
