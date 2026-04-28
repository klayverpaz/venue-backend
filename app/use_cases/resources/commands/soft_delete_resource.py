from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from app.domain.accounts.role import Role
from app.domain.bookings.repository import IBookingRepository
from app.domain.notifications.service import INotificationService, NotifKind
from app.domain.resources.repository import IResourceRepository
from app.domain.shared.result import Result
from app.use_cases.resources._common import load_owned_resource


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True, slots=True)
class SoftDeleteResourceCommand:
    actor_id: UUID
    resource_id: UUID


class SoftDeleteResourceHandler:
    """Plan 06 ships the plumbing. Plan 08 extends to:
    1. Reject when an APPROVED booking with future slot_start exists.
    2. Auto-cancel all PENDING bookings on the resource (reason=resource_deleted).
    3. Dispatch BOOKING_CANCELLED notifications to each affected customer.
    """

    def __init__(
        self,
        *,
        resources: IResourceRepository,
        bookings: IBookingRepository,
        notifications: INotificationService,
    ) -> None:
        self._resources = resources
        self._bookings = bookings
        self._notifications = notifications

    async def handle(self, cmd: SoftDeleteResourceCommand) -> Result[None]:
        loaded = await load_owned_resource(
            self._resources, resource_id=cmd.resource_id, actor_id=cmd.actor_id,
        )
        if loaded.is_failure:
            return Result.from_failure(loaded)
        res = loaded.value
        now = _utcnow()

        approved_future_r = await self._bookings.list_approved_with_start_after(
            res.id, now,
        )
        if approved_future_r.is_failure:
            return Result.from_failure(approved_future_r)
        if approved_future_r.value:
            return Result.failure(
                "ResourceHasFutureApprovedBookings", status_code=409,
            )

        pending_r = await self._bookings.list_pending_for_resource(res.id)
        if pending_r.is_failure:
            return Result.from_failure(pending_r)
        cancelled_targets: list[tuple[UUID, UUID]] = []
        for booking in pending_r.value:
            transition = booking.cancel(
                actor_id=cmd.actor_id, actor_role=Role.OWNER,
                now=now, reason="resource_deleted",
            )
            if transition.is_failure:
                continue
            update_r = await self._bookings.update(booking)
            if update_r.is_failure:
                return Result.from_failure(update_r)
            cancelled_targets.append((booking.id, booking.customer_id))

        del_r = res.soft_delete(now=now)
        if del_r.is_failure:
            return Result.from_failure(del_r, status_code=400)
        save = await self._resources.update(res)
        if save.is_failure:
            return Result.from_failure(save)

        for booking_id, customer_id in cancelled_targets:
            await self._notifications.notify(
                recipient_id=customer_id,
                kind=NotifKind.BOOKING_CANCELLED,
                payload={
                    "booking_id": str(booking_id),
                    "resource_id": str(res.id),
                    "cancelled_by": "owner",
                    "reason": "resource_deleted",
                },
            )
        return Result.success(None)
