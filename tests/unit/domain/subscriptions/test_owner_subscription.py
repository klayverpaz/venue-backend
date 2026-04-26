from __future__ import annotations
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.domain.subscriptions.owner_subscription import OwnerSubscription
from app.domain.subscriptions.sub_status import SubStatus


def _now() -> datetime:
    return datetime(2026, 4, 26, 12, 0, 0, tzinfo=timezone.utc)


# --- create_trialing factory ---

def test_create_trialing_success():
    owner_id = uuid4()
    now = _now()
    r = OwnerSubscription.create_trialing(
        owner_id=owner_id, trial_duration_days=3, now=now,
    )
    assert r.is_success
    sub = r.value
    assert sub.owner_id == owner_id
    assert sub.status is SubStatus.TRIALING
    assert sub.status_changed_at == now
    assert sub.trial_ends_at == now + timedelta(days=3)


def test_create_trialing_status_changed_at_is_tz_aware():
    r = OwnerSubscription.create_trialing(
        owner_id=uuid4(), trial_duration_days=3, now=_now(),
    )
    assert r.value.status_changed_at.tzinfo is not None


# --- __post_init__ cross-field invariants ---

def test_post_init_rejects_trialing_without_trial_ends_at():
    with pytest.raises(ValueError, match="TrialEndsAtRequiredForTrialing"):
        OwnerSubscription(
            owner_id=uuid4(),
            status=SubStatus.TRIALING,
            status_changed_at=_now(),
            trial_ends_at=None,
        )


def test_post_init_rejects_non_trialing_with_trial_ends_at():
    with pytest.raises(ValueError, match="TrialEndsAtForbiddenOutsideTrialing"):
        OwnerSubscription(
            owner_id=uuid4(),
            status=SubStatus.ACTIVE,
            status_changed_at=_now(),
            trial_ends_at=_now() + timedelta(days=3),
        )


def test_post_init_rejects_naive_status_changed_at():
    with pytest.raises(ValueError, match="StatusChangedAtMustBeTzAware"):
        OwnerSubscription(
            owner_id=uuid4(),
            status=SubStatus.ACTIVE,
            status_changed_at=datetime(2026, 4, 26, 12, 0, 0),
            trial_ends_at=None,
        )


def test_post_init_rejects_naive_trial_ends_at():
    with pytest.raises(ValueError, match="TrialEndsAtMustBeTzAware"):
        OwnerSubscription(
            owner_id=uuid4(),
            status=SubStatus.TRIALING,
            status_changed_at=_now(),
            trial_ends_at=datetime(2026, 4, 29, 12, 0, 0),
        )


# --- is_operational ---

def test_is_operational_delegates_to_status():
    sub = OwnerSubscription(
        owner_id=uuid4(), status=SubStatus.ACTIVE,
        status_changed_at=_now(), trial_ends_at=None,
    )
    assert sub.is_operational() is True

    sub2 = OwnerSubscription(
        owner_id=uuid4(), status=SubStatus.INACTIVE,
        status_changed_at=_now(), trial_ends_at=None,
    )
    assert sub2.is_operational() is False


# --- transition_to ---

def test_transition_to_real_change_updates_fields():
    sub = OwnerSubscription.create_trialing(
        owner_id=uuid4(), trial_duration_days=3, now=_now(),
    ).value
    later = _now() + timedelta(hours=1)
    r = sub.transition_to(SubStatus.ACTIVE, now=later, trial_duration_days=3)
    assert r.is_success
    assert sub.status is SubStatus.ACTIVE
    assert sub.status_changed_at == later
    assert sub.trial_ends_at is None
    assert sub.updated_at == later


def test_transition_to_same_status_is_idempotent_no_op():
    sub = OwnerSubscription.create_trialing(
        owner_id=uuid4(), trial_duration_days=3, now=_now(),
    ).value
    original_changed_at = sub.status_changed_at
    original_trial_end = sub.trial_ends_at
    original_updated = sub.updated_at

    later = _now() + timedelta(hours=5)
    r = sub.transition_to(SubStatus.TRIALING, now=later, trial_duration_days=3)
    assert r.is_success
    # Nothing changed.
    assert sub.status is SubStatus.TRIALING
    assert sub.status_changed_at == original_changed_at
    assert sub.trial_ends_at == original_trial_end
    assert sub.updated_at == original_updated


def test_transition_to_trialing_resets_trial_ends_at():
    sub = OwnerSubscription(
        owner_id=uuid4(), status=SubStatus.INACTIVE,
        status_changed_at=_now(), trial_ends_at=None,
    )
    later = _now() + timedelta(days=10)
    r = sub.transition_to(SubStatus.TRIALING, now=later, trial_duration_days=7)
    assert r.is_success
    assert sub.status is SubStatus.TRIALING
    assert sub.trial_ends_at == later + timedelta(days=7)


def test_transition_to_clears_trial_ends_at_on_leave():
    sub = OwnerSubscription.create_trialing(
        owner_id=uuid4(), trial_duration_days=3, now=_now(),
    ).value
    assert sub.trial_ends_at is not None  # sanity
    later = _now() + timedelta(days=1)
    sub.transition_to(SubStatus.PAST_DUE, now=later, trial_duration_days=3)
    assert sub.trial_ends_at is None


def test_transition_to_active_then_back_to_trialing_resets_trial_window():
    sub = OwnerSubscription.create_trialing(
        owner_id=uuid4(), trial_duration_days=3, now=_now(),
    ).value
    t1 = _now() + timedelta(days=1)
    sub.transition_to(SubStatus.ACTIVE, now=t1, trial_duration_days=3)
    assert sub.trial_ends_at is None

    t2 = _now() + timedelta(days=2)
    sub.transition_to(SubStatus.TRIALING, now=t2, trial_duration_days=3)
    assert sub.trial_ends_at == t2 + timedelta(days=3)
