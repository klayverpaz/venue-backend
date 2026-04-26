from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from app.domain.notifications.service import NotifKind
from app.domain.shared.entity import BaseEntity


@dataclass(slots=True, kw_only=True)
class Notification(BaseEntity):
    recipient_id: UUID
    kind: NotifKind
    payload: dict[str, Any]
    read_at: datetime | None = None

    @classmethod
    def create(
        cls,
        *,
        recipient_id: UUID,
        kind: NotifKind,
        payload: dict[str, Any],
        now: datetime,
    ) -> "Notification":
        return cls(
            id=uuid4(),
            recipient_id=recipient_id,
            kind=kind,
            payload=dict(payload),
            read_at=None,
            created_at=now,
            updated_at=now,
        )

    def mark_read(self, *, now: datetime) -> None:
        """Idempotent. If already read, no-op (read_at not bumped)."""
        if self.read_at is None:
            self.read_at = now
            self.updated_at = now
