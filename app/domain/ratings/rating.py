from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4

from app.domain.shared.entity import BaseEntity
from app.domain.shared.value_objects.rating_score import RatingScore
from app.domain.shared.value_objects.short_description import ShortDescription


@dataclass(slots=True, kw_only=True)
class Rating(BaseEntity):
    booking_id: UUID
    resource_id: UUID
    customer_id: UUID
    score: RatingScore
    comment: ShortDescription | None = None

    @classmethod
    def create(
        cls,
        *,
        booking_id: UUID,
        resource_id: UUID,
        customer_id: UUID,
        score: RatingScore,
        comment: ShortDescription | None,
        now: datetime,
    ) -> "Rating":
        """Factory. All eligibility validation lives in CreateRatingHandler
        (it requires Booking context). Sets created_at == updated_at == now.
        """
        return cls(
            id=uuid4(),
            booking_id=booking_id,
            resource_id=resource_id,
            customer_id=customer_id,
            score=score,
            comment=comment,
            created_at=now,
            updated_at=now,
        )

    def update_text(
        self,
        *,
        score: RatingScore,
        comment: ShortDescription | None,
        now: datetime,
    ) -> None:
        """Replace score (required) and comment (optional). Bumps updated_at.
        7-day window check lives in UpdateRatingHandler — this aggregate has
        no failure mode at the entity level."""
        self.score = score
        self.comment = comment
        self.updated_at = now
