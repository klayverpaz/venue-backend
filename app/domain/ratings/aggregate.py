from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class RatingAggregate:
    """Read-side projection: average score (rounded to one decimal) + count.

    `avg_score` is `None` exactly when `count == 0`. Used by every endpoint
    that returns a Resource (or owner page) to surface aggregate ratings
    without storing denormalized fields on the Resource aggregate.
    """

    avg_score: Decimal | None
    count: int
