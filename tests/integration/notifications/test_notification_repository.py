from __future__ import annotations
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.domain.notifications.notification import Notification
from app.domain.notifications.service import NotifKind
from app.infrastructure.repositories.notification_repository import (
    SQLAlchemyNotificationRepository,
)


pytestmark = pytest.mark.asyncio


def _now() -> datetime:
    return datetime(2026, 4, 26, 12, 0, 0, tzinfo=timezone.utc)


async def test_add_and_round_trip(db_session):
    repo = SQLAlchemyNotificationRepository(db_session)
    rid = uuid4()
    n = Notification.create(
        recipient_id=rid,
        kind=NotifKind.SUBSCRIPTION_CHANGED,
        payload={"old_status": "TRIALING", "new_status": "INACTIVE"},
        now=_now(),
    )
    add_r = await repo.add(n)
    assert add_r.is_success

    fetched = await repo.get_for_recipient(n.id, rid)
    assert fetched.is_success
    assert fetched.value is not None
    assert fetched.value.id == n.id
    assert fetched.value.kind is NotifKind.SUBSCRIPTION_CHANGED
    assert fetched.value.payload == {"old_status": "TRIALING", "new_status": "INACTIVE"}
    assert fetched.value.read_at is None


async def test_get_for_recipient_returns_none_on_cross_recipient(db_session):
    repo = SQLAlchemyNotificationRepository(db_session)
    owner_id = uuid4()
    intruder_id = uuid4()
    n = Notification.create(
        recipient_id=owner_id, kind=NotifKind.SUBSCRIPTION_CHANGED,
        payload={}, now=_now(),
    )
    await repo.add(n)
    fetched = await repo.get_for_recipient(n.id, intruder_id)
    assert fetched.is_success
    assert fetched.value is None


async def test_list_by_recipient_orders_newest_first(db_session):
    repo = SQLAlchemyNotificationRepository(db_session)
    rid = uuid4()
    base = _now()
    notifs = []
    for i in range(3):
        n = Notification.create(
            recipient_id=rid,
            kind=NotifKind.SUBSCRIPTION_CHANGED,
            payload={"i": i},
            now=base + timedelta(minutes=i),
        )
        await repo.add(n)
        notifs.append(n)

    listed = await repo.list_by_recipient(
        rid, limit=10, cursor=None, unread_only=False,
    )
    assert listed.is_success
    ids = [n.id for n in listed.value]
    assert ids == [notifs[2].id, notifs[1].id, notifs[0].id]


async def test_list_by_recipient_filters_other_recipients(db_session):
    repo = SQLAlchemyNotificationRepository(db_session)
    rid = uuid4()
    other = uuid4()
    n_mine = Notification.create(
        recipient_id=rid, kind=NotifKind.SUBSCRIPTION_CHANGED,
        payload={}, now=_now(),
    )
    n_theirs = Notification.create(
        recipient_id=other, kind=NotifKind.SUBSCRIPTION_CHANGED,
        payload={}, now=_now(),
    )
    await repo.add(n_mine)
    await repo.add(n_theirs)

    listed = await repo.list_by_recipient(
        rid, limit=10, cursor=None, unread_only=False,
    )
    assert listed.is_success
    assert [n.id for n in listed.value] == [n_mine.id]


async def test_list_by_recipient_unread_only_filter(db_session):
    repo = SQLAlchemyNotificationRepository(db_session)
    rid = uuid4()
    base = _now()
    read_n = Notification.create(
        recipient_id=rid, kind=NotifKind.SUBSCRIPTION_CHANGED,
        payload={}, now=base,
    )
    read_n.mark_read(now=base + timedelta(minutes=5))
    unread_n = Notification.create(
        recipient_id=rid, kind=NotifKind.SUBSCRIPTION_CHANGED,
        payload={}, now=base + timedelta(minutes=1),
    )
    await repo.add(read_n)
    await repo.add(unread_n)

    listed = await repo.list_by_recipient(
        rid, limit=10, cursor=None, unread_only=True,
    )
    assert listed.is_success
    assert [n.id for n in listed.value] == [unread_n.id]


async def test_list_by_recipient_cursor_pagination(db_session):
    repo = SQLAlchemyNotificationRepository(db_session)
    rid = uuid4()
    base = _now()
    notifs = []
    for i in range(5):
        n = Notification.create(
            recipient_id=rid, kind=NotifKind.SUBSCRIPTION_CHANGED,
            payload={"i": i}, now=base + timedelta(minutes=i),
        )
        await repo.add(n)
        notifs.append(n)

    page1 = await repo.list_by_recipient(rid, limit=2, cursor=None, unread_only=False)
    assert page1.is_success
    assert [n.id for n in page1.value] == [notifs[4].id, notifs[3].id]

    page2 = await repo.list_by_recipient(
        rid, limit=2, cursor=notifs[3].id, unread_only=False,
    )
    assert page2.is_success
    assert [n.id for n in page2.value] == [notifs[2].id, notifs[1].id]


async def test_update_persists_read_at(db_session):
    repo = SQLAlchemyNotificationRepository(db_session)
    rid = uuid4()
    n = Notification.create(
        recipient_id=rid, kind=NotifKind.SUBSCRIPTION_CHANGED,
        payload={}, now=_now(),
    )
    await repo.add(n)
    n.mark_read(now=_now() + timedelta(hours=1))
    update_r = await repo.update(n)
    assert update_r.is_success

    fetched = await repo.get_for_recipient(n.id, rid)
    assert fetched.value.read_at == _now() + timedelta(hours=1)


async def test_update_returns_failure_when_id_missing(db_session):
    repo = SQLAlchemyNotificationRepository(db_session)
    n = Notification.create(
        recipient_id=uuid4(), kind=NotifKind.SUBSCRIPTION_CHANGED,
        payload={}, now=_now(),
    )
    # not added — update should fail.
    update_r = await repo.update(n)
    assert update_r.is_failure
    assert update_r.error == "NotificationNotFound"
