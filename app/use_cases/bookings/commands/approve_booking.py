from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from app.domain.bookings.booking_status import BookingStatus
from app.domain.bookings.lock import IBookingLockService
from app.domain.bookings.repository import IBookingRepository
from app.domain.notifications.service import INotificationService, NotifKind
from app.domain.resources.repository import IResourceRepository
from app.domain.shared.result import Result
from app.domain.subscriptions.repository import ISubscriptionRepository
from app.use_cases.bookings.dtos import BookingDto


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True, kw_only=True, slots=True)
class ApproveBookingCommand:
    actor_id: UUID                       # owner
    booking_id: UUID


class ApproveBookingHandler:
    def __init__(
        self,
        *,
        bookings: IBookingRepository,
        resources: IResourceRepository,
        subscriptions: ISubscriptionRepository,
        notifications: INotificationService,
        lock: IBookingLockService,
    ) -> None:
        self._bookings = bookings
        self._resources = resources
        self._subscriptions = subscriptions
        self._notifications = notifications
        self._lock = lock

    async def handle(self, cmd: ApproveBookingCommand) -> Result[BookingDto]:
        # 1. Load booking — IBookingRepository.get_by_id returns Result[Booking | None].
        target_r = await self._bookings.get_by_id(cmd.booking_id)
        if target_r.is_failure:
            return Result.from_failure(target_r)
        target = target_r.value
        if target is None:
            return Result.failure("BookingNotFound", status_code=404)

        # 2. Load resource — IResourceRepository.get_by_id returns Resource | None.
        resource = await self._resources.get_by_id(target.resource_id)
        if resource is None or resource.is_deleted():
            return Result.failure("BookingNotFound", status_code=404)
        if resource.owner_id != cmd.actor_id:
            return Result.failure("BookingNotFound", status_code=404)

        # 3. Owner subscription must be operational.
        sub = await self._subscriptions.get_by_owner_id(resource.owner_id)
        if sub is None or not sub.status.is_operational():
            return Result.failure("OwnerSubscriptionInactive", status_code=403)

        rejected_ids: list[tuple[UUID, UUID]] = []  # (booking_id, customer_id)
        async with self._lock.acquire_for_resource(resource.id):
            # Re-fetch under lock to catch any races.
            target = (await self._bookings.get_by_id(cmd.booking_id)).value
            if target is None or target.status is not BookingStatus.PENDING:
                return Result.failure(
                    "BookingInvalidStateTransition", status_code=409,
                )

            competitors_r = await self._bookings.list_pending_overlapping(
                target.resource_id, target.slot_range,
                exclude_booking_id=target.id,
            )
            if competitors_r.is_failure:
                return Result.from_failure(competitors_r)
            competitors = competitors_r.value

            now = _utcnow()
            approve_r = target.approve(actor_id=cmd.actor_id, now=now)
            if approve_r.is_failure:
                return Result.failure("BookingInvalidStateTransition", status_code=409)

            update_r = await self._bookings.update(target)
            if update_r.is_failure:
                return Result.from_failure(update_r)

            for comp in competitors:
                comp.reject(
                    actor_id=cmd.actor_id, now=now,
                    reason="auto_rejected_competing_request",
                )
                upd = await self._bookings.update(comp)
                if upd.is_failure:
                    return Result.from_failure(upd)
                rejected_ids.append((comp.id, comp.customer_id))

        # Outside lock + outside TX: dispatch notifications.
        await self._notifications.notify(
            recipient_id=target.customer_id,
            kind=NotifKind.BOOKING_APPROVED,
            payload={
                "booking_id": str(target.id),
                "resource_id": str(resource.id),
            },
        )
        for booking_id, customer_id in rejected_ids:
            await self._notifications.notify(
                recipient_id=customer_id,
                kind=NotifKind.BOOKING_REJECTED,
                payload={
                    "booking_id": str(booking_id),
                    "resource_id": str(resource.id),
                    "reason": "auto_rejected_competing_request",
                },
            )
        return Result.success(BookingDto.from_entity(target))
