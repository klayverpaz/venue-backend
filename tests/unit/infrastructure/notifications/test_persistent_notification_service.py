from __future__ import annotations
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

import pytest

from app.domain.notifications.notification import Notification
from app.domain.notifications.service import NotifKind
from app.domain.shared.result import Result
from app.infrastructure.notifications.persistent_notification_service import (
    PersistentNotificationService,
)


pytestmark = pytest.mark.asyncio


class _SpyRepo:
    """Minimal IN-memory repo for service-level testing."""

    def __init__(self, fail: bool = False) -> None:
        self.added: list[Notification] = []
        self.fail = fail

    async def add(self, notif: Notification) -> Result[None]:
        if self.fail:
            return Result.failure("RepoBoom")
        self.added.append(notif)
        return Result.success(None)

    async def get_for_recipient(self, *args, **kwargs):  # not used here
        raise NotImplementedError

    async def list_by_recipient(self, *args, **kwargs):  # not used here
        raise NotImplementedError

    async def update(self, *args, **kwargs):  # not used here
        raise NotImplementedError


async def test_notify_persists_a_row():
    repo = _SpyRepo()
    svc = PersistentNotificationService(repo)
    rid = uuid4()
    await svc.notify(
        recipient_id=rid,
        kind=NotifKind.SUBSCRIPTION_CHANGED,
        payload={"old_status": "TRIALING", "new_status": "ACTIVE"},
    )
    assert len(repo.added) == 1
    n = repo.added[0]
    assert isinstance(n, Notification)
    assert n.recipient_id == rid
    assert n.kind is NotifKind.SUBSCRIPTION_CHANGED
    assert n.payload == {"old_status": "TRIALING", "new_status": "ACTIVE"}
    assert n.read_at is None
    assert n.created_at.tzinfo is timezone.utc


async def test_notify_swallows_repo_failures(caplog):
    repo = _SpyRepo(fail=True)
    svc = PersistentNotificationService(repo)
    with caplog.at_level(logging.WARNING):
        await svc.notify(
            recipient_id=uuid4(),
            kind=NotifKind.SUBSCRIPTION_CHANGED,
            payload={},
        )
    assert any("notification persistence failed" in r.message for r in caplog.records)
    # And critically: no exception raised — fire-and-forget invariant.
