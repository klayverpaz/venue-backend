from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from app.domain.notifications.notification import Notification
from app.domain.notifications.service import NotifKind


def _now() -> datetime:
    return datetime(2026, 4, 26, 12, 0, 0, tzinfo=timezone.utc)


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


def test_notification_create_sets_all_fields():
    rid = uuid4()
    n = Notification.create(
        recipient_id=rid,
        kind=NotifKind.SUBSCRIPTION_CHANGED,
        payload={"old_status": "TRIALING", "new_status": "INACTIVE"},
        now=_now(),
    )
    assert isinstance(n.id, UUID)
    assert n.recipient_id == rid
    assert n.kind is NotifKind.SUBSCRIPTION_CHANGED
    assert n.payload == {"old_status": "TRIALING", "new_status": "INACTIVE"}
    assert n.read_at is None
    assert n.created_at == _now()
    assert n.updated_at == _now()


def test_notification_create_generates_unique_ids():
    n1 = Notification.create(
        recipient_id=uuid4(),
        kind=NotifKind.SUBSCRIPTION_CHANGED,
        payload={},
        now=_now(),
    )
    n2 = Notification.create(
        recipient_id=uuid4(),
        kind=NotifKind.SUBSCRIPTION_CHANGED,
        payload={},
        now=_now(),
    )
    assert n1.id != n2.id


def test_mark_read_sets_read_at_when_unread():
    n = Notification.create(
        recipient_id=uuid4(),
        kind=NotifKind.SUBSCRIPTION_CHANGED,
        payload={},
        now=_now(),
    )
    later = datetime(2026, 4, 26, 13, 0, 0, tzinfo=timezone.utc)
    n.mark_read(now=later)
    assert n.read_at == later
    assert n.updated_at == later


def test_mark_read_is_idempotent_when_already_read():
    n = Notification.create(
        recipient_id=uuid4(),
        kind=NotifKind.SUBSCRIPTION_CHANGED,
        payload={},
        now=_now(),
    )
    first_read = datetime(2026, 4, 26, 13, 0, 0, tzinfo=timezone.utc)
    second_read = datetime(2026, 4, 26, 14, 0, 0, tzinfo=timezone.utc)
    n.mark_read(now=first_read)
    n.mark_read(now=second_read)
    assert n.read_at == first_read  # not bumped
    assert n.updated_at == first_read  # also not bumped
