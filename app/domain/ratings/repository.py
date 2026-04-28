from __future__ import annotations
from typing import Protocol
from uuid import UUID

from app.domain.ratings.aggregate import RatingAggregate
from app.domain.ratings.rating import Rating
from app.domain.shared.result import Result


class IRatingRepository(Protocol):
    """Persistence port for the ratings feature."""

    async def add(self, rating: Rating) -> Result[None]:
        """Inserts a new rating. Translates UNIQUE(booking_id) violations
        from the database into Result.failure('RatingAlreadyExists', 409)."""
        ...

    async def update(self, rating: Rating) -> Result[None]:
        """Persists score/comment/updated_at changes. Returns
        Result.failure('RatingNotFound', 404) if the id is absent."""
        ...

    async def get_by_id(self, rating_id: UUID) -> Result[Rating | None]:
        ...

    async def get_by_booking_id(self, booking_id: UUID) -> Result[Rating | None]:
        """Used by CreateRatingHandler for the existence/dedup check before
        attempting an insert that could collide with the UNIQUE constraint."""
        ...

    async def list_by_customer(
        self,
        customer_id: UUID,
        *,
        page: int,
        page_size: int,
    ) -> Result[list[Rating]]:
        """Customer's own ratings, newest first."""
        ...

    async def list_with_comment_for_resource(
        self,
        resource_id: UUID,
        *,
        page: int,
        page_size: int,
    ) -> Result[list[Rating]]:
        """Public listing — only ratings whose comment is non-NULL,
        newest first."""
        ...

    async def get_aggregates_for_resources(
        self,
        resource_ids: list[UUID],
    ) -> Result[dict[UUID, RatingAggregate]]:
        """Batch aggregate. For each resource_id provided, returns the
        (avg_score, count) pair. Resources with zero ratings are present
        in the dict with RatingAggregate(None, 0). Used by every resource
        listing/detail endpoint to avoid N+1."""
        ...
