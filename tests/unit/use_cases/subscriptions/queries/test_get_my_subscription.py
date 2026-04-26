from __future__ import annotations
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.domain.subscriptions.owner_subscription import OwnerSubscription
from app.domain.subscriptions.sub_status import SubStatus
from app.use_cases.subscriptions.queries.get_my_subscription import (
    GetMySubscriptionHandler,
    GetMySubscriptionQuery,
)
from tests.unit.use_cases.subscriptions.fakes.in_memory_subscription_repository import (
    InMemorySubscriptionRepository,
)


pytestmark = pytest.mark.asyncio


async def test_get_my_subscription_success():
    subs = InMemorySubscriptionRepository()
    now = datetime(2026, 4, 26, 12, 0, 0, tzinfo=timezone.utc)
    owner_id = uuid4()
    await subs.add(OwnerSubscription(
        owner_id=owner_id, status=SubStatus.ACTIVE,
        status_changed_at=now, trial_ends_at=None,
    ))
    handler = GetMySubscriptionHandler(subs)
    r = await handler.handle(GetMySubscriptionQuery(requester_id=owner_id))
    assert r.is_success
    assert r.value.owner_id == owner_id
    assert r.value.status == "ACTIVE"


async def test_get_my_subscription_returns_not_found_when_absent():
    subs = InMemorySubscriptionRepository()
    handler = GetMySubscriptionHandler(subs)
    r = await handler.handle(GetMySubscriptionQuery(requester_id=uuid4()))
    assert r.is_failure
    assert r.error == "SubscriptionNotFound"
    assert r.status_code == 404
