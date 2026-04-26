# Plan 05 — OwnerSubscription Design Doc

**Status:** Approved 2026-04-26.
**Author:** klayver + Claude (brainstorm session).
**Scope:** Plan 05 of the venue-backend roadmap (`docs/superpowers/specs/2026-04-25-venue-backend-design.md` §8). Refines and extends `OwnerSubscription` aggregate beyond what §5.5 specified.

## 1. Motivation

Decision 9 of the venue spec defines a "soft owner subscription" controlled by admins — `is_operational()` gates whether owner resources appear in public listings (Plan 06) and whether bookings can be approved (Plan 08). This doc nails down the business rules left implicit in §5.5: how subscriptions are created, how trials work, what state transitions admins can perform, what notifications fire, and how the operational gate is consumed.

This refinement deviates from §5.5 in three places (all approved by the user during brainstorming):
- **`notes` field is dropped** — no MVP use case (no billing, no admin-to-owner channel via this field).
- **`trial_ends_at` field is added** — required for the 3-day trial flow.
- **`OwnerSubscription` is auto-created on owner registration** in `TRIALING` status — §5.5 was silent on the lifecycle.

## 2. Scope

### In scope

- `OwnerSubscription` aggregate (`app/domain/subscriptions/owner_subscription.py`) + `SubStatus` enum.
- Auto-create of one `OwnerSubscription{TRIALING}` row per owner registration. Wired into `RegisterUserHandler` via a new `ISubscriptionRepository` dependency. Single transaction with the `User` insert.
- `SetOwnerSubscriptionStatusHandler` (admin-only): any-to-any state transition, idempotent (no-op on same-status POST), emits `SUBSCRIPTION_CHANGED` notification on real changes only.
- `ExpireTrialingSubscriptionsHandler` + cron entry-point script: nightly (or hourly) job that flips `TRIALING → INACTIVE` for subscriptions whose `trial_ends_at < now`. Emits `SUBSCRIPTION_CHANGED`.
- `INotificationService` Protocol introduced in `app/domain/notifications/service.py` (creates the `notifications/` domain package, port-only — Plan 07 fills in the aggregate). `LoggingNotificationService` no-op adapter in `app/infrastructure/notifications/`.
- Endpoints: `GET /v1/admin/subscriptions`, `POST /v1/admin/owners/{owner_id}/subscription`, `GET /v1/me/subscription`.
- Pydantic `Settings.trial_duration_days: int = 3` in `app/core/config.py` (env var `BACKEND_TRIAL_DURATION_DAYS`).
- Stable error codes registered in `ERROR_MESSAGES_PT_BR` + arch test allowlist.
- `is_operational` consumer pattern documented for Plan 06+ to follow.

### Out of scope

- `Notification` aggregate persistence, `IEmailSender` port, e-mail rendering — Plan 07.
- Billing, PSP integration, `payment_failed` events that would set `PAST_DUE` automatically. Decision 9 deferred this.
- Audit log of all status transitions. `status_changed_at` covers the most recent flip; a future plan can add a history table if needed.
- "Extend trial by N days" admin endpoint with custom N. Setting status to `TRIALING` on the existing endpoint already recreates `trial_ends_at` from `now + TRIAL_DURATION_DAYS`. Per-owner custom durations are YAGNI for MVP.
- Cascade behavior between `User.is_active` and `OwnerSubscription.status`. Each aggregate owns its own field; consumers (Plan 06+) compose the two checks. See §7.
- Owner-facing channel through subscription record (the dropped `notes` field). Communication with owners flows through `Notification` typed payloads (Plan 07).

## 3. Aggregate shape

### 3.1 `SubStatus` enum

`app/domain/subscriptions/sub_status.py`:

```python
from enum import Enum

class SubStatus(str, Enum):
    ACTIVE = "ACTIVE"
    TRIALING = "TRIALING"
    PAST_DUE = "PAST_DUE"
    INACTIVE = "INACTIVE"

    def is_operational(self) -> bool:
        return self in {SubStatus.ACTIVE, SubStatus.TRIALING}
```

`PAST_DUE` exists for forward compatibility with future billing integration; in MVP, no automatic transition lands there. Admin can still set it manually.

### 3.2 `OwnerSubscription` aggregate

`app/domain/subscriptions/owner_subscription.py`:

```python
@dataclass(slots=True, kw_only=True)
class OwnerSubscription(BaseEntity):
    OWNER_ID_REQUIRED = "OwnerIdRequired"
    TRIAL_ENDS_AT_REQUIRED_FOR_TRIALING = "TrialEndsAtRequiredForTrialing"
    TRIAL_ENDS_AT_FORBIDDEN_OUTSIDE_TRIALING = "TrialEndsAtForbiddenOutsideTrialing"
    TRIAL_DURATION_DAYS_INVALID = "TrialDurationDaysInvalid"

    owner_id: UUID
    status: SubStatus
    status_changed_at: datetime          # tz-aware UTC
    trial_ends_at: datetime | None = None  # tz-aware UTC; required iff status=TRIALING

    @classmethod
    def create_trialing(
        cls,
        *,
        owner_id: UUID,
        trial_duration_days: int,
        now: datetime,
    ) -> Result[Self]:
        """Factory used by RegisterUserHandler. Validates inputs and emits via
        failure_many. Always TRIALING — other states arrive via transition_to."""
        ...

    def transition_to(
        self,
        new_status: SubStatus,
        *,
        now: datetime,
        trial_duration_days: int,
    ) -> Result[None]:
        """Any-to-any state machine.

        Behavior:
        - If new_status == self.status → Result.success(None) without mutation.
          Idempotent on no-op; status_changed_at is NOT bumped.
        - Otherwise: status, status_changed_at, updated_at are updated.
          - If new_status == TRIALING: trial_ends_at = now + trial_duration_days.
          - If new_status != TRIALING: trial_ends_at = None.

        Validates trial_duration_days > 0 when transitioning to TRIALING.
        """
        ...

    def is_operational(self) -> bool:
        return self.status.is_operational()
```

### 3.3 Cross-field invariants

Enforced in `__post_init__`:

- `status == TRIALING` ⇔ `trial_ends_at is not None`. Both directions (TRIALING without `trial_ends_at` → `TRIAL_ENDS_AT_REQUIRED_FOR_TRIALING`; non-TRIALING with `trial_ends_at` set → `TRIAL_ENDS_AT_FORBIDDEN_OUTSIDE_TRIALING`).
- `trial_ends_at`, when set, must be tz-aware UTC. (Reuse pattern from `DateTimeRange` VO checks.)
- `status_changed_at` must be tz-aware UTC.

### 3.4 Repository Protocol

`app/domain/subscriptions/repository.py`:

```python
from typing import Protocol
from uuid import UUID
from datetime import datetime
from app.domain.shared.result import Result
from app.domain.subscriptions.owner_subscription import OwnerSubscription


class ISubscriptionRepository(Protocol):
    async def add(self, sub: OwnerSubscription) -> Result[None]: ...

    async def update(self, sub: OwnerSubscription) -> Result[None]: ...

    async def get_by_id(self, sub_id: UUID) -> OwnerSubscription | None: ...

    async def get_by_owner_id(self, owner_id: UUID) -> OwnerSubscription | None: ...

    async def list_all(
        self, *, status: str | None = None, limit: int = 50, offset: int = 0,
    ) -> list[OwnerSubscription]: ...

    async def list_trialing_with_expiry_before(
        self, threshold: datetime,
    ) -> list[OwnerSubscription]: ...
```

`add` and `update` return `Result[None]` (consistent with `IUserRepository` / `IResourceTypeRepository` patterns in Plans 02/04). `get_*` and `list_*` return entities or None directly — their caller is the handler, which builds the appropriate `Result`.

### 3.5 Persistence mapping

`app/infrastructure/db/mappings/owner_subscription.py`:

- Table `owner_subscriptions`.
- Columns: `id UUID PK`, `owner_id UUID NOT NULL UNIQUE FK→users.id`, `status TEXT NOT NULL`, `status_changed_at TIMESTAMPTZ NOT NULL`, `trial_ends_at TIMESTAMPTZ NULL`, `created_at TIMESTAMPTZ NOT NULL`, `updated_at TIMESTAMPTZ NOT NULL`.
- Index `idx_owner_subs_status_trial_end` on `(status, trial_ends_at)` for the cron query (`WHERE status='TRIALING' AND trial_ends_at < now()`).
- Foreign key on `owner_id` with `ON DELETE RESTRICT` (users are never hard-deleted per spec).
- Migration via `make migrate-new msg="owner_subscriptions table"`.

## 4. Auto-create on owner registration

`RegisterUserHandler` gains two new dependencies:

```python
class RegisterUserHandler:
    def __init__(
        self,
        users: IUserRepository,
        hasher: IPasswordHasher,
        subscriptions: ISubscriptionRepository,   # NEW
        config: Settings,                         # NEW
    ): ...
```

After `users.add(user)`, when `user.role is Role.OWNER`:

```python
sub_r = OwnerSubscription.create_trialing(
    owner_id=user.id,
    trial_duration_days=self._config.trial_duration_days,
    now=_utcnow(),
)
if sub_r.is_failure:
    return Result.from_failure(sub_r, status_code=500)
await self._subscriptions.add(sub_r.value)
```

**Atomicity:** both repos share the same `AsyncSession` injected by FastAPI deps. The session commits at request end. If `subscriptions.add` raises, the `users.add` is rolled back along with it. No outbox needed — single-DB scenario.

CUSTOMER and ADMIN registrations do NOT create a subscription row. `subscriptions.get_by_owner_id(non_owner)` returns `None`, which is the correct semantics (no subscription exists for non-owners).

## 5. Admin state transitions

### 5.1 Endpoint contract

```
POST /v1/admin/owners/{owner_id}/subscription
Body: { "status": "ACTIVE" | "TRIALING" | "PAST_DUE" | "INACTIVE" }
Auth: requires ADMIN role.
```

Returns 200 with the updated DTO, or 200 with the unchanged DTO on idempotent no-op. 404 if owner missing or not OWNER. 422 if `status` is not a valid `SubStatus`.

### 5.2 `SetOwnerSubscriptionStatusHandler`

Sequence:

1. `users.get_by_id(cmd.owner_id)` → `OwnerNotFound` (404) if `None`.
2. Verify `user.role is Role.OWNER` → `UserIsNotOwner` (422) otherwise. (No reject on `is_active=false` — see §7.)
3. `subscriptions.get_by_owner_id(cmd.owner_id)` → `SubscriptionNotFound` (404) if missing. Defensive — auto-create should always populate it, but a manual data-fix scenario shouldn't crash.
4. `old_status = sub.status`.
5. `sub.transition_to(cmd.status, now=_utcnow(), trial_duration_days=self._config.trial_duration_days)`. Failure here is a domain bug (no business rules can fail in any-to-any), but propagated via `Result.from_failure(...)`.
6. If `old_status == cmd.status`: skip write + skip notify. Return `Result.success(OwnerSubscriptionDto.from_entity(sub))`.
7. Else: `subscriptions.update(sub)` then `notifications.notify(recipient_id=sub.owner_id, kind=NotifKind.SUBSCRIPTION_CHANGED, payload={"old_status": old_status.value, "new_status": cmd.status.value, "reason": "admin_action"})`. Return `Result.success(OwnerSubscriptionDto.from_entity(sub))`.

### 5.3 State machine — any-to-any

Admin can move between any two `SubStatus` values. No transition graph enforcement in MVP; the only invariants are at the aggregate level (§3.3). Rationale (from brainstorming):

- Decision 9 already gives admin total control. A restricted graph adds defensive code without business value at MVP scale.
- The cron uses a separate handler with a narrow contract (TRIALING → INACTIVE only); it does NOT go through `SetOwnerSubscriptionStatusHandler`, so admin and cron flows are decoupled.
- Adding a graph later is non-breaking; removing one is breaking. YAGNI.

## 6. Trial expiry cron

### 6.1 `ExpireTrialingSubscriptionsHandler`

`app/use_cases/subscriptions/commands/expire_trialing_subscriptions.py`:

```python
@dataclass(frozen=True, slots=True)
class ExpireTrialingSubscriptionsCommand:
    pass  # no payload — handler queries internally

class ExpireTrialingSubscriptionsHandler:
    def __init__(
        self,
        subscriptions: ISubscriptionRepository,
        notifications: INotificationService,
        config: Settings,
    ): ...

    async def handle(self, cmd: ExpireTrialingSubscriptionsCommand) -> Result[int]:
        now = _utcnow()
        expired = await self._subscriptions.list_trialing_with_expiry_before(now)
        count = 0
        for sub in expired:
            r = sub.transition_to(
                SubStatus.INACTIVE,
                now=now,
                trial_duration_days=self._config.trial_duration_days,
            )
            if r.is_failure:
                # Should not happen in any-to-any; log + continue.
                continue
            await self._subscriptions.update(sub)
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

Repository method `list_trialing_with_expiry_before(now)` does:

```sql
SELECT * FROM owner_subscriptions
WHERE status = 'TRIALING' AND trial_ends_at < $1
```

Index on `(status, trial_ends_at)` covers it.

### 6.2 Entry-point script

`app/jobs/expire_trialing_subscriptions.py`:

```python
"""Cron entry-point. Run via `python -m app.jobs.expire_trialing_subscriptions`.

Suggested schedule: hourly (cron `0 * * * *`). Idempotent — safe to retry.
"""

import asyncio
import logging
from app.core.config import get_settings
from app.infrastructure.db.session import init_engine, dispose_engine, get_session
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
        # get_session is an async generator that yields one session and commits
        # at the end (or rolls back on exception). Reuse it for the cron flow.
        async for session in get_session():
            repo = SQLAlchemyOwnerSubscriptionRepository(session)
            handler = ExpireTrialingSubscriptionsHandler(repo, notifications, settings)
            result = await handler.handle(ExpireTrialingSubscriptionsCommand())
            logger.info("expired %s trialing subscriptions", result.value)
            return result.value or 0
        return 0
    finally:
        await dispose_engine()


if __name__ == "__main__":
    asyncio.run(main())
```

The implementation may refine this scaffolding (e.g., factor out a `run_job(handler_factory)` helper if Plan 08's `ExpirePendingBookings` shares the shape). What matters for the spec: a thin entry-point that initializes the engine, gets a session via existing `get_session()`, runs the handler once, and disposes. No scheduler library bundled — operations team configures cron / k8s CronJob / Airflow externally.

### 6.3 Stale-status window

Until the cron runs, a subscription whose `trial_ends_at < now` still reads as `TRIALING` in the DB and `is_operational() = true`. This window is bounded by the cron interval (e.g., 1 hour). Acceptable for MVP because:

- "Soft subscription" means no money is at stake from a few extra hours of operational status.
- Status-as-truth simplifies admin reporting — `WHERE status = 'TRIALING'` is honest about what the system thinks now.
- Reducing the window is an ops decision (cron more often), not a code change.

## 7. Subscription / User decoupling

`OwnerSubscription` is independent of `User.is_active`. Each aggregate owns one slice of state:

- `User.is_active` (Plan 02) → can this user log in / function at all?
- `OwnerSubscription.status` (Plan 05) → is this owner's business operational on the platform?

`is_operational(owner)` as a *single concept* is composed at the consumer layer, not on the aggregate:

```python
# Pattern for Plan 06 PublicListResourcesHandler and Plan 08 RequestBookingHandler:
async def is_owner_operational(self, owner_id: UUID) -> bool:
    sub = await self._subscriptions.get_by_owner_id(owner_id)
    owner = await self._users.get_by_id(owner_id)
    return bool(sub and sub.is_operational() and owner and owner.is_active)
```

`SetOwnerSubscriptionStatusHandler` does NOT reject mutation of an inactive owner's subscription — admin may want to pre-stage a status for a future reactivation. The mutation is inert in practice (consumer checks `owner.is_active` and ignores the subscription anyway).

`DeactivateUserHandler` (Plan 02) is NOT modified to cascade into subscriptions. Cross-feature cascade is exactly the anti-pattern CLAUDE.md proscribes ("handler com múltiplos repositórios via DI" applies to operations *owned* by that feature; deactivation is owned by accounts and shouldn't reach into subscriptions).

## 8. Notification port

### 8.1 Domain port

`app/domain/notifications/service.py` (new package, port-only — Plan 07 adds the aggregate):

```python
from enum import Enum
from typing import Any, Protocol
from uuid import UUID


class NotifKind(str, Enum):
    SUBSCRIPTION_CHANGED = "SUBSCRIPTION_CHANGED"
    # Plan 07/08 will add BOOKING_REQUESTED, BOOKING_APPROVED, etc.


class INotificationService(Protocol):
    async def notify(
        self,
        *,
        recipient_id: UUID,
        kind: NotifKind,
        payload: dict[str, Any],
    ) -> None: ...
```

### 8.2 Infrastructure adapter (no-op)

`app/infrastructure/notifications/logging_notification_service.py`:

```python
import logging

class LoggingNotificationService:
    def __init__(self, logger: logging.Logger):
        self._logger = logger

    async def notify(self, *, recipient_id, kind, payload) -> None:
        self._logger.info(
            "notification fired",
            extra={
                "recipient_id": str(recipient_id),
                "kind": kind.value,
                "payload": payload,
            },
        )
```

Wired into `main.py` DI; Plan 07 swaps it for `PersistentNotificationService` (writes to `notifications` table + invokes `IEmailSender`).

### 8.3 Tests

`tests/unit/use_cases/subscriptions/fakes/fake_notification_service.py`:

```python
class FakeNotificationService:
    def __init__(self):
        self.calls: list[tuple[UUID, NotifKind, dict[str, Any]]] = []

    async def notify(self, *, recipient_id, kind, payload) -> None:
        self.calls.append((recipient_id, kind, payload))
```

Used by `SetOwnerSubscriptionStatusHandler` and `ExpireTrialingSubscriptionsHandler` unit tests. Asserts: real status change emits exactly one call with the right payload; no-op emits zero calls.

## 9. Endpoints + DTOs

### 9.1 Routes

`app/api/v1/admin_subscriptions/routes.py`:
- `POST /v1/admin/owners/{owner_id}/subscription` → `SetOwnerSubscriptionStatusHandler`. Requires ADMIN role.
- `GET /v1/admin/subscriptions?status=&limit=&offset=` → `ListSubscriptionsHandler`. Requires ADMIN role.

`app/api/v1/me_subscription/routes.py`:
- `GET /v1/me/subscription` → `GetMySubscriptionHandler`. Auth: any logged-in user; if requester role is OWNER returns their subscription DTO, else returns 404 (`SubscriptionNotFound`).

### 9.2 DTOs

`app/use_cases/subscriptions/dtos.py`:

```python
@dataclass(frozen=True, slots=True)
class OwnerSubscriptionDto:
    id: UUID
    owner_id: UUID
    status: str                     # SubStatus.value
    status_changed_at: datetime
    trial_ends_at: datetime | None
    is_operational: bool            # computed; convenience for clients
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_entity(cls, sub: OwnerSubscription) -> Self: ...
```

Pydantic response models in `app/api/v1/.../schemas.py` mirror the DTO; `is_operational` is a top-level boolean that clients can use without knowing the SubStatus rules.

### 9.3 Listing pagination

`ListSubscriptionsResponse` uses the same shape as `ResourceTypeListResponse` from Plan 04: `{items, limit, offset}`. Optional `?status=` query filters by `SubStatus`. Default `limit=50`, max `100`.

## 10. Stable error codes

Adicionar a `app/api/error_codes.py`:

```python
"OwnerNotFound": "Proprietário não encontrado.",
"UserIsNotOwner": "Usuário não é proprietário.",
"SubscriptionNotFound": "Assinatura não encontrada.",
# Aggregate-level codes (registered as ResourceType-style class constants on OwnerSubscription)
OwnerSubscription.OWNER_ID_REQUIRED: "ID do proprietário é obrigatório.",
OwnerSubscription.TRIAL_ENDS_AT_REQUIRED_FOR_TRIALING:
    "Subscription em TRIALING precisa de data de fim de trial.",
OwnerSubscription.TRIAL_ENDS_AT_FORBIDDEN_OUTSIDE_TRIALING:
    "Data de fim de trial só é válida para status TRIALING.",
OwnerSubscription.TRIAL_DURATION_DAYS_INVALID:
    "Duração de trial deve ser inteiro positivo.",
```

Add **all** of these codes to `handler_level_allowlist` in `tests/unit/architecture/test_error_code_coverage.py`. The arch-test scanner only walks `BaseValueObject` subclasses; `OwnerSubscription` extends `BaseEntity`, so its class constants are not auto-discovered (same pattern as `ResourceType.DUPLICATE_ATTRIBUTE_KEY` etc., which is already in the allowlist).

Codes to add to the allowlist:

```python
"OwnerNotFound",
"UserIsNotOwner",
"SubscriptionNotFound",
"OwnerIdRequired",
"TrialEndsAtRequiredForTrialing",
"TrialEndsAtForbiddenOutsideTrialing",
"TrialDurationDaysInvalid",
```

## 11. Configuration

`app/core/config.py` adds:

```python
class Settings(BaseSettings):
    ...
    # Subscriptions
    trial_duration_days: int = 3
```

Env override: `BACKEND_TRIAL_DURATION_DAYS=7`. Validator: must be `> 0` (Pydantic constraint).

## 12. Tests

| Layer | Path | What it covers |
|---|---|---|
| Unit (domain) | `tests/unit/domain/subscriptions/test_sub_status.py` | enum values + `is_operational()` returns expected for each. |
| Unit (domain) | `tests/unit/domain/subscriptions/test_owner_subscription.py` | `create_trialing` happy path; cross-field invariants (TRIALING ↔ trial_ends_at); `transition_to` for every (old, new) pair including no-op idempotency; `trial_ends_at` reset on leave-TRIALING; bumps `status_changed_at` only on real change. |
| Unit (use_cases) | `tests/unit/use_cases/subscriptions/commands/test_set_status.py` | rejects non-existent owner, non-OWNER role; idempotent no-op; emits notification on real change with correct payload; preserves trial_ends_at on TRIALING→ACTIVE→TRIALING flow. |
| Unit (use_cases) | `tests/unit/use_cases/subscriptions/commands/test_expire_trialing.py` | finds expired candidates; flips to INACTIVE; emits one notify per flip; returns count; ignores non-trialing or non-expired rows. |
| Unit (use_cases) | `tests/unit/use_cases/accounts/commands/test_register_user.py` | extends existing tests: owner registration creates subscription in TRIALING; customer registration does NOT; subscription `trial_ends_at` matches `now + trial_duration_days`. |
| Integration | `tests/integration/subscriptions/test_owner_subscription_repository.py` | unique constraint on owner_id; round-trip persistence; query `list_trialing_with_expiry_before` returns expected rows. |
| E2E | `tests/e2e/subscriptions/test_admin_and_owner_flow.py` | admin sets status, owner sees it via /me/subscription; idempotent POST returns same DTO; non-admin gets 403; non-owner target gets 422. |

## 13. Migration

1. Aggregate + VO + repo Protocol + cross-field invariants (TDD per file).
2. SQLAlchemy mapping + migration (`make migrate-new`).
3. SQLAlchemy repository + integration tests.
4. `INotificationService` Protocol + `LoggingNotificationService` adapter + `FakeNotificationService` for tests.
5. `SetOwnerSubscriptionStatusHandler` + tests.
6. `ListSubscriptionsHandler` + `GetMySubscriptionHandler` + tests.
7. Routes (`admin_subscriptions/routes.py`, `me_subscription/routes.py`) + e2e tests.
8. `Settings.trial_duration_days` + `RegisterUserHandler` extension + test updates.
9. `ExpireTrialingSubscriptionsHandler` + tests.
10. Cron entry-point script (`app/jobs/expire_trialing_subscriptions.py`).
11. Add stable codes to `error_codes.py` + arch test allowlist.
12. Final verification: `grep "; "` tripwire still clean; full test suite green.

## 14. Follow-ups (post-merge)

- Update `docs/superpowers/specs/2026-04-25-venue-backend-design.md` §5.5 to reflect the schema changes (drop `notes`, add `trial_ends_at`, mention auto-create). Defer until Plan 05 actually merges.
- Plan 06 must implement the `is_operational(owner)` consumer pattern documented in §7. Public listing handler injects `ISubscriptionRepository` + `IUserRepository` and filters resources whose owner fails either gate.
- Plan 07 swaps `LoggingNotificationService` for `PersistentNotificationService`; updates DI in `main.py`. The `INotificationService` Protocol contract does not change.
