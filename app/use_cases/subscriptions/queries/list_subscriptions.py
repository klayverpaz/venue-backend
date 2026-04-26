from __future__ import annotations
from dataclasses import dataclass

from app.domain.shared.result import Result
from app.domain.subscriptions.repository import ISubscriptionRepository
from app.use_cases.subscriptions.dtos import OwnerSubscriptionDto


@dataclass(frozen=True, slots=True)
class ListSubscriptionsQuery:
    status: str | None
    limit: int
    offset: int


class ListSubscriptionsHandler:
    def __init__(self, subscriptions: ISubscriptionRepository) -> None:
        self._subscriptions = subscriptions

    async def handle(
        self, q: ListSubscriptionsQuery,
    ) -> Result[list[OwnerSubscriptionDto]]:
        rows = await self._subscriptions.list_all(
            status=q.status, limit=q.limit, offset=q.offset,
        )
        return Result.success([OwnerSubscriptionDto.from_entity(s) for s in rows])
