from __future__ import annotations
import pytest

from app.use_cases.resources.commands.create_resource import CustomAttributeInput
from app.use_cases.resources.commands.replace_custom_attributes import (
    ReplaceCustomAttributesCommand,
    ReplaceCustomAttributesHandler,
)
from tests.unit.use_cases.resources.fakes.in_memory_resource_repository import InMemoryResourceRepository
from tests.unit.use_cases.resources.fixtures import seed_resource


@pytest.mark.asyncio
async def test_replace_custom_attributes_happy():
    repo = InMemoryResourceRepository()
    res, _, _ = await seed_resource(repo)
    handler = ReplaceCustomAttributesHandler(repo)
    cmd = ReplaceCustomAttributesCommand(
        actor_id=res.owner_id, resource_id=res.id,
        custom_attributes=[
            CustomAttributeInput(key="wifi", label="Wi-Fi", value="sim"),
            CustomAttributeInput(key="parking", label="Estacionamento", value="50 vagas"),
        ],
    )
    r = await handler.handle(cmd)
    assert r.is_success
    fetched = await repo.get_by_id(res.id)
    assert len(fetched.custom_attributes) == 2


@pytest.mark.asyncio
async def test_replace_custom_attributes_aggregates_errors():
    repo = InMemoryResourceRepository()
    res, _, _ = await seed_resource(repo)
    handler = ReplaceCustomAttributesHandler(repo)
    cmd = ReplaceCustomAttributesCommand(
        actor_id=res.owner_id, resource_id=res.id,
        custom_attributes=[
            CustomAttributeInput(key="!!!", label="", value=""),
            CustomAttributeInput(key="wifi", label="Wi-Fi", value="x" * 600),
        ],
    )
    r = await handler.handle(cmd)
    assert r.is_failure
    fields = {e.field for e in r.details}
    assert any(f.startswith("custom_attributes[0]") for f in fields)
    assert any(f.startswith("custom_attributes[1]") for f in fields)
