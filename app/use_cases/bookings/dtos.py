from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal
from uuid import UUID

from app.domain.bookings.booking import Booking


@dataclass(frozen=True, kw_only=True, slots=True)
class StatusChangeDto:
    from_status: str
    to_status: str
    actor_id: UUID
    actor_role: str
    at: datetime
    reason: str | None


@dataclass(frozen=True, kw_only=True, slots=True)
class BookingDto:
    id: UUID
    resource_id: UUID
    customer_id: UUID
    slot_start_at: datetime
    slot_end_at: datetime
    status: str
    customer_note: str | None
    total_price_cents: int
    status_history: tuple[StatusChangeDto, ...]
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_entity(cls, b: Booking) -> "BookingDto":
        return cls(
            id=b.id,
            resource_id=b.resource_id,
            customer_id=b.customer_id,
            slot_start_at=b.slot_range.start_at,
            slot_end_at=b.slot_range.end_at,
            status=b.status.value,
            customer_note=b.customer_note.value if b.customer_note else None,
            total_price_cents=b.total_price_cents.cents,
            status_history=tuple(
                StatusChangeDto(
                    from_status=sc.from_status.value,
                    to_status=sc.to_status.value,
                    actor_id=sc.actor_id,
                    actor_role=sc.actor_role.value,
                    at=sc.at,
                    reason=sc.reason,
                )
                for sc in b.status_history
            ),
            created_at=b.created_at,
            updated_at=b.updated_at,
        )


@dataclass(frozen=True, kw_only=True, slots=True)
class BookingListDto:
    items: tuple[BookingDto, ...]
    page: int
    page_size: int


SlotStatus = Literal["AVAILABLE", "PENDING", "APPROVED"]


@dataclass(frozen=True, kw_only=True, slots=True)
class AgendaSlotDto:
    slot_start_at: datetime
    slot_end_at: datetime
    status: SlotStatus
    price_cents: int
    booking_id: UUID | None = None       # None for AVAILABLE / public view
    customer_id: UUID | None = None      # owner view only


@dataclass(frozen=True, kw_only=True, slots=True)
class AgendaDto:
    resource_id: UUID
    slots: tuple[AgendaSlotDto, ...]
