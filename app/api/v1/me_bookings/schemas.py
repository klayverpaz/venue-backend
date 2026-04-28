from __future__ import annotations
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.use_cases.bookings.dtos import (
    AgendaDto, AgendaSlotDto, BookingDto, BookingListDto, StatusChangeDto,
)


class CreateBookingRequest(BaseModel):
    resource_id: UUID
    slot_start_at: datetime
    slot_end_at: datetime
    customer_note: str | None = None


class CancelBookingRequest(BaseModel):
    reason: str | None = None


class RejectBookingRequest(BaseModel):
    reason: str | None = None


class StatusChangeResponse(BaseModel):
    from_status: str
    to_status: str
    actor_id: UUID
    actor_role: str
    at: datetime
    reason: str | None

    @classmethod
    def from_dto(cls, dto: StatusChangeDto) -> "StatusChangeResponse":
        return cls(
            from_status=dto.from_status,
            to_status=dto.to_status,
            actor_id=dto.actor_id,
            actor_role=dto.actor_role,
            at=dto.at,
            reason=dto.reason,
        )


class BookingResponse(BaseModel):
    id: UUID
    resource_id: UUID
    customer_id: UUID
    slot_start_at: datetime
    slot_end_at: datetime
    status: str
    customer_note: str | None
    total_price_cents: int
    status_history: list[StatusChangeResponse]
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_dto(cls, dto: BookingDto) -> "BookingResponse":
        return cls(
            id=dto.id,
            resource_id=dto.resource_id,
            customer_id=dto.customer_id,
            slot_start_at=dto.slot_start_at,
            slot_end_at=dto.slot_end_at,
            status=dto.status,
            customer_note=dto.customer_note,
            total_price_cents=dto.total_price_cents,
            status_history=[
                StatusChangeResponse.from_dto(sc) for sc in dto.status_history
            ],
            created_at=dto.created_at,
            updated_at=dto.updated_at,
        )


class BookingListResponse(BaseModel):
    items: list[BookingResponse]
    page: int
    page_size: int

    @classmethod
    def from_dto(cls, dto: BookingListDto) -> "BookingListResponse":
        return cls(
            items=[BookingResponse.from_dto(b) for b in dto.items],
            page=dto.page,
            page_size=dto.page_size,
        )


class AgendaSlotResponse(BaseModel):
    slot_start_at: datetime
    slot_end_at: datetime
    status: str
    price_cents: int
    booking_id: UUID | None = None
    customer_id: UUID | None = None

    @classmethod
    def from_dto(cls, dto: AgendaSlotDto) -> "AgendaSlotResponse":
        return cls(
            slot_start_at=dto.slot_start_at,
            slot_end_at=dto.slot_end_at,
            status=dto.status,
            price_cents=dto.price_cents,
            booking_id=dto.booking_id,
            customer_id=dto.customer_id,
        )


class AgendaResponse(BaseModel):
    resource_id: UUID
    slots: list[AgendaSlotResponse]

    @classmethod
    def from_dto(cls, dto: AgendaDto) -> "AgendaResponse":
        return cls(
            resource_id=dto.resource_id,
            slots=[AgendaSlotResponse.from_dto(s) for s in dto.slots],
        )
