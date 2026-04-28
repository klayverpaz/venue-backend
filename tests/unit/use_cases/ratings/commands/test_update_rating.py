from __future__ import annotations
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.domain.ratings.rating import Rating
from app.domain.shared.value_objects.rating_score import RatingScore
from app.domain.shared.value_objects.short_description import ShortDescription
from app.use_cases.ratings.commands.update_rating import (
    UpdateRatingCommand,
    UpdateRatingHandler,
)
from tests.unit.use_cases.ratings.fakes.in_memory_rating_repository import (
    InMemoryRatingRepository,
)


pytestmark = pytest.mark.asyncio


def _now() -> datetime:
    return datetime(2026, 4, 28, 12, 0, 0, tzinfo=timezone.utc)


def _seed_rating(*, customer_id, age_days: int = 0) -> Rating:
    return Rating.create(
        booking_id=uuid4(), resource_id=uuid4(), customer_id=customer_id,
        score=RatingScore.create(3).value,
        comment=ShortDescription.create("inicial").value,
        now=_now() - timedelta(days=age_days),
    )


async def test_happy_path_updates_score_and_comment():
    customer_id = uuid4()
    rating = _seed_rating(customer_id=customer_id)
    repo = InMemoryRatingRepository()
    await repo.add(rating)
    handler = UpdateRatingHandler(ratings=repo, clock=_now)
    cmd = UpdateRatingCommand(
        actor_id=customer_id, booking_id=rating.booking_id,
        score=5, comment="atualizado",
    )
    r = await handler.handle(cmd)
    assert r.is_success
    assert r.value.score == 5
    assert r.value.comment == "atualizado"


async def test_can_clear_comment():
    customer_id = uuid4()
    rating = _seed_rating(customer_id=customer_id)
    repo = InMemoryRatingRepository()
    await repo.add(rating)
    handler = UpdateRatingHandler(ratings=repo, clock=_now)
    r = await handler.handle(UpdateRatingCommand(
        actor_id=customer_id, booking_id=rating.booking_id,
        score=4, comment=None,
    ))
    assert r.is_success
    assert r.value.comment is None


async def test_unknown_booking_returns_404():
    handler = UpdateRatingHandler(
        ratings=InMemoryRatingRepository(), clock=_now,
    )
    r = await handler.handle(UpdateRatingCommand(
        actor_id=uuid4(), booking_id=uuid4(), score=5, comment=None,
    ))
    assert r.is_failure
    assert r.error == "RatingNotFound"
    assert r.status_code == 404


async def test_other_customer_returns_404():
    """Cross-customer access should look identical to "not found" — no leak."""
    real_customer = uuid4()
    rating = _seed_rating(customer_id=real_customer)
    repo = InMemoryRatingRepository()
    await repo.add(rating)
    handler = UpdateRatingHandler(ratings=repo, clock=_now)
    r = await handler.handle(UpdateRatingCommand(
        actor_id=uuid4(), booking_id=rating.booking_id,
        score=5, comment=None,
    ))
    assert r.is_failure
    assert r.error == "RatingNotFound"


async def test_past_7day_window_rejected():
    customer_id = uuid4()
    rating = _seed_rating(customer_id=customer_id, age_days=8)
    repo = InMemoryRatingRepository()
    await repo.add(rating)
    handler = UpdateRatingHandler(ratings=repo, clock=_now)
    r = await handler.handle(UpdateRatingCommand(
        actor_id=customer_id, booking_id=rating.booking_id,
        score=5, comment=None,
    ))
    assert r.is_failure
    assert r.error == "RatingEditWindowExpired"
    assert r.status_code == 403


async def test_invalid_score_returns_422():
    customer_id = uuid4()
    rating = _seed_rating(customer_id=customer_id)
    repo = InMemoryRatingRepository()
    await repo.add(rating)
    handler = UpdateRatingHandler(ratings=repo, clock=_now)
    r = await handler.handle(UpdateRatingCommand(
        actor_id=customer_id, booking_id=rating.booking_id,
        score=99, comment=None,
    ))
    assert r.is_failure
    assert r.status_code == 422
