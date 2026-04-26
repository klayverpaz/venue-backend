from __future__ import annotations
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.domain.accounts.role import Role
from app.domain.accounts.user import User
from app.domain.notifications.service import NotifKind
from app.domain.subscriptions.owner_subscription import OwnerSubscription
from app.domain.subscriptions.sub_status import SubStatus
from app.use_cases.subscriptions.commands.set_owner_subscription_status import (
    SetOwnerSubscriptionStatusCommand,
    SetOwnerSubscriptionStatusHandler,
)
from tests.unit.use_cases.accounts.fakes.in_memory_user_repository import (
    InMemoryUserRepository,
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


async def _seed_owner(users: InMemoryUserRepository, *, is_active: bool = True):
    user = User.create(
        email="owner@example.com",
        password_hash="fake:hash",
        role=Role.OWNER,
        full_name="Owner",
        phone=None,
        public_slug="owner",
    ).value
    if not is_active:
        user.deactivate()
    await users.add(user)
    return user


async def _seed_subscription(
    subs: InMemorySubscriptionRepository, *, owner_id, status: SubStatus,
):
    now = datetime(2026, 4, 26, 12, 0, 0, tzinfo=timezone.utc)
    if status is SubStatus.TRIALING:
        sub = OwnerSubscription.create_trialing(
            owner_id=owner_id, trial_duration_days=3, now=now,
        ).value
    else:
        sub = OwnerSubscription(
            owner_id=owner_id, status=status,
            status_changed_at=now, trial_ends_at=None,
        )
    await subs.add(sub)
    return sub


async def test_set_status_real_change_persists_and_notifies(monkeypatch):
    users, subs, notifs = (
        InMemoryUserRepository(), InMemorySubscriptionRepository(), FakeNotificationService(),
    )
    settings = _settings(monkeypatch)
    owner = await _seed_owner(users)
    await _seed_subscription(subs, owner_id=owner.id, status=SubStatus.TRIALING)

    handler = SetOwnerSubscriptionStatusHandler(users, subs, notifs, settings)
    r = await handler.handle(SetOwnerSubscriptionStatusCommand(
        owner_id=owner.id, status=SubStatus.ACTIVE,
    ))
    assert r.is_success
    assert r.value.status == "ACTIVE"
    sub = await subs.get_by_owner_id(owner.id)
    assert sub.status is SubStatus.ACTIVE
    assert sub.trial_ends_at is None
    assert len(notifs.calls) == 1
    recipient, kind, payload = notifs.calls[0]
    assert recipient == owner.id
    assert kind is NotifKind.SUBSCRIPTION_CHANGED
    assert payload == {
        "old_status": "TRIALING", "new_status": "ACTIVE", "reason": "admin_action",
    }


async def test_set_status_idempotent_no_op(monkeypatch):
    users, subs, notifs = (
        InMemoryUserRepository(), InMemorySubscriptionRepository(), FakeNotificationService(),
    )
    settings = _settings(monkeypatch)
    owner = await _seed_owner(users)
    sub = await _seed_subscription(subs, owner_id=owner.id, status=SubStatus.ACTIVE)
    original_changed_at = sub.status_changed_at

    handler = SetOwnerSubscriptionStatusHandler(users, subs, notifs, settings)
    r = await handler.handle(SetOwnerSubscriptionStatusCommand(
        owner_id=owner.id, status=SubStatus.ACTIVE,
    ))
    assert r.is_success
    assert r.value.status == "ACTIVE"
    assert notifs.calls == []
    sub_after = await subs.get_by_owner_id(owner.id)
    assert sub_after.status_changed_at == original_changed_at


async def test_set_status_returns_owner_not_found(monkeypatch):
    users, subs, notifs = (
        InMemoryUserRepository(), InMemorySubscriptionRepository(), FakeNotificationService(),
    )
    settings = _settings(monkeypatch)
    handler = SetOwnerSubscriptionStatusHandler(users, subs, notifs, settings)
    r = await handler.handle(SetOwnerSubscriptionStatusCommand(
        owner_id=uuid4(), status=SubStatus.ACTIVE,
    ))
    assert r.is_failure
    assert r.error == "OwnerNotFound"
    assert r.status_code == 404


async def test_set_status_rejects_non_owner(monkeypatch):
    users, subs, notifs = (
        InMemoryUserRepository(), InMemorySubscriptionRepository(), FakeNotificationService(),
    )
    settings = _settings(monkeypatch)
    customer = User.create(
        email="customer@example.com", password_hash="h",
        role=Role.CUSTOMER, full_name="C", phone=None,
    ).value
    await users.add(customer)
    handler = SetOwnerSubscriptionStatusHandler(users, subs, notifs, settings)
    r = await handler.handle(SetOwnerSubscriptionStatusCommand(
        owner_id=customer.id, status=SubStatus.ACTIVE,
    ))
    assert r.is_failure
    assert r.error == "UserIsNotOwner"
    assert r.status_code == 422


async def test_set_status_returns_subscription_not_found(monkeypatch):
    users, subs, notifs = (
        InMemoryUserRepository(), InMemorySubscriptionRepository(), FakeNotificationService(),
    )
    settings = _settings(monkeypatch)
    owner = await _seed_owner(users)  # owner exists, no subscription
    handler = SetOwnerSubscriptionStatusHandler(users, subs, notifs, settings)
    r = await handler.handle(SetOwnerSubscriptionStatusCommand(
        owner_id=owner.id, status=SubStatus.ACTIVE,
    ))
    assert r.is_failure
    assert r.error == "SubscriptionNotFound"
    assert r.status_code == 404


async def test_set_status_to_trialing_resets_trial_window(monkeypatch):
    users, subs, notifs = (
        InMemoryUserRepository(), InMemorySubscriptionRepository(), FakeNotificationService(),
    )
    settings = _settings(monkeypatch)
    owner = await _seed_owner(users)
    await _seed_subscription(subs, owner_id=owner.id, status=SubStatus.INACTIVE)
    handler = SetOwnerSubscriptionStatusHandler(users, subs, notifs, settings)
    r = await handler.handle(SetOwnerSubscriptionStatusCommand(
        owner_id=owner.id, status=SubStatus.TRIALING,
    ))
    assert r.is_success
    sub = await subs.get_by_owner_id(owner.id)
    assert sub.status is SubStatus.TRIALING
    assert sub.trial_ends_at is not None
    assert sub.trial_ends_at > sub.status_changed_at
    assert (sub.trial_ends_at - sub.status_changed_at) == timedelta(days=3)
