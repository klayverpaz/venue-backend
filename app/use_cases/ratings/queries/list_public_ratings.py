from __future__ import annotations
from dataclasses import dataclass

from app.domain.ratings.repository import IRatingRepository
from app.domain.resources.repository import IResourceRepository
from app.domain.shared.result import Result
from app.use_cases.ratings.dtos import PublicRatingDto, PublicRatingListDto


_MAX_PAGE_SIZE = 100


@dataclass(frozen=True, kw_only=True, slots=True)
class ListPublicRatingsForResourceQuery:
    owner_slug: str
    resource_slug: str
    page: int = 1
    page_size: int = 50


class ListPublicRatingsForResourceHandler:
    def __init__(
        self,
        *,
        ratings: IRatingRepository,
        resources: IResourceRepository,
    ) -> None:
        self._ratings = ratings
        self._resources = resources

    async def handle(
        self, query: ListPublicRatingsForResourceQuery,
    ) -> Result[PublicRatingListDto]:
        # IResourceRepository.get_by_owner_slug_and_resource_slug returns
        # Resource | None directly per Plan 08 Task 20 adaptation.
        resource = await self._resources.get_by_owner_slug_and_resource_slug(
            query.owner_slug, query.resource_slug,
        )
        if resource is None or resource.is_deleted():
            return Result.failure("ResourceNotFound", status_code=404)

        page = max(1, query.page)
        page_size = max(1, min(query.page_size, _MAX_PAGE_SIZE))
        rows_r = await self._ratings.list_with_comment_for_resource(
            resource.id, page=page, page_size=page_size,
        )
        if rows_r.is_failure:
            return Result.from_failure(rows_r)
        items = tuple(PublicRatingDto.from_entity(r) for r in rows_r.value)
        return Result.success(PublicRatingListDto(
            items=items, page=page, page_size=page_size,
        ))
