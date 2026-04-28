from __future__ import annotations
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import CurrentUser
from app.api.error_handler import unwrap
from app.api.v1.me_bookings.deps import (
    get_approve_booking_handler,
    get_cancel_booking_handler,
    get_list_my_bookings_handler,
    get_my_booking_handler,
    get_reject_booking_handler,
    get_request_booking_handler,
)
from app.api.v1.me_bookings.schemas import (
    BookingListResponse,
    BookingResponse,
    CancelBookingRequest,
    CreateBookingRequest,
    RejectBookingRequest,
)
from app.domain.bookings.booking_status import BookingStatus
from app.use_cases.bookings.commands.approve_booking import (
    ApproveBookingCommand,
    ApproveBookingHandler,
)
from app.use_cases.bookings.commands.cancel_booking import (
    CancelBookingCommand,
    CancelBookingHandler,
)
from app.use_cases.bookings.commands.reject_booking import (
    RejectBookingCommand,
    RejectBookingHandler,
)
from app.use_cases.bookings.commands.request_booking import (
    RequestBookingCommand,
    RequestBookingHandler,
)
from app.use_cases.bookings.queries.get_my_booking import (
    GetMyBookingHandler,
    GetMyBookingQuery,
)
from app.use_cases.bookings.queries.list_my_bookings import (
    ListMyBookingsHandler,
    ListMyBookingsQuery,
)


router = APIRouter(prefix="/v1/me/bookings", tags=["me"])


@router.post(
    "",
    response_model=BookingResponse,
    status_code=status.HTTP_201_CREATED,
)
async def request_booking(
    body: CreateBookingRequest,
    user: CurrentUser,
    handler: Annotated[
        RequestBookingHandler, Depends(get_request_booking_handler),
    ],
):
    dto = unwrap(await handler.handle(RequestBookingCommand(
        actor_id=user.user_id,
        resource_id=body.resource_id,
        slot_start_at=body.slot_start_at,
        slot_end_at=body.slot_end_at,
        customer_note=body.customer_note,
    )))
    return BookingResponse.from_dto(dto)


@router.get("", response_model=BookingListResponse)
async def list_my_bookings(
    user: CurrentUser,
    handler: Annotated[
        ListMyBookingsHandler, Depends(get_list_my_bookings_handler),
    ],
    status_filter: BookingStatus | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
):
    dto = unwrap(await handler.handle(ListMyBookingsQuery(
        actor_id=user.user_id, status=status_filter,
        page=page, page_size=page_size,
    )))
    return BookingListResponse.from_dto(dto)


@router.get("/{booking_id}", response_model=BookingResponse)
async def get_my_booking(
    booking_id: UUID,
    user: CurrentUser,
    handler: Annotated[
        GetMyBookingHandler, Depends(get_my_booking_handler),
    ],
):
    dto = unwrap(await handler.handle(GetMyBookingQuery(
        actor_id=user.user_id, booking_id=booking_id,
    )))
    return BookingResponse.from_dto(dto)


@router.post("/{booking_id}/cancel", response_model=BookingResponse)
async def cancel_booking(
    booking_id: UUID,
    body: CancelBookingRequest,
    user: CurrentUser,
    handler: Annotated[
        CancelBookingHandler, Depends(get_cancel_booking_handler),
    ],
):
    dto = unwrap(await handler.handle(CancelBookingCommand(
        actor_id=user.user_id, booking_id=booking_id, reason=body.reason,
    )))
    return BookingResponse.from_dto(dto)


@router.post("/{booking_id}/approve", response_model=BookingResponse)
async def approve_booking(
    booking_id: UUID,
    user: CurrentUser,
    handler: Annotated[
        ApproveBookingHandler, Depends(get_approve_booking_handler),
    ],
):
    dto = unwrap(await handler.handle(ApproveBookingCommand(
        actor_id=user.user_id, booking_id=booking_id,
    )))
    return BookingResponse.from_dto(dto)


@router.post("/{booking_id}/reject", response_model=BookingResponse)
async def reject_booking(
    booking_id: UUID,
    body: RejectBookingRequest,
    user: CurrentUser,
    handler: Annotated[
        RejectBookingHandler, Depends(get_reject_booking_handler),
    ],
):
    dto = unwrap(await handler.handle(RejectBookingCommand(
        actor_id=user.user_id, booking_id=booking_id, reason=body.reason,
    )))
    return BookingResponse.from_dto(dto)
