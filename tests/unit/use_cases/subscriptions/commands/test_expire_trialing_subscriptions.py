from __future__ import annotations
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.domain.notifications.service import NotifKind
from app.domain.subscriptions.owner_subscription import OwnerSubscription
from app.domain.subscriptions.sub_status import SubStatus
from app.use_cases.subscriptions.commands.expire_trialing_subscriptions import (
    ExpireTrialingSubscriptionsCommand,
    ExpireTrialingSubscriptionsHandler,
)
from tests.unit.use_cases.subscriptions.fakes.fake_notification_service import (
    FakeNotificationService,
)
from tests.unit.use_cases.subscriptions.fakes.in_memory_subscription_repository import (
    InMemorySubscriptionRepository,
)


pytestmark = pytest.mark.asyncio


def _settings(monkeypatch) -> Settings:
    monkeypatch.setenv("BACKEND_DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    monkeypatch.setenv("BACKEND_TRIAL_DURATION_DAYS", "3")
    return Settings()


async def test_expires_trialing_with_expired_trial(monkeypatch):
    subs = InMemorySubscriptionRepository()
    notifs = FakeNotificationService()
    settings = _settings(monkeypatch)

    # Trial that expired well in the past (created 10 days ago, 3-day trial).
    sub = OwnerSubscription.create_trialing(
        owner_id=uuid4(), trial_duration_days=3,
        now=datetime.now(timezone.utc) - timedelta(days=10),
    ).value
    await subs.add(sub)

    handler = ExpireTrialingSubscriptionsHandler(subs, notifs, settings)
    r = await handler.handle(ExpireTrialingSubscriptionsCommand())
    assert r.is_success
    assert r.value == 1
    sub_after = await subs.get_by_owner_id(sub.owner_id)
    assert sub_after.status is SubStatus.INACTIVE
    assert sub_after.trial_ends_at is None
    assert len(notifs.calls) == 1
    recipient, kind, payload = notifs.calls[0]
    assert recipient == sub.owner_id
    assert kind is NotifKind.SUBSCRIPTION_CHANGED
    assert payload == {
        "old_status": "TRIALING", "new_status": "INACTIVE", "reason": "trial_expired",
    }


async def test_skips_trialing_with_future_expiry(monkeypatch):
    subs = InMemorySubscriptionRepository()
    notifs = FakeNotificationService()
    settings = _settings(monkeypatch)
    sub = OwnerSubscription.create_trialing(
        owner_id=uuid4(), trial_duration_days=3,
        now=datetime.now(timezone.utc),
    ).value
    await subs.add(sub)
    handler = ExpireTrialingSubscriptionsHandler(subs, notifs, settings)
    r = await handler.handle(ExpireTrialingSubscriptionsCommand())
    assert r.is_success
    assert r.value == 0
    assert len(notifs.calls) == 0


async def test_skips_non_trialing(monkeypatch):
    subs = InMemorySubscriptionRepository()
    notifs = FakeNotificationService()
    settings = _settings(monkeypatch)
    now = datetime.now(timezone.utc)
    await subs.add(OwnerSubscription(
        owner_id=uuid4(), status=SubStatus.ACTIVE,
        status_changed_at=now, trial_ends_at=None,
    ))
    handler = ExpireTrialingSubscriptionsHandler(subs, notifs, settings)
    r = await handler.handle(ExpireTrialingSubscriptionsCommand())
    assert r.is_success
    assert r.value == 0
