from __future__ import annotations
from datetime import datetime
from uuid import UUID

from app.domain.bookings.booking import Booking
from app.domain.bookings.booking_status import BookingStatus
from app.domain.bookings.repository import IBookingRepository
from app.domain.shared.result import Result
from app.domain.shared.value_objects.date_time_range import DateTimeRange


def _overlaps(a: DateTimeRange, b: DateTimeRange) -> bool:
    return a.start_at < b.end_at and b.start_at < a.end_at


class InMemoryBookingRepository(IBookingRepository):
    def __init__(self) -> None:
        self._rows: list[Booking] = []

    async def add(self, booking: Booking) -> Result[None]:
        self._rows.append(booking)
        return Result.success(None)

    async def get_by_id(self, booking_id: UUID) -> Result[Booking | None]:
        for b in self._rows:
            if b.id == booking_id:
                return Result.success(b)
        return Result.success(None)

    async def list_by_customer(
        self, customer_id: UUID, *,
        status: BookingStatus | None,
        page: int,
        page_size: int,
    ) -> Result[list[Booking]]:
        filtered = [
            b for b in self._rows
            if b.customer_id == customer_id
            and (status is None or b.status is status)
        ]
        filtered.sort(key=lambda b: b.created_at, reverse=True)
        offset = (page - 1) * page_size
        return Result.success(filtered[offset:offset + page_size])

    async def list_active_by_customer_for_resource(
        self,
        customer_id: UUID,
        resource_id: UUID,
        slot_range: DateTimeRange,
    ) -> Result[list[Booking]]:
        return Result.success([
            b for b in self._rows
            if b.customer_id == customer_id
            and b.resource_id == resource_id
            and b.status.is_active()
            and _overlaps(b.slot_range, slot_range)
        ])

    async def list_pending_overlapping(
        self,
        resource_id: UUID,
        slot_range: DateTimeRange,
        *,
        exclude_booking_id: UUID | None = None,
    ) -> Result[list[Booking]]:
        return Result.success([
            b for b in self._rows
            if b.resource_id == resource_id
            and b.status is BookingStatus.PENDING
            and _overlaps(b.slot_range, slot_range)
            and b.id != exclude_booking_id
        ])

    async def list_by_resource(
        self,
        resource_id: UUID,
        *,
        status: BookingStatus | None,
        page: int,
        page_size: int,
    ) -> Result[list[Booking]]:
        filtered = [
            b for b in self._rows
            if b.resource_id == resource_id
            and (status is None or b.status is status)
        ]
        filtered.sort(key=lambda b: b.slot_range.start_at, reverse=True)
        offset = (page - 1) * page_size
        return Result.success(filtered[offset:offset + page_size])

    async def list_in_range_for_resource(
        self,
        resource_id: UUID,
        range_start: datetime,
        range_end: datetime,
    ) -> Result[list[Booking]]:
        return Result.success([
            b for b in self._rows
            if b.resource_id == resource_id
            and b.slot_range.start_at < range_end
            and b.slot_range.end_at > range_start
        ])

    async def list_pending_with_start_before(
        self, cutoff: datetime,
    ) -> Result[list[Booking]]:
        return Result.success([
            b for b in self._rows
            if b.status is BookingStatus.PENDING
            and b.slot_range.start_at < cutoff
        ])

    async def list_pending_for_resource(
        self, resource_id: UUID,
    ) -> Result[list[Booking]]:
        return Result.success([
            b for b in self._rows
            if b.resource_id == resource_id
            and b.status is BookingStatus.PENDING
        ])

    async def list_approved_with_start_after(
        self, resource_id: UUID, cutoff: datetime,
    ) -> Result[list[Booking]]:
        return Result.success([
            b for b in self._rows
            if b.resource_id == resource_id
            and b.status is BookingStatus.APPROVED
            and b.slot_range.start_at >= cutoff
        ])

    async def update(self, booking: Booking) -> Result[None]:
        for i, existing in enumerate(self._rows):
            if existing.id == booking.id:
                self._rows[i] = booking
                return Result.success(None)
        return Result.failure("BookingNotFound", status_code=404)
