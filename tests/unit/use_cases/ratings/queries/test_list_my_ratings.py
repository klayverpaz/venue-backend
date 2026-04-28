from __future__ import annotations
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.domain.ratings.rating import Rating
from app.domain.shared.value_objects.rating_score import RatingScore
from app.use_cases.ratings.queries.list_my_ratings import (
    ListMyRatingsHandler,
    ListMyRatingsQuery,
)
from tests.unit.use_cases.ratings.fakes.in_memory_rating_repository import (
    InMemoryRatingRepository,
)


pytestmark = pytest.mark.asyncio


def _now() -> datetime:
    return datetime(2026, 4, 28, 12, 0, 0, tzinfo=timezone.utc)


def _rating(*, customer_id, days_ago: int = 0) -> Rating:
    return Rating.create(
        booking_id=uuid4(), resource_id=uuid4(), customer_id=customer_id,
        score=RatingScore.create(5).value, comment=None,
        now=_now() - timedelta(days=days_ago),
    )


async def test_returns_only_my_ratings():
    me = uuid4()
    other = uuid4()
    repo = InMemoryRatingRepository()
    mine = _rating(customer_id=me)
    theirs = _rating(customer_id=other)
    await repo.add(mine)
    await repo.add(theirs)
    handler = ListMyRatingsHandler(ratings=repo)
    r = await handler.handle(ListMyRatingsQuery(actor_id=me))
    assert r.is_success
    assert [it.id for it in r.value.items] == [mine.id]


async def test_orders_newest_first():
    me = uuid4()
    repo = InMemoryRatingRepository()
    older = _rating(customer_id=me, days_ago=10)
    newer = _rating(customer_id=me, days_ago=1)
    await repo.add(older)
    await repo.add(newer)
    handler = ListMyRatingsHandler(ratings=repo)
    r = await handler.handle(ListMyRatingsQuery(actor_id=me))
    assert [it.id for it in r.value.items] == [newer.id, older.id]


async def test_clamps_page_size_to_100():
    handler = ListMyRatingsHandler(ratings=InMemoryRatingRepository())
    r = await handler.handle(ListMyRatingsQuery(actor_id=uuid4(), page_size=500))
    assert r.is_success
    assert r.value.page_size == 100


async def test_clamps_page_min_1():
    handler = ListMyRatingsHandler(ratings=InMemoryRatingRepository())
    r = await handler.handle(ListMyRatingsQuery(actor_id=uuid4(), page=0))
    assert r.is_success
    assert r.value.page == 1
