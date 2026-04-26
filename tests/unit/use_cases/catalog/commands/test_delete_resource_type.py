from __future__ import annotations
from uuid import uuid4
import pytest
from app.domain.catalog.resource_type import ResourceType
from app.use_cases.catalog.commands.delete_resource_type import (
    DeleteResourceTypeCommand,
    DeleteResourceTypeHandler,
)
from tests.unit.use_cases.catalog.fakes.in_memory_resource_type_repository import (
    InMemoryResourceTypeRepository,
)


pytestmark = pytest.mark.asyncio


async def test_delete_resource_type_success():
    repo = InMemoryResourceTypeRepository()
    rt = ResourceType.create(
        slug="football-field", name="Football Field", description="", attribute_schema=[],
    ).value
    await repo.add(rt)
    handler = DeleteResourceTypeHandler(repo)
    r = await handler.handle(DeleteResourceTypeCommand(id=rt.id))
    assert r.is_success
    assert (await repo.get_by_id(rt.id)) is None


async def test_delete_returns_not_found_for_missing_id():
    repo = InMemoryResourceTypeRepository()
    handler = DeleteResourceTypeHandler(repo)
    r = await handler.handle(DeleteResourceTypeCommand(id=uuid4()))
    assert r.is_failure
    assert r.error == "ResourceTypeNotFound"
