from __future__ import annotations
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.domain.bookings.booking import Booking
from app.domain.shared.value_objects.date_time_range import DateTimeRange
from app.domain.shared.value_objects.money import Money
from app.use_cases.bookings.queries.get_my_booking import (
    GetMyBookingHandler,
    GetMyBookingQuery,
)
from tests.unit.use_cases.bookings.fakes.in_memory_booking_repository import (
    InMemoryBookingRepository,
)


pytestmark = pytest.mark.asyncio


def _now() -> datetime:
    return datetime(2026, 4, 27, 12, 0, 0, tzinfo=timezone.utc)


def _booking(*, customer_id) -> Booking:
    sr = DateTimeRange.create(
        start_at=_now() + timedelta(days=1),
        end_at=_now() + timedelta(days=1, hours=1),
    ).value
    return Booking.create_pending(
        resource_id=uuid4(), customer_id=customer_id, slot_range=sr,
        total_price_cents=Money.create(8000).value,
        customer_note=None, now=_now(),
    )


async def test_returns_my_own_booking():
    repo = InMemoryBookingRepository()
    me = uuid4()
    b = _booking(customer_id=me)
    await repo.add(b)
    handler = GetMyBookingHandler(bookings=repo)
    r = await handler.handle(GetMyBookingQuery(actor_id=me, booking_id=b.id))
    assert r.is_success
    assert r.value.id == b.id


async def test_cross_customer_returns_404():
    repo = InMemoryBookingRepository()
    owner_of_booking = uuid4()
    intruder = uuid4()
    b = _booking(customer_id=owner_of_booking)
    await repo.add(b)
    handler = GetMyBookingHandler(bookings=repo)
    r = await handler.handle(GetMyBookingQuery(
        actor_id=intruder, booking_id=b.id,
    ))
    assert r.is_failure
    assert r.error == "BookingNotFound"
    assert r.status_code == 404


async def test_unknown_id_returns_404():
    repo = InMemoryBookingRepository()
    handler = GetMyBookingHandler(bookings=repo)
    r = await handler.handle(GetMyBookingQuery(
        actor_id=uuid4(), booking_id=uuid4(),
    ))
    assert r.is_failure
    assert r.error == "BookingNotFound"
