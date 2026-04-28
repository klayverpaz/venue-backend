from __future__ import annotations
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.session import get_session
from app.infrastructure.repositories.booking_repository import (
    SQLAlchemyBookingRepository,
)
from app.infrastructure.repositories.rating_repository import (
    SQLAlchemyRatingRepository,
)
from app.infrastructure.repositories.resource_repository import (
    SQLAlchemyResourceRepository,
)
from app.use_cases.ratings.commands.create_rating import CreateRatingHandler
from app.use_cases.ratings.commands.update_rating import UpdateRatingHandler
from app.use_cases.ratings.queries.list_my_ratings import ListMyRatingsHandler
from app.use_cases.ratings.queries.list_public_ratings import (
    ListPublicRatingsForResourceHandler,
)


async def get_create_rating_handler(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CreateRatingHandler:
    return CreateRatingHandler(
        ratings=SQLAlchemyRatingRepository(session),
        bookings=SQLAlchemyBookingRepository(session),
    )


async def get_update_rating_handler(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> UpdateRatingHandler:
    return UpdateRatingHandler(
        ratings=SQLAlchemyRatingRepository(session),
    )


async def get_list_my_ratings_handler(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ListMyRatingsHandler:
    return ListMyRatingsHandler(
        ratings=SQLAlchemyRatingRepository(session),
    )


async def get_list_public_ratings_handler(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ListPublicRatingsForResourceHandler:
    return ListPublicRatingsForResourceHandler(
        ratings=SQLAlchemyRatingRepository(session),
        resources=SQLAlchemyResourceRepository(session),
    )
