from __future__ import annotations
from uuid import uuid4

import pytest

from app.use_cases.resources.commands.update_resource_metadata import (
    UpdateResourceMetadataCommand,
    UpdateResourceMetadataHandler,
)
from tests.unit.use_cases.resources.fakes.in_memory_resource_repository import InMemoryResourceRepository
from tests.unit.use_cases.resources.fixtures import seed_resource


@pytest.mark.asyncio
async def test_update_metadata_happy_path():
    repo = InMemoryResourceRepository()
    res, owner_slug, rt_slug = await seed_resource(repo)
    handler = UpdateResourceMetadataHandler(repo)
    cmd = UpdateResourceMetadataCommand(
        actor_id=res.owner_id,
        resource_id=res.id,
        name="Novo Nome",
        city=None,
        region=None,
        description=None,
    )
    r = await handler.handle(cmd)
    assert r.is_success


@pytest.mark.asyncio
async def test_update_metadata_404_for_non_owner():
    repo = InMemoryResourceRepository()
    res, _, _ = await seed_resource(repo)
    handler = UpdateResourceMetadataHandler(repo)
    cmd = UpdateResourceMetadataCommand(
        actor_id=uuid4(),
        resource_id=res.id,
        name="X", city=None, region=None, description=None,
    )
    r = await handler.handle(cmd)
    assert r.is_failure
    assert r.error == "ResourceNotFound"
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_update_metadata_aggregates_field_errors():
    repo = InMemoryResourceRepository()
    res, _, _ = await seed_resource(repo)
    handler = UpdateResourceMetadataHandler(repo)
    cmd = UpdateResourceMetadataCommand(
        actor_id=res.owner_id,
        resource_id=res.id,
        name="",
        city="",
        region=None,
        description=None,
    )
    r = await handler.handle(cmd)
    assert r.is_failure
    fields = {e.field for e in r.details}
    assert "name" in fields
    assert "city" in fields
