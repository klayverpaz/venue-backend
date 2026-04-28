from __future__ import annotations
from decimal import Decimal

from app.domain.ratings.aggregate import RatingAggregate


def test_zero_count_aggregate():
    agg = RatingAggregate(avg_score=None, count=0)
    assert agg.avg_score is None
    assert agg.count == 0


def test_with_ratings():
    agg = RatingAggregate(avg_score=Decimal("4.3"), count=10)
    assert agg.avg_score == Decimal("4.3")
    assert agg.count == 10


def test_is_frozen():
    import dataclasses
    agg = RatingAggregate(avg_score=Decimal("4.0"), count=2)
    with __import__("pytest").raises(dataclasses.FrozenInstanceError):
        agg.count = 3  # type: ignore[misc]
