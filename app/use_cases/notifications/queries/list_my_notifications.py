from __future__ import annotations
from dataclasses import dataclass
from uuid import UUID

from app.domain.notifications.repository import INotificationRepository
from app.domain.shared.result import Result
from app.use_cases.notifications.dtos import NotificationDto, NotificationListDto


_MAX_LIMIT = 100


@dataclass(frozen=True, kw_only=True, slots=True)
class ListMyNotificationsQuery:
    actor_id: UUID
    limit: int = 50
    cursor: UUID | None = None
    unread_only: bool = False


class ListMyNotificationsHandler:
    def __init__(self, repository: INotificationRepository) -> None:
        self._repository = repository

    async def handle(
        self, query: ListMyNotificationsQuery,
    ) -> Result[NotificationListDto]:
        limit = max(1, min(query.limit, _MAX_LIMIT))
        list_r = await self._repository.list_by_recipient(
            query.actor_id,
            limit=limit + 1,           # fetch one extra to know if more pages exist
            cursor=query.cursor,
            unread_only=query.unread_only,
        )
        if list_r.is_failure:
            return Result.from_failure(list_r)
        rows = list_r.value
        has_more = len(rows) > limit
        page = rows[:limit]
        next_cursor = page[-1].id if has_more and page else None
        items = tuple(NotificationDto.from_entity(n) for n in page)
        return Result.success(NotificationListDto(items=items, next_cursor=next_cursor))
