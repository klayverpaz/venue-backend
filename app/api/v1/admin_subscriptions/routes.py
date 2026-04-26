from __future__ import annotations
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import require_role
from app.api.error_codes import translate
from app.api.error_handler import unwrap
from app.api.v1.admin_subscriptions.deps import (
    get_list_handler,
    get_set_status_handler,
)
from app.api.v1.admin_subscriptions.schemas import (
    OwnerSubscriptionResponse,
    SetSubscriptionStatusRequest,
    SubscriptionListResponse,
)
from app.domain.accounts.role import Role
from app.domain.subscriptions.sub_status import SubStatus
from app.use_cases.subscriptions.commands.set_owner_subscription_status import (
    SetOwnerSubscriptionStatusCommand,
    SetOwnerSubscriptionStatusHandler,
)
from app.use_cases.subscriptions.queries.list_subscriptions import (
    ListSubscriptionsHandler,
    ListSubscriptionsQuery,
)


router = APIRouter(
    prefix="/v1/admin",
    tags=["admin:subscriptions"],
    dependencies=[Depends(require_role(Role.ADMIN))],
)


@router.post(
    "/owners/{owner_id}/subscription",
    response_model=OwnerSubscriptionResponse,
)
async def set_owner_subscription_status(
    owner_id: UUID,
    body: SetSubscriptionStatusRequest,
    handler: SetOwnerSubscriptionStatusHandler = Depends(get_set_status_handler),
):
    try:
        status = SubStatus(body.status)
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "InvalidSubscriptionStatus",
                "message": translate("InvalidSubscriptionStatus"),
            },
        )
    cmd = SetOwnerSubscriptionStatusCommand(owner_id=owner_id, status=status)
    dto = unwrap(await handler.handle(cmd))
    return OwnerSubscriptionResponse.from_dto(dto)


@router.get("/subscriptions", response_model=SubscriptionListResponse)
async def list_subscriptions(
    status: str | None = Query(default=None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    handler: ListSubscriptionsHandler = Depends(get_list_handler),
):
    if status is not None:
        try:
            SubStatus(status)
        except ValueError:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "InvalidSubscriptionStatus",
                    "message": translate("InvalidSubscriptionStatus"),
                },
            )
    dtos = unwrap(await handler.handle(ListSubscriptionsQuery(
        status=status, limit=limit, offset=offset,
    )))
    return SubscriptionListResponse(
        items=[OwnerSubscriptionResponse.from_dto(d) for d in dtos],
        limit=limit,
        offset=offset,
    )
