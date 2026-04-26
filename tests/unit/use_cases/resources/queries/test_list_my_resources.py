from __future__ import annotations
import pytest

from app.domain.accounts.role import Role
from app.domain.accounts.user import User
from app.domain.catalog.resource_type import ResourceType
from app.use_cases.resources.queries.list_my_resources import (
    ListMyResourcesHandler, ListMyResourcesQuery,
)
from tests.unit.use_cases.accounts.fakes.in_memory_user_repository import InMemoryUserRepository
from tests.unit.use_cases.catalog.fakes.in_memory_resource_type_repository import InMemoryResourceTypeRepository
from tests.unit.use_cases.resources.fakes.in_memory_resource_repository import InMemoryResourceRepository
from tests.unit.use_cases.resources.fixtures import seed_resource


@pytest.mark.asyncio
async def test_list_my_resources_includes_drafts_excludes_deleted():
    repo = InMemoryResourceRepository()
    res_a, _, _ = await seed_resource(repo, slug="r-a")
    res_b, _, _ = await seed_resource(repo, owner_id=res_a.owner_id, slug="r-b")
    res_c, _, _ = await seed_resource(repo, owner_id=res_a.owner_id, slug="r-c")
    res_b.publish()
    from datetime import datetime, timezone
    res_c.soft_delete(now=datetime.now(timezone.utc))
    await repo.update(res_b)
    await repo.update(res_c)

    users = InMemoryUserRepository()
    owner = User.create(
        email="o@example.com", password_hash="x", role=Role.OWNER,
        full_name="O", phone=None, public_slug="o-slug",
    ).value
    owner.id = res_a.owner_id
    await users.add(owner)

    rts = InMemoryResourceTypeRepository()
    rt = ResourceType.create(
        slug="rt", name="RT", description="", attribute_schema=[],
    ).value
    rt.id = res_a.resource_type_id
    await rts.add(rt)

    handler = ListMyResourcesHandler(repo, users, rts)
    r = await handler.handle(ListMyResourcesQuery(actor_id=res_a.owner_id))
    assert r.is_success
    slugs = {dto.slug for dto in r.value}
    assert slugs == {"r-a", "r-b"}  # draft included; deleted excluded
