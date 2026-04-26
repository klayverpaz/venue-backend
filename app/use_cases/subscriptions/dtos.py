from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Self
from uuid import UUID

from app.domain.subscriptions.owner_subscription import OwnerSubscription


@dataclass(frozen=True, slots=True)
class OwnerSubscriptionDto:
    id: UUID
    owner_id: UUID
    status: str
    status_changed_at: datetime
    trial_ends_at: datetime | None
    is_operational: bool
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_entity(cls, sub: OwnerSubscription) -> Self:
        return cls(
            id=sub.id,
            owner_id=sub.owner_id,
            status=sub.status.value,
            status_changed_at=sub.status_changed_at,
            trial_ends_at=sub.trial_ends_at,
            is_operational=sub.is_operational(),
            created_at=sub.created_at,
            updated_at=sub.updated_at,
        )
