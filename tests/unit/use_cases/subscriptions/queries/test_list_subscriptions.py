from __future__ import annotations
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.domain.subscriptions.owner_subscription import OwnerSubscription
from app.domain.subscriptions.sub_status import SubStatus
from app.use_cases.subscriptions.queries.list_subscriptions import (
    ListSubscriptionsHandler,
    ListSubscriptionsQuery,
)
from tests.unit.use_cases.subscriptions.fakes.in_memory_subscription_repository import (
    InMemorySubscriptionRepository,
)


pytestmark = pytest.mark.asyncio


async def test_list_returns_all_when_no_filter():
    subs = InMemorySubscriptionRepository()
    now = datetime(2026, 4, 26, 12, 0, 0, tzinfo=timezone.utc)
    for st in [SubStatus.ACTIVE, SubStatus.INACTIVE]:
        await subs.add(OwnerSubscription(
            owner_id=uuid4(), status=st, status_changed_at=now, trial_ends_at=None,
        ))
    handler = ListSubscriptionsHandler(subs)
    r = await handler.handle(ListSubscriptionsQuery(status=None, limit=50, offset=0))
    assert r.is_success
    assert len(r.value) == 2


async def test_list_filters_by_status():
    subs = InMemorySubscriptionRepository()
    now = datetime(2026, 4, 26, 12, 0, 0, tzinfo=timezone.utc)
    await subs.add(OwnerSubscription(owner_id=uuid4(), status=SubStatus.ACTIVE, status_changed_at=now, trial_ends_at=None))
    await subs.add(OwnerSubscription(owner_id=uuid4(), status=SubStatus.INACTIVE, status_changed_at=now, trial_ends_at=None))
    handler = ListSubscriptionsHandler(subs)
    r = await handler.handle(ListSubscriptionsQuery(status="ACTIVE", limit=50, offset=0))
    assert r.is_success
    assert len(r.value) == 1
    assert r.value[0].status == "ACTIVE"


async def test_list_paginates():
    subs = InMemorySubscriptionRepository()
    now = datetime(2026, 4, 26, 12, 0, 0, tzinfo=timezone.utc)
    for _ in range(5):
        await subs.add(OwnerSubscription(owner_id=uuid4(), status=SubStatus.ACTIVE, status_changed_at=now, trial_ends_at=None))
    handler = ListSubscriptionsHandler(subs)
    r = await handler.handle(ListSubscriptionsQuery(status=None, limit=2, offset=1))
    assert r.is_success
    assert len(r.value) == 2
