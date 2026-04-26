from __future__ import annotations
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.domain.subscriptions.owner_subscription import OwnerSubscription
from app.domain.subscriptions.sub_status import SubStatus
from app.infrastructure.repositories.owner_subscription_repository import (
    SQLAlchemyOwnerSubscriptionRepository,
)


pytestmark = pytest.mark.asyncio


def _now() -> datetime:
    return datetime(2026, 4, 26, 12, 0, 0, tzinfo=timezone.utc)


async def test_add_and_get_by_owner_id_round_trips(db_session):
    repo = SQLAlchemyOwnerSubscriptionRepository(db_session)
    sub = OwnerSubscription.create_trialing(
        owner_id=uuid4(), trial_duration_days=3, now=_now(),
    ).value
    add_r = await repo.add(sub)
    assert add_r.is_success
    fetched = await repo.get_by_owner_id(sub.owner_id)
    assert fetched is not None
    assert fetched.id == sub.id
    assert fetched.status is SubStatus.TRIALING
    assert fetched.trial_ends_at == sub.trial_ends_at


async def test_add_rejects_duplicate_owner_id(db_session):
    repo = SQLAlchemyOwnerSubscriptionRepository(db_session)
    owner_id = uuid4()
    sub1 = OwnerSubscription.create_trialing(
        owner_id=owner_id, trial_duration_days=3, now=_now(),
    ).value
    sub2 = OwnerSubscription.create_trialing(
        owner_id=owner_id, trial_duration_days=3, now=_now(),
    ).value
    await repo.add(sub1)
    add_r = await repo.add(sub2)
    assert add_r.is_failure
    assert add_r.error == "OwnerAlreadyHasSubscription"


async def test_update_persists_changes(db_session):
    repo = SQLAlchemyOwnerSubscriptionRepository(db_session)
    sub = OwnerSubscription.create_trialing(
        owner_id=uuid4(), trial_duration_days=3, now=_now(),
    ).value
    await repo.add(sub)
    sub.transition_to(SubStatus.ACTIVE, now=_now() + timedelta(hours=1), trial_duration_days=3)
    update_r = await repo.update(sub)
    assert update_r.is_success
    fetched = await repo.get_by_owner_id(sub.owner_id)
    assert fetched.status is SubStatus.ACTIVE
    assert fetched.trial_ends_at is None


async def test_list_trialing_with_expiry_before(db_session):
    repo = SQLAlchemyOwnerSubscriptionRepository(db_session)
    now = _now()
    expired = OwnerSubscription.create_trialing(
        owner_id=uuid4(), trial_duration_days=3, now=now - timedelta(days=10),
    ).value
    fresh = OwnerSubscription.create_trialing(
        owner_id=uuid4(), trial_duration_days=3, now=now,
    ).value
    other = OwnerSubscription(
        owner_id=uuid4(), status=SubStatus.ACTIVE,
        status_changed_at=now, trial_ends_at=None,
    )
    for s in (expired, fresh, other):
        await repo.add(s)
    rows = await repo.list_trialing_with_expiry_before(now)
    assert len(rows) == 1
    assert rows[0].id == expired.id


async def test_list_all_filters_by_status(db_session):
    repo = SQLAlchemyOwnerSubscriptionRepository(db_session)
    now = _now()
    await repo.add(OwnerSubscription(
        owner_id=uuid4(), status=SubStatus.ACTIVE,
        status_changed_at=now, trial_ends_at=None,
    ))
    await repo.add(OwnerSubscription(
        owner_id=uuid4(), status=SubStatus.INACTIVE,
        status_changed_at=now, trial_ends_at=None,
    ))
    rows = await repo.list_all(status="ACTIVE", limit=50, offset=0)
    assert len(rows) == 1
    assert rows[0].status is SubStatus.ACTIVE


async def test_list_by_owner_ids(db_session):
    repo = SQLAlchemyOwnerSubscriptionRepository(db_session)
    a_id, b_id, c_id = uuid4(), uuid4(), uuid4()
    sub_a = OwnerSubscription.create_trialing(
        owner_id=a_id, trial_duration_days=3, now=_now(),
    ).value
    sub_b = OwnerSubscription.create_trialing(
        owner_id=b_id, trial_duration_days=3, now=_now(),
    ).value
    await repo.add(sub_a)
    await repo.add(sub_b)
    await db_session.flush()

    found = await repo.list_by_owner_ids([a_id, b_id, c_id])
    assert {s.owner_id for s in found} == {a_id, b_id}

    empty = await repo.list_by_owner_ids([])
    assert empty == []
