from __future__ import annotations
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.domain.notifications.notification import Notification
from app.domain.notifications.service import NotifKind
from app.use_cases.notifications.commands.mark_notification_read import (
    MarkNotificationReadCommand,
    MarkNotificationReadHandler,
)
from tests.unit.use_cases.notifications.fakes.in_memory_notification_repository import (
    InMemoryNotificationRepository,
)


pytestmark = pytest.mark.asyncio


def _now() -> datetime:
    return datetime(2026, 4, 26, 12, 0, 0, tzinfo=timezone.utc)


async def test_marks_unread_notification_read():
    repo = InMemoryNotificationRepository()
    rid = uuid4()
    n = Notification.create(
        recipient_id=rid, kind=NotifKind.SUBSCRIPTION_CHANGED,
        payload={}, now=_now(),
    )
    await repo.add(n)
    handler = MarkNotificationReadHandler(repo)

    result = await handler.handle(
        MarkNotificationReadCommand(actor_id=rid, notification_id=n.id)
    )
    assert result.is_success

    fetched = (await repo.get_for_recipient(n.id, rid)).value
    assert fetched.read_at is not None


async def test_already_read_is_idempotent_success():
    repo = InMemoryNotificationRepository()
    rid = uuid4()
    n = Notification.create(
        recipient_id=rid, kind=NotifKind.SUBSCRIPTION_CHANGED,
        payload={}, now=_now(),
    )
    n.mark_read(now=_now())
    await repo.add(n)
    first_read_at = n.read_at

    handler = MarkNotificationReadHandler(repo)
    result = await handler.handle(
        MarkNotificationReadCommand(actor_id=rid, notification_id=n.id)
    )
    assert result.is_success

    fetched = (await repo.get_for_recipient(n.id, rid)).value
    assert fetched.read_at == first_read_at  # not bumped


async def test_cross_recipient_returns_404():
    repo = InMemoryNotificationRepository()
    owner_id = uuid4()
    intruder_id = uuid4()
    n = Notification.create(
        recipient_id=owner_id, kind=NotifKind.SUBSCRIPTION_CHANGED,
        payload={}, now=_now(),
    )
    await repo.add(n)

    handler = MarkNotificationReadHandler(repo)
    result = await handler.handle(
        MarkNotificationReadCommand(actor_id=intruder_id, notification_id=n.id)
    )
    assert result.is_failure
    assert result.error == "NotificationNotFound"
    assert result.status_code == 404


async def test_unknown_id_returns_404():
    repo = InMemoryNotificationRepository()
    handler = MarkNotificationReadHandler(repo)
    result = await handler.handle(
        MarkNotificationReadCommand(actor_id=uuid4(), notification_id=uuid4())
    )
    assert result.is_failure
    assert result.error == "NotificationNotFound"
    assert result.status_code == 404
