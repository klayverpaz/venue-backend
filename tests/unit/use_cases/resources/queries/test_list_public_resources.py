from __future__ import annotations
from datetime import datetime, timezone

import pytest

from app.domain.accounts.role import Role
from app.domain.accounts.user import User
from app.domain.catalog.resource_type import ResourceType
from app.domain.subscriptions.owner_subscription import OwnerSubscription
from app.domain.subscriptions.sub_status import SubStatus
from app.use_cases.resources.queries.list_public_resources import (
    ListPublicResourcesHandler, ListPublicResourcesQuery,
)
from tests.unit.use_cases.accounts.fakes.in_memory_user_repository import InMemoryUserRepository
from tests.unit.use_cases.catalog.fakes.in_memory_resource_type_repository import InMemoryResourceTypeRepository
from tests.unit.use_cases.ratings.fakes.in_memory_rating_repository import InMemoryRatingRepository
from tests.unit.use_cases.resources.fakes.in_memory_resource_repository import InMemoryResourceRepository
from tests.unit.use_cases.subscriptions.fakes.in_memory_subscription_repository import InMemorySubscriptionRepository
from tests.unit.use_cases.resources.fixtures import seed_resource


def _now() -> datetime:
    return datetime(2026, 4, 26, 12, 0, 0, tzinfo=timezone.utc)


async def _seed(*, owner_slug: str, sub_status: SubStatus, slug: str):
    user = User.create(
        email=f"{owner_slug}@example.com", password_hash="x", role=Role.OWNER,
        full_name="O", phone=None, public_slug=owner_slug,
    ).value
    sub = OwnerSubscription.create_trialing(
        owner_id=user.id, trial_duration_days=3, now=_now(),
    ).value
    if sub_status is not SubStatus.TRIALING:
        sub.transition_to(sub_status, now=_now(), trial_duration_days=3)
    return user, sub, slug


@pytest.mark.asyncio
async def test_list_public_filters_by_operational_owner():
    repo = InMemoryResourceRepository()
    users = InMemoryUserRepository()
    rts = InMemoryResourceTypeRepository()
    subs = InMemorySubscriptionRepository()

    rt = ResourceType.create(
        slug="football-field", name="F", description="", attribute_schema=[],
    ).value
    await rts.add(rt)

    owner_a, sub_a, slug_a = await _seed(owner_slug="owner-a", sub_status=SubStatus.ACTIVE, slug="arena-a")
    await users.add(owner_a)
    await subs.add(sub_a)
    res_a, _, _ = await seed_resource(repo, owner_id=owner_a.id, slug=slug_a)
    res_a.resource_type_id = rt.id
    res_a.publish()
    await repo.update(res_a)

    owner_b, sub_b, slug_b = await _seed(owner_slug="owner-b", sub_status=SubStatus.INACTIVE, slug="arena-b")
    await users.add(owner_b)
    await subs.add(sub_b)
    res_b, _, _ = await seed_resource(repo, owner_id=owner_b.id, slug=slug_b)
    res_b.resource_type_id = rt.id
    res_b.publish()
    await repo.update(res_b)

    handler = ListPublicResourcesHandler(repo, users, rts, subs, InMemoryRatingRepository())
    r = await handler.handle(ListPublicResourcesQuery())
    assert r.is_success
    slugs = {dto.slug for dto in r.value}
    assert slugs == {"arena-a"}
