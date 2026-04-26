from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Self
from uuid import UUID

from app.domain.shared.entity import BaseEntity
from app.domain.shared.result import Result
from app.domain.subscriptions.sub_status import SubStatus


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(slots=True, kw_only=True)
class OwnerSubscription(BaseEntity):
    OWNER_ID_REQUIRED = "OwnerIdRequired"
    TRIAL_ENDS_AT_REQUIRED_FOR_TRIALING = "TrialEndsAtRequiredForTrialing"
    TRIAL_ENDS_AT_FORBIDDEN_OUTSIDE_TRIALING = "TrialEndsAtForbiddenOutsideTrialing"
    TRIAL_DURATION_DAYS_INVALID = "TrialDurationDaysInvalid"
    STATUS_CHANGED_AT_MUST_BE_TZ_AWARE = "StatusChangedAtMustBeTzAware"
    TRIAL_ENDS_AT_MUST_BE_TZ_AWARE = "TrialEndsAtMustBeTzAware"

    owner_id: UUID
    status: SubStatus
    status_changed_at: datetime
    trial_ends_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.status_changed_at.tzinfo is None:
            raise ValueError(self.STATUS_CHANGED_AT_MUST_BE_TZ_AWARE)
        if self.trial_ends_at is not None and self.trial_ends_at.tzinfo is None:
            raise ValueError(self.TRIAL_ENDS_AT_MUST_BE_TZ_AWARE)
        if self.status is SubStatus.TRIALING and self.trial_ends_at is None:
            raise ValueError(self.TRIAL_ENDS_AT_REQUIRED_FOR_TRIALING)
        if self.status is not SubStatus.TRIALING and self.trial_ends_at is not None:
            raise ValueError(self.TRIAL_ENDS_AT_FORBIDDEN_OUTSIDE_TRIALING)

    @classmethod
    def create_trialing(
        cls,
        *,
        owner_id: UUID,
        trial_duration_days: int,
        now: datetime,
    ) -> Result[Self]:
        return Result.success(cls(
            owner_id=owner_id,
            status=SubStatus.TRIALING,
            status_changed_at=now,
            trial_ends_at=now + timedelta(days=trial_duration_days),
        ))

    def transition_to(
        self,
        new_status: SubStatus,
        *,
        now: datetime,
        trial_duration_days: int,
    ) -> Result[None]:
        """Any-to-any state machine.

        - new_status == self.status → idempotent no-op (no field changes).
        - Otherwise: status, status_changed_at, updated_at updated. trial_ends_at
          is set when entering TRIALING and cleared when leaving it.
        """
        if new_status is self.status:
            return Result.success(None)

        self.status = new_status
        self.status_changed_at = now
        self.updated_at = now
        if new_status is SubStatus.TRIALING:
            self.trial_ends_at = now + timedelta(days=trial_duration_days)
        else:
            self.trial_ends_at = None
        return Result.success(None)

    def is_operational(self) -> bool:
        return self.status.is_operational()
