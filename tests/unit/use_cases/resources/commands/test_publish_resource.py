import pytest

from app.use_cases.resources.commands.publish_resource import (
    PublishResourceCommand, PublishResourceHandler,
    UnpublishResourceCommand, UnpublishResourceHandler,
)
from tests.unit.use_cases.resources.fakes.in_memory_resource_repository import InMemoryResourceRepository
from tests.unit.use_cases.resources.fixtures import seed_resource


@pytest.mark.asyncio
async def test_publish_then_unpublish():
    repo = InMemoryResourceRepository()
    res, _, _ = await seed_resource(repo)
    pub = PublishResourceHandler(repo)
    unpub = UnpublishResourceHandler(repo)

    r = await pub.handle(PublishResourceCommand(actor_id=res.owner_id, resource_id=res.id))
    assert r.is_success
    fetched = await repo.get_by_id(res.id)
    assert fetched.is_published is True

    r = await unpub.handle(UnpublishResourceCommand(actor_id=res.owner_id, resource_id=res.id))
    assert r.is_success
    fetched = await repo.get_by_id(res.id)
    assert fetched.is_published is False
