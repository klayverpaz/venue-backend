from __future__ import annotations

from app.domain.notifications.service import NotifKind


def test_notif_kind_subscription_changed():
    assert NotifKind.SUBSCRIPTION_CHANGED.value == "SUBSCRIPTION_CHANGED"


def test_notif_kind_booking_requested():
    assert NotifKind.BOOKING_REQUESTED.value == "BOOKING_REQUESTED"


def test_notif_kind_booking_approved():
    assert NotifKind.BOOKING_APPROVED.value == "BOOKING_APPROVED"


def test_notif_kind_booking_rejected():
    assert NotifKind.BOOKING_REJECTED.value == "BOOKING_REJECTED"


def test_notif_kind_booking_cancelled():
    assert NotifKind.BOOKING_CANCELLED.value == "BOOKING_CANCELLED"


def test_notif_kind_has_no_booking_rated():
    assert not hasattr(NotifKind, "BOOKING_RATED")
