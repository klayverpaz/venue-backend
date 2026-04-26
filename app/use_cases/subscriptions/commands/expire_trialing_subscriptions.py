from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone

from app.core.config import Settings
from app.domain.notifications.service import INotificationService, NotifKind
from app.domain.shared.result import Result
from app.domain.subscriptions.repository import ISubscriptionRepository
from app.domain.subscriptions.sub_status import SubStatus


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True, slots=True)
class ExpireTrialingSubscriptionsCommand:
    pass


class ExpireTrialingSubscriptionsHandler:
    def __init__(
        self,
        subscriptions: ISubscriptionRepository,
        notifications: INotificationService,
        config: Settings,
    ) -> None:
        self._subscriptions = subscriptions
        self._notifications = notifications
        self._config = config

    async def handle(
        self, cmd: ExpireTrialingSubscriptionsCommand,
    ) -> Result[int]:
        now = _utcnow()
        expired = await self._subscriptions.list_trialing_with_expiry_before(now)
        count = 0
        for sub in expired:
            sub.transition_to(
                SubStatus.INACTIVE,
                now=now,
                trial_duration_days=self._config.trial_duration_days,
            )
            update_r = await self._subscriptions.update(sub)
            if update_r.is_failure:
                continue
            await self._notifications.notify(
                recipient_id=sub.owner_id,
                kind=NotifKind.SUBSCRIPTION_CHANGED,
                payload={
                    "old_status": "TRIALING",
                    "new_status": "INACTIVE",
                    "reason": "trial_expired",
                },
            )
            count += 1
        return Result.success(count)
