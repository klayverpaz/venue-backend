from __future__ import annotations
from typing import Any
from uuid import UUID

from app.domain.notifications.service import NotifKind


class FakeNotificationService:
    """Captures notify() calls for assertion in handler tests."""

    def __init__(self) -> None:
        self.calls: list[tuple[UUID, NotifKind, dict[str, Any]]] = []

    async def notify(
        self, *, recipient_id: UUID, kind: NotifKind, payload: dict[str, Any],
    ) -> None:
        self.calls.append((recipient_id, kind, payload))
