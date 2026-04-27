from __future__ import annotations
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from app.domain.notifications.notification import Notification
from app.domain.notifications.repository import INotificationRepository
from app.domain.notifications.service import NotifKind


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class PersistentNotificationService:
    """Default INotificationService impl. Persists every call as a Notification
    row. Failures are logged and swallowed — fire-and-forget semantics preserved
    so emitting handlers never fail because of notification trouble.
    """

    def __init__(
        self,
        repository: INotificationRepository,
        *,
        logger: logging.Logger | None = None,
    ) -> None:
        self._repository = repository
        self._logger = logger or logging.getLogger(__name__)

    async def notify(
        self,
        *,
        recipient_id: UUID,
        kind: NotifKind,
        payload: dict[str, Any],
    ) -> None:
        notif = Notification.create(
            recipient_id=recipient_id,
            kind=kind,
            payload=payload,
            now=_utcnow(),
        )
        result = await self._repository.add(notif)
        if result.is_failure:
            self._logger.warning(
                "notification persistence failed",
                extra={
                    "recipient_id": str(recipient_id),
                    "kind": kind.value,
                    "error": result.error,
                },
            )
