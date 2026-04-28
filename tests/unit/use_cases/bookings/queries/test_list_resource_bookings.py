from __future__ import annotations
from datetime import datetime, time, timedelta, timezone
from uuid import uuid4

import pytest

from app.domain.bookings.booking import Booking
from app.domain.bookings.booking_status import BookingStatus
from app.domain.resources.resource import Resource
from app.domain.resources.weekly_schedule import WeeklySchedule
from app.domain.shared.value_objects.date_time_range import DateTimeRange
from app.domain.shared.value_objects.money import Money
from app.domain.shared.value_objects.time_window import TimeWindow
from app.domain.shared.weekday import Weekday
from app.use_cases.bookings.queries.list_resource_bookings import (
    ListResourceBookingsHandler,
    ListResourceBookingsQuery,
)
from tests.unit.use_cases.bookings.fakes.in_memory_booking_repository import (
    InMemoryBookingRepository,
)


pytestmark = pytest.mark.asyncio


def _now() -> datetime:
    return datetime(2026, 4, 27, 12, 0, 0, tzinfo=timezone.utc)


def _build_resource(*, owner_id) -> Resource:
    # ADAPT: use time(...) and WeeklySchedule wrapper
    operating = {wd: [TimeWindow.create(time(6, 0), time(22, 0)).value] for wd in Weekday}
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
        operating_hours=schedule, pricing_rules=[],
        custom_attributes=[], base_attributes={},
    ).value
    r.publish()
    return r


def _booking(*, resource_id) -> Booking:
    sr = DateTimeRange.create(
        start_at=_now() + timedelta(days=1),
        end_at=_now() + timedelta(days=1, hours=1),
    ).value
    return Booking.create_pending(
        resource_id=resource_id, customer_id=uuid4(),
        slot_range=sr, total_price_cents=Money.create(8000).value,
        customer_note=None, now=_now(),
    )


class _FakeResourceRepo:
    # ADAPT: returns Resource | None directly, not Result
    def __init__(self, resources):
        self._by_id = {r.id: r for r in resources}

    async def get_by_id(self, rid):
        return self._by_id.get(rid)


async def test_returns_bookings_for_my_resource():
    owner_id = uuid4()
    res = _build_resource(owner_id=owner_id)
    repo = InMemoryBookingRepository()
    b1 = _booking(resource_id=res.id)
    b2 = _booking(resource_id=res.id)
    other = _booking(resource_id=uuid4())
    await repo.add(b1)
    await repo.add(b2)
    await repo.add(other)
    handler = ListResourceBookingsHandler(
        bookings=repo, resources=_FakeResourceRepo([res]),
    )
    r = await handler.handle(ListResourceBookingsQuery(
        actor_id=owner_id, resource_id=res.id,
    ))
    assert r.is_success
    ids = {b.id for b in r.value.items}
    assert ids == {b1.id, b2.id}


async def test_non_owner_returns_404():
    res = _build_resource(owner_id=uuid4())
    handler = ListResourceBookingsHandler(
        bookings=InMemoryBookingRepository(),
        resources=_FakeResourceRepo([res]),
    )
    r = await handler.handle(ListResourceBookingsQuery(
        actor_id=uuid4(), resource_id=res.id,
    ))
    assert r.is_failure
    assert r.error == "ResourceNotFound"


async def test_status_filter():
    owner_id = uuid4()
    res = _build_resource(owner_id=owner_id)
    repo = InMemoryBookingRepository()
    pending = _booking(resource_id=res.id)
    approved = _booking(resource_id=res.id)
    approved.approve(actor_id=owner_id, now=_now())
    await repo.add(pending)
    await repo.add(approved)
    handler = ListResourceBookingsHandler(
        bookings=repo, resources=_FakeResourceRepo([res]),
    )
    r = await handler.handle(ListResourceBookingsQuery(
        actor_id=owner_id, resource_id=res.id,
        status=BookingStatus.APPROVED,
    ))
    assert r.is_success
    assert [b.id for b in r.value.items] == [approved.id]
