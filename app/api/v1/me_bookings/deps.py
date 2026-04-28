from __future__ import annotations
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.bookings.postgres_lock_service import (
    PostgresBookingLockService,
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
from app.use_cases.bookings.commands.approve_booking import ApproveBookingHandler
from app.use_cases.bookings.commands.cancel_booking import CancelBookingHandler
from app.use_cases.bookings.commands.reject_booking import RejectBookingHandler
from app.use_cases.bookings.commands.request_booking import RequestBookingHandler
from app.use_cases.bookings.queries.get_agenda import GetAgendaHandler
from app.use_cases.bookings.queries.get_my_booking import GetMyBookingHandler
from app.use_cases.bookings.queries.list_my_bookings import ListMyBookingsHandler
from app.use_cases.bookings.queries.list_resource_bookings import (
    ListResourceBookingsHandler,
)


def _booking_repo(session: AsyncSession) -> SQLAlchemyBookingRepository:
    return SQLAlchemyBookingRepository(session)


def _resource_repo(session: AsyncSession) -> SQLAlchemyResourceRepository:
    return SQLAlchemyResourceRepository(session)


def _sub_repo(session: AsyncSession) -> SQLAlchemyOwnerSubscriptionRepository:
    return SQLAlchemyOwnerSubscriptionRepository(session)


def _notifications(session: AsyncSession) -> PersistentNotificationService:
    return PersistentNotificationService(SQLAlchemyNotificationRepository(session))


def _lock(session: AsyncSession) -> PostgresBookingLockService:
    return PostgresBookingLockService(session)


async def get_request_booking_handler(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> RequestBookingHandler:
    return RequestBookingHandler(
        bookings=_booking_repo(session),
        resources=_resource_repo(session),
        subscriptions=_sub_repo(session),
        notifications=_notifications(session),
    )


async def get_approve_booking_handler(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ApproveBookingHandler:
    return ApproveBookingHandler(
        bookings=_booking_repo(session),
        resources=_resource_repo(session),
        subscriptions=_sub_repo(session),
        notifications=_notifications(session),
        lock=_lock(session),
    )


async def get_reject_booking_handler(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> RejectBookingHandler:
    return RejectBookingHandler(
        bookings=_booking_repo(session),
        resources=_resource_repo(session),
        notifications=_notifications(session),
    )


async def get_cancel_booking_handler(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CancelBookingHandler:
    return CancelBookingHandler(
        bookings=_booking_repo(session),
        resources=_resource_repo(session),
        notifications=_notifications(session),
    )


async def get_list_my_bookings_handler(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ListMyBookingsHandler:
    return ListMyBookingsHandler(bookings=_booking_repo(session))


async def get_my_booking_handler(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> GetMyBookingHandler:
    return GetMyBookingHandler(bookings=_booking_repo(session))


async def get_list_resource_bookings_handler(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ListResourceBookingsHandler:
    return ListResourceBookingsHandler(
        bookings=_booking_repo(session),
        resources=_resource_repo(session),
    )


async def get_agenda_handler(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> GetAgendaHandler:
    return GetAgendaHandler(
        bookings=_booking_repo(session),
        resources=_resource_repo(session),
    )
