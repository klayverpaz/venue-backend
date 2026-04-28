"""Cron entry-point. Run via `python -m app.jobs.expire_pending_bookings`.

Suggested schedule: hourly (cron `0 * * * *`). Idempotent — safe to retry.
Transitions PENDING bookings whose slot_start_at < now to EXPIRED and
dispatches BOOKING_REJECTED notifications (reason=slot_start_passed_with_no_decision).
"""
from __future__ import annotations
import asyncio
import logging

from app.infrastructure.db.session import dispose_engine, get_session, init_engine
from app.infrastructure.notifications.persistent_notification_service import (
    PersistentNotificationService,
)
from app.infrastructure.repositories.booking_repository import (
    SQLAlchemyBookingRepository,
)
from app.infrastructure.repositories.notification_repository import (
    SQLAlchemyNotificationRepository,
)
from app.use_cases.bookings.commands.expire_pending_bookings import (
    ExpirePendingBookingsCommand,
    ExpirePendingBookingsHandler,
)


logger = logging.getLogger(__name__)


async def main() -> int:
    init_engine()
    try:
        async for session in get_session():
            bookings = SQLAlchemyBookingRepository(session)
            notifications = PersistentNotificationService(
                SQLAlchemyNotificationRepository(session),
            )
            handler = ExpirePendingBookingsHandler(
                bookings=bookings, notifications=notifications,
            )
            result = await handler.handle(ExpirePendingBookingsCommand())
            count = result.value or 0
            logger.info("expired %s pending bookings", count)
            return count
        return 0
    finally:
        await dispose_engine()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
