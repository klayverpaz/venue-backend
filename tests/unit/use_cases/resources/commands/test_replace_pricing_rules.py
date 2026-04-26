from __future__ import annotations
import pytest

from app.domain.resources.resource import Resource
from app.domain.shared.weekday import Weekday
from app.use_cases.resources.commands.create_resource import (
    PricingRuleInput, TimeWindowInput,
)
from app.use_cases.resources.commands.replace_pricing_rules import (
    ReplacePricingRulesCommand,
    ReplacePricingRulesHandler,
)
from tests.unit.use_cases.resources.fakes.in_memory_resource_repository import InMemoryResourceRepository
from tests.unit.use_cases.resources.fixtures import seed_resource


@pytest.mark.asyncio
async def test_replace_rules_happy():
    repo = InMemoryResourceRepository()
    res, _, _ = await seed_resource(repo)
    handler = ReplacePricingRulesHandler(repo)
    cmd = ReplacePricingRulesCommand(
        actor_id=res.owner_id, resource_id=res.id,
        pricing_rules=[
            PricingRuleInput(
                weekdays=[Weekday.MONDAY],
                window=TimeWindowInput(start="18:00", end="22:00"),
                price_cents=12000,
            ),
        ],
    )
    r = await handler.handle(cmd)
    assert r.is_success
    fetched = await repo.get_by_id(res.id)
    assert len(fetched.pricing_rules) == 1


@pytest.mark.asyncio
async def test_replace_rules_overlap_rejected():
    repo = InMemoryResourceRepository()
    res, _, _ = await seed_resource(repo)
    handler = ReplacePricingRulesHandler(repo)
    cmd = ReplacePricingRulesCommand(
        actor_id=res.owner_id, resource_id=res.id,
        pricing_rules=[
            PricingRuleInput(
                weekdays=[Weekday.MONDAY],
                window=TimeWindowInput(start="08:00", end="14:00"),
                price_cents=5000,
            ),
            PricingRuleInput(
                weekdays=[Weekday.MONDAY],
                window=TimeWindowInput(start="13:00", end="22:00"),
                price_cents=10000,
            ),
        ],
    )
    r = await handler.handle(cmd)
    assert r.is_failure
    codes = {e.code for e in r.details}
    assert Resource.PRICING_RULES_OVERLAP in codes
