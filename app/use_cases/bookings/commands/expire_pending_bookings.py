from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable

from app.domain.bookings.repository import IBookingRepository
from app.domain.notifications.service import INotificationService, NotifKind
from app.domain.shared.result import Result


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True, slots=True)
class ExpirePendingBookingsCommand:
    pass


class ExpirePendingBookingsHandler:
    def __init__(
        self,
        *,
        bookings: IBookingRepository,
        notifications: INotificationService,
        clock: Callable[[], datetime] = _utcnow,
    ) -> None:
        self._bookings = bookings
        self._notifications = notifications
        self._clock = clock

    async def handle(
        self, cmd: ExpirePendingBookingsCommand,
    ) -> Result[int]:
        now = self._clock()
        expired_r = await self._bookings.list_pending_with_start_before(now)
        if expired_r.is_failure:
            return Result.from_failure(expired_r)
        count = 0
        for booking in expired_r.value:
            transition = booking.expire(now=now)
            if transition.is_failure:
                continue
            update_r = await self._bookings.update(booking)
            if update_r.is_failure:
                continue
            await self._notifications.notify(
                recipient_id=booking.customer_id,
                kind=NotifKind.BOOKING_REJECTED,
                payload={
                    "booking_id": str(booking.id),
                    "resource_id": str(booking.resource_id),
                    "reason": "slot_start_passed_with_no_decision",
                },
            )
            count += 1
        return Result.success(count)
