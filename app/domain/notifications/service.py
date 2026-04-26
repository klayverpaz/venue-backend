from __future__ import annotations
from enum import Enum
from typing import Any, Protocol
from uuid import UUID


class NotifKind(str, Enum):
    """Notification kinds. Plan 07 grows the booking values that Plan 08
    will emit. BOOKING_RATED is intentionally absent (Plan 07 dropped it for
    MVP — see plan-07-notifications-design.md §1).
    """

    SUBSCRIPTION_CHANGED = "SUBSCRIPTION_CHANGED"
    BOOKING_REQUESTED = "BOOKING_REQUESTED"
    BOOKING_APPROVED = "BOOKING_APPROVED"
    BOOKING_REJECTED = "BOOKING_REJECTED"
    BOOKING_CANCELLED = "BOOKING_CANCELLED"


class INotificationService(Protocol):
    """Domain port for fire-and-forget notification dispatch. Plan 07 swaps
    the no-op logging adapter for a persistent service that writes a
    Notification row per call. Email is intentionally not in scope.
    """

    async def notify(
        self,
        *,
        recipient_id: UUID,
        kind: NotifKind,
        payload: dict[str, Any],
    ) -> None: ...
