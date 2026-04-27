"""Cron entry-point. Run via `python -m app.jobs.expire_trialing_subscriptions`.

Suggested schedule: hourly (cron `0 * * * *`). Idempotent — safe to retry.
"""
from __future__ import annotations
import asyncio
import logging

from app.core.config import get_settings
from app.infrastructure.db.session import dispose_engine, get_session, init_engine
from app.infrastructure.notifications.persistent_notification_service import (
    PersistentNotificationService,
)
from app.infrastructure.repositories.notification_repository import (
    SQLAlchemyNotificationRepository,
)
from app.infrastructure.repositories.owner_subscription_repository import (
    SQLAlchemyOwnerSubscriptionRepository,
)
from app.use_cases.subscriptions.commands.expire_trialing_subscriptions import (
    ExpireTrialingSubscriptionsCommand,
    ExpireTrialingSubscriptionsHandler,
)


logger = logging.getLogger(__name__)


async def main() -> int:
    init_engine()
    settings = get_settings()
    try:
        async for session in get_session():
            repo = SQLAlchemyOwnerSubscriptionRepository(session)
            notifications = PersistentNotificationService(
                SQLAlchemyNotificationRepository(session),
            )
            handler = ExpireTrialingSubscriptionsHandler(repo, notifications, settings)
            result = await handler.handle(ExpireTrialingSubscriptionsCommand())
            count = result.value or 0
            logger.info("expired %s trialing subscriptions", count)
            return count
        return 0
    finally:
        await dispose_engine()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
