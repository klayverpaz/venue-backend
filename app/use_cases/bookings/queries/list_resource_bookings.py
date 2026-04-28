from __future__ import annotations
from dataclasses import dataclass
from uuid import UUID

from app.domain.bookings.booking_status import BookingStatus
from app.domain.bookings.repository import IBookingRepository
from app.domain.resources.repository import IResourceRepository
from app.domain.shared.result import Result
from app.use_cases.bookings.dtos import BookingDto, BookingListDto


_MAX_PAGE_SIZE = 100


@dataclass(frozen=True, kw_only=True, slots=True)
class ListResourceBookingsQuery:
    actor_id: UUID                       # owner
    resource_id: UUID
    status: BookingStatus | None = None
    page: int = 1
    page_size: int = 50


class ListResourceBookingsHandler:
    def __init__(
        self,
        *,
        bookings: IBookingRepository,
        resources: IResourceRepository,
    ) -> None:
        self._bookings = bookings
        self._resources = resources

    async def handle(
        self, query: ListResourceBookingsQuery,
    ) -> Result[BookingListDto]:
        # ADAPT: get_by_id returns Resource | None directly, not Result
        resource = await self._resources.get_by_id(query.resource_id)
        if resource is None or resource.owner_id != query.actor_id:
            return Result.failure("ResourceNotFound", status_code=404)

        page = max(1, query.page)
        page_size = max(1, min(query.page_size, _MAX_PAGE_SIZE))
        rows_r = await self._bookings.list_by_resource(
            resource.id, status=query.status,
            page=page, page_size=page_size,
        )
        if rows_r.is_failure:
            return Result.from_failure(rows_r)
        items = tuple(BookingDto.from_entity(b) for b in rows_r.value)
        return Result.success(BookingListDto(
            items=items, page=page, page_size=page_size,
        ))
