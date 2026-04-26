from __future__ import annotations
import pytest

from app.domain.shared.weekday import Weekday
from app.use_cases.resources.commands.replace_operating_hours import (
    ReplaceOperatingHoursCommand,
    ReplaceOperatingHoursHandler,
)
from app.use_cases.resources.commands.create_resource import (
    OperatingHoursInput, TimeWindowInput,
)
from tests.unit.use_cases.resources.fakes.in_memory_resource_repository import InMemoryResourceRepository
from tests.unit.use_cases.resources.fixtures import seed_resource


@pytest.mark.asyncio
async def test_replace_hours_happy():
    repo = InMemoryResourceRepository()
    res, _, _ = await seed_resource(repo)
    handler = ReplaceOperatingHoursHandler(repo)
    cmd = ReplaceOperatingHoursCommand(
        actor_id=res.owner_id, resource_id=res.id,
        operating_hours=OperatingHoursInput(days={
            Weekday.FRIDAY: [TimeWindowInput(start="18:00", end="23:00")],
        }),
    )
    r = await handler.handle(cmd)
    assert r.is_success
    fetched = await repo.get_by_id(res.id)
    assert len(fetched.operating_hours.for_weekday(Weekday.FRIDAY)) == 1


@pytest.mark.asyncio
async def test_replace_hours_invalid_alignment():
    repo = InMemoryResourceRepository()
    res, _, _ = await seed_resource(repo)
    handler = ReplaceOperatingHoursHandler(repo)
    cmd = ReplaceOperatingHoursCommand(
        actor_id=res.owner_id, resource_id=res.id,
        operating_hours=OperatingHoursInput(days={
            Weekday.FRIDAY: [TimeWindowInput(start="08:30", end="22:00")],
        }),
    )
    r = await handler.handle(cmd)
    assert r.is_failure
    fields = {e.field for e in r.details}
    assert any(f.startswith("operating_hours.") for f in fields)
