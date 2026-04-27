from __future__ import annotations
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.domain.accounts.role import Role
from app.domain.bookings.booking import Booking
from app.domain.bookings.booking_status import BookingStatus
from app.domain.shared.value_objects.date_time_range import DateTimeRange
from app.domain.shared.value_objects.money import Money
from app.domain.shared.value_objects.short_description import ShortDescription


def _now() -> datetime:
    return datetime(2026, 4, 27, 12, 0, 0, tzinfo=timezone.utc)


def _slot_range(hours: int = 1) -> DateTimeRange:
    return DateTimeRange.create(
        start_at=_now() + timedelta(days=1),
        end_at=_now() + timedelta(days=1, hours=hours),
    ).value


def _money(cents: int = 8000) -> Money:
    return Money.create(cents).value


def test_create_pending_sets_initial_state():
    rid, cid = uuid4(), uuid4()
    sr = _slot_range()
    b = Booking.create_pending(
        resource_id=rid,
        customer_id=cid,
        slot_range=sr,
        total_price_cents=_money(),
        customer_note=None,
        now=_now(),
    )
    assert b.resource_id == rid
    assert b.customer_id == cid
    assert b.slot_range == sr
    assert b.status is BookingStatus.PENDING
    assert b.total_price_cents.cents == 8000
    assert b.customer_note is None
    assert b.status_history == ()
    assert b.created_at == _now()
    assert b.updated_at == _now()


def test_create_pending_keeps_customer_note():
    note = ShortDescription.create("10 pessoas, festa de aniversário").value
    b = Booking.create_pending(
        resource_id=uuid4(), customer_id=uuid4(),
        slot_range=_slot_range(), total_price_cents=_money(),
        customer_note=note, now=_now(),
    )
    assert b.customer_note is note


def test_create_pending_generates_unique_ids():
    b1 = Booking.create_pending(
        resource_id=uuid4(), customer_id=uuid4(),
        slot_range=_slot_range(), total_price_cents=_money(),
        customer_note=None, now=_now(),
    )
    b2 = Booking.create_pending(
        resource_id=uuid4(), customer_id=uuid4(),
        slot_range=_slot_range(), total_price_cents=_money(),
        customer_note=None, now=_now(),
    )
    assert b1.id != b2.id


def test_slot_count():
    b = Booking.create_pending(
        resource_id=uuid4(), customer_id=uuid4(),
        slot_range=_slot_range(hours=3), total_price_cents=_money(),
        customer_note=None, now=_now(),
    )
    assert b.slot_count(slot_duration_minutes=60) == 3
    assert b.slot_count(slot_duration_minutes=30) == 6


def test_approve_transitions_pending_to_approved():
    b = Booking.create_pending(
        resource_id=uuid4(), customer_id=uuid4(),
        slot_range=_slot_range(), total_price_cents=_money(),
        customer_note=None, now=_now(),
    )
    actor = uuid4()
    later = _now() + timedelta(hours=1)
    r = b.approve(actor_id=actor, now=later)
    assert r.is_success
    assert b.status is BookingStatus.APPROVED
    assert b.updated_at == later
    assert len(b.status_history) == 1
    sc = b.status_history[0]
    assert sc.from_status is BookingStatus.PENDING
    assert sc.to_status is BookingStatus.APPROVED
    assert sc.actor_id == actor
    assert sc.actor_role is Role.OWNER
    assert sc.at == later
    assert sc.reason is None


def test_approve_already_approved_fails():
    b = Booking.create_pending(
        resource_id=uuid4(), customer_id=uuid4(),
        slot_range=_slot_range(), total_price_cents=_money(),
        customer_note=None, now=_now(),
    )
    b.approve(actor_id=uuid4(), now=_now())
    r = b.approve(actor_id=uuid4(), now=_now())
    assert r.is_failure


def test_reject_with_reason():
    b = Booking.create_pending(
        resource_id=uuid4(), customer_id=uuid4(),
        slot_range=_slot_range(), total_price_cents=_money(),
        customer_note=None, now=_now(),
    )
    r = b.reject(actor_id=uuid4(), now=_now(), reason="auto_rejected_competing_request")
    assert r.is_success
    assert b.status is BookingStatus.REJECTED
    assert b.status_history[-1].reason == "auto_rejected_competing_request"


def test_cancel_by_customer():
    b = Booking.create_pending(
        resource_id=uuid4(), customer_id=uuid4(),
        slot_range=_slot_range(), total_price_cents=_money(),
        customer_note=None, now=_now(),
    )
    r = b.cancel(actor_id=uuid4(), actor_role=Role.CUSTOMER, now=_now())
    assert r.is_success
    assert b.status is BookingStatus.CANCELLED
    assert b.status_history[-1].actor_role is Role.CUSTOMER


def test_cancel_approved_by_owner():
    b = Booking.create_pending(
        resource_id=uuid4(), customer_id=uuid4(),
        slot_range=_slot_range(), total_price_cents=_money(),
        customer_note=None, now=_now(),
    )
    b.approve(actor_id=uuid4(), now=_now())
    r = b.cancel(actor_id=uuid4(), actor_role=Role.OWNER, now=_now())
    assert r.is_success
    assert b.status is BookingStatus.CANCELLED
    # status_history has approve + cancel
    assert len(b.status_history) == 2


def test_expire_pending():
    b = Booking.create_pending(
        resource_id=uuid4(), customer_id=uuid4(),
        slot_range=_slot_range(), total_price_cents=_money(),
        customer_note=None, now=_now(),
    )
    r = b.expire(now=_now() + timedelta(days=2))
    assert r.is_success
    assert b.status is BookingStatus.EXPIRED
    sc = b.status_history[-1]
    assert sc.actor_role is Role.CUSTOMER
    assert sc.reason == "slot_start_passed_with_no_decision"


def test_expire_approved_fails():
    b = Booking.create_pending(
        resource_id=uuid4(), customer_id=uuid4(),
        slot_range=_slot_range(), total_price_cents=_money(),
        customer_note=None, now=_now(),
    )
    b.approve(actor_id=uuid4(), now=_now())
    r = b.expire(now=_now() + timedelta(days=2))
    assert r.is_failure


def test_status_history_is_append_only_view():
    b = Booking.create_pending(
        resource_id=uuid4(), customer_id=uuid4(),
        slot_range=_slot_range(), total_price_cents=_money(),
        customer_note=None, now=_now(),
    )
    b.approve(actor_id=uuid4(), now=_now())
    history = b.status_history
    assert isinstance(history, tuple)
    # Mutating private field doesn't affect prior view
    b.cancel(actor_id=uuid4(), actor_role=Role.OWNER, now=_now())
    assert len(b.status_history) == 2
