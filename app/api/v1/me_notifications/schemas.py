from __future__ import annotations
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.use_cases.notifications.dtos import NotificationDto, NotificationListDto


class NotificationResponse(BaseModel):
    id: UUID
    kind: str
    payload: dict[str, Any]
    read_at: datetime | None
    created_at: datetime

    @classmethod
    def from_dto(cls, dto: NotificationDto) -> "NotificationResponse":
        return cls(
            id=dto.id,
            kind=dto.kind,
            payload=dto.payload,
            read_at=dto.read_at,
            created_at=dto.created_at,
        )


class NotificationListResponse(BaseModel):
    items: list[NotificationResponse]
    next_cursor: UUID | None

    @classmethod
    def from_dto(cls, dto: NotificationListDto) -> "NotificationListResponse":
        return cls(
            items=[NotificationResponse.from_dto(n) for n in dto.items],
            next_cursor=dto.next_cursor,
        )
