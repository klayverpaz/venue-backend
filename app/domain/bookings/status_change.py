from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Self
from uuid import UUID

from app.domain.accounts.role import Role
from app.domain.bookings.booking_status import BookingStatus
from app.domain.shared.result import Result
from app.domain.shared.value_object import BaseValueObject


_REASON_MAX_LENGTH = 500


@dataclass(frozen=True, slots=True)
class StatusChange(BaseValueObject):
    """Audit record for one transition of a Booking. Immutable; appended to
    Booking._status_history on every state change."""

    STATUS_CHANGE_AT_NOT_TZ_AWARE = "StatusChangeAtNotTzAware"
    STATUS_CHANGE_REASON_TOO_LONG = "StatusChangeReasonTooLong"
    STATUS_CHANGE_INVALID_TRANSITION = "StatusChangeInvalidTransition"

    from_status: BookingStatus
    to_status: BookingStatus
    actor_id: UUID
    actor_role: Role
    at: datetime
    reason: str | None = None

    @classmethod
    def create(
        cls,
        *,
        from_status: BookingStatus,
        to_status: BookingStatus,
        actor_id: UUID,
        actor_role: Role,
        at: datetime,
        reason: str | None = None,
    ) -> Result[Self]:
        if at.tzinfo is None:
            return Result.failure(cls.STATUS_CHANGE_AT_NOT_TZ_AWARE)
        if reason is not None and len(reason) > _REASON_MAX_LENGTH:
            return Result.failure(cls.STATUS_CHANGE_REASON_TOO_LONG)
        if not _is_valid_transition(from_status, to_status):
            return Result.failure(cls.STATUS_CHANGE_INVALID_TRANSITION)
        return Result.success(cls(
            from_status=from_status,
            to_status=to_status,
            actor_id=actor_id,
            actor_role=actor_role,
            at=at,
            reason=reason,
        ))


_VALID_TRANSITIONS: dict[BookingStatus, set[BookingStatus]] = {
    BookingStatus.PENDING: {
        BookingStatus.APPROVED,
        BookingStatus.REJECTED,
        BookingStatus.CANCELLED,
        BookingStatus.EXPIRED,
    },
    BookingStatus.APPROVED: {BookingStatus.CANCELLED},
}


def _is_valid_transition(from_s: BookingStatus, to_s: BookingStatus) -> bool:
    return to_s in _VALID_TRANSITIONS.get(from_s, set())
