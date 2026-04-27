from __future__ import annotations
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import CurrentUser
from app.api.error_handler import unwrap
from app.api.v1.me_notifications.deps import (
    get_list_my_notifications_handler,
    get_mark_notification_read_handler,
)
from app.api.v1.me_notifications.schemas import NotificationListResponse
from app.use_cases.notifications.commands.mark_notification_read import (
    MarkNotificationReadCommand,
    MarkNotificationReadHandler,
)
from app.use_cases.notifications.queries.list_my_notifications import (
    ListMyNotificationsHandler,
    ListMyNotificationsQuery,
)


router = APIRouter(prefix="/v1/me/notifications", tags=["me"])


@router.get("", response_model=NotificationListResponse)
async def list_my_notifications(
    user: CurrentUser,
    handler: ListMyNotificationsHandler = Depends(get_list_my_notifications_handler),
    limit: int = Query(50, ge=1, le=100),
    cursor: UUID | None = Query(None),
    unread_only: bool = Query(False),
):
    dto = unwrap(
        await handler.handle(
            ListMyNotificationsQuery(
                actor_id=user.user_id,
                limit=limit,
                cursor=cursor,
                unread_only=unread_only,
            )
        )
    )
    return NotificationListResponse.from_dto(dto)


@router.post(
    "/{notification_id}/read",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)
async def mark_notification_read(
    notification_id: UUID,
    user: CurrentUser,
    handler: MarkNotificationReadHandler = Depends(
        get_mark_notification_read_handler,
    ),
):
    unwrap(
        await handler.handle(
            MarkNotificationReadCommand(
                actor_id=user.user_id, notification_id=notification_id,
            )
        )
    )
    return None
