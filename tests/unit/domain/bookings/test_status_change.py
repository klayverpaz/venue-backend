from __future__ import annotations
from datetime import datetime, timezone
from uuid import uuid4

from app.domain.accounts.role import Role
from app.domain.bookings.booking_status import BookingStatus
from app.domain.bookings.status_change import StatusChange


def _now() -> datetime:
    return datetime(2026, 4, 27, 12, 0, 0, tzinfo=timezone.utc)


def test_create_pending_to_approved_succeeds():
    r = StatusChange.create(
        from_status=BookingStatus.PENDING,
        to_status=BookingStatus.APPROVED,
        actor_id=uuid4(),
        actor_role=Role.OWNER,
        at=_now(),
        reason=None,
    )
    assert r.is_success
    sc = r.value
    assert sc.from_status is BookingStatus.PENDING
    assert sc.to_status is BookingStatus.APPROVED


def test_create_pending_to_pending_invalid():
    r = StatusChange.create(
        from_status=BookingStatus.PENDING,
        to_status=BookingStatus.PENDING,
        actor_id=uuid4(),
        actor_role=Role.CUSTOMER,
        at=_now(),
    )
    assert r.is_failure
    assert r.error == StatusChange.STATUS_CHANGE_INVALID_TRANSITION


def test_create_terminal_to_anything_invalid():
    for terminal in (BookingStatus.REJECTED, BookingStatus.CANCELLED, BookingStatus.EXPIRED):
        for to in (BookingStatus.PENDING, BookingStatus.APPROVED):
            r = StatusChange.create(
                from_status=terminal, to_status=to,
                actor_id=uuid4(), actor_role=Role.OWNER, at=_now(),
            )
            assert r.is_failure
            assert r.error == StatusChange.STATUS_CHANGE_INVALID_TRANSITION


def test_create_approved_to_cancelled_succeeds():
    r = StatusChange.create(
        from_status=BookingStatus.APPROVED,
        to_status=BookingStatus.CANCELLED,
        actor_id=uuid4(),
        actor_role=Role.OWNER,
        at=_now(),
        reason="storm cancelled the match",
    )
    assert r.is_success
    assert r.value.reason == "storm cancelled the match"


def test_create_approved_to_rejected_invalid():
    r = StatusChange.create(
        from_status=BookingStatus.APPROVED,
        to_status=BookingStatus.REJECTED,
        actor_id=uuid4(),
        actor_role=Role.OWNER,
        at=_now(),
    )
    assert r.is_failure
    assert r.error == StatusChange.STATUS_CHANGE_INVALID_TRANSITION


def test_create_rejects_naive_datetime():
    naive = datetime(2026, 4, 27, 12, 0, 0)
    r = StatusChange.create(
        from_status=BookingStatus.PENDING,
        to_status=BookingStatus.APPROVED,
        actor_id=uuid4(),
        actor_role=Role.OWNER,
        at=naive,
    )
    assert r.is_failure
    assert r.error == StatusChange.STATUS_CHANGE_AT_NOT_TZ_AWARE


def test_create_rejects_reason_too_long():
    r = StatusChange.create(
        from_status=BookingStatus.PENDING,
        to_status=BookingStatus.REJECTED,
        actor_id=uuid4(),
        actor_role=Role.OWNER,
        at=_now(),
        reason="x" * 501,
    )
    assert r.is_failure
    assert r.error == StatusChange.STATUS_CHANGE_REASON_TOO_LONG


def test_create_accepts_reason_at_max_length():
    r = StatusChange.create(
        from_status=BookingStatus.PENDING,
        to_status=BookingStatus.REJECTED,
        actor_id=uuid4(),
        actor_role=Role.OWNER,
        at=_now(),
        reason="x" * 500,
    )
    assert r.is_success


def test_status_change_is_frozen():
    sc = StatusChange.create(
        from_status=BookingStatus.PENDING,
        to_status=BookingStatus.APPROVED,
        actor_id=uuid4(),
        actor_role=Role.OWNER,
        at=_now(),
    ).value
    import dataclasses
    with __import__("pytest").raises(dataclasses.FrozenInstanceError):
        sc.reason = "x"  # type: ignore[misc]
