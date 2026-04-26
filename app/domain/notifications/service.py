from __future__ import annotations
from enum import Enum
from typing import Any, Protocol
from uuid import UUID


class NotifKind(str, Enum):
    """Notification kinds. Plan 05 only uses SUBSCRIPTION_CHANGED;
    Plans 07/08 will add BOOKING_REQUESTED, BOOKING_APPROVED, etc.
    """

    SUBSCRIPTION_CHANGED = "SUBSCRIPTION_CHANGED"


class INotificationService(Protocol):
    """Domain port for notifications. Plan 05 ships a no-op logging adapter;
    Plan 07 swaps for a persistent service that writes to the notifications
    table and triggers IEmailSender.
    """

    async def notify(
        self,
        *,
        recipient_id: UUID,
        kind: NotifKind,
        payload: dict[str, Any],
    ) -> None: ...
