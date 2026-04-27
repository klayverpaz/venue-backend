from __future__ import annotations
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.domain.bookings.booking import Booking
from app.domain.bookings.booking_status import BookingStatus
from app.domain.shared.value_objects.date_time_range import DateTimeRange
from app.domain.shared.value_objects.money import Money
from app.infrastructure.db.mappings.user import UserModel
from app.infrastructure.db.mappings.resource import ResourceModel
from app.infrastructure.db.mappings.resource_type import ResourceTypeModel
from app.infrastructure.repositories.booking_repository import (
    SQLAlchemyBookingRepository,
)


pytestmark = pytest.mark.asyncio


def _now() -> datetime:
    return datetime(2026, 4, 27, 12, 0, 0, tzinfo=timezone.utc)


def _slot_range(*, start_offset_days: int = 1, hours: int = 1) -> DateTimeRange:
    start = _now() + timedelta(days=start_offset_days)
    end = start + timedelta(hours=hours)
    return DateTimeRange.create(start_at=start, end_at=end).value


def _money(c: int = 8000) -> Money:
    return Money.create(c).value


async def _seed_user_and_resource(db_session) -> tuple:
    """Insert a user, resource_type, and resource so FK constraints
    are satisfied for booking inserts."""
    rt = ResourceTypeModel(
        id=str(uuid4()), slug="football-field", name="Football Field",
        description="", attribute_schema=[], is_active=True,
        created_at=_now(), updated_at=_now(),
    )
    owner = UserModel(
        id=str(uuid4()), email="o@example.com", full_name="Owner",
        password_hash="x", role="owner", is_active=True,
        public_slug="owner",
        phone_number=None,
        created_at=_now(), updated_at=_now(),
    )
    customer = UserModel(
        id=str(uuid4()), email="c@example.com", full_name="Customer",
        password_hash="x", role="customer", is_active=True,
        public_slug=None, phone_number=None,
        created_at=_now(), updated_at=_now(),
    )
    res = ResourceModel(
        id=str(uuid4()), owner_id=owner.id, resource_type_id=rt.id,
        slug="campo", name="Campo", description="",
        city="SP", region="SP", timezone="America/Sao_Paulo",
        slot_duration_minutes=60, base_price_cents=8000,
        customer_cancellation_cutoff_hours=24,
        operating_hours={"monday": [{"start": "06:00", "end": "22:00"}]},
        pricing_rules=[], custom_attributes=[], base_attributes={},
        is_published=True, deleted_at=None,
        created_at=_now(), updated_at=_now(),
    )
    db_session.add_all([rt, owner, customer, res])
    await db_session.flush()
    return owner, customer, res


async def test_add_and_get_round_trip(db_session):
    repo = SQLAlchemyBookingRepository(db_session)
    _, customer, res = await _seed_user_and_resource(db_session)
    sr = _slot_range()
    b = Booking.create_pending(
        resource_id=res.id, customer_id=customer.id,
        slot_range=sr, total_price_cents=_money(),
        customer_note=None, now=_now(),
    )
    add_r = await repo.add(b)
    assert add_r.is_success
    fetched = (await repo.get_by_id(b.id)).value
    assert fetched is not None
    assert fetched.id == b.id
    assert fetched.status is BookingStatus.PENDING
    assert fetched.slot_range.start_at == sr.start_at
    assert fetched.slot_range.end_at == sr.end_at


async def test_list_by_customer_filters_status(db_session):
    repo = SQLAlchemyBookingRepository(db_session)
    _, customer, res = await _seed_user_and_resource(db_session)
    pending = Booking.create_pending(
        resource_id=res.id, customer_id=customer.id,
        slot_range=_slot_range(start_offset_days=1),
        total_price_cents=_money(), customer_note=None, now=_now(),
    )
    approved = Booking.create_pending(
        resource_id=res.id, customer_id=customer.id,
        slot_range=_slot_range(start_offset_days=2),
        total_price_cents=_money(), customer_note=None, now=_now(),
    )
    approved.approve(actor_id=uuid4(), now=_now())
    await repo.add(pending)
    await repo.add(approved)

    pendings = (await repo.list_by_customer(
        customer.id, status=BookingStatus.PENDING, page=1, page_size=10,
    )).value
    assert [b.id for b in pendings] == [pending.id]


async def test_list_pending_overlapping_excludes_self_and_other_resources(db_session):
    repo = SQLAlchemyBookingRepository(db_session)
    _, customer, res = await _seed_user_and_resource(db_session)
    sr = _slot_range(start_offset_days=1, hours=2)

    # Insert a second customer for FK-safe competitors.
    other_customer = UserModel(
        id=str(uuid4()), email="x@example.com", full_name="X",
        password_hash="x", role="customer", is_active=True,
        public_slug=None, phone_number=None, created_at=_now(), updated_at=_now(),
    )
    db_session.add(other_customer)
    await db_session.flush()

    target = Booking.create_pending(
        resource_id=res.id, customer_id=customer.id,
        slot_range=sr, total_price_cents=_money(), customer_note=None,
        now=_now(),
    )
    competitor_overlapping = Booking.create_pending(
        resource_id=res.id, customer_id=other_customer.id,
        slot_range=DateTimeRange.create(
            start_at=sr.start_at + timedelta(minutes=30),
            end_at=sr.end_at + timedelta(minutes=30),
        ).value,
        total_price_cents=_money(), customer_note=None, now=_now(),
    )
    competitor_disjoint = Booking.create_pending(
        resource_id=res.id, customer_id=other_customer.id,
        slot_range=_slot_range(start_offset_days=5),
        total_price_cents=_money(), customer_note=None, now=_now(),
    )

    await repo.add(target)
    await repo.add(competitor_overlapping)
    await repo.add(competitor_disjoint)

    overlaps = (await repo.list_pending_overlapping(
        res.id, sr, exclude_booking_id=target.id,
    )).value
    assert {b.id for b in overlaps} == {competitor_overlapping.id}


async def test_list_active_by_customer_for_resource_filters_to_active(db_session):
    repo = SQLAlchemyBookingRepository(db_session)
    _, customer, res = await _seed_user_and_resource(db_session)
    sr = _slot_range()
    pending = Booking.create_pending(
        resource_id=res.id, customer_id=customer.id,
        slot_range=sr, total_price_cents=_money(),
        customer_note=None, now=_now(),
    )
    cancelled = Booking.create_pending(
        resource_id=res.id, customer_id=customer.id,
        slot_range=sr, total_price_cents=_money(),
        customer_note=None, now=_now(),
    )
    from app.domain.accounts.role import Role
    cancelled.cancel(
        actor_id=customer.id, actor_role=Role.CUSTOMER, now=_now(),
    )
    await repo.add(pending)
    await repo.add(cancelled)

    actives = (await repo.list_active_by_customer_for_resource(
        customer.id, res.id, sr,
    )).value
    assert [b.id for b in actives] == [pending.id]


async def test_list_pending_with_start_before_filters_correctly(db_session):
    repo = SQLAlchemyBookingRepository(db_session)
    _, customer, res = await _seed_user_and_resource(db_session)
    past = Booking.create_pending(
        resource_id=res.id, customer_id=customer.id,
        slot_range=DateTimeRange.create(
            start_at=_now() - timedelta(hours=2),
            end_at=_now() - timedelta(hours=1),
        ).value,
        total_price_cents=_money(), customer_note=None, now=_now() - timedelta(days=1),
    )
    future = Booking.create_pending(
        resource_id=res.id, customer_id=customer.id,
        slot_range=_slot_range(start_offset_days=2),
        total_price_cents=_money(), customer_note=None, now=_now(),
    )
    await repo.add(past)
    await repo.add(future)

    expired = (await repo.list_pending_with_start_before(_now())).value
    assert {b.id for b in expired} == {past.id}


async def test_update_persists_status_change(db_session):
    repo = SQLAlchemyBookingRepository(db_session)
    _, customer, res = await _seed_user_and_resource(db_session)
    b = Booking.create_pending(
        resource_id=res.id, customer_id=customer.id,
        slot_range=_slot_range(), total_price_cents=_money(),
        customer_note=None, now=_now(),
    )
    await repo.add(b)
    b.approve(actor_id=uuid4(), now=_now())
    update_r = await repo.update(b)
    assert update_r.is_success
    fetched = (await repo.get_by_id(b.id)).value
    assert fetched.status is BookingStatus.APPROVED
    assert len(fetched.status_history) == 1
    assert fetched.status_history[0].to_status is BookingStatus.APPROVED
