from __future__ import annotations
from dataclasses import dataclass
from uuid import UUID

from app.domain.bookings.repository import IBookingRepository
from app.domain.shared.result import Result
from app.use_cases.bookings.dtos import BookingDto


@dataclass(frozen=True, kw_only=True, slots=True)
class GetMyBookingQuery:
    actor_id: UUID
    booking_id: UUID


class GetMyBookingHandler:
    def __init__(self, *, bookings: IBookingRepository) -> None:
        self._bookings = bookings

    async def handle(self, query: GetMyBookingQuery) -> Result[BookingDto]:
        b_r = await self._bookings.get_by_id(query.booking_id)
        if b_r.is_failure:
            return Result.from_failure(b_r)
        b = b_r.value
        if b is None or b.customer_id != query.actor_id:
            return Result.failure("BookingNotFound", status_code=404)
        return Result.success(BookingDto.from_entity(b))
