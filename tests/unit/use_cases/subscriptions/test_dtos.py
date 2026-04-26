from __future__ import annotations
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.domain.subscriptions.owner_subscription import OwnerSubscription
from app.domain.subscriptions.sub_status import SubStatus
from app.use_cases.subscriptions.dtos import OwnerSubscriptionDto


def test_dto_from_entity_trialing():
    now = datetime(2026, 4, 26, 12, 0, 0, tzinfo=timezone.utc)
    sub = OwnerSubscription.create_trialing(
        owner_id=uuid4(), trial_duration_days=3, now=now,
    ).value
    dto = OwnerSubscriptionDto.from_entity(sub)
    assert dto.id == sub.id
    assert dto.owner_id == sub.owner_id
    assert dto.status == "TRIALING"
    assert dto.status_changed_at == now
    assert dto.trial_ends_at == now + timedelta(days=3)
    assert dto.is_operational is True


def test_dto_from_entity_inactive_has_no_trial_ends_at():
    now = datetime(2026, 4, 26, 12, 0, 0, tzinfo=timezone.utc)
    sub = OwnerSubscription(
        owner_id=uuid4(), status=SubStatus.INACTIVE,
        status_changed_at=now, trial_ends_at=None,
    )
    dto = OwnerSubscriptionDto.from_entity(sub)
    assert dto.status == "INACTIVE"
    assert dto.trial_ends_at is None
    assert dto.is_operational is False
