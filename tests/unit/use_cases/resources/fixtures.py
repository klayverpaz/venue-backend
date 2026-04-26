from __future__ import annotations
from datetime import time
from uuid import uuid4

from app.domain.resources.resource import Resource
from app.domain.resources.weekly_schedule import WeeklySchedule
from app.domain.shared.value_objects.time_window import TimeWindow
from app.domain.shared.weekday import Weekday
from tests.unit.use_cases.resources.fakes.in_memory_resource_repository import InMemoryResourceRepository


def _w(sh: int, eh: int) -> TimeWindow:
    return TimeWindow.create(time(sh, 0), time(eh, 0)).value


async def seed_resource(repo: InMemoryResourceRepository, *, owner_id=None, slug="arena-zl"):
    """Insert a valid Resource and return (resource, owner_slug, rt_slug)."""
    owner_id = owner_id or uuid4()
    rt_id = uuid4()
    ws = WeeklySchedule.create(
        slot_duration_minutes=60,
        days={Weekday.MONDAY: [_w(8, 22)]},
    ).value
    res = Resource.create(
        owner_id=owner_id, resource_type_id=rt_id,
        slug=slug, name="Arena", description="",
        city="São Paulo", region="SP",
        timezone="America/Sao_Paulo",
        slot_duration_minutes=60,
        operating_hours=ws,
        base_price_cents=8000,
        customer_cancellation_cutoff_hours=24,
        base_attributes={},
        pricing_rules=[],
        custom_attributes=[],
    ).value
    await repo.add(res)
    return res, "owner-slug", "type-slug"
