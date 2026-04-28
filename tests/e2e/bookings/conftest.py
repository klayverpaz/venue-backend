from __future__ import annotations
from typing import Annotated

import pytest_asyncio
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.me_bookings.deps import get_approve_booking_handler
from app.infrastructure.bookings.in_memory_lock_service import (
    InMemoryBookingLockService,
)
from app.infrastructure.db.session import get_session
from app.infrastructure.notifications.persistent_notification_service import (
    PersistentNotificationService,
)
from app.infrastructure.repositories.booking_repository import (
    SQLAlchemyBookingRepository,
)
from app.infrastructure.repositories.notification_repository import (
    SQLAlchemyNotificationRepository,
)
from app.infrastructure.repositories.owner_subscription_repository import (
    SQLAlchemyOwnerSubscriptionRepository,
)
from app.infrastructure.repositories.resource_repository import (
    SQLAlchemyResourceRepository,
)
from app.main import app
from app.use_cases.bookings.commands.approve_booking import ApproveBookingHandler


async def _get_approve_booking_handler_sqlite(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ApproveBookingHandler:
    """Override for SQLite e2e tests: swap PostgresBookingLockService →
    InMemoryBookingLockService so pg_advisory_xact_lock is never called."""
    return ApproveBookingHandler(
        bookings=SQLAlchemyBookingRepository(session),
        resources=SQLAlchemyResourceRepository(session),
        subscriptions=SQLAlchemyOwnerSubscriptionRepository(session),
        notifications=PersistentNotificationService(
            SQLAlchemyNotificationRepository(session),
        ),
        lock=InMemoryBookingLockService(),
    )


@pytest_asyncio.fixture(autouse=True)
async def _override_lock_service():
    """Replace the Postgres advisory lock with an in-memory asyncio lock for
    the SQLite-backed e2e test suite."""
    app.dependency_overrides[get_approve_booking_handler] = (
        _get_approve_booking_handler_sqlite
    )
    yield
    app.dependency_overrides.pop(get_approve_booking_handler, None)
