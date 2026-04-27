from __future__ import annotations
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.session import get_session
from app.infrastructure.repositories.notification_repository import (
    SQLAlchemyNotificationRepository,
)
from app.use_cases.notifications.commands.mark_notification_read import (
    MarkNotificationReadHandler,
)
from app.use_cases.notifications.queries.list_my_notifications import (
    ListMyNotificationsHandler,
)


async def get_notification_repository(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> SQLAlchemyNotificationRepository:
    return SQLAlchemyNotificationRepository(session)


async def get_list_my_notifications_handler(
    repo: Annotated[
        SQLAlchemyNotificationRepository, Depends(get_notification_repository),
    ],
) -> ListMyNotificationsHandler:
    return ListMyNotificationsHandler(repo)


async def get_mark_notification_read_handler(
    repo: Annotated[
        SQLAlchemyNotificationRepository, Depends(get_notification_repository),
    ],
) -> MarkNotificationReadHandler:
    return MarkNotificationReadHandler(repo)
