from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from app.domain.notifications.notification import Notification


@dataclass(frozen=True, kw_only=True, slots=True)
class NotificationDto:
    id: UUID
    kind: str
    payload: dict[str, Any]
    read_at: datetime | None
    created_at: datetime

    @classmethod
    def from_entity(cls, notif: Notification) -> "NotificationDto":
        return cls(
            id=notif.id,
            kind=notif.kind.value,
            payload=dict(notif.payload),
            read_at=notif.read_at,
            created_at=notif.created_at,
        )


@dataclass(frozen=True, kw_only=True, slots=True)
class NotificationListDto:
    items: tuple[NotificationDto, ...]
    next_cursor: UUID | None
