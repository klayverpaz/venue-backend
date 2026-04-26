from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from app.core.config import Settings
from app.domain.accounts.repository import IUserRepository
from app.domain.accounts.role import Role
from app.domain.notifications.service import INotificationService, NotifKind
from app.domain.shared.result import Result
from app.domain.subscriptions.repository import ISubscriptionRepository
from app.domain.subscriptions.sub_status import SubStatus
from app.use_cases.subscriptions.dtos import OwnerSubscriptionDto


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True, slots=True)
class SetOwnerSubscriptionStatusCommand:
    owner_id: UUID
    status: SubStatus


class SetOwnerSubscriptionStatusHandler:
    def __init__(
        self,
        users: IUserRepository,
        subscriptions: ISubscriptionRepository,
        notifications: INotificationService,
        config: Settings,
    ) -> None:
        self._users = users
        self._subscriptions = subscriptions
        self._notifications = notifications
        self._config = config

    async def handle(
        self, cmd: SetOwnerSubscriptionStatusCommand,
    ) -> Result[OwnerSubscriptionDto]:
        user = await self._users.get_by_id(cmd.owner_id)
        if user is None:
            return Result.failure("OwnerNotFound", status_code=404)
        if user.role is not Role.OWNER:
            return Result.failure("UserIsNotOwner", status_code=422)

        sub = await self._subscriptions.get_by_owner_id(cmd.owner_id)
        if sub is None:
            return Result.failure("SubscriptionNotFound", status_code=404)

        old_status = sub.status
        sub.transition_to(
            cmd.status,
            now=_utcnow(),
            trial_duration_days=self._config.trial_duration_days,
        )

        if old_status is cmd.status:
            return Result.success(OwnerSubscriptionDto.from_entity(sub))

        update_r = await self._subscriptions.update(sub)
        if update_r.is_failure:
            return Result.from_failure(update_r)

        await self._notifications.notify(
            recipient_id=sub.owner_id,
            kind=NotifKind.SUBSCRIPTION_CHANGED,
            payload={
                "old_status": old_status.value,
                "new_status": cmd.status.value,
                "reason": "admin_action",
            },
        )
        return Result.success(OwnerSubscriptionDto.from_entity(sub))
