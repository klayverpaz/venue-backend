from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.domain.ratings.rating import Rating


@dataclass(frozen=True, kw_only=True, slots=True)
class RatingDto:
    """Customer-facing rating shape (includes own customer_id, comment if any)."""
    id: UUID
    booking_id: UUID
    resource_id: UUID
    customer_id: UUID
    score: int
    comment: str | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_entity(cls, r: Rating) -> "RatingDto":
        return cls(
            id=r.id,
            booking_id=r.booking_id,
            resource_id=r.resource_id,
            customer_id=r.customer_id,
            score=r.score.value,
            comment=r.comment.value if r.comment is not None else None,
            created_at=r.created_at,
            updated_at=r.updated_at,
        )


@dataclass(frozen=True, kw_only=True, slots=True)
class RatingListDto:
    items: tuple[RatingDto, ...]
    page: int
    page_size: int


@dataclass(frozen=True, kw_only=True, slots=True)
class PublicRatingDto:
    """Privacy-filtered: omits customer_id and booking_id. Only used by the
    public ratings list, where comment is non-NULL by query construction."""
    score: int
    comment: str
    created_at: datetime

    @classmethod
    def from_entity(cls, r: Rating) -> "PublicRatingDto":
        return cls(
            score=r.score.value,
            comment=r.comment.value if r.comment is not None else "",
            created_at=r.created_at,
        )


@dataclass(frozen=True, kw_only=True, slots=True)
class PublicRatingListDto:
    items: tuple[PublicRatingDto, ...]
    page: int
    page_size: int
