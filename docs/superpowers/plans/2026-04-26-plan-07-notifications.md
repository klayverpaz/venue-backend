# Plan 07 — Notifications Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the persistent in-app notification inbox: `Notification` aggregate, `INotificationRepository` port + SQLAlchemy adapter, replace the no-op `LoggingNotificationService` with `PersistentNotificationService`, expand `NotifKind` from 1 → 5 values (adds the four booking kinds Plan 08 will emit), add `GET /v1/me/notifications` and `POST /v1/me/notifications/{id}/read` endpoints (cursor-paginated, idempotent mark-read, 404 on cross-recipient access), and refresh the canonical venue-backend spec §5.6 / §3 #13 / §4.2 / §8 to drop `BOOKING_RATED` + `IEmailSender`.

**Architecture:** `Notification` is a thin `BaseEntity` aggregate (no validation work; `recipient_id` and `kind` come from trusted handlers, `payload: dict[str, Any]` is freeform). Storage is a single `notifications` row per event, JSON-encoded payload, indexed on `(recipient_id, created_at DESC, id DESC)` for cursor paging. The existing `INotificationService.notify(...)` Protocol signature is preserved — only its adapter changes (`LoggingNotificationService` → `PersistentNotificationService`); the two existing call sites in `set_owner_subscription_status.py` and `expire_trialing_subscriptions.py` and their handler tests remain untouched. The HTTP surface mirrors `me_subscription` / `me_resources` (single `schemas.py`, `deps.py`, `routes.py`, `__init__.py`). Mark-read enforces ownership at the repo layer (`get_for_recipient` returns `None` on cross-recipient access) so the handler never leaks a 403; the public response is always 404 (`NotificationNotFound`).

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2 async, Alembic, Pydantic, pytest. No new dependencies.

**Reference spec:** `docs/superpowers/specs/2026-04-26-plan-07-notifications-design.md`.

**Conventions reminders:**
- Always invoke Python via venv: `.venv/bin/python` or `.venv/bin/pytest`. Never use the global Python.
- Domain code never imports from `infrastructure` or `use_cases`.
- After each task, commit with a focused message ending in `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>`.
- TDD: write failing test, run RED, write minimal impl, run GREEN, commit.
- `Result.failure(code, status_code=N)` for handler-level errors; `Result.failure_many(...)` is unused in this plan (no multi-field aggregation).

---

## File structure (created or modified over the plan)

```
app/domain/notifications/
├── __init__.py                                   already exists
├── service.py                                    MODIFIED — extend NotifKind, refresh docstrings
├── notification.py                               NEW — Notification aggregate
└── repository.py                                 NEW — INotificationRepository Protocol

app/use_cases/notifications/
├── __init__.py                                   NEW
├── dtos.py                                       NEW — NotificationDto, NotificationListDto
├── commands/
│   ├── __init__.py                               NEW
│   └── mark_notification_read.py                 NEW
└── queries/
    ├── __init__.py                               NEW
    └── list_my_notifications.py                  NEW

app/infrastructure/db/mappings/
└── notification.py                               NEW — NotificationModel

app/infrastructure/repositories/
└── notification_repository.py                    NEW — SQLAlchemyNotificationRepository

app/infrastructure/notifications/
├── __init__.py                                   already exists
├── logging_notification_service.py               DELETED
└── persistent_notification_service.py            NEW

app/api/v1/me_notifications/
├── __init__.py                                   NEW
├── deps.py                                       NEW
├── schemas.py                                    NEW
└── routes.py                                     NEW

app/api/v1/
├── router.py                                     MODIFIED — include me_notifications_router
└── admin_subscriptions/deps.py                   MODIFIED — swap LoggingNotificationService → PersistentNotificationService

app/jobs/
└── expire_trialing_subscriptions.py              MODIFIED — swap LoggingNotificationService → PersistentNotificationService

app/api/error_codes.py                            MODIFIED — register NotificationNotFound + arch test allowlist
app/migrations/env.py                             MODIFIED — register NotificationModel
app/migrations/versions/<ts>_notifications_table.py    NEW

tests/unit/domain/notifications/
├── __init__.py                                   NEW
└── test_notification.py                          NEW

tests/unit/infrastructure/notifications/
├── __init__.py                                   NEW
└── test_persistent_notification_service.py       NEW

tests/unit/use_cases/notifications/
├── __init__.py                                   NEW
├── fakes/
│   ├── __init__.py                               NEW
│   └── in_memory_notification_repository.py      NEW
├── commands/
│   ├── __init__.py                               NEW
│   └── test_mark_notification_read.py            NEW
└── queries/
    ├── __init__.py                               NEW
    └── test_list_my_notifications.py             NEW

tests/unit/architecture/test_error_code_coverage.py    MODIFIED — extend allowlist

tests/integration/notifications/
├── __init__.py                                   NEW
└── test_notification_repository.py               NEW

tests/integration/conftest.py                     MODIFIED — register notification mapping import

tests/e2e/notifications/
├── __init__.py                                   NEW
└── test_inbox_lifecycle.py                       NEW

docs/superpowers/specs/2026-04-25-venue-backend-design.md   MODIFIED — refresh §3 #13, §4.2, §5.6, §8
```

---

## Task 1: Extend `NotifKind` enum

**Files:**
- Modify: `app/domain/notifications/service.py`
- Test: `tests/unit/domain/notifications/test_notification.py` (also created in Task 2; here just the kind tests)

- [ ] **Step 1: Write the failing test**

Create `tests/unit/domain/notifications/__init__.py` (empty) and `tests/unit/domain/notifications/test_notification.py`:

```python
from __future__ import annotations

from app.domain.notifications.service import NotifKind


def test_notif_kind_subscription_changed():
    assert NotifKind.SUBSCRIPTION_CHANGED.value == "SUBSCRIPTION_CHANGED"


def test_notif_kind_booking_requested():
    assert NotifKind.BOOKING_REQUESTED.value == "BOOKING_REQUESTED"


def test_notif_kind_booking_approved():
    assert NotifKind.BOOKING_APPROVED.value == "BOOKING_APPROVED"


def test_notif_kind_booking_rejected():
    assert NotifKind.BOOKING_REJECTED.value == "BOOKING_REJECTED"


def test_notif_kind_booking_cancelled():
    assert NotifKind.BOOKING_CANCELLED.value == "BOOKING_CANCELLED"


def test_notif_kind_has_no_booking_rated():
    assert not hasattr(NotifKind, "BOOKING_RATED")
```

- [ ] **Step 2: Run test to verify the new ones fail**

Run: `.venv/bin/pytest tests/unit/domain/notifications/test_notification.py -v`
Expected: 4 of 6 FAIL with `AttributeError: BOOKING_REQUESTED` etc.; the SUBSCRIPTION_CHANGED and BOOKING_RATED-absence ones PASS.

- [ ] **Step 3: Edit `app/domain/notifications/service.py`**

Replace the existing `NotifKind` enum and refresh the docstrings:

```python
from __future__ import annotations
from enum import Enum
from typing import Any, Protocol
from uuid import UUID


class NotifKind(str, Enum):
    """Notification kinds. Plan 07 grows the booking values that Plan 08
    will emit. BOOKING_RATED is intentionally absent (Plan 07 dropped it for
    MVP — see plan-07-notifications-design.md §1).
    """

    SUBSCRIPTION_CHANGED = "SUBSCRIPTION_CHANGED"
    BOOKING_REQUESTED = "BOOKING_REQUESTED"
    BOOKING_APPROVED = "BOOKING_APPROVED"
    BOOKING_REJECTED = "BOOKING_REJECTED"
    BOOKING_CANCELLED = "BOOKING_CANCELLED"


class INotificationService(Protocol):
    """Domain port for fire-and-forget notification dispatch. Plan 07 swaps
    the no-op logging adapter for a persistent service that writes a
    Notification row per call. Email is intentionally not in scope.
    """

    async def notify(
        self,
        *,
        recipient_id: UUID,
        kind: NotifKind,
        payload: dict[str, Any],
    ) -> None: ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/unit/domain/notifications/test_notification.py -v`
Expected: 6 PASSED.

- [ ] **Step 5: Run the full unit suite to confirm no regression**

Run: `.venv/bin/pytest tests/unit/ -q`
Expected: all green (subscription tests still pass — they only use `SUBSCRIPTION_CHANGED`).

- [ ] **Step 6: Commit**

```bash
git add app/domain/notifications/service.py tests/unit/domain/notifications/
git commit -m "$(cat <<'EOF'
feat(notifications): extend NotifKind with four booking values

Plan 07 task 1. Adds BOOKING_REQUESTED / BOOKING_APPROVED /
BOOKING_REJECTED / BOOKING_CANCELLED so Plan 08 handlers can emit
without further schema changes. BOOKING_RATED intentionally omitted
per spec §1.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: `Notification` aggregate

**Files:**
- Create: `app/domain/notifications/notification.py`
- Test: `tests/unit/domain/notifications/test_notification.py` (extend)

- [ ] **Step 1: Write the failing tests**

Append to `tests/unit/domain/notifications/test_notification.py`:

```python
from datetime import datetime, timezone
from uuid import UUID, uuid4

from app.domain.notifications.notification import Notification


def _now() -> datetime:
    return datetime(2026, 4, 26, 12, 0, 0, tzinfo=timezone.utc)


def test_notification_create_sets_all_fields():
    rid = uuid4()
    n = Notification.create(
        recipient_id=rid,
        kind=NotifKind.SUBSCRIPTION_CHANGED,
        payload={"old_status": "TRIALING", "new_status": "INACTIVE"},
        now=_now(),
    )
    assert isinstance(n.id, UUID)
    assert n.recipient_id == rid
    assert n.kind is NotifKind.SUBSCRIPTION_CHANGED
    assert n.payload == {"old_status": "TRIALING", "new_status": "INACTIVE"}
    assert n.read_at is None
    assert n.created_at == _now()
    assert n.updated_at == _now()


def test_notification_create_generates_unique_ids():
    n1 = Notification.create(
        recipient_id=uuid4(),
        kind=NotifKind.SUBSCRIPTION_CHANGED,
        payload={},
        now=_now(),
    )
    n2 = Notification.create(
        recipient_id=uuid4(),
        kind=NotifKind.SUBSCRIPTION_CHANGED,
        payload={},
        now=_now(),
    )
    assert n1.id != n2.id


def test_mark_read_sets_read_at_when_unread():
    n = Notification.create(
        recipient_id=uuid4(),
        kind=NotifKind.SUBSCRIPTION_CHANGED,
        payload={},
        now=_now(),
    )
    later = datetime(2026, 4, 26, 13, 0, 0, tzinfo=timezone.utc)
    n.mark_read(now=later)
    assert n.read_at == later
    assert n.updated_at == later


def test_mark_read_is_idempotent_when_already_read():
    n = Notification.create(
        recipient_id=uuid4(),
        kind=NotifKind.SUBSCRIPTION_CHANGED,
        payload={},
        now=_now(),
    )
    first_read = datetime(2026, 4, 26, 13, 0, 0, tzinfo=timezone.utc)
    second_read = datetime(2026, 4, 26, 14, 0, 0, tzinfo=timezone.utc)
    n.mark_read(now=first_read)
    n.mark_read(now=second_read)
    assert n.read_at == first_read  # not bumped
    assert n.updated_at == first_read  # also not bumped
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/unit/domain/notifications/test_notification.py -v`
Expected: import error — `cannot import name 'Notification'`.

- [ ] **Step 3: Create `app/domain/notifications/notification.py`**

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
            payload=dict(payload),
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

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/unit/domain/notifications/test_notification.py -v`
Expected: all 10 PASSED.

- [ ] **Step 5: Commit**

```bash
git add app/domain/notifications/notification.py tests/unit/domain/notifications/test_notification.py
git commit -m "$(cat <<'EOF'
feat(notifications): Notification aggregate with idempotent mark_read

Plan 07 task 2. BaseEntity-backed aggregate. create() takes a now
parameter (matches Plan 06 convention); mark_read is idempotent on
already-read instances. Payload is copied via dict() to defeat caller
aliasing.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: `INotificationRepository` Protocol

**Files:**
- Create: `app/domain/notifications/repository.py`

This task has no production tests (Protocols are structural; consumers test against the interface via fakes). The architecture test suite will ensure later tasks honor the layer rules.

- [ ] **Step 1: Create `app/domain/notifications/repository.py`**

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

- [ ] **Step 2: Smoke import**

Run: `.venv/bin/python -c "from app.domain.notifications.repository import INotificationRepository; print(INotificationRepository.__name__)"`
Expected: `INotificationRepository` printed.

- [ ] **Step 3: Run unit suite**

Run: `.venv/bin/pytest tests/unit/ -q`
Expected: all green.

- [ ] **Step 4: Commit**

```bash
git add app/domain/notifications/repository.py
git commit -m "$(cat <<'EOF'
feat(notifications): INotificationRepository Protocol

Plan 07 task 3. Four-method port: add, get_for_recipient (enforces
ownership at repo layer to prevent leaking 403), list_by_recipient
(cursor + unread_only), update.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: `NotificationModel` SQLAlchemy mapping

**Files:**
- Create: `app/infrastructure/db/mappings/notification.py`

- [ ] **Step 1: Create the mapping file**

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

- [ ] **Step 2: Wire into Alembic env**

Edit `app/migrations/env.py`. Find the existing block:

```python
from app.infrastructure.db.mappings import owner_subscription  # noqa: F401
from app.infrastructure.db.mappings import resource  # noqa: F401
from app.infrastructure.db.mappings import resource_type  # noqa: F401  (registers metadata)
from app.infrastructure.db.mappings import user  # noqa: F401
```

Add a new import (alphabetically positioned after `user` is fine — order is irrelevant for metadata side-effect):

```python
from app.infrastructure.db.mappings import notification  # noqa: F401
```

The block becomes:

```python
from app.infrastructure.db.mappings import notification  # noqa: F401
from app.infrastructure.db.mappings import owner_subscription  # noqa: F401
from app.infrastructure.db.mappings import resource  # noqa: F401
from app.infrastructure.db.mappings import resource_type  # noqa: F401  (registers metadata)
from app.infrastructure.db.mappings import user  # noqa: F401
```

- [ ] **Step 3: Wire into the integration conftest**

Edit `tests/integration/conftest.py`. Find:

```python
from app.infrastructure.db.mappings import resource, resource_type, user  # noqa: F401
```

Replace with:

```python
from app.infrastructure.db.mappings import (  # noqa: F401
    notification, owner_subscription, resource, resource_type, user,
)
```

(Note: `owner_subscription` was missing from the conftest at Plan 06 close — including it here as a defensive add since some integration tests transitively touch its tables.)

- [ ] **Step 4: Smoke-test the mapping**

Run: `.venv/bin/python -c "from app.infrastructure.db.mappings.notification import NotificationModel; print(NotificationModel.__tablename__, [c.name for c in NotificationModel.__table__.columns])"`
Expected: `notifications ['id', 'recipient_id', 'kind', 'payload', 'read_at', 'created_at', 'updated_at']`

- [ ] **Step 5: Commit**

```bash
git add app/infrastructure/db/mappings/notification.py app/migrations/env.py tests/integration/conftest.py
git commit -m "$(cat <<'EOF'
feat(notifications): NotificationModel mapping

Plan 07 task 4. Declarative model with CHAR(36) UUIDs, JSON payload,
composite index (recipient_id, created_at, id) for cursor paging.
Registered in migrations env.py and integration conftest.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Alembic migration for `notifications` table

**Files:**
- Create: `app/migrations/versions/<auto-timestamp>_notifications_table.py`

- [ ] **Step 1: Generate the migration**

Run: `make migrate-new msg="notifications_table"`

A new file appears under `app/migrations/versions/`. Open it.

- [ ] **Step 2: Inspect and tighten the auto-generated migration**

The file should contain `op.create_table("notifications", ...)` and `op.create_index("idx_notifications_recipient_created", ...)`. Verify against the spec §4 shape; if Alembic produced extra constraints from `OwnerSubscriptionModel`/`ResourceModel` autogenerate noise, scrub them.

The expected `upgrade()` body (replace if autogen produced something different):

```python
def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column("id", sa.CHAR(36), primary_key=True, nullable=False),
        sa.Column("recipient_id", sa.CHAR(36), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_notifications_recipient_id",
        "notifications",
        ["recipient_id"],
    )
    op.create_index(
        "idx_notifications_recipient_created",
        "notifications",
        ["recipient_id", "created_at", "id"],
    )


def downgrade() -> None:
    op.drop_index("idx_notifications_recipient_created", table_name="notifications")
    op.drop_index("ix_notifications_recipient_id", table_name="notifications")
    op.drop_table("notifications")
```

(`ix_notifications_recipient_id` comes from `index=True` on the column; the named composite is the explicit `Index(...)`.)

- [ ] **Step 3: Run migrations against the dev DB**

Run: `make migrate-up`
Expected: migration applies cleanly. No errors.

- [ ] **Step 4: Verify schema**

Run: `.venv/bin/python -c "
from sqlalchemy import create_engine, inspect
from app.core.config import get_settings
e = create_engine(get_settings().database_url.replace('+asyncpg', '+psycopg').replace('+aiosqlite', ''))
print(sorted(inspect(e).get_columns('notifications'), key=lambda c: c['name']))
"`

Expected: lists 7 columns matching the table schema. (Skip this step if your local DB is sqlite-only — covered by the integration test suite next.)

- [ ] **Step 5: Commit**

```bash
git add app/migrations/versions/
git commit -m "$(cat <<'EOF'
feat(notifications): alembic migration for notifications table

Plan 07 task 5. Creates notifications table + composite index for
cursor paging.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: `SQLAlchemyNotificationRepository` (full implementation)

**Files:**
- Create: `app/infrastructure/repositories/notification_repository.py`
- Test: `tests/integration/notifications/test_notification_repository.py`

- [ ] **Step 1: Write failing integration tests**

Create `tests/integration/notifications/__init__.py` (empty) and `tests/integration/notifications/test_notification_repository.py`:

```python
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.domain.notifications.notification import Notification
from app.domain.notifications.service import NotifKind
from app.infrastructure.repositories.notification_repository import (
    SQLAlchemyNotificationRepository,
)


pytestmark = pytest.mark.asyncio


def _now() -> datetime:
    return datetime(2026, 4, 26, 12, 0, 0, tzinfo=timezone.utc)


async def test_add_and_round_trip(db_session):
    repo = SQLAlchemyNotificationRepository(db_session)
    rid = uuid4()
    n = Notification.create(
        recipient_id=rid,
        kind=NotifKind.SUBSCRIPTION_CHANGED,
        payload={"old_status": "TRIALING", "new_status": "INACTIVE"},
        now=_now(),
    )
    add_r = await repo.add(n)
    assert add_r.is_success

    fetched = await repo.get_for_recipient(n.id, rid)
    assert fetched.is_success
    assert fetched.value is not None
    assert fetched.value.id == n.id
    assert fetched.value.kind is NotifKind.SUBSCRIPTION_CHANGED
    assert fetched.value.payload == {"old_status": "TRIALING", "new_status": "INACTIVE"}
    assert fetched.value.read_at is None


async def test_get_for_recipient_returns_none_on_cross_recipient(db_session):
    repo = SQLAlchemyNotificationRepository(db_session)
    owner_id = uuid4()
    intruder_id = uuid4()
    n = Notification.create(
        recipient_id=owner_id, kind=NotifKind.SUBSCRIPTION_CHANGED,
        payload={}, now=_now(),
    )
    await repo.add(n)
    fetched = await repo.get_for_recipient(n.id, intruder_id)
    assert fetched.is_success
    assert fetched.value is None


async def test_list_by_recipient_orders_newest_first(db_session):
    repo = SQLAlchemyNotificationRepository(db_session)
    rid = uuid4()
    base = _now()
    notifs = []
    for i in range(3):
        n = Notification.create(
            recipient_id=rid,
            kind=NotifKind.SUBSCRIPTION_CHANGED,
            payload={"i": i},
            now=base + timedelta(minutes=i),
        )
        await repo.add(n)
        notifs.append(n)

    listed = await repo.list_by_recipient(
        rid, limit=10, cursor=None, unread_only=False,
    )
    assert listed.is_success
    ids = [n.id for n in listed.value]
    assert ids == [notifs[2].id, notifs[1].id, notifs[0].id]


async def test_list_by_recipient_filters_other_recipients(db_session):
    repo = SQLAlchemyNotificationRepository(db_session)
    rid = uuid4()
    other = uuid4()
    n_mine = Notification.create(
        recipient_id=rid, kind=NotifKind.SUBSCRIPTION_CHANGED,
        payload={}, now=_now(),
    )
    n_theirs = Notification.create(
        recipient_id=other, kind=NotifKind.SUBSCRIPTION_CHANGED,
        payload={}, now=_now(),
    )
    await repo.add(n_mine)
    await repo.add(n_theirs)

    listed = await repo.list_by_recipient(
        rid, limit=10, cursor=None, unread_only=False,
    )
    assert listed.is_success
    assert [n.id for n in listed.value] == [n_mine.id]


async def test_list_by_recipient_unread_only_filter(db_session):
    repo = SQLAlchemyNotificationRepository(db_session)
    rid = uuid4()
    base = _now()
    read_n = Notification.create(
        recipient_id=rid, kind=NotifKind.SUBSCRIPTION_CHANGED,
        payload={}, now=base,
    )
    read_n.mark_read(now=base + timedelta(minutes=5))
    unread_n = Notification.create(
        recipient_id=rid, kind=NotifKind.SUBSCRIPTION_CHANGED,
        payload={}, now=base + timedelta(minutes=1),
    )
    await repo.add(read_n)
    await repo.add(unread_n)

    listed = await repo.list_by_recipient(
        rid, limit=10, cursor=None, unread_only=True,
    )
    assert listed.is_success
    assert [n.id for n in listed.value] == [unread_n.id]


async def test_list_by_recipient_cursor_pagination(db_session):
    repo = SQLAlchemyNotificationRepository(db_session)
    rid = uuid4()
    base = _now()
    notifs = []
    for i in range(5):
        n = Notification.create(
            recipient_id=rid, kind=NotifKind.SUBSCRIPTION_CHANGED,
            payload={"i": i}, now=base + timedelta(minutes=i),
        )
        await repo.add(n)
        notifs.append(n)

    page1 = await repo.list_by_recipient(rid, limit=2, cursor=None, unread_only=False)
    assert page1.is_success
    assert [n.id for n in page1.value] == [notifs[4].id, notifs[3].id]

    page2 = await repo.list_by_recipient(
        rid, limit=2, cursor=notifs[3].id, unread_only=False,
    )
    assert page2.is_success
    assert [n.id for n in page2.value] == [notifs[2].id, notifs[1].id]


async def test_update_persists_read_at(db_session):
    repo = SQLAlchemyNotificationRepository(db_session)
    rid = uuid4()
    n = Notification.create(
        recipient_id=rid, kind=NotifKind.SUBSCRIPTION_CHANGED,
        payload={}, now=_now(),
    )
    await repo.add(n)
    n.mark_read(now=_now() + timedelta(hours=1))
    update_r = await repo.update(n)
    assert update_r.is_success

    fetched = await repo.get_for_recipient(n.id, rid)
    assert fetched.value.read_at == _now() + timedelta(hours=1)


async def test_update_returns_failure_when_id_missing(db_session):
    repo = SQLAlchemyNotificationRepository(db_session)
    n = Notification.create(
        recipient_id=uuid4(), kind=NotifKind.SUBSCRIPTION_CHANGED,
        payload={}, now=_now(),
    )
    # not added — update should fail.
    update_r = await repo.update(n)
    assert update_r.is_failure
    assert update_r.error == "NotificationNotFound"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/integration/notifications/test_notification_repository.py -v`
Expected: import error — `cannot import name 'SQLAlchemyNotificationRepository'`.

- [ ] **Step 3: Create `app/infrastructure/repositories/notification_repository.py`**

```python
from __future__ import annotations
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.notifications.notification import Notification
from app.domain.notifications.repository import INotificationRepository
from app.domain.notifications.service import NotifKind
from app.domain.shared.result import Result
from app.infrastructure.db.mappings.notification import NotificationModel


def _ensure_utc(dt: datetime | None) -> datetime | None:
    """SQLite + aiosqlite drop tzinfo on roundtrip; assume stored values are UTC."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


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
        payload=dict(model.payload or {}),
        read_at=_ensure_utc(model.read_at),
        created_at=_ensure_utc(model.created_at),
        updated_at=_ensure_utc(model.updated_at),
    )


class SQLAlchemyNotificationRepository(INotificationRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, notification: Notification) -> Result[None]:
        self._session.add(NotificationModel(**_to_model_kwargs(notification)))
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
            cursor_created = (
                await self._session.execute(cursor_stmt)
            ).scalar_one_or_none()
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

    async def update(self, notification: Notification) -> Result[None]:
        stmt = select(NotificationModel).where(
            NotificationModel.id == str(notification.id),
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        if row is None:
            return Result.failure("NotificationNotFound", status_code=404)
        kwargs = _to_model_kwargs(notification)
        for k, v in kwargs.items():
            if k == "id":
                continue
            setattr(row, k, v)
        await self._session.flush()
        return Result.success(None)
```

- [ ] **Step 4: Run integration tests**

Run: `.venv/bin/pytest tests/integration/notifications/ -v`
Expected: all 8 PASSED.

- [ ] **Step 5: Run unit + integration suite to confirm no regression**

Run: `.venv/bin/pytest tests/unit/ tests/integration/ -q`
Expected: all green.

- [ ] **Step 6: Commit**

```bash
git add app/infrastructure/repositories/notification_repository.py tests/integration/notifications/
git commit -m "$(cat <<'EOF'
feat(notifications): SQLAlchemyNotificationRepository

Plan 07 task 6. Implements the four-method INotificationRepository
port over AsyncSession. get_for_recipient enforces ownership at
repo level (returns None on cross-recipient access — never leaks
a 403). list_by_recipient supports cursor pagination ordered by
(created_at DESC, id DESC) with optional unread_only filter.
update returns NotificationNotFound 404 on missing id (defensive).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: `PersistentNotificationService` adapter (replaces `LoggingNotificationService`)

**Files:**
- Create: `app/infrastructure/notifications/persistent_notification_service.py`
- Delete: `app/infrastructure/notifications/logging_notification_service.py`
- Test: `tests/unit/infrastructure/notifications/test_persistent_notification_service.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/infrastructure/notifications/__init__.py` (empty) and `tests/unit/infrastructure/notifications/test_persistent_notification_service.py`:

```python
from __future__ import annotations
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

import pytest

from app.domain.notifications.notification import Notification
from app.domain.notifications.service import NotifKind
from app.domain.shared.result import Result
from app.infrastructure.notifications.persistent_notification_service import (
    PersistentNotificationService,
)


pytestmark = pytest.mark.asyncio


class _SpyRepo:
    """Minimal IN-memory repo for service-level testing."""

    def __init__(self, fail: bool = False) -> None:
        self.added: list[Notification] = []
        self.fail = fail

    async def add(self, notif: Notification) -> Result[None]:
        if self.fail:
            return Result.failure("RepoBoom")
        self.added.append(notif)
        return Result.success(None)

    async def get_for_recipient(self, *args, **kwargs):  # not used here
        raise NotImplementedError

    async def list_by_recipient(self, *args, **kwargs):  # not used here
        raise NotImplementedError

    async def update(self, *args, **kwargs):  # not used here
        raise NotImplementedError


async def test_notify_persists_a_row():
    repo = _SpyRepo()
    svc = PersistentNotificationService(repo)
    rid = uuid4()
    await svc.notify(
        recipient_id=rid,
        kind=NotifKind.SUBSCRIPTION_CHANGED,
        payload={"old_status": "TRIALING", "new_status": "ACTIVE"},
    )
    assert len(repo.added) == 1
    n = repo.added[0]
    assert isinstance(n, Notification)
    assert n.recipient_id == rid
    assert n.kind is NotifKind.SUBSCRIPTION_CHANGED
    assert n.payload == {"old_status": "TRIALING", "new_status": "ACTIVE"}
    assert n.read_at is None
    assert n.created_at.tzinfo is timezone.utc


async def test_notify_swallows_repo_failures(caplog):
    repo = _SpyRepo(fail=True)
    svc = PersistentNotificationService(repo)
    with caplog.at_level(logging.WARNING):
        await svc.notify(
            recipient_id=uuid4(),
            kind=NotifKind.SUBSCRIPTION_CHANGED,
            payload={},
        )
    assert any("notification persistence failed" in r.message for r in caplog.records)
    # And critically: no exception raised — fire-and-forget invariant.
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/unit/infrastructure/notifications/ -v`
Expected: import error — `cannot import name 'PersistentNotificationService'`.

- [ ] **Step 3: Create the service**

Create `app/infrastructure/notifications/persistent_notification_service.py`:

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

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/unit/infrastructure/notifications/ -v`
Expected: 2 PASSED.

- [ ] **Step 5: Delete the old logging adapter**

```bash
rm app/infrastructure/notifications/logging_notification_service.py
```

(Call sites still importing it are fixed in Task 14. The deletion right now will surface a focused failure list when running the suite next.)

- [ ] **Step 6: Run the unit suite — expect failures in admin_subscriptions/deps and the cron job until Task 14**

Run: `.venv/bin/pytest tests/unit/ -q`
Expected: 2 import-time failures (`admin_subscriptions/deps.py` + `app/jobs/expire_trialing_subscriptions.py`). Subscription handler tests still pass — they use `FakeNotificationService`, not the deleted concrete one.

(This is intentional. Task 14 wires the replacement; we keep those failures pinned for one task to make the rewire mechanical.)

- [ ] **Step 7: Commit**

```bash
git add app/infrastructure/notifications/persistent_notification_service.py tests/unit/infrastructure/notifications/
git rm app/infrastructure/notifications/logging_notification_service.py
git commit -m "$(cat <<'EOF'
feat(notifications): PersistentNotificationService replaces logging stub

Plan 07 task 7. New adapter persists each notify() call as a
Notification row via INotificationRepository. Repo failures log a
warning but do not raise — fire-and-forget invariant preserved so
emitting handlers (set_owner_subscription_status, expire_trialing)
never fail because of notification trouble.

LoggingNotificationService deleted; admin_subscriptions/deps.py and
app/jobs/expire_trialing_subscriptions.py rewired in Task 14.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: Use case DTOs

**Files:**
- Create: `app/use_cases/notifications/__init__.py` (empty)
- Create: `app/use_cases/notifications/dtos.py`

- [ ] **Step 1: Create the DTO module**

Create `app/use_cases/notifications/__init__.py` (empty) and `app/use_cases/notifications/dtos.py`:

```python
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from app.domain.notifications.notification import Notification


@dataclass(frozen=True, kw_only=True, slots=True)
class NotificationDto:
    id: UUID
    kind: str
    payload: dict[str, Any]
    read_at: datetime | None
    created_at: datetime

    @classmethod
    def from_entity(cls, notif: Notification) -> "NotificationDto":
        return cls(
            id=notif.id,
            kind=notif.kind.value,
            payload=dict(notif.payload),
            read_at=notif.read_at,
            created_at=notif.created_at,
        )


@dataclass(frozen=True, kw_only=True, slots=True)
class NotificationListDto:
    items: tuple[NotificationDto, ...]
    next_cursor: UUID | None
```

- [ ] **Step 2: Smoke import**

Run: `.venv/bin/python -c "from app.use_cases.notifications.dtos import NotificationDto, NotificationListDto; print('ok')"`
Expected: `ok`.

- [ ] **Step 3: Commit**

```bash
git add app/use_cases/notifications/
git commit -m "$(cat <<'EOF'
feat(notifications): use case DTOs

Plan 07 task 8. NotificationDto.from_entity() flattens kind to its
str value for the HTTP boundary; NotificationListDto pairs items
with next_cursor for cursor pagination.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 9: `InMemoryNotificationRepository` test fake

**Files:**
- Create: `tests/unit/use_cases/notifications/__init__.py` (empty)
- Create: `tests/unit/use_cases/notifications/fakes/__init__.py` (empty)
- Create: `tests/unit/use_cases/notifications/fakes/in_memory_notification_repository.py`

This is a test-only dependency for the next two tasks. No production tests; the fake exercises itself implicitly when used by the handler tests.

- [ ] **Step 1: Create the fake**

```python
from __future__ import annotations
from uuid import UUID

from app.domain.notifications.notification import Notification
from app.domain.notifications.repository import INotificationRepository
from app.domain.shared.result import Result


class InMemoryNotificationRepository(INotificationRepository):
    """List-backed implementation for handler tests. Mirrors the SQL repo's
    ordering (newest first, cursor-aware) but skips IntegrityError handling.
    """

    def __init__(self) -> None:
        self._rows: list[Notification] = []

    async def add(self, notification: Notification) -> Result[None]:
        self._rows.append(notification)
        return Result.success(None)

    async def get_for_recipient(
        self, notification_id: UUID, recipient_id: UUID,
    ) -> Result[Notification | None]:
        for n in self._rows:
            if n.id == notification_id and n.recipient_id == recipient_id:
                return Result.success(n)
        return Result.success(None)

    async def list_by_recipient(
        self,
        recipient_id: UUID,
        *,
        limit: int,
        cursor: UUID | None,
        unread_only: bool,
    ) -> Result[list[Notification]]:
        ordered = sorted(
            (n for n in self._rows if n.recipient_id == recipient_id),
            key=lambda n: (n.created_at, n.id),
            reverse=True,
        )
        if unread_only:
            ordered = [n for n in ordered if n.read_at is None]
        if cursor is not None:
            cursor_row = next((n for n in self._rows if n.id == cursor), None)
            if cursor_row is not None:
                ordered = [
                    n for n in ordered
                    if (n.created_at, n.id) < (cursor_row.created_at, cursor_row.id)
                ]
        return Result.success(ordered[:limit])

    async def update(self, notification: Notification) -> Result[None]:
        for i, existing in enumerate(self._rows):
            if existing.id == notification.id:
                self._rows[i] = notification
                return Result.success(None)
        return Result.failure("NotificationNotFound", status_code=404)
```

- [ ] **Step 2: Smoke import**

Run: `.venv/bin/python -c "from tests.unit.use_cases.notifications.fakes.in_memory_notification_repository import InMemoryNotificationRepository; print('ok')"`
Expected: `ok`.

- [ ] **Step 3: Commit**

```bash
git add tests/unit/use_cases/notifications/
git commit -m "$(cat <<'EOF'
test(notifications): InMemoryNotificationRepository fake

Plan 07 task 9. Mirrors SQL repo cursor semantics for handler tests.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 10: `ListMyNotificationsHandler` query

**Files:**
- Create: `app/use_cases/notifications/queries/__init__.py` (empty)
- Create: `app/use_cases/notifications/queries/list_my_notifications.py`
- Test: `tests/unit/use_cases/notifications/queries/__init__.py` (empty)
- Test: `tests/unit/use_cases/notifications/queries/test_list_my_notifications.py`

- [ ] **Step 1: Write failing tests**

```python
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.domain.notifications.notification import Notification
from app.domain.notifications.service import NotifKind
from app.use_cases.notifications.queries.list_my_notifications import (
    ListMyNotificationsHandler,
    ListMyNotificationsQuery,
)
from tests.unit.use_cases.notifications.fakes.in_memory_notification_repository import (
    InMemoryNotificationRepository,
)


pytestmark = pytest.mark.asyncio


def _now() -> datetime:
    return datetime(2026, 4, 26, 12, 0, 0, tzinfo=timezone.utc)


async def test_returns_my_notifications_newest_first():
    repo = InMemoryNotificationRepository()
    rid = uuid4()
    older = Notification.create(
        recipient_id=rid, kind=NotifKind.SUBSCRIPTION_CHANGED,
        payload={}, now=_now(),
    )
    newer = Notification.create(
        recipient_id=rid, kind=NotifKind.BOOKING_REQUESTED,
        payload={}, now=_now() + timedelta(minutes=5),
    )
    await repo.add(older)
    await repo.add(newer)

    handler = ListMyNotificationsHandler(repo)
    result = await handler.handle(
        ListMyNotificationsQuery(actor_id=rid, limit=50, cursor=None, unread_only=False)
    )
    assert result.is_success
    ids = [n.id for n in result.value.items]
    assert ids == [newer.id, older.id]
    assert result.value.next_cursor is None


async def test_clamps_limit_to_max_100():
    repo = InMemoryNotificationRepository()
    rid = uuid4()
    handler = ListMyNotificationsHandler(repo)
    # Inject 105 notifs
    base = _now()
    for i in range(105):
        n = Notification.create(
            recipient_id=rid, kind=NotifKind.SUBSCRIPTION_CHANGED,
            payload={"i": i}, now=base + timedelta(seconds=i),
        )
        await repo.add(n)

    result = await handler.handle(
        ListMyNotificationsQuery(actor_id=rid, limit=500, cursor=None, unread_only=False)
    )
    assert result.is_success
    assert len(result.value.items) == 100
    assert result.value.next_cursor is not None  # 5 more rows beyond


async def test_clamps_limit_to_min_1():
    repo = InMemoryNotificationRepository()
    rid = uuid4()
    handler = ListMyNotificationsHandler(repo)
    n = Notification.create(
        recipient_id=rid, kind=NotifKind.SUBSCRIPTION_CHANGED,
        payload={}, now=_now(),
    )
    await repo.add(n)

    result = await handler.handle(
        ListMyNotificationsQuery(actor_id=rid, limit=0, cursor=None, unread_only=False)
    )
    assert result.is_success
    assert len(result.value.items) == 1


async def test_next_cursor_set_when_more_pages():
    repo = InMemoryNotificationRepository()
    rid = uuid4()
    handler = ListMyNotificationsHandler(repo)
    base = _now()
    notifs = []
    for i in range(3):
        n = Notification.create(
            recipient_id=rid, kind=NotifKind.SUBSCRIPTION_CHANGED,
            payload={}, now=base + timedelta(seconds=i),
        )
        await repo.add(n)
        notifs.append(n)

    result = await handler.handle(
        ListMyNotificationsQuery(actor_id=rid, limit=2, cursor=None, unread_only=False)
    )
    assert result.is_success
    items = result.value.items
    assert [n.id for n in items] == [notifs[2].id, notifs[1].id]
    assert result.value.next_cursor == notifs[1].id


async def test_next_cursor_none_when_last_page():
    repo = InMemoryNotificationRepository()
    rid = uuid4()
    handler = ListMyNotificationsHandler(repo)
    base = _now()
    for i in range(2):
        await repo.add(Notification.create(
            recipient_id=rid, kind=NotifKind.SUBSCRIPTION_CHANGED,
            payload={}, now=base + timedelta(seconds=i),
        ))

    result = await handler.handle(
        ListMyNotificationsQuery(actor_id=rid, limit=5, cursor=None, unread_only=False)
    )
    assert result.is_success
    assert result.value.next_cursor is None


async def test_unread_only_filters_read_rows():
    repo = InMemoryNotificationRepository()
    rid = uuid4()
    handler = ListMyNotificationsHandler(repo)
    base = _now()
    read_n = Notification.create(
        recipient_id=rid, kind=NotifKind.SUBSCRIPTION_CHANGED,
        payload={}, now=base,
    )
    read_n.mark_read(now=base + timedelta(seconds=10))
    unread_n = Notification.create(
        recipient_id=rid, kind=NotifKind.SUBSCRIPTION_CHANGED,
        payload={}, now=base + timedelta(seconds=1),
    )
    await repo.add(read_n)
    await repo.add(unread_n)

    result = await handler.handle(
        ListMyNotificationsQuery(actor_id=rid, limit=10, cursor=None, unread_only=True)
    )
    assert result.is_success
    assert [n.id for n in result.value.items] == [unread_n.id]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/unit/use_cases/notifications/queries/ -v`
Expected: import error — `cannot import name 'ListMyNotificationsHandler'`.

- [ ] **Step 3: Implement the handler**

Create `app/use_cases/notifications/queries/__init__.py` (empty) and `app/use_cases/notifications/queries/list_my_notifications.py`:

```python
from __future__ import annotations
from dataclasses import dataclass
from uuid import UUID

from app.domain.notifications.repository import INotificationRepository
from app.domain.shared.result import Result
from app.use_cases.notifications.dtos import NotificationDto, NotificationListDto


_MAX_LIMIT = 100


@dataclass(frozen=True, kw_only=True, slots=True)
class ListMyNotificationsQuery:
    actor_id: UUID
    limit: int = 50
    cursor: UUID | None = None
    unread_only: bool = False


class ListMyNotificationsHandler:
    def __init__(self, repository: INotificationRepository) -> None:
        self._repository = repository

    async def handle(
        self, query: ListMyNotificationsQuery,
    ) -> Result[NotificationListDto]:
        limit = max(1, min(query.limit, _MAX_LIMIT))
        list_r = await self._repository.list_by_recipient(
            query.actor_id,
            limit=limit + 1,           # fetch one extra to know if more pages exist
            cursor=query.cursor,
            unread_only=query.unread_only,
        )
        if list_r.is_failure:
            return Result.from_failure(list_r)
        rows = list_r.value
        has_more = len(rows) > limit
        page = rows[:limit]
        next_cursor = page[-1].id if has_more and page else None
        items = tuple(NotificationDto.from_entity(n) for n in page)
        return Result.success(NotificationListDto(items=items, next_cursor=next_cursor))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/unit/use_cases/notifications/queries/ -v`
Expected: 6 PASSED.

- [ ] **Step 5: Commit**

```bash
git add app/use_cases/notifications/queries/ tests/unit/use_cases/notifications/queries/
git commit -m "$(cat <<'EOF'
feat(notifications): ListMyNotificationsHandler

Plan 07 task 10. Cursor pagination via limit+1 lookahead. Limit
clamped to [1, 100]. unread_only filter delegates to the repo.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 11: `MarkNotificationReadHandler` command

**Files:**
- Create: `app/use_cases/notifications/commands/__init__.py` (empty)
- Create: `app/use_cases/notifications/commands/mark_notification_read.py`
- Test: `tests/unit/use_cases/notifications/commands/__init__.py` (empty)
- Test: `tests/unit/use_cases/notifications/commands/test_mark_notification_read.py`

- [ ] **Step 1: Write failing tests**

```python
from __future__ import annotations
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.domain.notifications.notification import Notification
from app.domain.notifications.service import NotifKind
from app.use_cases.notifications.commands.mark_notification_read import (
    MarkNotificationReadCommand,
    MarkNotificationReadHandler,
)
from tests.unit.use_cases.notifications.fakes.in_memory_notification_repository import (
    InMemoryNotificationRepository,
)


pytestmark = pytest.mark.asyncio


def _now() -> datetime:
    return datetime(2026, 4, 26, 12, 0, 0, tzinfo=timezone.utc)


async def test_marks_unread_notification_read():
    repo = InMemoryNotificationRepository()
    rid = uuid4()
    n = Notification.create(
        recipient_id=rid, kind=NotifKind.SUBSCRIPTION_CHANGED,
        payload={}, now=_now(),
    )
    await repo.add(n)
    handler = MarkNotificationReadHandler(repo)

    result = await handler.handle(
        MarkNotificationReadCommand(actor_id=rid, notification_id=n.id)
    )
    assert result.is_success

    fetched = (await repo.get_for_recipient(n.id, rid)).value
    assert fetched.read_at is not None


async def test_already_read_is_idempotent_success():
    repo = InMemoryNotificationRepository()
    rid = uuid4()
    n = Notification.create(
        recipient_id=rid, kind=NotifKind.SUBSCRIPTION_CHANGED,
        payload={}, now=_now(),
    )
    n.mark_read(now=_now())
    await repo.add(n)
    first_read_at = n.read_at

    handler = MarkNotificationReadHandler(repo)
    result = await handler.handle(
        MarkNotificationReadCommand(actor_id=rid, notification_id=n.id)
    )
    assert result.is_success

    fetched = (await repo.get_for_recipient(n.id, rid)).value
    assert fetched.read_at == first_read_at  # not bumped


async def test_cross_recipient_returns_404():
    repo = InMemoryNotificationRepository()
    owner_id = uuid4()
    intruder_id = uuid4()
    n = Notification.create(
        recipient_id=owner_id, kind=NotifKind.SUBSCRIPTION_CHANGED,
        payload={}, now=_now(),
    )
    await repo.add(n)

    handler = MarkNotificationReadHandler(repo)
    result = await handler.handle(
        MarkNotificationReadCommand(actor_id=intruder_id, notification_id=n.id)
    )
    assert result.is_failure
    assert result.error == "NotificationNotFound"
    assert result.status_code == 404


async def test_unknown_id_returns_404():
    repo = InMemoryNotificationRepository()
    handler = MarkNotificationReadHandler(repo)
    result = await handler.handle(
        MarkNotificationReadCommand(actor_id=uuid4(), notification_id=uuid4())
    )
    assert result.is_failure
    assert result.error == "NotificationNotFound"
    assert result.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/unit/use_cases/notifications/commands/ -v`
Expected: import error — `cannot import name 'MarkNotificationReadHandler'`.

- [ ] **Step 3: Implement the handler**

Create `app/use_cases/notifications/commands/__init__.py` (empty) and `app/use_cases/notifications/commands/mark_notification_read.py`:

```python
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from app.domain.notifications.repository import INotificationRepository
from app.domain.shared.result import Result


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True, kw_only=True, slots=True)
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

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/unit/use_cases/notifications/commands/ -v`
Expected: 4 PASSED.

- [ ] **Step 5: Run unit + integration suite to confirm only Task 7's pinned import errors remain**

Run: `.venv/bin/pytest tests/unit/ tests/integration/ -q --ignore=tests/unit/api`

Expected: only the two pinned import errors from Task 7 (admin_subscriptions deps, jobs/expire_trialing). Notification tests all green. (We ignore `tests/unit/api` until the API tasks ship.)

- [ ] **Step 6: Commit**

```bash
git add app/use_cases/notifications/commands/ tests/unit/use_cases/notifications/commands/
git commit -m "$(cat <<'EOF'
feat(notifications): MarkNotificationReadHandler

Plan 07 task 11. Cross-recipient access returns NotificationNotFound
404 (no leak). Already-read calls are idempotent successes.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 12: Register `NotificationNotFound` stable error code

**Files:**
- Modify: `app/api/error_codes.py`
- Modify: `tests/unit/architecture/test_error_code_coverage.py`

- [ ] **Step 1: Add the pt-BR mapping**

In `app/api/error_codes.py`, locate the "Resource handler-level (Plan 06)" block (around line 144) and add a new section just below it:

```python
    # Notifications (Plan 07) — handler-level
    "NotificationNotFound": "Notificação não encontrada.",
```

Insert it after the existing "Resource handler-level (Plan 06)" block, before the "ResourceType (entity-level codes — registered in arch test allowlist)" block. The exact placement is cosmetic; the dict key is what matters.

- [ ] **Step 2: Add to the architecture-test allowlist**

In `tests/unit/architecture/test_error_code_coverage.py`, find the `handler_level_allowlist: set[str] = {...}` block and add at the end (just before the closing brace), in a new section:

```python
        # Plan 07 — notifications
        "NotificationNotFound",
```

- [ ] **Step 3: Run the architecture test**

Run: `.venv/bin/pytest tests/unit/architecture/test_error_code_coverage.py -v`
Expected: PASSED.

- [ ] **Step 4: Commit**

```bash
git add app/api/error_codes.py tests/unit/architecture/test_error_code_coverage.py
git commit -m "$(cat <<'EOF'
feat(notifications): NotificationNotFound stable code + arch allowlist

Plan 07 task 12. pt-BR mapping in error_codes.py and allowlist
extension keep the architecture coverage check green.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 13: API schemas (Pydantic)

**Files:**
- Create: `app/api/v1/me_notifications/__init__.py` (empty)
- Create: `app/api/v1/me_notifications/schemas.py`

- [ ] **Step 1: Create the package init**

Create `app/api/v1/me_notifications/__init__.py` (empty file).

- [ ] **Step 2: Create the schemas**

`app/api/v1/me_notifications/schemas.py`:

```python
from __future__ import annotations
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.use_cases.notifications.dtos import NotificationDto, NotificationListDto


class NotificationResponse(BaseModel):
    id: UUID
    kind: str
    payload: dict[str, Any]
    read_at: datetime | None
    created_at: datetime

    @classmethod
    def from_dto(cls, dto: NotificationDto) -> "NotificationResponse":
        return cls(
            id=dto.id,
            kind=dto.kind,
            payload=dto.payload,
            read_at=dto.read_at,
            created_at=dto.created_at,
        )


class NotificationListResponse(BaseModel):
    items: list[NotificationResponse]
    next_cursor: UUID | None

    @classmethod
    def from_dto(cls, dto: NotificationListDto) -> "NotificationListResponse":
        return cls(
            items=[NotificationResponse.from_dto(n) for n in dto.items],
            next_cursor=dto.next_cursor,
        )
```

- [ ] **Step 3: Smoke import**

Run: `.venv/bin/python -c "from app.api.v1.me_notifications.schemas import NotificationListResponse; print('ok')"`
Expected: `ok`.

- [ ] **Step 4: Commit**

```bash
git add app/api/v1/me_notifications/__init__.py app/api/v1/me_notifications/schemas.py
git commit -m "$(cat <<'EOF'
feat(notifications): API schemas

Plan 07 task 13. NotificationResponse and NotificationListResponse
with from_dto constructors mirroring me_resources / me_subscription
conventions.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 14: API deps + routes + rewire existing call sites

**Files:**
- Create: `app/api/v1/me_notifications/deps.py`
- Create: `app/api/v1/me_notifications/routes.py`
- Modify: `app/api/v1/router.py`
- Modify: `app/api/v1/admin_subscriptions/deps.py`
- Modify: `app/jobs/expire_trialing_subscriptions.py`

This task fixes the two pinned import errors from Task 7 in the same commit as the new endpoints — the rewire is mechanical and adding it here keeps the suite green at task boundary.

- [ ] **Step 1: Create the deps**

`app/api/v1/me_notifications/deps.py`:

```python
from __future__ import annotations
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.session import get_session
from app.infrastructure.repositories.notification_repository import (
    SQLAlchemyNotificationRepository,
)
from app.use_cases.notifications.commands.mark_notification_read import (
    MarkNotificationReadHandler,
)
from app.use_cases.notifications.queries.list_my_notifications import (
    ListMyNotificationsHandler,
)


async def get_notification_repository(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> SQLAlchemyNotificationRepository:
    return SQLAlchemyNotificationRepository(session)


async def get_list_my_notifications_handler(
    repo: Annotated[
        SQLAlchemyNotificationRepository, Depends(get_notification_repository),
    ],
) -> ListMyNotificationsHandler:
    return ListMyNotificationsHandler(repo)


async def get_mark_notification_read_handler(
    repo: Annotated[
        SQLAlchemyNotificationRepository, Depends(get_notification_repository),
    ],
) -> MarkNotificationReadHandler:
    return MarkNotificationReadHandler(repo)
```

- [ ] **Step 2: Create the routes**

`app/api/v1/me_notifications/routes.py`:

```python
from __future__ import annotations
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import CurrentUser
from app.api.error_handler import unwrap
from app.api.v1.me_notifications.deps import (
    get_list_my_notifications_handler,
    get_mark_notification_read_handler,
)
from app.api.v1.me_notifications.schemas import NotificationListResponse
from app.use_cases.notifications.commands.mark_notification_read import (
    MarkNotificationReadCommand,
    MarkNotificationReadHandler,
)
from app.use_cases.notifications.queries.list_my_notifications import (
    ListMyNotificationsHandler,
    ListMyNotificationsQuery,
)


router = APIRouter(prefix="/v1/me/notifications", tags=["me"])


@router.get("", response_model=NotificationListResponse)
async def list_my_notifications(
    user: CurrentUser,
    handler: ListMyNotificationsHandler = Depends(get_list_my_notifications_handler),
    limit: int = Query(50, ge=1, le=100),
    cursor: UUID | None = Query(None),
    unread_only: bool = Query(False),
):
    dto = unwrap(
        await handler.handle(
            ListMyNotificationsQuery(
                actor_id=user.user_id,
                limit=limit,
                cursor=cursor,
                unread_only=unread_only,
            )
        )
    )
    return NotificationListResponse.from_dto(dto)


@router.post(
    "/{notification_id}/read",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)
async def mark_notification_read(
    notification_id: UUID,
    user: CurrentUser,
    handler: MarkNotificationReadHandler = Depends(
        get_mark_notification_read_handler,
    ),
):
    unwrap(
        await handler.handle(
            MarkNotificationReadCommand(
                actor_id=user.user_id, notification_id=notification_id,
            )
        )
    )
    return None
```

- [ ] **Step 3: Wire the router**

Edit `app/api/v1/router.py`. After `from app.api.v1.me_resources.routes import router as me_resources_router`, add:

```python
from app.api.v1.me_notifications.routes import router as me_notifications_router
```

After `api_router.include_router(me_resources_router)`, add:

```python
api_router.include_router(me_notifications_router)
```

- [ ] **Step 4: Rewire `admin_subscriptions/deps.py`**

Open `app/api/v1/admin_subscriptions/deps.py`. The current top-of-file imports a logger and `LoggingNotificationService`:

```python
from app.infrastructure.notifications.logging_notification_service import (
    LoggingNotificationService,
)
```

Replace with:

```python
from app.infrastructure.notifications.persistent_notification_service import (
    PersistentNotificationService,
)
from app.infrastructure.repositories.notification_repository import (
    SQLAlchemyNotificationRepository,
)
```

Then the `get_notification_service` provider (around line 39 — current body returns `LoggingNotificationService(_logger)`) becomes:

```python
async def get_notification_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> PersistentNotificationService:
    return PersistentNotificationService(
        SQLAlchemyNotificationRepository(session),
    )
```

If a `_logger = logging.getLogger(__name__)` module-level statement existed only to feed `LoggingNotificationService`, remove it. The `set_owner_subscription_status` handler dep that consumes `notifs: Annotated[..., Depends(get_notification_service)]` must update its annotation to `PersistentNotificationService`.

If the file imports `Annotated, Depends, AsyncSession, get_session` (it should — they're all already used by the surrounding deps), no new imports beyond the two service ones above.

- [ ] **Step 5: Rewire the cron job**

Edit `app/jobs/expire_trialing_subscriptions.py`. Replace:

```python
from app.infrastructure.notifications.logging_notification_service import (
    LoggingNotificationService,
)
```

with:

```python
from app.infrastructure.notifications.persistent_notification_service import (
    PersistentNotificationService,
)
from app.infrastructure.repositories.notification_repository import (
    SQLAlchemyNotificationRepository,
)
```

Find the line `notifications = LoggingNotificationService(logger)` (around line 29). Replace with:

```python
notifications = PersistentNotificationService(
    SQLAlchemyNotificationRepository(session),
)
```

If `logger` was used only there, the import of `logging.getLogger(__name__)` may now be unused — remove if so.

- [ ] **Step 6: Run the full unit + integration suite**

Run: `.venv/bin/pytest tests/unit/ tests/integration/ -q`
Expected: all green. The two pinned Task 7 import errors are now resolved.

- [ ] **Step 7: Smoke-boot the FastAPI app**

Run: `.venv/bin/python -c "
import asyncio
from app.main import app
routes = sorted(r.path for r in app.routes)
print(len(routes), 'routes')
print('me/notifications routes:', [r for r in routes if 'notifications' in r])
"`
Expected: ≥ 38 routes; the list includes `/v1/me/notifications` and `/v1/me/notifications/{notification_id}/read`.

- [ ] **Step 8: Commit**

```bash
git add app/api/v1/me_notifications/deps.py app/api/v1/me_notifications/routes.py \
        app/api/v1/router.py app/api/v1/admin_subscriptions/deps.py \
        app/jobs/expire_trialing_subscriptions.py
git commit -m "$(cat <<'EOF'
feat(notifications): /v1/me/notifications endpoints + rewire DI

Plan 07 task 14. Adds GET /v1/me/notifications (cursor pagination,
unread_only filter, limit clamp [1,100]) and POST
/v1/me/notifications/{id}/read (204, idempotent, 404 on
cross-recipient). Rewires admin_subscriptions/deps and the trial
expiry cron to PersistentNotificationService(SQLAlchemyNotification
Repository(session)) — removes the last LoggingNotificationService
references.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 15: E2E happy path (notification appears + mark read)

**Files:**
- Create: `tests/e2e/notifications/__init__.py` (empty)
- Create: `tests/e2e/notifications/test_inbox_lifecycle.py`

- [ ] **Step 1: Inspect an existing e2e test for the project's fixture conventions**

Skim `tests/e2e/resources/test_owner_lifecycle.py` (or any other e2e file) to confirm the auth-helper / client-fixture names. Match the same imports.

- [ ] **Step 2: Write the e2e test**

`tests/e2e/notifications/test_inbox_lifecycle.py`:

```python
from __future__ import annotations
from uuid import UUID

import pytest

from app.domain.subscriptions.sub_status import SubStatus

pytestmark = pytest.mark.asyncio


async def test_owner_sees_notification_after_subscription_transition(
    client, register_owner, login_admin,
):
    """End-to-end: admin transitions an owner's subscription → owner reads
    GET /v1/me/notifications and sees the SUBSCRIPTION_CHANGED row → owner
    POSTs /read → second GET shows read_at populated."""
    owner_token, owner_id = await register_owner()
    admin_token = await login_admin()

    # Admin transitions the subscription to INACTIVE
    resp = await client.post(
        f"/v1/admin/owners/{owner_id}/subscription",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"status": SubStatus.INACTIVE.value},
    )
    assert resp.status_code == 200, resp.text

    # Owner lists notifications — expects exactly 1 (TRIALING→INACTIVE)
    resp = await client.get(
        "/v1/me/notifications",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["next_cursor"] is None
    assert len(body["items"]) == 1
    notif = body["items"][0]
    assert notif["kind"] == "SUBSCRIPTION_CHANGED"
    assert notif["payload"]["new_status"] == "INACTIVE"
    assert notif["read_at"] is None

    # Mark read
    notif_id = notif["id"]
    resp = await client.post(
        f"/v1/me/notifications/{notif_id}/read",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert resp.status_code == 204, resp.text

    # Verify read_at is now populated
    resp = await client.get(
        "/v1/me/notifications",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    body = resp.json()
    assert body["items"][0]["read_at"] is not None

    # And unread_only=true returns empty
    resp = await client.get(
        "/v1/me/notifications?unread_only=true",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    body = resp.json()
    assert body["items"] == []


async def test_customer_inbox_starts_empty(client, register_customer):
    """Customers haven't done anything — inbox is empty."""
    token, _customer_id = await register_customer()
    resp = await client.get(
        "/v1/me/notifications",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["items"] == []
    assert body["next_cursor"] is None


async def test_mark_read_returns_204_when_already_read(
    client, register_owner, login_admin,
):
    owner_token, owner_id = await register_owner()
    admin_token = await login_admin()
    await client.post(
        f"/v1/admin/owners/{owner_id}/subscription",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"status": SubStatus.INACTIVE.value},
    )
    resp = await client.get(
        "/v1/me/notifications",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    notif_id = resp.json()["items"][0]["id"]

    # First read
    resp = await client.post(
        f"/v1/me/notifications/{notif_id}/read",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert resp.status_code == 204

    # Second read — idempotent
    resp = await client.post(
        f"/v1/me/notifications/{notif_id}/read",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert resp.status_code == 204
```

If the existing fixtures `register_owner`, `register_customer`, `login_admin` aren't named exactly that, rename to whatever the project's `tests/e2e/conftest.py` provides (Plan 06 added this kind of helper — confirm before running).

- [ ] **Step 3: Run the e2e**

Run: `.venv/bin/pytest tests/e2e/notifications/ -v`
Expected: 3 PASSED.

- [ ] **Step 4: Commit**

```bash
git add tests/e2e/notifications/
git commit -m "$(cat <<'EOF'
test(e2e): notifications inbox lifecycle

Plan 07 task 15. Owner sees SUBSCRIPTION_CHANGED row after admin
transition; mark-read flips read_at; unread_only filters it out;
double mark-read is idempotent 204; customer inbox starts empty.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 16: E2E cross-recipient 404

**Files:**
- Modify: `tests/e2e/notifications/test_inbox_lifecycle.py` (extend)

- [ ] **Step 1: Add a cross-recipient test**

Append to `tests/e2e/notifications/test_inbox_lifecycle.py`:

```python
async def test_cross_recipient_mark_read_returns_404(
    client, register_owner, register_customer, login_admin,
):
    owner_token, owner_id = await register_owner()
    admin_token = await login_admin()
    customer_token, _customer_id = await register_customer()

    # Trigger a notification on the owner.
    await client.post(
        f"/v1/admin/owners/{owner_id}/subscription",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"status": SubStatus.INACTIVE.value},
    )
    resp = await client.get(
        "/v1/me/notifications",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    notif_id = resp.json()["items"][0]["id"]

    # Customer tries to mark it read — should be 404 (no leak).
    resp = await client.post(
        f"/v1/me/notifications/{notif_id}/read",
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert resp.status_code == 404, resp.text
    body = resp.json()
    assert body["error"]["code"] == "NotificationNotFound"


async def test_unknown_id_returns_404(client, register_customer):
    token, _ = await register_customer()
    resp = await client.post(
        "/v1/me/notifications/00000000-0000-0000-0000-000000000000/read",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404, resp.text
    assert resp.json()["error"]["code"] == "NotificationNotFound"
```

(If the error envelope shape differs from `body["error"]["code"]` in this project, match what `app/api/error_handler.py` actually emits — check an existing 404 e2e in `tests/e2e/resources/` or similar to confirm.)

- [ ] **Step 2: Run the e2e**

Run: `.venv/bin/pytest tests/e2e/notifications/ -v`
Expected: 5 PASSED (3 from Task 15 + 2 new).

- [ ] **Step 3: Run the full test suite**

Run: `.venv/bin/pytest -q`
Expected: all green. Total count should be ~444 (Plan 06 baseline) + ~30 from Plan 07 ≈ ~470+.

- [ ] **Step 4: Commit**

```bash
git add tests/e2e/notifications/test_inbox_lifecycle.py
git commit -m "$(cat <<'EOF'
test(e2e): notifications cross-recipient + unknown-id return 404

Plan 07 task 16. Verifies NotificationNotFound is the response for
both lookup-failures so the API never reveals 'someone else's notif
exists'.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 17: Refresh canonical venue-backend spec (§3 #13, §4.2, §5.6, §8)

**Files:**
- Modify: `docs/superpowers/specs/2026-04-25-venue-backend-design.md`

This is a doc-only edit, parallel to Plan 06's task 38 (which refreshed §5.5). It captures Plan 07's deliberate departures from the original §5.6 wording so future plans don't accidentally reintroduce email/`BOOKING_RATED`.

- [ ] **Step 1: Refresh decision §3 #13**

Find the line:

```markdown
| 13 | Notifications: in-app inbox for every event + transactional email via a port (`IEmailSender`). Logging adapter for MVP; real provider later. | In-app alone gets missed; email is essentially free; port keeps WhatsApp/SMS a swap-in. |
```

Replace with:

```markdown
| 13 | Notifications: in-app inbox for every event. **Email deferred** (MVP scope cut, see plan-07-notifications-design.md §1; port reintroducible later). | In-app coverage is enough for the MVP feedback loop; email/SMS stays a future plan. |
```

- [ ] **Step 2: Refresh §4.2 cross-feature handler row for `CreateRatingHandler`**

Find:

```markdown
| `CreateRatingHandler` | `ratings/commands` | `IRatingRepository`, `IBookingRepository`, `INotificationService` | Verifies booking is APPROVED + ended + within 90d window + customer matches; persists rating; notifies owner. |
```

Replace with:

```markdown
| `CreateRatingHandler` | `ratings/commands` | `IRatingRepository`, `IBookingRepository` | Verifies booking is APPROVED + ended + within 90d window + customer matches; persists rating. (Plan 07 dropped the owner notification — `BOOKING_RATED` is out of scope; rating signal flows through `Resource.rating_avg` aggregates added by Plan 09.) |
```

- [ ] **Step 3: Refresh §5.6 `Notification` aggregate + `NotifKind`**

Replace the current §5.6 block (the `Notification` schema + `NotifKind` list + `IEmailSender` block + invariants) with:

```markdown
### 5.6 `notifications` — `Notification`

```
Notification
├── id: UUID
├── recipient_id: UUID
├── kind: NotifKind
├── payload: dict                           # JSON, kind-specific shape
├── read_at: datetime | None
└── created_at, updated_at

NotifKind
├── SUBSCRIPTION_CHANGED
├── BOOKING_REQUESTED
├── BOOKING_APPROVED
├── BOOKING_REJECTED
└── BOOKING_CANCELLED

INotificationService (Protocol, in domain/notifications/service.py)
└── notify(*, recipient_id, kind, payload) -> None        # fire-and-forget

INotificationRepository (Protocol, in domain/notifications/repository.py)
├── add(notification) -> Result[None]
├── get_for_recipient(notification_id, recipient_id) -> Result[Notification | None]
├── list_by_recipient(recipient_id, *, limit, cursor, unread_only) -> Result[list[Notification]]
└── update(notification) -> Result[None]
```

**Invariants**
- Every `notify(...)` call persists exactly one `Notification` row.
- Persistence failures inside `PersistentNotificationService` are logged and swallowed — emitting handlers never fail because of notification trouble.
- `mark_read(now)` is idempotent: calling on an already-read notification is a no-op.
- `get_for_recipient(...)` returns `None` for cross-recipient lookups so the API responds 404 (`NotificationNotFound`), never 403.

**Plan 07 deliberate cuts (see `docs/superpowers/specs/2026-04-26-plan-07-notifications-design.md`):**
- `BOOKING_RATED` removed — owner has no actionable response to a rating; Plan 09 adds `rating_avg`/`rating_count` aggregates on `Resource` GETs instead.
- `IEmailSender` port deferred — MVP ships in-app inbox only. The port can be reintroduced in a future plan without touching the inbox surface.
```

(Use the `<!-- raw markdown -->` style if the embedded fenced block confuses an editor — but `markdown` syntax inside a fenced block with a language tag of `markdown` works fine.)

- [ ] **Step 4: Refresh §8 plan 07 description**

Find:

```markdown
7. **Plan 07 — Notifications.** `Notification` aggregate + `IEmailSender` port + logging adapter. Includes `BOOKING_RATED` enum value.
```

Replace with:

```markdown
7. **Plan 07 — Notifications.** `Notification` aggregate (persistent in-app inbox) + `INotificationRepository` + `PersistentNotificationService` adapter. `NotifKind` grows to 5 values: `SUBSCRIPTION_CHANGED` (existing) plus `BOOKING_REQUESTED` / `BOOKING_APPROVED` / `BOOKING_REJECTED` / `BOOKING_CANCELLED` (Plan 08 emits). `GET /v1/me/notifications` (cursor paged) + `POST /v1/me/notifications/{id}/read`. Email and `BOOKING_RATED` deferred — see plan-07 design doc §1.
```

- [ ] **Step 5: Sanity check the doc still renders**

Run: `.venv/bin/python -c "
from pathlib import Path
text = Path('docs/superpowers/specs/2026-04-25-venue-backend-design.md').read_text()
assert 'BOOKING_RATED' not in text or 'dropped' in text.lower() or 'deferred' in text.lower()
assert 'IEmailSender' not in text or 'deferred' in text.lower() or 'reintroducible' in text.lower()
print('canonical spec refresh OK')
"`
Expected: `canonical spec refresh OK`. (The asserts allow the words to appear in the explicit "deferred / dropped" callout but not as live spec.)

- [ ] **Step 6: Commit**

```bash
git add docs/superpowers/specs/2026-04-25-venue-backend-design.md
git commit -m "$(cat <<'EOF'
docs(spec): refresh canonical §5.6 / §3 #13 / §4.2 / §8 with Plan 07 deltas

Plan 07 task 17. Drops BOOKING_RATED and IEmailSender from the
canonical spec, mirroring how Plan 06 task 38 refreshed §5.5 with
Plan 05 deltas. Future plans reading the canonical spec see the
MVP-scope-cut versions, not the original aspirational ones.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Final verification

- [ ] **Step 1: Run the entire test suite**

Run: `.venv/bin/pytest -q`
Expected: all green. Total count ~470+.

- [ ] **Step 2: Smoke-boot the FastAPI app**

Run: `.venv/bin/python -c "
from app.main import app
routes = sorted(r.path for r in app.routes)
print(len(routes), 'total routes')
notif_routes = [r for r in routes if 'notifications' in r]
print('notifications routes:', notif_routes)
assert '/v1/me/notifications' in notif_routes
assert '/v1/me/notifications/{notification_id}/read' in notif_routes
print('OK')
"`
Expected: ≥ 38 routes, both `/v1/me/notifications` paths present, prints `OK`.

- [ ] **Step 3: Confirm `LoggingNotificationService` is fully purged**

Run: `grep -rn "LoggingNotificationService" app/ tests/ 2>/dev/null`
Expected: no matches (the class and all imports are gone).

- [ ] **Step 4: Confirm `BOOKING_RATED` is fully purged from production code**

Run: `grep -rn "BOOKING_RATED" app/ tests/ 2>/dev/null`
Expected: no matches.

- [ ] **Step 5: Confirm `IEmailSender` is fully purged from production code**

Run: `grep -rn "IEmailSender" app/ tests/ 2>/dev/null`
Expected: no matches.

- [ ] **Step 6: Final commit (only if any verification shows untracked drift)**

If steps 1–5 all pass without changes, no commit needed. Otherwise: investigate, fix, commit.
