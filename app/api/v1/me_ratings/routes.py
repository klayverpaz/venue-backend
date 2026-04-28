from __future__ import annotations
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import CurrentUser
from app.api.error_handler import unwrap
from app.api.v1.me_ratings.deps import (
    get_create_rating_handler,
    get_list_my_ratings_handler,
    get_update_rating_handler,
)
from app.api.v1.me_ratings.schemas import (
    CreateRatingBody,
    RatingListResponse,
    RatingResponse,
    UpdateRatingBody,
)
from app.use_cases.ratings.commands.create_rating import (
    CreateRatingCommand, CreateRatingHandler,
)
from app.use_cases.ratings.commands.update_rating import (
    UpdateRatingCommand, UpdateRatingHandler,
)
from app.use_cases.ratings.queries.list_my_ratings import (
    ListMyRatingsHandler, ListMyRatingsQuery,
)


router = APIRouter(prefix="/v1/me", tags=["me:ratings"])


@router.post(
    "/bookings/{booking_id}/rating",
    response_model=RatingResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_rating(
    booking_id: UUID,
    body: CreateRatingBody,
    user: CurrentUser,
    handler: Annotated[
        CreateRatingHandler, Depends(get_create_rating_handler),
    ],
):
    dto = unwrap(await handler.handle(CreateRatingCommand(
        actor_id=user.user_id,
        booking_id=booking_id,
        score=body.score,
        comment=body.comment,
    )))
    return RatingResponse.from_dto(dto)


@router.patch(
    "/bookings/{booking_id}/rating",
    response_model=RatingResponse,
)
async def update_rating(
    booking_id: UUID,
    body: UpdateRatingBody,
    user: CurrentUser,
    handler: Annotated[
        UpdateRatingHandler, Depends(get_update_rating_handler),
    ],
):
    # Handler resolves rating from booking_id internally — the route stays
    # booking-keyed (per spec §7.3), handler does the lookup + ownership +
    # edit-window check in one place.
    dto = unwrap(await handler.handle(UpdateRatingCommand(
        actor_id=user.user_id,
        booking_id=booking_id,
        score=body.score,
        comment=body.comment,
    )))
    return RatingResponse.from_dto(dto)


@router.get("/ratings", response_model=RatingListResponse)
async def list_my_ratings(
    user: CurrentUser,
    handler: Annotated[
        ListMyRatingsHandler, Depends(get_list_my_ratings_handler),
    ],
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
):
    dto = unwrap(await handler.handle(ListMyRatingsQuery(
        actor_id=user.user_id, page=page, page_size=page_size,
    )))
    return RatingListResponse.from_dto(dto)
