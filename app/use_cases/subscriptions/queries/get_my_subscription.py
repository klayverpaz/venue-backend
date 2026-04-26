from __future__ import annotations
from dataclasses import dataclass
from uuid import UUID

from app.domain.shared.result import Result
from app.domain.subscriptions.repository import ISubscriptionRepository
from app.use_cases.subscriptions.dtos import OwnerSubscriptionDto


@dataclass(frozen=True, slots=True)
class GetMySubscriptionQuery:
    requester_id: UUID


class GetMySubscriptionHandler:
    def __init__(self, subscriptions: ISubscriptionRepository) -> None:
        self._subscriptions = subscriptions

    async def handle(self, q: GetMySubscriptionQuery) -> Result[OwnerSubscriptionDto]:
        sub = await self._subscriptions.get_by_owner_id(q.requester_id)
        if sub is None:
            return Result.failure("SubscriptionNotFound", status_code=404)
        return Result.success(OwnerSubscriptionDto.from_entity(sub))
