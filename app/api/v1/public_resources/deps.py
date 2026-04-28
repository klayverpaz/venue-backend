from __future__ import annotations
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.session import get_session
from app.infrastructure.repositories.owner_subscription_repository import (
    SQLAlchemyOwnerSubscriptionRepository,
)
from app.infrastructure.repositories.rating_repository import SQLAlchemyRatingRepository
from app.infrastructure.repositories.resource_repository import SQLAlchemyResourceRepository
from app.infrastructure.repositories.resource_type_repository import SQLAlchemyResourceTypeRepository
from app.infrastructure.repositories.user_repository import UserRepository
from app.use_cases.accounts.queries.get_owner_public_page import GetOwnerPublicPageHandler
from app.use_cases.resources.queries.get_public_resource import GetPublicResourceHandler
from app.use_cases.resources.queries.list_public_resources import ListPublicResourcesHandler


def _r(s: Annotated[AsyncSession, Depends(get_session)]):
    return SQLAlchemyResourceRepository(s)


def _u(s: Annotated[AsyncSession, Depends(get_session)]):
    return UserRepository(s)


def _rt(s: Annotated[AsyncSession, Depends(get_session)]):
    return SQLAlchemyResourceTypeRepository(s)


def _sub(s: Annotated[AsyncSession, Depends(get_session)]):
    return SQLAlchemyOwnerSubscriptionRepository(s)


async def get_public_resource_handler(
    s: Annotated[AsyncSession, Depends(get_session)],
    res=Depends(_r), u=Depends(_u), rt=Depends(_rt), sub=Depends(_sub),
):
    return GetPublicResourceHandler(res, u, rt, sub, SQLAlchemyRatingRepository(s))


async def get_list_public_handler(
    s: Annotated[AsyncSession, Depends(get_session)],
    res=Depends(_r), u=Depends(_u), rt=Depends(_rt), sub=Depends(_sub),
):
    return ListPublicResourcesHandler(res, u, rt, sub, SQLAlchemyRatingRepository(s))


async def get_owner_page_handler(
    s: Annotated[AsyncSession, Depends(get_session)],
    u=Depends(_u), sub=Depends(_sub), res=Depends(_r), rt=Depends(_rt),
):
    return GetOwnerPublicPageHandler(u, sub, res, rt, SQLAlchemyRatingRepository(s))
