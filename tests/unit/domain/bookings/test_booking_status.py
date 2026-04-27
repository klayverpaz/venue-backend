from __future__ import annotations

from app.domain.bookings.booking_status import BookingStatus


def test_booking_status_values():
    assert BookingStatus.PENDING.value == "PENDING"
    assert BookingStatus.APPROVED.value == "APPROVED"
    assert BookingStatus.REJECTED.value == "REJECTED"
    assert BookingStatus.CANCELLED.value == "CANCELLED"
    assert BookingStatus.EXPIRED.value == "EXPIRED"


def test_booking_status_count():
    assert len(list(BookingStatus)) == 5


def test_booking_status_is_active():
    assert BookingStatus.PENDING.is_active() is True
    assert BookingStatus.APPROVED.is_active() is True
    assert BookingStatus.REJECTED.is_active() is False
    assert BookingStatus.CANCELLED.is_active() is False
    assert BookingStatus.EXPIRED.is_active() is False


def test_booking_status_is_terminal():
    assert BookingStatus.REJECTED.is_terminal() is True
    assert BookingStatus.CANCELLED.is_terminal() is True
    assert BookingStatus.EXPIRED.is_terminal() is True
    assert BookingStatus.PENDING.is_terminal() is False
    assert BookingStatus.APPROVED.is_terminal() is False
