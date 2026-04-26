from __future__ import annotations
from datetime import datetime, timezone

import pytest

from app.domain.accounts.role import Role
from app.domain.accounts.user import User
from app.domain.catalog.resource_type import ResourceType
from app.domain.subscriptions.owner_subscription import OwnerSubscription
from app.domain.subscriptions.sub_status import SubStatus
from app.use_cases.accounts.queries.get_owner_public_page import (
    GetOwnerPublicPageHandler, GetOwnerPublicPageQuery,
)
from tests.unit.use_cases.accounts.fakes.in_memory_user_repository import InMemoryUserRepository
from tests.unit.use_cases.catalog.fakes.in_memory_resource_type_repository import InMemoryResourceTypeRepository
from tests.unit.use_cases.resources.fakes.in_memory_resource_repository import InMemoryResourceRepository
from tests.unit.use_cases.subscriptions.fakes.in_memory_subscription_repository import InMemorySubscriptionRepository
from tests.unit.use_cases.resources.fixtures import seed_resource


def _now() -> datetime:
    return datetime(2026, 4, 26, 12, 0, 0, tzinfo=timezone.utc)


async def _build():
    users = InMemoryUserRepository()
    subs = InMemorySubscriptionRepository()
    repo = InMemoryResourceRepository()
    rts = InMemoryResourceTypeRepository()
    owner = User.create(
        email="o@example.com", password_hash="x", role=Role.OWNER,
        full_name="Owner", phone=None, public_slug="o-slug",
    ).value
    await users.add(owner)
    sub = OwnerSubscription.create_trialing(
        owner_id=owner.id, trial_duration_days=3, now=_now(),
    ).value
    sub.transition_to(SubStatus.ACTIVE, now=_now(), trial_duration_days=3)
    await subs.add(sub)
    rt = ResourceType.create(
        slug="football-field", name="F", description="", attribute_schema=[],
    ).value
    await rts.add(rt)
    res, _, _ = await seed_resource(repo, owner_id=owner.id, slug="arena-1")
    res.resource_type_id = rt.id
    res.publish()
    await repo.update(res)
    return owner, repo, users, rts, subs


@pytest.mark.asyncio
async def test_get_owner_public_page_returns_owner_and_published_resources():
    owner, repo, users, rts, subs = await _build()
    handler = GetOwnerPublicPageHandler(users, subs, repo, rts)
    r = await handler.handle(GetOwnerPublicPageQuery(owner_slug="o-slug"))
    assert r.is_success
    page = r.value
    assert page.owner_slug == "o-slug"
    assert page.full_name == "Owner"
    assert len(page.resources) == 1


@pytest.mark.asyncio
async def test_get_owner_public_page_404_for_non_owner():
    users = InMemoryUserRepository()
    subs = InMemorySubscriptionRepository()
    repo = InMemoryResourceRepository()
    rts = InMemoryResourceTypeRepository()
    cust = User.create(
        email="c@example.com", password_hash="x", role=Role.CUSTOMER,
        full_name="C", phone=None, public_slug=None,
    ).value
    await users.add(cust)
    handler = GetOwnerPublicPageHandler(users, subs, repo, rts)
    r = await handler.handle(GetOwnerPublicPageQuery(owner_slug="not-found"))
    assert r.is_failure
    assert r.status_code == 404
