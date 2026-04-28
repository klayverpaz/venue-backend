from __future__ import annotations
from dataclasses import dataclass
from uuid import UUID

from app.domain.ratings.repository import IRatingRepository
from app.domain.shared.result import Result
from app.use_cases.ratings.dtos import RatingDto, RatingListDto


_MAX_PAGE_SIZE = 100


@dataclass(frozen=True, kw_only=True, slots=True)
class ListMyRatingsQuery:
    actor_id: UUID
    page: int = 1
    page_size: int = 50


class ListMyRatingsHandler:
    def __init__(self, *, ratings: IRatingRepository) -> None:
        self._ratings = ratings

    async def handle(
        self, query: ListMyRatingsQuery,
    ) -> Result[RatingListDto]:
        page = max(1, query.page)
        page_size = max(1, min(query.page_size, _MAX_PAGE_SIZE))
        rows_r = await self._ratings.list_by_customer(
            query.actor_id, page=page, page_size=page_size,
        )
        if rows_r.is_failure:
            return Result.from_failure(rows_r)
        items = tuple(RatingDto.from_entity(r) for r in rows_r.value)
        return Result.success(RatingListDto(
            items=items, page=page, page_size=page_size,
        ))
