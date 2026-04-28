from __future__ import annotations
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.domain.bookings.booking import Booking
from app.domain.bookings.booking_status import BookingStatus
from app.domain.shared.value_objects.date_time_range import DateTimeRange
from app.domain.shared.value_objects.money import Money
from app.use_cases.ratings.commands.create_rating import (
    CreateRatingCommand,
    CreateRatingHandler,
)
from tests.unit.use_cases.bookings.fakes.in_memory_booking_repository import (
    InMemoryBookingRepository,
)
from tests.unit.use_cases.ratings.fakes.in_memory_rating_repository import (
    InMemoryRatingRepository,
)


pytestmark = pytest.mark.asyncio


def _now() -> datetime:
    return datetime(2026, 4, 28, 12, 0, 0, tzinfo=timezone.utc)


def _build_approved_ended(*, customer_id, days_ago: int = 1) -> Booking:
    """Build a Booking that's APPROVED and whose slot ended `days_ago` ago."""
    end = _now() - timedelta(days=days_ago)
    start = end - timedelta(hours=1)
    sr = DateTimeRange.create(start_at=start, end_at=end).value
    b = Booking.create_pending(
        resource_id=uuid4(), customer_id=customer_id,
        slot_range=sr, total_price_cents=Money.create(8000).value,
        customer_note=None, now=_now() - timedelta(days=days_ago + 1),
    )
    b.approve(actor_id=uuid4(), now=_now() - timedelta(days=days_ago + 1))
    return b


async def test_happy_path_creates_rating():
    customer_id = uuid4()
    booking = _build_approved_ended(customer_id=customer_id)
    bookings = InMemoryBookingRepository()
    ratings = InMemoryRatingRepository()
    await bookings.add(booking)
    handler = CreateRatingHandler(
        ratings=ratings, bookings=bookings, clock=_now,
    )
    cmd = CreateRatingCommand(
        actor_id=customer_id, booking_id=booking.id,
        score=5, comment="excelente",
    )
    r = await handler.handle(cmd)
    assert r.is_success, r.error
    dto = r.value
    assert dto.score == 5
    assert dto.comment == "excelente"
    assert dto.booking_id == booking.id
    assert dto.customer_id == customer_id


async def test_creates_without_comment():
    customer_id = uuid4()
    booking = _build_approved_ended(customer_id=customer_id)
    bookings = InMemoryBookingRepository()
    ratings = InMemoryRatingRepository()
    await bookings.add(booking)
    handler = CreateRatingHandler(
        ratings=ratings, bookings=bookings, clock=_now,
    )
    r = await handler.handle(CreateRatingCommand(
        actor_id=customer_id, booking_id=booking.id, score=4, comment=None,
    ))
    assert r.is_success
    assert r.value.comment is None


async def test_unknown_booking_returns_404():
    handler = CreateRatingHandler(
        ratings=InMemoryRatingRepository(),
        bookings=InMemoryBookingRepository(),
        clock=_now,
    )
    r = await handler.handle(CreateRatingCommand(
        actor_id=uuid4(), booking_id=uuid4(), score=5, comment=None,
    ))
    assert r.is_failure
    assert r.error == "BookingNotFound"
    assert r.status_code == 404


async def test_other_customers_booking_rejected():
    real_customer = uuid4()
    booking = _build_approved_ended(customer_id=real_customer)
    bookings = InMemoryBookingRepository()
    ratings = InMemoryRatingRepository()
    await bookings.add(booking)
    handler = CreateRatingHandler(
        ratings=ratings, bookings=bookings, clock=_now,
    )
    r = await handler.handle(CreateRatingCommand(
        actor_id=uuid4(),  # not real_customer
        booking_id=booking.id, score=5, comment=None,
    ))
    assert r.is_failure
    assert r.error == "BookingNotEligibleForRating"
    assert r.status_code == 422


async def test_pending_booking_rejected():
    customer_id = uuid4()
    end = _now() - timedelta(days=1)
    start = end - timedelta(hours=1)
    sr = DateTimeRange.create(start_at=start, end_at=end).value
    pending = Booking.create_pending(
        resource_id=uuid4(), customer_id=customer_id,
        slot_range=sr, total_price_cents=Money.create(8000).value,
        customer_note=None, now=_now() - timedelta(days=2),
    )
    bookings = InMemoryBookingRepository()
    ratings = InMemoryRatingRepository()
    await bookings.add(pending)
    handler = CreateRatingHandler(
        ratings=ratings, bookings=bookings, clock=_now,
    )
    r = await handler.handle(CreateRatingCommand(
        actor_id=customer_id, booking_id=pending.id, score=5, comment=None,
    ))
    assert r.is_failure
    assert r.error == "BookingNotEligibleForRating"


async def test_future_slot_rejected():
    """APPROVED but slot end is still in the future → ineligible."""
    customer_id = uuid4()
    end = _now() + timedelta(hours=1)
    start = _now()
    sr = DateTimeRange.create(start_at=start, end_at=end).value
    booking = Booking.create_pending(
        resource_id=uuid4(), customer_id=customer_id,
        slot_range=sr, total_price_cents=Money.create(8000).value,
        customer_note=None, now=_now(),
    )
    booking.approve(actor_id=uuid4(), now=_now())
    bookings = InMemoryBookingRepository()
    ratings = InMemoryRatingRepository()
    await bookings.add(booking)
    handler = CreateRatingHandler(
        ratings=ratings, bookings=bookings, clock=_now,
    )
    r = await handler.handle(CreateRatingCommand(
        actor_id=customer_id, booking_id=booking.id, score=5, comment=None,
    ))
    assert r.is_failure
    assert r.error == "BookingNotEligibleForRating"


async def test_past_90day_window_rejected():
    customer_id = uuid4()
    booking = _build_approved_ended(customer_id=customer_id, days_ago=91)
    bookings = InMemoryBookingRepository()
    ratings = InMemoryRatingRepository()
    await bookings.add(booking)
    handler = CreateRatingHandler(
        ratings=ratings, bookings=bookings, clock=_now,
    )
    r = await handler.handle(CreateRatingCommand(
        actor_id=customer_id, booking_id=booking.id, score=5, comment=None,
    ))
    assert r.is_failure
    assert r.error == "BookingNotEligibleForRating"


async def test_existing_rating_returns_409():
    customer_id = uuid4()
    booking = _build_approved_ended(customer_id=customer_id)
    bookings = InMemoryBookingRepository()
    ratings = InMemoryRatingRepository()
    await bookings.add(booking)
    handler = CreateRatingHandler(
        ratings=ratings, bookings=bookings, clock=_now,
    )
    cmd = CreateRatingCommand(
        actor_id=customer_id, booking_id=booking.id, score=5, comment=None,
    )
    first = await handler.handle(cmd)
    assert first.is_success
    second = await handler.handle(cmd)
    assert second.is_failure
    assert second.error == "RatingAlreadyExists"
    assert second.status_code == 409


async def test_invalid_score_returns_422():
    customer_id = uuid4()
    booking = _build_approved_ended(customer_id=customer_id)
    bookings = InMemoryBookingRepository()
    ratings = InMemoryRatingRepository()
    await bookings.add(booking)
    handler = CreateRatingHandler(
        ratings=ratings, bookings=bookings, clock=_now,
    )
    r = await handler.handle(CreateRatingCommand(
        actor_id=customer_id, booking_id=booking.id, score=0, comment=None,
    ))
    assert r.is_failure
    assert r.status_code == 422
