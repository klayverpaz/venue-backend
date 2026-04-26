import pytest

from app.use_cases.resources.commands.set_slot_duration import (
    SetSlotDurationCommand, SetSlotDurationHandler,
)
from tests.unit.use_cases.resources.fakes.in_memory_resource_repository import InMemoryResourceRepository
from tests.unit.use_cases.resources.fixtures import seed_resource


@pytest.mark.asyncio
async def test_set_slot_duration_happy():
    repo = InMemoryResourceRepository()
    res, _, _ = await seed_resource(repo)
    handler = SetSlotDurationHandler(repo)
    r = await handler.handle(SetSlotDurationCommand(
        actor_id=res.owner_id, resource_id=res.id, minutes=120,
    ))
    assert r.is_success
    fetched = await repo.get_by_id(res.id)
    assert fetched.slot_duration_minutes.minutes == 120


@pytest.mark.asyncio
async def test_set_slot_duration_invalid_value():
    repo = InMemoryResourceRepository()
    res, _, _ = await seed_resource(repo)
    handler = SetSlotDurationHandler(repo)
    r = await handler.handle(SetSlotDurationCommand(
        actor_id=res.owner_id, resource_id=res.id, minutes=37,
    ))
    assert r.is_failure
    assert r.status_code == 400
