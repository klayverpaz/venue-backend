# Plan 08 — Bookings Design Doc

**Status:** Approved 2026-04-27.
**Author:** klayver + Claude (brainstorm session).
**Scope:** Plan 08 of the venue-backend roadmap (`docs/superpowers/specs/2026-04-25-venue-backend-design.md` §8). Refines and extends `Booking` aggregate beyond what §5.4 specified.

## 1. Motivation

Decisions §5–§8, §12, §14 of the venue spec define the core booking flow: customers request slot ranges on a resource, owners approve/reject, the platform auto-rejects competing pendings on approval, payments stay off-platform, and idempotency must prevent double-clicks creating duplicate pendings. §6 of the canonical spec lays out the lifecycle and concurrency primitives (Postgres advisory lock + `btree_gist` exclusion constraint). Plan 08 implements all of this end-to-end so Plan 09 (ratings) has approved+ended bookings to gate against.

This refinement deviates from canonical §3 #14 + §5.4 in three places (all approved during brainstorming):

- **`Idempotency-Key` infrastructure dropped.** Replaced by domain-level natural dedup: `RequestBookingHandler` rejects with `BookingAlreadyExists` (409) when the same customer already has a `PENDING` or `APPROVED` booking that overlaps the requested slot on the same resource. State-machine idempotency handles the approve/reject/cancel paths. Saves one table + middleware with no protection regression for the MVP threat model (double-click, mobile retry, load-balancer retry).
- **`Booking.cancelled_by` field dropped.** Derivable from `status_history[-1]` when `status == CANCELLED`. YAGNI to duplicate.
- **Owner cancellation reason kept optional.** Spec §5.4 invariants didn't require it; brainstorm option A (require on owner-cancels-APPROVED) was rejected for option B (always optional, frontend may encourage). Backend never enforces.

## 2. Scope

### In scope

- `BookingStatus` enum (`app/domain/bookings/booking_status.py`): `PENDING | APPROVED | REJECTED | CANCELLED | EXPIRED`.
- `StatusChange` composite VO (`app/domain/bookings/status_change.py`): immutable audit record.
- `Booking` aggregate (`app/domain/bookings/booking.py`): factory, mutators (`approve`, `reject`, `cancel`, `expire`), `slot_count(slot_duration_minutes)` derived helper.
- `IBookingRepository` Protocol (`app/domain/bookings/repository.py`): `add`, `get_by_id`, `list_by_customer`, `list_pending_overlapping`, `list_by_resource_in_range`, `list_pending_expired`, `update`.
- `IBookingLockService` Protocol (`app/domain/bookings/lock.py`): `acquire_for_resource(resource_id) -> AsyncContextManager`. Production adapter wraps Postgres advisory lock; test/SQLite adapter is `asyncio.Lock` per resource_id.
- `Resource.compute_price(slot_range) -> Money` — Plan 06 retroactive: new method on the Resource aggregate that iterates slot-by-slot in the resource's local timezone, applies matching `PricingRule`, falls back to `base_price_cents` per slot. Frozen onto `Booking.total_price_cents` at request time.
- Use cases in `app/use_cases/bookings/`:
  - `commands/request_booking.py` → `RequestBookingHandler`
  - `commands/approve_booking.py` → `ApproveBookingHandler` (auto-rejects competing pendings in the same DB transaction)
  - `commands/reject_booking.py` → `RejectBookingHandler` (owner manual reject)
  - `commands/cancel_booking.py` → `CancelBookingHandler` (branches on actor role; enforces customer cutoff)
  - `commands/expire_pending_bookings.py` → `ExpirePendingBookingsHandler` (cron entry-point)
  - `queries/list_my_bookings.py` (customer)
  - `queries/get_my_booking.py` (customer)
  - `queries/list_resource_bookings.py` (owner)
  - `queries/get_agenda.py` (shared shape; behavior switches on actor_role for response detail)
- Persistence: `BookingModel` declarative mapping in `app/infrastructure/db/mappings/booking.py`; `bookings` table; Alembic migration with conditional Postgres-only `btree_gist` exclusion constraint.
- Concurrency primitives: Postgres advisory lock service + Postgres exclusion constraint (production); in-memory async lock + Python-level overlap check (tests/SQLite).
- API in `app/api/v1/me_bookings/` (customer + owner mutations + reads), `app/api/v1/me_resources/` extension (per-resource booking list + agenda), `app/api/v1/public_resources/` extension (public agenda).
- Cron entry-point at `app/jobs/expire_pending_bookings.py` (`python -m app.jobs.expire_pending_bookings`); suggested schedule hourly. Reuses Plan 07's `PersistentNotificationService` to dispatch `BOOKING_REJECTED`.
- Plan 06 follow-ups absorbed: soft-delete of a `Resource` now auto-rejects its own `PENDING` bookings via the new `IBookingRepository` (Plan 06 task list explicitly deferred this hook).
- Stable error codes registered in `app/api/error_codes.py` + arch test allowlist + pt-BR translations.
- Test coverage: unit (domain + handlers), integration (SQLAlchemy repo + lock service against SQLite), e2e (happy path, competing approval, past-cutoff cancel, INACTIVE owner can't approve, cron expiry, agenda).
- Canonical spec refresh (`docs/superpowers/specs/2026-04-25-venue-backend-design.md` §3 #14, §4.2 cross-feature handlers, §5.4 invariants, §8 Plan 08 description) capturing the dropped `Idempotency-Key` decision and the `cancelled_by` removal.

### Out of scope

- **`Idempotency-Key` table + middleware.** Replaced by natural dedup at the handler level. If a future plan adds payment endpoints, that plan can introduce a generic idempotency layer.
- **`max_consecutive_slots` field on `Resource`.** Owner rejects pathological requests manually for MVP. If abuse becomes real in production, add later.
- **Required cancellation reason on any state transition.** All `reason: str | None` fields are optional. Frontend is responsible for prompting.
- **Holiday / schedule exception calendar.** Bookings are validated against `Resource.operating_hours` only. Out of scope per canonical §10.
- **Booking modification (edit slot range, customer_note).** Customer can only cancel + create-new. Owner cannot edit. Out of scope.
- **Push / WebSocket / SSE.** Inbox stays poll-based via `GET /v1/me/notifications` (Plan 07).
- **Booking transfer between customers.** Out of scope.
- **Concurrent approvals across different resources by the same owner.** Each lock is per `resource_id`; multi-resource approvals don't conflict and don't need cross-resource locks.

## 3. Domain shape

### 3.1 `BookingStatus` enum

`app/domain/bookings/booking_status.py`:

```python
from __future__ import annotations
from enum import Enum


class BookingStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"

    def is_active(self) -> bool:
        """Used by natural dedup: only PENDING and APPROVED count as 'active'."""
        return self in {BookingStatus.PENDING, BookingStatus.APPROVED}

    def is_terminal(self) -> bool:
        return self in {
            BookingStatus.REJECTED, BookingStatus.CANCELLED, BookingStatus.EXPIRED,
        }
```

### 3.2 `StatusChange` composite VO

`app/domain/bookings/status_change.py`:

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
            from_status=from_status, to_status=to_status,
            actor_id=actor_id, actor_role=actor_role, at=at, reason=reason,
        ))


def _is_valid_transition(from_s: BookingStatus, to_s: BookingStatus) -> bool:
    """Enforces the §6.1 state machine."""
    valid: dict[BookingStatus, set[BookingStatus]] = {
        BookingStatus.PENDING: {
            BookingStatus.APPROVED, BookingStatus.REJECTED,
            BookingStatus.CANCELLED, BookingStatus.EXPIRED,
        },
        BookingStatus.APPROVED: {BookingStatus.CANCELLED},
    }
    return to_s in valid.get(from_s, set())
```

**Why `reason` stays as raw `str | None`:** spec §5.4 explicitly notes "not VO-wrapped (audit field)". Bumping into 500 char limit is the only invariant; encoded as a class constant.

### 3.3 `Booking` aggregate

`app/domain/bookings/booking.py`:

```python
@dataclass(slots=True, kw_only=True)
class Booking(BaseEntity):
    resource_id: UUID
    customer_id: UUID
    slot_range: DateTimeRange
    status: BookingStatus
    total_price_cents: Money
    customer_note: ShortDescription | None
    _status_history: tuple[StatusChange, ...] = ()

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
            to_status=BookingStatus.APPROVED, actor_id=actor_id,
            actor_role=Role.OWNER, now=now, reason=None,
        )

    def reject(
        self, *, actor_id: UUID, now: datetime,
        reason: str | None = None,
    ) -> Result[None]:
        return self._transition(
            to_status=BookingStatus.REJECTED, actor_id=actor_id,
            actor_role=Role.OWNER, now=now, reason=reason,
        )

    def cancel(
        self, *, actor_id: UUID, actor_role: Role, now: datetime,
        reason: str | None = None,
    ) -> Result[None]:
        return self._transition(
            to_status=BookingStatus.CANCELLED, actor_id=actor_id,
            actor_role=actor_role, now=now, reason=reason,
        )

    def expire(self, *, now: datetime) -> Result[None]:
        return self._transition(
            to_status=BookingStatus.EXPIRED, actor_id=self.customer_id,
            actor_role=Role.CUSTOMER, now=now,
            reason="slot_start_passed_with_no_decision",
        )

    def _transition(
        self, *, to_status: BookingStatus, actor_id: UUID,
        actor_role: Role, now: datetime, reason: str | None,
    ) -> Result[None]:
        change_r = StatusChange.create(
            from_status=self.status, to_status=to_status,
            actor_id=actor_id, actor_role=actor_role,
            at=now, reason=reason,
        )
        if change_r.is_failure:
            return Result.from_failure(change_r)
        self.status = to_status
        self._status_history = (*self._status_history, change_r.value)
        self.updated_at = now
        return Result.success(None)
```

**Invariants**
- `status_history` is append-only; mutators only ever extend it.
- `slot_range` (a `DateTimeRange`) already enforces `start_at < end_at`, both tz-aware UTC.
- Slot grid alignment, operating-hours containment, and `slot_count >= 1` are NOT validated on the aggregate itself — they require `Resource` context. The `RequestBookingHandler` validates them before calling `create_pending`.
- `total_price_cents` is computed once at request time via `Resource.compute_price(slot_range)`; never recomputed.
- `_status_history` starts empty: the initial PENDING state is implicit from `created_at` + `status`. First transition appends the first `StatusChange`.

**`status_history` initial state.** Empty tuple. Saves a synthetic "creation" `StatusChange` row with no semantic value (the booking row's `created_at` + `status=PENDING` is the source of truth for "when did this come into existence as PENDING"). `StatusChange` requires a non-None `from_status`; modeling creation as a transition would force a synthetic enum value or nullable field.

### 3.4 `IBookingRepository` Protocol

`app/domain/bookings/repository.py`:

```python
class IBookingRepository(Protocol):
    async def add(self, booking: Booking) -> Result[None]: ...

    async def get_by_id(self, booking_id: UUID) -> Result[Booking | None]: ...
    """Returns the booking regardless of customer. Handlers apply scoping."""

    async def list_by_customer(
        self, customer_id: UUID, *,
        status: BookingStatus | None,
        page: int, page_size: int,
    ) -> Result[list[Booking]]: ...

    async def list_pending_overlapping(
        self, resource_id: UUID, slot_range: DateTimeRange,
        *, exclude_booking_id: UUID | None = None,
    ) -> Result[list[Booking]]: ...
    """Used by ApproveBookingHandler to find competitors and by
    RequestBookingHandler natural-dedup pre-check."""

    async def list_active_by_customer_for_resource(
        self, customer_id: UUID, resource_id: UUID,
        slot_range: DateTimeRange,
    ) -> Result[list[Booking]]: ...
    """Natural dedup: returns this customer's PENDING/APPROVED bookings on
    this resource that overlap the slot_range."""

    async def list_by_resource(
        self, resource_id: UUID, *,
        status: BookingStatus | None,
        page: int, page_size: int,
    ) -> Result[list[Booking]]: ...

    async def list_in_range_for_resource(
        self, resource_id: UUID, range_start: datetime, range_end: datetime,
    ) -> Result[list[Booking]]: ...
    """Used by GetAgendaHandler — pulls all bookings that intersect [start, end]
    for the resource, regardless of status; the handler decides what to surface."""

    async def list_pending_with_start_before(
        self, cutoff: datetime,
    ) -> Result[list[Booking]]: ...
    """Used by ExpirePendingBookingsHandler cron."""

    async def list_pending_for_resource(
        self, resource_id: UUID,
    ) -> Result[list[Booking]]: ...
    """Used by Resource soft-delete handler (Plan 06 follow-up) to auto-reject
    pendings."""

    async def update(self, booking: Booking) -> Result[None]: ...
```

### 3.5 `IBookingLockService` Protocol

`app/domain/bookings/lock.py`:

```python
class IBookingLockService(Protocol):
    def acquire_for_resource(
        self, resource_id: UUID,
    ) -> AbstractAsyncContextManager[None]: ...
    """Async context manager that blocks until the per-resource_id lock is
    held, releases on exit. Implementation is dialect-specific:

    - Postgres adapter: pg_advisory_xact_lock(hash(resource_id)) — released
      automatically at TX commit/rollback.
    - In-memory adapter (SQLite, tests): asyncio.Lock keyed by resource_id in
      a module-level dict. Single-process only; sufficient for test isolation.
    """
```

### 3.6 `Resource.compute_price` — Plan 06 retroactive

`app/domain/resources/resource.py` gains a new method:

```python
def compute_price(self, slot_range: DateTimeRange) -> Money:
    """Sum of per-slot prices over slot_range. Iterates slot-by-slot in this
    resource's local timezone, applies the matching PricingRule (weekday +
    time-of-day), falls back to base_price_cents per slot.

    Caller MUST ensure slot_range is grid-aligned and contained in operating
    hours; this method does not validate.
    """
    slot_minutes = self.slot_duration_minutes.minutes
    tz = self.timezone.to_zoneinfo()   # existing IanaTimezone helper (Plan 06)
    total_cents = 0
    cursor = slot_range.start_at
    while cursor < slot_range.end_at:
        local = cursor.astimezone(tz)
        weekday = Weekday.from_iso(local.isoweekday())
        time_of_day = local.time()
        rule = next(
            (r for r in self._pricing_rules
             if weekday in r.weekdays
             and r.window.start <= time_of_day < r.window.end),
            None,
        )
        slot_cents = rule.price.cents if rule else self.base_price_cents.cents
        total_cents += slot_cents
        cursor += timedelta(minutes=slot_minutes)
    return Money.create(total_cents).value  # always succeeds: sum of valid Money
```

`IanaTimezone.to_zoneinfo()` already exists (Plan 06 shipped it). No change needed there.

`Weekday.from_iso(iso_weekday: int)` is a small class method to add: maps Python's `datetime.isoweekday()` (1=Monday … 7=Sunday) to the `Weekday` enum. Implemented as `return _ISO_TO_WEEKDAY[iso_weekday]` with a module-level dict.

## 4. Persistence

The project uses **declarative SQLAlchemy 2.x ORM** (`Base`/`TimestampMixin`) per the established convention. Repositories translate between `Booking` (domain) and `BookingModel` (ORM) via `_to_model_kwargs` / `_to_entity` helpers, mirroring `SQLAlchemyResourceRepository`.

### 4.1 `bookings` table

| Column | SQLAlchemy type | Constraints |
|---|---|---|
| `id` | `CHAR(36)` | PK |
| `resource_id` | `CHAR(36)` | NOT NULL, FK `resources.id` ON DELETE RESTRICT |
| `customer_id` | `CHAR(36)` | NOT NULL, FK `users.id` ON DELETE RESTRICT |
| `slot_start_at` | `DateTime(timezone=True)` | NOT NULL |
| `slot_end_at` | `DateTime(timezone=True)` | NOT NULL |
| `status` | `Text` | NOT NULL |
| `customer_note` | `Text` | nullable |
| `total_price_cents` | `BigInteger` | NOT NULL |
| `status_history` | `JSON` | NOT NULL, default `[]` |
| `created_at` | `DateTime(timezone=True)` | NOT NULL (`TimestampMixin`) |
| `updated_at` | `DateTime(timezone=True)` | NOT NULL (`TimestampMixin`) |

**Slot range stored as two columns** (`slot_start_at`, `slot_end_at`) rather than as a Postgres `tstzrange` type — keeps mapping portable to SQLite for tests. The exclusion constraint constructs `tstzrange(slot_start_at, slot_end_at, '[)')` inline in production.

**Indexes (declarative):**
- `idx_bookings_customer_status_created` on `(customer_id, status, created_at DESC)` — `GET /me/bookings?status=` listing.
- `idx_bookings_resource_status_start` on `(resource_id, status, slot_start_at)` — agenda query + approval transaction's competitor scan.
- `idx_bookings_pending_start` on `(slot_start_at)` `WHERE status = 'PENDING'` — partial index, Postgres only; the cron query.

**Foreign keys** match Plan 06 `ResourceModel.owner_id` precedent (FK with `ON DELETE RESTRICT`). Booking rows are audit-relevant and must never orphan after user/resource cascade.

### 4.2 Mapping

`app/infrastructure/db/mappings/booking.py`:

```python
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

Registered in `app/migrations/env.py` and `tests/integration/conftest.py` mapping import lists.

### 4.3 Migration

`make migrate-new msg="bookings_table"` generates a new revision. The file:

1. Creates the table + 3 indexes.
2. Conditionally on Postgres only:
   - `CREATE EXTENSION IF NOT EXISTS btree_gist`
   - Adds the exclusion constraint:
     ```sql
     ALTER TABLE bookings ADD CONSTRAINT bookings_no_approved_overlap
     EXCLUDE USING gist (
         resource_id WITH =,
         tstzrange(slot_start_at, slot_end_at, '[)') WITH &&
     ) WHERE (status = 'APPROVED')
     ```
3. Down migration drops the constraint (Postgres only), the indexes, then the table.

Pseudocode:

```python
def upgrade() -> None:
    op.create_table("bookings", ...)
    op.create_index(...)
    op.create_index(...)
    op.create_index(
        "idx_bookings_pending_start", "bookings", ["slot_start_at"],
        postgresql_where=text("status = 'PENDING'"),
    )
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
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
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TABLE bookings DROP CONSTRAINT IF EXISTS bookings_no_approved_overlap")
    op.drop_index("idx_bookings_pending_start", table_name="bookings")
    op.drop_index("idx_bookings_resource_status_start", table_name="bookings")
    op.drop_index("idx_bookings_customer_status_created", table_name="bookings")
    op.drop_table("bookings")
```

## 5. Concurrency

### 5.1 `PostgresBookingLockService`

`app/infrastructure/bookings/postgres_lock_service.py`:

```python
class PostgresBookingLockService(IBookingLockService):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @asynccontextmanager
    async def acquire_for_resource(self, resource_id: UUID):
        # Hash UUID to int8 bigint for pg_advisory_xact_lock
        lock_key = self._hash_uuid(resource_id)
        await self._session.execute(
            text("SELECT pg_advisory_xact_lock(:k)"), {"k": lock_key},
        )
        try:
            yield None
        finally:
            # Released automatically at COMMIT/ROLLBACK (xact lock).
            pass

    @staticmethod
    def _hash_uuid(uuid: UUID) -> int:
        return int.from_bytes(uuid.bytes[:8], "big", signed=True)
```

### 5.2 `InMemoryBookingLockService`

`app/infrastructure/bookings/in_memory_lock_service.py`:

```python
class InMemoryBookingLockService(IBookingLockService):
    """asyncio.Lock per resource_id in a process-local dict. Sufficient for
    SQLite-backed integration tests and unit tests; NOT suitable for prod."""

    def __init__(self) -> None:
        self._locks: dict[UUID, asyncio.Lock] = {}

    @asynccontextmanager
    async def acquire_for_resource(self, resource_id: UUID):
        lock = self._locks.setdefault(resource_id, asyncio.Lock())
        async with lock:
            yield None
```

DI factory selects by dialect (or env): production uses `PostgresBookingLockService`; tests get `InMemoryBookingLockService`.

### 5.3 Approval transaction (per spec §6.2)

`ApproveBookingHandler.handle` body, in order:

```python
async with self._lock.acquire_for_resource(target.resource_id):
    target_r = await self._bookings.get_by_id(cmd.booking_id)
    target = target_r.value
    if target is None:
        return Result.failure("BookingNotFound", status_code=404)
    resource_r = await self._resources.get_by_id(target.resource_id)
    resource = resource_r.value
    if resource is None or resource.is_deleted():
        return Result.failure("BookingNotFound", status_code=404)
    if resource.owner_id != cmd.actor_id:
        return Result.failure("BookingNotFound", status_code=404)  # no leak
    if target.status is not BookingStatus.PENDING:
        return Result.failure("BookingInvalidStateTransition", status_code=409)

    sub_r = await self._subscriptions.get_by_owner_id(resource.owner_id)
    if not sub_r.value or not sub_r.value.is_operational():
        return Result.failure("OwnerSubscriptionInactive", status_code=403)

    competitors_r = await self._bookings.list_pending_overlapping(
        target.resource_id, target.slot_range, exclude_booking_id=target.id,
    )
    competitors = competitors_r.value

    target.approve(actor_id=cmd.actor_id, now=_utcnow())
    await self._bookings.update(target)
    for comp in competitors:
        comp.reject(
            actor_id=cmd.actor_id, now=_utcnow(),
            reason="auto_rejected_competing_request",
        )
        await self._bookings.update(comp)
    # All in same transaction (caller wraps via FastAPI dep).

# Outside lock + outside TX: dispatch notifications.
await self._notifications.notify(
    recipient_id=target.customer_id,
    kind=NotifKind.BOOKING_APPROVED,
    payload={"booking_id": str(target.id), "resource_id": str(resource.id)},
)
for comp in competitors:
    await self._notifications.notify(
        recipient_id=comp.customer_id,
        kind=NotifKind.BOOKING_REJECTED,
        payload={
            "booking_id": str(comp.id), "resource_id": str(resource.id),
            "reason": "auto_rejected_competing_request",
        },
    )
return Result.success(BookingDto.from_entity(target))
```

The advisory lock ensures only one approval transaction proceeds per resource at a time. The exclusion constraint is the safety net: if the lock is ever bypassed (bug, alternate code path), the constraint rejects an `INSERT/UPDATE` to `APPROVED` that would overlap an existing approved booking.

## 6. Use cases

### 6.1 `RequestBookingHandler` (customer)

Signature:

```python
@dataclass(frozen=True, kw_only=True, slots=True)
class RequestBookingCommand:
    actor_id: UUID  # customer
    resource_id: UUID
    slot_start_at: datetime
    slot_end_at: datetime
    customer_note: str | None
```

Flow (errors short-circuit; multi-error envelope only for VO-level validations on the input):

1. **VO-validate inputs** (`DateTimeRange.create`, `ShortDescription.create_if_not_empty`). Aggregate via `failure_many` on validation failures.
2. Load `Resource` by id (404 `ResourceNotFound` if missing OR `deleted_at != NULL`).
3. **Gating (option A from brainstorm):** reject with 404 `ResourceNotPublished` if `resource.is_published is False`. Reject with 404 `ResourceNotPublished` if owner subscription is not operational (`OwnerSubscriptionInactive` semantically but use 404 to not reveal owner state — same 404 code as unpublished).
4. Validate `slot_range.start_at > now` (`BookingSlotInPast` 422).
5. Validate slot-grid alignment: `(start_minutes_local % slot_duration) == 0` AND `(duration % slot_duration) == 0` (`BookingSlotNotAligned` 422). `start_minutes_local` is `slot_start_at` converted to resource's local timezone, then `hour*60 + minute`.
6. Validate operating hours: for each weekday the slot spans (1 or 2), check that the local-time portion is contained in some operating-hours window (`BookingOutsideOperatingHours` 422).
7. **Natural dedup:** `list_active_by_customer_for_resource(customer_id, resource_id, slot_range)`. If non-empty → `BookingAlreadyExists` (409) with the existing booking's id in the response details for the frontend to surface.
8. Compute `total_price_cents` via `resource.compute_price(slot_range)`.
9. `Booking.create_pending(...)`.
10. `await self._bookings.add(booking)`.
11. Notify owner: `notify(recipient_id=resource.owner_id, kind=BOOKING_REQUESTED, payload={booking_id, resource_id, slot_range})`.
12. Return `Result.success(BookingDto.from_entity(booking))`.

### 6.2 `ApproveBookingHandler` (owner)

Already detailed in §5.3.

### 6.3 `RejectBookingHandler` (owner)

Owner-initiated reject of a `PENDING`. No competitor scan, no lock necessary (state machine handles concurrent rejects: second one fails with `BookingInvalidStateTransition`).

```python
async def handle(self, cmd: RejectBookingCommand) -> Result[BookingDto]:
    booking_r = await self._bookings.get_by_id(cmd.booking_id)
    booking = booking_r.value
    if booking is None:
        return Result.failure("BookingNotFound", status_code=404)
    resource_r = await self._resources.get_by_id(booking.resource_id)
    resource = resource_r.value
    if resource is None or resource.owner_id != cmd.actor_id:
        return Result.failure("BookingNotFound", status_code=404)
    transition_r = booking.reject(
        actor_id=cmd.actor_id, now=_utcnow(), reason=cmd.reason,
    )
    if transition_r.is_failure:
        return Result.failure("BookingInvalidStateTransition", status_code=409)
    update_r = await self._bookings.update(booking)
    if update_r.is_failure:
        return Result.from_failure(update_r)
    await self._notifications.notify(
        recipient_id=booking.customer_id,
        kind=NotifKind.BOOKING_REJECTED,
        payload={
            "booking_id": str(booking.id), "resource_id": str(resource.id),
            "reason": cmd.reason or "owner_rejected",
        },
    )
    return Result.success(BookingDto.from_entity(booking))
```

### 6.4 `CancelBookingHandler` (customer or owner)

Single handler; branches on actor role.

```python
async def handle(self, cmd: CancelBookingCommand) -> Result[BookingDto]:
    booking_r = await self._bookings.get_by_id(cmd.booking_id)
    booking = booking_r.value
    if booking is None:
        return Result.failure("BookingNotFound", status_code=404)
    resource_r = await self._resources.get_by_id(booking.resource_id)
    resource = resource_r.value
    if resource is None:
        return Result.failure("BookingNotFound", status_code=404)

    is_customer = booking.customer_id == cmd.actor_id
    is_owner = resource.owner_id == cmd.actor_id
    if not (is_customer or is_owner):
        return Result.failure("BookingNotFound", status_code=404)

    if is_customer and not is_owner:
        # Customer cancellation enforces cutoff.
        cutoff_hours = resource.customer_cancellation_cutoff_hours.hours
        if _utcnow() >= booking.slot_range.start_at - timedelta(hours=cutoff_hours):
            return Result.failure(
                "BookingCancellationPastCutoff", status_code=403,
            )

    actor_role = Role.OWNER if is_owner else Role.CUSTOMER
    transition_r = booking.cancel(
        actor_id=cmd.actor_id, actor_role=actor_role,
        now=_utcnow(), reason=cmd.reason,
    )
    if transition_r.is_failure:
        return Result.failure("BookingInvalidStateTransition", status_code=409)
    await self._bookings.update(booking)

    # Notify counterpart.
    counterpart_id = (
        resource.owner_id if is_customer else booking.customer_id
    )
    await self._notifications.notify(
        recipient_id=counterpart_id,
        kind=NotifKind.BOOKING_CANCELLED,
        payload={
            "booking_id": str(booking.id), "resource_id": str(resource.id),
            "cancelled_by": actor_role.value,
        },
    )
    return Result.success(BookingDto.from_entity(booking))
```

**Owner-acting-as-customer edge case:** if the same user is both the resource owner AND the booking's customer (unusual but possible: an owner books their own resource), `is_owner = True` wins, no cutoff applied. Fine.

### 6.5 `ExpirePendingBookingsHandler` (cron)

```python
@dataclass(frozen=True, slots=True)
class ExpirePendingBookingsCommand:
    pass

class ExpirePendingBookingsHandler:
    def __init__(
        self, bookings: IBookingRepository,
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
            transition_r = booking.expire(now=now)
            if transition_r.is_failure:
                continue   # state changed under us; skip
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

Cron entry-point at `app/jobs/expire_pending_bookings.py` mirrors the existing `expire_trialing_subscriptions` script: `init_engine` → loop session → instantiate handler with real repos + `PersistentNotificationService` → `await handler.handle(...)` → log count → `dispose_engine`. Suggested cron schedule: hourly (`0 * * * *`).

### 6.6 `ListMyBookingsHandler` (customer)

```python
@dataclass(frozen=True, kw_only=True, slots=True)
class ListMyBookingsQuery:
    actor_id: UUID
    status: BookingStatus | None = None
    page: int = 1
    page_size: int = 50

# Returns BookingListDto (items + total_count or has_more).
```

Page-based pagination (max page_size=100), matching the rest of the API. Repo offset/limit query.

### 6.7 `GetMyBookingHandler` (customer)

`get_by_id` + scoping check (`booking.customer_id == actor_id`). Mismatch → `BookingNotFound` (404, no leak).

### 6.8 `ListBookingsForResourceHandler` (owner)

`get_by_id` resource → verify `owner_id == actor_id` (else `ResourceNotFound`) → `list_by_resource(resource_id, status?, page, page_size)`.

### 6.9 `GetAgendaHandler` (shared shape)

```python
@dataclass(frozen=True, kw_only=True, slots=True)
class GetAgendaQuery:
    resource_id: UUID | None = None       # mutually exclusive with resource_slug
    resource_slug: str | None = None
    range_start: datetime                  # inclusive, UTC
    range_end: datetime                    # exclusive, UTC
    actor_id: UUID | None = None           # None → public; set → owner detail level
```

Behavior:

1. Resolve resource (by id for owner path, by slug for public).
2. If actor present and is owner → owner detail level (returns booking ids per slot). Else public.
3. Enforce `(range_end - range_start) <= 31 days` (`AgendaRangeTooWide` 422). Prevents abusive scans.
4. `list_in_range_for_resource(resource_id, range_start, range_end)` — returns ALL bookings (any status) intersecting the range.
5. Generate the slot grid: for each day in `[range_start.date(), range_end.date()]` (in resource's local timezone), iterate operating-hours windows, yield slots of `slot_duration_minutes`.
6. Annotate each slot:
   - If covered by an `APPROVED` booking → `status=APPROVED`, `price_cents=booking.total_price_cents` for that slot's portion (or just the resource's per-slot computed price; pick once for consistency).
   - Elif covered by ≥1 `PENDING` booking → `status=PENDING`.
   - Else → `status=AVAILABLE`, `price_cents=resource.compute_price(slot_range_of_one_slot)`.
7. Owner response includes `booking_id` and `customer_id` per occupied slot; public response does not.

**Pricing in agenda:** computed per-slot via `resource.compute_price(...)`. Booking's frozen price is NOT used for agenda display — the agenda always reflects current pricing rules. (Frozen price applies only to the booking's own checkout-style detail view.)

### 6.10 `SoftDeleteResourceHandler` extension (Plan 06 retroactive)

Existing `DeleteResourceHandler` (Plan 06) gets an `IBookingRepository` injection. Before flipping `deleted_at`:

1. Fetch `list_pending_for_resource(resource_id)` and `list_approved_with_start_after(resource_id, now)`.
2. If any approved future bookings → reject the delete with `ResourceHasFutureApprovedBookings` (409, new code).
3. Otherwise, for each pending booking:
   - `booking.cancel(actor_id=owner_id, actor_role=OWNER, now=now, reason="resource_deleted")` (cancel, not reject — distinct semantic).
   - Persist + notify customer (`BOOKING_CANCELLED` with reason).
4. Then proceed with the existing soft-delete.

Plan 06 already shipped the soft-delete plumbing without this hook (per its task list). Plan 08 adds the hook + tests.

## 7. API surface

All endpoints under `/api/v1/`. JWT auth except where noted. Page-based pagination on lists (`?page=&page_size=`, max 100).

### 7.1 Customer endpoints (`role=CUSTOMER`)

```
POST   /v1/me/bookings
  body: { resource_id: UUID, slot_start_at, slot_end_at, customer_note? }
  201: BookingResponse
  404 ResourceNotFound | ResourceNotPublished
  409 BookingAlreadyExists (with details.existing_booking_id)
  422 BookingSlotInPast | BookingSlotNotAligned | BookingOutsideOperatingHours | ValidationFailed

GET    /v1/me/bookings?status=&page=&page_size=
  200: BookingListResponse

GET    /v1/me/bookings/{id}
  200: BookingResponse
  404 BookingNotFound

POST   /v1/me/bookings/{id}/cancel
  body: { reason? }
  200: BookingResponse
  403 BookingCancellationPastCutoff
  404 BookingNotFound
  409 BookingInvalidStateTransition
```

### 7.2 Owner endpoints (`role=OWNER`)

```
GET    /v1/me/resources/{resource_id}/bookings?status=&page=&page_size=
  200: BookingListResponse
  404 ResourceNotFound

GET    /v1/me/resources/{resource_id}/agenda?from=&to=
  200: OwnerAgendaResponse
  404 ResourceNotFound
  422 AgendaRangeTooWide

POST   /v1/me/bookings/{id}/approve
  201: BookingResponse
  403 OwnerSubscriptionInactive
  404 BookingNotFound
  409 BookingInvalidStateTransition | BookingHasApprovedOverlap (extreme race; constraint kicked in)

POST   /v1/me/bookings/{id}/reject
  body: { reason? }
  200: BookingResponse
  404 BookingNotFound
  409 BookingInvalidStateTransition

POST   /v1/me/bookings/{id}/cancel  (same path as customer; handler branches on actor role)
  body: { reason? }
  200: BookingResponse
  404 BookingNotFound
  409 BookingInvalidStateTransition
```

### 7.3 Public endpoint (no auth)

```
GET    /v1/resources/{owner_slug}/{resource_slug}/agenda?from=&to=
  200: PublicAgendaResponse  (no booking ids; status: AVAILABLE | PENDING | APPROVED + price_cents)
  404 ResourceNotFound
  422 AgendaRangeTooWide
```

The public agenda path is namespaced under the existing `/v1/resources/{owner_slug}/{resource_slug}` shape established by Plan 06's public resource page.

### 7.4 Routes file structure

```
app/api/v1/me_bookings/
├── __init__.py                empty
├── deps.py                    DI providers
├── routes.py                  customer + owner mutation routes
└── schemas.py                 Pydantic request/response models

app/api/v1/me_resources/       (modified — Plan 06 routes already exist)
└── routes.py                  +GET /me/resources/{id}/bookings
                                +GET /me/resources/{id}/agenda

app/api/v1/public_resources/   (modified — Plan 06 routes already exist)
└── routes.py                  +GET /v1/resources/{owner_slug}/{resource_slug}/agenda
```

`app/api/v1/router.py` adds `api_router.include_router(me_bookings_router)`.

## 8. Stable error codes

New codes registered in `app/api/error_codes.py` + arch test allowlist + pt-BR translations:

| Code | HTTP | pt-BR |
|---|---|---|
| `BookingNotFound` | 404 | `Reserva não encontrada.` |
| `ResourceNotPublished` | 404 | `Recurso indisponível para reserva.` |
| `OwnerSubscriptionInactive` | 403 | `Proprietário não pode aprovar reservas no momento.` |
| `BookingSlotInPast` | 422 | `Não é possível reservar horário passado.` |
| `BookingSlotNotAligned` | 422 | `Horário não alinhado à grade de slots.` |
| `BookingOutsideOperatingHours` | 422 | `Horário fora do funcionamento do recurso.` |
| `BookingAlreadyExists` | 409 | `Você já tem uma reserva ativa para esse horário.` |
| `BookingInvalidStateTransition` | 409 | `Transição de estado de reserva inválida.` |
| `BookingCancellationPastCutoff` | 403 | `Prazo de cancelamento expirado.` |
| `BookingHasApprovedOverlap` | 409 | `Horário já tem reserva aprovada.` |
| `AgendaRangeTooWide` | 422 | `Intervalo da agenda excede o máximo de 31 dias.` |
| `ResourceHasFutureApprovedBookings` | 409 | `Recurso possui reservas aprovadas futuras.` |
| `StatusChangeAtNotTzAware` | (entity-level; programming bug) | `Timestamp de mudança precisa ter fuso horário.` |
| `StatusChangeReasonTooLong` | (entity-level) | `Motivo excede 500 caracteres.` |
| `StatusChangeInvalidTransition` | (entity-level — propagates to handler `BookingInvalidStateTransition`) | `Transição de estado inválida.` |
| `BookingSlotCountTooLow` | 422 | `Reserva precisa ter ao menos um slot.` |

## 9. Testing strategy

| Level | Path | Coverage |
|---|---|---|
| Unit (domain) | `tests/unit/domain/bookings/test_booking_status.py` | `is_active`, `is_terminal` |
| Unit (domain) | `tests/unit/domain/bookings/test_status_change.py` | `create` validates tzinfo, reason length, transition matrix |
| Unit (domain) | `tests/unit/domain/bookings/test_booking.py` | `create_pending`, transitions append `StatusChange`, invalid transitions return failure, `slot_count` math |
| Unit (domain) | `tests/unit/domain/resources/test_resource_compute_price.py` | Plan 06 retroactive: pricing rule match, fallback, multi-slot, weekday switch, edge of window |
| Unit (use cases) | `tests/unit/use_cases/bookings/commands/...` | All 5 mutation handlers with `InMemoryBookingRepository` + `InMemoryBookingLockService` + Plan 07's `FakeNotificationService` (renamed/copied as `FakeNotificationService` for bookings tests) |
| Unit (use cases) | `tests/unit/use_cases/bookings/queries/...` | List/get/agenda with in-memory repo |
| Integration | `tests/integration/bookings/test_booking_repository.py` | SQL round-trip, status-history JSON serialization, status-filtered listing, `list_pending_overlapping`, `list_pending_with_start_before` |
| Integration | `tests/integration/bookings/test_in_memory_lock_service.py` | Two concurrent `acquire_for_resource` on same id serialize; on different ids do not |
| E2E | `tests/e2e/bookings/test_happy_path.py` | Customer requests → owner approves → notification appears in customer inbox → both can view |
| E2E | `tests/e2e/bookings/test_competing_approval.py` | Two customers PENDING same slot; owner approves one; the other is REJECTED with `auto_rejected_competing_request` reason; both inboxes get correct notifications |
| E2E | `tests/e2e/bookings/test_cancellation_cutoff.py` | Customer cancel within cutoff = OK; past cutoff = 403 |
| E2E | `tests/e2e/bookings/test_inactive_owner_cannot_approve.py` | Admin INACTIVE owner; owner attempts approve → 403 OwnerSubscriptionInactive |
| E2E | `tests/e2e/bookings/test_natural_dedup.py` | Customer POSTs same booking twice → second returns 409 BookingAlreadyExists |
| E2E | `tests/e2e/bookings/test_agenda.py` | Public agenda shape; owner agenda includes booking_id; PENDING + APPROVED slot statuses |
| E2E | `tests/e2e/bookings/test_cron_expiry.py` | Pending booking with `slot_start_at < now` → cron handler transitions it to EXPIRED + sends notification |
| E2E | `tests/e2e/bookings/test_resource_delete_cascades_pendings.py` | Plan 06 hook: soft-deleting a resource cancels its PENDINGs |
| Architecture | (existing) | New stable codes added to allowlist; pt-BR coverage check stays green |

In-memory test fakes:
- `tests/unit/use_cases/bookings/fakes/in_memory_booking_repository.py`
- `tests/unit/use_cases/bookings/fakes/fake_booking_lock_service.py` (no-op acquire — tests don't need real serialization)

## 10. Plan 06 retroactive items (folded into Plan 08)

- **`Resource.compute_price(slot_range) -> Money` method.** New code on the existing aggregate; tests under `tests/unit/domain/resources/test_resource_compute_price.py`. Documented invariant in §3.6.
- **`Weekday.from_iso(iso_weekday)` helper** + tests. (`IanaTimezone.to_zoneinfo()` already exists from Plan 06; reused as-is.)
- **`SoftDeleteResourceHandler` gains `IBookingRepository` injection** + auto-cancel of pending bookings + 409 if approved future bookings exist. Plan 06 explicitly deferred this hook to Plan 08.
- **Canonical spec refresh** (`docs/superpowers/specs/2026-04-25-venue-backend-design.md`): §5.3 invariant about soft-delete blocking gets refined to mention "auto-cancels pendings; rejects if approved future bookings exist".

## 11. Canonical spec refresh deliverable

Plan 08 ships a doc-only commit refreshing the canonical venue-backend-design.md, parallel to Plan 06 task 38 / Plan 07 task 17:

- **§3 #14** updated to: "Booking creation uses domain-level natural dedup (same customer + resource + overlapping slot already PENDING/APPROVED → 409). Approve/reject/cancel idempotency comes from the state machine. **`Idempotency-Key` infrastructure deferred** — see plan-08-bookings-design.md §1."
- **§4.2** `RequestBookingHandler` row gets the natural-dedup note; no signature change.
- **§5.4** invariants block: drop `cancelled_by` field reference; clarify `status_history` is the audit source of truth.
- **§5.3** soft-delete invariant refined as above.
- **§8 plan 08** description gets the Plan 08 deliverables (lock service, exclusion constraint, cron, agenda, natural dedup).

## 12. Open items (none blocking)

- **Distributed lock for multi-instance deployment.** `pg_advisory_xact_lock` is per-cluster, so multi-instance Postgres deployment shares the lock natively. Multi-cluster (e.g., logical replication, shard) would need rework — out of MVP scope.
- **Agenda price caching.** Current design recomputes price per slot per request. At MVP scale (small resource catalog, modest agenda windows ≤ 31 days) this is fine. If profiling shows `compute_price` on agenda is hot, cache `(resource_id, weekday, time_of_day) → price_cents` per request.
- **Booking modification.** Customer cancel + create-new for now. If a future plan adds "edit slot range", needs to re-validate alignment + operating hours + reset competitor scan.
- **Approve double-click race within the lock window.** Same owner clicks approve twice rapidly: first call holds advisory lock, second waits. First commits, releases. Second acquires, sees `status != PENDING`, returns 409. Safe.
- **EXPIRED notification kind.** Spec §5.6 has only 5 kinds (no `BOOKING_EXPIRED`). The cron uses `BOOKING_REJECTED` with `reason="slot_start_passed_with_no_decision"` so the customer sees a rejection-style notification. Fine for MVP; a future plan could add `BOOKING_EXPIRED` if the UX needs to differentiate.
- **`status_history` size.** Realistic max ~5 entries per booking (PENDING → APPROVED → CANCELLED is common max). JSON column handles indefinitely large lists; no bound enforced.
- **Lock granularity.** Current lock is per-resource. A booking that competes on two resources (theoretical: one bundled package) would need per-(resource_id, slot_range) granularity — out of scope; MVP has 1 resource per booking.
