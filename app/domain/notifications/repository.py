from __future__ import annotations
from typing import Protocol
from uuid import UUID

from app.domain.notifications.notification import Notification
from app.domain.shared.result import Result


class INotificationRepository(Protocol):
    async def add(self, notification: Notification) -> Result[None]: ...

    async def get_for_recipient(
        self,
        notification_id: UUID,
        recipient_id: UUID,
    ) -> Result[Notification | None]: ...

    async def list_by_recipient(
        self,
        recipient_id: UUID,
        *,
        limit: int,
        cursor: UUID | None,
        unread_only: bool,
    ) -> Result[list[Notification]]: ...

    async def update(self, notification: Notification) -> Result[None]: ...
