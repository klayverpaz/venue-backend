from __future__ import annotations
from datetime import datetime, time, timezone
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.accounts.role import Role
from app.domain.accounts.user import User
from app.domain.catalog.resource_type import ResourceType
from app.domain.resources.custom_attribute import CustomAttribute
from app.domain.resources.pricing_rule import PricingRule
from app.domain.resources.resource import Resource
from app.domain.resources.weekly_schedule import WeeklySchedule
from app.domain.shared.value_objects.money import Money
from app.domain.shared.value_objects.time_window import TimeWindow
from app.domain.shared.weekday import Weekday
from app.infrastructure.repositories.resource_repository import SQLAlchemyResourceRepository
from app.infrastructure.repositories.resource_type_repository import SQLAlchemyResourceTypeRepository
from app.infrastructure.repositories.user_repository import UserRepository


def _w(sh: int, eh: int) -> TimeWindow:
    return TimeWindow.create(time(sh, 0), time(eh, 0)).value


def _ws() -> WeeklySchedule:
    return WeeklySchedule.create(
        slot_duration_minutes=60,
        days={Weekday.MONDAY: [_w(8, 22)]},
    ).value


async def _seed_owner_and_type(db_session: AsyncSession) -> tuple[User, ResourceType]:
    users = UserRepository(db_session)
    rts = SQLAlchemyResourceTypeRepository(db_session)
    owner = User.create(
        email=f"{uuid4().hex}@example.com", password_hash="x", role=Role.OWNER,
        full_name="Owner Name", phone=None, public_slug=f"owner-{uuid4().hex[:6]}",
    ).value
    await users.add(owner)
    rt = ResourceType.create(
        slug=f"type-{uuid4().hex[:6]}", name="Type", description="",
        attribute_schema=[],
    ).value
    await rts.add(rt)
    await db_session.flush()
    return owner, rt


def _make_resource(owner_id, rt_id, slug="arena-x") -> Resource:
    return Resource.create(
        owner_id=owner_id,
        resource_type_id=rt_id,
        slug=slug,
        name="Arena X",
        description="campo society",
        city="São Paulo",
        region="SP",
        timezone="America/Sao_Paulo",
        slot_duration_minutes=60,
        operating_hours=_ws(),
        base_price_cents=8000,
        customer_cancellation_cutoff_hours=24,
        base_attributes={},
        pricing_rules=[],
        custom_attributes=[],
    ).value


@pytest.mark.asyncio
async def test_add_and_get_by_id(db_session: AsyncSession):
    owner, rt = await _seed_owner_and_type(db_session)
    repo = SQLAlchemyResourceRepository(db_session)
    res = _make_resource(owner.id, rt.id)
    add_r = await repo.add(res)
    assert add_r.is_success
    await db_session.flush()

    fetched = await repo.get_by_id(res.id)
    assert fetched is not None
    assert fetched.slug.value == "arena-x"
    assert fetched.owner_id == owner.id


@pytest.mark.asyncio
async def test_unique_owner_slug_constraint(db_session: AsyncSession):
    owner, rt = await _seed_owner_and_type(db_session)
    repo = SQLAlchemyResourceRepository(db_session)
    a = _make_resource(owner.id, rt.id, slug="arena-zl")
    b = _make_resource(owner.id, rt.id, slug="arena-zl")
    assert (await repo.add(a)).is_success
    await db_session.flush()
    r = await repo.add(b)
    assert r.is_failure
    assert r.error == "SlugAlreadyTaken"


@pytest.mark.asyncio
async def test_two_owners_can_share_slug(db_session: AsyncSession):
    owner_a, rt = await _seed_owner_and_type(db_session)
    owner_b, _ = await _seed_owner_and_type(db_session)
    repo = SQLAlchemyResourceRepository(db_session)
    a = _make_resource(owner_a.id, rt.id, slug="arena")
    b = _make_resource(owner_b.id, rt.id, slug="arena")
    assert (await repo.add(a)).is_success
    assert (await repo.add(b)).is_success
    await db_session.flush()


@pytest.mark.asyncio
async def test_round_trip_composites(db_session: AsyncSession):
    owner, rt = await _seed_owner_and_type(db_session)
    repo = SQLAlchemyResourceRepository(db_session)
    rule = PricingRule.create(
        weekdays=[Weekday.FRIDAY], window=_w(18, 22), price=Money.create(12000).value,
    ).value
    custom = CustomAttribute.create(key="wifi", label="Wi-Fi", value="sim").value
    res = Resource.create(
        owner_id=owner.id, resource_type_id=rt.id,
        slug="arena-rt", name="Arena RT", description="",
        city="São Paulo", region="SP", timezone="America/Sao_Paulo",
        slot_duration_minutes=60,
        operating_hours=WeeklySchedule.create(
            slot_duration_minutes=60,
            days={Weekday.FRIDAY: [_w(8, 23)]},
        ).value,
        base_price_cents=8000, customer_cancellation_cutoff_hours=24,
        base_attributes={"surface_type": "GRASS"},
        pricing_rules=[rule],
        custom_attributes=[custom],
    ).value
    await repo.add(res)
    await db_session.flush()

    fetched = await repo.get_by_id(res.id)
    assert fetched.pricing_rules[0].price.cents == 12000
    assert fetched.custom_attributes[0].key.value == "wifi"
    assert fetched.base_attributes == {"surface_type": "GRASS"}
    assert fetched.operating_hours.for_weekday(Weekday.FRIDAY)[0].start == time(8, 0)


@pytest.mark.asyncio
async def test_list_published_excludes_deleted_and_unpublished(db_session: AsyncSession):
    owner, rt = await _seed_owner_and_type(db_session)
    repo = SQLAlchemyResourceRepository(db_session)

    draft = _make_resource(owner.id, rt.id, slug="draft")  # not published
    published = _make_resource(owner.id, rt.id, slug="public")
    published.publish()
    deleted = _make_resource(owner.id, rt.id, slug="deleted")
    deleted.publish()
    deleted.soft_delete(now=datetime.now(timezone.utc))

    for r in (draft, published, deleted):
        await repo.add(r)
    await db_session.flush()
    for r in (draft, published, deleted):
        await repo.update(r)
    await db_session.flush()

    listed = await repo.list_published()
    slugs = {r.slug.value for r in listed}
    assert "public" in slugs
    assert "draft" not in slugs
    assert "deleted" not in slugs


@pytest.mark.asyncio
async def test_list_published_filters_by_owner_ids(db_session: AsyncSession):
    owner_a, rt = await _seed_owner_and_type(db_session)
    owner_b, _ = await _seed_owner_and_type(db_session)
    repo = SQLAlchemyResourceRepository(db_session)
    ra = _make_resource(owner_a.id, rt.id, slug="from-a")
    ra.publish()
    rb = _make_resource(owner_b.id, rt.id, slug="from-b")
    rb.publish()
    for r in (ra, rb):
        await repo.add(r)
    await db_session.flush()
    for r in (ra, rb):
        await repo.update(r)
    await db_session.flush()

    listed = await repo.list_published(owner_ids_filter=[owner_a.id])
    slugs = {r.slug.value for r in listed}
    assert slugs == {"from-a"}


@pytest.mark.asyncio
async def test_get_by_owner_slug_and_resource_slug(db_session: AsyncSession):
    owner, rt = await _seed_owner_and_type(db_session)
    repo = SQLAlchemyResourceRepository(db_session)
    res = _make_resource(owner.id, rt.id, slug="quadra-x")
    await repo.add(res)
    await db_session.flush()

    owner_slug_str = owner.public_slug.value

    # Hit: correct owner_slug + resource_slug
    fetched = await repo.get_by_owner_slug_and_resource_slug(
        owner_slug_str, "quadra-x",
    )
    assert fetched is not None
    assert fetched.id == res.id

    # Miss: wrong resource_slug
    missing = await repo.get_by_owner_slug_and_resource_slug(
        owner_slug_str, "nonexistent",
    )
    assert missing is None

    # Miss: wrong owner_slug
    missing2 = await repo.get_by_owner_slug_and_resource_slug(
        "wrong-owner", "quadra-x",
    )
    assert missing2 is None
