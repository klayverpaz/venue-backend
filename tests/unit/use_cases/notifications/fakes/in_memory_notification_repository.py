from __future__ import annotations
from uuid import UUID

from app.domain.notifications.notification import Notification
from app.domain.notifications.repository import INotificationRepository
from app.domain.shared.result import Result


class InMemoryNotificationRepository(INotificationRepository):
    """List-backed implementation for handler tests. Mirrors the SQL repo's
    ordering (newest first, cursor-aware) but skips IntegrityError handling.
    """

    def __init__(self) -> None:
        self._rows: list[Notification] = []

    async def add(self, notification: Notification) -> Result[None]:
        self._rows.append(notification)
        return Result.success(None)

    async def get_for_recipient(
        self, notification_id: UUID, recipient_id: UUID,
    ) -> Result[Notification | None]:
        for n in self._rows:
            if n.id == notification_id and n.recipient_id == recipient_id:
                return Result.success(n)
        return Result.success(None)

    async def list_by_recipient(
        self,
        recipient_id: UUID,
        *,
        limit: int,
        cursor: UUID | None,
        unread_only: bool,
    ) -> Result[list[Notification]]:
        ordered = sorted(
            (n for n in self._rows if n.recipient_id == recipient_id),
            key=lambda n: (n.created_at, n.id),
            reverse=True,
        )
        if unread_only:
            ordered = [n for n in ordered if n.read_at is None]
        if cursor is not None:
            cursor_row = next(
                (
                    n for n in self._rows
                    if n.id == cursor and n.recipient_id == recipient_id
                ),
                None,
            )
            if cursor_row is not None:
                ordered = [
                    n for n in ordered
                    if (n.created_at, n.id) < (cursor_row.created_at, cursor_row.id)
                ]
        return Result.success(ordered[:limit])

    async def update(self, notification: Notification) -> Result[None]:
        for i, existing in enumerate(self._rows):
            if existing.id == notification.id:
                self._rows[i] = notification
                return Result.success(None)
        return Result.failure("NotificationNotFound", status_code=404)
