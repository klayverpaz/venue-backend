from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from app.domain.bookings.repository import IBookingRepository
from app.domain.notifications.service import INotificationService, NotifKind
from app.domain.resources.repository import IResourceRepository
from app.domain.shared.result import Result
from app.use_cases.bookings.dtos import BookingDto


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True, kw_only=True, slots=True)
class RejectBookingCommand:
    actor_id: UUID                       # owner
    booking_id: UUID
    reason: str | None


class RejectBookingHandler:
    def __init__(
        self,
        *,
        bookings: IBookingRepository,
        resources: IResourceRepository,
        notifications: INotificationService,
    ) -> None:
        self._bookings = bookings
        self._resources = resources
        self._notifications = notifications

    async def handle(self, cmd: RejectBookingCommand) -> Result[BookingDto]:
        # 1. Load booking — IBookingRepository.get_by_id returns Result[Booking | None].
        b_r = await self._bookings.get_by_id(cmd.booking_id)
        if b_r.is_failure:
            return Result.from_failure(b_r)
        booking = b_r.value
        if booking is None:
            return Result.failure("BookingNotFound", status_code=404)

        # 2. Load resource — IResourceRepository.get_by_id returns Resource | None.
        resource = await self._resources.get_by_id(booking.resource_id)
        if resource is None or resource.owner_id != cmd.actor_id:
            return Result.failure("BookingNotFound", status_code=404)

        # 3. Transition domain state.
        transition = booking.reject(
            actor_id=cmd.actor_id, now=_utcnow(), reason=cmd.reason,
        )
        if transition.is_failure:
            return Result.failure(
                "BookingInvalidStateTransition", status_code=409,
            )

        # 4. Persist.
        update_r = await self._bookings.update(booking)
        if update_r.is_failure:
            return Result.from_failure(update_r)

        # 5. Notify customer.
        await self._notifications.notify(
            recipient_id=booking.customer_id,
            kind=NotifKind.BOOKING_REJECTED,
            payload={
                "booking_id": str(booking.id),
                "resource_id": str(resource.id),
                "reason": cmd.reason or "owner_rejected",
            },
        )
        return Result.success(BookingDto.from_entity(booking))
