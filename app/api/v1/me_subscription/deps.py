from __future__ import annotations
from typing import Annotated
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.session import get_session
from app.infrastructure.repositories.owner_subscription_repository import (
    SQLAlchemyOwnerSubscriptionRepository,
)
from app.use_cases.subscriptions.queries.get_my_subscription import (
    GetMySubscriptionHandler,
)


async def get_subscription_repo(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> SQLAlchemyOwnerSubscriptionRepository:
    return SQLAlchemyOwnerSubscriptionRepository(session)


async def get_my_subscription_handler(
    repo: Annotated[
        SQLAlchemyOwnerSubscriptionRepository, Depends(get_subscription_repo),
    ],
) -> GetMySubscriptionHandler:
    return GetMySubscriptionHandler(repo)
