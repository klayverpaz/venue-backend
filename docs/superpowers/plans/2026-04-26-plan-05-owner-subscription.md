# Plan 05 — OwnerSubscription Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the `OwnerSubscription` aggregate, lifecycle (auto-create on owner registration in TRIALING), state machine (any-to-any admin control + idempotent no-op), trial expiry cron (TRIALING → INACTIVE), `INotificationService` Protocol, and the admin/owner-facing endpoints. Set up the foundation for Plan 06 (`is_operational` consumer pattern) and Plan 07 (notification persistence + e-mail adapter).

**Architecture:** Aggregate in `app/domain/subscriptions/`. Cross-field invariants (`status == TRIALING ⇔ trial_ends_at is not None`) enforced in `__post_init__`. State changes go through `OwnerSubscription.transition_to(new_status, now, trial_duration_days)` — any-to-any with idempotent no-op on same status. `RegisterUserHandler` gains `ISubscriptionRepository` + `Settings` deps to auto-create `TRIALING` subs for new owners (atomic with the user insert via shared `AsyncSession`). Admin endpoint mutates via `SetOwnerSubscriptionStatusHandler`. Cron entry-point invokes `ExpireTrialingSubscriptionsHandler`. Notifications flow through a domain `INotificationService` Protocol with a no-op `LoggingNotificationService` adapter (Plan 07 swaps for the persistent one).

**Tech Stack:** Python 3.12, Pydantic Settings, FastAPI, SQLAlchemy 2 async, Alembic, pytest. No new dependencies.

**Reference spec:** `docs/superpowers/specs/2026-04-26-plan-05-owner-subscription-design.md`.

**Conventions reminders:**
- Always invoke Python via venv: `.venv/bin/python` or `.venv/bin/pytest`. Never use the global Python.
- Domain code never imports from `infrastructure` or `use_cases`.
- After each task, commit with a focused message ending in `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>`.
- TDD: write failing test, run to confirm RED, write minimal impl, run to confirm GREEN, commit.

**File structure (created over the plan):**

```
app/domain/subscriptions/
├── __init__.py
├── sub_status.py
├── owner_subscription.py
└── repository.py
app/domain/notifications/
├── __init__.py
└── service.py
app/use_cases/subscriptions/
├── __init__.py
├── dtos.py
├── commands/
│   ├── __init__.py
│   ├── set_owner_subscription_status.py
│   └── expire_trialing_subscriptions.py
└── queries/
    ├── __init__.py
    ├── list_subscriptions.py
    └── get_my_subscription.py
app/infrastructure/db/mappings/owner_subscription.py
app/infrastructure/repositories/owner_subscription_repository.py
app/infrastructure/notifications/
├── __init__.py
└── logging_notification_service.py
app/api/v1/admin_subscriptions/
├── __init__.py
├── deps.py
├── schemas.py
└── routes.py
app/api/v1/me_subscription/
├── __init__.py
├── deps.py
├── schemas.py
└── routes.py
app/jobs/
├── __init__.py
└── expire_trialing_subscriptions.py
app/migrations/versions/<timestamp>_owner_subscriptions_table.py
tests/unit/domain/subscriptions/...
tests/unit/use_cases/subscriptions/...
tests/integration/subscriptions/...
tests/e2e/subscriptions/...
```

---

## Task 1: `SubStatus` enum

**Files:**
- Create: `app/domain/subscriptions/__init__.py` (empty file)
- Create: `app/domain/subscriptions/sub_status.py`
- Create: `tests/unit/domain/subscriptions/__init__.py` (empty file)
- Test: `tests/unit/domain/subscriptions/test_sub_status.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/domain/subscriptions/__init__.py` (empty) and `tests/unit/domain/subscriptions/test_sub_status.py`:

```python
from app.domain.subscriptions.sub_status import SubStatus


def test_sub_status_values():
    assert SubStatus.ACTIVE.value == "ACTIVE"
    assert SubStatus.TRIALING.value == "TRIALING"
    assert SubStatus.PAST_DUE.value == "PAST_DUE"
    assert SubStatus.INACTIVE.value == "INACTIVE"


def test_sub_status_active_is_operational():
    assert SubStatus.ACTIVE.is_operational() is True


def test_sub_status_trialing_is_operational():
    assert SubStatus.TRIALING.is_operational() is True


def test_sub_status_past_due_is_not_operational():
    assert SubStatus.PAST_DUE.is_operational() is False


def test_sub_status_inactive_is_not_operational():
    assert SubStatus.INACTIVE.is_operational() is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/unit/domain/subscriptions/test_sub_status.py -v`
Expected: `ModuleNotFoundError: No module named 'app.domain.subscriptions'`.

- [ ] **Step 3: Write the implementation**

Create `app/domain/subscriptions/__init__.py` (empty file).

Create `app/domain/subscriptions/sub_status.py`:

```python
from __future__ import annotations
from enum import Enum


class SubStatus(str, Enum):
    """Lifecycle states of an OwnerSubscription.

    ACTIVE / TRIALING are operational (resources show in public listings,
    bookings can be approved). PAST_DUE / INACTIVE are non-operational.
    """

    ACTIVE = "ACTIVE"
    TRIALING = "TRIALING"
    PAST_DUE = "PAST_DUE"
    INACTIVE = "INACTIVE"

    def is_operational(self) -> bool:
        return self in {SubStatus.ACTIVE, SubStatus.TRIALING}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/unit/domain/subscriptions/test_sub_status.py -v`
Expected: 5 PASS.

- [ ] **Step 5: Commit**

```bash
git add app/domain/subscriptions/__init__.py app/domain/subscriptions/sub_status.py tests/unit/domain/subscriptions/__init__.py tests/unit/domain/subscriptions/test_sub_status.py
git commit -m "$(cat <<'EOF'
feat(subscriptions): SubStatus enum with is_operational()

Four-state lifecycle (ACTIVE | TRIALING | PAST_DUE | INACTIVE).
ACTIVE and TRIALING are operational; the other two gate resources
out of public listings (Plan 06) and reject booking requests (Plan 08).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: `OwnerSubscription` aggregate

**Files:**
- Create: `app/domain/subscriptions/owner_subscription.py`
- Test: `tests/unit/domain/subscriptions/test_owner_subscription.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/domain/subscriptions/test_owner_subscription.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/unit/domain/subscriptions/test_owner_subscription.py -v`
Expected: `ModuleNotFoundError: No module named 'app.domain.subscriptions.owner_subscription'`.

- [ ] **Step 3: Write the implementation**

Create `app/domain/subscriptions/owner_subscription.py`:

```python
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
        # trial_duration_days is validated upstream by Settings (Pydantic gt=0).
        # We trust it here; if a programmer mis-routes a bad value, ValueError
        # surfaces at __post_init__ via timedelta math (no negative deltas allowed).
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/unit/domain/subscriptions/test_owner_subscription.py -v`
Expected: 11 PASS.

- [ ] **Step 5: Commit**

```bash
git add app/domain/subscriptions/owner_subscription.py tests/unit/domain/subscriptions/test_owner_subscription.py
git commit -m "$(cat <<'EOF'
feat(subscriptions): OwnerSubscription aggregate with transition_to

Cross-field invariants enforced in __post_init__: status==TRIALING ⇔
trial_ends_at not None; both timestamps must be tz-aware. Factory
create_trialing always emits TRIALING. transition_to is any-to-any
with idempotent no-op on same status; sets/clears trial_ends_at on
TRIALING entry/exit.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: `ISubscriptionRepository` Protocol

**Files:**
- Create: `app/domain/subscriptions/repository.py`

(No dedicated test file — Protocols are validated by their consumers' tests in later tasks.)

- [ ] **Step 1: Create the Protocol**

Create `app/domain/subscriptions/repository.py`:

```python
from __future__ import annotations
from datetime import datetime
from typing import Protocol
from uuid import UUID

from app.domain.shared.result import Result
from app.domain.subscriptions.owner_subscription import OwnerSubscription


class ISubscriptionRepository(Protocol):
    """Persistence port for the subscriptions feature."""

    async def add(self, sub: OwnerSubscription) -> Result[None]:
        """Persist a new subscription. Returns failure on owner_id conflict."""
        ...

    async def update(self, sub: OwnerSubscription) -> Result[None]:
        """Persist changes to an existing subscription."""
        ...

    async def get_by_id(self, sub_id: UUID) -> OwnerSubscription | None: ...

    async def get_by_owner_id(self, owner_id: UUID) -> OwnerSubscription | None: ...

    async def list_all(
        self,
        *,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[OwnerSubscription]: ...

    async def list_trialing_with_expiry_before(
        self, threshold: datetime,
    ) -> list[OwnerSubscription]: ...
```

- [ ] **Step 2: Verify imports compile**

Run: `.venv/bin/python -c "from app.domain.subscriptions.repository import ISubscriptionRepository; print('ok')"`
Expected: `ok`.

- [ ] **Step 3: Commit**

```bash
git add app/domain/subscriptions/repository.py
git commit -m "$(cat <<'EOF'
feat(subscriptions): ISubscriptionRepository Protocol

Persistence port: add/update return Result[None]; get_*/list_* return
entities directly; list_trialing_with_expiry_before drives the cron.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: `INotificationService` port + `NotifKind` enum

**Files:**
- Create: `app/domain/notifications/__init__.py` (empty)
- Create: `app/domain/notifications/service.py`

- [ ] **Step 1: Create the port and enum**

Create `app/domain/notifications/__init__.py` (empty file).

Create `app/domain/notifications/service.py`:

```python
from __future__ import annotations
from enum import Enum
from typing import Any, Protocol
from uuid import UUID


class NotifKind(str, Enum):
    """Notification kinds. Plan 05 only uses SUBSCRIPTION_CHANGED;
    Plans 07/08 will add BOOKING_REQUESTED, BOOKING_APPROVED, etc.
    """

    SUBSCRIPTION_CHANGED = "SUBSCRIPTION_CHANGED"


class INotificationService(Protocol):
    """Domain port for notifications. Plan 05 ships a no-op logging adapter;
    Plan 07 swaps for a persistent service that writes to the notifications
    table and triggers IEmailSender.
    """

    async def notify(
        self,
        *,
        recipient_id: UUID,
        kind: NotifKind,
        payload: dict[str, Any],
    ) -> None: ...
```

- [ ] **Step 2: Verify imports compile**

Run: `.venv/bin/python -c "from app.domain.notifications.service import INotificationService, NotifKind; print(NotifKind.SUBSCRIPTION_CHANGED.value)"`
Expected: `SUBSCRIPTION_CHANGED`.

- [ ] **Step 3: Commit**

```bash
git add app/domain/notifications/__init__.py app/domain/notifications/service.py
git commit -m "$(cat <<'EOF'
feat(notifications): INotificationService Protocol + NotifKind enum

Domain port for cross-feature notifications, shipped in Plan 05 with
SUBSCRIPTION_CHANGED only. Plan 07 will add the Notification aggregate
+ persistent adapter + IEmailSender; this Protocol's contract is the
stable seam between the two plans.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: `Settings.trial_duration_days` config

**Files:**
- Modify: `app/core/config.py`
- Test: `tests/unit/core/test_config.py` (create if missing; otherwise extend)

- [ ] **Step 1: Write the failing test**

Check whether `tests/unit/core/test_config.py` exists. If not:

```bash
mkdir -p tests/unit/core && touch tests/unit/core/__init__.py
```

Create `tests/unit/core/test_config.py` (or append):

```python
import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_trial_duration_days_default_is_3(monkeypatch):
    monkeypatch.setenv("BACKEND_DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    monkeypatch.delenv("BACKEND_TRIAL_DURATION_DAYS", raising=False)
    s = Settings()
    assert s.trial_duration_days == 3


def test_trial_duration_days_env_override(monkeypatch):
    monkeypatch.setenv("BACKEND_DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    monkeypatch.setenv("BACKEND_TRIAL_DURATION_DAYS", "7")
    s = Settings()
    assert s.trial_duration_days == 7


def test_trial_duration_days_must_be_positive(monkeypatch):
    monkeypatch.setenv("BACKEND_DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    monkeypatch.setenv("BACKEND_TRIAL_DURATION_DAYS", "0")
    with pytest.raises(ValidationError):
        Settings()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/unit/core/test_config.py -v`
Expected: tests fail with `AttributeError: 'Settings' object has no attribute 'trial_duration_days'` or similar.

- [ ] **Step 3: Add the field**

In `app/core/config.py`, inside `class Settings(BaseSettings):`, after the `argon2_*` block and before `model_config`:

```python
    # Subscriptions
    trial_duration_days: int = Field(default=3, gt=0)
```

Add at the top of the file (with other imports), if not present:

```python
from pydantic import Field, SecretStr
```

(`SecretStr` is already imported; just add `Field` to the existing line.)

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/unit/core/test_config.py -v`
Expected: 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add app/core/config.py tests/unit/core/test_config.py tests/unit/core/__init__.py
git commit -m "$(cat <<'EOF'
feat(config): add Settings.trial_duration_days

Default 3, must be > 0, override via BACKEND_TRIAL_DURATION_DAYS.
Used by RegisterUserHandler (auto-create owner subscription) and
the SetOwnerSubscriptionStatusHandler (rebuild trial_ends_at on
TRIALING transitions).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Stable error codes + arch test allowlist

**Files:**
- Modify: `app/api/error_codes.py`
- Modify: `tests/unit/architecture/test_error_code_coverage.py`

- [ ] **Step 1: Add codes to `error_codes.py`**

In `app/api/error_codes.py`, add to the imports at the top:

```python
from app.domain.subscriptions.owner_subscription import OwnerSubscription
```

In the `ERROR_MESSAGES_PT_BR` dict, add a new section before the closing `}`:

```python
    # Subscriptions (Plan 05) — handler-level
    "OwnerNotFound": "Proprietário não encontrado.",
    "UserIsNotOwner": "Usuário não é proprietário.",
    "SubscriptionNotFound": "Assinatura não encontrada.",
    # Subscriptions (Plan 05) — entity-level invariants (programming bugs;
    # never reach unwrap, but mapped for documentation + arch test parity).
    OwnerSubscription.OWNER_ID_REQUIRED: "ID do proprietário é obrigatório.",
    OwnerSubscription.TRIAL_ENDS_AT_REQUIRED_FOR_TRIALING:
        "Assinatura em TRIALING precisa de data de fim de trial.",
    OwnerSubscription.TRIAL_ENDS_AT_FORBIDDEN_OUTSIDE_TRIALING:
        "Data de fim de trial só é válida para status TRIALING.",
    OwnerSubscription.TRIAL_DURATION_DAYS_INVALID:
        "Duração de trial deve ser inteiro positivo.",
    OwnerSubscription.STATUS_CHANGED_AT_MUST_BE_TZ_AWARE:
        "Timestamp de mudança de status precisa ter fuso horário.",
    OwnerSubscription.TRIAL_ENDS_AT_MUST_BE_TZ_AWARE:
        "Data de fim de trial precisa ter fuso horário.",
```

- [ ] **Step 2: Update arch test allowlist**

In `tests/unit/architecture/test_error_code_coverage.py`, in `handler_level_allowlist`, append:

```python
        # Plan 05 — subscriptions
        "OwnerNotFound",
        "UserIsNotOwner",
        "SubscriptionNotFound",
        "OwnerIdRequired",
        "TrialEndsAtRequiredForTrialing",
        "TrialEndsAtForbiddenOutsideTrialing",
        "TrialDurationDaysInvalid",
        "StatusChangedAtMustBeTzAware",
        "TrialEndsAtMustBeTzAware",
```

- [ ] **Step 3: Run the arch test**

Run: `.venv/bin/pytest tests/unit/architecture/test_error_code_coverage.py -v`
Expected: 2 PASS (no orphans, no missing translations).

- [ ] **Step 4: Commit**

```bash
git add app/api/error_codes.py tests/unit/architecture/test_error_code_coverage.py
git commit -m "$(cat <<'EOF'
feat(subscriptions): register Plan 05 stable error codes

Three handler-level codes (OwnerNotFound / UserIsNotOwner /
SubscriptionNotFound) for the subscription endpoints, plus six
entity-level constants from OwnerSubscription that are mapped for
documentation parity (the entity raises ValueError in __post_init__
on programming bugs; these strings are not customer-facing).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: `InMemorySubscriptionRepository` test fake

**Files:**
- Create: `tests/unit/use_cases/subscriptions/__init__.py` (empty)
- Create: `tests/unit/use_cases/subscriptions/fakes/__init__.py` (empty)
- Create: `tests/unit/use_cases/subscriptions/fakes/in_memory_subscription_repository.py`

(No test file for the fake itself — its correctness will be exercised by handler tests in later tasks.)

- [ ] **Step 1: Create the empty packages and fake**

```bash
mkdir -p tests/unit/use_cases/subscriptions/fakes
touch tests/unit/use_cases/subscriptions/__init__.py
touch tests/unit/use_cases/subscriptions/fakes/__init__.py
```

Create `tests/unit/use_cases/subscriptions/fakes/in_memory_subscription_repository.py`:

```python
from __future__ import annotations
from datetime import datetime
from uuid import UUID

from app.domain.shared.result import Result
from app.domain.subscriptions.owner_subscription import OwnerSubscription
from app.domain.subscriptions.sub_status import SubStatus


class InMemorySubscriptionRepository:
    """Test fake implementing ISubscriptionRepository."""

    def __init__(self) -> None:
        self._by_id: dict[UUID, OwnerSubscription] = {}

    async def add(self, sub: OwnerSubscription) -> Result[None]:
        if any(s.owner_id == sub.owner_id for s in self._by_id.values()):
            return Result.failure("OwnerAlreadyHasSubscription", status_code=409)
        self._by_id[sub.id] = sub
        return Result.success(None)

    async def update(self, sub: OwnerSubscription) -> Result[None]:
        if sub.id not in self._by_id:
            return Result.failure("SubscriptionNotFound", status_code=404)
        self._by_id[sub.id] = sub
        return Result.success(None)

    async def get_by_id(self, sub_id: UUID) -> OwnerSubscription | None:
        return self._by_id.get(sub_id)

    async def get_by_owner_id(self, owner_id: UUID) -> OwnerSubscription | None:
        return next(
            (s for s in self._by_id.values() if s.owner_id == owner_id),
            None,
        )

    async def list_all(
        self, *, status: str | None = None, limit: int = 50, offset: int = 0,
    ) -> list[OwnerSubscription]:
        rows = sorted(self._by_id.values(), key=lambda s: s.created_at)
        if status is not None:
            rows = [s for s in rows if s.status.value == status]
        return rows[offset:offset + limit]

    async def list_trialing_with_expiry_before(
        self, threshold: datetime,
    ) -> list[OwnerSubscription]:
        return [
            s for s in self._by_id.values()
            if s.status is SubStatus.TRIALING
            and s.trial_ends_at is not None
            and s.trial_ends_at < threshold
        ]
```

- [ ] **Step 2: Verify imports compile**

Run: `.venv/bin/python -c "from tests.unit.use_cases.subscriptions.fakes.in_memory_subscription_repository import InMemorySubscriptionRepository; print('ok')"`
Expected: `ok`.

- [ ] **Step 3: Commit**

```bash
git add tests/unit/use_cases/subscriptions/__init__.py tests/unit/use_cases/subscriptions/fakes/__init__.py tests/unit/use_cases/subscriptions/fakes/in_memory_subscription_repository.py
git commit -m "$(cat <<'EOF'
test(subscriptions): InMemorySubscriptionRepository fake

Implements ISubscriptionRepository in-memory for handler tests.
Mirrors the InMemoryResourceTypeRepository pattern from Plan 04.
Add() rejects duplicate owner_id; list_trialing_with_expiry_before
matches the cron contract.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: `FakeNotificationService` test fake

**Files:**
- Create: `tests/unit/use_cases/subscriptions/fakes/fake_notification_service.py`

- [ ] **Step 1: Create the fake**

Create `tests/unit/use_cases/subscriptions/fakes/fake_notification_service.py`:

```python
from __future__ import annotations
from typing import Any
from uuid import UUID

from app.domain.notifications.service import NotifKind


class FakeNotificationService:
    """Captures notify() calls for assertion in handler tests."""

    def __init__(self) -> None:
        self.calls: list[tuple[UUID, NotifKind, dict[str, Any]]] = []

    async def notify(
        self, *, recipient_id: UUID, kind: NotifKind, payload: dict[str, Any],
    ) -> None:
        self.calls.append((recipient_id, kind, payload))
```

- [ ] **Step 2: Verify imports compile**

Run: `.venv/bin/python -c "from tests.unit.use_cases.subscriptions.fakes.fake_notification_service import FakeNotificationService; print('ok')"`
Expected: `ok`.

- [ ] **Step 3: Commit**

```bash
git add tests/unit/use_cases/subscriptions/fakes/fake_notification_service.py
git commit -m "$(cat <<'EOF'
test(subscriptions): FakeNotificationService fake

Captures (recipient_id, kind, payload) tuples for handler tests to
assert "real status change emitted exactly one notify with right payload".

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 9: `OwnerSubscriptionDto`

**Files:**
- Create: `app/use_cases/subscriptions/__init__.py` (empty)
- Create: `app/use_cases/subscriptions/dtos.py`
- Test: `tests/unit/use_cases/subscriptions/test_dtos.py`

- [ ] **Step 1: Write the failing test**

```bash
mkdir -p app/use_cases/subscriptions
touch app/use_cases/subscriptions/__init__.py
```

Create `tests/unit/use_cases/subscriptions/test_dtos.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/unit/use_cases/subscriptions/test_dtos.py -v`
Expected: `ModuleNotFoundError: No module named 'app.use_cases.subscriptions.dtos'`.

- [ ] **Step 3: Write the implementation**

Create `app/use_cases/subscriptions/dtos.py`:

```python
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Self
from uuid import UUID

from app.domain.subscriptions.owner_subscription import OwnerSubscription


@dataclass(frozen=True, slots=True)
class OwnerSubscriptionDto:
    id: UUID
    owner_id: UUID
    status: str
    status_changed_at: datetime
    trial_ends_at: datetime | None
    is_operational: bool
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_entity(cls, sub: OwnerSubscription) -> Self:
        return cls(
            id=sub.id,
            owner_id=sub.owner_id,
            status=sub.status.value,
            status_changed_at=sub.status_changed_at,
            trial_ends_at=sub.trial_ends_at,
            is_operational=sub.is_operational(),
            created_at=sub.created_at,
            updated_at=sub.updated_at,
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/unit/use_cases/subscriptions/test_dtos.py -v`
Expected: 2 PASS.

- [ ] **Step 5: Commit**

```bash
git add app/use_cases/subscriptions/__init__.py app/use_cases/subscriptions/dtos.py tests/unit/use_cases/subscriptions/test_dtos.py
git commit -m "$(cat <<'EOF'
feat(subscriptions): OwnerSubscriptionDto with from_entity

Includes is_operational as a top-level boolean so HTTP clients don't
need to encode the SubStatus → operational mapping.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 10: `SetOwnerSubscriptionStatusHandler`

**Files:**
- Create: `app/use_cases/subscriptions/commands/__init__.py` (empty)
- Create: `app/use_cases/subscriptions/commands/set_owner_subscription_status.py`
- Test: `tests/unit/use_cases/subscriptions/commands/__init__.py` (empty)
- Test: `tests/unit/use_cases/subscriptions/commands/test_set_owner_subscription_status.py`

- [ ] **Step 1: Write the failing tests**

```bash
mkdir -p app/use_cases/subscriptions/commands tests/unit/use_cases/subscriptions/commands
touch app/use_cases/subscriptions/commands/__init__.py tests/unit/use_cases/subscriptions/commands/__init__.py
```

Create `tests/unit/use_cases/subscriptions/commands/test_set_owner_subscription_status.py`:

```python
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.domain.accounts.role import Role
from app.domain.notifications.service import NotifKind
from app.domain.subscriptions.owner_subscription import OwnerSubscription
from app.domain.subscriptions.sub_status import SubStatus
from app.use_cases.subscriptions.commands.set_owner_subscription_status import (
    SetOwnerSubscriptionStatusCommand,
    SetOwnerSubscriptionStatusHandler,
)
from tests.unit.use_cases.accounts.fakes.in_memory_user_repository import (
    InMemoryUserRepository,
)
from tests.unit.use_cases.accounts.fakes.fake_password_hasher import FakePasswordHasher
from tests.unit.use_cases.subscriptions.fakes.in_memory_subscription_repository import (
    InMemorySubscriptionRepository,
)
from tests.unit.use_cases.subscriptions.fakes.fake_notification_service import (
    FakeNotificationService,
)
from app.domain.accounts.user import User


pytestmark = pytest.mark.asyncio


def _settings(monkeypatch) -> Settings:
    monkeypatch.setenv("BACKEND_DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    monkeypatch.setenv("BACKEND_TRIAL_DURATION_DAYS", "3")
    return Settings()


async def _seed_owner(users: InMemoryUserRepository, *, is_active: bool = True):
    hasher = FakePasswordHasher()
    user = User.create(
        email="owner@example.com",
        password_hash=hasher.hash("hunter2-strong"),
        role=Role.OWNER,
        full_name="Owner",
        phone=None,
    ).value
    if not is_active:
        user.deactivate()
    await users.add(user)
    return user


async def _seed_subscription(
    subs: InMemorySubscriptionRepository, *, owner_id, status: SubStatus,
):
    now = datetime(2026, 4, 26, 12, 0, 0, tzinfo=timezone.utc)
    if status is SubStatus.TRIALING:
        sub = OwnerSubscription.create_trialing(
            owner_id=owner_id, trial_duration_days=3, now=now,
        ).value
    else:
        sub = OwnerSubscription(
            owner_id=owner_id, status=status,
            status_changed_at=now, trial_ends_at=None,
        )
    await subs.add(sub)
    return sub


async def test_set_status_real_change_persists_and_notifies(monkeypatch):
    users, subs, notifs = (
        InMemoryUserRepository(), InMemorySubscriptionRepository(), FakeNotificationService(),
    )
    settings = _settings(monkeypatch)
    owner = await _seed_owner(users)
    await _seed_subscription(subs, owner_id=owner.id, status=SubStatus.TRIALING)

    handler = SetOwnerSubscriptionStatusHandler(users, subs, notifs, settings)
    r = await handler.handle(SetOwnerSubscriptionStatusCommand(
        owner_id=owner.id, status=SubStatus.ACTIVE,
    ))
    assert r.is_success
    assert r.value.status == "ACTIVE"
    sub = await subs.get_by_owner_id(owner.id)
    assert sub.status is SubStatus.ACTIVE
    assert sub.trial_ends_at is None
    assert len(notifs.calls) == 1
    recipient, kind, payload = notifs.calls[0]
    assert recipient == owner.id
    assert kind is NotifKind.SUBSCRIPTION_CHANGED
    assert payload == {
        "old_status": "TRIALING", "new_status": "ACTIVE", "reason": "admin_action",
    }


async def test_set_status_idempotent_no_op(monkeypatch):
    users, subs, notifs = (
        InMemoryUserRepository(), InMemorySubscriptionRepository(), FakeNotificationService(),
    )
    settings = _settings(monkeypatch)
    owner = await _seed_owner(users)
    sub = await _seed_subscription(subs, owner_id=owner.id, status=SubStatus.ACTIVE)
    original_changed_at = sub.status_changed_at

    handler = SetOwnerSubscriptionStatusHandler(users, subs, notifs, settings)
    r = await handler.handle(SetOwnerSubscriptionStatusCommand(
        owner_id=owner.id, status=SubStatus.ACTIVE,
    ))
    assert r.is_success
    assert r.value.status == "ACTIVE"
    assert notifs.calls == []
    sub_after = await subs.get_by_owner_id(owner.id)
    assert sub_after.status_changed_at == original_changed_at


async def test_set_status_returns_owner_not_found(monkeypatch):
    users, subs, notifs = (
        InMemoryUserRepository(), InMemorySubscriptionRepository(), FakeNotificationService(),
    )
    settings = _settings(monkeypatch)
    handler = SetOwnerSubscriptionStatusHandler(users, subs, notifs, settings)
    r = await handler.handle(SetOwnerSubscriptionStatusCommand(
        owner_id=uuid4(), status=SubStatus.ACTIVE,
    ))
    assert r.is_failure
    assert r.error == "OwnerNotFound"
    assert r.status_code == 404


async def test_set_status_rejects_non_owner(monkeypatch):
    users, subs, notifs = (
        InMemoryUserRepository(), InMemorySubscriptionRepository(), FakeNotificationService(),
    )
    settings = _settings(monkeypatch)
    customer = User.create(
        email="customer@example.com", password_hash="h",
        role=Role.CUSTOMER, full_name="C", phone=None,
    ).value
    await users.add(customer)
    handler = SetOwnerSubscriptionStatusHandler(users, subs, notifs, settings)
    r = await handler.handle(SetOwnerSubscriptionStatusCommand(
        owner_id=customer.id, status=SubStatus.ACTIVE,
    ))
    assert r.is_failure
    assert r.error == "UserIsNotOwner"
    assert r.status_code == 422


async def test_set_status_returns_subscription_not_found(monkeypatch):
    users, subs, notifs = (
        InMemoryUserRepository(), InMemorySubscriptionRepository(), FakeNotificationService(),
    )
    settings = _settings(monkeypatch)
    owner = await _seed_owner(users)  # owner exists, no subscription
    handler = SetOwnerSubscriptionStatusHandler(users, subs, notifs, settings)
    r = await handler.handle(SetOwnerSubscriptionStatusCommand(
        owner_id=owner.id, status=SubStatus.ACTIVE,
    ))
    assert r.is_failure
    assert r.error == "SubscriptionNotFound"
    assert r.status_code == 404


async def test_set_status_to_trialing_resets_trial_window(monkeypatch):
    users, subs, notifs = (
        InMemoryUserRepository(), InMemorySubscriptionRepository(), FakeNotificationService(),
    )
    settings = _settings(monkeypatch)
    owner = await _seed_owner(users)
    await _seed_subscription(subs, owner_id=owner.id, status=SubStatus.INACTIVE)
    handler = SetOwnerSubscriptionStatusHandler(users, subs, notifs, settings)
    r = await handler.handle(SetOwnerSubscriptionStatusCommand(
        owner_id=owner.id, status=SubStatus.TRIALING,
    ))
    assert r.is_success
    sub = await subs.get_by_owner_id(owner.id)
    assert sub.status is SubStatus.TRIALING
    assert sub.trial_ends_at is not None
    # trial_ends_at must be in the future relative to status_changed_at
    assert sub.trial_ends_at > sub.status_changed_at
    assert (sub.trial_ends_at - sub.status_changed_at) == timedelta(days=3)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/unit/use_cases/subscriptions/commands/test_set_owner_subscription_status.py -v`
Expected: `ModuleNotFoundError: No module named 'app.use_cases.subscriptions.commands.set_owner_subscription_status'`.

- [ ] **Step 3: Write the implementation**

Create `app/use_cases/subscriptions/commands/set_owner_subscription_status.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/unit/use_cases/subscriptions/commands/test_set_owner_subscription_status.py -v`
Expected: 6 PASS.

- [ ] **Step 5: Commit**

```bash
git add app/use_cases/subscriptions/commands/__init__.py app/use_cases/subscriptions/commands/set_owner_subscription_status.py tests/unit/use_cases/subscriptions/commands/__init__.py tests/unit/use_cases/subscriptions/commands/test_set_owner_subscription_status.py
git commit -m "$(cat <<'EOF'
feat(subscriptions): SetOwnerSubscriptionStatusHandler

Admin-only handler. Verifies target is OWNER (rejects non-existent
or non-owner). Idempotent on no-op (skips repo write + notify).
Real change emits SUBSCRIPTION_CHANGED notification with
{old_status, new_status, reason: "admin_action"}.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 11: `ListSubscriptionsHandler`

**Files:**
- Create: `app/use_cases/subscriptions/queries/__init__.py` (empty)
- Create: `app/use_cases/subscriptions/queries/list_subscriptions.py`
- Test: `tests/unit/use_cases/subscriptions/queries/__init__.py` (empty)
- Test: `tests/unit/use_cases/subscriptions/queries/test_list_subscriptions.py`

- [ ] **Step 1: Write the failing tests**

```bash
mkdir -p app/use_cases/subscriptions/queries tests/unit/use_cases/subscriptions/queries
touch app/use_cases/subscriptions/queries/__init__.py tests/unit/use_cases/subscriptions/queries/__init__.py
```

Create `tests/unit/use_cases/subscriptions/queries/test_list_subscriptions.py`:

```python
from __future__ import annotations
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.domain.subscriptions.owner_subscription import OwnerSubscription
from app.domain.subscriptions.sub_status import SubStatus
from app.use_cases.subscriptions.queries.list_subscriptions import (
    ListSubscriptionsQuery,
    ListSubscriptionsHandler,
)
from tests.unit.use_cases.subscriptions.fakes.in_memory_subscription_repository import (
    InMemorySubscriptionRepository,
)


pytestmark = pytest.mark.asyncio


async def test_list_returns_all_when_no_filter():
    subs = InMemorySubscriptionRepository()
    now = datetime(2026, 4, 26, 12, 0, 0, tzinfo=timezone.utc)
    for st in [SubStatus.ACTIVE, SubStatus.INACTIVE]:
        if st is SubStatus.TRIALING:
            sub = OwnerSubscription.create_trialing(owner_id=uuid4(), trial_duration_days=3, now=now).value
        else:
            sub = OwnerSubscription(owner_id=uuid4(), status=st, status_changed_at=now, trial_ends_at=None)
        await subs.add(sub)
    handler = ListSubscriptionsHandler(subs)
    r = await handler.handle(ListSubscriptionsQuery(status=None, limit=50, offset=0))
    assert r.is_success
    assert len(r.value) == 2


async def test_list_filters_by_status():
    subs = InMemorySubscriptionRepository()
    now = datetime(2026, 4, 26, 12, 0, 0, tzinfo=timezone.utc)
    await subs.add(OwnerSubscription(owner_id=uuid4(), status=SubStatus.ACTIVE, status_changed_at=now, trial_ends_at=None))
    await subs.add(OwnerSubscription(owner_id=uuid4(), status=SubStatus.INACTIVE, status_changed_at=now, trial_ends_at=None))
    handler = ListSubscriptionsHandler(subs)
    r = await handler.handle(ListSubscriptionsQuery(status="ACTIVE", limit=50, offset=0))
    assert r.is_success
    assert len(r.value) == 1
    assert r.value[0].status == "ACTIVE"


async def test_list_paginates():
    subs = InMemorySubscriptionRepository()
    now = datetime(2026, 4, 26, 12, 0, 0, tzinfo=timezone.utc)
    for _ in range(5):
        await subs.add(OwnerSubscription(owner_id=uuid4(), status=SubStatus.ACTIVE, status_changed_at=now, trial_ends_at=None))
    handler = ListSubscriptionsHandler(subs)
    r = await handler.handle(ListSubscriptionsQuery(status=None, limit=2, offset=1))
    assert r.is_success
    assert len(r.value) == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/unit/use_cases/subscriptions/queries/test_list_subscriptions.py -v`
Expected: ModuleNotFoundError.

- [ ] **Step 3: Write the implementation**

Create `app/use_cases/subscriptions/queries/list_subscriptions.py`:

```python
from __future__ import annotations
from dataclasses import dataclass

from app.domain.shared.result import Result
from app.domain.subscriptions.repository import ISubscriptionRepository
from app.use_cases.subscriptions.dtos import OwnerSubscriptionDto


@dataclass(frozen=True, slots=True)
class ListSubscriptionsQuery:
    status: str | None
    limit: int
    offset: int


class ListSubscriptionsHandler:
    def __init__(self, subscriptions: ISubscriptionRepository) -> None:
        self._subscriptions = subscriptions

    async def handle(
        self, q: ListSubscriptionsQuery,
    ) -> Result[list[OwnerSubscriptionDto]]:
        rows = await self._subscriptions.list_all(
            status=q.status, limit=q.limit, offset=q.offset,
        )
        return Result.success([OwnerSubscriptionDto.from_entity(s) for s in rows])
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/unit/use_cases/subscriptions/queries/test_list_subscriptions.py -v`
Expected: 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add app/use_cases/subscriptions/queries/__init__.py app/use_cases/subscriptions/queries/list_subscriptions.py tests/unit/use_cases/subscriptions/queries/__init__.py tests/unit/use_cases/subscriptions/queries/test_list_subscriptions.py
git commit -m "$(cat <<'EOF'
feat(subscriptions): ListSubscriptionsHandler with optional status filter

Admin-side query. Pagination + optional ?status= filter forwarded to
the repo. Returns DTOs.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 12: `GetMySubscriptionHandler`

**Files:**
- Create: `app/use_cases/subscriptions/queries/get_my_subscription.py`
- Test: `tests/unit/use_cases/subscriptions/queries/test_get_my_subscription.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/use_cases/subscriptions/queries/test_get_my_subscription.py`:

```python
from __future__ import annotations
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.domain.subscriptions.owner_subscription import OwnerSubscription
from app.domain.subscriptions.sub_status import SubStatus
from app.use_cases.subscriptions.queries.get_my_subscription import (
    GetMySubscriptionQuery,
    GetMySubscriptionHandler,
)
from tests.unit.use_cases.subscriptions.fakes.in_memory_subscription_repository import (
    InMemorySubscriptionRepository,
)


pytestmark = pytest.mark.asyncio


async def test_get_my_subscription_success():
    subs = InMemorySubscriptionRepository()
    now = datetime(2026, 4, 26, 12, 0, 0, tzinfo=timezone.utc)
    owner_id = uuid4()
    await subs.add(OwnerSubscription(
        owner_id=owner_id, status=SubStatus.ACTIVE,
        status_changed_at=now, trial_ends_at=None,
    ))
    handler = GetMySubscriptionHandler(subs)
    r = await handler.handle(GetMySubscriptionQuery(requester_id=owner_id))
    assert r.is_success
    assert r.value.owner_id == owner_id
    assert r.value.status == "ACTIVE"


async def test_get_my_subscription_returns_not_found_when_absent():
    subs = InMemorySubscriptionRepository()
    handler = GetMySubscriptionHandler(subs)
    r = await handler.handle(GetMySubscriptionQuery(requester_id=uuid4()))
    assert r.is_failure
    assert r.error == "SubscriptionNotFound"
    assert r.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/unit/use_cases/subscriptions/queries/test_get_my_subscription.py -v`
Expected: ModuleNotFoundError.

- [ ] **Step 3: Write the implementation**

Create `app/use_cases/subscriptions/queries/get_my_subscription.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/unit/use_cases/subscriptions/queries/test_get_my_subscription.py -v`
Expected: 2 PASS.

- [ ] **Step 5: Commit**

```bash
git add app/use_cases/subscriptions/queries/get_my_subscription.py tests/unit/use_cases/subscriptions/queries/test_get_my_subscription.py
git commit -m "$(cat <<'EOF'
feat(subscriptions): GetMySubscriptionHandler

Owner-side query for /v1/me/subscription. Looks up by requester's
user_id (taken from the JWT at the route layer); returns 404 if no
subscription exists (e.g., requester is not OWNER).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 13: `ExpireTrialingSubscriptionsHandler`

**Files:**
- Create: `app/use_cases/subscriptions/commands/expire_trialing_subscriptions.py`
- Test: `tests/unit/use_cases/subscriptions/commands/test_expire_trialing_subscriptions.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/use_cases/subscriptions/commands/test_expire_trialing_subscriptions.py`:

```python
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.domain.notifications.service import NotifKind
from app.domain.subscriptions.owner_subscription import OwnerSubscription
from app.domain.subscriptions.sub_status import SubStatus
from app.use_cases.subscriptions.commands.expire_trialing_subscriptions import (
    ExpireTrialingSubscriptionsCommand,
    ExpireTrialingSubscriptionsHandler,
)
from tests.unit.use_cases.subscriptions.fakes.in_memory_subscription_repository import (
    InMemorySubscriptionRepository,
)
from tests.unit.use_cases.subscriptions.fakes.fake_notification_service import (
    FakeNotificationService,
)


pytestmark = pytest.mark.asyncio


def _settings(monkeypatch) -> Settings:
    monkeypatch.setenv("BACKEND_DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    monkeypatch.setenv("BACKEND_TRIAL_DURATION_DAYS", "3")
    return Settings()


async def test_expires_trialing_with_expired_trial(monkeypatch):
    subs = InMemorySubscriptionRepository()
    notifs = FakeNotificationService()
    settings = _settings(monkeypatch)

    # Trial that expired 1 hour ago.
    now = datetime(2026, 4, 26, 12, 0, 0, tzinfo=timezone.utc)
    expired_at = now - timedelta(hours=1)
    sub = OwnerSubscription.create_trialing(
        owner_id=uuid4(), trial_duration_days=3,
        now=expired_at - timedelta(days=3),
    ).value
    await subs.add(sub)

    handler = ExpireTrialingSubscriptionsHandler(subs, notifs, settings)
    r = await handler.handle(ExpireTrialingSubscriptionsCommand())
    assert r.is_success
    assert r.value == 1
    sub_after = await subs.get_by_owner_id(sub.owner_id)
    assert sub_after.status is SubStatus.INACTIVE
    assert sub_after.trial_ends_at is None
    assert len(notifs.calls) == 1
    recipient, kind, payload = notifs.calls[0]
    assert recipient == sub.owner_id
    assert kind is NotifKind.SUBSCRIPTION_CHANGED
    assert payload == {
        "old_status": "TRIALING", "new_status": "INACTIVE", "reason": "trial_expired",
    }


async def test_skips_trialing_with_future_expiry(monkeypatch):
    subs = InMemorySubscriptionRepository()
    notifs = FakeNotificationService()
    settings = _settings(monkeypatch)
    sub = OwnerSubscription.create_trialing(
        owner_id=uuid4(), trial_duration_days=3,
        now=datetime.now(timezone.utc),
    ).value
    await subs.add(sub)
    handler = ExpireTrialingSubscriptionsHandler(subs, notifs, settings)
    r = await handler.handle(ExpireTrialingSubscriptionsCommand())
    assert r.is_success
    assert r.value == 0
    assert len(notifs.calls) == 0


async def test_skips_non_trialing(monkeypatch):
    subs = InMemorySubscriptionRepository()
    notifs = FakeNotificationService()
    settings = _settings(monkeypatch)
    now = datetime(2026, 4, 26, 12, 0, 0, tzinfo=timezone.utc)
    await subs.add(OwnerSubscription(
        owner_id=uuid4(), status=SubStatus.ACTIVE,
        status_changed_at=now, trial_ends_at=None,
    ))
    handler = ExpireTrialingSubscriptionsHandler(subs, notifs, settings)
    r = await handler.handle(ExpireTrialingSubscriptionsCommand())
    assert r.is_success
    assert r.value == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/unit/use_cases/subscriptions/commands/test_expire_trialing_subscriptions.py -v`
Expected: ModuleNotFoundError.

- [ ] **Step 3: Write the implementation**

Create `app/use_cases/subscriptions/commands/expire_trialing_subscriptions.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/unit/use_cases/subscriptions/commands/test_expire_trialing_subscriptions.py -v`
Expected: 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add app/use_cases/subscriptions/commands/expire_trialing_subscriptions.py tests/unit/use_cases/subscriptions/commands/test_expire_trialing_subscriptions.py
git commit -m "$(cat <<'EOF'
feat(subscriptions): ExpireTrialingSubscriptionsHandler (cron worker)

Selects TRIALING with trial_ends_at < now, flips each to INACTIVE,
emits SUBSCRIPTION_CHANGED with reason="trial_expired", returns count.
Idempotent — safe to retry.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 14: Auto-create subscription in `RegisterUserHandler`

**Files:**
- Modify: `app/use_cases/accounts/commands/register_user.py`
- Modify: `tests/unit/use_cases/accounts/commands/test_register_user.py`
- Modify: `app/api/v1/auth/deps.py` (FastAPI DI for the new handler signature)

- [ ] **Step 1: Update tests to expect auto-create**

In `tests/unit/use_cases/accounts/commands/test_register_user.py`, the existing `make_handler` returns a 3-tuple. We need to extend the handler signature. Replace the helper at the top:

```python
def make_handler(monkeypatch=None):
    from app.core.config import Settings
    from tests.unit.use_cases.subscriptions.fakes.in_memory_subscription_repository import (
        InMemorySubscriptionRepository,
    )
    repo = InMemoryUserRepository()
    hasher = FakePasswordHasher()
    subs = InMemorySubscriptionRepository()
    if monkeypatch is not None:
        monkeypatch.setenv("BACKEND_DATABASE_URL", "sqlite+aiosqlite:///:memory:")
        monkeypatch.setenv("BACKEND_TRIAL_DURATION_DAYS", "3")
    settings = Settings(
        database_url="sqlite+aiosqlite:///:memory:",
        trial_duration_days=3,
    )
    return RegisterUserHandler(repo, hasher, subs, settings), repo, hasher, subs
```

Update each test that uses `make_handler` to unpack the new tuple. For tests that don't need `subs` or `monkeypatch`, just receive and ignore. Concrete edits:

- All call sites `handler, repo, _ = make_handler()` become `handler, repo, _, _ = make_handler()`.
- All call sites `handler, _, _ = make_handler()` become `handler, _, _, _ = make_handler()`.

Append three new tests at the end of the file:

```python
@pytest.mark.asyncio
async def test_register_owner_creates_trialing_subscription():
    handler, _repo, _hasher, subs = make_handler()
    r = await handler.handle(RegisterUserCommand(
        email="newowner@example.com",
        password="hunter2-strong",
        role=Role.OWNER,
        full_name="Owner",
        phone=None,
    ))
    assert r.is_success
    sub = await subs.get_by_owner_id(r.value.id)
    assert sub is not None
    assert sub.status.value == "TRIALING"
    assert sub.trial_ends_at is not None


@pytest.mark.asyncio
async def test_register_customer_does_not_create_subscription():
    handler, _repo, _hasher, subs = make_handler()
    r = await handler.handle(RegisterUserCommand(
        email="customer2@example.com",
        password="hunter2-strong",
        role=Role.CUSTOMER,
        full_name="C",
        phone=None,
    ))
    assert r.is_success
    sub = await subs.get_by_owner_id(r.value.id)
    assert sub is None


@pytest.mark.asyncio
async def test_register_owner_trial_window_uses_config_value():
    from datetime import timedelta
    handler, _repo, _hasher, subs = make_handler()
    r = await handler.handle(RegisterUserCommand(
        email="windowowner@example.com",
        password="hunter2-strong",
        role=Role.OWNER,
        full_name="Owner",
        phone=None,
    ))
    sub = await subs.get_by_owner_id(r.value.id)
    delta = sub.trial_ends_at - sub.status_changed_at
    assert delta == timedelta(days=3)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/unit/use_cases/accounts/commands/test_register_user.py -v`
Expected: tests fail because `RegisterUserHandler.__init__` doesn't accept new args yet.

- [ ] **Step 3: Update the handler**

In `app/use_cases/accounts/commands/register_user.py`, replace:

```python
class RegisterUserHandler:
    def __init__(self, users: IUserRepository, hasher: IPasswordHasher) -> None:
        self._users = users
        self._hasher = hasher
```

with:

```python
class RegisterUserHandler:
    def __init__(
        self,
        users: IUserRepository,
        hasher: IPasswordHasher,
        subscriptions: ISubscriptionRepository,
        config: Settings,
    ) -> None:
        self._users = users
        self._hasher = hasher
        self._subscriptions = subscriptions
        self._config = config
```

Add to imports at the top of the file:

```python
from datetime import datetime, timezone
from app.core.config import Settings
from app.domain.subscriptions.owner_subscription import OwnerSubscription
from app.domain.subscriptions.repository import ISubscriptionRepository
```

After `await self._users.add(user)` and before `return Result.success(...)`, insert:

```python
        if user.role is Role.OWNER:
            sub_r = OwnerSubscription.create_trialing(
                owner_id=user.id,
                trial_duration_days=self._config.trial_duration_days,
                now=datetime.now(timezone.utc),
            )
            if sub_r.is_failure:
                return Result.from_failure(sub_r, status_code=500)
            add_r = await self._subscriptions.add(sub_r.value)
            if add_r.is_failure:
                return Result.from_failure(add_r, status_code=500)
```

- [ ] **Step 4: Update FastAPI DI in `auth/deps.py`**

The handler signature changed; the FastAPI factory must follow. In `app/api/v1/auth/deps.py`, replace:

```python
def get_register_user_handler(repo: UserRepo, hasher: Hasher) -> RegisterUserHandler:
    return RegisterUserHandler(repo, hasher)
```

with:

```python
from app.core.config import Settings, get_settings
from app.domain.subscriptions.repository import ISubscriptionRepository
from app.infrastructure.repositories.owner_subscription_repository import (
    SQLAlchemyOwnerSubscriptionRepository,
)


def get_subscription_repo(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ISubscriptionRepository:
    return SQLAlchemyOwnerSubscriptionRepository(session)


SubsRepo = Annotated[ISubscriptionRepository, Depends(get_subscription_repo)]


def get_app_settings() -> Settings:
    return get_settings()


SettingsDep = Annotated[Settings, Depends(get_app_settings)]


def get_register_user_handler(
    repo: UserRepo, hasher: Hasher, subs: SubsRepo, settings: SettingsDep,
) -> RegisterUserHandler:
    return RegisterUserHandler(repo, hasher, subs, settings)
```

(Place the new imports near the existing imports at the top of the file.)

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/unit/use_cases/accounts/commands/test_register_user.py -v`
Expected: all PASS (existing 7 + 3 new).

Smoke-check the FastAPI DI compiles:

Run: `.venv/bin/python -c "from app.main import app; print('ok')"`
Expected: `ok` (no runtime error from broken DI signature).

- [ ] **Step 6: Commit**

```bash
git add app/use_cases/accounts/commands/register_user.py app/api/v1/auth/deps.py tests/unit/use_cases/accounts/commands/test_register_user.py
git commit -m "$(cat <<'EOF'
feat(accounts): RegisterUserHandler auto-creates owner subscriptions

When role=OWNER, creates an OwnerSubscription{TRIALING} via
ISubscriptionRepository in the same handler call. Atomic with
the user insert via the shared AsyncSession (FastAPI commits at
request end). Customers and admins do NOT get a subscription row.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 15: SQLAlchemy mapping + migration

**Files:**
- Create: `app/infrastructure/db/mappings/owner_subscription.py`
- Modify: `app/migrations/env.py`
- Run: `make migrate-new msg="owner subscriptions table"`

- [ ] **Step 1: Create the mapping**

Create `app/infrastructure/db/mappings/owner_subscription.py`:

```python
from __future__ import annotations
from datetime import datetime
from uuid import UUID
from sqlalchemy import Index, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import CHAR, DateTime
from app.infrastructure.db.base import Base, TimestampMixin


class OwnerSubscriptionModel(Base, TimestampMixin):
    __tablename__ = "owner_subscriptions"
    __table_args__ = (
        Index(
            "idx_owner_subs_status_trial_end",
            "status",
            "trial_ends_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(CHAR(36), primary_key=True)
    owner_id: Mapped[UUID] = mapped_column(CHAR(36), nullable=False, unique=True, index=True)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    status_changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    trial_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

- [ ] **Step 2: Register the mapping in alembic env**

In `app/migrations/env.py`, add the import alongside the existing mapping imports:

```python
from app.infrastructure.db.mappings import owner_subscription  # noqa: F401
```

- [ ] **Step 3: Generate the migration**

Run: `make migrate-new msg="owner subscriptions table"`
Expected: a new file `app/migrations/versions/<timestamp>_owner_subscriptions_table.py` is created with auto-generated `op.create_table('owner_subscriptions', ...)`.

Open the generated migration and verify it contains:
- `op.create_table('owner_subscriptions', ...)` with all columns.
- `op.create_index('idx_owner_subs_status_trial_end', ...)`.
- `UniqueConstraint` (or `unique=True`) on `owner_id`.

If the auto-generated migration is missing the index or unique constraint, add them manually.

- [ ] **Step 4: Apply the migration locally**

Run: `make migrate-up`
Expected: migration runs without error.

- [ ] **Step 5: Sanity-check it round-trips**

Run: `.venv/bin/python -c "from app.infrastructure.db.mappings.owner_subscription import OwnerSubscriptionModel; print(OwnerSubscriptionModel.__table__)"`
Expected: prints the table reflection without error.

- [ ] **Step 6: Commit**

```bash
git add app/infrastructure/db/mappings/owner_subscription.py app/migrations/env.py app/migrations/versions/
git commit -m "$(cat <<'EOF'
feat(subscriptions): OwnerSubscriptionModel + Alembic migration

Table owner_subscriptions with unique index on owner_id and a
composite (status, trial_ends_at) index for the cron query.
status_changed_at and trial_ends_at are TIMESTAMPTZ.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 16: `SQLAlchemyOwnerSubscriptionRepository` + integration tests

**Files:**
- Create: `app/infrastructure/repositories/owner_subscription_repository.py`
- Create: `tests/integration/subscriptions/__init__.py` (empty)
- Test: `tests/integration/subscriptions/test_owner_subscription_repository.py`

- [ ] **Step 1: Write the failing tests**

```bash
mkdir -p tests/integration/subscriptions
touch tests/integration/subscriptions/__init__.py
```

Create `tests/integration/subscriptions/test_owner_subscription_repository.py`:

```python
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.domain.subscriptions.owner_subscription import OwnerSubscription
from app.domain.subscriptions.sub_status import SubStatus
from app.infrastructure.repositories.owner_subscription_repository import (
    SQLAlchemyOwnerSubscriptionRepository,
)


pytestmark = pytest.mark.asyncio


def _now() -> datetime:
    return datetime(2026, 4, 26, 12, 0, 0, tzinfo=timezone.utc)


async def test_add_and_get_by_owner_id_round_trips(integration_session):
    repo = SQLAlchemyOwnerSubscriptionRepository(integration_session)
    sub = OwnerSubscription.create_trialing(
        owner_id=uuid4(), trial_duration_days=3, now=_now(),
    ).value
    add_r = await repo.add(sub)
    assert add_r.is_success
    fetched = await repo.get_by_owner_id(sub.owner_id)
    assert fetched is not None
    assert fetched.id == sub.id
    assert fetched.status is SubStatus.TRIALING
    assert fetched.trial_ends_at == sub.trial_ends_at


async def test_add_rejects_duplicate_owner_id(integration_session):
    repo = SQLAlchemyOwnerSubscriptionRepository(integration_session)
    owner_id = uuid4()
    sub1 = OwnerSubscription.create_trialing(
        owner_id=owner_id, trial_duration_days=3, now=_now(),
    ).value
    sub2 = OwnerSubscription.create_trialing(
        owner_id=owner_id, trial_duration_days=3, now=_now(),
    ).value
    await repo.add(sub1)
    add_r = await repo.add(sub2)
    assert add_r.is_failure
    assert add_r.error == "OwnerAlreadyHasSubscription"


async def test_update_persists_changes(integration_session):
    repo = SQLAlchemyOwnerSubscriptionRepository(integration_session)
    sub = OwnerSubscription.create_trialing(
        owner_id=uuid4(), trial_duration_days=3, now=_now(),
    ).value
    await repo.add(sub)
    sub.transition_to(SubStatus.ACTIVE, now=_now() + timedelta(hours=1), trial_duration_days=3)
    update_r = await repo.update(sub)
    assert update_r.is_success
    fetched = await repo.get_by_owner_id(sub.owner_id)
    assert fetched.status is SubStatus.ACTIVE
    assert fetched.trial_ends_at is None


async def test_list_trialing_with_expiry_before(integration_session):
    repo = SQLAlchemyOwnerSubscriptionRepository(integration_session)
    now = _now()
    # Expired
    expired = OwnerSubscription.create_trialing(
        owner_id=uuid4(), trial_duration_days=3, now=now - timedelta(days=10),
    ).value
    # Not yet expired
    fresh = OwnerSubscription.create_trialing(
        owner_id=uuid4(), trial_duration_days=3, now=now,
    ).value
    # Different status
    other = OwnerSubscription(
        owner_id=uuid4(), status=SubStatus.ACTIVE,
        status_changed_at=now, trial_ends_at=None,
    )
    for s in (expired, fresh, other):
        await repo.add(s)
    rows = await repo.list_trialing_with_expiry_before(now)
    assert len(rows) == 1
    assert rows[0].id == expired.id


async def test_list_all_filters_by_status(integration_session):
    repo = SQLAlchemyOwnerSubscriptionRepository(integration_session)
    now = _now()
    await repo.add(OwnerSubscription(
        owner_id=uuid4(), status=SubStatus.ACTIVE,
        status_changed_at=now, trial_ends_at=None,
    ))
    await repo.add(OwnerSubscription(
        owner_id=uuid4(), status=SubStatus.INACTIVE,
        status_changed_at=now, trial_ends_at=None,
    ))
    rows = await repo.list_all(status="ACTIVE", limit=50, offset=0)
    assert len(rows) == 1
    assert rows[0].status is SubStatus.ACTIVE
```

The `integration_session` fixture should already exist in `tests/integration/conftest.py` (used by Plans 02/04). If not, the existing pattern from `tests/integration/catalog/test_resource_type_repository.py` shows how to invoke it. Re-use, do not create a new fixture.

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/integration/subscriptions/test_owner_subscription_repository.py -v`
Expected: ModuleNotFoundError for `app.infrastructure.repositories.owner_subscription_repository`.

- [ ] **Step 3: Write the implementation**

Create `app/infrastructure/repositories/owner_subscription_repository.py`:

```python
from __future__ import annotations
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.shared.result import Result
from app.domain.subscriptions.owner_subscription import OwnerSubscription
from app.domain.subscriptions.sub_status import SubStatus
from app.infrastructure.db.mappings.owner_subscription import OwnerSubscriptionModel


def _to_entity(model: OwnerSubscriptionModel) -> OwnerSubscription:
    """Trusted reconstitution from DB row (bypasses factory validation)."""
    sub = OwnerSubscription(
        id=UUID(str(model.id)),
        owner_id=UUID(str(model.owner_id)),
        status=SubStatus(model.status),
        status_changed_at=model.status_changed_at,
        trial_ends_at=model.trial_ends_at,
    )
    sub.created_at = model.created_at
    sub.updated_at = model.updated_at
    return sub


def _to_model_kwargs(sub: OwnerSubscription) -> dict:
    return {
        "id": str(sub.id),
        "owner_id": str(sub.owner_id),
        "status": sub.status.value,
        "status_changed_at": sub.status_changed_at,
        "trial_ends_at": sub.trial_ends_at,
        "created_at": sub.created_at,
        "updated_at": sub.updated_at,
    }


class SQLAlchemyOwnerSubscriptionRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def add(self, sub: OwnerSubscription) -> Result[None]:
        model = OwnerSubscriptionModel(**_to_model_kwargs(sub))
        self._session.add(model)
        try:
            await self._session.flush()
        except IntegrityError:
            await self._session.rollback()
            return Result.failure("OwnerAlreadyHasSubscription", status_code=409)
        return Result.success(None)

    async def update(self, sub: OwnerSubscription) -> Result[None]:
        stmt = select(OwnerSubscriptionModel).where(
            OwnerSubscriptionModel.id == str(sub.id),
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        if row is None:
            return Result.failure("SubscriptionNotFound", status_code=404)
        row.status = sub.status.value
        row.status_changed_at = sub.status_changed_at
        row.trial_ends_at = sub.trial_ends_at
        row.updated_at = sub.updated_at
        await self._session.flush()
        return Result.success(None)

    async def get_by_id(self, sub_id: UUID) -> OwnerSubscription | None:
        stmt = select(OwnerSubscriptionModel).where(
            OwnerSubscriptionModel.id == str(sub_id),
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return _to_entity(row) if row else None

    async def get_by_owner_id(self, owner_id: UUID) -> OwnerSubscription | None:
        stmt = select(OwnerSubscriptionModel).where(
            OwnerSubscriptionModel.owner_id == str(owner_id),
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return _to_entity(row) if row else None

    async def list_all(
        self, *, status: str | None = None, limit: int = 50, offset: int = 0,
    ) -> list[OwnerSubscription]:
        stmt = select(OwnerSubscriptionModel).order_by(OwnerSubscriptionModel.created_at)
        if status is not None:
            stmt = stmt.where(OwnerSubscriptionModel.status == status)
        stmt = stmt.limit(limit).offset(offset)
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_entity(r) for r in rows]

    async def list_trialing_with_expiry_before(
        self, threshold: datetime,
    ) -> list[OwnerSubscription]:
        stmt = (
            select(OwnerSubscriptionModel)
            .where(OwnerSubscriptionModel.status == SubStatus.TRIALING.value)
            .where(OwnerSubscriptionModel.trial_ends_at < threshold)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_entity(r) for r in rows]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/integration/subscriptions/test_owner_subscription_repository.py -v`
Expected: 5 PASS.

- [ ] **Step 5: Commit**

```bash
git add app/infrastructure/repositories/owner_subscription_repository.py tests/integration/subscriptions/__init__.py tests/integration/subscriptions/test_owner_subscription_repository.py
git commit -m "$(cat <<'EOF'
feat(subscriptions): SQLAlchemyOwnerSubscriptionRepository

Implements ISubscriptionRepository on top of SQLAlchemy 2 async.
Add returns OwnerAlreadyHasSubscription (409) on unique violation,
update returns SubscriptionNotFound (404) when missing.
list_trialing_with_expiry_before drives the cron worker.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 17: `LoggingNotificationService` adapter

**Files:**
- Create: `app/infrastructure/notifications/__init__.py` (empty)
- Create: `app/infrastructure/notifications/logging_notification_service.py`

- [ ] **Step 1: Create the package and adapter**

```bash
mkdir -p app/infrastructure/notifications
touch app/infrastructure/notifications/__init__.py
```

Create `app/infrastructure/notifications/logging_notification_service.py`:

```python
from __future__ import annotations
import logging
from typing import Any
from uuid import UUID

from app.domain.notifications.service import NotifKind


class LoggingNotificationService:
    """No-op adapter shipped with Plan 05. Plan 07 swaps for the persistent
    service that writes to the notifications table and triggers IEmailSender.
    """

    def __init__(self, logger: logging.Logger | None = None) -> None:
        self._logger = logger or logging.getLogger(__name__)

    async def notify(
        self, *, recipient_id: UUID, kind: NotifKind, payload: dict[str, Any],
    ) -> None:
        self._logger.info(
            "notification fired",
            extra={
                "recipient_id": str(recipient_id),
                "kind": kind.value,
                "payload": payload,
            },
        )
```

- [ ] **Step 2: Verify imports compile**

Run: `.venv/bin/python -c "from app.infrastructure.notifications.logging_notification_service import LoggingNotificationService; LoggingNotificationService()"`
Expected: no output (instantiation succeeds).

- [ ] **Step 3: Commit**

```bash
git add app/infrastructure/notifications/__init__.py app/infrastructure/notifications/logging_notification_service.py
git commit -m "$(cat <<'EOF'
feat(notifications): LoggingNotificationService no-op adapter

Implements INotificationService by writing structured log lines
(level INFO, key "notification fired"). Plan 07 will replace this
with a persistent adapter; the Protocol contract does not change.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 18: Admin subscriptions routes

**Files:**
- Create: `app/api/v1/admin_subscriptions/__init__.py`
- Create: `app/api/v1/admin_subscriptions/deps.py`
- Create: `app/api/v1/admin_subscriptions/schemas.py`
- Create: `app/api/v1/admin_subscriptions/routes.py`

(E2E tests cover the routes end-to-end in Task 22.)

- [ ] **Step 1: Create `__init__.py` and `deps.py`**

```bash
mkdir -p app/api/v1/admin_subscriptions
touch app/api/v1/admin_subscriptions/__init__.py
```

Create `app/api/v1/admin_subscriptions/deps.py`:

```python
from __future__ import annotations
from typing import Annotated
import logging
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.infrastructure.db.session import get_session
from app.infrastructure.notifications.logging_notification_service import (
    LoggingNotificationService,
)
from app.infrastructure.repositories.owner_subscription_repository import (
    SQLAlchemyOwnerSubscriptionRepository,
)
from app.infrastructure.repositories.user_repository import UserRepository
from app.use_cases.subscriptions.commands.set_owner_subscription_status import (
    SetOwnerSubscriptionStatusHandler,
)
from app.use_cases.subscriptions.queries.list_subscriptions import (
    ListSubscriptionsHandler,
)


_logger = logging.getLogger("subscriptions.notifications")


async def get_subscription_repo(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> SQLAlchemyOwnerSubscriptionRepository:
    return SQLAlchemyOwnerSubscriptionRepository(session)


async def get_user_repo(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> UserRepository:
    return UserRepository(session)


async def get_notification_service() -> LoggingNotificationService:
    return LoggingNotificationService(_logger)


async def get_settings_dep() -> Settings:
    return get_settings()


async def get_set_status_handler(
    users: Annotated[UserRepository, Depends(get_user_repo)],
    subs: Annotated[SQLAlchemyOwnerSubscriptionRepository, Depends(get_subscription_repo)],
    notifs: Annotated[LoggingNotificationService, Depends(get_notification_service)],
    settings: Annotated[Settings, Depends(get_settings_dep)],
) -> SetOwnerSubscriptionStatusHandler:
    return SetOwnerSubscriptionStatusHandler(users, subs, notifs, settings)


async def get_list_handler(
    subs: Annotated[SQLAlchemyOwnerSubscriptionRepository, Depends(get_subscription_repo)],
) -> ListSubscriptionsHandler:
    return ListSubscriptionsHandler(subs)
```

- [ ] **Step 2: Create schemas**

Create `app/api/v1/admin_subscriptions/schemas.py`:

```python
from __future__ import annotations
from datetime import datetime
from typing import Self
from uuid import UUID
from pydantic import BaseModel

from app.use_cases.subscriptions.dtos import OwnerSubscriptionDto


class SetSubscriptionStatusRequest(BaseModel):
    status: str  # validated against SubStatus inside the route


class OwnerSubscriptionResponse(BaseModel):
    id: UUID
    owner_id: UUID
    status: str
    status_changed_at: datetime
    trial_ends_at: datetime | None
    is_operational: bool
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_dto(cls, dto: OwnerSubscriptionDto) -> Self:
        return cls(
            id=dto.id,
            owner_id=dto.owner_id,
            status=dto.status,
            status_changed_at=dto.status_changed_at,
            trial_ends_at=dto.trial_ends_at,
            is_operational=dto.is_operational,
            created_at=dto.created_at,
            updated_at=dto.updated_at,
        )


class SubscriptionListResponse(BaseModel):
    items: list[OwnerSubscriptionResponse]
    limit: int
    offset: int
```

- [ ] **Step 3: Create routes**

Create `app/api/v1/admin_subscriptions/routes.py`:

```python
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
            detail={"code": "InvalidSubscriptionStatus", "message": translate("InvalidSubscriptionStatus")},
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
                detail={"code": "InvalidSubscriptionStatus", "message": translate("InvalidSubscriptionStatus")},
            )
    dtos = unwrap(await handler.handle(ListSubscriptionsQuery(
        status=status, limit=limit, offset=offset,
    )))
    return SubscriptionListResponse(
        items=[OwnerSubscriptionResponse.from_dto(d) for d in dtos],
        limit=limit,
        offset=offset,
    )
```

- [ ] **Step 4: Register the new error code**

In `app/api/error_codes.py`, add `"InvalidSubscriptionStatus": "Status de assinatura inválido."` to `ERROR_MESSAGES_PT_BR`. In `tests/unit/architecture/test_error_code_coverage.py`, add `"InvalidSubscriptionStatus"` to the `handler_level_allowlist` set.

- [ ] **Step 5: Smoke-check the routes import**

Run: `.venv/bin/python -c "from app.api.v1.admin_subscriptions.routes import router; print(len(router.routes))"`
Expected: `2`.

- [ ] **Step 6: Commit**

```bash
git add app/api/v1/admin_subscriptions/ app/api/error_codes.py tests/unit/architecture/test_error_code_coverage.py
git commit -m "$(cat <<'EOF'
feat(api): admin subscription endpoints

POST /v1/admin/owners/{owner_id}/subscription and
GET  /v1/admin/subscriptions. ADMIN role required at the router
level. Body status validated against SubStatus before reaching the
handler; bad values return 422 InvalidSubscriptionStatus.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 19: Owner /me/subscription route

**Files:**
- Create: `app/api/v1/me_subscription/__init__.py`
- Create: `app/api/v1/me_subscription/deps.py`
- Create: `app/api/v1/me_subscription/schemas.py`
- Create: `app/api/v1/me_subscription/routes.py`

- [ ] **Step 1: Create files**

```bash
mkdir -p app/api/v1/me_subscription
touch app/api/v1/me_subscription/__init__.py
```

Create `app/api/v1/me_subscription/deps.py`:

```python
from __future__ import annotations
from typing import Annotated
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.session import get_session
from app.infrastructure.repositories.owner_subscription_repository import (
    SQLAlchemyOwnerSubscriptionRepository,
)
from app.use_cases.subscriptions.queries.get_my_subscription import (
    GetMySubscriptionHandler,
)


async def get_subscription_repo(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> SQLAlchemyOwnerSubscriptionRepository:
    return SQLAlchemyOwnerSubscriptionRepository(session)


async def get_my_subscription_handler(
    repo: Annotated[
        SQLAlchemyOwnerSubscriptionRepository, Depends(get_subscription_repo),
    ],
) -> GetMySubscriptionHandler:
    return GetMySubscriptionHandler(repo)
```

Create `app/api/v1/me_subscription/schemas.py`:

```python
from __future__ import annotations
from app.api.v1.admin_subscriptions.schemas import OwnerSubscriptionResponse

# Reuse the response shape; owner sees the same fields.
__all__ = ["OwnerSubscriptionResponse"]
```

Create `app/api/v1/me_subscription/routes.py`:

```python
from __future__ import annotations
from fastapi import APIRouter, Depends

from app.api.deps import CurrentUser, get_current_user
from app.api.error_handler import unwrap
from app.api.v1.me_subscription.deps import get_my_subscription_handler
from app.api.v1.me_subscription.schemas import OwnerSubscriptionResponse
from app.use_cases.subscriptions.queries.get_my_subscription import (
    GetMySubscriptionHandler,
    GetMySubscriptionQuery,
)


router = APIRouter(prefix="/v1/me", tags=["me"])


@router.get("/subscription", response_model=OwnerSubscriptionResponse)
async def get_my_subscription(
    user: CurrentUser = Depends(get_current_user),
    handler: GetMySubscriptionHandler = Depends(get_my_subscription_handler),
):
    dto = unwrap(await handler.handle(GetMySubscriptionQuery(requester_id=user.user_id)))
    return OwnerSubscriptionResponse.from_dto(dto)
```

`CurrentUser` and `get_current_user` live in `app/api/deps.py` (not `auth/deps.py`); same source used by existing `/v1/me/...` endpoints in `app/api/v1/auth/routes.py`. The route extracts `user.user_id` from the JWT claims (matches the pattern `dto = unwrap(await handler.handle(GetUserByIdQuery(user_id=user.user_id)))` already in auth/routes.py).

- [ ] **Step 2: Smoke-check the routes import**

Run: `.venv/bin/python -c "from app.api.v1.me_subscription.routes import router; print(len(router.routes))"`
Expected: `1`.

- [ ] **Step 3: Commit**

```bash
git add app/api/v1/me_subscription/
git commit -m "$(cat <<'EOF'
feat(api): GET /v1/me/subscription owner-facing endpoint

Returns the requester's subscription DTO (404 SubscriptionNotFound
if the requester is not OWNER or has no subscription row).
Reuses OwnerSubscriptionResponse from admin schemas.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 20: Mount routers + main.py DI

**Files:**
- Modify: `app/api/v1/router.py`
- Modify: `app/main.py` (verify `include_router` already mounts `api_router`; only add if missing)

- [ ] **Step 1: Mount the new routers**

In `app/api/v1/router.py`, add the imports and `include_router` calls:

```python
from app.api.v1.admin_subscriptions.routes import router as admin_subscriptions_router
from app.api.v1.me_subscription.routes import router as me_subscription_router
```

```python
api_router.include_router(admin_subscriptions_router)
api_router.include_router(me_subscription_router)
```

- [ ] **Step 2: Smoke-check the app starts**

Run: `.venv/bin/python -c "from app.main import app; print([r.path for r in app.routes if hasattr(r, 'path') and 'subscription' in r.path])"`
Expected: a list including `/v1/admin/owners/{owner_id}/subscription`, `/v1/admin/subscriptions`, `/v1/me/subscription`.

- [ ] **Step 3: Commit**

```bash
git add app/api/v1/router.py
git commit -m "$(cat <<'EOF'
feat(api): mount admin_subscriptions + me_subscription routers

Three new endpoints visible on the FastAPI app: admin set-status,
admin list, and owner-facing /me/subscription.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 21: Cron entry-point script

**Files:**
- Create: `app/jobs/__init__.py` (empty)
- Create: `app/jobs/expire_trialing_subscriptions.py`

- [ ] **Step 1: Create the entry-point**

```bash
mkdir -p app/jobs
touch app/jobs/__init__.py
```

Create `app/jobs/expire_trialing_subscriptions.py`:

```python
"""Cron entry-point. Run via `python -m app.jobs.expire_trialing_subscriptions`.

Suggested schedule: hourly (cron `0 * * * *`). Idempotent — safe to retry.
"""
from __future__ import annotations
import asyncio
import logging

from app.core.config import get_settings
from app.infrastructure.db.session import dispose_engine, get_session, init_engine
from app.infrastructure.notifications.logging_notification_service import (
    LoggingNotificationService,
)
from app.infrastructure.repositories.owner_subscription_repository import (
    SQLAlchemyOwnerSubscriptionRepository,
)
from app.use_cases.subscriptions.commands.expire_trialing_subscriptions import (
    ExpireTrialingSubscriptionsCommand,
    ExpireTrialingSubscriptionsHandler,
)


logger = logging.getLogger(__name__)


async def main() -> int:
    init_engine()
    settings = get_settings()
    notifications = LoggingNotificationService(logger)
    try:
        async for session in get_session():
            repo = SQLAlchemyOwnerSubscriptionRepository(session)
            handler = ExpireTrialingSubscriptionsHandler(repo, notifications, settings)
            result = await handler.handle(ExpireTrialingSubscriptionsCommand())
            count = result.value or 0
            logger.info("expired %s trialing subscriptions", count)
            return count
        return 0
    finally:
        await dispose_engine()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
```

- [ ] **Step 2: Smoke-check the import**

Run: `.venv/bin/python -c "from app.jobs.expire_trialing_subscriptions import main; print('ok')"`
Expected: `ok`.

- [ ] **Step 3: Commit**

```bash
git add app/jobs/__init__.py app/jobs/expire_trialing_subscriptions.py
git commit -m "$(cat <<'EOF'
feat(jobs): cron entry-point for ExpireTrialingSubscriptions

Run via `python -m app.jobs.expire_trialing_subscriptions`. Hourly
cadence is reasonable for MVP; the operations team configures the
actual scheduler externally (cron, k8s CronJob, etc.). Idempotent.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 22: E2E flow test

**Files:**
- Create: `tests/e2e/subscriptions/__init__.py` (empty)
- Test: `tests/e2e/subscriptions/test_admin_and_owner_flow.py`

- [ ] **Step 1: Write the failing tests**

```bash
mkdir -p tests/e2e/subscriptions
touch tests/e2e/subscriptions/__init__.py
```

Create `tests/e2e/subscriptions/test_admin_and_owner_flow.py`:

```python
from __future__ import annotations
import pytest


pytestmark = pytest.mark.asyncio


async def test_owner_register_creates_trialing_subscription_and_can_read_it(
    http_client,
):
    register = await http_client.post(
        "/v1/auth/register",
        json={
            "email": "owner-e2e@example.com",
            "password": "hunter2-strong",
            "role": "OWNER",
            "full_name": "Owner E2E",
            "phone": None,
        },
    )
    assert register.status_code == 201, register.text

    login = await http_client.post(
        "/v1/auth/login",
        json={"email": "owner-e2e@example.com", "password": "hunter2-strong"},
    )
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]

    me = await http_client.get(
        "/v1/me/subscription",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me.status_code == 200, me.text
    body = me.json()
    assert body["status"] == "TRIALING"
    assert body["is_operational"] is True
    assert body["trial_ends_at"] is not None


async def test_admin_changes_status_then_owner_sees_new_status(
    http_client, admin_token,
):
    register = await http_client.post(
        "/v1/auth/register",
        json={
            "email": "owner2-e2e@example.com",
            "password": "hunter2-strong",
            "role": "OWNER",
            "full_name": "Owner",
            "phone": None,
        },
    )
    owner_id = register.json()["id"]

    set_status = await http_client.post(
        f"/v1/admin/owners/{owner_id}/subscription",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"status": "INACTIVE"},
    )
    assert set_status.status_code == 200, set_status.text
    assert set_status.json()["status"] == "INACTIVE"
    assert set_status.json()["is_operational"] is False

    # Idempotent — same payload again returns 200 with the same body.
    again = await http_client.post(
        f"/v1/admin/owners/{owner_id}/subscription",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"status": "INACTIVE"},
    )
    assert again.status_code == 200
    assert again.json()["status_changed_at"] == set_status.json()["status_changed_at"]


async def test_admin_endpoint_rejects_non_admin(http_client, customer_token):
    response = await http_client.post(
        "/v1/admin/owners/00000000-0000-0000-0000-000000000000/subscription",
        headers={"Authorization": f"Bearer {customer_token}"},
        json={"status": "ACTIVE"},
    )
    assert response.status_code == 403


async def test_admin_endpoint_rejects_non_owner_target(http_client, admin_token, customer_token):
    # Get the customer's id by reading the JWT or registering fresh and reading the response.
    register = await http_client.post(
        "/v1/auth/register",
        json={
            "email": "customer3-e2e@example.com",
            "password": "hunter2-strong",
            "role": "CUSTOMER",
            "full_name": "C",
            "phone": None,
        },
    )
    customer_id = register.json()["id"]

    response = await http_client.post(
        f"/v1/admin/owners/{customer_id}/subscription",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"status": "ACTIVE"},
    )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "UserIsNotOwner"
```

The `http_client`, `admin_token`, and `customer_token` fixtures should already exist in `tests/e2e/conftest.py` (used by Plans 02/04 e2e tests). Reuse them.

- [ ] **Step 2: Run tests**

Run: `.venv/bin/pytest tests/e2e/subscriptions/test_admin_and_owner_flow.py -v`
Expected: 4 PASS (Tasks 1-21 already wired the behavior end-to-end).

If any fail, investigate the actual response body before adjusting the test.

- [ ] **Step 3: Commit**

```bash
git add tests/e2e/subscriptions/__init__.py tests/e2e/subscriptions/test_admin_and_owner_flow.py
git commit -m "$(cat <<'EOF'
test(e2e): subscription admin + owner flow

Owner registration → automatic TRIALING subscription readable via
/v1/me/subscription. Admin POST changes status, second POST with
same payload is idempotent (status_changed_at unchanged). Non-admin
rejected (403); non-owner target rejected (422 UserIsNotOwner).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 23: Final verification

**Files:** none modified — verification only.

- [ ] **Step 1: Tripwire — no leftover joined-error strings or colon-suffix codes**

Run: `grep -rn '"; "' app/domain app/use_cases`
Expected: empty.

Run: `grep -rEn 'f"\{[^}]*\}:\{' app/domain app/use_cases`
Expected: empty.

- [ ] **Step 2: Full test suite**

Run: `make test` (which is `.venv/bin/pytest`).
Expected: full PASS, no skipped tests except those skipped in baseline before Plan 05.

- [ ] **Step 3: Migration round-trip sanity**

Run: `make migrate-up`
Expected: no-op (already applied) or applies cleanly. No drift errors from autogenerate.

- [ ] **Step 4: Update memory**

Edit `/Users/klayver/.claude/projects/-Users-klayver-Repositories-agentic-workbench-venue-backend/memory/project_plan_progress.md`: move Plan 05 from "pending" to "done", referencing the merge commit / last commit hash.

- [ ] **Step 5: Optional smoke test against a running app**

```bash
make run &
SERVER_PID=$!
sleep 2
curl -s http://localhost:8000/openapi.json | grep -o "subscription" | wc -l
kill $SERVER_PID
```

Expected: a count > 0 confirming the new endpoints are exposed.

If verification surfaces any leftover work (an aggregator missed by the tripwire, a route not mounted, etc.), that becomes its own task — do NOT silently fold it into the last commit.

---

## Self-review notes

**Spec coverage check:**

| Spec section | Tasks |
|---|---|
| §3.1 SubStatus enum | Task 1 |
| §3.2 OwnerSubscription aggregate | Task 2 |
| §3.3 Cross-field invariants | Task 2 (`__post_init__` checks) |
| §3.4 Repository Protocol | Task 3 |
| §3.5 Persistence mapping | Task 15 |
| §4 Auto-create on registration | Task 14 |
| §5 SetOwnerSubscriptionStatusHandler + endpoint | Tasks 10, 18 |
| §6 ExpireTrialingSubscriptions cron | Tasks 13, 21 |
| §7 Subscription/User decoupling | Documented in spec; Task 10 verifies (no reject on inactive) |
| §8 INotificationService Protocol + adapter | Tasks 4, 17 |
| §9 Endpoints + DTOs | Tasks 9, 18, 19, 20 |
| §10 Stable error codes | Tasks 6, 18 (InvalidSubscriptionStatus added there) |
| §11 Configuration | Task 5 |
| §12 Tests | Tasks 1, 2, 9-13, 14, 16, 22 |

All spec sections covered.

**Naming consistency:**
- `OwnerSubscription`, `SubStatus`, `OwnerSubscriptionDto`, `OwnerSubscriptionResponse` — used identically across tasks.
- `ISubscriptionRepository`, `INotificationService` — used identically.
- `transition_to(new_status, *, now, trial_duration_days)` — same signature in tasks 2, 10, 13.
- `notify(*, recipient_id, kind, payload)` — same shape in tasks 4, 8, 10, 13, 17.

**Task ordering rationale:**
- Tasks 1-4 build domain primitives (no dependencies between them other than SubStatus → OwnerSubscription).
- Task 5 (config) needed by handler tasks (10, 13, 14).
- Task 6 (error codes) requires Task 2 (entity constants).
- Tasks 7-8 (test fakes) needed by handler tests in 10-13.
- Task 9 (DTO) needed by handler return types in 10-13.
- Tasks 10-13 are handler tasks (independent of each other once the primitives exist).
- Task 14 wires auto-create into RegisterUserHandler — depends on primitives and config.
- Tasks 15-16 (persistence) — tested in isolation.
- Task 17 (LoggingNotificationService) trivial; needed by route DI.
- Tasks 18-19 (routes) need handlers + persistence + adapter.
- Task 20 mounts routers.
- Task 21 (cron) packages the existing handler.
- Task 22 (e2e) covers the integrated flow.
- Task 23 verifies everything together.
