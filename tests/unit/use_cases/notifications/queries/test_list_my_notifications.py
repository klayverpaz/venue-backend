from __future__ import annotations
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.domain.notifications.notification import Notification
from app.domain.notifications.service import NotifKind
from app.use_cases.notifications.queries.list_my_notifications import (
    ListMyNotificationsHandler,
    ListMyNotificationsQuery,
)
from tests.unit.use_cases.notifications.fakes.in_memory_notification_repository import (
    InMemoryNotificationRepository,
)


pytestmark = pytest.mark.asyncio


def _now() -> datetime:
    return datetime(2026, 4, 26, 12, 0, 0, tzinfo=timezone.utc)


async def test_returns_my_notifications_newest_first():
    repo = InMemoryNotificationRepository()
    rid = uuid4()
    older = Notification.create(
        recipient_id=rid, kind=NotifKind.SUBSCRIPTION_CHANGED,
        payload={}, now=_now(),
    )
    newer = Notification.create(
        recipient_id=rid, kind=NotifKind.BOOKING_REQUESTED,
        payload={}, now=_now() + timedelta(minutes=5),
    )
    await repo.add(older)
    await repo.add(newer)

    handler = ListMyNotificationsHandler(repo)
    result = await handler.handle(
        ListMyNotificationsQuery(actor_id=rid, limit=50, cursor=None, unread_only=False)
    )
    assert result.is_success
    ids = [n.id for n in result.value.items]
    assert ids == [newer.id, older.id]
    assert result.value.next_cursor is None


async def test_clamps_limit_to_max_100():
    repo = InMemoryNotificationRepository()
    rid = uuid4()
    handler = ListMyNotificationsHandler(repo)
    # Inject 105 notifs
    base = _now()
    for i in range(105):
        n = Notification.create(
            recipient_id=rid, kind=NotifKind.SUBSCRIPTION_CHANGED,
            payload={"i": i}, now=base + timedelta(seconds=i),
        )
        await repo.add(n)

    result = await handler.handle(
        ListMyNotificationsQuery(actor_id=rid, limit=500, cursor=None, unread_only=False)
    )
    assert result.is_success
    assert len(result.value.items) == 100
    assert result.value.next_cursor is not None  # 5 more rows beyond


async def test_clamps_limit_to_min_1():
    repo = InMemoryNotificationRepository()
    rid = uuid4()
    handler = ListMyNotificationsHandler(repo)
    n = Notification.create(
        recipient_id=rid, kind=NotifKind.SUBSCRIPTION_CHANGED,
        payload={}, now=_now(),
    )
    await repo.add(n)

    result = await handler.handle(
        ListMyNotificationsQuery(actor_id=rid, limit=0, cursor=None, unread_only=False)
    )
    assert result.is_success
    assert len(result.value.items) == 1


async def test_next_cursor_set_when_more_pages():
    repo = InMemoryNotificationRepository()
    rid = uuid4()
    handler = ListMyNotificationsHandler(repo)
    base = _now()
    notifs = []
    for i in range(3):
        n = Notification.create(
            recipient_id=rid, kind=NotifKind.SUBSCRIPTION_CHANGED,
            payload={}, now=base + timedelta(seconds=i),
        )
        await repo.add(n)
        notifs.append(n)

    result = await handler.handle(
        ListMyNotificationsQuery(actor_id=rid, limit=2, cursor=None, unread_only=False)
    )
    assert result.is_success
    items = result.value.items
    assert [n.id for n in items] == [notifs[2].id, notifs[1].id]
    assert result.value.next_cursor == notifs[1].id


async def test_next_cursor_none_when_last_page():
    repo = InMemoryNotificationRepository()
    rid = uuid4()
    handler = ListMyNotificationsHandler(repo)
    base = _now()
    for i in range(2):
        await repo.add(Notification.create(
            recipient_id=rid, kind=NotifKind.SUBSCRIPTION_CHANGED,
            payload={}, now=base + timedelta(seconds=i),
        ))

    result = await handler.handle(
        ListMyNotificationsQuery(actor_id=rid, limit=5, cursor=None, unread_only=False)
    )
    assert result.is_success
    assert result.value.next_cursor is None


async def test_unread_only_filters_read_rows():
    repo = InMemoryNotificationRepository()
    rid = uuid4()
    handler = ListMyNotificationsHandler(repo)
    base = _now()
    read_n = Notification.create(
        recipient_id=rid, kind=NotifKind.SUBSCRIPTION_CHANGED,
        payload={}, now=base,
    )
    read_n.mark_read(now=base + timedelta(seconds=10))
    unread_n = Notification.create(
        recipient_id=rid, kind=NotifKind.SUBSCRIPTION_CHANGED,
        payload={}, now=base + timedelta(seconds=1),
    )
    await repo.add(read_n)
    await repo.add(unread_n)

    result = await handler.handle(
        ListMyNotificationsQuery(actor_id=rid, limit=10, cursor=None, unread_only=True)
    )
    assert result.is_success
    assert [n.id for n in result.value.items] == [unread_n.id]
