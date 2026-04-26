from __future__ import annotations
from uuid import uuid4

import pytest

from app.domain.accounts.role import Role
from app.domain.accounts.user import User
from app.domain.catalog.resource_type import ResourceType
from app.use_cases.resources.queries.get_my_resource import (
    GetMyResourceHandler, GetMyResourceQuery,
)
from tests.unit.use_cases.accounts.fakes.in_memory_user_repository import InMemoryUserRepository
from tests.unit.use_cases.catalog.fakes.in_memory_resource_type_repository import InMemoryResourceTypeRepository
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

    handler = GetMyResourceHandler(repo, users, rts)
    r = await handler.handle(GetMyResourceQuery(actor_id=res.owner_id, resource_id=res.id))
    assert r.is_success
    assert r.value.owner_slug == "my-owner"
    assert r.value.resource_type_slug == "my-type"


@pytest.mark.asyncio
async def test_get_my_resource_not_owned_returns_404():
    repo = InMemoryResourceRepository()
    res, _, _ = await seed_resource(repo)
    handler = GetMyResourceHandler(repo, InMemoryUserRepository(), InMemoryResourceTypeRepository())
    r = await handler.handle(GetMyResourceQuery(actor_id=uuid4(), resource_id=res.id))
    assert r.is_failure
    assert r.error == "ResourceNotFound"
    assert r.status_code == 404
