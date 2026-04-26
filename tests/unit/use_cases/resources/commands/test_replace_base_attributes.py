from __future__ import annotations
import pytest

from app.domain.catalog.attribute import AttrType, AttributeDefinition
from app.domain.catalog.resource_type import ResourceType
from app.use_cases.resources.commands.replace_base_attributes import (
    ReplaceBaseAttributesCommand,
    ReplaceBaseAttributesHandler,
)
from tests.unit.use_cases.catalog.fakes.in_memory_resource_type_repository import InMemoryResourceTypeRepository
from tests.unit.use_cases.resources.fakes.in_memory_resource_repository import InMemoryResourceRepository
from tests.unit.use_cases.resources.fixtures import seed_resource


def _rt_with_required_surface() -> ResourceType:
    return ResourceType.create(
        slug="football-field", name="Football", description="",
        attribute_schema=[
            AttributeDefinition.create(
                key="surface_type", label="Surface", data_type=AttrType.ENUM,
                required=True, enum_values=["GRASS", "SAND"],
            ).value,
        ],
    ).value


@pytest.mark.asyncio
async def test_replace_base_attributes_happy():
    rts = InMemoryResourceTypeRepository()
    rt = _rt_with_required_surface()
    await rts.add(rt)
    repo = InMemoryResourceRepository()
    res, _, _ = await seed_resource(repo)
    res.resource_type_id = rt.id

    handler = ReplaceBaseAttributesHandler(repo, rts)
    cmd = ReplaceBaseAttributesCommand(
        actor_id=res.owner_id, resource_id=res.id,
        base_attributes={"surface_type": "GRASS"},
    )
    r = await handler.handle(cmd)
    assert r.is_success
    fetched = await repo.get_by_id(res.id)
    assert fetched.base_attributes == {"surface_type": "GRASS"}


@pytest.mark.asyncio
async def test_replace_base_attributes_schema_violation():
    rts = InMemoryResourceTypeRepository()
    rt = _rt_with_required_surface()
    await rts.add(rt)
    repo = InMemoryResourceRepository()
    res, _, _ = await seed_resource(repo)
    res.resource_type_id = rt.id

    handler = ReplaceBaseAttributesHandler(repo, rts)
    cmd = ReplaceBaseAttributesCommand(
        actor_id=res.owner_id, resource_id=res.id,
        base_attributes={"surface_type": "MARS_DUST"},
    )
    r = await handler.handle(cmd)
    assert r.is_failure
    fields = {e.field for e in r.details}
    assert "base_attributes.surface_type" in fields
