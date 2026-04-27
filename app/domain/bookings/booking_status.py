from __future__ import annotations
from enum import Enum


class BookingStatus(str, Enum):
    """Booking lifecycle states (spec §6.1).

    State machine:
        PENDING → APPROVED | REJECTED | CANCELLED | EXPIRED
        APPROVED → CANCELLED
        REJECTED, CANCELLED, EXPIRED are terminal.
    """

    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"

    def is_active(self) -> bool:
        """True for PENDING and APPROVED only. Used by natural dedup —
        only active bookings block creation of overlapping requests."""
        return self in {BookingStatus.PENDING, BookingStatus.APPROVED}

    def is_terminal(self) -> bool:
        return self in {
            BookingStatus.REJECTED,
            BookingStatus.CANCELLED,
            BookingStatus.EXPIRED,
        }
