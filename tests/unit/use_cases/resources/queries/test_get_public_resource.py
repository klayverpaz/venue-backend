from __future__ import annotations
from datetime import datetime, timezone

import pytest

from app.domain.accounts.role import Role
from app.domain.accounts.user import User
from app.domain.catalog.resource_type import ResourceType
from app.domain.subscriptions.owner_subscription import OwnerSubscription
from app.domain.subscriptions.sub_status import SubStatus
from app.use_cases.resources.queries.get_public_resource import (
    GetPublicResourceHandler, GetPublicResourceQuery,
)
from tests.unit.use_cases.accounts.fakes.in_memory_user_repository import InMemoryUserRepository
from tests.unit.use_cases.catalog.fakes.in_memory_resource_type_repository import InMemoryResourceTypeRepository
from tests.unit.use_cases.ratings.fakes.in_memory_rating_repository import InMemoryRatingRepository
from tests.unit.use_cases.resources.fakes.in_memory_resource_repository import InMemoryResourceRepository
from tests.unit.use_cases.subscriptions.fakes.in_memory_subscription_repository import InMemorySubscriptionRepository
from tests.unit.use_cases.resources.fixtures import seed_resource


def _now() -> datetime:
    return datetime(2026, 4, 26, 12, 0, 0, tzinfo=timezone.utc)


async def _build_environment(*, sub_status=SubStatus.ACTIVE, user_active=True, published=True):
    repo = InMemoryResourceRepository()
    res, _, _ = await seed_resource(repo, slug="arena-zl")
    if published:
        res.publish()
        await repo.update(res)
    users = InMemoryUserRepository()
    owner = User.create(
        email="o@example.com", password_hash="x", role=Role.OWNER,
        full_name="Owner", phone=None, public_slug="o-slug",
    ).value
    owner.id = res.owner_id
    if not user_active:
        owner.deactivate()
    await users.add(owner)
    rts = InMemoryResourceTypeRepository()
    rt = ResourceType.create(
        slug="football-field", name="F", description="", attribute_schema=[],
    ).value
    rt.id = res.resource_type_id
    await rts.add(rt)
    subs = InMemorySubscriptionRepository()
    sub = OwnerSubscription.create_trialing(
        owner_id=res.owner_id, trial_duration_days=3, now=_now(),
    ).value
    if sub_status is not SubStatus.TRIALING:
        sub.transition_to(sub_status, now=_now(), trial_duration_days=3)
    await subs.add(sub)
    return repo, users, rts, subs, res


@pytest.mark.asyncio
async def test_get_public_resource_happy():
    repo, users, rts, subs, res = await _build_environment(sub_status=SubStatus.ACTIVE)
    handler = GetPublicResourceHandler(repo, users, rts, subs, InMemoryRatingRepository())
    r = await handler.handle(GetPublicResourceQuery(
        owner_slug="o-slug", resource_slug="arena-zl",
    ))
    assert r.is_success
    assert r.value.slug == "arena-zl"


@pytest.mark.asyncio
async def test_get_public_resource_404_when_owner_inactive_subscription():
    repo, users, rts, subs, res = await _build_environment(sub_status=SubStatus.INACTIVE)
    handler = GetPublicResourceHandler(repo, users, rts, subs, InMemoryRatingRepository())
    r = await handler.handle(GetPublicResourceQuery(
        owner_slug="o-slug", resource_slug="arena-zl",
    ))
    assert r.is_failure
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_get_public_resource_404_when_user_deactivated():
    repo, users, rts, subs, res = await _build_environment(user_active=False)
    handler = GetPublicResourceHandler(repo, users, rts, subs, InMemoryRatingRepository())
    r = await handler.handle(GetPublicResourceQuery(
        owner_slug="o-slug", resource_slug="arena-zl",
    ))
    assert r.is_failure
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_get_public_resource_404_when_unpublished():
    repo, users, rts, subs, res = await _build_environment(published=False)
    handler = GetPublicResourceHandler(repo, users, rts, subs, InMemoryRatingRepository())
    r = await handler.handle(GetPublicResourceQuery(
        owner_slug="o-slug", resource_slug="arena-zl",
    ))
    assert r.is_failure
    assert r.status_code == 404
