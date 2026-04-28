from __future__ import annotations
from collections import defaultdict
from decimal import Decimal
from uuid import UUID

from app.domain.ratings.aggregate import RatingAggregate
from app.domain.ratings.rating import Rating
from app.domain.ratings.repository import IRatingRepository
from app.domain.shared.result import Result


class InMemoryRatingRepository(IRatingRepository):
    def __init__(self) -> None:
        self._rows: list[Rating] = []

    async def add(self, rating: Rating) -> Result[None]:
        if any(r.booking_id == rating.booking_id for r in self._rows):
            return Result.failure("RatingAlreadyExists", status_code=409)
        self._rows.append(rating)
        return Result.success(None)

    async def update(self, rating: Rating) -> Result[None]:
        for i, existing in enumerate(self._rows):
            if existing.id == rating.id:
                self._rows[i] = rating
                return Result.success(None)
        return Result.failure("RatingNotFound", status_code=404)

    async def get_by_id(self, rating_id: UUID) -> Result[Rating | None]:
        for r in self._rows:
            if r.id == rating_id:
                return Result.success(r)
        return Result.success(None)

    async def get_by_booking_id(
        self, booking_id: UUID,
    ) -> Result[Rating | None]:
        for r in self._rows:
            if r.booking_id == booking_id:
                return Result.success(r)
        return Result.success(None)

    async def list_by_customer(
        self,
        customer_id: UUID,
        *,
        page: int,
        page_size: int,
    ) -> Result[list[Rating]]:
        filtered = [r for r in self._rows if r.customer_id == customer_id]
        filtered.sort(key=lambda r: r.created_at, reverse=True)
        offset = (page - 1) * page_size
        return Result.success(filtered[offset:offset + page_size])

    async def list_with_comment_for_resource(
        self,
        resource_id: UUID,
        *,
        page: int,
        page_size: int,
    ) -> Result[list[Rating]]:
        filtered = [
            r for r in self._rows
            if r.resource_id == resource_id and r.comment is not None
        ]
        filtered.sort(key=lambda r: r.created_at, reverse=True)
        offset = (page - 1) * page_size
        return Result.success(filtered[offset:offset + page_size])

    async def get_aggregates_for_resources(
        self,
        resource_ids: list[UUID],
    ) -> Result[dict[UUID, RatingAggregate]]:
        out: dict[UUID, RatingAggregate] = {
            rid: RatingAggregate(avg_score=None, count=0)
            for rid in resource_ids
        }
        groups: dict[UUID, list[int]] = defaultdict(list)
        for r in self._rows:
            if r.resource_id in out:
                groups[r.resource_id].append(r.score.value)
        for rid, scores in groups.items():
            avg = (Decimal(sum(scores)) / Decimal(len(scores))).quantize(
                Decimal("0.1"),
            )
            out[rid] = RatingAggregate(avg_score=avg, count=len(scores))
        return Result.success(out)
