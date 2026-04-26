from __future__ import annotations
from datetime import datetime
from typing import Self
from uuid import UUID
from pydantic import BaseModel

from app.use_cases.subscriptions.dtos import OwnerSubscriptionDto


class SetSubscriptionStatusRequest(BaseModel):
    status: str  # validated against SubStatus inside the route


class OwnerSubscriptionResponse(BaseModel):
    id: UUID
    owner_id: UUID
    status: str
    status_changed_at: datetime
    trial_ends_at: datetime | None
    is_operational: bool
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_dto(cls, dto: OwnerSubscriptionDto) -> Self:
        return cls(
            id=dto.id,
            owner_id=dto.owner_id,
            status=dto.status,
            status_changed_at=dto.status_changed_at,
            trial_ends_at=dto.trial_ends_at,
            is_operational=dto.is_operational,
            created_at=dto.created_at,
            updated_at=dto.updated_at,
        )


class SubscriptionListResponse(BaseModel):
    items: list[OwnerSubscriptionResponse]
    limit: int
    offset: int
