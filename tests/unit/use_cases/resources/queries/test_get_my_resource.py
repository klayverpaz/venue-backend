from __future__ import annotations
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from app.domain.accounts.role import Role
from app.domain.accounts.user import User
from app.domain.catalog.resource_type import ResourceType
from app.domain.ratings.rating import Rating
from app.domain.shared.value_objects.rating_score import RatingScore
from app.use_cases.resources.queries.get_my_resource import (
    GetMyResourceHandler, GetMyResourceQuery,
)
from tests.unit.use_cases.accounts.fakes.in_memory_user_repository import InMemoryUserRepository
from tests.unit.use_cases.catalog.fakes.in_memory_resource_type_repository import InMemoryResourceTypeRepository
from tests.unit.use_cases.ratings.fakes.in_memory_rating_repository import InMemoryRatingRepository
from tests.unit.use_cases.resources.fakes.in_memory_resource_repository import InMemoryResourceRepository
from tests.unit.use_cases.resources.fixtures import seed_resource


@pytest.mark.asyncio
async def test_get_my_resource_returns_dto():
    repo = InMemoryResourceRepository()
    res, _, _ = await seed_resource(repo)

    users = InMemoryUserRepository()
    owner = User.create(
        email="o@example.com", password_hash="x", role=Role.OWNER,
        full_name="O", phone=None, public_slug="my-owner",
    ).value
    owner.id = res.owner_id
    await users.add(owner)

    rts = InMemoryResourceTypeRepository()
    rt = ResourceType.create(
        slug="my-type", name="T", description="", attribute_schema=[],
    ).value
    rt.id = res.resource_type_id
    await rts.add(rt)

    handler = GetMyResourceHandler(repo, users, rts, InMemoryRatingRepository())
    r = await handler.handle(GetMyResourceQuery(actor_id=res.owner_id, resource_id=res.id))
    assert r.is_success
    assert r.value.owner_slug == "my-owner"
    assert r.value.resource_type_slug == "my-type"


@pytest.mark.asyncio
async def test_get_my_resource_not_owned_returns_404():
    repo = InMemoryResourceRepository()
    res, _, _ = await seed_resource(repo)
    handler = GetMyResourceHandler(repo, InMemoryUserRepository(), InMemoryResourceTypeRepository(), InMemoryRatingRepository())
    r = await handler.handle(GetMyResourceQuery(actor_id=uuid4(), resource_id=res.id))
    assert r.is_failure
    assert r.error == "ResourceNotFound"
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_get_my_resource_includes_rating_fields():
    """Retrofit: ResourceDto.rating_avg + rating_count are populated from the ratings repo."""
    repo = InMemoryResourceRepository()
    res, _, _ = await seed_resource(repo)

    users = InMemoryUserRepository()
    owner = User.create(
        email="o2@example.com", password_hash="x", role=Role.OWNER,
        full_name="O2", phone=None, public_slug="my-owner-2",
    ).value
    owner.id = res.owner_id
    await users.add(owner)

    rts = InMemoryResourceTypeRepository()
    rt = ResourceType.create(
        slug="my-type-2", name="T2", description="", attribute_schema=[],
    ).value
    rt.id = res.resource_type_id
    await rts.add(rt)

    now = datetime(2026, 4, 27, 12, 0, 0, tzinfo=timezone.utc)
    ratings = InMemoryRatingRepository()
    rating = Rating.create(
        booking_id=uuid4(),
        resource_id=res.id,
        customer_id=uuid4(),
        score=RatingScore.create(5).value,
        comment=None,
        now=now,
    )
    await ratings.add(rating)

    handler = GetMyResourceHandler(repo, users, rts, ratings)
    r = await handler.handle(GetMyResourceQuery(actor_id=res.owner_id, resource_id=res.id))
    assert r.is_success
    assert r.value.rating_avg == Decimal("5.0")
    assert r.value.rating_count == 1
