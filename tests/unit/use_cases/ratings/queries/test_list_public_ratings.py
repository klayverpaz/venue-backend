from __future__ import annotations
from datetime import datetime, time, timedelta, timezone
from uuid import uuid4

import pytest

from app.domain.ratings.rating import Rating
from app.domain.resources.resource import Resource
from app.domain.resources.weekly_schedule import WeeklySchedule
from app.domain.shared.value_objects.rating_score import RatingScore
from app.domain.shared.value_objects.short_description import ShortDescription
from app.domain.shared.value_objects.time_window import TimeWindow
from app.domain.shared.weekday import Weekday
from app.use_cases.ratings.queries.list_public_ratings import (
    ListPublicRatingsForResourceHandler,
    ListPublicRatingsForResourceQuery,
)
from tests.unit.use_cases.ratings.fakes.in_memory_rating_repository import (
    InMemoryRatingRepository,
)


pytestmark = pytest.mark.asyncio


def _now() -> datetime:
    return datetime(2026, 4, 28, 12, 0, 0, tzinfo=timezone.utc)


def _build_resource(*, owner_slug: str = "owner", resource_slug: str = "campo") -> Resource:
    """Plan 08 lessons: use time(...) and WeeklySchedule wrapper for Resource.create."""
    operating = {wd: [TimeWindow.create(time(6, 0), time(22, 0)).value] for wd in Weekday}
    schedule = WeeklySchedule.create(slot_duration_minutes=60, days=operating).value
    r = Resource.create(
        owner_id=uuid4(), resource_type_id=uuid4(),
        slug=resource_slug, name="Campo", description="",
        city="SP", region="SP", timezone="America/Sao_Paulo",
        slot_duration_minutes=60, base_price_cents=8000,
        customer_cancellation_cutoff_hours=24,
        operating_hours=schedule, pricing_rules=[],
        custom_attributes=[], base_attributes={},
    ).value
    r.publish()
    return r


class _FakeResourceRepo:
    """Adapts the get-by-(owner_slug, resource_slug) shape used by Plan 08 Task 20."""
    def __init__(self, resource: Resource | None):
        self._r = resource

    async def get_by_owner_slug_and_resource_slug(self, owner_slug, resource_slug):
        return self._r


async def test_returns_only_comment_bearing_for_resource():
    res = _build_resource()
    repo = InMemoryRatingRepository()
    note = ShortDescription.create("ótimo").value
    with_comment = Rating.create(
        booking_id=uuid4(), resource_id=res.id, customer_id=uuid4(),
        score=RatingScore.create(5).value, comment=note, now=_now(),
    )
    no_comment = Rating.create(
        booking_id=uuid4(), resource_id=res.id, customer_id=uuid4(),
        score=RatingScore.create(4).value, comment=None,
        now=_now() - timedelta(days=1),
    )
    other_resource = Rating.create(
        booking_id=uuid4(), resource_id=uuid4(), customer_id=uuid4(),
        score=RatingScore.create(5).value, comment=note, now=_now(),
    )
    await repo.add(with_comment)
    await repo.add(no_comment)
    await repo.add(other_resource)
    handler = ListPublicRatingsForResourceHandler(
        ratings=repo, resources=_FakeResourceRepo(res),
    )
    r = await handler.handle(ListPublicRatingsForResourceQuery(
        owner_slug="owner", resource_slug="campo",
    ))
    assert r.is_success
    items = r.value.items
    assert len(items) == 1
    assert items[0].score == 5
    assert items[0].comment == "ótimo"


async def test_unknown_resource_returns_404():
    handler = ListPublicRatingsForResourceHandler(
        ratings=InMemoryRatingRepository(),
        resources=_FakeResourceRepo(None),
    )
    r = await handler.handle(ListPublicRatingsForResourceQuery(
        owner_slug="missing", resource_slug="missing",
    ))
    assert r.is_failure
    assert r.error == "ResourceNotFound"
    assert r.status_code == 404


async def test_soft_deleted_resource_returns_404():
    res = _build_resource()
    res.soft_delete(now=_now() - timedelta(days=1))
    handler = ListPublicRatingsForResourceHandler(
        ratings=InMemoryRatingRepository(),
        resources=_FakeResourceRepo(res),
    )
    r = await handler.handle(ListPublicRatingsForResourceQuery(
        owner_slug="owner", resource_slug="campo",
    ))
    assert r.is_failure
    assert r.error == "ResourceNotFound"


async def test_clamps_page_size():
    res = _build_resource()
    handler = ListPublicRatingsForResourceHandler(
        ratings=InMemoryRatingRepository(),
        resources=_FakeResourceRepo(res),
    )
    r = await handler.handle(ListPublicRatingsForResourceQuery(
        owner_slug="owner", resource_slug="campo", page_size=500,
    ))
    assert r.is_success
    assert r.value.page_size == 100
