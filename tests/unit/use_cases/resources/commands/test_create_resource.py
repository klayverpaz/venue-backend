from __future__ import annotations
from datetime import time
from uuid import uuid4

import pytest

from app.domain.accounts.role import Role
from app.domain.accounts.user import User
from app.domain.catalog.attribute import AttrType, AttributeDefinition
from app.domain.catalog.resource_type import ResourceType
from app.domain.shared.weekday import Weekday
from app.use_cases.resources.commands.create_resource import (
    CreateResourceCommand,
    CreateResourceHandler,
    PricingRuleInput,
    CustomAttributeInput,
    OperatingHoursInput,
    TimeWindowInput,
)
from tests.unit.use_cases.resources.fakes.in_memory_resource_repository import InMemoryResourceRepository
from tests.unit.use_cases.catalog.fakes.in_memory_resource_type_repository import (
    InMemoryResourceTypeRepository,
)
from tests.unit.use_cases.accounts.fakes.in_memory_user_repository import InMemoryUserRepository


def _hours_dict_full_open() -> dict[str, list[dict]]:
    return {wd.value.lower(): [{"start": "08:00", "end": "22:00"}] for wd in Weekday}


def _make_owner_and_type():
    owner = User.create(
        email="o@example.com", password_hash="x", role=Role.OWNER,
        full_name="O", phone=None, public_slug="o-owner",
    ).value
    rt = ResourceType.create(
        slug="football-field", name="Football", description="",
        attribute_schema=[
            AttributeDefinition.create(
                key="surface_type", label="Surface", data_type=AttrType.ENUM,
                required=True, enum_values=["GRASS", "SAND"],
            ).value,
        ],
    ).value
    return owner, rt


@pytest.mark.asyncio
async def test_create_resource_happy_path():
    owner, rt = _make_owner_and_type()
    users = InMemoryUserRepository()
    rts = InMemoryResourceTypeRepository()
    resources = InMemoryResourceRepository()
    await users.add(owner)
    await rts.add(rt)

    handler = CreateResourceHandler(resources, rts, users)
    cmd = CreateResourceCommand(
        actor_id=owner.id,
        resource_type_id=rt.id,
        slug="arena-zl",
        name="Arena ZL",
        description="campo society",
        city="São Paulo",
        region="SP",
        timezone="America/Sao_Paulo",
        slot_duration_minutes=60,
        operating_hours=OperatingHoursInput(
            days={Weekday.MONDAY: [TimeWindowInput(start="08:00", end="22:00")]},
        ),
        base_price_cents=8000,
        customer_cancellation_cutoff_hours=24,
        base_attributes={"surface_type": "GRASS"},
        pricing_rules=[],
        custom_attributes=[],
    )
    r = await handler.handle(cmd)
    assert r.is_success
    dto = r.value
    assert dto.slug == "arena-zl"
    assert dto.owner_slug == "o-owner"
    assert dto.resource_type_slug == "football-field"


@pytest.mark.asyncio
async def test_create_resource_validates_base_attributes_against_schema():
    owner, rt = _make_owner_and_type()
    users = InMemoryUserRepository()
    rts = InMemoryResourceTypeRepository()
    await users.add(owner)
    await rts.add(rt)
    handler = CreateResourceHandler(InMemoryResourceRepository(), rts, users)
    cmd = CreateResourceCommand(
        actor_id=owner.id,
        resource_type_id=rt.id,
        slug="arena",
        name="Arena",
        description="",
        city="SP",
        region="SP",
        timezone="America/Sao_Paulo",
        slot_duration_minutes=60,
        operating_hours=OperatingHoursInput(
            days={Weekday.MONDAY: [TimeWindowInput(start="08:00", end="22:00")]},
        ),
        base_price_cents=8000,
        customer_cancellation_cutoff_hours=24,
        base_attributes={},  # surface_type required by schema → should fail
        pricing_rules=[],
        custom_attributes=[],
    )
    r = await handler.handle(cmd)
    assert r.is_failure
    fields = {e.field for e in r.details}
    assert "base_attributes.surface_type" in fields


@pytest.mark.asyncio
async def test_create_resource_aggregates_resource_and_attribute_errors():
    owner, rt = _make_owner_and_type()
    users = InMemoryUserRepository()
    rts = InMemoryResourceTypeRepository()
    await users.add(owner)
    await rts.add(rt)
    handler = CreateResourceHandler(InMemoryResourceRepository(), rts, users)
    cmd = CreateResourceCommand(
        actor_id=owner.id,
        resource_type_id=rt.id,
        slug="UPPER!!!",   # invalid slug
        name="",            # invalid name
        description="",
        city="SP",
        region="SP",
        timezone="America/Sao_Paulo",
        slot_duration_minutes=60,
        operating_hours=OperatingHoursInput(
            days={Weekday.MONDAY: [TimeWindowInput(start="08:00", end="22:00")]},
        ),
        base_price_cents=8000,
        customer_cancellation_cutoff_hours=24,
        base_attributes={},  # missing required surface_type
        pricing_rules=[],
        custom_attributes=[],
    )
    r = await handler.handle(cmd)
    assert r.is_failure
    fields = {e.field for e in r.details}
    assert "slug" in fields
    assert "name" in fields
    assert "base_attributes.surface_type" in fields


@pytest.mark.asyncio
async def test_create_resource_rejects_inactive_resource_type():
    owner, rt = _make_owner_and_type()
    rt.deactivate()
    users = InMemoryUserRepository()
    rts = InMemoryResourceTypeRepository()
    await users.add(owner)
    await rts.add(rt)
    handler = CreateResourceHandler(InMemoryResourceRepository(), rts, users)
    cmd = CreateResourceCommand(
        actor_id=owner.id,
        resource_type_id=rt.id,
        slug="arena",
        name="Arena", description="",
        city="SP", region="SP",
        timezone="America/Sao_Paulo",
        slot_duration_minutes=60,
        operating_hours=OperatingHoursInput(days={}),
        base_price_cents=8000,
        customer_cancellation_cutoff_hours=24,
        base_attributes={"surface_type": "GRASS"},
        pricing_rules=[],
        custom_attributes=[],
    )
    r = await handler.handle(cmd)
    assert r.is_failure
    assert r.error == "ResourceTypeInactive"
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_create_resource_rejects_non_owner_actor():
    customer = User.create(
        email="c@example.com", password_hash="x", role=Role.CUSTOMER,
        full_name="C", phone=None, public_slug=None,
    ).value
    _, rt = _make_owner_and_type()
    users = InMemoryUserRepository()
    rts = InMemoryResourceTypeRepository()
    await users.add(customer)
    await rts.add(rt)
    handler = CreateResourceHandler(InMemoryResourceRepository(), rts, users)
    cmd = CreateResourceCommand(
        actor_id=customer.id,
        resource_type_id=rt.id,
        slug="arena",
        name="Arena", description="",
        city="SP", region="SP",
        timezone="America/Sao_Paulo",
        slot_duration_minutes=60,
        operating_hours=OperatingHoursInput(days={}),
        base_price_cents=8000,
        customer_cancellation_cutoff_hours=24,
        base_attributes={"surface_type": "GRASS"},
        pricing_rules=[],
        custom_attributes=[],
    )
    r = await handler.handle(cmd)
    assert r.is_failure
    assert r.error == "UserIsNotOwner"
    assert r.status_code == 403
