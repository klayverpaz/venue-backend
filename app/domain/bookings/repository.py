from __future__ import annotations
from datetime import datetime
from typing import Protocol
from uuid import UUID

from app.domain.bookings.booking import Booking
from app.domain.bookings.booking_status import BookingStatus
from app.domain.shared.result import Result
from app.domain.shared.value_objects.date_time_range import DateTimeRange


class IBookingRepository(Protocol):
    """Persistence port for the bookings feature."""

    async def add(self, booking: Booking) -> Result[None]: ...

    async def get_by_id(self, booking_id: UUID) -> Result[Booking | None]:
        """Returns the booking regardless of customer/owner. Handlers apply scoping."""
        ...

    async def list_by_customer(
        self,
        customer_id: UUID,
        *,
        status: BookingStatus | None,
        page: int,
        page_size: int,
    ) -> Result[list[Booking]]: ...

    async def list_active_by_customer_for_resource(
        self,
        customer_id: UUID,
        resource_id: UUID,
        slot_range: DateTimeRange,
    ) -> Result[list[Booking]]:
        """Natural dedup: returns this customer's PENDING/APPROVED bookings on
        this resource that overlap the slot_range."""
        ...

    async def list_pending_overlapping(
        self,
        resource_id: UUID,
        slot_range: DateTimeRange,
        *,
        exclude_booking_id: UUID | None = None,
    ) -> Result[list[Booking]]:
        """Used by ApproveBookingHandler to find competitors."""
        ...

    async def list_by_resource(
        self,
        resource_id: UUID,
        *,
        status: BookingStatus | None,
        page: int,
        page_size: int,
    ) -> Result[list[Booking]]: ...

    async def list_in_range_for_resource(
        self,
        resource_id: UUID,
        range_start: datetime,
        range_end: datetime,
    ) -> Result[list[Booking]]:
        """Used by GetAgendaHandler — returns all bookings (any status) whose
        slot_range intersects [range_start, range_end]."""
        ...

    async def list_pending_with_start_before(
        self, cutoff: datetime,
    ) -> Result[list[Booking]]:
        """Used by ExpirePendingBookingsHandler cron."""
        ...

    async def list_pending_for_resource(
        self, resource_id: UUID,
    ) -> Result[list[Booking]]:
        """Used by SoftDeleteResourceHandler cascade."""
        ...

    async def list_approved_with_start_after(
        self, resource_id: UUID, cutoff: datetime,
    ) -> Result[list[Booking]]:
        """Used by SoftDeleteResourceHandler to detect future approved bookings
        that should block deletion."""
        ...

    async def update(self, booking: Booking) -> Result[None]: ...
