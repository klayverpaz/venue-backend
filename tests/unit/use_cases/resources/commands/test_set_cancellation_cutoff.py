import pytest

from app.use_cases.resources.commands.set_cancellation_cutoff import (
    SetCancellationCutoffCommand, SetCancellationCutoffHandler,
)
from tests.unit.use_cases.resources.fakes.in_memory_resource_repository import InMemoryResourceRepository
from tests.unit.use_cases.resources.fixtures import seed_resource


@pytest.mark.asyncio
async def test_set_cutoff_happy():
    repo = InMemoryResourceRepository()
    res, _, _ = await seed_resource(repo)
    handler = SetCancellationCutoffHandler(repo)
    r = await handler.handle(SetCancellationCutoffCommand(
        actor_id=res.owner_id, resource_id=res.id, hours=48,
    ))
    assert r.is_success
    fetched = await repo.get_by_id(res.id)
    assert fetched.customer_cancellation_cutoff_hours.hours == 48


@pytest.mark.asyncio
async def test_set_cutoff_out_of_range():
    repo = InMemoryResourceRepository()
    res, _, _ = await seed_resource(repo)
    handler = SetCancellationCutoffHandler(repo)
    r = await handler.handle(SetCancellationCutoffCommand(
        actor_id=res.owner_id, resource_id=res.id, hours=999,
    ))
    assert r.is_failure
    assert r.status_code == 400
