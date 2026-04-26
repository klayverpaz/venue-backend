import pytest

from app.use_cases.resources.commands.set_base_price import (
    SetBasePriceCommand, SetBasePriceHandler,
)
from tests.unit.use_cases.resources.fakes.in_memory_resource_repository import InMemoryResourceRepository
from tests.unit.use_cases.resources.fixtures import seed_resource


@pytest.mark.asyncio
async def test_set_base_price_happy():
    repo = InMemoryResourceRepository()
    res, _, _ = await seed_resource(repo)
    handler = SetBasePriceHandler(repo)
    r = await handler.handle(SetBasePriceCommand(
        actor_id=res.owner_id, resource_id=res.id, base_price_cents=15000,
    ))
    assert r.is_success
    fetched = await repo.get_by_id(res.id)
    assert fetched.base_price_cents.cents == 15000


@pytest.mark.asyncio
async def test_set_base_price_invalid_money():
    repo = InMemoryResourceRepository()
    res, _, _ = await seed_resource(repo)
    handler = SetBasePriceHandler(repo)
    r = await handler.handle(SetBasePriceCommand(
        actor_id=res.owner_id, resource_id=res.id, base_price_cents=-1,
    ))
    assert r.is_failure
    assert r.status_code == 400
