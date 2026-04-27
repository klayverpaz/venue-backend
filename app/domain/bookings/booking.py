from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Self
from uuid import UUID, uuid4

from app.domain.accounts.role import Role
from app.domain.bookings.booking_status import BookingStatus
from app.domain.bookings.status_change import StatusChange
from app.domain.shared.entity import BaseEntity
from app.domain.shared.result import Result
from app.domain.shared.value_objects.date_time_range import DateTimeRange
from app.domain.shared.value_objects.money import Money
from app.domain.shared.value_objects.short_description import ShortDescription


@dataclass(slots=True, kw_only=True)
class Booking(BaseEntity):
    resource_id: UUID
    customer_id: UUID
    slot_range: DateTimeRange
    status: BookingStatus
    total_price_cents: Money
    customer_note: ShortDescription | None = None
    _status_history: tuple[StatusChange, ...] = field(default_factory=tuple)

    @classmethod
    def create_pending(
        cls,
        *,
        resource_id: UUID,
        customer_id: UUID,
        slot_range: DateTimeRange,
        total_price_cents: Money,
        customer_note: ShortDescription | None,
        now: datetime,
    ) -> "Booking":
        return cls(
            id=uuid4(),
            resource_id=resource_id,
            customer_id=customer_id,
            slot_range=slot_range,
            status=BookingStatus.PENDING,
            total_price_cents=total_price_cents,
            customer_note=customer_note,
            _status_history=(),
            created_at=now,
            updated_at=now,
        )

    @property
    def status_history(self) -> tuple[StatusChange, ...]:
        return self._status_history

    def slot_count(self, slot_duration_minutes: int) -> int:
        return self.slot_range.duration_minutes() // slot_duration_minutes

    def approve(self, *, actor_id: UUID, now: datetime) -> Result[None]:
        return self._transition(
            to_status=BookingStatus.APPROVED,
            actor_id=actor_id,
            actor_role=Role.OWNER,
            now=now,
            reason=None,
        )

    def reject(
        self, *, actor_id: UUID, now: datetime, reason: str | None = None,
    ) -> Result[None]:
        return self._transition(
            to_status=BookingStatus.REJECTED,
            actor_id=actor_id,
            actor_role=Role.OWNER,
            now=now,
            reason=reason,
        )

    def cancel(
        self, *, actor_id: UUID, actor_role: Role, now: datetime,
        reason: str | None = None,
    ) -> Result[None]:
        return self._transition(
            to_status=BookingStatus.CANCELLED,
            actor_id=actor_id,
            actor_role=actor_role,
            now=now,
            reason=reason,
        )

    def expire(self, *, now: datetime) -> Result[None]:
        return self._transition(
            to_status=BookingStatus.EXPIRED,
            actor_id=self.customer_id,
            actor_role=Role.CUSTOMER,
            now=now,
            reason="slot_start_passed_with_no_decision",
        )

    def _transition(
        self,
        *,
        to_status: BookingStatus,
        actor_id: UUID,
        actor_role: Role,
        now: datetime,
        reason: str | None,
    ) -> Result[None]:
        change_r = StatusChange.create(
            from_status=self.status,
            to_status=to_status,
            actor_id=actor_id,
            actor_role=actor_role,
            at=now,
            reason=reason,
        )
        if change_r.is_failure:
            return Result.from_failure(change_r)
        self.status = to_status
        self._status_history = (*self._status_history, change_r.value)
        self.updated_at = now
        return Result.success(None)
