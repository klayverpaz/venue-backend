# Plan 07 — Notifications Design Doc

**Status:** Approved 2026-04-26.
**Author:** klayver + Claude (brainstorm session).
**Scope:** Plan 07 of the venue-backend roadmap (`docs/superpowers/specs/2026-04-25-venue-backend-design.md` §8). Refines §5.6 with a leaner MVP shape: in-app inbox only, no email channel, no rating notifications.

## 1. Motivation

Plan 05 introduced an `INotificationService` port with a no-op `LoggingNotificationService` adapter so the subscription handlers (`SetOwnerSubscriptionStatusHandler`, `ExpireTrialingSubscriptionsHandler`) could fire `SUBSCRIPTION_CHANGED` events without blocking on the rest of the notifications feature. Plan 07 closes that loop: notifications start being persisted, end-users (OWNER + CUSTOMER) gain endpoints to list and mark them read, and the enum grows the four booking kinds that Plan 08 will emit.

Plan 07 also unlocks Plan 08. `RequestBookingHandler`, `ApproveBookingHandler`, and `CancelBookingHandler` (§4.2) inject `INotificationService` and emit `BOOKING_REQUESTED` / `BOOKING_APPROVED` / `BOOKING_REJECTED` / `BOOKING_CANCELLED`. Those kinds need to exist in the enum and be persisted before Plan 08 wires them.

This refinement deviates from venue-backend §5.6 in three places (all approved by the user during brainstorming):

- **`BOOKING_RATED` is dropped.** Owner has no actionable response to a rating (decision §10 of the venue spec puts "Owner reply to a rating" out of scope), and Plan 09 already adds `rating_avg` / `rating_count` to every `Resource` GET. A pure-FYI notification is redundant.
- **`IEmailSender` port and email channel are dropped.** MVP ships in-app inbox only. Email integration is deferred to a post-MVP plan; the port can be reintroduced later with a new `LoggingEmailSender` / SES adapter without rewriting the inbox.
- **`INotificationService` is kept as the coarse-grained port that handlers consume.** Spec §5.6 only models `Notification` (aggregate) + `IEmailSender` (port), implying handlers would inject a repository and an email sender directly. Plan 05 already shipped `INotificationService` and two handlers depend on it. Plan 07 evolves that port instead of refactoring it: the adapter behind `INotificationService.notify(...)` switches from no-op logging to repository persistence, leaving handler call sites untouched.

## 2. Scope

### In scope

- `Notification` aggregate (`app/domain/notifications/notification.py`) — `id`, `recipient_id`, `kind: NotifKind`, `payload: dict[str, Any]`, `read_at: datetime | None`, `created_at: datetime`. Factory `create(...)`. Mutator `mark_read(now)` idempotent.
- `NotifKind` enum extended from 1 → 5 values: `SUBSCRIPTION_CHANGED` (existing), `BOOKING_REQUESTED`, `BOOKING_APPROVED`, `BOOKING_REJECTED`, `BOOKING_CANCELLED`.
- `INotificationRepository` Protocol in `app/domain/notifications/repository.py` (`add`, `list_by_recipient`, `get_for_recipient`, `update`).
- `INotificationService` Protocol stays at `app/domain/notifications/service.py` with the same `notify(*, recipient_id, kind, payload) -> None` signature. Behavior changes: implementation persists a row instead of logging.
- `PersistentNotificationService` adapter in `app/infrastructure/notifications/persistent_notification_service.py`. Replaces `LoggingNotificationService`.
- `SQLAlchemyNotificationRepository` in `app/infrastructure/repositories/notification_repository.py` (matches the project's existing `infrastructure/repositories/<feature>_repository.py` layout).
- Declarative SQLAlchemy mapping in `app/infrastructure/db/mappings/notification.py` (`NotificationModel(Base, TimestampMixin)`). Registered in `app/migrations/env.py`. Alembic migration for the `notifications` table.
- Use cases in `app/use_cases/notifications/`:
  - `queries/list_my_notifications.py` → `ListMyNotificationsHandler` with cursor-based pagination.
  - `commands/mark_notification_read.py` → `MarkNotificationReadHandler`.
- API in `app/api/v1/me_notifications/`:
  - `GET /v1/me/notifications`
  - `POST /v1/me/notifications/{id}/read`
- DI rewiring: `app/api/v1/admin_subscriptions/deps.py` and `app/jobs/expire_trialing_subscriptions.py` swap `LoggingNotificationService(logger)` for `PersistentNotificationService(SQLAlchemyNotificationRepository(session))`.
- Stable error code: `NotificationNotFound` registered in `app/api/error_codes.py` + arch test allowlist + pt-BR mapping.
- New test fakes:
  - `tests/unit/use_cases/notifications/fakes/in_memory_notification_repository.py`.
  - The existing `tests/unit/use_cases/subscriptions/fakes/fake_notification_service.py` stays for unit tests of subscription handlers (still implements `INotificationService`).
- Test coverage: domain unit, repository integration, handler unit (with in-memory repo), e2e for listing + marking read.
- **Canonical spec refresh.** Doc-only edit to `docs/superpowers/specs/2026-04-25-venue-backend-design.md`: §5.6 (`Notification` aggregate + `NotifKind`) drops `BOOKING_RATED` and the `IEmailSender` block; decision §3 #13 reflects "in-app inbox only, email deferred"; §4.2 cross-feature handlers row for `CreateRatingHandler` drops `INotificationService` from the injected ports; §8 plan 07 description loses the "Includes `BOOKING_RATED`" sentence and the `IEmailSender` mention. Same pattern Plan 06 task 38 used for §5.5.

### Out of scope

- **`BOOKING_RATED` enum value and its emission in `CreateRatingHandler`.** Cut for MVP. Plan 09 ships `rating_avg`/`rating_count` aggregates; owners read those instead of receiving an FYI ping.
- **`IEmailSender` port + transactional email.** MVP is in-app only. A future plan reintroduces the port with a real adapter (Mailgun/SES/Resend) without touching the inbox surface.
- **De-duplication of equal `(recipient_id, kind, payload)` rows.** Append-only table; duplicates are tolerated. Producing handlers (subscription, booking) prevent dupes at their level via state checks (`old_status is cmd.status` short-circuit) and idempotency keys (decision §14 of the venue spec, landing in Plan 08).
- **`mark_all_as_read` endpoint, `unread_count` endpoint, `archive`/`delete` endpoints.** YAGNI for MVP. Frontend can derive an unread badge from `?unread_only=true&limit=1`.
- **Push notifications, websocket push, server-sent events.** Inbox is poll-based via `GET /me/notifications`.
- **Typed payload dataclasses per kind.** `Notification.payload` stays `dict[str, Any]`. Plan 08 may introduce typed builders inside its own handlers if useful, but no domain-level contract.
- **Foreign key from `notifications.recipient_id` to `users.id`.** Matches the Plan 05 `owner_subscriptions.owner_id` pattern (no FK; `CHAR(36)` + index only). The project has mixed precedent — Plan 06's `resources.owner_id` does FK with `ondelete="RESTRICT"`, while `owner_subscriptions.owner_id` does not. For an append-only audit-style table, no FK keeps writes cheap and tolerates eventual user pruning. Emitters are trusted to pass real recipient UUIDs.
- **Soft-delete or retention policy on notifications.** Append-only forever for MVP. A future cleanup job can prune `read_at IS NOT NULL AND created_at < now - 90 days` if volume becomes a concern.
- **Admin-facing notifications endpoint or admin notification kinds.** Roles ADMIN does not receive any of the 5 kinds; the routes stay at `/me/...` and respond with the actor's own notifications regardless of role.

## 3. Domain shape

### 3.1 `NotifKind` enum

`app/domain/notifications/service.py` (existing file, extended):

```python
from __future__ import annotations
from enum import Enum


class NotifKind(str, Enum):
    SUBSCRIPTION_CHANGED = "SUBSCRIPTION_CHANGED"
    BOOKING_REQUESTED = "BOOKING_REQUESTED"
    BOOKING_APPROVED = "BOOKING_APPROVED"
    BOOKING_REJECTED = "BOOKING_REJECTED"
    BOOKING_CANCELLED = "BOOKING_CANCELLED"
```

The four booking values land in this Plan 07; emission of the four booking kinds happens in Plan 08 handlers. `SUBSCRIPTION_CHANGED` continues to be emitted by the existing two subscription handlers, unchanged.

### 3.2 `Notification` aggregate

`app/domain/notifications/notification.py`:

```python
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from app.domain.notifications.service import NotifKind
from app.domain.shared.entity import BaseEntity


@dataclass(slots=True, kw_only=True)
class Notification(BaseEntity):
    recipient_id: UUID
    kind: NotifKind
    payload: dict[str, Any]
    read_at: datetime | None = None

    @classmethod
    def create(
        cls,
        *,
        recipient_id: UUID,
        kind: NotifKind,
        payload: dict[str, Any],
        now: datetime,
    ) -> "Notification":
        return cls(
            id=uuid4(),
            recipient_id=recipient_id,
            kind=kind,
            payload=payload,
            read_at=None,
            created_at=now,
            updated_at=now,
        )

    def mark_read(self, *, now: datetime) -> None:
        """Idempotent. If already read, no-op (read_at not bumped)."""
        if self.read_at is None:
            self.read_at = now
            self.updated_at = now
```

**Invariants**

- `payload` is stored as-is. Producers own the schema. Consumers deserialize defensively.
- `mark_read` is idempotent; calling twice does not bump `read_at` from the first call.
- No setters for `recipient_id`, `kind`, `payload`, or `created_at` — immutable after `create()`.

**No factory `Result` wrapper.** Unlike Plan 06's `Resource.create`, `Notification.create` has no validation work to do — `recipient_id` is a UUID coming from a trusted handler, `kind` is an enum (compile-time-safe), and `payload` is unvalidated by design. The factory returns `Notification` directly, not `Result[Notification]`. This matches the lighter aggregates in `accounts` (where `User` validation lives in VOs, not at aggregate level).

### 3.3 `INotificationRepository` Protocol

`app/domain/notifications/repository.py`:

```python
from __future__ import annotations
from typing import Protocol
from uuid import UUID

from app.domain.notifications.notification import Notification
from app.domain.shared.result import Result


class INotificationRepository(Protocol):
    async def add(self, notification: Notification) -> Result[None]: ...

    async def get_for_recipient(
        self,
        notification_id: UUID,
        recipient_id: UUID,
    ) -> Result[Notification | None]: ...

    async def list_by_recipient(
        self,
        recipient_id: UUID,
        *,
        limit: int,
        cursor: UUID | None,
        unread_only: bool,
    ) -> Result[list[Notification]]: ...

    async def update(self, notification: Notification) -> Result[None]: ...
```

**`get_for_recipient` enforces ownership at the repo level** — handlers do not need to fetch and then check `notification.recipient_id == actor_id`. If the row exists but belongs to someone else, the repo returns `Result.success(None)`, identical to "not found". Mirrors the Plan 06 pattern (`ResourceNotFound` 404 on cross-owner access; never leaks a 403).

**`list_by_recipient` cursor semantics:**
- `cursor` is the `id` of the last notification of the previous page.
- Repo returns rows where `(created_at, id) < (cursor_row.created_at, cursor_row.id)`, ordered `created_at DESC, id DESC`.
- `limit` is the requested page size (handler clamps to `[1, 100]`).
- `unread_only=True` filters to `read_at IS NULL`.

### 3.4 `INotificationService` Protocol (unchanged signature)

`app/domain/notifications/service.py` keeps the existing Protocol:

```python
class INotificationService(Protocol):
    async def notify(
        self,
        *,
        recipient_id: UUID,
        kind: NotifKind,
        payload: dict[str, Any],
    ) -> None: ...
```

Plan 05's docstring saying "Plan 05 ships a no-op logging adapter; Plan 07 swaps for a persistent service that writes to the notifications table and triggers IEmailSender" gets updated: drop the `IEmailSender` reference, keep the rest.

## 4. Persistence

The project uses **declarative SQLAlchemy 2.x ORM** (`Base`/`TimestampMixin` from `app/infrastructure/db/base.py`) with a separate `*Model` class per table; the domain entity is **NOT** mapped directly. Repositories translate between `Notification` (domain) and `NotificationModel` (ORM) via helper functions, mirroring `app/infrastructure/repositories/resource_repository.py`.

### 4.1 Table

`notifications`:

| Column | SQLAlchemy type | Constraints |
|---|---|---|
| `id` | `CHAR(36)` | PK |
| `recipient_id` | `CHAR(36)` | NOT NULL, indexed |
| `kind` | `Text` | NOT NULL |
| `payload` | `JSON` | NOT NULL |
| `read_at` | `DateTime(timezone=True)` | NULL |
| `created_at` | `DateTime(timezone=True)` | NOT NULL (from `TimestampMixin`) |
| `updated_at` | `DateTime(timezone=True)` | NOT NULL (from `TimestampMixin`) |

**Indexes:**
- `idx_notifications_recipient_created` on `(recipient_id, created_at DESC, id DESC)` — covers the inbox listing and cursor paging.

**Type choices:**
- `CHAR(36)` for UUIDs — matches every other model in the project (`UserModel`, `ResourceModel`, `OwnerSubscriptionModel`). UUIDs are `str(uuid)`-encoded at the repo boundary.
- `Text` for `kind` — the project uses `Text` for all string columns (decision §17 of the venue spec: "DB columns for VO-backed strings are `TEXT`"). `kind` is a non-VO enum but reusing `Text` keeps the migration shape uniform.
- `JSON` (SQLAlchemy generic) for `payload` — the dialect resolves it (`JSONB` on Postgres, `NVARCHAR(MAX)` on MSSQL). Same as `ResourceModel.operating_hours` / `pricing_rules` / `custom_attributes`.

**No FK on `recipient_id`.** Matches `OwnerSubscriptionModel.owner_id` (Plan 05). The project has mixed precedent (`ResourceModel.owner_id` does FK with `ondelete="RESTRICT"`); for an append-only inbox the index alone is sufficient and avoids cross-aggregate write coupling.

### 4.2 Mapping

`app/infrastructure/db/mappings/notification.py`:

```python
from __future__ import annotations
from datetime import datetime
from uuid import UUID
from sqlalchemy import Index, JSON, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import CHAR, DateTime
from app.infrastructure.db.base import Base, TimestampMixin


class NotificationModel(Base, TimestampMixin):
    __tablename__ = "notifications"
    __table_args__ = (
        Index(
            "idx_notifications_recipient_created",
            "recipient_id",
            "created_at",
            "id",
        ),
    )

    id: Mapped[UUID] = mapped_column(CHAR(36), primary_key=True)
    recipient_id: Mapped[UUID] = mapped_column(CHAR(36), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

Registered for Alembic via `from app.infrastructure.db.mappings import notification  # noqa: F401` added to `app/migrations/env.py`, alphabetically sorted with the existing four imports.

### 4.3 Migration

`make migrate-new msg="add_notifications_table"` generates a new revision file. The plan inspects and tightens the auto-generated migration to ensure:

- `op.create_table("notifications", ...)` with the column types listed above.
- `op.create_index("idx_notifications_recipient_created", "notifications", ["recipient_id", "created_at", "id"])`.
- Down migration drops the index then the table.

No conditional `JSONB`/`NVARCHAR(MAX)` switch needed — SQLAlchemy generic `JSON` resolves per dialect, same as Plan 06's columns.

## 5. Infrastructure adapters

### 5.1 `SQLAlchemyNotificationRepository`

`app/infrastructure/repositories/notification_repository.py` (matches the project layout — every repo lives under `infrastructure/repositories/<feature>_repository.py`). Class `SQLAlchemyNotificationRepository(INotificationRepository)` over an `AsyncSession`. Pattern mirrors `SQLAlchemyResourceRepository`:

```python
def _to_model_kwargs(notif: Notification) -> dict:
    return {
        "id": str(notif.id),
        "recipient_id": str(notif.recipient_id),
        "kind": notif.kind.value,
        "payload": dict(notif.payload),
        "read_at": notif.read_at,
        "created_at": notif.created_at,
        "updated_at": notif.updated_at,
    }


def _to_entity(model: NotificationModel) -> Notification:
    return Notification(
        id=UUID(str(model.id)),
        recipient_id=UUID(str(model.recipient_id)),
        kind=NotifKind(model.kind),
        payload=dict(model.payload),
        read_at=_ensure_utc(model.read_at),
        created_at=_ensure_utc(model.created_at),
        updated_at=_ensure_utc(model.updated_at),
    )


class SQLAlchemyNotificationRepository(INotificationRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def add(self, notif: Notification) -> Result[None]:
        model = NotificationModel(**_to_model_kwargs(notif))
        self._session.add(model)
        await self._session.flush()
        return Result.success(None)

    async def get_for_recipient(
        self, notification_id: UUID, recipient_id: UUID,
    ) -> Result[Notification | None]:
        stmt = select(NotificationModel).where(
            NotificationModel.id == str(notification_id),
            NotificationModel.recipient_id == str(recipient_id),
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return Result.success(_to_entity(row) if row else None)

    async def list_by_recipient(
        self,
        recipient_id: UUID,
        *,
        limit: int,
        cursor: UUID | None,
        unread_only: bool,
    ) -> Result[list[Notification]]:
        stmt = (
            select(NotificationModel)
            .where(NotificationModel.recipient_id == str(recipient_id))
            .order_by(NotificationModel.created_at.desc(), NotificationModel.id.desc())
            .limit(limit)
        )
        if unread_only:
            stmt = stmt.where(NotificationModel.read_at.is_(None))
        if cursor is not None:
            cursor_stmt = select(NotificationModel.created_at).where(
                NotificationModel.id == str(cursor),
                NotificationModel.recipient_id == str(recipient_id),
            )
            cursor_created = (await self._session.execute(cursor_stmt)).scalar_one_or_none()
            if cursor_created is not None:
                stmt = stmt.where(
                    (NotificationModel.created_at < cursor_created)
                    | (
                        (NotificationModel.created_at == cursor_created)
                        & (NotificationModel.id < str(cursor))
                    )
                )
        rows = (await self._session.execute(stmt)).scalars().all()
        return Result.success([_to_entity(r) for r in rows])

    async def update(self, notif: Notification) -> Result[None]:
        stmt = select(NotificationModel).where(NotificationModel.id == str(notif.id))
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        if row is None:
            return Result.failure("NotificationNotFound", status_code=404)
        for k, v in _to_model_kwargs(notif).items():
            if k == "id":
                continue
            setattr(row, k, v)
        await self._session.flush()
        return Result.success(None)
```

`_ensure_utc` is the same helper Plan 06 uses (`SQLAlchemyResourceRepository._ensure_utc`) for SQLite/aiosqlite roundtrip safety in tests.

### 5.2 `PersistentNotificationService`

`app/infrastructure/notifications/persistent_notification_service.py`:

```python
from __future__ import annotations
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from app.domain.notifications.notification import Notification
from app.domain.notifications.repository import INotificationRepository
from app.domain.notifications.service import NotifKind


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class PersistentNotificationService:
    """Default INotificationService impl. Persists every call as a Notification
    row. Failures are logged and swallowed — fire-and-forget semantics preserved
    so emitting handlers never fail because of notification trouble.
    """

    def __init__(
        self,
        repository: INotificationRepository,
        *,
        logger: logging.Logger | None = None,
    ) -> None:
        self._repository = repository
        self._logger = logger or logging.getLogger(__name__)

    async def notify(
        self,
        *,
        recipient_id: UUID,
        kind: NotifKind,
        payload: dict[str, Any],
    ) -> None:
        notif = Notification.create(
            recipient_id=recipient_id,
            kind=kind,
            payload=payload,
            now=_utcnow(),
        )
        result = await self._repository.add(notif)
        if result.is_failure:
            self._logger.warning(
                "notification persistence failed",
                extra={
                    "recipient_id": str(recipient_id),
                    "kind": kind.value,
                    "error": result.error,
                },
            )
```

**`LoggingNotificationService` is deleted.** All call sites (DI provider, cron) switch to `PersistentNotificationService`. Tests that need observability use `FakeNotificationService` (already exists; captures calls in a list).

## 6. Use cases

### 6.1 `ListMyNotificationsHandler`

`app/use_cases/notifications/queries/list_my_notifications.py`:

```python
@dataclass(frozen=True, kw_only=True)
class ListMyNotificationsQuery:
    actor_id: UUID
    limit: int = 50
    cursor: UUID | None = None
    unread_only: bool = False


@dataclass(frozen=True, kw_only=True)
class NotificationDto:
    id: UUID
    kind: str
    payload: dict[str, Any]
    read_at: datetime | None
    created_at: datetime


@dataclass(frozen=True, kw_only=True)
class NotificationListDto:
    items: list[NotificationDto]
    next_cursor: UUID | None


class ListMyNotificationsHandler:
    def __init__(self, repository: INotificationRepository) -> None:
        self._repository = repository

    async def handle(
        self, query: ListMyNotificationsQuery,
    ) -> Result[NotificationListDto]:
        limit = max(1, min(query.limit, 100))
        list_r = await self._repository.list_by_recipient(
            query.actor_id,
            limit=limit + 1,           # fetch one extra to know if more pages exist
            cursor=query.cursor,
            unread_only=query.unread_only,
        )
        if list_r.is_failure:
            return Result.from_failure(list_r)
        rows = list_r.value
        next_cursor = rows[limit - 1].id if len(rows) > limit else None
        items = [NotificationDto.from_entity(n) for n in rows[:limit]]
        return Result.success(NotificationListDto(items=items, next_cursor=next_cursor))
```

### 6.2 `MarkNotificationReadHandler`

`app/use_cases/notifications/commands/mark_notification_read.py`:

```python
@dataclass(frozen=True, kw_only=True)
class MarkNotificationReadCommand:
    actor_id: UUID
    notification_id: UUID


class MarkNotificationReadHandler:
    def __init__(self, repository: INotificationRepository) -> None:
        self._repository = repository

    async def handle(
        self, cmd: MarkNotificationReadCommand,
    ) -> Result[None]:
        get_r = await self._repository.get_for_recipient(
            cmd.notification_id, cmd.actor_id,
        )
        if get_r.is_failure:
            return Result.from_failure(get_r)
        notif = get_r.value
        if notif is None:
            return Result.failure("NotificationNotFound", status_code=404)
        if notif.read_at is None:
            notif.mark_read(now=_utcnow())
            update_r = await self._repository.update(notif)
            if update_r.is_failure:
                return Result.from_failure(update_r)
        return Result.success(None)
```

Already-read is a no-op success (idempotent). Cross-recipient lookup returns 404 (`NotificationNotFound`), not 403 — same anti-leak pattern as Plan 06's `ResourceNotFound`.

## 7. API surface

### 7.1 `GET /v1/me/notifications`

**Auth:** any authenticated role.

**Query params:**
- `limit: int` — default `50`, clamped to `[1, 100]`.
- `cursor: UUID | None` — opaque cursor; pass back the `next_cursor` from the previous response.
- `unread_only: bool` — default `false`.

**Response 200:**
```json
{
  "items": [
    {
      "id": "uuid",
      "kind": "SUBSCRIPTION_CHANGED",
      "payload": { "old_status": "TRIALING", "new_status": "INACTIVE", "reason": "trial_expired" },
      "read_at": null,
      "created_at": "2026-04-26T12:34:56Z"
    }
  ],
  "next_cursor": "uuid-or-null"
}
```

**Errors:**
- `401 Unauthorized` if no JWT.
- `422 ValidationFailed` if `limit` outside `[1, 100]` or `cursor` malformed UUID — Pydantic-driven validation envelope (see `validation-error-envelope-design.md`).

### 7.2 `POST /v1/me/notifications/{id}/read`

**Auth:** any authenticated role.

**Body:** none.

**Response 204:** No Content. Idempotent (same response for already-read notifications).

**Errors:**
- `401 Unauthorized` if no JWT.
- `404 NotificationNotFound` if id does not exist OR belongs to another recipient.

### 7.3 Routes file structure

`app/api/v1/me_notifications/`:
- `__init__.py` — exports `me_notifications_router`.
- `routes.py` — FastAPI router with both endpoints.
- `deps.py` — DI providers for `ListMyNotificationsHandler` and `MarkNotificationReadHandler`. Repository is built from the request-scoped `AsyncSession`.
- `schemas.py` — Pydantic request/response models, matching the `me_subscription` / `me_resources` / `admin_subscriptions` layout (single file for both, not split into `request.py` / `response.py`). Includes `NotificationResponse.from_dto(...)` and `NotificationListResponse.from_dto(...)`.

`app/api/v1/router.py` adds `api_router.include_router(me_notifications_router)` alongside the existing seven includes.

## 8. Refactor of existing call sites

### 8.1 DI provider

`app/api/v1/admin_subscriptions/deps.py:39` (`get_notification_service`) becomes:

```python
async def get_notification_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> PersistentNotificationService:
    return PersistentNotificationService(SQLAlchemyNotificationRepository(session))
```

The `LoggingNotificationService` import is removed. The `_logger` module-level fallback is removed.

### 8.2 Cron entry point

`app/jobs/expire_trialing_subscriptions.py:12` import changes from `LoggingNotificationService` to `PersistentNotificationService`. Line 29 becomes:

```python
notifications = PersistentNotificationService(SQLAlchemyNotificationRepository(session))
```

`session` is the `AsyncSession` already created earlier in the script.

### 8.3 Subscription handler tests

`tests/unit/use_cases/subscriptions/...` already inject `FakeNotificationService` (in-memory). No change needed — that fake implements `INotificationService.notify(...)` with the same signature.

### 8.4 Handler that currently returns success when notification fails

`set_owner_subscription_status.py:66-74` and `expire_trialing_subscriptions.py:47-55` already use fire-and-forget (`await self._notifications.notify(...)` with no return-value handling). No change.

## 9. Stable error codes

New code registered in `app/api/error_codes.py`, `app/api/error_handler.py` pt-BR mapping, and the architecture-test allowlist in `tests/unit/architecture/`:

| Code | HTTP | pt-BR |
|---|---|---|
| `NotificationNotFound` | 404 | `Notificação não encontrada.` |

No other handler-level codes — the inbox is read/write, no validation beyond Pydantic on the routes.

## 10. Testing strategy

| Level | Target | Asserts |
|---|---|---|
| Unit (domain) | `tests/unit/domain/notifications/test_notification.py` | `Notification.create` produces correct fields; `mark_read` idempotent; setting `mark_read` twice does not bump `read_at`. |
| Unit (use cases) | `tests/unit/use_cases/notifications/` | `ListMyNotificationsHandler` paginates correctly with cursor; `unread_only` filters; `MarkNotificationReadHandler` returns success on already-read; returns `NotificationNotFound` on cross-recipient lookup. |
| Unit (service) | `tests/unit/infrastructure/notifications/test_persistent_notification_service.py` | `notify(...)` calls `repository.add(...)` with correct `Notification` shape; logs and swallows on `add` failure (does not raise). |
| Integration | `tests/integration/notifications/` | `SQLAlchemyNotificationRepository` against the test DB: round-trip, ordered listing, cursor stability, JSON payload preserved exactly. |
| E2E | `tests/e2e/notifications/` | OWNER reads `/me/notifications` after triggering a subscription transition, sees one row, marks it read, second GET shows `read_at` populated. CUSTOMER (no notifications yet) gets empty list. Cross-recipient `POST /read` returns 404. |
| Architecture | already covered | No `domain/notifications` imports from `infrastructure/`; Notification mapping registered. |

In-memory test fakes:
- **Keep** `tests/unit/use_cases/subscriptions/fakes/fake_notification_service.py` — still implements `INotificationService` for the two existing subscription handler tests.
- **Add** `tests/unit/use_cases/notifications/fakes/in_memory_notification_repository.py` — implements `INotificationRepository` over a `list[Notification]` plus a `MagicMock`-style failure mode for the persistence-failure test.

## 11. Open items (none blocking)

- **Email channel.** The `IEmailSender` port spec'd in §5.6 is not built. When the platform later adds transactional email, a new plan introduces the port + `LoggingEmailSender` adapter, and `PersistentNotificationService` grows a second collaborator — ideally with the same fire-and-forget invariant ("email failure logs but does not fail use case").
- **Rating notifications (`BOOKING_RATED`).** If the product later wants owner reply to ratings or "rating below threshold" alerts, reintroduce the kind. For MVP, ratings are a pure read-side concern visible via `Resource.rating_avg`.
- **Retention.** Append-only forever. If volume becomes a concern post-launch, add a nightly job to delete `read_at IS NOT NULL AND created_at < now - 90 days`.
- **Push / websocket.** Inbox is poll-only. Frontend polls `GET /me/notifications` (or filters `unread_only=true&limit=1` for a badge). Server-side push is a separate plan.
- **Owner-side typed payload contracts.** Plan 08 will define the actual payload shapes for `BOOKING_*` events. Plan 07 stays neutral.
