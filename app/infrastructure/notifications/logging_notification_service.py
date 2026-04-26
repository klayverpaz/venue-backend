from __future__ import annotations
import logging
from typing import Any
from uuid import UUID

from app.domain.notifications.service import NotifKind


class LoggingNotificationService:
    """No-op adapter shipped with Plan 05. Plan 07 swaps for the persistent
    service that writes to the notifications table and triggers IEmailSender.
    """

    def __init__(self, logger: logging.Logger | None = None) -> None:
        self._logger = logger or logging.getLogger(__name__)

    async def notify(
        self, *, recipient_id: UUID, kind: NotifKind, payload: dict[str, Any],
    ) -> None:
        self._logger.info(
            "notification fired",
            extra={
                "recipient_id": str(recipient_id),
                "kind": kind.value,
                "payload": payload,
            },
        )
