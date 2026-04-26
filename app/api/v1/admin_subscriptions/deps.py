from __future__ import annotations
from typing import Annotated
import logging
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.infrastructure.db.session import get_session
from app.infrastructure.notifications.logging_notification_service import (
    LoggingNotificationService,
)
from app.infrastructure.repositories.owner_subscription_repository import (
    SQLAlchemyOwnerSubscriptionRepository,
)
from app.infrastructure.repositories.user_repository import UserRepository
from app.use_cases.subscriptions.commands.set_owner_subscription_status import (
    SetOwnerSubscriptionStatusHandler,
)
from app.use_cases.subscriptions.queries.list_subscriptions import (
    ListSubscriptionsHandler,
)


_logger = logging.getLogger("subscriptions.notifications")


async def get_subscription_repo(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> SQLAlchemyOwnerSubscriptionRepository:
    return SQLAlchemyOwnerSubscriptionRepository(session)


async def get_user_repo(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> UserRepository:
    return UserRepository(session)


async def get_notification_service() -> LoggingNotificationService:
    return LoggingNotificationService(_logger)


async def get_settings_dep() -> Settings:
    return get_settings()


async def get_set_status_handler(
    users: Annotated[UserRepository, Depends(get_user_repo)],
    subs: Annotated[SQLAlchemyOwnerSubscriptionRepository, Depends(get_subscription_repo)],
    notifs: Annotated[LoggingNotificationService, Depends(get_notification_service)],
    settings: Annotated[Settings, Depends(get_settings_dep)],
) -> SetOwnerSubscriptionStatusHandler:
    return SetOwnerSubscriptionStatusHandler(users, subs, notifs, settings)


async def get_list_handler(
    subs: Annotated[SQLAlchemyOwnerSubscriptionRepository, Depends(get_subscription_repo)],
) -> ListSubscriptionsHandler:
    return ListSubscriptionsHandler(subs)
