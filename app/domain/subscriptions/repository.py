from __future__ import annotations
from datetime import datetime
from typing import Protocol
from uuid import UUID

from app.domain.shared.result import Result
from app.domain.subscriptions.owner_subscription import OwnerSubscription


class ISubscriptionRepository(Protocol):
    """Persistence port for the subscriptions feature."""

    async def add(self, sub: OwnerSubscription) -> Result[None]:
        """Persist a new subscription. Returns failure on owner_id conflict."""
        ...

    async def update(self, sub: OwnerSubscription) -> Result[None]:
        """Persist changes to an existing subscription."""
        ...

    async def get_by_id(self, sub_id: UUID) -> OwnerSubscription | None: ...

    async def get_by_owner_id(self, owner_id: UUID) -> OwnerSubscription | None: ...

    async def list_all(
        self,
        *,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[OwnerSubscription]: ...

    async def list_trialing_with_expiry_before(
        self, threshold: datetime,
    ) -> list[OwnerSubscription]: ...
