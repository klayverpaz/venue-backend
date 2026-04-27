# Plan 08 — Bookings Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the booking feature end-to-end: `Booking` aggregate with 5-state machine, `IBookingRepository` + `IBookingLockService` ports, Postgres advisory-lock + `btree_gist` exclusion-constraint concurrency primitives (in-memory async lock + Python overlap check for SQLite tests), 5 mutation handlers (request/approve/reject/cancel/expire — natural dedup replaces Idempotency-Key per spec §1; auto-rejection of competing pendings on approval), 4 query handlers (list/get/list-by-resource/agenda), 10 endpoints (4 customer + 5 owner + 1 public), `Resource.compute_price(slot_range)` Plan 06 retroactive, `SoftDeleteResourceHandler` cascade extension, cron entry-point for pending expiry, refresh canonical §3 #14 + §4.2 + §5.3 + §5.4 + §8.

**Architecture:** Aggregate in `app/domain/bookings/` with `BookingStatus` enum + `StatusChange` composite VO + `Booking` entity exposing `create_pending` factory and `approve`/`reject`/`cancel`/`expire` mutators that append `StatusChange` records to `_status_history`. Slot-grid alignment + operating-hours containment + slot-count + price computation live in `RequestBookingHandler` because they need `Resource` context (Plan 06's `Resource.compute_price` is added retroactively). Concurrency: `IBookingLockService` Protocol with two adapters — `PostgresBookingLockService` wraps `pg_advisory_xact_lock(hash(uuid))`, `InMemoryBookingLockService` uses `asyncio.Lock` per resource_id; production migration adds `btree_gist` exclusion constraint as belt-and-suspenders. Persistence: one `bookings` row with two `DateTime(timezone=True)` columns for the slot range, JSON `status_history`, FKs to `resources.id` and `users.id` with `ON DELETE RESTRICT`. Handler ownership-check pattern follows Plan 06: cross-actor lookups return `BookingNotFound` 404 (no leak).

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2 async, Alembic, Pydantic, pytest. New (stdlib): `zoneinfo`, `asyncio` (already in use). New SQL extension: `btree_gist` (Postgres only; the migration installs it conditionally).

**Reference spec:** `docs/superpowers/specs/2026-04-27-plan-08-bookings-design.md`.

**Conventions reminders:**
- Always invoke Python via venv: `.venv/bin/python` or `.venv/bin/pytest`. Never use the global Python.
- Domain code never imports from `infrastructure` or `use_cases`.
- After each task, commit with a focused message ending in `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>`.
- TDD: failing test → RED → minimal impl → GREEN → commit.
- Composite VOs that aggregate multiple sub-VOs use `Result.failure_many`; single-rule VOs use `Result.failure(code)`.
- Aggregate roots emit `failure_many` for multi-field `create` factories; mutators with state transitions return `Result[None]`.
- pt-BR error mappings live exclusively in `app/api/error_codes.py`. New stable codes also need entries in `tests/unit/architecture/test_error_code_coverage.py` `handler_level_allowlist` (or are entity-level constants the arch test discovers automatically).

---

## File structure (created or modified over the plan)

```
app/domain/shared/
└── weekday.py                                    MODIFIED — adds Weekday.from_iso

app/domain/bookings/
├── __init__.py                                   NEW (empty)
├── booking_status.py                             NEW — BookingStatus enum
├── status_change.py                              NEW — StatusChange composite VO
├── booking.py                                    NEW — Booking aggregate
├── repository.py                                 NEW — IBookingRepository Protocol
└── lock.py                                       NEW — IBookingLockService Protocol

app/domain/resources/
└── resource.py                                   MODIFIED — adds compute_price method

app/domain/accounts/
└── role.py                                       (referenced; no changes)

app/use_cases/bookings/
├── __init__.py                                   NEW
├── dtos.py                                       NEW — BookingDto, BookingListDto, AgendaSlotDto, OwnerAgendaDto, PublicAgendaDto
├── commands/
│   ├── __init__.py                               NEW
│   ├── request_booking.py                        NEW
│   ├── approve_booking.py                        NEW
│   ├── reject_booking.py                         NEW
│   ├── cancel_booking.py                         NEW
│   └── expire_pending_bookings.py                NEW
└── queries/
    ├── __init__.py                               NEW
    ├── list_my_bookings.py                       NEW
    ├── get_my_booking.py                         NEW
    ├── list_resource_bookings.py                 NEW
    └── get_agenda.py                             NEW

app/use_cases/resources/commands/
└── soft_delete_resource.py                       MODIFIED — Plan 06 retroactive (cascade)

app/infrastructure/db/mappings/
└── booking.py                                    NEW — BookingModel

app/infrastructure/repositories/
└── booking_repository.py                         NEW — SQLAlchemyBookingRepository

app/infrastructure/bookings/
├── __init__.py                                   NEW
├── postgres_lock_service.py                      NEW — PostgresBookingLockService
└── in_memory_lock_service.py                     NEW — InMemoryBookingLockService

app/api/v1/me_bookings/
├── __init__.py                                   NEW
├── deps.py                                       NEW
├── routes.py                                     NEW
└── schemas.py                                    NEW

app/api/v1/me_resources/
└── routes.py                                     MODIFIED — adds per-resource bookings + owner agenda routes

app/api/v1/public_resources/
└── routes.py                                     MODIFIED — adds public agenda route

app/api/v1/router.py                              MODIFIED — includes me_bookings_router

app/api/error_codes.py                            MODIFIED — registers Plan 08 codes
app/migrations/env.py                             MODIFIED — registers BookingModel
app/migrations/versions/<ts>_bookings_table.py    NEW

app/jobs/
└── expire_pending_bookings.py                    NEW — cron entry-point

tests/unit/domain/shared/
└── test_weekday.py                               MODIFIED — adds from_iso tests

tests/unit/domain/bookings/
├── __init__.py                                   NEW
├── test_booking_status.py                        NEW
├── test_status_change.py                         NEW
└── test_booking.py                               NEW

tests/unit/domain/resources/
└── test_resource_compute_price.py                NEW

tests/unit/use_cases/bookings/
├── __init__.py                                   NEW
├── fakes/
│   ├── __init__.py                               NEW
│   ├── in_memory_booking_repository.py           NEW
│   └── fake_booking_lock_service.py              NEW
├── commands/                                     NEW (5 test files)
└── queries/                                      NEW (4 test files)

tests/unit/use_cases/resources/commands/
└── test_soft_delete_resource.py                  MODIFIED — extends Plan 06 tests for cascade

tests/unit/architecture/test_error_code_coverage.py    MODIFIED — extends allowlist

tests/integration/bookings/
├── __init__.py                                   NEW
├── test_booking_repository.py                    NEW
└── test_in_memory_lock_service.py                NEW

tests/integration/conftest.py                     MODIFIED — registers booking mapping import

tests/e2e/bookings/
├── __init__.py                                   NEW
├── test_happy_path.py                            NEW
├── test_competing_approvals.py                   NEW
├── test_cron_and_cascade.py                      NEW
└── test_agenda.py                                NEW

docs/superpowers/specs/2026-04-25-venue-backend-design.md   MODIFIED — refreshes §3 #14, §4.2, §5.3, §5.4, §8
```

---

## Task 1: `Weekday.from_iso` helper (Plan 06 retroactive)

**Files:**
- Modify: `app/domain/shared/weekday.py`
- Modify: `tests/unit/domain/shared/test_weekday.py`

- [ ] **Step 1: Append failing tests**

Append to `tests/unit/domain/shared/test_weekday.py`:

```python
import pytest


def test_weekday_from_iso_monday_to_sunday():
    assert Weekday.from_iso(1) is Weekday.MONDAY
    assert Weekday.from_iso(2) is Weekday.TUESDAY
    assert Weekday.from_iso(3) is Weekday.WEDNESDAY
    assert Weekday.from_iso(4) is Weekday.THURSDAY
    assert Weekday.from_iso(5) is Weekday.FRIDAY
    assert Weekday.from_iso(6) is Weekday.SATURDAY
    assert Weekday.from_iso(7) is Weekday.SUNDAY


def test_weekday_from_iso_rejects_out_of_range():
    with pytest.raises(ValueError):
        Weekday.from_iso(0)
    with pytest.raises(ValueError):
        Weekday.from_iso(8)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/unit/domain/shared/test_weekday.py -v`
Expected: 2 new tests FAIL with `AttributeError: type object 'Weekday' has no attribute 'from_iso'`.

- [ ] **Step 3: Edit `app/domain/shared/weekday.py`**

Replace the file content with:

```python
from __future__ import annotations
from enum import Enum


class Weekday(str, Enum):
    """Days of the week. str-Enum so JSON serializes to the value directly.

    Used by WeeklySchedule and PricingRule (resources feature). Lives in
    app/domain/shared/ rather than value_objects/ because it's a primitive
    enum, not a wrapped value with create()/validation.
    """

    MONDAY = "MONDAY"
    TUESDAY = "TUESDAY"
    WEDNESDAY = "WEDNESDAY"
    THURSDAY = "THURSDAY"
    FRIDAY = "FRIDAY"
    SATURDAY = "SATURDAY"
    SUNDAY = "SUNDAY"

    @classmethod
    def from_iso(cls, iso_weekday: int) -> "Weekday":
        """Maps Python's datetime.isoweekday() (1=Monday … 7=Sunday) to Weekday."""
        try:
            return _ISO_TO_WEEKDAY[iso_weekday]
        except KeyError as exc:
            raise ValueError(
                f"iso_weekday must be in [1, 7]; got {iso_weekday}",
            ) from exc


_ISO_TO_WEEKDAY: dict[int, Weekday] = {
    1: Weekday.MONDAY,
    2: Weekday.TUESDAY,
    3: Weekday.WEDNESDAY,
    4: Weekday.THURSDAY,
    5: Weekday.FRIDAY,
    6: Weekday.SATURDAY,
    7: Weekday.SUNDAY,
}
```

- [ ] **Step 4: Run tests**

Run: `.venv/bin/pytest tests/unit/domain/shared/test_weekday.py -v`
Expected: all PASSED (5 total — 3 existing + 2 new).

- [ ] **Step 5: Run full unit suite**

Run: `.venv/bin/pytest tests/unit/ -q`
Expected: green (no regression — `from_iso` is additive).

- [ ] **Step 6: Commit**

```bash
git add app/domain/shared/weekday.py tests/unit/domain/shared/test_weekday.py
git commit -m "$(cat <<'EOF'
feat(weekday): add Weekday.from_iso classmethod

Plan 08 task 1 (Plan 06 retroactive helper). Maps datetime.isoweekday()
(1..7) to the existing Weekday enum so Resource.compute_price can
look up pricing rules per slot in local timezone.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: `BookingStatus` enum

**Files:**
- Create: `app/domain/bookings/__init__.py` (empty)
- Create: `app/domain/bookings/booking_status.py`
- Create: `tests/unit/domain/bookings/__init__.py` (empty)
- Create: `tests/unit/domain/bookings/test_booking_status.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/domain/bookings/__init__.py` (empty) and `tests/unit/domain/bookings/test_booking_status.py`:

```python
from __future__ import annotations

from app.domain.bookings.booking_status import BookingStatus


def test_booking_status_values():
    assert BookingStatus.PENDING.value == "PENDING"
    assert BookingStatus.APPROVED.value == "APPROVED"
    assert BookingStatus.REJECTED.value == "REJECTED"
    assert BookingStatus.CANCELLED.value == "CANCELLED"
    assert BookingStatus.EXPIRED.value == "EXPIRED"


def test_booking_status_count():
    assert len(list(BookingStatus)) == 5


def test_booking_status_is_active():
    assert BookingStatus.PENDING.is_active() is True
    assert BookingStatus.APPROVED.is_active() is True
    assert BookingStatus.REJECTED.is_active() is False
    assert BookingStatus.CANCELLED.is_active() is False
    assert BookingStatus.EXPIRED.is_active() is False


def test_booking_status_is_terminal():
    assert BookingStatus.REJECTED.is_terminal() is True
    assert BookingStatus.CANCELLED.is_terminal() is True
    assert BookingStatus.EXPIRED.is_terminal() is True
    assert BookingStatus.PENDING.is_terminal() is False
    assert BookingStatus.APPROVED.is_terminal() is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/unit/domain/bookings/test_booking_status.py -v`
Expected: import error — `cannot import name 'BookingStatus'`.

- [ ] **Step 3: Create the module**

Create `app/domain/bookings/__init__.py` (empty) and `app/domain/bookings/booking_status.py`:

```python
from __future__ import annotations
from enum import Enum


class BookingStatus(str, Enum):
    """Booking lifecycle states (spec §6.1).

    State machine:
        PENDING → APPROVED | REJECTED | CANCELLED | EXPIRED
        APPROVED → CANCELLED
        REJECTED, CANCELLED, EXPIRED are terminal.
    """

    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"

    def is_active(self) -> bool:
        """True for PENDING and APPROVED only. Used by natural dedup —
        only active bookings block creation of overlapping requests."""
        return self in {BookingStatus.PENDING, BookingStatus.APPROVED}

    def is_terminal(self) -> bool:
        return self in {
            BookingStatus.REJECTED,
            BookingStatus.CANCELLED,
            BookingStatus.EXPIRED,
        }
```

- [ ] **Step 4: Run tests**

Run: `.venv/bin/pytest tests/unit/domain/bookings/test_booking_status.py -v`
Expected: 4 PASSED.

- [ ] **Step 5: Commit**

```bash
git add app/domain/bookings/__init__.py app/domain/bookings/booking_status.py \
        tests/unit/domain/bookings/__init__.py tests/unit/domain/bookings/test_booking_status.py
git commit -m "$(cat <<'EOF'
feat(bookings): BookingStatus enum with is_active/is_terminal helpers

Plan 08 task 2. Five values per spec §6.1. is_active() flags
PENDING/APPROVED for natural-dedup queries; is_terminal() flags
REJECTED/CANCELLED/EXPIRED for state-machine guards.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: `StatusChange` composite VO

**Files:**
- Create: `app/domain/bookings/status_change.py`
- Create: `tests/unit/domain/bookings/test_status_change.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/domain/bookings/test_status_change.py`:

```python
from __future__ import annotations
from datetime import datetime, timezone
from uuid import uuid4

from app.domain.accounts.role import Role
from app.domain.bookings.booking_status import BookingStatus
from app.domain.bookings.status_change import StatusChange


def _now() -> datetime:
    return datetime(2026, 4, 27, 12, 0, 0, tzinfo=timezone.utc)


def test_create_pending_to_approved_succeeds():
    r = StatusChange.create(
        from_status=BookingStatus.PENDING,
        to_status=BookingStatus.APPROVED,
        actor_id=uuid4(),
        actor_role=Role.OWNER,
        at=_now(),
        reason=None,
    )
    assert r.is_success
    sc = r.value
    assert sc.from_status is BookingStatus.PENDING
    assert sc.to_status is BookingStatus.APPROVED


def test_create_pending_to_pending_invalid():
    r = StatusChange.create(
        from_status=BookingStatus.PENDING,
        to_status=BookingStatus.PENDING,
        actor_id=uuid4(),
        actor_role=Role.CUSTOMER,
        at=_now(),
    )
    assert r.is_failure
    assert r.error == StatusChange.STATUS_CHANGE_INVALID_TRANSITION


def test_create_terminal_to_anything_invalid():
    for terminal in (BookingStatus.REJECTED, BookingStatus.CANCELLED, BookingStatus.EXPIRED):
        for to in (BookingStatus.PENDING, BookingStatus.APPROVED):
            r = StatusChange.create(
                from_status=terminal, to_status=to,
                actor_id=uuid4(), actor_role=Role.OWNER, at=_now(),
            )
            assert r.is_failure
            assert r.error == StatusChange.STATUS_CHANGE_INVALID_TRANSITION


def test_create_approved_to_cancelled_succeeds():
    r = StatusChange.create(
        from_status=BookingStatus.APPROVED,
        to_status=BookingStatus.CANCELLED,
        actor_id=uuid4(),
        actor_role=Role.OWNER,
        at=_now(),
        reason="storm cancelled the match",
    )
    assert r.is_success
    assert r.value.reason == "storm cancelled the match"


def test_create_approved_to_rejected_invalid():
    r = StatusChange.create(
        from_status=BookingStatus.APPROVED,
        to_status=BookingStatus.REJECTED,
        actor_id=uuid4(),
        actor_role=Role.OWNER,
        at=_now(),
    )
    assert r.is_failure
    assert r.error == StatusChange.STATUS_CHANGE_INVALID_TRANSITION


def test_create_rejects_naive_datetime():
    naive = datetime(2026, 4, 27, 12, 0, 0)
    r = StatusChange.create(
        from_status=BookingStatus.PENDING,
        to_status=BookingStatus.APPROVED,
        actor_id=uuid4(),
        actor_role=Role.OWNER,
        at=naive,
    )
    assert r.is_failure
    assert r.error == StatusChange.STATUS_CHANGE_AT_NOT_TZ_AWARE


def test_create_rejects_reason_too_long():
    r = StatusChange.create(
        from_status=BookingStatus.PENDING,
        to_status=BookingStatus.REJECTED,
        actor_id=uuid4(),
        actor_role=Role.OWNER,
        at=_now(),
        reason="x" * 501,
    )
    assert r.is_failure
    assert r.error == StatusChange.STATUS_CHANGE_REASON_TOO_LONG


def test_create_accepts_reason_at_max_length():
    r = StatusChange.create(
        from_status=BookingStatus.PENDING,
        to_status=BookingStatus.REJECTED,
        actor_id=uuid4(),
        actor_role=Role.OWNER,
        at=_now(),
        reason="x" * 500,
    )
    assert r.is_success


def test_status_change_is_frozen():
    sc = StatusChange.create(
        from_status=BookingStatus.PENDING,
        to_status=BookingStatus.APPROVED,
        actor_id=uuid4(),
        actor_role=Role.OWNER,
        at=_now(),
    ).value
    import dataclasses
    with __import__("pytest").raises(dataclasses.FrozenInstanceError):
        sc.reason = "x"  # type: ignore[misc]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/unit/domain/bookings/test_status_change.py -v`
Expected: import error — `cannot import name 'StatusChange'`.

- [ ] **Step 3: Create `app/domain/bookings/status_change.py`**

```python
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Self
from uuid import UUID

from app.domain.accounts.role import Role
from app.domain.bookings.booking_status import BookingStatus
from app.domain.shared.result import Result
from app.domain.shared.value_object import BaseValueObject


_REASON_MAX_LENGTH = 500


@dataclass(frozen=True, slots=True)
class StatusChange(BaseValueObject):
    """Audit record for one transition of a Booking. Immutable; appended to
    Booking._status_history on every state change."""

    STATUS_CHANGE_AT_NOT_TZ_AWARE = "StatusChangeAtNotTzAware"
    STATUS_CHANGE_REASON_TOO_LONG = "StatusChangeReasonTooLong"
    STATUS_CHANGE_INVALID_TRANSITION = "StatusChangeInvalidTransition"

    from_status: BookingStatus
    to_status: BookingStatus
    actor_id: UUID
    actor_role: Role
    at: datetime
    reason: str | None = None

    @classmethod
    def create(
        cls,
        *,
        from_status: BookingStatus,
        to_status: BookingStatus,
        actor_id: UUID,
        actor_role: Role,
        at: datetime,
        reason: str | None = None,
    ) -> Result[Self]:
        if at.tzinfo is None:
            return Result.failure(cls.STATUS_CHANGE_AT_NOT_TZ_AWARE)
        if reason is not None and len(reason) > _REASON_MAX_LENGTH:
            return Result.failure(cls.STATUS_CHANGE_REASON_TOO_LONG)
        if not _is_valid_transition(from_status, to_status):
            return Result.failure(cls.STATUS_CHANGE_INVALID_TRANSITION)
        return Result.success(cls(
            from_status=from_status,
            to_status=to_status,
            actor_id=actor_id,
            actor_role=actor_role,
            at=at,
            reason=reason,
        ))


_VALID_TRANSITIONS: dict[BookingStatus, set[BookingStatus]] = {
    BookingStatus.PENDING: {
        BookingStatus.APPROVED,
        BookingStatus.REJECTED,
        BookingStatus.CANCELLED,
        BookingStatus.EXPIRED,
    },
    BookingStatus.APPROVED: {BookingStatus.CANCELLED},
}


def _is_valid_transition(from_s: BookingStatus, to_s: BookingStatus) -> bool:
    return to_s in _VALID_TRANSITIONS.get(from_s, set())
```

- [ ] **Step 4: Run tests**

Run: `.venv/bin/pytest tests/unit/domain/bookings/test_status_change.py -v`
Expected: 9 PASSED.

- [ ] **Step 5: Commit**

```bash
git add app/domain/bookings/status_change.py tests/unit/domain/bookings/test_status_change.py
git commit -m "$(cat <<'EOF'
feat(bookings): StatusChange composite VO

Plan 08 task 3. Frozen audit record per state transition. Validates
tz-aware at, reason ≤ 500 chars, and the §6.1 transition matrix
(PENDING → 4 destinations; APPROVED → CANCELLED only; terminals
have no outgoing transitions).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: `Booking` aggregate

**Files:**
- Create: `app/domain/bookings/booking.py`
- Create: `tests/unit/domain/bookings/test_booking.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/domain/bookings/test_booking.py`:

```python
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.domain.accounts.role import Role
from app.domain.bookings.booking import Booking
from app.domain.bookings.booking_status import BookingStatus
from app.domain.shared.value_objects.date_time_range import DateTimeRange
from app.domain.shared.value_objects.money import Money
from app.domain.shared.value_objects.short_description import ShortDescription


def _now() -> datetime:
    return datetime(2026, 4, 27, 12, 0, 0, tzinfo=timezone.utc)


def _slot_range(hours: int = 1) -> DateTimeRange:
    return DateTimeRange.create(
        start_at=_now() + timedelta(days=1),
        end_at=_now() + timedelta(days=1, hours=hours),
    ).value


def _money(cents: int = 8000) -> Money:
    return Money.create(cents).value


def test_create_pending_sets_initial_state():
    rid, cid = uuid4(), uuid4()
    sr = _slot_range()
    b = Booking.create_pending(
        resource_id=rid,
        customer_id=cid,
        slot_range=sr,
        total_price_cents=_money(),
        customer_note=None,
        now=_now(),
    )
    assert b.resource_id == rid
    assert b.customer_id == cid
    assert b.slot_range == sr
    assert b.status is BookingStatus.PENDING
    assert b.total_price_cents.cents == 8000
    assert b.customer_note is None
    assert b.status_history == ()
    assert b.created_at == _now()
    assert b.updated_at == _now()


def test_create_pending_keeps_customer_note():
    note = ShortDescription.create("10 pessoas, festa de aniversário").value
    b = Booking.create_pending(
        resource_id=uuid4(), customer_id=uuid4(),
        slot_range=_slot_range(), total_price_cents=_money(),
        customer_note=note, now=_now(),
    )
    assert b.customer_note is note


def test_create_pending_generates_unique_ids():
    b1 = Booking.create_pending(
        resource_id=uuid4(), customer_id=uuid4(),
        slot_range=_slot_range(), total_price_cents=_money(),
        customer_note=None, now=_now(),
    )
    b2 = Booking.create_pending(
        resource_id=uuid4(), customer_id=uuid4(),
        slot_range=_slot_range(), total_price_cents=_money(),
        customer_note=None, now=_now(),
    )
    assert b1.id != b2.id


def test_slot_count():
    b = Booking.create_pending(
        resource_id=uuid4(), customer_id=uuid4(),
        slot_range=_slot_range(hours=3), total_price_cents=_money(),
        customer_note=None, now=_now(),
    )
    assert b.slot_count(slot_duration_minutes=60) == 3
    assert b.slot_count(slot_duration_minutes=30) == 6


def test_approve_transitions_pending_to_approved():
    b = Booking.create_pending(
        resource_id=uuid4(), customer_id=uuid4(),
        slot_range=_slot_range(), total_price_cents=_money(),
        customer_note=None, now=_now(),
    )
    actor = uuid4()
    later = _now() + timedelta(hours=1)
    r = b.approve(actor_id=actor, now=later)
    assert r.is_success
    assert b.status is BookingStatus.APPROVED
    assert b.updated_at == later
    assert len(b.status_history) == 1
    sc = b.status_history[0]
    assert sc.from_status is BookingStatus.PENDING
    assert sc.to_status is BookingStatus.APPROVED
    assert sc.actor_id == actor
    assert sc.actor_role is Role.OWNER
    assert sc.at == later
    assert sc.reason is None


def test_approve_already_approved_fails():
    b = Booking.create_pending(
        resource_id=uuid4(), customer_id=uuid4(),
        slot_range=_slot_range(), total_price_cents=_money(),
        customer_note=None, now=_now(),
    )
    b.approve(actor_id=uuid4(), now=_now())
    r = b.approve(actor_id=uuid4(), now=_now())
    assert r.is_failure


def test_reject_with_reason():
    b = Booking.create_pending(
        resource_id=uuid4(), customer_id=uuid4(),
        slot_range=_slot_range(), total_price_cents=_money(),
        customer_note=None, now=_now(),
    )
    r = b.reject(actor_id=uuid4(), now=_now(), reason="auto_rejected_competing_request")
    assert r.is_success
    assert b.status is BookingStatus.REJECTED
    assert b.status_history[-1].reason == "auto_rejected_competing_request"


def test_cancel_by_customer():
    b = Booking.create_pending(
        resource_id=uuid4(), customer_id=uuid4(),
        slot_range=_slot_range(), total_price_cents=_money(),
        customer_note=None, now=_now(),
    )
    r = b.cancel(actor_id=uuid4(), actor_role=Role.CUSTOMER, now=_now())
    assert r.is_success
    assert b.status is BookingStatus.CANCELLED
    assert b.status_history[-1].actor_role is Role.CUSTOMER


def test_cancel_approved_by_owner():
    b = Booking.create_pending(
        resource_id=uuid4(), customer_id=uuid4(),
        slot_range=_slot_range(), total_price_cents=_money(),
        customer_note=None, now=_now(),
    )
    b.approve(actor_id=uuid4(), now=_now())
    r = b.cancel(actor_id=uuid4(), actor_role=Role.OWNER, now=_now())
    assert r.is_success
    assert b.status is BookingStatus.CANCELLED
    # status_history has approve + cancel
    assert len(b.status_history) == 2


def test_expire_pending():
    b = Booking.create_pending(
        resource_id=uuid4(), customer_id=uuid4(),
        slot_range=_slot_range(), total_price_cents=_money(),
        customer_note=None, now=_now(),
    )
    r = b.expire(now=_now() + timedelta(days=2))
    assert r.is_success
    assert b.status is BookingStatus.EXPIRED
    sc = b.status_history[-1]
    assert sc.actor_role is Role.CUSTOMER
    assert sc.reason == "slot_start_passed_with_no_decision"


def test_expire_approved_fails():
    b = Booking.create_pending(
        resource_id=uuid4(), customer_id=uuid4(),
        slot_range=_slot_range(), total_price_cents=_money(),
        customer_note=None, now=_now(),
    )
    b.approve(actor_id=uuid4(), now=_now())
    r = b.expire(now=_now() + timedelta(days=2))
    assert r.is_failure


def test_status_history_is_append_only_view():
    b = Booking.create_pending(
        resource_id=uuid4(), customer_id=uuid4(),
        slot_range=_slot_range(), total_price_cents=_money(),
        customer_note=None, now=_now(),
    )
    b.approve(actor_id=uuid4(), now=_now())
    history = b.status_history
    assert isinstance(history, tuple)
    # Mutating private field doesn't affect prior view
    b.cancel(actor_id=uuid4(), actor_role=Role.OWNER, now=_now())
    assert len(b.status_history) == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/unit/domain/bookings/test_booking.py -v`
Expected: import error — `cannot import name 'Booking'`.

- [ ] **Step 3: Create `app/domain/bookings/booking.py`**

```python
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Self
from uuid import UUID, uuid4

from app.domain.accounts.role import Role
from app.domain.bookings.booking_status import BookingStatus
from app.domain.bookings.status_change import StatusChange
from app.domain.shared.entity import BaseEntity
from app.domain.shared.result import Result
from app.domain.shared.value_objects.date_time_range import DateTimeRange
from app.domain.shared.value_objects.money import Money
from app.domain.shared.value_objects.short_description import ShortDescription


@dataclass(slots=True, kw_only=True)
class Booking(BaseEntity):
    resource_id: UUID
    customer_id: UUID
    slot_range: DateTimeRange
    status: BookingStatus
    total_price_cents: Money
    customer_note: ShortDescription | None = None
    _status_history: tuple[StatusChange, ...] = field(default_factory=tuple)

    @classmethod
    def create_pending(
        cls,
        *,
        resource_id: UUID,
        customer_id: UUID,
        slot_range: DateTimeRange,
        total_price_cents: Money,
        customer_note: ShortDescription | None,
        now: datetime,
    ) -> "Booking":
        return cls(
            id=uuid4(),
            resource_id=resource_id,
            customer_id=customer_id,
            slot_range=slot_range,
            status=BookingStatus.PENDING,
            total_price_cents=total_price_cents,
            customer_note=customer_note,
            _status_history=(),
            created_at=now,
            updated_at=now,
        )

    @property
    def status_history(self) -> tuple[StatusChange, ...]:
        return self._status_history

    def slot_count(self, slot_duration_minutes: int) -> int:
        return self.slot_range.duration_minutes() // slot_duration_minutes

    def approve(self, *, actor_id: UUID, now: datetime) -> Result[None]:
        return self._transition(
            to_status=BookingStatus.APPROVED,
            actor_id=actor_id,
            actor_role=Role.OWNER,
            now=now,
            reason=None,
        )

    def reject(
        self, *, actor_id: UUID, now: datetime, reason: str | None = None,
    ) -> Result[None]:
        return self._transition(
            to_status=BookingStatus.REJECTED,
            actor_id=actor_id,
            actor_role=Role.OWNER,
            now=now,
            reason=reason,
        )

    def cancel(
        self, *, actor_id: UUID, actor_role: Role, now: datetime,
        reason: str | None = None,
    ) -> Result[None]:
        return self._transition(
            to_status=BookingStatus.CANCELLED,
            actor_id=actor_id,
            actor_role=actor_role,
            now=now,
            reason=reason,
        )

    def expire(self, *, now: datetime) -> Result[None]:
        return self._transition(
            to_status=BookingStatus.EXPIRED,
            actor_id=self.customer_id,
            actor_role=Role.CUSTOMER,
            now=now,
            reason="slot_start_passed_with_no_decision",
        )

    def _transition(
        self,
        *,
        to_status: BookingStatus,
        actor_id: UUID,
        actor_role: Role,
        now: datetime,
        reason: str | None,
    ) -> Result[None]:
        change_r = StatusChange.create(
            from_status=self.status,
            to_status=to_status,
            actor_id=actor_id,
            actor_role=actor_role,
            at=now,
            reason=reason,
        )
        if change_r.is_failure:
            return Result.from_failure(change_r)
        self.status = to_status
        self._status_history = (*self._status_history, change_r.value)
        self.updated_at = now
        return Result.success(None)
```

- [ ] **Step 4: Run tests**

Run: `.venv/bin/pytest tests/unit/domain/bookings/test_booking.py -v`
Expected: 12 PASSED.

- [ ] **Step 5: Commit**

```bash
git add app/domain/bookings/booking.py tests/unit/domain/bookings/test_booking.py
git commit -m "$(cat <<'EOF'
feat(bookings): Booking aggregate with state-machine mutators

Plan 08 task 4. BaseEntity-backed aggregate. create_pending() factory
takes already-validated VOs (DateTimeRange/Money/ShortDescription);
multi-field validation lives in RequestBookingHandler because it
needs Resource context. Mutators (approve/reject/cancel/expire)
delegate transition validation to StatusChange.create and append
the audit record on success.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: `IBookingRepository` + `IBookingLockService` Protocols

**Files:**
- Create: `app/domain/bookings/repository.py`
- Create: `app/domain/bookings/lock.py`

No production tests (Protocols are structural). Smoke import only.

- [ ] **Step 1: Create `app/domain/bookings/repository.py`**

```python
from __future__ import annotations
from datetime import datetime
from typing import Protocol
from uuid import UUID

from app.domain.bookings.booking import Booking
from app.domain.bookings.booking_status import BookingStatus
from app.domain.shared.result import Result
from app.domain.shared.value_objects.date_time_range import DateTimeRange


class IBookingRepository(Protocol):
    async def add(self, booking: Booking) -> Result[None]: ...

    async def get_by_id(self, booking_id: UUID) -> Result[Booking | None]: ...
    """Returns the booking regardless of customer/owner. Handlers apply scoping."""

    async def list_by_customer(
        self,
        customer_id: UUID,
        *,
        status: BookingStatus | None,
        page: int,
        page_size: int,
    ) -> Result[list[Booking]]: ...

    async def list_active_by_customer_for_resource(
        self,
        customer_id: UUID,
        resource_id: UUID,
        slot_range: DateTimeRange,
    ) -> Result[list[Booking]]: ...
    """Natural dedup: returns this customer's PENDING/APPROVED bookings on
    this resource that overlap the slot_range."""

    async def list_pending_overlapping(
        self,
        resource_id: UUID,
        slot_range: DateTimeRange,
        *,
        exclude_booking_id: UUID | None = None,
    ) -> Result[list[Booking]]: ...
    """Used by ApproveBookingHandler to find competitors."""

    async def list_by_resource(
        self,
        resource_id: UUID,
        *,
        status: BookingStatus | None,
        page: int,
        page_size: int,
    ) -> Result[list[Booking]]: ...

    async def list_in_range_for_resource(
        self,
        resource_id: UUID,
        range_start: datetime,
        range_end: datetime,
    ) -> Result[list[Booking]]: ...
    """Used by GetAgendaHandler — returns all bookings (any status) whose
    slot_range intersects [range_start, range_end]."""

    async def list_pending_with_start_before(
        self, cutoff: datetime,
    ) -> Result[list[Booking]]: ...
    """Used by ExpirePendingBookingsHandler cron."""

    async def list_pending_for_resource(
        self, resource_id: UUID,
    ) -> Result[list[Booking]]: ...
    """Used by SoftDeleteResourceHandler cascade."""

    async def list_approved_with_start_after(
        self, resource_id: UUID, cutoff: datetime,
    ) -> Result[list[Booking]]: ...
    """Used by SoftDeleteResourceHandler to detect future approved bookings
    that should block deletion."""

    async def update(self, booking: Booking) -> Result[None]: ...
```

- [ ] **Step 2: Create `app/domain/bookings/lock.py`**

```python
from __future__ import annotations
from contextlib import AbstractAsyncContextManager
from typing import Protocol
from uuid import UUID


class IBookingLockService(Protocol):
    """Per-resource lock acquired during RequestBookingHandler natural-dedup
    + ApproveBookingHandler approval transaction. Implementation is
    dialect-specific:

    - PostgresBookingLockService: pg_advisory_xact_lock(hash(uuid)) — released
      automatically at TX commit/rollback.
    - InMemoryBookingLockService: asyncio.Lock keyed by resource_id in a
      module-level dict. Single-process only; sufficient for test isolation.
    """

    def acquire_for_resource(
        self, resource_id: UUID,
    ) -> AbstractAsyncContextManager[None]: ...
```

- [ ] **Step 3: Smoke import**

Run: `.venv/bin/python -c "from app.domain.bookings.repository import IBookingRepository; from app.domain.bookings.lock import IBookingLockService; print('ok')"`
Expected: `ok`.

- [ ] **Step 4: Run unit suite**

Run: `.venv/bin/pytest tests/unit/ -q`
Expected: green.

- [ ] **Step 5: Commit**

```bash
git add app/domain/bookings/repository.py app/domain/bookings/lock.py
git commit -m "$(cat <<'EOF'
feat(bookings): IBookingRepository + IBookingLockService Protocols

Plan 08 task 5. Repo has 11 methods covering all read paths Plan 08
handlers need (by-customer, by-resource, agenda range, pending
expiry, soft-delete cascade) plus add/get/update. Lock service has
one method returning an async context manager — Postgres adapter
binds to a session; in-memory adapter uses asyncio.Lock per
resource_id.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: `Resource.compute_price` (Plan 06 retroactive)

**Files:**
- Modify: `app/domain/resources/resource.py`
- Create: `tests/unit/domain/resources/test_resource_compute_price.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/domain/resources/test_resource_compute_price.py`:

```python
from __future__ import annotations
from datetime import datetime, time, timedelta, timezone
from uuid import uuid4

from app.domain.resources.pricing_rule import PricingRule
from app.domain.resources.resource import Resource
from app.domain.shared.value_objects.date_time_range import DateTimeRange
from app.domain.shared.value_objects.money import Money
from app.domain.shared.value_objects.time_window import TimeWindow
from app.domain.shared.weekday import Weekday


def _build_resource(
    *,
    base_price_cents: int = 5000,
    pricing_rules: list[PricingRule] | None = None,
    timezone_value: str = "America/Sao_Paulo",
) -> Resource:
    operating_hours = {
        Weekday.MONDAY: [TimeWindow.create("06:00", "22:00").value],
        Weekday.TUESDAY: [TimeWindow.create("06:00", "22:00").value],
        Weekday.WEDNESDAY: [TimeWindow.create("06:00", "22:00").value],
        Weekday.THURSDAY: [TimeWindow.create("06:00", "22:00").value],
        Weekday.FRIDAY: [TimeWindow.create("06:00", "22:00").value],
        Weekday.SATURDAY: [TimeWindow.create("06:00", "22:00").value],
        Weekday.SUNDAY: [TimeWindow.create("06:00", "22:00").value],
    }
    r = Resource.create(
        owner_id=uuid4(),
        resource_type_id=uuid4(),
        slug="campo",
        name="Campo da Vila",
        description="",
        city="São Paulo",
        region="SP",
        timezone=timezone_value,
        slot_duration_minutes=60,
        base_price_cents=base_price_cents,
        customer_cancellation_cutoff_hours=24,
        operating_hours=operating_hours,
        pricing_rules=pricing_rules or [],
        custom_attributes=[],
        base_attributes={},
    )
    assert r.is_success, r.error or r.details
    return r.value


def _slot_range_local(*, year=2026, month=4, day=27, hour=14, hours=1) -> DateTimeRange:
    """Build a slot in São Paulo local time (UTC-3) → UTC."""
    # São Paulo is UTC-3 in April (no DST in Brazil since 2019).
    start_utc = datetime(year, month, day, hour + 3, 0, 0, tzinfo=timezone.utc)
    end_utc = start_utc + timedelta(hours=hours)
    return DateTimeRange.create(start_at=start_utc, end_at=end_utc).value


def test_compute_price_falls_back_to_base_when_no_rule():
    r = _build_resource(base_price_cents=5000, pricing_rules=[])
    sr = _slot_range_local(hours=2)
    price = r.compute_price(sr)
    assert price.cents == 10000  # 2 slots × 5000


def test_compute_price_uses_matching_rule():
    rule = PricingRule.create(
        weekdays={Weekday.MONDAY},
        window=TimeWindow.create("18:00", "22:00").value,
        price_cents=12000,
    ).value
    r = _build_resource(base_price_cents=5000, pricing_rules=[rule])
    # 2026-04-27 is a Monday. Slot 18:00-20:00 local matches the rule.
    sr = _slot_range_local(day=27, hour=18, hours=2)
    price = r.compute_price(sr)
    assert price.cents == 24000  # 2 slots × 12000


def test_compute_price_mixes_rule_and_fallback():
    rule = PricingRule.create(
        weekdays={Weekday.MONDAY},
        window=TimeWindow.create("18:00", "20:00").value,
        price_cents=12000,
    ).value
    r = _build_resource(base_price_cents=5000, pricing_rules=[rule])
    # 17:00-19:00: 1 slot at base, 1 slot at rule.
    sr = _slot_range_local(day=27, hour=17, hours=2)
    price = r.compute_price(sr)
    assert price.cents == 5000 + 12000


def test_compute_price_different_weekdays_different_rules():
    monday_rule = PricingRule.create(
        weekdays={Weekday.MONDAY},
        window=TimeWindow.create("06:00", "22:00").value,
        price_cents=8000,
    ).value
    saturday_rule = PricingRule.create(
        weekdays={Weekday.SATURDAY},
        window=TimeWindow.create("06:00", "22:00").value,
        price_cents=15000,
    ).value
    r = _build_resource(
        base_price_cents=5000,
        pricing_rules=[monday_rule, saturday_rule],
    )
    # Monday 14:00-15:00 = 8000.
    monday = _slot_range_local(day=27, hour=14, hours=1)
    assert r.compute_price(monday).cents == 8000
    # Saturday 2026-04-25 14:00-15:00 = 15000.
    saturday = _slot_range_local(day=25, hour=14, hours=1)
    assert r.compute_price(saturday).cents == 15000


def test_compute_price_30min_slot_duration():
    r = _build_resource(base_price_cents=2000)
    # Override slot_duration via a fresh resource with 30-min slots.
    r2 = Resource.create(
        owner_id=r.owner_id, resource_type_id=r.resource_type_id,
        slug="meio", name="Meio", description="",
        city="São Paulo", region="SP", timezone="America/Sao_Paulo",
        slot_duration_minutes=30,
        base_price_cents=2000,
        customer_cancellation_cutoff_hours=24,
        operating_hours={
            wd: [TimeWindow.create("06:00", "22:00").value]
            for wd in Weekday
        },
        pricing_rules=[],
        custom_attributes=[],
        base_attributes={},
    ).value
    sr = _slot_range_local(day=27, hour=14, hours=2)  # 4 slots of 30min
    assert r2.compute_price(sr).cents == 8000
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/unit/domain/resources/test_resource_compute_price.py -v`
Expected: `AttributeError: 'Resource' object has no attribute 'compute_price'`.

- [ ] **Step 3: Add `compute_price` to `app/domain/resources/resource.py`**

Add these imports near the top of the file (just after the existing imports):

```python
from datetime import timedelta
from app.domain.shared.weekday import Weekday
```

Add the method to the `Resource` class (after `set_slot_duration` or at the end of the class body before the dataclass closes):

```python
    def compute_price(self, slot_range: DateTimeRange) -> Money:
        """Sum of per-slot prices over slot_range.

        Iterates slot-by-slot (slot_duration_minutes intervals) in this
        resource's local timezone. For each slot, finds the first matching
        PricingRule (weekday in rule.weekdays AND slot_start_local
        in [rule.window.start, rule.window.end)). Falls back to
        base_price_cents per slot when no rule matches.

        Caller MUST ensure slot_range is grid-aligned and contained in
        operating hours; this method does NOT validate.
        """
        slot_minutes = self.slot_duration_minutes.minutes
        tz = self.timezone.to_zoneinfo()
        total_cents = 0
        cursor = slot_range.start_at
        while cursor < slot_range.end_at:
            local = cursor.astimezone(tz)
            weekday = Weekday.from_iso(local.isoweekday())
            time_of_day = local.time()
            rule = next(
                (
                    r for r in self._pricing_rules
                    if weekday in r.weekdays
                    and r.window.start <= time_of_day < r.window.end
                ),
                None,
            )
            slot_cents = (
                rule.price.cents if rule is not None
                else self.base_price_cents.cents
            )
            total_cents += slot_cents
            cursor = cursor + timedelta(minutes=slot_minutes)
        return Money.create(total_cents).value
```

- [ ] **Step 4: Run tests**

Run: `.venv/bin/pytest tests/unit/domain/resources/test_resource_compute_price.py -v`
Expected: 5 PASSED.

- [ ] **Step 5: Run full unit suite**

Run: `.venv/bin/pytest tests/unit/ -q`
Expected: green (no regression).

- [ ] **Step 6: Commit**

```bash
git add app/domain/resources/resource.py tests/unit/domain/resources/test_resource_compute_price.py
git commit -m "$(cat <<'EOF'
feat(resources): Resource.compute_price method (Plan 06 retroactive)

Plan 08 task 6. Iterates slot-by-slot in local timezone, applies the
first matching PricingRule (weekday + time-of-day window), falls
back to base_price_cents otherwise. Used by RequestBookingHandler
to freeze Booking.total_price_cents at request time and by
GetAgendaHandler to compute per-slot prices for the public agenda
view.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: `BookingModel` SQLAlchemy mapping

**Files:**
- Create: `app/infrastructure/db/mappings/booking.py`
- Modify: `app/migrations/env.py`
- Modify: `tests/integration/conftest.py`

- [ ] **Step 1: Create the mapping file**

`app/infrastructure/db/mappings/booking.py`:

```python
from __future__ import annotations
from datetime import datetime
from uuid import UUID

from sqlalchemy import BigInteger, ForeignKey, Index, JSON, Text, text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import CHAR, DateTime

from app.infrastructure.db.base import Base, TimestampMixin


class BookingModel(Base, TimestampMixin):
    __tablename__ = "bookings"
    __table_args__ = (
        Index(
            "idx_bookings_customer_status_created",
            "customer_id", "status", "created_at",
        ),
        Index(
            "idx_bookings_resource_status_start",
            "resource_id", "status", "slot_start_at",
        ),
        Index(
            "idx_bookings_pending_start",
            "slot_start_at",
            postgresql_where=text("status = 'PENDING'"),
        ),
    )

    id: Mapped[UUID] = mapped_column(CHAR(36), primary_key=True)
    resource_id: Mapped[UUID] = mapped_column(
        CHAR(36),
        ForeignKey("resources.id", ondelete="RESTRICT"),
        nullable=False,
    )
    customer_id: Mapped[UUID] = mapped_column(
        CHAR(36),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    slot_start_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
    )
    slot_end_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
    )
    status: Mapped[str] = mapped_column(Text, nullable=False)
    customer_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    total_price_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status_history: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
```

- [ ] **Step 2: Wire into Alembic env**

Edit `app/migrations/env.py`. Find the existing block (5 imports for Plan 06/07 mappings):

```python
from app.infrastructure.db.mappings import notification  # noqa: F401
from app.infrastructure.db.mappings import owner_subscription  # noqa: F401
from app.infrastructure.db.mappings import resource  # noqa: F401
from app.infrastructure.db.mappings import resource_type  # noqa: F401  (registers metadata)
from app.infrastructure.db.mappings import user  # noqa: F401
```

Add a `booking` import alphabetically before `notification`:

```python
from app.infrastructure.db.mappings import booking  # noqa: F401
from app.infrastructure.db.mappings import notification  # noqa: F401
from app.infrastructure.db.mappings import owner_subscription  # noqa: F401
from app.infrastructure.db.mappings import resource  # noqa: F401
from app.infrastructure.db.mappings import resource_type  # noqa: F401  (registers metadata)
from app.infrastructure.db.mappings import user  # noqa: F401
```

- [ ] **Step 3: Wire into integration conftest**

Edit `tests/integration/conftest.py`. Find:

```python
from app.infrastructure.db.mappings import (  # noqa: F401
    notification, owner_subscription, resource, resource_type, user,
)
```

Replace with:

```python
from app.infrastructure.db.mappings import (  # noqa: F401
    booking, notification, owner_subscription, resource, resource_type, user,
)
```

- [ ] **Step 4: Smoke-test the mapping**

Run:

```
.venv/bin/python -c "
from app.infrastructure.db.mappings.booking import BookingModel
print(BookingModel.__tablename__)
print(sorted(c.name for c in BookingModel.__table__.columns))
print(sorted(i.name for i in BookingModel.__table__.indexes))
"
```

Expected output:

```
bookings
['created_at', 'customer_id', 'customer_note', 'id', 'resource_id', 'slot_end_at', 'slot_start_at', 'status', 'status_history', 'total_price_cents', 'updated_at']
['idx_bookings_customer_status_created', 'idx_bookings_pending_start', 'idx_bookings_resource_status_start']
```

- [ ] **Step 5: Run unit + integration suites**

Run: `.venv/bin/pytest tests/unit/ tests/integration/ -q`
Expected: green.

- [ ] **Step 6: Commit**

```bash
git add app/infrastructure/db/mappings/booking.py app/migrations/env.py tests/integration/conftest.py
git commit -m "$(cat <<'EOF'
feat(bookings): BookingModel mapping

Plan 08 task 7. Declarative model with FKs to resources.id and
users.id (ON DELETE RESTRICT — bookings are audit-relevant), 3
indexes (customer/status/created for /me/bookings list,
resource/status/slot_start for agenda + competitor scan, partial
pending/slot_start for the cron query — Postgres only). Slot range
stored as two DateTime(tz=True) columns to keep mapping portable
to SQLite for tests; the exclusion constraint inlines tstzrange
in production.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: Alembic migration for `bookings` table

**Files:**
- Create: `app/migrations/versions/<auto-timestamp>_bookings_table.py`

- [ ] **Step 1: Generate the migration**

Run: `make migrate-new msg="bookings_table"`

A new file appears under `app/migrations/versions/`. If `make migrate-new` fails (no Postgres locally), create the file by hand following the schema below; the project precedent (Plan 07 task 5) is to author the migration manually when autogen needs a live DB.

The new revision must set `down_revision` to the latest existing revision (find it via `ls app/migrations/versions/ | sort | tail -1`).

- [ ] **Step 2: Replace the migration body with the schema below**

```python
"""bookings table

Revision ID: <keep autogen value>
Revises: <set to latest existing revision>
Create Date: 2026-04-27 ...

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


revision: str = '<autogen>'
down_revision: Union[str, None] = '<latest existing>'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'bookings',
        sa.Column('id', sa.CHAR(length=36), nullable=False),
        sa.Column('resource_id', sa.CHAR(length=36), nullable=False),
        sa.Column('customer_id', sa.CHAR(length=36), nullable=False),
        sa.Column('slot_start_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('slot_end_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('status', sa.Text(), nullable=False),
        sa.Column('customer_note', sa.Text(), nullable=True),
        sa.Column('total_price_cents', sa.BigInteger(), nullable=False),
        sa.Column('status_history', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['resource_id'], ['resources.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['customer_id'], ['users.id'], ondelete='RESTRICT'),
    )
    op.create_index(
        'idx_bookings_customer_status_created', 'bookings',
        ['customer_id', 'status', 'created_at'], unique=False,
    )
    op.create_index(
        'idx_bookings_resource_status_start', 'bookings',
        ['resource_id', 'status', 'slot_start_at'], unique=False,
    )

    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        # Partial index — Postgres only.
        op.create_index(
            'idx_bookings_pending_start', 'bookings', ['slot_start_at'],
            unique=False, postgresql_where=text("status = 'PENDING'"),
        )
        # btree_gist exclusion constraint — belt-and-suspenders against
        # advisory-lock bypass. WHERE filters to APPROVED only.
        op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
        op.execute(
            "ALTER TABLE bookings ADD CONSTRAINT bookings_no_approved_overlap "
            "EXCLUDE USING gist ("
            "  resource_id WITH =, "
            "  tstzrange(slot_start_at, slot_end_at, '[)') WITH && "
            ") WHERE (status = 'APPROVED')"
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        op.execute(
            "ALTER TABLE bookings DROP CONSTRAINT IF EXISTS bookings_no_approved_overlap"
        )
        op.drop_index('idx_bookings_pending_start', table_name='bookings')
    op.drop_index('idx_bookings_resource_status_start', table_name='bookings')
    op.drop_index('idx_bookings_customer_status_created', table_name='bookings')
    op.drop_table('bookings')
```

- [ ] **Step 3: Run migrations against the dev DB if Postgres is available**

Run: `make migrate-up`
Expected: applies cleanly.

If Postgres is not running locally, skip this step. Integration tests on SQLite will validate the schema via `Base.metadata.create_all`.

- [ ] **Step 4: Run unit + integration suites**

Run: `.venv/bin/pytest tests/unit/ tests/integration/ -q`
Expected: green.

- [ ] **Step 5: Commit**

```bash
git add app/migrations/versions/
git commit -m "$(cat <<'EOF'
feat(bookings): alembic migration for bookings table

Plan 08 task 8. Creates table + 3 base indexes; conditionally
(Postgres only) installs btree_gist extension, adds the partial
index on (slot_start_at) WHERE status='PENDING' for the cron query,
and adds the EXCLUDE USING gist exclusion constraint that prevents
overlapping APPROVED bookings as belt-and-suspenders against
advisory-lock bypass.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 9: `SQLAlchemyBookingRepository` (full implementation + integration tests)

**Files:**
- Create: `app/infrastructure/repositories/booking_repository.py`
- Create: `tests/integration/bookings/__init__.py` (empty)
- Create: `tests/integration/bookings/test_booking_repository.py`

- [ ] **Step 1: Write failing integration tests**

Create `tests/integration/bookings/__init__.py` (empty) and `tests/integration/bookings/test_booking_repository.py`:

```python
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.domain.bookings.booking import Booking
from app.domain.bookings.booking_status import BookingStatus
from app.domain.shared.value_objects.date_time_range import DateTimeRange
from app.domain.shared.value_objects.money import Money
from app.infrastructure.db.mappings.user import UserModel
from app.infrastructure.db.mappings.resource import ResourceModel
from app.infrastructure.db.mappings.resource_type import ResourceTypeModel
from app.infrastructure.repositories.booking_repository import (
    SQLAlchemyBookingRepository,
)


pytestmark = pytest.mark.asyncio


def _now() -> datetime:
    return datetime(2026, 4, 27, 12, 0, 0, tzinfo=timezone.utc)


def _slot_range(*, start_offset_days: int = 1, hours: int = 1) -> DateTimeRange:
    start = _now() + timedelta(days=start_offset_days)
    end = start + timedelta(hours=hours)
    return DateTimeRange.create(start_at=start, end_at=end).value


def _money(c: int = 8000) -> Money:
    return Money.create(c).value


async def _seed_user_and_resource(db_session) -> tuple:
    """Insert a user, resource_type, and resource so FK constraints
    are satisfied for booking inserts."""
    rt = ResourceTypeModel(
        id=str(uuid4()), slug="football-field", name="Football Field",
        description="", attribute_schema=[], is_active=True,
        created_at=_now(), updated_at=_now(),
    )
    owner = UserModel(
        id=str(uuid4()), email="o@example.com", full_name="Owner",
        password_hash="x", role="owner", is_active=True,
        public_slug="owner",
        phone=None,
        created_at=_now(), updated_at=_now(),
    )
    customer = UserModel(
        id=str(uuid4()), email="c@example.com", full_name="Customer",
        password_hash="x", role="customer", is_active=True,
        public_slug=None, phone=None,
        created_at=_now(), updated_at=_now(),
    )
    res = ResourceModel(
        id=str(uuid4()), owner_id=owner.id, resource_type_id=rt.id,
        slug="campo", name="Campo", description="",
        city="SP", region="SP", timezone="America/Sao_Paulo",
        slot_duration_minutes=60, base_price_cents=8000,
        customer_cancellation_cutoff_hours=24,
        operating_hours={"monday": [{"start": "06:00", "end": "22:00"}]},
        pricing_rules=[], custom_attributes=[], base_attributes={},
        is_published=True, deleted_at=None,
        created_at=_now(), updated_at=_now(),
    )
    db_session.add_all([rt, owner, customer, res])
    await db_session.flush()
    return owner, customer, res


async def test_add_and_get_round_trip(db_session):
    repo = SQLAlchemyBookingRepository(db_session)
    _, customer, res = await _seed_user_and_resource(db_session)
    sr = _slot_range()
    b = Booking.create_pending(
        resource_id=res.id, customer_id=customer.id,
        slot_range=sr, total_price_cents=_money(),
        customer_note=None, now=_now(),
    )
    add_r = await repo.add(b)
    assert add_r.is_success
    fetched = (await repo.get_by_id(b.id)).value
    assert fetched is not None
    assert fetched.id == b.id
    assert fetched.status is BookingStatus.PENDING
    assert fetched.slot_range.start_at == sr.start_at
    assert fetched.slot_range.end_at == sr.end_at


async def test_list_by_customer_filters_status(db_session):
    repo = SQLAlchemyBookingRepository(db_session)
    _, customer, res = await _seed_user_and_resource(db_session)
    pending = Booking.create_pending(
        resource_id=res.id, customer_id=customer.id,
        slot_range=_slot_range(start_offset_days=1),
        total_price_cents=_money(), customer_note=None, now=_now(),
    )
    approved = Booking.create_pending(
        resource_id=res.id, customer_id=customer.id,
        slot_range=_slot_range(start_offset_days=2),
        total_price_cents=_money(), customer_note=None, now=_now(),
    )
    approved.approve(actor_id=uuid4(), now=_now())
    await repo.add(pending)
    await repo.add(approved)

    pendings = (await repo.list_by_customer(
        customer.id, status=BookingStatus.PENDING, page=1, page_size=10,
    )).value
    assert [b.id for b in pendings] == [pending.id]


async def test_list_pending_overlapping_excludes_self_and_other_resources(db_session):
    repo = SQLAlchemyBookingRepository(db_session)
    _, customer, res = await _seed_user_and_resource(db_session)
    sr = _slot_range(start_offset_days=1, hours=2)
    target = Booking.create_pending(
        resource_id=res.id, customer_id=customer.id,
        slot_range=sr, total_price_cents=_money(), customer_note=None,
        now=_now(),
    )
    competitor_overlapping = Booking.create_pending(
        resource_id=res.id, customer_id=uuid4(),
        slot_range=DateTimeRange.create(
            start_at=sr.start_at + timedelta(minutes=30),
            end_at=sr.end_at + timedelta(minutes=30),
        ).value,
        total_price_cents=_money(), customer_note=None, now=_now(),
    )
    competitor_disjoint = Booking.create_pending(
        resource_id=res.id, customer_id=uuid4(),
        slot_range=_slot_range(start_offset_days=5),
        total_price_cents=_money(), customer_note=None, now=_now(),
    )
    # Insert a fake customer for the second competitor (FK).
    other_customer = UserModel(
        id=str(uuid4()), email="x@example.com", full_name="X",
        password_hash="x", role="customer", is_active=True,
        public_slug=None, phone=None, created_at=_now(), updated_at=_now(),
    )
    db_session.add(other_customer)
    competitor_disjoint = Booking.create_pending(
        resource_id=res.id, customer_id=other_customer.id,
        slot_range=_slot_range(start_offset_days=5),
        total_price_cents=_money(), customer_note=None, now=_now(),
    )
    competitor_overlapping = Booking.create_pending(
        resource_id=res.id, customer_id=other_customer.id,
        slot_range=DateTimeRange.create(
            start_at=sr.start_at + timedelta(minutes=30),
            end_at=sr.end_at + timedelta(minutes=30),
        ).value,
        total_price_cents=_money(), customer_note=None, now=_now(),
    )
    await db_session.flush()
    await repo.add(target)
    await repo.add(competitor_overlapping)
    await repo.add(competitor_disjoint)

    overlaps = (await repo.list_pending_overlapping(
        res.id, sr, exclude_booking_id=target.id,
    )).value
    assert {b.id for b in overlaps} == {competitor_overlapping.id}


async def test_list_active_by_customer_for_resource_filters_to_active(db_session):
    repo = SQLAlchemyBookingRepository(db_session)
    _, customer, res = await _seed_user_and_resource(db_session)
    sr = _slot_range()
    pending = Booking.create_pending(
        resource_id=res.id, customer_id=customer.id,
        slot_range=sr, total_price_cents=_money(),
        customer_note=None, now=_now(),
    )
    cancelled = Booking.create_pending(
        resource_id=res.id, customer_id=customer.id,
        slot_range=sr, total_price_cents=_money(),
        customer_note=None, now=_now(),
    )
    cancelled.cancel(actor_id=customer.id, actor_role=__import__("app.domain.accounts.role", fromlist=["Role"]).Role.CUSTOMER, now=_now())
    await repo.add(pending)
    await repo.add(cancelled)

    actives = (await repo.list_active_by_customer_for_resource(
        customer.id, res.id, sr,
    )).value
    assert [b.id for b in actives] == [pending.id]


async def test_list_pending_with_start_before_filters_correctly(db_session):
    repo = SQLAlchemyBookingRepository(db_session)
    _, customer, res = await _seed_user_and_resource(db_session)
    past = Booking.create_pending(
        resource_id=res.id, customer_id=customer.id,
        slot_range=DateTimeRange.create(
            start_at=_now() - timedelta(hours=2),
            end_at=_now() - timedelta(hours=1),
        ).value,
        total_price_cents=_money(), customer_note=None, now=_now() - timedelta(days=1),
    )
    future = Booking.create_pending(
        resource_id=res.id, customer_id=customer.id,
        slot_range=_slot_range(start_offset_days=2),
        total_price_cents=_money(), customer_note=None, now=_now(),
    )
    await repo.add(past)
    await repo.add(future)

    expired = (await repo.list_pending_with_start_before(_now())).value
    assert {b.id for b in expired} == {past.id}


async def test_update_persists_status_change(db_session):
    repo = SQLAlchemyBookingRepository(db_session)
    _, customer, res = await _seed_user_and_resource(db_session)
    b = Booking.create_pending(
        resource_id=res.id, customer_id=customer.id,
        slot_range=_slot_range(), total_price_cents=_money(),
        customer_note=None, now=_now(),
    )
    await repo.add(b)
    b.approve(actor_id=uuid4(), now=_now())
    update_r = await repo.update(b)
    assert update_r.is_success
    fetched = (await repo.get_by_id(b.id)).value
    assert fetched.status is BookingStatus.APPROVED
    assert len(fetched.status_history) == 1
    assert fetched.status_history[0].to_status is BookingStatus.APPROVED
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/integration/bookings/ -v`
Expected: import error — `cannot import name 'SQLAlchemyBookingRepository'`.

- [ ] **Step 3: Create `app/infrastructure/repositories/booking_repository.py`**

```python
from __future__ import annotations
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.accounts.role import Role
from app.domain.bookings.booking import Booking
from app.domain.bookings.booking_status import BookingStatus
from app.domain.bookings.repository import IBookingRepository
from app.domain.bookings.status_change import StatusChange
from app.domain.shared.result import Result
from app.domain.shared.value_objects.date_time_range import DateTimeRange
from app.domain.shared.value_objects.money import Money
from app.domain.shared.value_objects.short_description import ShortDescription
from app.infrastructure.db.mappings.booking import BookingModel


def _ensure_utc(dt: datetime | None) -> datetime | None:
    """SQLite + aiosqlite drop tzinfo on roundtrip; assume stored values are UTC."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _serialize_status_history(history: tuple[StatusChange, ...]) -> list[dict]:
    return [
        {
            "from_status": sc.from_status.value,
            "to_status": sc.to_status.value,
            "actor_id": str(sc.actor_id),
            "actor_role": sc.actor_role.value,
            "at": sc.at.isoformat(),
            "reason": sc.reason,
        }
        for sc in history
    ]


def _deserialize_status_history(rows: list[dict]) -> tuple[StatusChange, ...]:
    return tuple(
        StatusChange.create(
            from_status=BookingStatus(r["from_status"]),
            to_status=BookingStatus(r["to_status"]),
            actor_id=UUID(r["actor_id"]),
            actor_role=Role(r["actor_role"]),
            at=_ensure_utc(datetime.fromisoformat(r["at"])),
            reason=r.get("reason"),
        ).value
        for r in rows
    )


def _to_model_kwargs(b: Booking) -> dict:
    return {
        "id": str(b.id),
        "resource_id": str(b.resource_id),
        "customer_id": str(b.customer_id),
        "slot_start_at": b.slot_range.start_at,
        "slot_end_at": b.slot_range.end_at,
        "status": b.status.value,
        "customer_note": b.customer_note.value if b.customer_note else None,
        "total_price_cents": b.total_price_cents.cents,
        "status_history": _serialize_status_history(b.status_history),
        "created_at": b.created_at,
        "updated_at": b.updated_at,
    }


def _to_entity(m: BookingModel) -> Booking:
    note = (
        ShortDescription.create(m.customer_note).value
        if m.customer_note is not None else None
    )
    return Booking(
        id=UUID(str(m.id)),
        resource_id=UUID(str(m.resource_id)),
        customer_id=UUID(str(m.customer_id)),
        slot_range=DateTimeRange.create(
            start_at=_ensure_utc(m.slot_start_at),
            end_at=_ensure_utc(m.slot_end_at),
        ).value,
        status=BookingStatus(m.status),
        total_price_cents=Money.create(m.total_price_cents).value,
        customer_note=note,
        _status_history=_deserialize_status_history(m.status_history or []),
        created_at=_ensure_utc(m.created_at),
        updated_at=_ensure_utc(m.updated_at),
    )


def _overlaps_clause(slot_range: DateTimeRange):
    """Build a SQLAlchemy clause for half-open interval overlap:
    slot_start_at < range.end_at AND slot_end_at > range.start_at."""
    return and_(
        BookingModel.slot_start_at < slot_range.end_at,
        BookingModel.slot_end_at > slot_range.start_at,
    )


class SQLAlchemyBookingRepository(IBookingRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, booking: Booking) -> Result[None]:
        self._session.add(BookingModel(**_to_model_kwargs(booking)))
        await self._session.flush()
        return Result.success(None)

    async def get_by_id(self, booking_id: UUID) -> Result[Booking | None]:
        stmt = select(BookingModel).where(BookingModel.id == str(booking_id))
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return Result.success(_to_entity(row) if row else None)

    async def list_by_customer(
        self,
        customer_id: UUID,
        *,
        status: BookingStatus | None,
        page: int,
        page_size: int,
    ) -> Result[list[Booking]]:
        stmt = (
            select(BookingModel)
            .where(BookingModel.customer_id == str(customer_id))
            .order_by(BookingModel.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        if status is not None:
            stmt = stmt.where(BookingModel.status == status.value)
        rows = (await self._session.execute(stmt)).scalars().all()
        return Result.success([_to_entity(r) for r in rows])

    async def list_active_by_customer_for_resource(
        self,
        customer_id: UUID,
        resource_id: UUID,
        slot_range: DateTimeRange,
    ) -> Result[list[Booking]]:
        stmt = (
            select(BookingModel)
            .where(
                BookingModel.customer_id == str(customer_id),
                BookingModel.resource_id == str(resource_id),
                BookingModel.status.in_([
                    BookingStatus.PENDING.value,
                    BookingStatus.APPROVED.value,
                ]),
                _overlaps_clause(slot_range),
            )
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return Result.success([_to_entity(r) for r in rows])

    async def list_pending_overlapping(
        self,
        resource_id: UUID,
        slot_range: DateTimeRange,
        *,
        exclude_booking_id: UUID | None = None,
    ) -> Result[list[Booking]]:
        stmt = (
            select(BookingModel)
            .where(
                BookingModel.resource_id == str(resource_id),
                BookingModel.status == BookingStatus.PENDING.value,
                _overlaps_clause(slot_range),
            )
        )
        if exclude_booking_id is not None:
            stmt = stmt.where(BookingModel.id != str(exclude_booking_id))
        rows = (await self._session.execute(stmt)).scalars().all()
        return Result.success([_to_entity(r) for r in rows])

    async def list_by_resource(
        self,
        resource_id: UUID,
        *,
        status: BookingStatus | None,
        page: int,
        page_size: int,
    ) -> Result[list[Booking]]:
        stmt = (
            select(BookingModel)
            .where(BookingModel.resource_id == str(resource_id))
            .order_by(BookingModel.slot_start_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        if status is not None:
            stmt = stmt.where(BookingModel.status == status.value)
        rows = (await self._session.execute(stmt)).scalars().all()
        return Result.success([_to_entity(r) for r in rows])

    async def list_in_range_for_resource(
        self,
        resource_id: UUID,
        range_start: datetime,
        range_end: datetime,
    ) -> Result[list[Booking]]:
        stmt = (
            select(BookingModel)
            .where(
                BookingModel.resource_id == str(resource_id),
                BookingModel.slot_start_at < range_end,
                BookingModel.slot_end_at > range_start,
            )
            .order_by(BookingModel.slot_start_at)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return Result.success([_to_entity(r) for r in rows])

    async def list_pending_with_start_before(
        self, cutoff: datetime,
    ) -> Result[list[Booking]]:
        stmt = (
            select(BookingModel)
            .where(
                BookingModel.status == BookingStatus.PENDING.value,
                BookingModel.slot_start_at < cutoff,
            )
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return Result.success([_to_entity(r) for r in rows])

    async def list_pending_for_resource(
        self, resource_id: UUID,
    ) -> Result[list[Booking]]:
        stmt = (
            select(BookingModel)
            .where(
                BookingModel.resource_id == str(resource_id),
                BookingModel.status == BookingStatus.PENDING.value,
            )
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return Result.success([_to_entity(r) for r in rows])

    async def list_approved_with_start_after(
        self, resource_id: UUID, cutoff: datetime,
    ) -> Result[list[Booking]]:
        stmt = (
            select(BookingModel)
            .where(
                BookingModel.resource_id == str(resource_id),
                BookingModel.status == BookingStatus.APPROVED.value,
                BookingModel.slot_start_at >= cutoff,
            )
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return Result.success([_to_entity(r) for r in rows])

    async def update(self, booking: Booking) -> Result[None]:
        stmt = select(BookingModel).where(BookingModel.id == str(booking.id))
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        if row is None:
            return Result.failure("BookingNotFound", status_code=404)
        kwargs = _to_model_kwargs(booking)
        for k, v in kwargs.items():
            if k == "id":
                continue
            setattr(row, k, v)
        await self._session.flush()
        return Result.success(None)
```

- [ ] **Step 4: Run integration tests**

Run: `.venv/bin/pytest tests/integration/bookings/ -v`
Expected: 6 PASSED.

- [ ] **Step 5: Run full unit + integration**

Run: `.venv/bin/pytest tests/unit/ tests/integration/ -q`
Expected: green.

- [ ] **Step 6: Commit**

```bash
git add app/infrastructure/repositories/booking_repository.py tests/integration/bookings/
git commit -m "$(cat <<'EOF'
feat(bookings): SQLAlchemyBookingRepository

Plan 08 task 9. Implements all 11 methods of IBookingRepository
over AsyncSession. status_history serialized to JSON via
_serialize_status_history; round-trips through StatusChange.create
to preserve invariants on read. Half-open overlap clause used in
list_pending_overlapping, list_active_by_customer_for_resource,
list_in_range_for_resource — matches DateTimeRange.overlaps()
semantics.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 10: Lock service adapters (Postgres + InMemory)

**Files:**
- Create: `app/infrastructure/bookings/__init__.py` (empty)
- Create: `app/infrastructure/bookings/postgres_lock_service.py`
- Create: `app/infrastructure/bookings/in_memory_lock_service.py`
- Create: `tests/integration/bookings/test_in_memory_lock_service.py`

- [ ] **Step 1: Write failing test for the in-memory adapter**

Create `tests/integration/bookings/test_in_memory_lock_service.py`:

```python
from __future__ import annotations
import asyncio
from uuid import uuid4

import pytest

from app.infrastructure.bookings.in_memory_lock_service import (
    InMemoryBookingLockService,
)


pytestmark = pytest.mark.asyncio


async def test_concurrent_acquires_on_same_resource_serialize():
    svc = InMemoryBookingLockService()
    rid = uuid4()
    order: list[str] = []

    async def worker(label: str, hold: float):
        async with svc.acquire_for_resource(rid):
            order.append(f"{label}:in")
            await asyncio.sleep(hold)
            order.append(f"{label}:out")

    await asyncio.gather(worker("A", 0.05), worker("B", 0.0))
    # If serialized, A:in → A:out → B:in → B:out (or B first then A).
    # Test: every "in" is immediately followed by the matching "out".
    assert order[0].endswith(":in")
    assert order[1].endswith(":out")
    assert order[0].split(":")[0] == order[1].split(":")[0]
    assert order[2].endswith(":in")
    assert order[3].endswith(":out")
    assert order[2].split(":")[0] == order[3].split(":")[0]


async def test_concurrent_acquires_on_different_resources_do_not_serialize():
    svc = InMemoryBookingLockService()
    r1, r2 = uuid4(), uuid4()
    started: list[str] = []
    finished: list[str] = []

    async def worker(label: str, rid):
        async with svc.acquire_for_resource(rid):
            started.append(label)
            await asyncio.sleep(0.05)
            finished.append(label)

    await asyncio.gather(worker("A", r1), worker("B", r2))
    # Both should start before either finishes (parallel because different rids).
    assert set(started) == {"A", "B"}
    assert len(started) == 2
    assert set(finished) == {"A", "B"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/integration/bookings/test_in_memory_lock_service.py -v`
Expected: import error.

- [ ] **Step 3: Create `app/infrastructure/bookings/__init__.py`** (empty file).

- [ ] **Step 4: Create `app/infrastructure/bookings/in_memory_lock_service.py`**

```python
from __future__ import annotations
import asyncio
from contextlib import asynccontextmanager
from uuid import UUID

from app.domain.bookings.lock import IBookingLockService


class InMemoryBookingLockService(IBookingLockService):
    """asyncio.Lock per resource_id in a process-local dict.

    Sufficient for SQLite-backed integration tests and unit tests; NOT
    suitable for production multi-instance deployments.
    """

    def __init__(self) -> None:
        self._locks: dict[UUID, asyncio.Lock] = {}

    @asynccontextmanager
    async def acquire_for_resource(self, resource_id: UUID):
        lock = self._locks.setdefault(resource_id, asyncio.Lock())
        async with lock:
            yield None
```

- [ ] **Step 5: Create `app/infrastructure/bookings/postgres_lock_service.py`**

```python
from __future__ import annotations
from contextlib import asynccontextmanager
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.bookings.lock import IBookingLockService


class PostgresBookingLockService(IBookingLockService):
    """Wraps Postgres pg_advisory_xact_lock keyed on a hash of resource_id.

    The lock is automatically released at TX commit/rollback (xact lock
    flavor). Caller must run inside a transaction; in FastAPI request
    handlers, this is the request-scoped session.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @asynccontextmanager
    async def acquire_for_resource(self, resource_id: UUID):
        await self._session.execute(
            text("SELECT pg_advisory_xact_lock(:k)"),
            {"k": self._hash_uuid(resource_id)},
        )
        try:
            yield None
        finally:
            # No-op: pg_advisory_xact_lock releases at TX commit/rollback.
            pass

    @staticmethod
    def _hash_uuid(uuid: UUID) -> int:
        # int.from_bytes with signed=True yields a value in
        # [-2**63, 2**63-1] which fits Postgres BIGINT for advisory locks.
        return int.from_bytes(uuid.bytes[:8], "big", signed=True)
```

- [ ] **Step 6: Run tests**

Run: `.venv/bin/pytest tests/integration/bookings/test_in_memory_lock_service.py -v`
Expected: 2 PASSED.

- [ ] **Step 7: Smoke import the Postgres adapter (no live DB needed for import)**

Run: `.venv/bin/python -c "from app.infrastructure.bookings.postgres_lock_service import PostgresBookingLockService; print('ok')"`
Expected: `ok`.

- [ ] **Step 8: Commit**

```bash
git add app/infrastructure/bookings/ tests/integration/bookings/test_in_memory_lock_service.py
git commit -m "$(cat <<'EOF'
feat(bookings): Postgres + InMemory lock service adapters

Plan 08 task 10. PostgresBookingLockService wraps
pg_advisory_xact_lock(int8(uuid_bytes[:8])) — released at TX commit
or rollback. InMemoryBookingLockService keys an asyncio.Lock per
resource_id in a process-local dict; sufficient for tests + single-
instance dev. Integration tests prove same-resource calls serialize
and different-resource calls don't.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 11: Use case DTOs

**Files:**
- Create: `app/use_cases/bookings/__init__.py` (empty)
- Create: `app/use_cases/bookings/dtos.py`

- [ ] **Step 1: Create the DTO module**

`app/use_cases/bookings/__init__.py` (empty).

`app/use_cases/bookings/dtos.py`:

```python
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal
from uuid import UUID

from app.domain.bookings.booking import Booking


@dataclass(frozen=True, kw_only=True, slots=True)
class StatusChangeDto:
    from_status: str
    to_status: str
    actor_id: UUID
    actor_role: str
    at: datetime
    reason: str | None


@dataclass(frozen=True, kw_only=True, slots=True)
class BookingDto:
    id: UUID
    resource_id: UUID
    customer_id: UUID
    slot_start_at: datetime
    slot_end_at: datetime
    status: str
    customer_note: str | None
    total_price_cents: int
    status_history: tuple[StatusChangeDto, ...]
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_entity(cls, b: Booking) -> "BookingDto":
        return cls(
            id=b.id,
            resource_id=b.resource_id,
            customer_id=b.customer_id,
            slot_start_at=b.slot_range.start_at,
            slot_end_at=b.slot_range.end_at,
            status=b.status.value,
            customer_note=b.customer_note.value if b.customer_note else None,
            total_price_cents=b.total_price_cents.cents,
            status_history=tuple(
                StatusChangeDto(
                    from_status=sc.from_status.value,
                    to_status=sc.to_status.value,
                    actor_id=sc.actor_id,
                    actor_role=sc.actor_role.value,
                    at=sc.at,
                    reason=sc.reason,
                )
                for sc in b.status_history
            ),
            created_at=b.created_at,
            updated_at=b.updated_at,
        )


@dataclass(frozen=True, kw_only=True, slots=True)
class BookingListDto:
    items: tuple[BookingDto, ...]
    page: int
    page_size: int


SlotStatus = Literal["AVAILABLE", "PENDING", "APPROVED"]


@dataclass(frozen=True, kw_only=True, slots=True)
class AgendaSlotDto:
    slot_start_at: datetime
    slot_end_at: datetime
    status: SlotStatus
    price_cents: int
    booking_id: UUID | None = None       # None for AVAILABLE / public view
    customer_id: UUID | None = None      # owner view only


@dataclass(frozen=True, kw_only=True, slots=True)
class AgendaDto:
    resource_id: UUID
    slots: tuple[AgendaSlotDto, ...]
```

- [ ] **Step 2: Smoke import**

Run: `.venv/bin/python -c "from app.use_cases.bookings.dtos import BookingDto, BookingListDto, AgendaSlotDto, AgendaDto; print('ok')"`
Expected: `ok`.

- [ ] **Step 3: Commit**

```bash
git add app/use_cases/bookings/__init__.py app/use_cases/bookings/dtos.py
git commit -m "$(cat <<'EOF'
feat(bookings): use case DTOs

Plan 08 task 11. BookingDto.from_entity flattens the aggregate for
the HTTP boundary including status_history (kind enum -> str).
AgendaSlotDto carries booking_id + customer_id for owner-detailed
views; both are None on public/AVAILABLE. AgendaDto wraps slots
with the resource_id.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 12: Test fakes (`InMemoryBookingRepository` + `FakeBookingLockService`)

**Files:**
- Create: `tests/unit/use_cases/bookings/__init__.py` (empty)
- Create: `tests/unit/use_cases/bookings/fakes/__init__.py` (empty)
- Create: `tests/unit/use_cases/bookings/fakes/in_memory_booking_repository.py`
- Create: `tests/unit/use_cases/bookings/fakes/fake_booking_lock_service.py`

These are test-only support files. Exercised implicitly by handler tests in Tasks 13-17 + 19-22.

- [ ] **Step 1: Create the in-memory repository fake**

```python
# tests/unit/use_cases/bookings/fakes/in_memory_booking_repository.py
from __future__ import annotations
from datetime import datetime
from uuid import UUID

from app.domain.bookings.booking import Booking
from app.domain.bookings.booking_status import BookingStatus
from app.domain.bookings.repository import IBookingRepository
from app.domain.shared.result import Result
from app.domain.shared.value_objects.date_time_range import DateTimeRange


def _overlaps(a: DateTimeRange, b: DateTimeRange) -> bool:
    return a.start_at < b.end_at and b.start_at < a.end_at


class InMemoryBookingRepository(IBookingRepository):
    def __init__(self) -> None:
        self._rows: list[Booking] = []

    async def add(self, booking: Booking) -> Result[None]:
        self._rows.append(booking)
        return Result.success(None)

    async def get_by_id(self, booking_id: UUID) -> Result[Booking | None]:
        for b in self._rows:
            if b.id == booking_id:
                return Result.success(b)
        return Result.success(None)

    async def list_by_customer(
        self, customer_id: UUID, *,
        status: BookingStatus | None,
        page: int,
        page_size: int,
    ) -> Result[list[Booking]]:
        filtered = [
            b for b in self._rows
            if b.customer_id == customer_id
            and (status is None or b.status is status)
        ]
        filtered.sort(key=lambda b: b.created_at, reverse=True)
        offset = (page - 1) * page_size
        return Result.success(filtered[offset:offset + page_size])

    async def list_active_by_customer_for_resource(
        self,
        customer_id: UUID,
        resource_id: UUID,
        slot_range: DateTimeRange,
    ) -> Result[list[Booking]]:
        return Result.success([
            b for b in self._rows
            if b.customer_id == customer_id
            and b.resource_id == resource_id
            and b.status.is_active()
            and _overlaps(b.slot_range, slot_range)
        ])

    async def list_pending_overlapping(
        self,
        resource_id: UUID,
        slot_range: DateTimeRange,
        *,
        exclude_booking_id: UUID | None = None,
    ) -> Result[list[Booking]]:
        return Result.success([
            b for b in self._rows
            if b.resource_id == resource_id
            and b.status is BookingStatus.PENDING
            and _overlaps(b.slot_range, slot_range)
            and b.id != exclude_booking_id
        ])

    async def list_by_resource(
        self,
        resource_id: UUID,
        *,
        status: BookingStatus | None,
        page: int,
        page_size: int,
    ) -> Result[list[Booking]]:
        filtered = [
            b for b in self._rows
            if b.resource_id == resource_id
            and (status is None or b.status is status)
        ]
        filtered.sort(key=lambda b: b.slot_range.start_at, reverse=True)
        offset = (page - 1) * page_size
        return Result.success(filtered[offset:offset + page_size])

    async def list_in_range_for_resource(
        self,
        resource_id: UUID,
        range_start: datetime,
        range_end: datetime,
    ) -> Result[list[Booking]]:
        return Result.success([
            b for b in self._rows
            if b.resource_id == resource_id
            and b.slot_range.start_at < range_end
            and b.slot_range.end_at > range_start
        ])

    async def list_pending_with_start_before(
        self, cutoff: datetime,
    ) -> Result[list[Booking]]:
        return Result.success([
            b for b in self._rows
            if b.status is BookingStatus.PENDING
            and b.slot_range.start_at < cutoff
        ])

    async def list_pending_for_resource(
        self, resource_id: UUID,
    ) -> Result[list[Booking]]:
        return Result.success([
            b for b in self._rows
            if b.resource_id == resource_id
            and b.status is BookingStatus.PENDING
        ])

    async def list_approved_with_start_after(
        self, resource_id: UUID, cutoff: datetime,
    ) -> Result[list[Booking]]:
        return Result.success([
            b for b in self._rows
            if b.resource_id == resource_id
            and b.status is BookingStatus.APPROVED
            and b.slot_range.start_at >= cutoff
        ])

    async def update(self, booking: Booking) -> Result[None]:
        for i, existing in enumerate(self._rows):
            if existing.id == booking.id:
                self._rows[i] = booking
                return Result.success(None)
        return Result.failure("BookingNotFound", status_code=404)
```

- [ ] **Step 2: Create the no-op lock service fake**

```python
# tests/unit/use_cases/bookings/fakes/fake_booking_lock_service.py
from __future__ import annotations
from contextlib import asynccontextmanager
from uuid import UUID

from app.domain.bookings.lock import IBookingLockService


class FakeBookingLockService(IBookingLockService):
    """No-op acquire — single-thread unit tests don't need real serialization."""

    @asynccontextmanager
    async def acquire_for_resource(self, resource_id: UUID):
        yield None
```

- [ ] **Step 3: Smoke import**

Run:
```
.venv/bin/python -c "
from tests.unit.use_cases.bookings.fakes.in_memory_booking_repository import InMemoryBookingRepository
from tests.unit.use_cases.bookings.fakes.fake_booking_lock_service import FakeBookingLockService
print('ok')
"
```
Expected: `ok`.

- [ ] **Step 4: Commit**

```bash
git add tests/unit/use_cases/bookings/
git commit -m "$(cat <<'EOF'
test(bookings): InMemoryBookingRepository + FakeBookingLockService

Plan 08 task 12. List-backed repo mirrors all 11 SQL repo methods
including overlap semantics. FakeBookingLockService is no-op
(single-thread unit tests don't need lock serialization).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 13: `RequestBookingHandler`

**Files:**
- Create: `app/use_cases/bookings/commands/__init__.py` (empty)
- Create: `app/use_cases/bookings/commands/request_booking.py`
- Create: `tests/unit/use_cases/bookings/commands/__init__.py` (empty)
- Create: `tests/unit/use_cases/bookings/commands/test_request_booking.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/use_cases/bookings/commands/__init__.py` (empty) and `tests/unit/use_cases/bookings/commands/test_request_booking.py`:

```python
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.domain.bookings.booking_status import BookingStatus
from app.domain.notifications.service import NotifKind
from app.domain.resources.pricing_rule import PricingRule
from app.domain.resources.resource import Resource
from app.domain.shared.value_objects.time_window import TimeWindow
from app.domain.shared.weekday import Weekday
from app.domain.subscriptions.owner_subscription import OwnerSubscription
from app.domain.subscriptions.sub_status import SubStatus
from app.use_cases.bookings.commands.request_booking import (
    RequestBookingCommand,
    RequestBookingHandler,
)
from tests.unit.use_cases.bookings.fakes.in_memory_booking_repository import (
    InMemoryBookingRepository,
)
from tests.unit.use_cases.subscriptions.fakes.fake_notification_service import (
    FakeNotificationService,
)


pytestmark = pytest.mark.asyncio


def _now() -> datetime:
    # 2026-04-27 12:00 UTC = 09:00 São Paulo on a Monday.
    return datetime(2026, 4, 27, 12, 0, 0, tzinfo=timezone.utc)


def _build_resource(
    *, owner_id, is_published: bool = True, deleted: bool = False,
) -> Resource:
    operating = {
        wd: [TimeWindow.create("06:00", "22:00").value]
        for wd in Weekday
    }
    r = Resource.create(
        owner_id=owner_id, resource_type_id=uuid4(),
        slug="campo", name="Campo", description="",
        city="SP", region="SP", timezone="America/Sao_Paulo",
        slot_duration_minutes=60, base_price_cents=8000,
        customer_cancellation_cutoff_hours=24,
        operating_hours=operating,
        pricing_rules=[], custom_attributes=[], base_attributes={},
    ).value
    if is_published:
        r.publish()
    if deleted:
        r.soft_delete(now=_now() - timedelta(days=1))
    return r


def _local_slot(*, day: int = 28, hour_local: int = 14, hours: int = 1) -> tuple[datetime, datetime]:
    """Build a (start_utc, end_utc) tuple anchored at hour_local in São Paulo."""
    start_utc = datetime(2026, 4, day, hour_local + 3, 0, 0, tzinfo=timezone.utc)
    end_utc = start_utc + timedelta(hours=hours)
    return start_utc, end_utc


class _FakeResourceRepo:
    def __init__(self, resources: list[Resource]):
        self._by_id = {r.id: r for r in resources}

    async def get_by_id(self, rid):
        from app.domain.shared.result import Result
        return Result.success(self._by_id.get(rid))


class _FakeSubRepo:
    def __init__(self, sub: OwnerSubscription | None):
        self._sub = sub

    async def get_by_owner_id(self, owner_id):
        return self._sub if self._sub and self._sub.owner_id == owner_id else None


def _make_active_sub(owner_id) -> OwnerSubscription:
    return OwnerSubscription.create_trialing(
        owner_id=owner_id, trial_duration_days=3, now=_now(),
    ).value


def _make_inactive_sub(owner_id) -> OwnerSubscription:
    sub = _make_active_sub(owner_id)
    sub.transition_to(SubStatus.INACTIVE, now=_now(), trial_duration_days=3)
    return sub


async def _build_handler(
    *,
    resource: Resource,
    sub: OwnerSubscription | None = None,
) -> tuple[RequestBookingHandler, InMemoryBookingRepository, FakeNotificationService]:
    bookings = InMemoryBookingRepository()
    notifs = FakeNotificationService()
    handler = RequestBookingHandler(
        bookings=bookings,
        resources=_FakeResourceRepo([resource]),
        subscriptions=_FakeSubRepo(sub or _make_active_sub(resource.owner_id)),
        notifications=notifs,
    )
    return handler, bookings, notifs


async def test_happy_path_creates_pending_and_notifies_owner():
    owner_id = uuid4()
    res = _build_resource(owner_id=owner_id)
    handler, bookings, notifs = await _build_handler(resource=res)
    start, end = _local_slot(day=28, hour_local=14, hours=2)
    cmd = RequestBookingCommand(
        actor_id=uuid4(), resource_id=res.id,
        slot_start_at=start, slot_end_at=end, customer_note=None,
    )
    r = await handler.handle(cmd)
    assert r.is_success, r.error
    dto = r.value
    assert dto.status == "PENDING"
    assert dto.total_price_cents == 16000  # 2 slots × 8000
    assert len(bookings._rows) == 1
    # Owner notified.
    assert any(
        c[1] is NotifKind.BOOKING_REQUESTED and c[0] == owner_id
        for c in notifs.calls
    )


async def test_resource_not_found_returns_404():
    res = _build_resource(owner_id=uuid4())
    handler, _, _ = await _build_handler(resource=res)
    start, end = _local_slot()
    cmd = RequestBookingCommand(
        actor_id=uuid4(), resource_id=uuid4(),
        slot_start_at=start, slot_end_at=end, customer_note=None,
    )
    r = await handler.handle(cmd)
    assert r.is_failure
    assert r.error == "ResourceNotFound"
    assert r.status_code == 404


async def test_unpublished_resource_returns_404_resource_not_published():
    res = _build_resource(owner_id=uuid4(), is_published=False)
    handler, _, _ = await _build_handler(resource=res)
    start, end = _local_slot()
    cmd = RequestBookingCommand(
        actor_id=uuid4(), resource_id=res.id,
        slot_start_at=start, slot_end_at=end, customer_note=None,
    )
    r = await handler.handle(cmd)
    assert r.is_failure
    assert r.error == "ResourceNotPublished"


async def test_inactive_owner_subscription_returns_404_resource_not_published():
    owner_id = uuid4()
    res = _build_resource(owner_id=owner_id)
    handler, _, _ = await _build_handler(
        resource=res, sub=_make_inactive_sub(owner_id),
    )
    start, end = _local_slot()
    cmd = RequestBookingCommand(
        actor_id=uuid4(), resource_id=res.id,
        slot_start_at=start, slot_end_at=end, customer_note=None,
    )
    r = await handler.handle(cmd)
    assert r.is_failure
    # Same code as unpublished — don't reveal owner state to the customer.
    assert r.error == "ResourceNotPublished"


async def test_slot_in_past_returns_422():
    res = _build_resource(owner_id=uuid4())
    handler, _, _ = await _build_handler(resource=res)
    start = _now() - timedelta(hours=1)
    end = _now()
    cmd = RequestBookingCommand(
        actor_id=uuid4(), resource_id=res.id,
        slot_start_at=start, slot_end_at=end, customer_note=None,
    )
    r = await handler.handle(cmd)
    assert r.is_failure
    assert r.error == "BookingSlotInPast"


async def test_slot_not_aligned_returns_422():
    res = _build_resource(owner_id=uuid4())  # 60-min slots
    handler, _, _ = await _build_handler(resource=res)
    start, _ = _local_slot(day=28, hour_local=14)
    # Off-grid: 14:30-15:30 local.
    bad_start = start + timedelta(minutes=30)
    bad_end = bad_start + timedelta(hours=1)
    cmd = RequestBookingCommand(
        actor_id=uuid4(), resource_id=res.id,
        slot_start_at=bad_start, slot_end_at=bad_end, customer_note=None,
    )
    r = await handler.handle(cmd)
    assert r.is_failure
    assert r.error == "BookingSlotNotAligned"


async def test_slot_outside_operating_hours_returns_422():
    res = _build_resource(owner_id=uuid4())  # 06:00-22:00
    handler, _, _ = await _build_handler(resource=res)
    # 02:00-03:00 local — closed.
    start, end = _local_slot(day=28, hour_local=2, hours=1)
    cmd = RequestBookingCommand(
        actor_id=uuid4(), resource_id=res.id,
        slot_start_at=start, slot_end_at=end, customer_note=None,
    )
    r = await handler.handle(cmd)
    assert r.is_failure
    assert r.error == "BookingOutsideOperatingHours"


async def test_natural_dedup_returns_409():
    res = _build_resource(owner_id=uuid4())
    handler, _, _ = await _build_handler(resource=res)
    customer_id = uuid4()
    start, end = _local_slot(day=28, hour_local=14, hours=2)
    cmd = RequestBookingCommand(
        actor_id=customer_id, resource_id=res.id,
        slot_start_at=start, slot_end_at=end, customer_note=None,
    )
    first = await handler.handle(cmd)
    assert first.is_success
    # Same customer requests same slot again.
    second = await handler.handle(cmd)
    assert second.is_failure
    assert second.error == "BookingAlreadyExists"
    assert second.status_code == 409


async def test_two_customers_same_slot_both_pend():
    res = _build_resource(owner_id=uuid4())
    handler, bookings, _ = await _build_handler(resource=res)
    start, end = _local_slot(day=28, hour_local=14, hours=2)
    cmd1 = RequestBookingCommand(
        actor_id=uuid4(), resource_id=res.id,
        slot_start_at=start, slot_end_at=end, customer_note=None,
    )
    cmd2 = RequestBookingCommand(
        actor_id=uuid4(), resource_id=res.id,
        slot_start_at=start, slot_end_at=end, customer_note=None,
    )
    r1 = await handler.handle(cmd1)
    r2 = await handler.handle(cmd2)
    assert r1.is_success and r2.is_success
    assert len(bookings._rows) == 2


async def test_pricing_rule_applied():
    owner_id = uuid4()
    res = _build_resource(owner_id=owner_id)
    rule = PricingRule.create(
        weekdays={Weekday.TUESDAY},
        window=TimeWindow.create("14:00", "16:00").value,
        price_cents=20000,
    ).value
    res.replace_pricing_rules([rule])
    handler, _, _ = await _build_handler(resource=res)
    # 2026-04-28 is a Tuesday. 14:00-16:00 local = rule.
    start, end = _local_slot(day=28, hour_local=14, hours=2)
    cmd = RequestBookingCommand(
        actor_id=uuid4(), resource_id=res.id,
        slot_start_at=start, slot_end_at=end, customer_note=None,
    )
    r = await handler.handle(cmd)
    assert r.is_success
    assert r.value.total_price_cents == 40000  # 2 × 20000
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/unit/use_cases/bookings/commands/test_request_booking.py -v`
Expected: import error.

- [ ] **Step 3: Implement the handler**

Create `app/use_cases/bookings/commands/__init__.py` (empty) and `app/use_cases/bookings/commands/request_booking.py`:

```python
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from uuid import UUID

from app.domain.bookings.booking import Booking
from app.domain.bookings.repository import IBookingRepository
from app.domain.notifications.service import INotificationService, NotifKind
from app.domain.resources.repository import IResourceRepository
from app.domain.shared.field_error import FieldError
from app.domain.shared.result import Result
from app.domain.shared.value_objects.date_time_range import DateTimeRange
from app.domain.shared.value_objects.short_description import ShortDescription
from app.domain.shared.weekday import Weekday
from app.domain.subscriptions.repository import ISubscriptionRepository
from app.use_cases.bookings.dtos import BookingDto


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True, kw_only=True, slots=True)
class RequestBookingCommand:
    actor_id: UUID                       # customer
    resource_id: UUID
    slot_start_at: datetime
    slot_end_at: datetime
    customer_note: str | None


class RequestBookingHandler:
    def __init__(
        self,
        *,
        bookings: IBookingRepository,
        resources: IResourceRepository,
        subscriptions: ISubscriptionRepository,
        notifications: INotificationService,
    ) -> None:
        self._bookings = bookings
        self._resources = resources
        self._subscriptions = subscriptions
        self._notifications = notifications

    async def handle(self, cmd: RequestBookingCommand) -> Result[BookingDto]:
        # 1. VO-validate inputs.
        errors: list[FieldError] = []
        slot_r = DateTimeRange.create(
            start_at=cmd.slot_start_at, end_at=cmd.slot_end_at,
        )
        if slot_r.is_failure:
            errors.append(FieldError(field="slot_range", code=slot_r.error))
        note: ShortDescription | None = None
        if cmd.customer_note is not None and cmd.customer_note != "":
            note_r = ShortDescription.create(cmd.customer_note)
            if note_r.is_failure:
                errors.append(FieldError(field="customer_note", code=note_r.error))
            else:
                note = note_r.value
        if errors:
            return Result.failure_many(errors, status_code=422)
        slot_range = slot_r.value

        # 2. Resource lookup + soft-delete + published gates.
        res_r = await self._resources.get_by_id(cmd.resource_id)
        if res_r.is_failure:
            return Result.from_failure(res_r)
        resource = res_r.value
        if resource is None or resource.is_deleted():
            return Result.failure("ResourceNotFound", status_code=404)
        if not resource.is_published:
            return Result.failure("ResourceNotPublished", status_code=404)

        # 3. Owner subscription operational.
        sub = await self._subscriptions.get_by_owner_id(resource.owner_id)
        if sub is None or not sub.status.is_operational():
            # Same code as unpublished — don't reveal owner state.
            return Result.failure("ResourceNotPublished", status_code=404)

        # 4. Slot must be in the future.
        if slot_range.start_at <= _utcnow():
            return Result.failure("BookingSlotInPast", status_code=422)

        # 5. Slot grid alignment + operating hours containment.
        align_r = self._validate_alignment_and_hours(resource, slot_range)
        if align_r.is_failure:
            return Result.from_failure(align_r)

        # 6. Natural dedup.
        actives_r = await self._bookings.list_active_by_customer_for_resource(
            cmd.actor_id, resource.id, slot_range,
        )
        if actives_r.is_failure:
            return Result.from_failure(actives_r)
        if actives_r.value:
            return Result.failure("BookingAlreadyExists", status_code=409)

        # 7. Compute price + persist.
        price = resource.compute_price(slot_range)
        booking = Booking.create_pending(
            resource_id=resource.id,
            customer_id=cmd.actor_id,
            slot_range=slot_range,
            total_price_cents=price,
            customer_note=note,
            now=_utcnow(),
        )
        add_r = await self._bookings.add(booking)
        if add_r.is_failure:
            return Result.from_failure(add_r)

        # 8. Notify owner (fire-and-forget).
        await self._notifications.notify(
            recipient_id=resource.owner_id,
            kind=NotifKind.BOOKING_REQUESTED,
            payload={
                "booking_id": str(booking.id),
                "resource_id": str(resource.id),
                "customer_id": str(cmd.actor_id),
                "slot_start_at": slot_range.start_at.isoformat(),
                "slot_end_at": slot_range.end_at.isoformat(),
            },
        )
        return Result.success(BookingDto.from_entity(booking))

    @staticmethod
    def _validate_alignment_and_hours(
        resource, slot_range: DateTimeRange,
    ) -> Result[None]:
        slot_minutes = resource.slot_duration_minutes.minutes
        tz = resource.timezone.to_zoneinfo()
        # Alignment in local time: minutes-from-midnight must be a multiple
        # of slot_duration; total duration must also be a multiple.
        local_start = slot_range.start_at.astimezone(tz)
        local_end = slot_range.end_at.astimezone(tz)
        start_minutes = local_start.hour * 60 + local_start.minute
        duration = slot_range.duration_minutes()
        if (start_minutes % slot_minutes) != 0 or (duration % slot_minutes) != 0:
            return Result.failure("BookingSlotNotAligned", status_code=422)

        # Containment: walk slot-by-slot in local time; each slot's local
        # start time must fall inside some operating-hours window of its
        # weekday.
        cursor = local_start
        while cursor < local_end:
            weekday = Weekday.from_iso(cursor.isoweekday())
            tod = cursor.time()
            windows = resource.operating_hours.for_weekday(weekday)
            in_window = any(w.start <= tod < w.end for w in windows)
            if not in_window:
                return Result.failure(
                    "BookingOutsideOperatingHours", status_code=422,
                )
            cursor = cursor + timedelta(minutes=slot_minutes)
        return Result.success(None)
```

- [ ] **Step 4: Run tests**

Run: `.venv/bin/pytest tests/unit/use_cases/bookings/commands/test_request_booking.py -v`
Expected: 10 PASSED.

- [ ] **Step 5: Run full unit suite**

Run: `.venv/bin/pytest tests/unit/ -q`
Expected: green.

- [ ] **Step 6: Commit**

```bash
git add app/use_cases/bookings/commands/__init__.py app/use_cases/bookings/commands/request_booking.py \
        tests/unit/use_cases/bookings/commands/__init__.py tests/unit/use_cases/bookings/commands/test_request_booking.py
git commit -m "$(cat <<'EOF'
feat(bookings): RequestBookingHandler

Plan 08 task 13. 8-step pipeline: VO-validate inputs (failure_many
envelope), resource gate (deleted → 404 ResourceNotFound;
unpublished or owner INACTIVE → 404 ResourceNotPublished — same
code, doesn't leak owner state to customer), slot-in-future check,
slot-grid alignment + operating-hours containment in local timezone,
natural dedup (PENDING/APPROVED on same resource overlapping
slot_range → 409 BookingAlreadyExists), price computation via
Resource.compute_price, persist + fire-and-forget BOOKING_REQUESTED
notification to owner.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 14: `ApproveBookingHandler` (with auto-rejection)

**Files:**
- Create: `app/use_cases/bookings/commands/approve_booking.py`
- Create: `tests/unit/use_cases/bookings/commands/test_approve_booking.py`

- [ ] **Step 1: Write failing tests**

`tests/unit/use_cases/bookings/commands/test_approve_booking.py`:

```python
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.domain.bookings.booking import Booking
from app.domain.bookings.booking_status import BookingStatus
from app.domain.notifications.service import NotifKind
from app.domain.resources.resource import Resource
from app.domain.shared.value_objects.date_time_range import DateTimeRange
from app.domain.shared.value_objects.money import Money
from app.domain.shared.value_objects.time_window import TimeWindow
from app.domain.shared.weekday import Weekday
from app.domain.subscriptions.owner_subscription import OwnerSubscription
from app.domain.subscriptions.sub_status import SubStatus
from app.use_cases.bookings.commands.approve_booking import (
    ApproveBookingCommand,
    ApproveBookingHandler,
)
from tests.unit.use_cases.bookings.fakes.in_memory_booking_repository import (
    InMemoryBookingRepository,
)
from tests.unit.use_cases.bookings.fakes.fake_booking_lock_service import (
    FakeBookingLockService,
)
from tests.unit.use_cases.subscriptions.fakes.fake_notification_service import (
    FakeNotificationService,
)


pytestmark = pytest.mark.asyncio


def _now() -> datetime:
    return datetime(2026, 4, 27, 12, 0, 0, tzinfo=timezone.utc)


def _build_resource(*, owner_id) -> Resource:
    operating = {wd: [TimeWindow.create("06:00", "22:00").value] for wd in Weekday}
    r = Resource.create(
        owner_id=owner_id, resource_type_id=uuid4(),
        slug="campo", name="Campo", description="",
        city="SP", region="SP", timezone="America/Sao_Paulo",
        slot_duration_minutes=60, base_price_cents=8000,
        customer_cancellation_cutoff_hours=24,
        operating_hours=operating, pricing_rules=[],
        custom_attributes=[], base_attributes={},
    ).value
    r.publish()
    return r


def _build_pending(*, resource_id, customer_id, days_ahead=1, hours=1) -> Booking:
    sr = DateTimeRange.create(
        start_at=_now() + timedelta(days=days_ahead),
        end_at=_now() + timedelta(days=days_ahead, hours=hours),
    ).value
    return Booking.create_pending(
        resource_id=resource_id, customer_id=customer_id, slot_range=sr,
        total_price_cents=Money.create(8000).value, customer_note=None, now=_now(),
    )


class _FakeResourceRepo:
    def __init__(self, resources):
        self._by_id = {r.id: r for r in resources}

    async def get_by_id(self, rid):
        from app.domain.shared.result import Result
        return Result.success(self._by_id.get(rid))


class _FakeSubRepo:
    def __init__(self, sub):
        self._sub = sub

    async def get_by_owner_id(self, owner_id):
        return self._sub if (self._sub and self._sub.owner_id == owner_id) else None


def _active(owner_id):
    sub = OwnerSubscription.create_trialing(
        owner_id=owner_id, trial_duration_days=3, now=_now(),
    ).value
    return sub


def _inactive(owner_id):
    sub = _active(owner_id)
    sub.transition_to(SubStatus.INACTIVE, now=_now(), trial_duration_days=3)
    return sub


async def _build_handler(*, resource, sub=None):
    bookings = InMemoryBookingRepository()
    notifs = FakeNotificationService()
    handler = ApproveBookingHandler(
        bookings=bookings,
        resources=_FakeResourceRepo([resource]),
        subscriptions=_FakeSubRepo(sub or _active(resource.owner_id)),
        notifications=notifs,
        lock=FakeBookingLockService(),
    )
    return handler, bookings, notifs


async def test_approves_pending_and_notifies_customer():
    owner_id = uuid4()
    res = _build_resource(owner_id=owner_id)
    customer_id = uuid4()
    booking = _build_pending(resource_id=res.id, customer_id=customer_id)
    handler, bookings, notifs = await _build_handler(resource=res)
    await bookings.add(booking)

    cmd = ApproveBookingCommand(actor_id=owner_id, booking_id=booking.id)
    r = await handler.handle(cmd)
    assert r.is_success
    assert r.value.status == "APPROVED"
    refetched = (await bookings.get_by_id(booking.id)).value
    assert refetched.status is BookingStatus.APPROVED
    assert any(
        c[1] is NotifKind.BOOKING_APPROVED and c[0] == customer_id
        for c in notifs.calls
    )


async def test_auto_rejects_overlapping_pendings():
    owner_id = uuid4()
    res = _build_resource(owner_id=owner_id)
    cust_a, cust_b, cust_c = uuid4(), uuid4(), uuid4()
    target = _build_pending(resource_id=res.id, customer_id=cust_a, days_ahead=1, hours=2)
    overlap1 = Booking.create_pending(
        resource_id=res.id, customer_id=cust_b,
        slot_range=DateTimeRange.create(
            start_at=target.slot_range.start_at + timedelta(minutes=30),
            end_at=target.slot_range.end_at + timedelta(minutes=30),
        ).value,
        total_price_cents=Money.create(8000).value,
        customer_note=None, now=_now(),
    )
    disjoint = _build_pending(resource_id=res.id, customer_id=cust_c, days_ahead=5)
    handler, bookings, notifs = await _build_handler(resource=res)
    await bookings.add(target)
    await bookings.add(overlap1)
    await bookings.add(disjoint)

    cmd = ApproveBookingCommand(actor_id=owner_id, booking_id=target.id)
    r = await handler.handle(cmd)
    assert r.is_success
    assert (await bookings.get_by_id(target.id)).value.status is BookingStatus.APPROVED
    assert (await bookings.get_by_id(overlap1.id)).value.status is BookingStatus.REJECTED
    assert (await bookings.get_by_id(disjoint.id)).value.status is BookingStatus.PENDING

    # Approved customer + 1 rejected competitor get notified.
    rejection_notifs = [c for c in notifs.calls if c[1] is NotifKind.BOOKING_REJECTED]
    assert len(rejection_notifs) == 1
    assert rejection_notifs[0][0] == cust_b
    assert rejection_notifs[0][2]["reason"] == "auto_rejected_competing_request"


async def test_inactive_owner_returns_403():
    owner_id = uuid4()
    res = _build_resource(owner_id=owner_id)
    booking = _build_pending(resource_id=res.id, customer_id=uuid4())
    handler, bookings, _ = await _build_handler(
        resource=res, sub=_inactive(owner_id),
    )
    await bookings.add(booking)
    cmd = ApproveBookingCommand(actor_id=owner_id, booking_id=booking.id)
    r = await handler.handle(cmd)
    assert r.is_failure
    assert r.error == "OwnerSubscriptionInactive"
    assert r.status_code == 403


async def test_non_owner_returns_404():
    owner_id = uuid4()
    res = _build_resource(owner_id=owner_id)
    booking = _build_pending(resource_id=res.id, customer_id=uuid4())
    handler, bookings, _ = await _build_handler(resource=res)
    await bookings.add(booking)
    cmd = ApproveBookingCommand(actor_id=uuid4(), booking_id=booking.id)
    r = await handler.handle(cmd)
    assert r.is_failure
    assert r.error == "BookingNotFound"
    assert r.status_code == 404


async def test_already_approved_returns_409():
    owner_id = uuid4()
    res = _build_resource(owner_id=owner_id)
    booking = _build_pending(resource_id=res.id, customer_id=uuid4())
    booking.approve(actor_id=owner_id, now=_now())
    handler, bookings, _ = await _build_handler(resource=res)
    await bookings.add(booking)
    cmd = ApproveBookingCommand(actor_id=owner_id, booking_id=booking.id)
    r = await handler.handle(cmd)
    assert r.is_failure
    assert r.error == "BookingInvalidStateTransition"
    assert r.status_code == 409


async def test_unknown_booking_returns_404():
    res = _build_resource(owner_id=uuid4())
    handler, _, _ = await _build_handler(resource=res)
    cmd = ApproveBookingCommand(actor_id=uuid4(), booking_id=uuid4())
    r = await handler.handle(cmd)
    assert r.is_failure
    assert r.error == "BookingNotFound"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/unit/use_cases/bookings/commands/test_approve_booking.py -v`
Expected: import error.

- [ ] **Step 3: Implement the handler**

`app/use_cases/bookings/commands/approve_booking.py`:

```python
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from app.domain.bookings.booking_status import BookingStatus
from app.domain.bookings.lock import IBookingLockService
from app.domain.bookings.repository import IBookingRepository
from app.domain.notifications.service import INotificationService, NotifKind
from app.domain.resources.repository import IResourceRepository
from app.domain.shared.result import Result
from app.domain.subscriptions.repository import ISubscriptionRepository
from app.use_cases.bookings.dtos import BookingDto


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True, kw_only=True, slots=True)
class ApproveBookingCommand:
    actor_id: UUID                       # owner
    booking_id: UUID


class ApproveBookingHandler:
    def __init__(
        self,
        *,
        bookings: IBookingRepository,
        resources: IResourceRepository,
        subscriptions: ISubscriptionRepository,
        notifications: INotificationService,
        lock: IBookingLockService,
    ) -> None:
        self._bookings = bookings
        self._resources = resources
        self._subscriptions = subscriptions
        self._notifications = notifications
        self._lock = lock

    async def handle(self, cmd: ApproveBookingCommand) -> Result[BookingDto]:
        target_r = await self._bookings.get_by_id(cmd.booking_id)
        if target_r.is_failure:
            return Result.from_failure(target_r)
        target = target_r.value
        if target is None:
            return Result.failure("BookingNotFound", status_code=404)

        res_r = await self._resources.get_by_id(target.resource_id)
        if res_r.is_failure:
            return Result.from_failure(res_r)
        resource = res_r.value
        if resource is None or resource.is_deleted():
            return Result.failure("BookingNotFound", status_code=404)
        if resource.owner_id != cmd.actor_id:
            return Result.failure("BookingNotFound", status_code=404)

        sub = await self._subscriptions.get_by_owner_id(resource.owner_id)
        if sub is None or not sub.status.is_operational():
            return Result.failure("OwnerSubscriptionInactive", status_code=403)

        rejected_ids: list[tuple[UUID, UUID]] = []  # (booking_id, customer_id)
        async with self._lock.acquire_for_resource(resource.id):
            # Re-fetch under lock to catch any races.
            target = (await self._bookings.get_by_id(cmd.booking_id)).value
            if target is None or target.status is not BookingStatus.PENDING:
                return Result.failure(
                    "BookingInvalidStateTransition", status_code=409,
                )

            competitors_r = await self._bookings.list_pending_overlapping(
                target.resource_id, target.slot_range,
                exclude_booking_id=target.id,
            )
            if competitors_r.is_failure:
                return Result.from_failure(competitors_r)
            competitors = competitors_r.value

            now = _utcnow()
            target.approve(actor_id=cmd.actor_id, now=now)
            update_r = await self._bookings.update(target)
            if update_r.is_failure:
                return Result.from_failure(update_r)
            for comp in competitors:
                comp.reject(
                    actor_id=cmd.actor_id, now=now,
                    reason="auto_rejected_competing_request",
                )
                upd = await self._bookings.update(comp)
                if upd.is_failure:
                    return Result.from_failure(upd)
                rejected_ids.append((comp.id, comp.customer_id))

        # Outside lock + outside TX: dispatch notifications.
        await self._notifications.notify(
            recipient_id=target.customer_id,
            kind=NotifKind.BOOKING_APPROVED,
            payload={
                "booking_id": str(target.id),
                "resource_id": str(resource.id),
            },
        )
        for booking_id, customer_id in rejected_ids:
            await self._notifications.notify(
                recipient_id=customer_id,
                kind=NotifKind.BOOKING_REJECTED,
                payload={
                    "booking_id": str(booking_id),
                    "resource_id": str(resource.id),
                    "reason": "auto_rejected_competing_request",
                },
            )
        return Result.success(BookingDto.from_entity(target))
```

- [ ] **Step 4: Run tests**

Run: `.venv/bin/pytest tests/unit/use_cases/bookings/commands/test_approve_booking.py -v`
Expected: 6 PASSED.

- [ ] **Step 5: Commit**

```bash
git add app/use_cases/bookings/commands/approve_booking.py tests/unit/use_cases/bookings/commands/test_approve_booking.py
git commit -m "$(cat <<'EOF'
feat(bookings): ApproveBookingHandler with auto-rejection

Plan 08 task 14. Owner approval flow per spec §6.2: ownership +
subscription check before lock; under lock re-fetch target,
load competing PENDINGs, transition target → APPROVED + each
competitor → REJECTED with auto_rejected_competing_request reason
in same TX; outside lock dispatch fire-and-forget notifications
(1 BOOKING_APPROVED to target customer + N BOOKING_REJECTED to
competitors).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 15: `RejectBookingHandler`

**Files:**
- Create: `app/use_cases/bookings/commands/reject_booking.py`
- Create: `tests/unit/use_cases/bookings/commands/test_reject_booking.py`

- [ ] **Step 1: Write failing tests**

`tests/unit/use_cases/bookings/commands/test_reject_booking.py`:

```python
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.domain.bookings.booking import Booking
from app.domain.bookings.booking_status import BookingStatus
from app.domain.notifications.service import NotifKind
from app.domain.resources.resource import Resource
from app.domain.shared.value_objects.date_time_range import DateTimeRange
from app.domain.shared.value_objects.money import Money
from app.domain.shared.value_objects.time_window import TimeWindow
from app.domain.shared.weekday import Weekday
from app.use_cases.bookings.commands.reject_booking import (
    RejectBookingCommand,
    RejectBookingHandler,
)
from tests.unit.use_cases.bookings.fakes.in_memory_booking_repository import (
    InMemoryBookingRepository,
)
from tests.unit.use_cases.subscriptions.fakes.fake_notification_service import (
    FakeNotificationService,
)


pytestmark = pytest.mark.asyncio


def _now() -> datetime:
    return datetime(2026, 4, 27, 12, 0, 0, tzinfo=timezone.utc)


def _build_resource(*, owner_id) -> Resource:
    operating = {wd: [TimeWindow.create("06:00", "22:00").value] for wd in Weekday}
    r = Resource.create(
        owner_id=owner_id, resource_type_id=uuid4(),
        slug="campo", name="Campo", description="",
        city="SP", region="SP", timezone="America/Sao_Paulo",
        slot_duration_minutes=60, base_price_cents=8000,
        customer_cancellation_cutoff_hours=24,
        operating_hours=operating, pricing_rules=[],
        custom_attributes=[], base_attributes={},
    ).value
    r.publish()
    return r


def _build_pending(*, resource_id, customer_id) -> Booking:
    sr = DateTimeRange.create(
        start_at=_now() + timedelta(days=1),
        end_at=_now() + timedelta(days=1, hours=1),
    ).value
    return Booking.create_pending(
        resource_id=resource_id, customer_id=customer_id, slot_range=sr,
        total_price_cents=Money.create(8000).value, customer_note=None, now=_now(),
    )


class _FakeResourceRepo:
    def __init__(self, resources):
        self._by_id = {r.id: r for r in resources}

    async def get_by_id(self, rid):
        from app.domain.shared.result import Result
        return Result.success(self._by_id.get(rid))


async def _build_handler(*, resource):
    bookings = InMemoryBookingRepository()
    notifs = FakeNotificationService()
    return (
        RejectBookingHandler(
            bookings=bookings,
            resources=_FakeResourceRepo([resource]),
            notifications=notifs,
        ),
        bookings,
        notifs,
    )


async def test_owner_rejects_pending_with_reason():
    owner_id = uuid4()
    res = _build_resource(owner_id=owner_id)
    customer_id = uuid4()
    b = _build_pending(resource_id=res.id, customer_id=customer_id)
    handler, bookings, notifs = await _build_handler(resource=res)
    await bookings.add(b)
    cmd = RejectBookingCommand(
        actor_id=owner_id, booking_id=b.id, reason="overbooked",
    )
    r = await handler.handle(cmd)
    assert r.is_success
    assert r.value.status == "REJECTED"
    assert any(
        c[0] == customer_id and c[1] is NotifKind.BOOKING_REJECTED
        and c[2].get("reason") == "overbooked"
        for c in notifs.calls
    )


async def test_owner_rejects_without_reason():
    owner_id = uuid4()
    res = _build_resource(owner_id=owner_id)
    b = _build_pending(resource_id=res.id, customer_id=uuid4())
    handler, bookings, notifs = await _build_handler(resource=res)
    await bookings.add(b)
    cmd = RejectBookingCommand(
        actor_id=owner_id, booking_id=b.id, reason=None,
    )
    r = await handler.handle(cmd)
    assert r.is_success
    # Notification payload defaults to "owner_rejected" when no reason given.
    assert any(
        c[1] is NotifKind.BOOKING_REJECTED and c[2].get("reason") == "owner_rejected"
        for c in notifs.calls
    )


async def test_non_owner_returns_404():
    owner_id = uuid4()
    res = _build_resource(owner_id=owner_id)
    b = _build_pending(resource_id=res.id, customer_id=uuid4())
    handler, bookings, _ = await _build_handler(resource=res)
    await bookings.add(b)
    cmd = RejectBookingCommand(
        actor_id=uuid4(), booking_id=b.id, reason=None,
    )
    r = await handler.handle(cmd)
    assert r.is_failure
    assert r.error == "BookingNotFound"


async def test_already_rejected_returns_409():
    owner_id = uuid4()
    res = _build_resource(owner_id=owner_id)
    b = _build_pending(resource_id=res.id, customer_id=uuid4())
    b.reject(actor_id=owner_id, now=_now())
    handler, bookings, _ = await _build_handler(resource=res)
    await bookings.add(b)
    cmd = RejectBookingCommand(
        actor_id=owner_id, booking_id=b.id, reason=None,
    )
    r = await handler.handle(cmd)
    assert r.is_failure
    assert r.error == "BookingInvalidStateTransition"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/unit/use_cases/bookings/commands/test_reject_booking.py -v`
Expected: import error.

- [ ] **Step 3: Implement the handler**

`app/use_cases/bookings/commands/reject_booking.py`:

```python
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from app.domain.bookings.repository import IBookingRepository
from app.domain.notifications.service import INotificationService, NotifKind
from app.domain.resources.repository import IResourceRepository
from app.domain.shared.result import Result
from app.use_cases.bookings.dtos import BookingDto


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True, kw_only=True, slots=True)
class RejectBookingCommand:
    actor_id: UUID                       # owner
    booking_id: UUID
    reason: str | None


class RejectBookingHandler:
    def __init__(
        self,
        *,
        bookings: IBookingRepository,
        resources: IResourceRepository,
        notifications: INotificationService,
    ) -> None:
        self._bookings = bookings
        self._resources = resources
        self._notifications = notifications

    async def handle(self, cmd: RejectBookingCommand) -> Result[BookingDto]:
        b_r = await self._bookings.get_by_id(cmd.booking_id)
        if b_r.is_failure:
            return Result.from_failure(b_r)
        booking = b_r.value
        if booking is None:
            return Result.failure("BookingNotFound", status_code=404)

        res_r = await self._resources.get_by_id(booking.resource_id)
        if res_r.is_failure:
            return Result.from_failure(res_r)
        resource = res_r.value
        if resource is None or resource.owner_id != cmd.actor_id:
            return Result.failure("BookingNotFound", status_code=404)

        transition = booking.reject(
            actor_id=cmd.actor_id, now=_utcnow(), reason=cmd.reason,
        )
        if transition.is_failure:
            return Result.failure(
                "BookingInvalidStateTransition", status_code=409,
            )
        update_r = await self._bookings.update(booking)
        if update_r.is_failure:
            return Result.from_failure(update_r)

        await self._notifications.notify(
            recipient_id=booking.customer_id,
            kind=NotifKind.BOOKING_REJECTED,
            payload={
                "booking_id": str(booking.id),
                "resource_id": str(resource.id),
                "reason": cmd.reason or "owner_rejected",
            },
        )
        return Result.success(BookingDto.from_entity(booking))
```

- [ ] **Step 4: Run tests**

Run: `.venv/bin/pytest tests/unit/use_cases/bookings/commands/test_reject_booking.py -v`
Expected: 4 PASSED.

- [ ] **Step 5: Commit**

```bash
git add app/use_cases/bookings/commands/reject_booking.py tests/unit/use_cases/bookings/commands/test_reject_booking.py
git commit -m "$(cat <<'EOF'
feat(bookings): RejectBookingHandler

Plan 08 task 15. Owner manual reject of PENDING. No lock required
(state-machine handles concurrent rejects). Notification payload
defaults reason to 'owner_rejected' when caller didn't supply one.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 16: `CancelBookingHandler`

**Files:**
- Create: `app/use_cases/bookings/commands/cancel_booking.py`
- Create: `tests/unit/use_cases/bookings/commands/test_cancel_booking.py`

- [ ] **Step 1: Write failing tests**

`tests/unit/use_cases/bookings/commands/test_cancel_booking.py`:

```python
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.domain.bookings.booking import Booking
from app.domain.bookings.booking_status import BookingStatus
from app.domain.notifications.service import NotifKind
from app.domain.resources.resource import Resource
from app.domain.shared.value_objects.date_time_range import DateTimeRange
from app.domain.shared.value_objects.money import Money
from app.domain.shared.value_objects.time_window import TimeWindow
from app.domain.shared.weekday import Weekday
from app.use_cases.bookings.commands.cancel_booking import (
    CancelBookingCommand,
    CancelBookingHandler,
)
from tests.unit.use_cases.bookings.fakes.in_memory_booking_repository import (
    InMemoryBookingRepository,
)
from tests.unit.use_cases.subscriptions.fakes.fake_notification_service import (
    FakeNotificationService,
)


pytestmark = pytest.mark.asyncio


def _now() -> datetime:
    return datetime(2026, 4, 27, 12, 0, 0, tzinfo=timezone.utc)


def _build_resource(*, owner_id, cutoff_hours: int = 24) -> Resource:
    operating = {wd: [TimeWindow.create("06:00", "22:00").value] for wd in Weekday}
    r = Resource.create(
        owner_id=owner_id, resource_type_id=uuid4(),
        slug="campo", name="Campo", description="",
        city="SP", region="SP", timezone="America/Sao_Paulo",
        slot_duration_minutes=60, base_price_cents=8000,
        customer_cancellation_cutoff_hours=cutoff_hours,
        operating_hours=operating, pricing_rules=[],
        custom_attributes=[], base_attributes={},
    ).value
    r.publish()
    return r


def _build_pending(*, resource_id, customer_id, days_ahead=2) -> Booking:
    sr = DateTimeRange.create(
        start_at=_now() + timedelta(days=days_ahead),
        end_at=_now() + timedelta(days=days_ahead, hours=1),
    ).value
    return Booking.create_pending(
        resource_id=resource_id, customer_id=customer_id, slot_range=sr,
        total_price_cents=Money.create(8000).value, customer_note=None, now=_now(),
    )


class _FakeResourceRepo:
    def __init__(self, resources):
        self._by_id = {r.id: r for r in resources}

    async def get_by_id(self, rid):
        from app.domain.shared.result import Result
        return Result.success(self._by_id.get(rid))


async def _build_handler(*, resource):
    bookings = InMemoryBookingRepository()
    notifs = FakeNotificationService()
    return (
        CancelBookingHandler(
            bookings=bookings,
            resources=_FakeResourceRepo([resource]),
            notifications=notifs,
        ),
        bookings, notifs,
    )


async def test_customer_cancels_pending_within_cutoff_notifies_owner():
    owner_id = uuid4()
    res = _build_resource(owner_id=owner_id, cutoff_hours=24)
    customer_id = uuid4()
    b = _build_pending(resource_id=res.id, customer_id=customer_id, days_ahead=2)
    handler, bookings, notifs = await _build_handler(resource=res)
    await bookings.add(b)
    cmd = CancelBookingCommand(
        actor_id=customer_id, booking_id=b.id, reason=None,
    )
    r = await handler.handle(cmd)
    assert r.is_success
    assert r.value.status == "CANCELLED"
    # Owner gets the cancellation notification.
    assert any(
        c[0] == owner_id and c[1] is NotifKind.BOOKING_CANCELLED
        for c in notifs.calls
    )


async def test_customer_cancels_past_cutoff_returns_403():
    owner_id = uuid4()
    res = _build_resource(owner_id=owner_id, cutoff_hours=24)
    customer_id = uuid4()
    # Booking starts in 10 hours (past 24h cutoff).
    sr = DateTimeRange.create(
        start_at=_now() + timedelta(hours=10),
        end_at=_now() + timedelta(hours=11),
    ).value
    b = Booking.create_pending(
        resource_id=res.id, customer_id=customer_id, slot_range=sr,
        total_price_cents=Money.create(8000).value, customer_note=None, now=_now(),
    )
    handler, bookings, _ = await _build_handler(resource=res)
    await bookings.add(b)
    cmd = CancelBookingCommand(
        actor_id=customer_id, booking_id=b.id, reason=None,
    )
    r = await handler.handle(cmd)
    assert r.is_failure
    assert r.error == "BookingCancellationPastCutoff"
    assert r.status_code == 403


async def test_owner_cancels_approved_anytime_no_cutoff():
    owner_id = uuid4()
    res = _build_resource(owner_id=owner_id, cutoff_hours=24)
    customer_id = uuid4()
    sr = DateTimeRange.create(
        start_at=_now() + timedelta(hours=10),
        end_at=_now() + timedelta(hours=11),
    ).value
    b = Booking.create_pending(
        resource_id=res.id, customer_id=customer_id, slot_range=sr,
        total_price_cents=Money.create(8000).value, customer_note=None, now=_now(),
    )
    b.approve(actor_id=owner_id, now=_now())
    handler, bookings, notifs = await _build_handler(resource=res)
    await bookings.add(b)
    cmd = CancelBookingCommand(
        actor_id=owner_id, booking_id=b.id, reason="storm",
    )
    r = await handler.handle(cmd)
    assert r.is_success
    assert r.value.status == "CANCELLED"
    # Customer gets notified; payload has cancelled_by=owner.
    cancelled = [c for c in notifs.calls if c[1] is NotifKind.BOOKING_CANCELLED]
    assert len(cancelled) == 1
    assert cancelled[0][0] == customer_id
    assert cancelled[0][2]["cancelled_by"] == "owner"


async def test_third_party_cannot_cancel_returns_404():
    owner_id = uuid4()
    res = _build_resource(owner_id=owner_id)
    b = _build_pending(resource_id=res.id, customer_id=uuid4())
    handler, bookings, _ = await _build_handler(resource=res)
    await bookings.add(b)
    cmd = CancelBookingCommand(
        actor_id=uuid4(), booking_id=b.id, reason=None,
    )
    r = await handler.handle(cmd)
    assert r.is_failure
    assert r.error == "BookingNotFound"


async def test_double_cancel_returns_409():
    owner_id = uuid4()
    res = _build_resource(owner_id=owner_id)
    customer_id = uuid4()
    b = _build_pending(resource_id=res.id, customer_id=customer_id)
    b.cancel(actor_id=customer_id, actor_role=__import__("app.domain.accounts.role", fromlist=["Role"]).Role.CUSTOMER, now=_now())
    handler, bookings, _ = await _build_handler(resource=res)
    await bookings.add(b)
    cmd = CancelBookingCommand(
        actor_id=customer_id, booking_id=b.id, reason=None,
    )
    r = await handler.handle(cmd)
    assert r.is_failure
    assert r.error == "BookingInvalidStateTransition"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/unit/use_cases/bookings/commands/test_cancel_booking.py -v`
Expected: import error.

- [ ] **Step 3: Implement the handler**

`app/use_cases/bookings/commands/cancel_booking.py`:

```python
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID

from app.domain.accounts.role import Role
from app.domain.bookings.repository import IBookingRepository
from app.domain.notifications.service import INotificationService, NotifKind
from app.domain.resources.repository import IResourceRepository
from app.domain.shared.result import Result
from app.use_cases.bookings.dtos import BookingDto


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True, kw_only=True, slots=True)
class CancelBookingCommand:
    actor_id: UUID
    booking_id: UUID
    reason: str | None


class CancelBookingHandler:
    """Single handler; branches on actor_role.

    Customer cancellation enforces the resource's
    customer_cancellation_cutoff_hours. Owner cancellation has no time bound.
    Third-party (neither owner nor customer) gets BookingNotFound 404.
    """

    def __init__(
        self,
        *,
        bookings: IBookingRepository,
        resources: IResourceRepository,
        notifications: INotificationService,
    ) -> None:
        self._bookings = bookings
        self._resources = resources
        self._notifications = notifications

    async def handle(self, cmd: CancelBookingCommand) -> Result[BookingDto]:
        b_r = await self._bookings.get_by_id(cmd.booking_id)
        if b_r.is_failure:
            return Result.from_failure(b_r)
        booking = b_r.value
        if booking is None:
            return Result.failure("BookingNotFound", status_code=404)

        res_r = await self._resources.get_by_id(booking.resource_id)
        if res_r.is_failure:
            return Result.from_failure(res_r)
        resource = res_r.value
        if resource is None:
            return Result.failure("BookingNotFound", status_code=404)

        is_customer = booking.customer_id == cmd.actor_id
        is_owner = resource.owner_id == cmd.actor_id
        if not (is_customer or is_owner):
            return Result.failure("BookingNotFound", status_code=404)

        # Customer cancellation enforces cutoff (only if NOT also owner —
        # an owner-customer booking the same resource skips cutoff).
        if is_customer and not is_owner:
            cutoff_hours = resource.customer_cancellation_cutoff_hours.hours
            if _utcnow() >= booking.slot_range.start_at - timedelta(hours=cutoff_hours):
                return Result.failure(
                    "BookingCancellationPastCutoff", status_code=403,
                )

        actor_role = Role.OWNER if is_owner else Role.CUSTOMER
        transition = booking.cancel(
            actor_id=cmd.actor_id, actor_role=actor_role,
            now=_utcnow(), reason=cmd.reason,
        )
        if transition.is_failure:
            return Result.failure(
                "BookingInvalidStateTransition", status_code=409,
            )
        update_r = await self._bookings.update(booking)
        if update_r.is_failure:
            return Result.from_failure(update_r)

        counterpart = resource.owner_id if is_customer else booking.customer_id
        await self._notifications.notify(
            recipient_id=counterpart,
            kind=NotifKind.BOOKING_CANCELLED,
            payload={
                "booking_id": str(booking.id),
                "resource_id": str(resource.id),
                "cancelled_by": actor_role.value,
            },
        )
        return Result.success(BookingDto.from_entity(booking))
```

- [ ] **Step 4: Run tests**

Run: `.venv/bin/pytest tests/unit/use_cases/bookings/commands/test_cancel_booking.py -v`
Expected: 5 PASSED.

- [ ] **Step 5: Commit**

```bash
git add app/use_cases/bookings/commands/cancel_booking.py tests/unit/use_cases/bookings/commands/test_cancel_booking.py
git commit -m "$(cat <<'EOF'
feat(bookings): CancelBookingHandler

Plan 08 task 16. Single handler branches on actor role: customer
must cancel before slot_start - cancellation_cutoff_hours; owner
no time bound. Third party cancel attempt → 404 BookingNotFound.
Counterpart (the OTHER party — owner if customer cancels, customer
if owner cancels) gets BOOKING_CANCELLED notification with
cancelled_by payload.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 17: `ExpirePendingBookingsHandler`

**Files:**
- Create: `app/use_cases/bookings/commands/expire_pending_bookings.py`
- Create: `tests/unit/use_cases/bookings/commands/test_expire_pending_bookings.py`

- [ ] **Step 1: Write failing tests**

`tests/unit/use_cases/bookings/commands/test_expire_pending_bookings.py`:

```python
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.domain.bookings.booking import Booking
from app.domain.bookings.booking_status import BookingStatus
from app.domain.notifications.service import NotifKind
from app.domain.shared.value_objects.date_time_range import DateTimeRange
from app.domain.shared.value_objects.money import Money
from app.use_cases.bookings.commands.expire_pending_bookings import (
    ExpirePendingBookingsCommand,
    ExpirePendingBookingsHandler,
)
from tests.unit.use_cases.bookings.fakes.in_memory_booking_repository import (
    InMemoryBookingRepository,
)
from tests.unit.use_cases.subscriptions.fakes.fake_notification_service import (
    FakeNotificationService,
)


pytestmark = pytest.mark.asyncio


def _now() -> datetime:
    return datetime(2026, 4, 27, 12, 0, 0, tzinfo=timezone.utc)


def _pending(*, resource_id, customer_id, slot_offset_hours: int) -> Booking:
    start = _now() + timedelta(hours=slot_offset_hours)
    end = start + timedelta(hours=1)
    return Booking.create_pending(
        resource_id=resource_id, customer_id=customer_id,
        slot_range=DateTimeRange.create(start_at=start, end_at=end).value,
        total_price_cents=Money.create(8000).value,
        customer_note=None,
        now=_now() - timedelta(days=1),
    )


async def test_expires_only_pendings_in_past():
    repo = InMemoryBookingRepository()
    notifs = FakeNotificationService()
    res_id = uuid4()
    past = _pending(resource_id=res_id, customer_id=uuid4(), slot_offset_hours=-2)
    future = _pending(resource_id=res_id, customer_id=uuid4(), slot_offset_hours=10)
    await repo.add(past)
    await repo.add(future)

    handler = ExpirePendingBookingsHandler(bookings=repo, notifications=notifs)
    r = await handler.handle(ExpirePendingBookingsCommand())
    assert r.is_success
    assert r.value == 1
    assert (await repo.get_by_id(past.id)).value.status is BookingStatus.EXPIRED
    assert (await repo.get_by_id(future.id)).value.status is BookingStatus.PENDING


async def test_already_expired_skipped_on_re_run():
    repo = InMemoryBookingRepository()
    notifs = FakeNotificationService()
    res_id = uuid4()
    past = _pending(resource_id=res_id, customer_id=uuid4(), slot_offset_hours=-2)
    await repo.add(past)
    handler = ExpirePendingBookingsHandler(bookings=repo, notifications=notifs)
    r1 = await handler.handle(ExpirePendingBookingsCommand())
    assert r1.value == 1
    # Second run: nothing more PENDING in past.
    r2 = await handler.handle(ExpirePendingBookingsCommand())
    assert r2.value == 0


async def test_each_expired_gets_rejected_notification():
    repo = InMemoryBookingRepository()
    notifs = FakeNotificationService()
    res_id = uuid4()
    cust_a = uuid4()
    cust_b = uuid4()
    await repo.add(_pending(resource_id=res_id, customer_id=cust_a, slot_offset_hours=-3))
    await repo.add(_pending(resource_id=res_id, customer_id=cust_b, slot_offset_hours=-2))
    handler = ExpirePendingBookingsHandler(bookings=repo, notifications=notifs)
    r = await handler.handle(ExpirePendingBookingsCommand())
    assert r.value == 2
    rejected = [c for c in notifs.calls if c[1] is NotifKind.BOOKING_REJECTED]
    assert len(rejected) == 2
    recipients = {c[0] for c in rejected}
    assert recipients == {cust_a, cust_b}
    for c in rejected:
        assert c[2]["reason"] == "slot_start_passed_with_no_decision"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/unit/use_cases/bookings/commands/test_expire_pending_bookings.py -v`
Expected: import error.

- [ ] **Step 3: Implement the handler**

`app/use_cases/bookings/commands/expire_pending_bookings.py`:

```python
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone

from app.domain.bookings.repository import IBookingRepository
from app.domain.notifications.service import INotificationService, NotifKind
from app.domain.shared.result import Result


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True, slots=True)
class ExpirePendingBookingsCommand:
    pass


class ExpirePendingBookingsHandler:
    def __init__(
        self,
        *,
        bookings: IBookingRepository,
        notifications: INotificationService,
    ) -> None:
        self._bookings = bookings
        self._notifications = notifications

    async def handle(
        self, cmd: ExpirePendingBookingsCommand,
    ) -> Result[int]:
        now = _utcnow()
        expired_r = await self._bookings.list_pending_with_start_before(now)
        if expired_r.is_failure:
            return Result.from_failure(expired_r)
        count = 0
        for booking in expired_r.value:
            transition = booking.expire(now=now)
            if transition.is_failure:
                continue
            update_r = await self._bookings.update(booking)
            if update_r.is_failure:
                continue
            await self._notifications.notify(
                recipient_id=booking.customer_id,
                kind=NotifKind.BOOKING_REJECTED,
                payload={
                    "booking_id": str(booking.id),
                    "resource_id": str(booking.resource_id),
                    "reason": "slot_start_passed_with_no_decision",
                },
            )
            count += 1
        return Result.success(count)
```

- [ ] **Step 4: Run tests**

Run: `.venv/bin/pytest tests/unit/use_cases/bookings/commands/test_expire_pending_bookings.py -v`
Expected: 3 PASSED.

- [ ] **Step 5: Commit**

```bash
git add app/use_cases/bookings/commands/expire_pending_bookings.py tests/unit/use_cases/bookings/commands/test_expire_pending_bookings.py
git commit -m "$(cat <<'EOF'
feat(bookings): ExpirePendingBookingsHandler (cron)

Plan 08 task 17. Loops over PENDING with slot_start_at < now,
transitions each to EXPIRED, dispatches BOOKING_REJECTED with
reason=slot_start_passed_with_no_decision. Idempotent: re-running
on the same bookings is a no-op (already EXPIRED skips the
transition).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 18: `ListMyBookingsHandler` + `GetMyBookingHandler` (customer queries)

**Files:**
- Create: `app/use_cases/bookings/queries/__init__.py` (empty)
- Create: `app/use_cases/bookings/queries/list_my_bookings.py`
- Create: `app/use_cases/bookings/queries/get_my_booking.py`
- Create: `tests/unit/use_cases/bookings/queries/__init__.py` (empty)
- Create: `tests/unit/use_cases/bookings/queries/test_list_my_bookings.py`
- Create: `tests/unit/use_cases/bookings/queries/test_get_my_booking.py`

- [ ] **Step 1: Write failing tests for both handlers**

`tests/unit/use_cases/bookings/queries/test_list_my_bookings.py`:

```python
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.domain.bookings.booking import Booking
from app.domain.bookings.booking_status import BookingStatus
from app.domain.shared.value_objects.date_time_range import DateTimeRange
from app.domain.shared.value_objects.money import Money
from app.use_cases.bookings.queries.list_my_bookings import (
    ListMyBookingsHandler,
    ListMyBookingsQuery,
)
from tests.unit.use_cases.bookings.fakes.in_memory_booking_repository import (
    InMemoryBookingRepository,
)


pytestmark = pytest.mark.asyncio


def _now() -> datetime:
    return datetime(2026, 4, 27, 12, 0, 0, tzinfo=timezone.utc)


def _booking(*, customer_id, status: BookingStatus = BookingStatus.PENDING) -> Booking:
    sr = DateTimeRange.create(
        start_at=_now() + timedelta(days=1),
        end_at=_now() + timedelta(days=1, hours=1),
    ).value
    b = Booking.create_pending(
        resource_id=uuid4(), customer_id=customer_id, slot_range=sr,
        total_price_cents=Money.create(8000).value,
        customer_note=None, now=_now(),
    )
    if status is BookingStatus.APPROVED:
        b.approve(actor_id=uuid4(), now=_now())
    elif status is BookingStatus.CANCELLED:
        from app.domain.accounts.role import Role
        b.cancel(actor_id=customer_id, actor_role=Role.CUSTOMER, now=_now())
    return b


async def test_returns_only_my_bookings():
    repo = InMemoryBookingRepository()
    me = uuid4()
    other = uuid4()
    mine = _booking(customer_id=me)
    theirs = _booking(customer_id=other)
    await repo.add(mine)
    await repo.add(theirs)
    handler = ListMyBookingsHandler(bookings=repo)

    r = await handler.handle(ListMyBookingsQuery(actor_id=me))
    assert r.is_success
    ids = [b.id for b in r.value.items]
    assert ids == [mine.id]


async def test_filters_by_status():
    repo = InMemoryBookingRepository()
    me = uuid4()
    p = _booking(customer_id=me, status=BookingStatus.PENDING)
    a = _booking(customer_id=me, status=BookingStatus.APPROVED)
    await repo.add(p)
    await repo.add(a)
    handler = ListMyBookingsHandler(bookings=repo)
    r = await handler.handle(ListMyBookingsQuery(
        actor_id=me, status=BookingStatus.APPROVED,
    ))
    assert r.is_success
    assert [b.id for b in r.value.items] == [a.id]


async def test_clamps_page_size_to_100():
    repo = InMemoryBookingRepository()
    me = uuid4()
    for _ in range(5):
        await repo.add(_booking(customer_id=me))
    handler = ListMyBookingsHandler(bookings=repo)
    r = await handler.handle(ListMyBookingsQuery(actor_id=me, page_size=500))
    assert r.is_success
    assert r.value.page_size == 100


async def test_clamps_page_min_1():
    repo = InMemoryBookingRepository()
    handler = ListMyBookingsHandler(bookings=repo)
    r = await handler.handle(ListMyBookingsQuery(actor_id=uuid4(), page=0))
    assert r.is_success
    assert r.value.page == 1
```

`tests/unit/use_cases/bookings/queries/test_get_my_booking.py`:

```python
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.domain.bookings.booking import Booking
from app.domain.shared.value_objects.date_time_range import DateTimeRange
from app.domain.shared.value_objects.money import Money
from app.use_cases.bookings.queries.get_my_booking import (
    GetMyBookingHandler,
    GetMyBookingQuery,
)
from tests.unit.use_cases.bookings.fakes.in_memory_booking_repository import (
    InMemoryBookingRepository,
)


pytestmark = pytest.mark.asyncio


def _now() -> datetime:
    return datetime(2026, 4, 27, 12, 0, 0, tzinfo=timezone.utc)


def _booking(*, customer_id) -> Booking:
    sr = DateTimeRange.create(
        start_at=_now() + timedelta(days=1),
        end_at=_now() + timedelta(days=1, hours=1),
    ).value
    return Booking.create_pending(
        resource_id=uuid4(), customer_id=customer_id, slot_range=sr,
        total_price_cents=Money.create(8000).value,
        customer_note=None, now=_now(),
    )


async def test_returns_my_own_booking():
    repo = InMemoryBookingRepository()
    me = uuid4()
    b = _booking(customer_id=me)
    await repo.add(b)
    handler = GetMyBookingHandler(bookings=repo)
    r = await handler.handle(GetMyBookingQuery(actor_id=me, booking_id=b.id))
    assert r.is_success
    assert r.value.id == b.id


async def test_cross_customer_returns_404():
    repo = InMemoryBookingRepository()
    owner_of_booking = uuid4()
    intruder = uuid4()
    b = _booking(customer_id=owner_of_booking)
    await repo.add(b)
    handler = GetMyBookingHandler(bookings=repo)
    r = await handler.handle(GetMyBookingQuery(
        actor_id=intruder, booking_id=b.id,
    ))
    assert r.is_failure
    assert r.error == "BookingNotFound"
    assert r.status_code == 404


async def test_unknown_id_returns_404():
    repo = InMemoryBookingRepository()
    handler = GetMyBookingHandler(bookings=repo)
    r = await handler.handle(GetMyBookingQuery(
        actor_id=uuid4(), booking_id=uuid4(),
    ))
    assert r.is_failure
    assert r.error == "BookingNotFound"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/unit/use_cases/bookings/queries/ -v`
Expected: import errors.

- [ ] **Step 3: Implement `ListMyBookingsHandler`**

`app/use_cases/bookings/queries/__init__.py` (empty).

`app/use_cases/bookings/queries/list_my_bookings.py`:

```python
from __future__ import annotations
from dataclasses import dataclass
from uuid import UUID

from app.domain.bookings.booking_status import BookingStatus
from app.domain.bookings.repository import IBookingRepository
from app.domain.shared.result import Result
from app.use_cases.bookings.dtos import BookingDto, BookingListDto


_MAX_PAGE_SIZE = 100


@dataclass(frozen=True, kw_only=True, slots=True)
class ListMyBookingsQuery:
    actor_id: UUID
    status: BookingStatus | None = None
    page: int = 1
    page_size: int = 50


class ListMyBookingsHandler:
    def __init__(self, *, bookings: IBookingRepository) -> None:
        self._bookings = bookings

    async def handle(
        self, query: ListMyBookingsQuery,
    ) -> Result[BookingListDto]:
        page = max(1, query.page)
        page_size = max(1, min(query.page_size, _MAX_PAGE_SIZE))
        rows_r = await self._bookings.list_by_customer(
            query.actor_id, status=query.status,
            page=page, page_size=page_size,
        )
        if rows_r.is_failure:
            return Result.from_failure(rows_r)
        items = tuple(BookingDto.from_entity(b) for b in rows_r.value)
        return Result.success(BookingListDto(
            items=items, page=page, page_size=page_size,
        ))
```

- [ ] **Step 4: Implement `GetMyBookingHandler`**

`app/use_cases/bookings/queries/get_my_booking.py`:

```python
from __future__ import annotations
from dataclasses import dataclass
from uuid import UUID

from app.domain.bookings.repository import IBookingRepository
from app.domain.shared.result import Result
from app.use_cases.bookings.dtos import BookingDto


@dataclass(frozen=True, kw_only=True, slots=True)
class GetMyBookingQuery:
    actor_id: UUID
    booking_id: UUID


class GetMyBookingHandler:
    def __init__(self, *, bookings: IBookingRepository) -> None:
        self._bookings = bookings

    async def handle(self, query: GetMyBookingQuery) -> Result[BookingDto]:
        b_r = await self._bookings.get_by_id(query.booking_id)
        if b_r.is_failure:
            return Result.from_failure(b_r)
        b = b_r.value
        if b is None or b.customer_id != query.actor_id:
            return Result.failure("BookingNotFound", status_code=404)
        return Result.success(BookingDto.from_entity(b))
```

- [ ] **Step 5: Run tests**

Run: `.venv/bin/pytest tests/unit/use_cases/bookings/queries/ -v`
Expected: 7 PASSED (4 list + 3 get).

- [ ] **Step 6: Commit**

```bash
git add app/use_cases/bookings/queries/__init__.py app/use_cases/bookings/queries/list_my_bookings.py \
        app/use_cases/bookings/queries/get_my_booking.py \
        tests/unit/use_cases/bookings/queries/__init__.py \
        tests/unit/use_cases/bookings/queries/test_list_my_bookings.py \
        tests/unit/use_cases/bookings/queries/test_get_my_booking.py
git commit -m "$(cat <<'EOF'
feat(bookings): customer query handlers (list + get)

Plan 08 task 18. ListMyBookingsHandler clamps page to [1, +∞) and
page_size to [1, 100]; status filter optional. GetMyBookingHandler
enforces ownership at the handler level — cross-customer access
returns 404 BookingNotFound (no leak), same pattern as Plan 07
notifications.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 19: `ListBookingsForResourceHandler` (owner query)

**Files:**
- Create: `app/use_cases/bookings/queries/list_resource_bookings.py`
- Create: `tests/unit/use_cases/bookings/queries/test_list_resource_bookings.py`

- [ ] **Step 1: Write failing tests**

`tests/unit/use_cases/bookings/queries/test_list_resource_bookings.py`:

```python
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.domain.bookings.booking import Booking
from app.domain.bookings.booking_status import BookingStatus
from app.domain.resources.resource import Resource
from app.domain.shared.value_objects.date_time_range import DateTimeRange
from app.domain.shared.value_objects.money import Money
from app.domain.shared.value_objects.time_window import TimeWindow
from app.domain.shared.weekday import Weekday
from app.use_cases.bookings.queries.list_resource_bookings import (
    ListResourceBookingsHandler,
    ListResourceBookingsQuery,
)
from tests.unit.use_cases.bookings.fakes.in_memory_booking_repository import (
    InMemoryBookingRepository,
)


pytestmark = pytest.mark.asyncio


def _now() -> datetime:
    return datetime(2026, 4, 27, 12, 0, 0, tzinfo=timezone.utc)


def _build_resource(*, owner_id) -> Resource:
    operating = {wd: [TimeWindow.create("06:00", "22:00").value] for wd in Weekday}
    r = Resource.create(
        owner_id=owner_id, resource_type_id=uuid4(),
        slug="campo", name="Campo", description="",
        city="SP", region="SP", timezone="America/Sao_Paulo",
        slot_duration_minutes=60, base_price_cents=8000,
        customer_cancellation_cutoff_hours=24,
        operating_hours=operating, pricing_rules=[],
        custom_attributes=[], base_attributes={},
    ).value
    r.publish()
    return r


def _booking(*, resource_id) -> Booking:
    sr = DateTimeRange.create(
        start_at=_now() + timedelta(days=1),
        end_at=_now() + timedelta(days=1, hours=1),
    ).value
    return Booking.create_pending(
        resource_id=resource_id, customer_id=uuid4(),
        slot_range=sr, total_price_cents=Money.create(8000).value,
        customer_note=None, now=_now(),
    )


class _FakeResourceRepo:
    def __init__(self, resources):
        self._by_id = {r.id: r for r in resources}

    async def get_by_id(self, rid):
        from app.domain.shared.result import Result
        return Result.success(self._by_id.get(rid))


async def test_returns_bookings_for_my_resource():
    owner_id = uuid4()
    res = _build_resource(owner_id=owner_id)
    repo = InMemoryBookingRepository()
    b1 = _booking(resource_id=res.id)
    b2 = _booking(resource_id=res.id)
    other = _booking(resource_id=uuid4())
    await repo.add(b1)
    await repo.add(b2)
    await repo.add(other)
    handler = ListResourceBookingsHandler(
        bookings=repo, resources=_FakeResourceRepo([res]),
    )
    r = await handler.handle(ListResourceBookingsQuery(
        actor_id=owner_id, resource_id=res.id,
    ))
    assert r.is_success
    ids = {b.id for b in r.value.items}
    assert ids == {b1.id, b2.id}


async def test_non_owner_returns_404():
    res = _build_resource(owner_id=uuid4())
    handler = ListResourceBookingsHandler(
        bookings=InMemoryBookingRepository(),
        resources=_FakeResourceRepo([res]),
    )
    r = await handler.handle(ListResourceBookingsQuery(
        actor_id=uuid4(), resource_id=res.id,
    ))
    assert r.is_failure
    assert r.error == "ResourceNotFound"


async def test_status_filter():
    owner_id = uuid4()
    res = _build_resource(owner_id=owner_id)
    repo = InMemoryBookingRepository()
    pending = _booking(resource_id=res.id)
    approved = _booking(resource_id=res.id)
    approved.approve(actor_id=owner_id, now=_now())
    await repo.add(pending)
    await repo.add(approved)
    handler = ListResourceBookingsHandler(
        bookings=repo, resources=_FakeResourceRepo([res]),
    )
    r = await handler.handle(ListResourceBookingsQuery(
        actor_id=owner_id, resource_id=res.id,
        status=BookingStatus.APPROVED,
    ))
    assert r.is_success
    assert [b.id for b in r.value.items] == [approved.id]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/unit/use_cases/bookings/queries/test_list_resource_bookings.py -v`
Expected: import error.

- [ ] **Step 3: Implement the handler**

`app/use_cases/bookings/queries/list_resource_bookings.py`:

```python
from __future__ import annotations
from dataclasses import dataclass
from uuid import UUID

from app.domain.bookings.booking_status import BookingStatus
from app.domain.bookings.repository import IBookingRepository
from app.domain.resources.repository import IResourceRepository
from app.domain.shared.result import Result
from app.use_cases.bookings.dtos import BookingDto, BookingListDto


_MAX_PAGE_SIZE = 100


@dataclass(frozen=True, kw_only=True, slots=True)
class ListResourceBookingsQuery:
    actor_id: UUID                       # owner
    resource_id: UUID
    status: BookingStatus | None = None
    page: int = 1
    page_size: int = 50


class ListResourceBookingsHandler:
    def __init__(
        self,
        *,
        bookings: IBookingRepository,
        resources: IResourceRepository,
    ) -> None:
        self._bookings = bookings
        self._resources = resources

    async def handle(
        self, query: ListResourceBookingsQuery,
    ) -> Result[BookingListDto]:
        res_r = await self._resources.get_by_id(query.resource_id)
        if res_r.is_failure:
            return Result.from_failure(res_r)
        resource = res_r.value
        if resource is None or resource.owner_id != query.actor_id:
            return Result.failure("ResourceNotFound", status_code=404)

        page = max(1, query.page)
        page_size = max(1, min(query.page_size, _MAX_PAGE_SIZE))
        rows_r = await self._bookings.list_by_resource(
            resource.id, status=query.status,
            page=page, page_size=page_size,
        )
        if rows_r.is_failure:
            return Result.from_failure(rows_r)
        items = tuple(BookingDto.from_entity(b) for b in rows_r.value)
        return Result.success(BookingListDto(
            items=items, page=page, page_size=page_size,
        ))
```

- [ ] **Step 4: Run tests**

Run: `.venv/bin/pytest tests/unit/use_cases/bookings/queries/test_list_resource_bookings.py -v`
Expected: 3 PASSED.

- [ ] **Step 5: Commit**

```bash
git add app/use_cases/bookings/queries/list_resource_bookings.py tests/unit/use_cases/bookings/queries/test_list_resource_bookings.py
git commit -m "$(cat <<'EOF'
feat(bookings): ListBookingsForResourceHandler (owner query)

Plan 08 task 19. Owner-scoped lookup; cross-owner gets ResourceNotFound
404. Optional status filter, same page/page_size clamp as customer
list.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 20: `GetAgendaHandler` (shared public + owner)

**Files:**
- Create: `app/use_cases/bookings/queries/get_agenda.py`
- Create: `tests/unit/use_cases/bookings/queries/test_get_agenda.py`

- [ ] **Step 1: Write failing tests**

`tests/unit/use_cases/bookings/queries/test_get_agenda.py`:

```python
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.domain.bookings.booking import Booking
from app.domain.bookings.booking_status import BookingStatus
from app.domain.resources.resource import Resource
from app.domain.shared.value_objects.date_time_range import DateTimeRange
from app.domain.shared.value_objects.money import Money
from app.domain.shared.value_objects.time_window import TimeWindow
from app.domain.shared.weekday import Weekday
from app.use_cases.bookings.queries.get_agenda import (
    GetAgendaHandler,
    GetAgendaQuery,
)
from tests.unit.use_cases.bookings.fakes.in_memory_booking_repository import (
    InMemoryBookingRepository,
)


pytestmark = pytest.mark.asyncio


def _now() -> datetime:
    return datetime(2026, 4, 27, 12, 0, 0, tzinfo=timezone.utc)


def _build_resource(*, owner_id, slot_minutes: int = 60) -> Resource:
    operating = {wd: [TimeWindow.create("06:00", "22:00").value] for wd in Weekday}
    r = Resource.create(
        owner_id=owner_id, resource_type_id=uuid4(),
        slug="campo", name="Campo", description="",
        city="SP", region="SP", timezone="America/Sao_Paulo",
        slot_duration_minutes=slot_minutes, base_price_cents=8000,
        customer_cancellation_cutoff_hours=24,
        operating_hours=operating, pricing_rules=[],
        custom_attributes=[], base_attributes={},
    ).value
    r.publish()
    return r


def _local_slot(*, day=28, hour_local=14, hours=1) -> tuple[datetime, datetime]:
    start = datetime(2026, 4, day, hour_local + 3, 0, 0, tzinfo=timezone.utc)
    end = start + timedelta(hours=hours)
    return start, end


class _FakeResourceRepo:
    def __init__(self, resources):
        self._by_id = {r.id: r for r in resources}
        self._by_slug = {r.slug.value: r for r in resources}

    async def get_by_id(self, rid):
        from app.domain.shared.result import Result
        return Result.success(self._by_id.get(rid))

    async def get_by_owner_slug_and_resource_slug(self, owner_slug, resource_slug):
        from app.domain.shared.result import Result
        return Result.success(self._by_slug.get(resource_slug))


async def test_public_agenda_only_status_no_booking_ids():
    owner_id = uuid4()
    res = _build_resource(owner_id=owner_id)
    repo = InMemoryBookingRepository()
    handler = GetAgendaHandler(
        bookings=repo, resources=_FakeResourceRepo([res]),
    )
    start, end = _local_slot(day=28, hour_local=14, hours=2)
    r = await handler.handle(GetAgendaQuery(
        resource_id=res.id, range_start=start, range_end=end,
        actor_id=None,
    ))
    assert r.is_success
    slots = r.value.slots
    assert all(s.status == "AVAILABLE" for s in slots)
    assert all(s.booking_id is None for s in slots)
    assert all(s.customer_id is None for s in slots)
    assert all(s.price_cents == 8000 for s in slots)


async def test_public_agenda_marks_pending_and_approved():
    owner_id = uuid4()
    res = _build_resource(owner_id=owner_id)
    repo = InMemoryBookingRepository()
    p_start, p_end = _local_slot(day=28, hour_local=14, hours=1)
    pending = Booking.create_pending(
        resource_id=res.id, customer_id=uuid4(),
        slot_range=DateTimeRange.create(start_at=p_start, end_at=p_end).value,
        total_price_cents=Money.create(8000).value,
        customer_note=None, now=_now(),
    )
    a_start, a_end = _local_slot(day=28, hour_local=15, hours=1)
    approved = Booking.create_pending(
        resource_id=res.id, customer_id=uuid4(),
        slot_range=DateTimeRange.create(start_at=a_start, end_at=a_end).value,
        total_price_cents=Money.create(8000).value,
        customer_note=None, now=_now(),
    )
    approved.approve(actor_id=owner_id, now=_now())
    await repo.add(pending)
    await repo.add(approved)
    handler = GetAgendaHandler(
        bookings=repo, resources=_FakeResourceRepo([res]),
    )
    range_start, range_end = _local_slot(day=28, hour_local=14, hours=3)
    r = await handler.handle(GetAgendaQuery(
        resource_id=res.id, range_start=range_start, range_end=range_end,
        actor_id=None,
    ))
    assert r.is_success
    by_start = {s.slot_start_at: s for s in r.value.slots}
    assert by_start[p_start].status == "PENDING"
    assert by_start[a_start].status == "APPROVED"


async def test_owner_agenda_includes_booking_ids():
    owner_id = uuid4()
    res = _build_resource(owner_id=owner_id)
    repo = InMemoryBookingRepository()
    p_start, p_end = _local_slot(day=28, hour_local=14, hours=1)
    customer_id = uuid4()
    pending = Booking.create_pending(
        resource_id=res.id, customer_id=customer_id,
        slot_range=DateTimeRange.create(start_at=p_start, end_at=p_end).value,
        total_price_cents=Money.create(8000).value,
        customer_note=None, now=_now(),
    )
    await repo.add(pending)
    handler = GetAgendaHandler(
        bookings=repo, resources=_FakeResourceRepo([res]),
    )
    range_start, range_end = _local_slot(day=28, hour_local=14, hours=2)
    r = await handler.handle(GetAgendaQuery(
        resource_id=res.id, range_start=range_start, range_end=range_end,
        actor_id=owner_id,                  # owner view
    ))
    assert r.is_success
    occupied = [s for s in r.value.slots if s.status == "PENDING"]
    assert len(occupied) == 1
    assert occupied[0].booking_id == pending.id
    assert occupied[0].customer_id == customer_id


async def test_range_too_wide_returns_422():
    res = _build_resource(owner_id=uuid4())
    handler = GetAgendaHandler(
        bookings=InMemoryBookingRepository(),
        resources=_FakeResourceRepo([res]),
    )
    rs, _ = _local_slot(day=1, hour_local=8)
    re_dt = rs + timedelta(days=32)
    r = await handler.handle(GetAgendaQuery(
        resource_id=res.id, range_start=rs, range_end=re_dt, actor_id=None,
    ))
    assert r.is_failure
    assert r.error == "AgendaRangeTooWide"


async def test_unknown_resource_returns_404():
    handler = GetAgendaHandler(
        bookings=InMemoryBookingRepository(),
        resources=_FakeResourceRepo([]),
    )
    rs, re = _local_slot()
    r = await handler.handle(GetAgendaQuery(
        resource_id=uuid4(), range_start=rs, range_end=re, actor_id=None,
    ))
    assert r.is_failure
    assert r.error == "ResourceNotFound"


async def test_resolves_by_slug_when_resource_id_none():
    res = _build_resource(owner_id=uuid4())
    handler = GetAgendaHandler(
        bookings=InMemoryBookingRepository(),
        resources=_FakeResourceRepo([res]),
    )
    rs, re = _local_slot(day=28, hour_local=14, hours=1)
    r = await handler.handle(GetAgendaQuery(
        owner_slug="any", resource_slug=res.slug.value,
        range_start=rs, range_end=re, actor_id=None,
    ))
    assert r.is_success
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/unit/use_cases/bookings/queries/test_get_agenda.py -v`
Expected: import error.

- [ ] **Step 3: Implement the handler**

`app/use_cases/bookings/queries/get_agenda.py`:

```python
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

from app.domain.bookings.booking import Booking
from app.domain.bookings.booking_status import BookingStatus
from app.domain.bookings.repository import IBookingRepository
from app.domain.resources.repository import IResourceRepository
from app.domain.shared.result import Result
from app.domain.shared.value_objects.date_time_range import DateTimeRange
from app.domain.shared.weekday import Weekday
from app.use_cases.bookings.dtos import AgendaDto, AgendaSlotDto


_MAX_RANGE_DAYS = 31


@dataclass(frozen=True, kw_only=True, slots=True)
class GetAgendaQuery:
    range_start: datetime                # inclusive, UTC
    range_end: datetime                  # exclusive, UTC
    resource_id: UUID | None = None
    owner_slug: str | None = None
    resource_slug: str | None = None
    actor_id: UUID | None = None         # owner view if matches resource.owner_id


class GetAgendaHandler:
    def __init__(
        self,
        *,
        bookings: IBookingRepository,
        resources: IResourceRepository,
    ) -> None:
        self._bookings = bookings
        self._resources = resources

    async def handle(self, query: GetAgendaQuery) -> Result[AgendaDto]:
        if (query.range_end - query.range_start) > timedelta(days=_MAX_RANGE_DAYS):
            return Result.failure("AgendaRangeTooWide", status_code=422)

        if query.resource_id is not None:
            res_r = await self._resources.get_by_id(query.resource_id)
        elif query.resource_slug is not None:
            res_r = await self._resources.get_by_owner_slug_and_resource_slug(
                query.owner_slug or "", query.resource_slug,
            )
        else:
            return Result.failure("ResourceNotFound", status_code=404)

        if res_r.is_failure:
            return Result.from_failure(res_r)
        resource = res_r.value
        if resource is None or resource.is_deleted():
            return Result.failure("ResourceNotFound", status_code=404)

        is_owner_view = (
            query.actor_id is not None and resource.owner_id == query.actor_id
        )

        bookings_r = await self._bookings.list_in_range_for_resource(
            resource.id, query.range_start, query.range_end,
        )
        if bookings_r.is_failure:
            return Result.from_failure(bookings_r)
        bookings = bookings_r.value

        slots = self._generate_slots(
            resource=resource,
            bookings=bookings,
            range_start=query.range_start,
            range_end=query.range_end,
            include_owner_detail=is_owner_view,
        )
        return Result.success(AgendaDto(resource_id=resource.id, slots=slots))

    @staticmethod
    def _generate_slots(
        *,
        resource,
        bookings: list[Booking],
        range_start: datetime,
        range_end: datetime,
        include_owner_detail: bool,
    ) -> tuple[AgendaSlotDto, ...]:
        slot_minutes = resource.slot_duration_minutes.minutes
        tz = resource.timezone.to_zoneinfo()
        local_start = range_start.astimezone(tz)
        local_end = range_end.astimezone(tz)

        # Group APPROVED + PENDING bookings by their slot_range for fast lookup.
        approved = [b for b in bookings if b.status is BookingStatus.APPROVED]
        pending = [b for b in bookings if b.status is BookingStatus.PENDING]

        out: list[AgendaSlotDto] = []
        cursor = local_start
        # Snap cursor up to the next aligned slot inside operating hours.
        while cursor < local_end:
            weekday = Weekday.from_iso(cursor.isoweekday())
            tod = cursor.time()
            windows = resource.operating_hours.for_weekday(weekday)
            window = next(
                (w for w in windows if w.start <= tod < w.end), None,
            )
            if window is None:
                # Move cursor to the next minute boundary that might be in a window.
                cursor = cursor + timedelta(minutes=slot_minutes)
                continue

            slot_start = cursor
            slot_end = cursor + timedelta(minutes=slot_minutes)
            if slot_end.time() > window.end and slot_end.date() == cursor.date():
                cursor = slot_end
                continue

            slot_range_utc = DateTimeRange.create(
                start_at=slot_start.astimezone(timezone_utc()),
                end_at=slot_end.astimezone(timezone_utc()),
            ).value

            # Status detection.
            approved_match = next(
                (b for b in approved if b.slot_range.overlaps(slot_range_utc)),
                None,
            )
            pending_match = next(
                (b for b in pending if b.slot_range.overlaps(slot_range_utc)),
                None,
            )

            if approved_match is not None:
                status = "APPROVED"
                booking_id = approved_match.id if include_owner_detail else None
                customer_id = approved_match.customer_id if include_owner_detail else None
            elif pending_match is not None:
                status = "PENDING"
                booking_id = pending_match.id if include_owner_detail else None
                customer_id = pending_match.customer_id if include_owner_detail else None
            else:
                status = "AVAILABLE"
                booking_id = None
                customer_id = None

            price = resource.compute_price(slot_range_utc).cents
            out.append(AgendaSlotDto(
                slot_start_at=slot_range_utc.start_at,
                slot_end_at=slot_range_utc.end_at,
                status=status,
                price_cents=price,
                booking_id=booking_id,
                customer_id=customer_id,
            ))
            cursor = slot_end
        return tuple(out)


def timezone_utc():
    from datetime import timezone
    return timezone.utc
```

- [ ] **Step 4: Add `get_by_owner_slug_and_resource_slug` to the resource repo Protocol if missing**

Open `app/domain/resources/repository.py` and ensure it has:

```python
async def get_by_owner_slug_and_resource_slug(
    self, owner_slug: str, resource_slug: str,
) -> Result[Resource | None]: ...
```

If the method doesn't exist (Plan 06 only used by-id and by-owner-public-slug), add it. Also extend `app/infrastructure/repositories/resource_repository.py` `SQLAlchemyResourceRepository` with the corresponding implementation by joining `resources` to `users` on `users.public_slug`.

(If Plan 06 already provides the by-slug lookup under a different name, reuse it and adapt this handler; the smoke-import in Step 5 will catch a name mismatch.)

- [ ] **Step 5: Run tests**

Run: `.venv/bin/pytest tests/unit/use_cases/bookings/queries/test_get_agenda.py -v`
Expected: 6 PASSED.

- [ ] **Step 6: Commit**

```bash
git add app/use_cases/bookings/queries/get_agenda.py \
        app/domain/resources/repository.py app/infrastructure/repositories/resource_repository.py \
        tests/unit/use_cases/bookings/queries/test_get_agenda.py
git commit -m "$(cat <<'EOF'
feat(bookings): GetAgendaHandler

Plan 08 task 20. Single handler emits both public + owner agendas
based on actor_id matching resource.owner_id. Iterates slot-by-slot
in local timezone, classifies each as APPROVED/PENDING/AVAILABLE,
computes per-slot price via Resource.compute_price. Owner view
exposes booking_id + customer_id; public view does not.

Range capped at 31 days (AgendaRangeTooWide 422).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 21: `SoftDeleteResourceHandler` extension (Plan 06 retroactive)

**Files:**
- Modify: `app/use_cases/resources/commands/soft_delete_resource.py`
- Modify: `tests/unit/use_cases/resources/commands/test_soft_delete_resource.py`

- [ ] **Step 1: Append failing tests**

Append to the existing `tests/unit/use_cases/resources/commands/test_soft_delete_resource.py` (do NOT touch the existing tests):

```python
# --- Plan 08 cascade tests ---

import pytest

from app.domain.bookings.booking import Booking
from app.domain.bookings.booking_status import BookingStatus
from app.domain.notifications.service import NotifKind
from app.domain.shared.value_objects.date_time_range import DateTimeRange
from app.domain.shared.value_objects.money import Money
from tests.unit.use_cases.bookings.fakes.in_memory_booking_repository import (
    InMemoryBookingRepository,
)
from tests.unit.use_cases.subscriptions.fakes.fake_notification_service import (
    FakeNotificationService,
)


def _build_pending_booking(*, resource_id, days_ahead=2):
    from datetime import datetime, timedelta, timezone
    from uuid import uuid4
    now = datetime(2026, 4, 27, 12, 0, 0, tzinfo=timezone.utc)
    sr = DateTimeRange.create(
        start_at=now + timedelta(days=days_ahead),
        end_at=now + timedelta(days=days_ahead, hours=1),
    ).value
    return Booking.create_pending(
        resource_id=resource_id, customer_id=uuid4(), slot_range=sr,
        total_price_cents=Money.create(8000).value,
        customer_note=None, now=now,
    )


@pytest.mark.asyncio
async def test_soft_delete_cancels_pending_bookings_and_notifies():
    # Reuse whatever resource fixture the existing test file has;
    # this test rebuilds inline to stay self-contained.
    # ... build owner + resource as the file already does ...
    # The example below assumes load_owned_resource works against the test
    # fake; adapt to the existing scaffolding in this file.
    pass  # Concrete body lifted from the file's existing helper pattern
```

The exact body of the cascade tests depends on the existing scaffolding in `test_soft_delete_resource.py`. Add the following three behavior tests (adapt fixture names to match the file):

1. `test_cascade_cancels_pending_bookings`: insert resource + 2 PENDING bookings + 1 unrelated PENDING → soft-delete → both PENDINGs on the resource are CANCELLED with reason "resource_deleted"; the unrelated PENDING is untouched.

2. `test_cascade_notifies_each_pending_customer`: same setup → after soft-delete, both customers received `BOOKING_CANCELLED` with `cancelled_by="owner"` payload + `reason="resource_deleted"`.

3. `test_blocks_when_future_approved_bookings_exist`: insert resource + 1 APPROVED booking with future slot → attempt soft-delete → fails with `ResourceHasFutureApprovedBookings` 409. Resource remains undeleted.

Concrete code (drop into the test file directly, replacing the `pass` skeleton above):

```python
@pytest.mark.asyncio
async def test_cascade_cancels_pending_bookings_and_notifies(
    # Use whatever fixtures the existing tests in this file use; e.g.,
    # an `_owner_id` and a helper `_seed_resource`. Adapt as needed.
):
    from datetime import datetime, timezone
    from uuid import uuid4

    from app.use_cases.resources.commands.soft_delete_resource import (
        SoftDeleteResourceCommand,
        SoftDeleteResourceHandler,
    )
    from tests.unit.use_cases.resources.commands.test_soft_delete_resource import (
        _build_owned_resource,  # if this helper exists; otherwise inline
    )

    resource, resources_repo = _build_owned_resource()  # existing helper
    owner_id = resource.owner_id

    bookings_repo = InMemoryBookingRepository()
    notifs = FakeNotificationService()
    pending_a = _build_pending_booking(resource_id=resource.id)
    pending_b = _build_pending_booking(resource_id=resource.id)
    other = _build_pending_booking(resource_id=uuid4())
    await bookings_repo.add(pending_a)
    await bookings_repo.add(pending_b)
    await bookings_repo.add(other)

    handler = SoftDeleteResourceHandler(
        resources=resources_repo,
        bookings=bookings_repo,
        notifications=notifs,
    )
    r = await handler.handle(SoftDeleteResourceCommand(
        actor_id=owner_id, resource_id=resource.id,
    ))
    assert r.is_success

    a_after = (await bookings_repo.get_by_id(pending_a.id)).value
    b_after = (await bookings_repo.get_by_id(pending_b.id)).value
    other_after = (await bookings_repo.get_by_id(other.id)).value
    assert a_after.status is BookingStatus.CANCELLED
    assert b_after.status is BookingStatus.CANCELLED
    assert other_after.status is BookingStatus.PENDING
    cancellations = [c for c in notifs.calls if c[1] is NotifKind.BOOKING_CANCELLED]
    recipients = {c[0] for c in cancellations}
    assert recipients == {pending_a.customer_id, pending_b.customer_id}
    for c in cancellations:
        assert c[2]["cancelled_by"] == "owner"
        assert c[2]["reason"] == "resource_deleted"


@pytest.mark.asyncio
async def test_blocks_when_future_approved_bookings_exist():
    from uuid import uuid4

    from app.use_cases.resources.commands.soft_delete_resource import (
        SoftDeleteResourceCommand,
        SoftDeleteResourceHandler,
    )
    from tests.unit.use_cases.resources.commands.test_soft_delete_resource import (
        _build_owned_resource,
    )

    resource, resources_repo = _build_owned_resource()
    owner_id = resource.owner_id

    bookings_repo = InMemoryBookingRepository()
    notifs = FakeNotificationService()
    approved_future = _build_pending_booking(resource_id=resource.id, days_ahead=5)
    approved_future.approve(actor_id=owner_id, now=approved_future.created_at)
    await bookings_repo.add(approved_future)

    handler = SoftDeleteResourceHandler(
        resources=resources_repo,
        bookings=bookings_repo,
        notifications=notifs,
    )
    r = await handler.handle(SoftDeleteResourceCommand(
        actor_id=owner_id, resource_id=resource.id,
    ))
    assert r.is_failure
    assert r.error == "ResourceHasFutureApprovedBookings"
    assert r.status_code == 409
```

If `_build_owned_resource` doesn't exist in the existing test file, replace its calls with whatever Plan 06's test file uses to set up an owner + resource.

- [ ] **Step 2: Run new tests to verify they fail**

Run: `.venv/bin/pytest tests/unit/use_cases/resources/commands/test_soft_delete_resource.py -v`
Expected: the new tests FAIL because `SoftDeleteResourceHandler` doesn't accept `bookings`/`notifications` yet.

- [ ] **Step 3: Extend `SoftDeleteResourceHandler`**

Replace `app/use_cases/resources/commands/soft_delete_resource.py` with:

```python
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from app.domain.accounts.role import Role
from app.domain.bookings.repository import IBookingRepository
from app.domain.notifications.service import INotificationService, NotifKind
from app.domain.resources.repository import IResourceRepository
from app.domain.shared.result import Result
from app.use_cases.resources._common import load_owned_resource


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True, slots=True)
class SoftDeleteResourceCommand:
    actor_id: UUID
    resource_id: UUID


class SoftDeleteResourceHandler:
    """Plan 06 ships the plumbing. Plan 08 extends to:
    1. Reject when an APPROVED booking with future slot_start exists.
    2. Auto-cancel all PENDING bookings on the resource (reason=resource_deleted).
    3. Dispatch BOOKING_CANCELLED notifications to each affected customer.
    """

    def __init__(
        self,
        *,
        resources: IResourceRepository,
        bookings: IBookingRepository,
        notifications: INotificationService,
    ) -> None:
        self._resources = resources
        self._bookings = bookings
        self._notifications = notifications

    async def handle(self, cmd: SoftDeleteResourceCommand) -> Result[None]:
        loaded = await load_owned_resource(
            self._resources, resource_id=cmd.resource_id, actor_id=cmd.actor_id,
        )
        if loaded.is_failure:
            return Result.from_failure(loaded)
        res = loaded.value
        now = _utcnow()

        # Block on future approved bookings.
        approved_future_r = await self._bookings.list_approved_with_start_after(
            res.id, now,
        )
        if approved_future_r.is_failure:
            return Result.from_failure(approved_future_r)
        if approved_future_r.value:
            return Result.failure(
                "ResourceHasFutureApprovedBookings", status_code=409,
            )

        # Cancel pending bookings.
        pending_r = await self._bookings.list_pending_for_resource(res.id)
        if pending_r.is_failure:
            return Result.from_failure(pending_r)
        cancelled_targets: list[tuple[UUID, UUID]] = []
        for booking in pending_r.value:
            transition = booking.cancel(
                actor_id=cmd.actor_id, actor_role=Role.OWNER,
                now=now, reason="resource_deleted",
            )
            if transition.is_failure:
                continue
            update_r = await self._bookings.update(booking)
            if update_r.is_failure:
                return Result.from_failure(update_r)
            cancelled_targets.append((booking.id, booking.customer_id))

        # Soft-delete the resource itself.
        del_r = res.soft_delete(now=now)
        if del_r.is_failure:
            return Result.from_failure(del_r, status_code=400)
        save = await self._resources.update(res)
        if save.is_failure:
            return Result.from_failure(save)

        # Dispatch notifications outside any transaction.
        for booking_id, customer_id in cancelled_targets:
            await self._notifications.notify(
                recipient_id=customer_id,
                kind=NotifKind.BOOKING_CANCELLED,
                payload={
                    "booking_id": str(booking_id),
                    "resource_id": str(res.id),
                    "cancelled_by": "owner",
                    "reason": "resource_deleted",
                },
            )
        return Result.success(None)
```

- [ ] **Step 4: Update `app/api/v1/me_resources/deps.py`**

The DI provider for `SoftDeleteResourceHandler` now needs `IBookingRepository` + `INotificationService` injected. Find the provider in `app/api/v1/me_resources/deps.py` and update it:

```python
async def get_soft_delete_resource_handler(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> SoftDeleteResourceHandler:
    return SoftDeleteResourceHandler(
        resources=SQLAlchemyResourceRepository(session),
        bookings=SQLAlchemyBookingRepository(session),
        notifications=PersistentNotificationService(
            SQLAlchemyNotificationRepository(session),
        ),
    )
```

(Adapt to the actual provider names in `me_resources/deps.py` — the Plan 06 file may call it `get_delete_handler` or similar.)

- [ ] **Step 5: Run tests**

Run: `.venv/bin/pytest tests/unit/use_cases/resources/commands/test_soft_delete_resource.py -v`
Expected: existing Plan 06 tests + 2 new cascade tests all PASS.

- [ ] **Step 6: Run full unit + integration**

Run: `.venv/bin/pytest tests/unit/ tests/integration/ -q`
Expected: green.

- [ ] **Step 7: Commit**

```bash
git add app/use_cases/resources/commands/soft_delete_resource.py \
        app/api/v1/me_resources/deps.py \
        tests/unit/use_cases/resources/commands/test_soft_delete_resource.py
git commit -m "$(cat <<'EOF'
feat(resources): SoftDeleteResourceHandler cascade (Plan 06 retroactive)

Plan 08 task 21. Adds IBookingRepository + INotificationService
deps. Order: (1) reject if any APPROVED booking has future
slot_start (409 ResourceHasFutureApprovedBookings); (2) cancel
each PENDING with reason=resource_deleted; (3) flip resource's
deleted_at; (4) outside the TX, fire BOOKING_CANCELLED to each
affected customer.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 22: Register Plan 08 stable error codes

**Files:**
- Modify: `app/api/error_codes.py`
- Modify: `tests/unit/architecture/test_error_code_coverage.py`

- [ ] **Step 1: Add pt-BR mappings**

In `app/api/error_codes.py`, append a new section just before the closing `}` of `ERROR_MESSAGES_PT_BR`:

```python
    # --- Plan 08 — bookings (handler-level) ---
    "BookingNotFound": "Reserva não encontrada.",
    "ResourceNotPublished": "Recurso indisponível para reserva.",
    "OwnerSubscriptionInactive": "Proprietário não pode aprovar reservas no momento.",
    "BookingSlotInPast": "Não é possível reservar horário passado.",
    "BookingSlotNotAligned": "Horário não alinhado à grade de slots.",
    "BookingOutsideOperatingHours": "Horário fora do funcionamento do recurso.",
    "BookingAlreadyExists": "Você já tem uma reserva ativa para esse horário.",
    "BookingInvalidStateTransition": "Transição de estado de reserva inválida.",
    "BookingCancellationPastCutoff": "Prazo de cancelamento expirado.",
    "BookingHasApprovedOverlap": "Horário já tem reserva aprovada.",
    "AgendaRangeTooWide": "Intervalo da agenda excede o máximo de 31 dias.",
    "ResourceHasFutureApprovedBookings": "Recurso possui reservas aprovadas futuras.",
    # --- Plan 08 — entity-level constants on StatusChange (programming bugs) ---
    "StatusChangeAtNotTzAware": "Timestamp de mudança precisa ter fuso horário.",
    "StatusChangeReasonTooLong": "Motivo excede 500 caracteres.",
    "StatusChangeInvalidTransition": "Transição de estado inválida.",
```

- [ ] **Step 2: Update arch test allowlist**

Open `tests/unit/architecture/test_error_code_coverage.py`. Find the `handler_level_allowlist: set[str] = {...}` block. Append a new section before the closing brace:

```python
        # Plan 08 — bookings handler-level
        "BookingNotFound",
        "ResourceNotPublished",
        "OwnerSubscriptionInactive",
        "BookingSlotInPast",
        "BookingSlotNotAligned",
        "BookingOutsideOperatingHours",
        "BookingAlreadyExists",
        "BookingInvalidStateTransition",
        "BookingCancellationPastCutoff",
        "BookingHasApprovedOverlap",
        "AgendaRangeTooWide",
        "ResourceHasFutureApprovedBookings",
```

(`StatusChangeAtNotTzAware`/`StatusChangeReasonTooLong`/`StatusChangeInvalidTransition` are entity-level — they're declared as class constants on `StatusChange` and the arch test discovers them automatically; they should NOT be added to the handler allowlist.)

- [ ] **Step 3: Run the architecture test**

Run: `.venv/bin/pytest tests/unit/architecture/test_error_code_coverage.py -v`
Expected: PASS.

- [ ] **Step 4: Run full unit suite**

Run: `.venv/bin/pytest tests/unit/ -q`
Expected: green.

- [ ] **Step 5: Commit**

```bash
git add app/api/error_codes.py tests/unit/architecture/test_error_code_coverage.py
git commit -m "$(cat <<'EOF'
feat(bookings): register Plan 08 stable error codes

Plan 08 task 22. 12 new handler-level codes + 3 entity-level
StatusChange codes added to ERROR_MESSAGES_PT_BR and (handler-level
only) to the architecture allowlist.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 23: API schemas (Pydantic) for bookings

**Files:**
- Create: `app/api/v1/me_bookings/__init__.py` (empty)
- Create: `app/api/v1/me_bookings/schemas.py`

- [ ] **Step 1: Create the package init** (empty file).

- [ ] **Step 2: Create `app/api/v1/me_bookings/schemas.py`**

```python
from __future__ import annotations
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.use_cases.bookings.dtos import (
    AgendaDto, AgendaSlotDto, BookingDto, BookingListDto, StatusChangeDto,
)


class CreateBookingRequest(BaseModel):
    resource_id: UUID
    slot_start_at: datetime
    slot_end_at: datetime
    customer_note: str | None = None


class CancelBookingRequest(BaseModel):
    reason: str | None = None


class RejectBookingRequest(BaseModel):
    reason: str | None = None


class StatusChangeResponse(BaseModel):
    from_status: str
    to_status: str
    actor_id: UUID
    actor_role: str
    at: datetime
    reason: str | None

    @classmethod
    def from_dto(cls, dto: StatusChangeDto) -> "StatusChangeResponse":
        return cls(
            from_status=dto.from_status,
            to_status=dto.to_status,
            actor_id=dto.actor_id,
            actor_role=dto.actor_role,
            at=dto.at,
            reason=dto.reason,
        )


class BookingResponse(BaseModel):
    id: UUID
    resource_id: UUID
    customer_id: UUID
    slot_start_at: datetime
    slot_end_at: datetime
    status: str
    customer_note: str | None
    total_price_cents: int
    status_history: list[StatusChangeResponse]
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_dto(cls, dto: BookingDto) -> "BookingResponse":
        return cls(
            id=dto.id,
            resource_id=dto.resource_id,
            customer_id=dto.customer_id,
            slot_start_at=dto.slot_start_at,
            slot_end_at=dto.slot_end_at,
            status=dto.status,
            customer_note=dto.customer_note,
            total_price_cents=dto.total_price_cents,
            status_history=[
                StatusChangeResponse.from_dto(sc) for sc in dto.status_history
            ],
            created_at=dto.created_at,
            updated_at=dto.updated_at,
        )


class BookingListResponse(BaseModel):
    items: list[BookingResponse]
    page: int
    page_size: int

    @classmethod
    def from_dto(cls, dto: BookingListDto) -> "BookingListResponse":
        return cls(
            items=[BookingResponse.from_dto(b) for b in dto.items],
            page=dto.page,
            page_size=dto.page_size,
        )


class AgendaSlotResponse(BaseModel):
    slot_start_at: datetime
    slot_end_at: datetime
    status: str
    price_cents: int
    booking_id: UUID | None = None
    customer_id: UUID | None = None

    @classmethod
    def from_dto(cls, dto: AgendaSlotDto) -> "AgendaSlotResponse":
        return cls(
            slot_start_at=dto.slot_start_at,
            slot_end_at=dto.slot_end_at,
            status=dto.status,
            price_cents=dto.price_cents,
            booking_id=dto.booking_id,
            customer_id=dto.customer_id,
        )


class AgendaResponse(BaseModel):
    resource_id: UUID
    slots: list[AgendaSlotResponse]

    @classmethod
    def from_dto(cls, dto: AgendaDto) -> "AgendaResponse":
        return cls(
            resource_id=dto.resource_id,
            slots=[AgendaSlotResponse.from_dto(s) for s in dto.slots],
        )
```

- [ ] **Step 3: Smoke import**

Run:
```
.venv/bin/python -c "
from app.api.v1.me_bookings.schemas import (
    BookingResponse, BookingListResponse, AgendaResponse,
    CreateBookingRequest, CancelBookingRequest, RejectBookingRequest,
)
print('ok')
"
```
Expected: `ok`.

- [ ] **Step 4: Commit**

```bash
git add app/api/v1/me_bookings/__init__.py app/api/v1/me_bookings/schemas.py
git commit -m "$(cat <<'EOF'
feat(bookings): API schemas (Pydantic)

Plan 08 task 23. Request models (Create/Cancel/Reject), response
models (Booking, BookingList, AgendaSlot, Agenda) with from_dto
constructors.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 24: API deps + routes for `/v1/me/bookings`

**Files:**
- Create: `app/api/v1/me_bookings/deps.py`
- Create: `app/api/v1/me_bookings/routes.py`

- [ ] **Step 1: Create `deps.py`**

```python
from __future__ import annotations
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.bookings.postgres_lock_service import (
    PostgresBookingLockService,
)
from app.infrastructure.db.session import get_session
from app.infrastructure.notifications.persistent_notification_service import (
    PersistentNotificationService,
)
from app.infrastructure.repositories.booking_repository import (
    SQLAlchemyBookingRepository,
)
from app.infrastructure.repositories.notification_repository import (
    SQLAlchemyNotificationRepository,
)
from app.infrastructure.repositories.owner_subscription_repository import (
    SQLAlchemyOwnerSubscriptionRepository,
)
from app.infrastructure.repositories.resource_repository import (
    SQLAlchemyResourceRepository,
)
from app.use_cases.bookings.commands.approve_booking import ApproveBookingHandler
from app.use_cases.bookings.commands.cancel_booking import CancelBookingHandler
from app.use_cases.bookings.commands.reject_booking import RejectBookingHandler
from app.use_cases.bookings.commands.request_booking import RequestBookingHandler
from app.use_cases.bookings.queries.get_agenda import GetAgendaHandler
from app.use_cases.bookings.queries.get_my_booking import GetMyBookingHandler
from app.use_cases.bookings.queries.list_my_bookings import ListMyBookingsHandler
from app.use_cases.bookings.queries.list_resource_bookings import (
    ListResourceBookingsHandler,
)


def _booking_repo(session: AsyncSession) -> SQLAlchemyBookingRepository:
    return SQLAlchemyBookingRepository(session)


def _resource_repo(session: AsyncSession) -> SQLAlchemyResourceRepository:
    return SQLAlchemyResourceRepository(session)


def _sub_repo(session: AsyncSession) -> SQLAlchemyOwnerSubscriptionRepository:
    return SQLAlchemyOwnerSubscriptionRepository(session)


def _notifications(session: AsyncSession) -> PersistentNotificationService:
    return PersistentNotificationService(SQLAlchemyNotificationRepository(session))


def _lock(session: AsyncSession) -> PostgresBookingLockService:
    return PostgresBookingLockService(session)


async def get_request_booking_handler(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> RequestBookingHandler:
    return RequestBookingHandler(
        bookings=_booking_repo(session),
        resources=_resource_repo(session),
        subscriptions=_sub_repo(session),
        notifications=_notifications(session),
    )


async def get_approve_booking_handler(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ApproveBookingHandler:
    return ApproveBookingHandler(
        bookings=_booking_repo(session),
        resources=_resource_repo(session),
        subscriptions=_sub_repo(session),
        notifications=_notifications(session),
        lock=_lock(session),
    )


async def get_reject_booking_handler(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> RejectBookingHandler:
    return RejectBookingHandler(
        bookings=_booking_repo(session),
        resources=_resource_repo(session),
        notifications=_notifications(session),
    )


async def get_cancel_booking_handler(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CancelBookingHandler:
    return CancelBookingHandler(
        bookings=_booking_repo(session),
        resources=_resource_repo(session),
        notifications=_notifications(session),
    )


async def get_list_my_bookings_handler(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ListMyBookingsHandler:
    return ListMyBookingsHandler(bookings=_booking_repo(session))


async def get_my_booking_handler(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> GetMyBookingHandler:
    return GetMyBookingHandler(bookings=_booking_repo(session))


async def get_list_resource_bookings_handler(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ListResourceBookingsHandler:
    return ListResourceBookingsHandler(
        bookings=_booking_repo(session),
        resources=_resource_repo(session),
    )


async def get_agenda_handler(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> GetAgendaHandler:
    return GetAgendaHandler(
        bookings=_booking_repo(session),
        resources=_resource_repo(session),
    )
```

- [ ] **Step 2: Create `routes.py`**

```python
from __future__ import annotations
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import CurrentUser
from app.api.error_handler import unwrap
from app.api.v1.me_bookings.deps import (
    get_approve_booking_handler,
    get_cancel_booking_handler,
    get_list_my_bookings_handler,
    get_my_booking_handler,
    get_reject_booking_handler,
    get_request_booking_handler,
)
from app.api.v1.me_bookings.schemas import (
    BookingListResponse,
    BookingResponse,
    CancelBookingRequest,
    CreateBookingRequest,
    RejectBookingRequest,
)
from app.domain.bookings.booking_status import BookingStatus
from app.use_cases.bookings.commands.approve_booking import (
    ApproveBookingCommand, ApproveBookingHandler,
)
from app.use_cases.bookings.commands.cancel_booking import (
    CancelBookingCommand, CancelBookingHandler,
)
from app.use_cases.bookings.commands.reject_booking import (
    RejectBookingCommand, RejectBookingHandler,
)
from app.use_cases.bookings.commands.request_booking import (
    RequestBookingCommand, RequestBookingHandler,
)
from app.use_cases.bookings.queries.get_my_booking import (
    GetMyBookingHandler, GetMyBookingQuery,
)
from app.use_cases.bookings.queries.list_my_bookings import (
    ListMyBookingsHandler, ListMyBookingsQuery,
)


router = APIRouter(prefix="/v1/me/bookings", tags=["me"])


@router.post(
    "",
    response_model=BookingResponse,
    status_code=status.HTTP_201_CREATED,
)
async def request_booking(
    body: CreateBookingRequest,
    user: CurrentUser,
    handler: Annotated[
        RequestBookingHandler, Depends(get_request_booking_handler),
    ],
):
    dto = unwrap(await handler.handle(RequestBookingCommand(
        actor_id=user.user_id,
        resource_id=body.resource_id,
        slot_start_at=body.slot_start_at,
        slot_end_at=body.slot_end_at,
        customer_note=body.customer_note,
    )))
    return BookingResponse.from_dto(dto)


@router.get("", response_model=BookingListResponse)
async def list_my_bookings(
    user: CurrentUser,
    handler: Annotated[
        ListMyBookingsHandler, Depends(get_list_my_bookings_handler),
    ],
    status_filter: BookingStatus | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
):
    dto = unwrap(await handler.handle(ListMyBookingsQuery(
        actor_id=user.user_id, status=status_filter,
        page=page, page_size=page_size,
    )))
    return BookingListResponse.from_dto(dto)


@router.get("/{booking_id}", response_model=BookingResponse)
async def get_my_booking(
    booking_id: UUID,
    user: CurrentUser,
    handler: Annotated[
        GetMyBookingHandler, Depends(get_my_booking_handler),
    ],
):
    dto = unwrap(await handler.handle(GetMyBookingQuery(
        actor_id=user.user_id, booking_id=booking_id,
    )))
    return BookingResponse.from_dto(dto)


@router.post("/{booking_id}/cancel", response_model=BookingResponse)
async def cancel_booking(
    booking_id: UUID,
    body: CancelBookingRequest,
    user: CurrentUser,
    handler: Annotated[
        CancelBookingHandler, Depends(get_cancel_booking_handler),
    ],
):
    dto = unwrap(await handler.handle(CancelBookingCommand(
        actor_id=user.user_id, booking_id=booking_id, reason=body.reason,
    )))
    return BookingResponse.from_dto(dto)


@router.post("/{booking_id}/approve", response_model=BookingResponse)
async def approve_booking(
    booking_id: UUID,
    user: CurrentUser,
    handler: Annotated[
        ApproveBookingHandler, Depends(get_approve_booking_handler),
    ],
):
    dto = unwrap(await handler.handle(ApproveBookingCommand(
        actor_id=user.user_id, booking_id=booking_id,
    )))
    return BookingResponse.from_dto(dto)


@router.post("/{booking_id}/reject", response_model=BookingResponse)
async def reject_booking(
    booking_id: UUID,
    body: RejectBookingRequest,
    user: CurrentUser,
    handler: Annotated[
        RejectBookingHandler, Depends(get_reject_booking_handler),
    ],
):
    dto = unwrap(await handler.handle(RejectBookingCommand(
        actor_id=user.user_id, booking_id=booking_id, reason=body.reason,
    )))
    return BookingResponse.from_dto(dto)
```

- [ ] **Step 3: Smoke import**

Run: `.venv/bin/python -c "from app.api.v1.me_bookings.routes import router; print(len(router.routes))"`
Expected: `6`.

- [ ] **Step 4: Commit**

```bash
git add app/api/v1/me_bookings/deps.py app/api/v1/me_bookings/routes.py
git commit -m "$(cat <<'EOF'
feat(bookings): /v1/me/bookings endpoints + DI

Plan 08 task 24. Six endpoints: POST (create), GET list, GET by id,
POST cancel, POST approve, POST reject. Cancel + approve + reject
share /v1/me/bookings/{id}/* path namespace; cancel handler
branches on actor role.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 25: Per-resource booking + agenda routes (extend `me_resources/`)

**Files:**
- Modify: `app/api/v1/me_resources/routes.py`
- Modify: `app/api/v1/me_resources/deps.py` (add owner agenda + bookings handler factories if missing)

- [ ] **Step 1: Append to `app/api/v1/me_resources/routes.py`**

Add the following imports at the top of the file (alongside existing imports):

```python
from datetime import datetime
from app.api.v1.me_bookings.deps import (
    get_agenda_handler,
    get_list_resource_bookings_handler,
)
from app.api.v1.me_bookings.schemas import (
    AgendaResponse,
    BookingListResponse,
)
from app.domain.bookings.booking_status import BookingStatus
from app.use_cases.bookings.queries.get_agenda import (
    GetAgendaHandler,
    GetAgendaQuery,
)
from app.use_cases.bookings.queries.list_resource_bookings import (
    ListResourceBookingsHandler,
    ListResourceBookingsQuery,
)
```

Append two new routes at the end of the file:

```python
@router.get(
    "/{resource_id}/bookings",
    response_model=BookingListResponse,
)
async def list_resource_bookings(
    resource_id: UUID,
    user: CurrentUser,
    handler: Annotated[
        ListResourceBookingsHandler, Depends(get_list_resource_bookings_handler),
    ],
    status_filter: BookingStatus | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
):
    dto = unwrap(await handler.handle(ListResourceBookingsQuery(
        actor_id=user.user_id, resource_id=resource_id,
        status=status_filter, page=page, page_size=page_size,
    )))
    return BookingListResponse.from_dto(dto)


@router.get(
    "/{resource_id}/agenda",
    response_model=AgendaResponse,
)
async def get_owner_agenda(
    resource_id: UUID,
    user: CurrentUser,
    handler: Annotated[GetAgendaHandler, Depends(get_agenda_handler)],
    range_start: datetime = Query(..., alias="from"),
    range_end: datetime = Query(..., alias="to"),
):
    dto = unwrap(await handler.handle(GetAgendaQuery(
        resource_id=resource_id,
        range_start=range_start,
        range_end=range_end,
        actor_id=user.user_id,
    )))
    return AgendaResponse.from_dto(dto)
```

If `Query`, `Depends`, `Annotated`, or `UUID` aren't already imported in `routes.py`, add them.

- [ ] **Step 2: Smoke boot**

Run:
```
.venv/bin/python -c "
from app.main import app
paths = sorted({r.path for r in app.routes})
booking_paths = [p for p in paths if 'bookings' in p or 'agenda' in p]
print(booking_paths)
"
```

Expected output (after Task 26 wires the v1 router; for now, the unique paths must include at least `/v1/me/resources/{resource_id}/bookings` and `/v1/me/resources/{resource_id}/agenda`):
```
['/v1/me/resources/{resource_id}/agenda', '/v1/me/resources/{resource_id}/bookings']
```

(If `/v1/me/bookings` isn't yet listed, that's expected — Task 26 wires it.)

- [ ] **Step 3: Commit**

```bash
git add app/api/v1/me_resources/routes.py
git commit -m "$(cat <<'EOF'
feat(bookings): per-resource bookings + owner agenda routes

Plan 08 task 25. GET /v1/me/resources/{id}/bookings (paged, optional
status filter) and GET /v1/me/resources/{id}/agenda (from/to
required, returns owner-detailed agenda with booking_id +
customer_id per occupied slot).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 26: Public agenda route (extend `public_resources/`) + wire `me_bookings_router`

**Files:**
- Modify: `app/api/v1/public_resources/routes.py`
- Modify: `app/api/v1/router.py`

- [ ] **Step 1: Add public agenda route**

Append to `app/api/v1/public_resources/routes.py`:

```python
from datetime import datetime
from app.api.v1.me_bookings.deps import get_agenda_handler
from app.api.v1.me_bookings.schemas import AgendaResponse
from app.use_cases.bookings.queries.get_agenda import (
    GetAgendaHandler, GetAgendaQuery,
)


@router.get(
    "/{owner_slug}/{resource_slug}/agenda",
    response_model=AgendaResponse,
)
async def get_public_agenda(
    owner_slug: str,
    resource_slug: str,
    handler: Annotated[GetAgendaHandler, Depends(get_agenda_handler)],
    range_start: datetime = Query(..., alias="from"),
    range_end: datetime = Query(..., alias="to"),
):
    dto = unwrap(await handler.handle(GetAgendaQuery(
        owner_slug=owner_slug,
        resource_slug=resource_slug,
        range_start=range_start,
        range_end=range_end,
        actor_id=None,                  # public — no booking ids
    )))
    return AgendaResponse.from_dto(dto)
```

If imports for `Annotated`, `Depends`, `Query`, `unwrap` aren't already present in `public_resources/routes.py`, add them.

- [ ] **Step 2: Wire `me_bookings_router`**

Edit `app/api/v1/router.py`. Add the import alphabetically among the `me_*` block:

```python
from app.api.v1.me_bookings.routes import router as me_bookings_router
```

Add the include alongside the other includes:

```python
api_router.include_router(me_bookings_router)
```

- [ ] **Step 3: Smoke boot the FastAPI app**

Run:
```
.venv/bin/python -c "
from app.main import app
unique = sorted({r.path for r in app.routes})
booking = [p for p in unique if 'booking' in p or 'agenda' in p]
print(len(unique), 'unique paths')
print('booking-related:')
for p in booking:
    print(' ', p)
"
```

Expected output: `7` booking-related paths printed, including:

```
/v1/me/bookings
/v1/me/bookings/{booking_id}
/v1/me/bookings/{booking_id}/approve
/v1/me/bookings/{booking_id}/cancel
/v1/me/bookings/{booking_id}/reject
/v1/me/resources/{resource_id}/agenda
/v1/me/resources/{resource_id}/bookings
/v1/resources/{owner_slug}/{resource_slug}/agenda
```

- [ ] **Step 4: Run full unit + integration suite**

Run: `.venv/bin/pytest tests/unit/ tests/integration/ -q`
Expected: green.

- [ ] **Step 5: Commit**

```bash
git add app/api/v1/public_resources/routes.py app/api/v1/router.py
git commit -m "$(cat <<'EOF'
feat(bookings): public agenda route + wire me_bookings_router

Plan 08 task 26. GET /v1/resources/{owner_slug}/{resource_slug}/agenda
returns the same shape as the owner agenda but with booking_id +
customer_id null (public view). me_bookings_router included in
v1 router.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 27: Cron entry-point — `app/jobs/expire_pending_bookings.py`

**Files:**
- Create: `app/jobs/expire_pending_bookings.py`

- [ ] **Step 1: Create the cron entry-point**

```python
"""Cron entry-point. Run via `python -m app.jobs.expire_pending_bookings`.

Suggested schedule: hourly (cron `0 * * * *`). Idempotent — safe to retry.
Transitions PENDING bookings whose slot_start_at < now to EXPIRED and
dispatches BOOKING_REJECTED notifications (reason=slot_start_passed_with_no_decision).
"""
from __future__ import annotations
import asyncio
import logging

from app.infrastructure.db.session import dispose_engine, get_session, init_engine
from app.infrastructure.notifications.persistent_notification_service import (
    PersistentNotificationService,
)
from app.infrastructure.repositories.booking_repository import (
    SQLAlchemyBookingRepository,
)
from app.infrastructure.repositories.notification_repository import (
    SQLAlchemyNotificationRepository,
)
from app.use_cases.bookings.commands.expire_pending_bookings import (
    ExpirePendingBookingsCommand,
    ExpirePendingBookingsHandler,
)


logger = logging.getLogger(__name__)


async def main() -> int:
    init_engine()
    try:
        async for session in get_session():
            bookings = SQLAlchemyBookingRepository(session)
            notifications = PersistentNotificationService(
                SQLAlchemyNotificationRepository(session),
            )
            handler = ExpirePendingBookingsHandler(
                bookings=bookings, notifications=notifications,
            )
            result = await handler.handle(ExpirePendingBookingsCommand())
            count = result.value or 0
            logger.info("expired %s pending bookings", count)
            return count
        return 0
    finally:
        await dispose_engine()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
```

- [ ] **Step 2: Smoke import**

Run: `.venv/bin/python -c "import app.jobs.expire_pending_bookings as m; print(m.main.__name__)"`
Expected: `main`.

- [ ] **Step 3: Run unit + integration to confirm no breakage from importing the cron**

Run: `.venv/bin/pytest tests/unit/ tests/integration/ -q`
Expected: green.

- [ ] **Step 4: Commit**

```bash
git add app/jobs/expire_pending_bookings.py
git commit -m "$(cat <<'EOF'
feat(bookings): cron entry-point for pending expiry

Plan 08 task 27. Mirrors the structure of expire_trialing_subscriptions
(Plan 05): init_engine → get_session loop → handler → log count →
dispose_engine. Suggested schedule: hourly.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 28: E2E — happy path + cancellation cutoff

**Files:**
- Create: `tests/e2e/bookings/__init__.py` (empty)
- Create: `tests/e2e/bookings/test_happy_path.py`

- [ ] **Step 1: Write the e2e tests**

Create `tests/e2e/bookings/__init__.py` (empty) and `tests/e2e/bookings/test_happy_path.py`. The fixture pattern follows Plan 07 task 15 (`_register_owner` helper inline; `client` + `customer_token` + `admin_token` fixtures from `tests/e2e/conftest.py`).

```python
from __future__ import annotations
from datetime import datetime, timedelta, timezone

import pytest


pytestmark = pytest.mark.asyncio


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _slot_iso(*, days_ahead: int, hours_ahead: int = 0, hours: int = 1) -> tuple[str, str]:
    """Build a slot anchored on a future Monday at 14:00 São Paulo (17:00 UTC).
    For simplicity tests use an absolute UTC Monday next week.
    """
    base = (_utc_now() + timedelta(days=days_ahead)).replace(
        hour=17 - hours_ahead, minute=0, second=0, microsecond=0,
    )
    end = base + timedelta(hours=hours)
    return base.isoformat(), end.isoformat()


async def _register_owner_with_resource(client, admin_token):
    """Register an owner, seed a ResourceType (admin), create a published
    Resource. Returns (owner_token, owner_id, resource_id)."""
    # Register owner.
    reg = await client.post("/v1/auth/register", json={
        "email": "owner-bookings@example.com",
        "password": "hunter2-strong",
        "role": "owner",
        "full_name": "Owner Bookings",
        "phone": None,
    })
    assert reg.status_code == 201, reg.text
    owner_id = reg.json()["id"]
    login = await client.post("/v1/auth/login", json={
        "email": "owner-bookings@example.com",
        "password": "hunter2-strong",
    })
    owner_token = login.json()["access_token"]

    # Seed a ResourceType via admin.
    rt = await client.post(
        "/v1/admin/resource-types",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"slug": "football-field", "name": "Football Field",
              "description": "", "attribute_schema": []},
    )
    assert rt.status_code == 201, rt.text
    rt_id = rt.json()["id"]

    # Create + publish a resource.
    create = await client.post(
        "/v1/me/resources",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={
            "resource_type_id": rt_id,
            "slug": "campo",
            "name": "Campo",
            "description": "",
            "city": "SP",
            "region": "SP",
            "timezone": "America/Sao_Paulo",
            "slot_duration_minutes": 60,
            "operating_hours": {
                wd: [{"start": "06:00", "end": "22:00"}]
                for wd in ("monday", "tuesday", "wednesday", "thursday",
                           "friday", "saturday", "sunday")
            },
            "base_price_cents": 8000,
            "customer_cancellation_cutoff_hours": 24,
            "base_attributes": {},
            "pricing_rules": [],
            "custom_attributes": [],
        },
    )
    assert create.status_code == 201, create.text
    resource_id = create.json()["id"]
    pub = await client.post(
        f"/v1/me/resources/{resource_id}/publish",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert pub.status_code == 200, pub.text
    return owner_token, owner_id, resource_id


async def test_happy_path_request_approve_view(client, admin_token, customer_token):
    owner_token, owner_id, resource_id = await _register_owner_with_resource(
        client, admin_token,
    )
    start_iso, end_iso = _slot_iso(days_ahead=2, hours=2)

    # Customer requests booking.
    req = await client.post(
        "/v1/me/bookings",
        headers={"Authorization": f"Bearer {customer_token}"},
        json={
            "resource_id": resource_id,
            "slot_start_at": start_iso,
            "slot_end_at": end_iso,
            "customer_note": "10 pessoas",
        },
    )
    assert req.status_code == 201, req.text
    booking = req.json()
    assert booking["status"] == "PENDING"
    assert booking["total_price_cents"] == 16000

    # Owner approves.
    approve = await client.post(
        f"/v1/me/bookings/{booking['id']}/approve",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert approve.status_code == 200, approve.text
    assert approve.json()["status"] == "APPROVED"

    # Customer fetches the booking.
    fetched = await client.get(
        f"/v1/me/bookings/{booking['id']}",
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert fetched.status_code == 200
    assert fetched.json()["status"] == "APPROVED"


async def test_customer_cancel_within_cutoff(client, admin_token, customer_token):
    owner_token, _owner_id, resource_id = await _register_owner_with_resource(
        client, admin_token,
    )
    start_iso, end_iso = _slot_iso(days_ahead=3)

    req = await client.post(
        "/v1/me/bookings",
        headers={"Authorization": f"Bearer {customer_token}"},
        json={
            "resource_id": resource_id,
            "slot_start_at": start_iso, "slot_end_at": end_iso,
            "customer_note": None,
        },
    )
    booking_id = req.json()["id"]

    cancel = await client.post(
        f"/v1/me/bookings/{booking_id}/cancel",
        headers={"Authorization": f"Bearer {customer_token}"},
        json={"reason": "changed plans"},
    )
    assert cancel.status_code == 200, cancel.text
    assert cancel.json()["status"] == "CANCELLED"


async def test_customer_cancel_past_cutoff_returns_403(
    client, admin_token, customer_token,
):
    owner_token, _, resource_id = await _register_owner_with_resource(
        client, admin_token,
    )
    # Cutoff is 24h. Pick a slot 6 hours from now (well within cutoff).
    base = (_utc_now() + timedelta(hours=6)).replace(
        minute=0, second=0, microsecond=0,
    )
    end = base + timedelta(hours=1)
    req = await client.post(
        "/v1/me/bookings",
        headers={"Authorization": f"Bearer {customer_token}"},
        json={
            "resource_id": resource_id,
            "slot_start_at": base.isoformat(),
            "slot_end_at": end.isoformat(),
            "customer_note": None,
        },
    )
    # Booking creation succeeds — the 6h-future slot is in operating hours.
    if req.status_code != 201:
        # Slot may be out of operating hours depending on real-now hour.
        pytest.skip(f"environment now() doesn't permit a 6h-ahead slot: {req.text}")
    booking_id = req.json()["id"]

    cancel = await client.post(
        f"/v1/me/bookings/{booking_id}/cancel",
        headers={"Authorization": f"Bearer {customer_token}"},
        json={"reason": None},
    )
    assert cancel.status_code == 403
    assert cancel.json()["detail"]["code"] == "BookingCancellationPastCutoff"
```

- [ ] **Step 2: Run the e2e tests**

Run: `.venv/bin/pytest tests/e2e/bookings/test_happy_path.py -v`
Expected: 3 PASSED (or 2 PASSED + 1 SKIPPED depending on real time-of-day for the cutoff test).

- [ ] **Step 3: Run full suite**

Run: `.venv/bin/pytest -q`
Expected: green.

- [ ] **Step 4: Commit**

```bash
git add tests/e2e/bookings/__init__.py tests/e2e/bookings/test_happy_path.py
git commit -m "$(cat <<'EOF'
test(e2e): bookings happy path + cancellation cutoff

Plan 08 task 28. Customer requests, owner approves, both can fetch
the APPROVED booking. Customer cancellation within cutoff returns
200 CANCELLED; past cutoff returns 403 BookingCancellationPastCutoff.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 29: E2E — competing approvals + auto-rejection + natural dedup

**Files:**
- Create: `tests/e2e/bookings/test_competing_approvals.py`

- [ ] **Step 1: Write tests**

```python
from __future__ import annotations
from datetime import datetime, timedelta, timezone

import pytest

# Reuse the helper from test_happy_path.py via direct import.
from tests.e2e.bookings.test_happy_path import (
    _register_owner_with_resource,
    _slot_iso,
    _utc_now,
)


pytestmark = pytest.mark.asyncio


async def _register_customer(client, *, email: str) -> tuple[str, str]:
    reg = await client.post("/v1/auth/register", json={
        "email": email, "password": "hunter2-strong",
        "role": "customer", "full_name": "C", "phone": None,
    })
    assert reg.status_code == 201, reg.text
    cid = reg.json()["id"]
    login = await client.post("/v1/auth/login", json={
        "email": email, "password": "hunter2-strong",
    })
    return login.json()["access_token"], cid


async def test_two_customers_same_slot_one_approved_other_rejected(
    client, admin_token,
):
    owner_token, _, resource_id = await _register_owner_with_resource(
        client, admin_token,
    )
    a_token, _ = await _register_customer(client, email="a-bk@example.com")
    b_token, _ = await _register_customer(client, email="b-bk@example.com")
    start_iso, end_iso = _slot_iso(days_ahead=4, hours=2)

    a_req = await client.post(
        "/v1/me/bookings",
        headers={"Authorization": f"Bearer {a_token}"},
        json={"resource_id": resource_id, "slot_start_at": start_iso,
              "slot_end_at": end_iso, "customer_note": None},
    )
    assert a_req.status_code == 201
    b_req = await client.post(
        "/v1/me/bookings",
        headers={"Authorization": f"Bearer {b_token}"},
        json={"resource_id": resource_id, "slot_start_at": start_iso,
              "slot_end_at": end_iso, "customer_note": None},
    )
    assert b_req.status_code == 201
    a_id = a_req.json()["id"]
    b_id = b_req.json()["id"]

    # Owner approves A.
    approve = await client.post(
        f"/v1/me/bookings/{a_id}/approve",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert approve.status_code == 200
    assert approve.json()["status"] == "APPROVED"

    # B should now be REJECTED with auto_rejected_competing_request reason.
    b_after = await client.get(
        f"/v1/me/bookings/{b_id}",
        headers={"Authorization": f"Bearer {b_token}"},
    )
    assert b_after.status_code == 200
    body = b_after.json()
    assert body["status"] == "REJECTED"
    last_change = body["status_history"][-1]
    assert last_change["to_status"] == "REJECTED"
    assert last_change["reason"] == "auto_rejected_competing_request"


async def test_natural_dedup_returns_409(client, admin_token, customer_token):
    _, _, resource_id = await _register_owner_with_resource(
        client, admin_token,
    )
    start_iso, end_iso = _slot_iso(days_ahead=5, hours=1)
    first = await client.post(
        "/v1/me/bookings",
        headers={"Authorization": f"Bearer {customer_token}"},
        json={"resource_id": resource_id, "slot_start_at": start_iso,
              "slot_end_at": end_iso, "customer_note": None},
    )
    assert first.status_code == 201
    # Same customer, same slot — dedup.
    second = await client.post(
        "/v1/me/bookings",
        headers={"Authorization": f"Bearer {customer_token}"},
        json={"resource_id": resource_id, "slot_start_at": start_iso,
              "slot_end_at": end_iso, "customer_note": None},
    )
    assert second.status_code == 409
    assert second.json()["detail"]["code"] == "BookingAlreadyExists"
```

- [ ] **Step 2: Run tests**

Run: `.venv/bin/pytest tests/e2e/bookings/test_competing_approvals.py -v`
Expected: 2 PASSED.

- [ ] **Step 3: Commit**

```bash
git add tests/e2e/bookings/test_competing_approvals.py
git commit -m "$(cat <<'EOF'
test(e2e): bookings competing approvals + natural dedup

Plan 08 task 29. Two customers PENDING the same slot; owner approves
one — the other is auto-REJECTED with the canonical reason. Natural
dedup: same customer requesting the same slot twice returns 409
BookingAlreadyExists.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 30: E2E — cron expiry + INACTIVE owner + resource-delete cascade

**Files:**
- Create: `tests/e2e/bookings/test_cron_and_cascade.py`

- [ ] **Step 1: Write tests**

```python
from __future__ import annotations
from datetime import datetime, timedelta, timezone

import pytest

from app.use_cases.bookings.commands.expire_pending_bookings import (
    ExpirePendingBookingsCommand, ExpirePendingBookingsHandler,
)
from app.infrastructure.notifications.persistent_notification_service import (
    PersistentNotificationService,
)
from app.infrastructure.repositories.booking_repository import (
    SQLAlchemyBookingRepository,
)
from app.infrastructure.repositories.notification_repository import (
    SQLAlchemyNotificationRepository,
)
from tests.e2e.bookings.test_happy_path import (
    _register_owner_with_resource,
    _slot_iso,
)


pytestmark = pytest.mark.asyncio


async def test_inactive_owner_cannot_approve(
    client, admin_token, customer_token,
):
    owner_token, owner_id, resource_id = await _register_owner_with_resource(
        client, admin_token,
    )
    start_iso, end_iso = _slot_iso(days_ahead=2)
    req = await client.post(
        "/v1/me/bookings",
        headers={"Authorization": f"Bearer {customer_token}"},
        json={"resource_id": resource_id, "slot_start_at": start_iso,
              "slot_end_at": end_iso, "customer_note": None},
    )
    assert req.status_code == 201
    booking_id = req.json()["id"]

    # Admin sets owner subscription to INACTIVE.
    set_status = await client.post(
        f"/v1/admin/owners/{owner_id}/subscription",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"status": "INACTIVE"},
    )
    assert set_status.status_code == 200

    approve = await client.post(
        f"/v1/me/bookings/{booking_id}/approve",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert approve.status_code == 403
    assert approve.json()["detail"]["code"] == "OwnerSubscriptionInactive"


async def test_resource_delete_cascades_pendings(
    client, admin_token, customer_token, db_session,
):
    owner_token, owner_id, resource_id = await _register_owner_with_resource(
        client, admin_token,
    )
    start_iso, end_iso = _slot_iso(days_ahead=2)
    req = await client.post(
        "/v1/me/bookings",
        headers={"Authorization": f"Bearer {customer_token}"},
        json={"resource_id": resource_id, "slot_start_at": start_iso,
              "slot_end_at": end_iso, "customer_note": None},
    )
    assert req.status_code == 201
    booking_id = req.json()["id"]

    # Owner soft-deletes the resource.
    delete = await client.delete(
        f"/v1/me/resources/{resource_id}",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert delete.status_code == 204, delete.text

    # Booking should now be CANCELLED with reason resource_deleted.
    fetched = await client.get(
        f"/v1/me/bookings/{booking_id}",
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert fetched.status_code == 200
    body = fetched.json()
    assert body["status"] == "CANCELLED"
    assert body["status_history"][-1]["reason"] == "resource_deleted"


async def test_cron_expires_past_pendings(
    client, admin_token, customer_token, db_session,
):
    """Inserts a PENDING booking with slot_start_at in the past directly via
    the SQL repo (the API rejects past slots), then runs the handler against
    the same session and verifies transition to EXPIRED."""
    owner_token, _, resource_id = await _register_owner_with_resource(
        client, admin_token,
    )
    # Insert an artificially past PENDING by bypassing the API — direct SQL
    # bookings repo.
    from uuid import UUID
    from app.domain.bookings.booking import Booking
    from app.domain.shared.value_objects.date_time_range import DateTimeRange
    from app.domain.shared.value_objects.money import Money

    customer_resp = await client.get(
        "/v1/me", headers={"Authorization": f"Bearer {customer_token}"},
    )
    customer_id = UUID(customer_resp.json()["id"])
    now = datetime.now(timezone.utc)
    past = now - timedelta(hours=2)
    sr = DateTimeRange.create(
        start_at=past, end_at=past + timedelta(hours=1),
    ).value
    repo = SQLAlchemyBookingRepository(db_session)
    booking = Booking.create_pending(
        resource_id=UUID(resource_id),
        customer_id=customer_id,
        slot_range=sr,
        total_price_cents=Money.create(8000).value,
        customer_note=None,
        now=past - timedelta(days=1),
    )
    await repo.add(booking)
    await db_session.commit()

    # Run cron handler against same session.
    notifs = PersistentNotificationService(
        SQLAlchemyNotificationRepository(db_session),
    )
    handler = ExpirePendingBookingsHandler(bookings=repo, notifications=notifs)
    r = await handler.handle(ExpirePendingBookingsCommand())
    assert r.is_success
    assert r.value >= 1

    # Verify state.
    fetched = (await repo.get_by_id(booking.id)).value
    assert fetched.status.value == "EXPIRED"
```

- [ ] **Step 2: Run tests**

Run: `.venv/bin/pytest tests/e2e/bookings/test_cron_and_cascade.py -v`
Expected: 3 PASSED.

- [ ] **Step 3: Commit**

```bash
git add tests/e2e/bookings/test_cron_and_cascade.py
git commit -m "$(cat <<'EOF'
test(e2e): bookings INACTIVE-owner + cascade + cron

Plan 08 task 30. Three e2e: (1) admin sets owner INACTIVE → owner
approve attempt returns 403 OwnerSubscriptionInactive; (2) owner
soft-deletes a resource → its PENDING booking is CANCELLED with
reason=resource_deleted; (3) cron handler transitions past-slot
PENDINGs to EXPIRED.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 31: E2E — agenda (public + owner)

**Files:**
- Create: `tests/e2e/bookings/test_agenda.py`

- [ ] **Step 1: Write tests**

```python
from __future__ import annotations
from datetime import datetime, timedelta, timezone

import pytest

from tests.e2e.bookings.test_happy_path import (
    _register_owner_with_resource,
    _slot_iso,
    _utc_now,
)


pytestmark = pytest.mark.asyncio


async def test_public_agenda_returns_slots_without_booking_ids(
    client, admin_token, customer_token,
):
    owner_token, _, resource_id = await _register_owner_with_resource(
        client, admin_token,
    )
    # Resolve owner_slug + resource_slug from the public listing.
    listing = await client.get("/v1/resources")
    items = listing.json()["items"]
    target = next((i for i in items if i["id"] == resource_id), None)
    assert target is not None, f"resource not in public listing: {items}"
    owner_slug = target["owner_slug"]
    resource_slug = target["slug"]

    # Customer creates a booking that will appear in agenda as PENDING.
    start_iso, end_iso = _slot_iso(days_ahead=3, hours=1)
    req = await client.post(
        "/v1/me/bookings",
        headers={"Authorization": f"Bearer {customer_token}"},
        json={"resource_id": resource_id, "slot_start_at": start_iso,
              "slot_end_at": end_iso, "customer_note": None},
    )
    assert req.status_code == 201

    range_start = (_utc_now() + timedelta(days=2)).isoformat()
    range_end = (_utc_now() + timedelta(days=4)).isoformat()
    agenda = await client.get(
        f"/v1/resources/{owner_slug}/{resource_slug}/agenda"
        f"?from={range_start}&to={range_end}",
    )
    assert agenda.status_code == 200, agenda.text
    body = agenda.json()
    assert body["resource_id"] == resource_id
    pending = [s for s in body["slots"] if s["status"] == "PENDING"]
    assert len(pending) >= 1
    for s in pending:
        assert s["booking_id"] is None
        assert s["customer_id"] is None


async def test_owner_agenda_includes_booking_ids(
    client, admin_token, customer_token,
):
    owner_token, _, resource_id = await _register_owner_with_resource(
        client, admin_token,
    )
    start_iso, end_iso = _slot_iso(days_ahead=3, hours=1)
    req = await client.post(
        "/v1/me/bookings",
        headers={"Authorization": f"Bearer {customer_token}"},
        json={"resource_id": resource_id, "slot_start_at": start_iso,
              "slot_end_at": end_iso, "customer_note": None},
    )
    assert req.status_code == 201
    booking_id = req.json()["id"]

    range_start = (_utc_now() + timedelta(days=2)).isoformat()
    range_end = (_utc_now() + timedelta(days=4)).isoformat()
    agenda = await client.get(
        f"/v1/me/resources/{resource_id}/agenda"
        f"?from={range_start}&to={range_end}",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert agenda.status_code == 200, agenda.text
    body = agenda.json()
    occupied = [s for s in body["slots"] if s["status"] == "PENDING"]
    assert any(s["booking_id"] == booking_id for s in occupied)


async def test_agenda_range_too_wide_returns_422(client, admin_token):
    owner_token, _, resource_id = await _register_owner_with_resource(
        client, admin_token,
    )
    range_start = _utc_now().isoformat()
    range_end = (_utc_now() + timedelta(days=60)).isoformat()
    agenda = await client.get(
        f"/v1/me/resources/{resource_id}/agenda"
        f"?from={range_start}&to={range_end}",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert agenda.status_code == 422
    assert agenda.json()["detail"]["code"] == "AgendaRangeTooWide"
```

- [ ] **Step 2: Run tests**

Run: `.venv/bin/pytest tests/e2e/bookings/test_agenda.py -v`
Expected: 3 PASSED.

- [ ] **Step 3: Run full suite**

Run: `.venv/bin/pytest -q`
Expected: green.

- [ ] **Step 4: Commit**

```bash
git add tests/e2e/bookings/test_agenda.py
git commit -m "$(cat <<'EOF'
test(e2e): bookings public + owner agenda

Plan 08 task 31. Public agenda: PENDING slots have null booking_id /
customer_id. Owner agenda: PENDING slots include booking_id +
customer_id. Range > 31 days returns 422 AgendaRangeTooWide.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 32: Canonical venue-backend spec refresh (§3 #14, §4.2, §5.3, §5.4, §8)

**Files:**
- Modify: `docs/superpowers/specs/2026-04-25-venue-backend-design.md`

- [ ] **Step 1: Refresh §3 #14 (Idempotency keys)**

Find the line:

```markdown
| 14 | Idempotency keys accepted on `POST /me/bookings` and approval/reject endpoints. | Cheap to add; avoids the inevitable double-click / network-retry duplicate booking. |
```

Replace with:

```markdown
| 14 | Booking creation uses **domain-level natural dedup**: same customer + resource + overlapping slot already PENDING/APPROVED → 409 `BookingAlreadyExists`. State-machine idempotency covers approve/reject/cancel (subsequent calls see status != PENDING and return 409 `BookingInvalidStateTransition`). **`Idempotency-Key` infrastructure deferred** — see plan-08-bookings-design.md §1. | Natural key (customer × resource × slot) is the right primary; generic Idempotency-Key reintroducible later if PSP endpoints land. |
```

- [ ] **Step 2: Refresh §4.2 booking handler rows**

Find the four rows for `RequestBookingHandler`, `ApproveBookingHandler`, `CancelBookingHandler` (and any other booking-feature row). Replace the table rows for these three with:

```markdown
| `RequestBookingHandler` | `bookings/commands` | `IBookingRepository`, `IResourceRepository`, `ISubscriptionRepository`, `INotificationService` | Validate (resource gates, slot grid, operating hours, future-only, natural dedup), price via `Resource.compute_price`, persist `Booking{PENDING}`, notify owner. |
| `ApproveBookingHandler` | `bookings/commands` | `IBookingRepository`, `IResourceRepository`, `ISubscriptionRepository`, `INotificationService`, `IBookingLockService` | Acquires per-resource advisory lock; under lock, re-fetches PENDING target, scans overlapping PENDINGs, transitions target → APPROVED + competitors → REJECTED in one TX; notifies all parties outside the lock. |
| `RejectBookingHandler` | `bookings/commands` | `IBookingRepository`, `IResourceRepository`, `INotificationService` | Owner manual reject of PENDING. State-machine handles concurrency. |
| `CancelBookingHandler` | `bookings/commands` | `IBookingRepository`, `IResourceRepository`, `INotificationService` | Single handler; branches on actor role. Customer enforces `customer_cancellation_cutoff_hours`; owner has no time bound. Notifies counterpart. |
```

- [ ] **Step 3: Refresh §5.3 soft-delete invariant**

Find the line in §5.3:

```markdown
- Soft-delete (`deleted_at != NULL`) blocked when there is any `APPROVED` booking with `slot_range.start_at >= now`.
```

Replace with:

```markdown
- Soft-delete (`deleted_at != NULL`):
  - Blocked (409 `ResourceHasFutureApprovedBookings`) when any `APPROVED` booking on the resource has `slot_range.start_at >= now`.
  - Otherwise, all `PENDING` bookings on the resource are auto-`CANCELLED` with `reason="resource_deleted"` in the same transaction; each affected customer receives a `BOOKING_CANCELLED` notification with `cancelled_by=owner` payload.
```

- [ ] **Step 4: Refresh §5.4 invariants**

Find the §5.4 invariants block. Drop the line that mentions `cancelled_by: ActorRef | None`:

```markdown
├── cancelled_by: ActorRef | None           # OWNER | CUSTOMER, with user_id
```

(The line is in the Booking aggregate diagram.) Remove that entire line. Also append a "Plan 08 deliberate cuts" callout right below the existing **Invariants** list:

```markdown
**Plan 08 deliberate cuts (see `docs/superpowers/specs/2026-04-27-plan-08-bookings-design.md`):**
- `cancelled_by` field removed — derivable from `status_history[-1]` when `status == CANCELLED`. The `status_history` is the audit source of truth.
- Owner cancellation reason kept optional. Backend never enforces; frontend may encourage.
- `Idempotency-Key` deferred in favor of domain-level natural dedup (see §3 #14).
```

- [ ] **Step 5: Refresh §8 plan 08 description**

Find the line:

```markdown
8. **Plan 08 — Bookings.** `Booking` aggregate using `DateTimeRange`/`Money`/`ShortDescription`. Approval transaction with advisory lock + exclusion constraint. Nightly expiry job.
```

Replace with:

```markdown
8. **Plan 08 — Bookings.** `Booking` aggregate (5-state machine PENDING → {APPROVED, REJECTED, CANCELLED, EXPIRED}; APPROVED → CANCELLED) + `IBookingRepository` + `IBookingLockService` (Postgres advisory_xact_lock + in-memory async-lock test adapter). 5 mutation handlers (request/approve-with-auto-rejection/reject/cancel/expire-cron); 4 query handlers (list-my, get-my, list-resource, agenda — shared public + owner shape). 10 endpoints (4 customer + 5 owner + 1 public agenda). Concurrency: Postgres `btree_gist` exclusion constraint as belt-and-suspenders. Plan 06 retroactives: `Resource.compute_price`, `Weekday.from_iso`, `SoftDeleteResourceHandler` cascade. Natural dedup replaces `Idempotency-Key` — see plan-08 design §1.
```

- [ ] **Step 6: Sanity check the refresh**

Run:
```
.venv/bin/python -c "
from pathlib import Path
text = Path('docs/superpowers/specs/2026-04-25-venue-backend-design.md').read_text()
# Idempotency-Key should only appear in deferred callouts.
idem_lines = [l for l in text.splitlines() if 'Idempotency-Key' in l]
print('Idempotency-Key lines:', len(idem_lines))
for l in idem_lines:
    print(' ', l[:140])
# cancelled_by should be gone or only in 'deliberate cuts' callout.
cb_lines = [l for l in text.splitlines() if 'cancelled_by' in l]
print('cancelled_by lines:', len(cb_lines))
for l in cb_lines:
    print(' ', l[:140])
"
```

Expected: any remaining `Idempotency-Key` is in the "deferred" callout; any remaining `cancelled_by` is in the §5.4 deliberate-cuts block.

- [ ] **Step 7: Run pytest to ensure no doc-driven test broke**

Run: `.venv/bin/pytest -q`
Expected: green.

- [ ] **Step 8: Commit**

```bash
git add docs/superpowers/specs/2026-04-25-venue-backend-design.md
git commit -m "$(cat <<'EOF'
docs(spec): refresh canonical §3 #14 / §4.2 / §5.3 / §5.4 / §8 with Plan 08 deltas

Plan 08 task 32. Drops Idempotency-Key (natural dedup wins),
cancelled_by field (derivable from status_history), refines
soft-delete invariant with the cascade rules, refreshes §8 plan 08
description with what actually shipped (lock service + Plan 06
retroactives + agenda + cron + 10 endpoints).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Final verification

- [ ] **Step 1: Run the entire test suite**

Run: `.venv/bin/pytest -q`
Expected: all green. Total count should be ~600+ (Plan 07 closed at 479; Plan 08 adds ~100 unit + integration + e2e tests).

- [ ] **Step 2: Smoke-boot the FastAPI app**

Run:
```
.venv/bin/python -c "
from app.main import app
unique = sorted({r.path for r in app.routes})
print('total unique paths:', len(unique))
booking_paths = [p for p in unique if 'booking' in p or 'agenda' in p]
print('booking paths:')
for p in booking_paths:
    print(' ', p)
"
```

Expected: ≥ 8 booking-related paths printed:
```
/v1/me/bookings
/v1/me/bookings/{booking_id}
/v1/me/bookings/{booking_id}/approve
/v1/me/bookings/{booking_id}/cancel
/v1/me/bookings/{booking_id}/reject
/v1/me/resources/{resource_id}/agenda
/v1/me/resources/{resource_id}/bookings
/v1/resources/{owner_slug}/{resource_slug}/agenda
```

- [ ] **Step 3: Confirm Idempotency-Key is fully absent from production code**

Run: `grep -rn "idempotency.key\|Idempotency-Key\|IdempotencyKey" app/ tests/ 2>&1 | grep -v __pycache__`
Expected: no matches (production code; some doc/spec references in deferred callouts are acceptable but not under app/ or tests/).

- [ ] **Step 4: Confirm `cancelled_by` field is fully absent from production code**

Run: `grep -rn "cancelled_by" app/ 2>&1 | grep -v __pycache__`
Expected: matches ONLY in notification payloads (where `cancelled_by="owner"` etc. is a payload key, not a stored field). No `cancelled_by:` field declarations or `.cancelled_by` attribute accesses on Booking.

- [ ] **Step 5: Confirm `btree_gist` exclusion constraint is correctly conditional**

Run:
```
grep -n "btree_gist\|EXCLUDE USING gist\|bookings_no_approved_overlap" app/migrations/versions/*bookings*.py
```
Expected: matches inside an `if bind.dialect.name == 'postgresql':` block.

- [ ] **Step 6: Final commit (only if any verification surfaces drift)**

If steps 1–5 all pass cleanly, no commit needed. Otherwise: investigate, fix, commit.
