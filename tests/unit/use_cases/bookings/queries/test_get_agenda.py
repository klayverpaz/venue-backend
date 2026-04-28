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
from app.use_cases.bookings.queries.get_agenda import (
    GetAgendaHandler,
    GetAgendaQuery,
)
from tests.unit.use_cases.bookings.fakes.in_memory_booking_repository import (
    InMemoryBookingRepository,
)


pytestmark = pytest.mark.asyncio


def _now() -> datetime:
    return datetime(2026, 4, 27, 12, 0, 0, tzinfo=timezone.utc)


def _build_resource(*, owner_id, slot_minutes: int = 60) -> Resource:
    operating = {
        wd: [TimeWindow.create(time(6, 0), time(22, 0)).value]
        for wd in Weekday
    }
    schedule = WeeklySchedule.create(
        slot_duration_minutes=slot_minutes,
        days=operating,
    ).value
    r = Resource.create(
        owner_id=owner_id, resource_type_id=uuid4(),
        slug="campo", name="Campo", description="",
        city="SP", region="SP", timezone="America/Sao_Paulo",
        slot_duration_minutes=slot_minutes, base_price_cents=8000,
        customer_cancellation_cutoff_hours=24,
        operating_hours=schedule, pricing_rules=[],
        custom_attributes=[], base_attributes={},
    ).value
    r.publish()
    return r


def _local_slot(*, day=28, hour_local=14, hours=1) -> tuple[datetime, datetime]:
    start = datetime(2026, 4, day, hour_local + 3, 0, 0, tzinfo=timezone.utc)
    end = start + timedelta(hours=hours)
    return start, end


class _FakeResourceRepo:
    def __init__(self, resources):
        self._by_id = {r.id: r for r in resources}
        self._by_slug = {r.slug.value: r for r in resources}

    async def get_by_id(self, rid):
        return self._by_id.get(rid)

    async def get_by_owner_slug_and_resource_slug(self, owner_slug, resource_slug):
        return self._by_slug.get(resource_slug)


async def test_public_agenda_only_status_no_booking_ids():
    owner_id = uuid4()
    res = _build_resource(owner_id=owner_id)
    repo = InMemoryBookingRepository()
    handler = GetAgendaHandler(
        bookings=repo, resources=_FakeResourceRepo([res]),
    )
    start, end = _local_slot(day=28, hour_local=14, hours=2)
    r = await handler.handle(GetAgendaQuery(
        resource_id=res.id, range_start=start, range_end=end,
        actor_id=None,
    ))
    assert r.is_success
    slots = r.value.slots
    assert all(s.status == "AVAILABLE" for s in slots)
    assert all(s.booking_id is None for s in slots)
    assert all(s.customer_id is None for s in slots)
    assert all(s.price_cents == 8000 for s in slots)


async def test_public_agenda_marks_pending_and_approved():
    owner_id = uuid4()
    res = _build_resource(owner_id=owner_id)
    repo = InMemoryBookingRepository()
    p_start, p_end = _local_slot(day=28, hour_local=14, hours=1)
    pending = Booking.create_pending(
        resource_id=res.id, customer_id=uuid4(),
        slot_range=DateTimeRange.create(start_at=p_start, end_at=p_end).value,
        total_price_cents=Money.create(8000).value,
        customer_note=None, now=_now(),
    )
    a_start, a_end = _local_slot(day=28, hour_local=15, hours=1)
    approved = Booking.create_pending(
        resource_id=res.id, customer_id=uuid4(),
        slot_range=DateTimeRange.create(start_at=a_start, end_at=a_end).value,
        total_price_cents=Money.create(8000).value,
        customer_note=None, now=_now(),
    )
    approved.approve(actor_id=owner_id, now=_now())
    await repo.add(pending)
    await repo.add(approved)
    handler = GetAgendaHandler(
        bookings=repo, resources=_FakeResourceRepo([res]),
    )
    range_start, range_end = _local_slot(day=28, hour_local=14, hours=3)
    r = await handler.handle(GetAgendaQuery(
        resource_id=res.id, range_start=range_start, range_end=range_end,
        actor_id=None,
    ))
    assert r.is_success
    by_start = {s.slot_start_at: s for s in r.value.slots}
    assert by_start[p_start].status == "PENDING"
    assert by_start[a_start].status == "APPROVED"


async def test_owner_agenda_includes_booking_ids():
    owner_id = uuid4()
    res = _build_resource(owner_id=owner_id)
    repo = InMemoryBookingRepository()
    p_start, p_end = _local_slot(day=28, hour_local=14, hours=1)
    customer_id = uuid4()
    pending = Booking.create_pending(
        resource_id=res.id, customer_id=customer_id,
        slot_range=DateTimeRange.create(start_at=p_start, end_at=p_end).value,
        total_price_cents=Money.create(8000).value,
        customer_note=None, now=_now(),
    )
    await repo.add(pending)
    handler = GetAgendaHandler(
        bookings=repo, resources=_FakeResourceRepo([res]),
    )
    range_start, range_end = _local_slot(day=28, hour_local=14, hours=2)
    r = await handler.handle(GetAgendaQuery(
        resource_id=res.id, range_start=range_start, range_end=range_end,
        actor_id=owner_id,
    ))
    assert r.is_success
    occupied = [s for s in r.value.slots if s.status == "PENDING"]
    assert len(occupied) == 1
    assert occupied[0].booking_id == pending.id
    assert occupied[0].customer_id == customer_id


async def test_range_too_wide_returns_422():
    res = _build_resource(owner_id=uuid4())
    handler = GetAgendaHandler(
        bookings=InMemoryBookingRepository(),
        resources=_FakeResourceRepo([res]),
    )
    rs, _ = _local_slot(day=1, hour_local=8)
    re_dt = rs + timedelta(days=32)
    r = await handler.handle(GetAgendaQuery(
        resource_id=res.id, range_start=rs, range_end=re_dt, actor_id=None,
    ))
    assert r.is_failure
    assert r.error == "AgendaRangeTooWide"


async def test_unknown_resource_returns_404():
    handler = GetAgendaHandler(
        bookings=InMemoryBookingRepository(),
        resources=_FakeResourceRepo([]),
    )
    rs, re = _local_slot()
    r = await handler.handle(GetAgendaQuery(
        resource_id=uuid4(), range_start=rs, range_end=re, actor_id=None,
    ))
    assert r.is_failure
    assert r.error == "ResourceNotFound"


async def test_resolves_by_slug_when_resource_id_none():
    res = _build_resource(owner_id=uuid4())
    handler = GetAgendaHandler(
        bookings=InMemoryBookingRepository(),
        resources=_FakeResourceRepo([res]),
    )
    rs, re = _local_slot(day=28, hour_local=14, hours=1)
    r = await handler.handle(GetAgendaQuery(
        owner_slug="any", resource_slug=res.slug.value,
        range_start=rs, range_end=re, actor_id=None,
    ))
    assert r.is_success
