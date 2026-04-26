import pytest

from app.use_cases.resources.commands.soft_delete_resource import (
    SoftDeleteResourceCommand, SoftDeleteResourceHandler,
)
from tests.unit.use_cases.resources.fakes.in_memory_resource_repository import InMemoryResourceRepository
from tests.unit.use_cases.resources.fixtures import seed_resource


@pytest.mark.asyncio
async def test_soft_delete_happy():
    repo = InMemoryResourceRepository()
    res, _, _ = await seed_resource(repo)
    handler = SoftDeleteResourceHandler(repo)
    r = await handler.handle(SoftDeleteResourceCommand(
        actor_id=res.owner_id, resource_id=res.id,
    ))
    assert r.is_success
    r2 = await handler.handle(SoftDeleteResourceCommand(
        actor_id=res.owner_id, resource_id=res.id,
    ))
    assert r2.is_failure
    assert r2.error == "ResourceNotFound"
