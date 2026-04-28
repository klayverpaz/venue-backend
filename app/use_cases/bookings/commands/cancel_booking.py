from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID

from app.domain.accounts.role import Role
from app.domain.bookings.repository import IBookingRepository
from app.domain.notifications.service import INotificationService, NotifKind
from app.domain.resources.repository import IResourceRepository
from app.domain.shared.result import Result
from app.use_cases.bookings.dtos import BookingDto


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True, kw_only=True, slots=True)
class CancelBookingCommand:
    actor_id: UUID
    booking_id: UUID
    reason: str | None


class CancelBookingHandler:
    """Single handler; branches on actor_role.

    Customer cancellation enforces the resource's
    customer_cancellation_cutoff_hours. Owner cancellation has no time bound.
    Third-party (neither owner nor customer) gets BookingNotFound 404.
    """

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

    async def handle(self, cmd: CancelBookingCommand) -> Result[BookingDto]:
        # 1. Load booking — IBookingRepository.get_by_id returns Result[Booking | None].
        b_r = await self._bookings.get_by_id(cmd.booking_id)
        if b_r.is_failure:
            return Result.from_failure(b_r)
        booking = b_r.value
        if booking is None:
            return Result.failure("BookingNotFound", status_code=404)

        # 2. Load resource — IResourceRepository.get_by_id returns Resource | None.
        resource = await self._resources.get_by_id(booking.resource_id)
        if resource is None:
            return Result.failure("BookingNotFound", status_code=404)

        is_customer = booking.customer_id == cmd.actor_id
        is_owner = resource.owner_id == cmd.actor_id
        if not (is_customer or is_owner):
            return Result.failure("BookingNotFound", status_code=404)

        # Customer cancellation enforces cutoff (only if NOT also owner —
        # an owner-customer booking the same resource skips cutoff).
        if is_customer and not is_owner:
            cutoff_hours = resource.customer_cancellation_cutoff_hours.hours
            if _utcnow() >= booking.slot_range.start_at - timedelta(hours=cutoff_hours):
                return Result.failure(
                    "BookingCancellationPastCutoff", status_code=403,
                )

        actor_role = Role.OWNER if is_owner else Role.CUSTOMER
        transition = booking.cancel(
            actor_id=cmd.actor_id, actor_role=actor_role,
            now=_utcnow(), reason=cmd.reason,
        )
        if transition.is_failure:
            return Result.failure(
                "BookingInvalidStateTransition", status_code=409,
            )
        update_r = await self._bookings.update(booking)
        if update_r.is_failure:
            return Result.from_failure(update_r)

        counterpart = resource.owner_id if is_customer else booking.customer_id
        await self._notifications.notify(
            recipient_id=counterpart,
            kind=NotifKind.BOOKING_CANCELLED,
            payload={
                "booking_id": str(booking.id),
                "resource_id": str(resource.id),
                "cancelled_by": actor_role.value,
            },
        )
        return Result.success(BookingDto.from_entity(booking))
