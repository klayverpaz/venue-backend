from __future__ import annotations
from datetime import datetime
from uuid import UUID

from app.domain.shared.result import Result
from app.domain.subscriptions.owner_subscription import OwnerSubscription
from app.domain.subscriptions.sub_status import SubStatus


class InMemorySubscriptionRepository:
    """Test fake implementing ISubscriptionRepository."""

    def __init__(self) -> None:
        self._by_id: dict[UUID, OwnerSubscription] = {}

    async def add(self, sub: OwnerSubscription) -> Result[None]:
        if any(s.owner_id == sub.owner_id for s in self._by_id.values()):
            return Result.failure("OwnerAlreadyHasSubscription", status_code=409)
        self._by_id[sub.id] = sub
        return Result.success(None)

    async def update(self, sub: OwnerSubscription) -> Result[None]:
        if sub.id not in self._by_id:
            return Result.failure("SubscriptionNotFound", status_code=404)
        self._by_id[sub.id] = sub
        return Result.success(None)

    async def get_by_id(self, sub_id: UUID) -> OwnerSubscription | None:
        return self._by_id.get(sub_id)

    async def get_by_owner_id(self, owner_id: UUID) -> OwnerSubscription | None:
        return next(
            (s for s in self._by_id.values() if s.owner_id == owner_id),
            None,
        )

    async def list_all(
        self, *, status: str | None = None, limit: int = 50, offset: int = 0,
    ) -> list[OwnerSubscription]:
        rows = sorted(self._by_id.values(), key=lambda s: s.created_at)
        if status is not None:
            rows = [s for s in rows if s.status.value == status]
        return rows[offset:offset + limit]

    async def list_trialing_with_expiry_before(
        self, threshold: datetime,
    ) -> list[OwnerSubscription]:
        return [
            s for s in self._by_id.values()
            if s.status is SubStatus.TRIALING
            and s.trial_ends_at is not None
            and s.trial_ends_at < threshold
        ]

    async def list_by_owner_ids(self, owner_ids):
        ids_set = set(owner_ids)
        return [s for s in self._by_id.values() if s.owner_id in ids_set]
