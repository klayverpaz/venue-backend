from __future__ import annotations
from fastapi import APIRouter, Depends

from app.api.deps import CurrentUser
from app.api.error_handler import unwrap
from app.api.v1.admin_subscriptions.schemas import OwnerSubscriptionResponse
from app.api.v1.me_subscription.deps import get_my_subscription_handler
from app.use_cases.subscriptions.queries.get_my_subscription import (
    GetMySubscriptionHandler,
    GetMySubscriptionQuery,
)


router = APIRouter(prefix="/v1/me", tags=["me"])


@router.get("/subscription", response_model=OwnerSubscriptionResponse)
async def get_my_subscription(
    user: CurrentUser,
    handler: GetMySubscriptionHandler = Depends(get_my_subscription_handler),
):
    dto = unwrap(await handler.handle(GetMySubscriptionQuery(requester_id=user.user_id)))
    return OwnerSubscriptionResponse.from_dto(dto)
