from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from app.domain.notifications.repository import INotificationRepository
from app.domain.shared.result import Result


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True, kw_only=True, slots=True)
class MarkNotificationReadCommand:
    actor_id: UUID
    notification_id: UUID


class MarkNotificationReadHandler:
    def __init__(self, repository: INotificationRepository) -> None:
        self._repository = repository

    async def handle(
        self, cmd: MarkNotificationReadCommand,
    ) -> Result[None]:
        get_r = await self._repository.get_for_recipient(
            cmd.notification_id, cmd.actor_id,
        )
        if get_r.is_failure:
            return Result.from_failure(get_r)
        notif = get_r.value
        if notif is None:
            return Result.failure("NotificationNotFound", status_code=404)
        if notif.read_at is None:
            notif.mark_read(now=_utcnow())
            update_r = await self._repository.update(notif)
            if update_r.is_failure:
                return Result.from_failure(update_r)
        return Result.success(None)
