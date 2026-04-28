# Plan 09 — Ratings Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the ratings feature end-to-end: `Rating` aggregate (per-booking, score 1-5, optional comment, no moderation), `IRatingRepository` port, 4 handlers (create/update/list-mine/list-public), batch aggregate query for resource listings, retrofit 5 resource endpoints with `rating_avg` + `rating_count`, 4 new HTTP routes (3 customer + 1 public), canonical spec refresh dropping moderation surface.

**Architecture:** Aggregate in `app/domain/ratings/` with simple `Rating` entity (no state machine — ratings either exist within edit window or are immutable past it) and `RatingAggregate` frozen-dataclass value type for the read-side `(avg_score, count)` projection. Eligibility gates (booking is APPROVED + ended + customer match + within 90d) live in `CreateRatingHandler` because they need `Booking` context. 7-day edit window lives in `UpdateRatingHandler` because it needs `now()` clock. Concurrency: DB UNIQUE constraint on `booking_id` is the only race protection — duplicate submits race to the constraint and the loser gets 409. Persistence: one `ratings` row, three FK columns (booking, resource, customer) all `ON DELETE RESTRICT`, plain b-tree indexes, no Postgres-specific extensions. Resource listings batch-fetch aggregates via `IRatingRepository.get_aggregates_for_resources(ids)` to avoid N+1.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2 async, Alembic, Pydantic, pytest. Standard library `decimal.Decimal` for the rounded aggregate avg.

**Reference spec:** `docs/superpowers/specs/2026-04-28-plan-09-ratings-design.md`.

**Conventions reminders:**
- Always invoke Python via venv: `.venv/bin/python` or `.venv/bin/pytest`. Never use the global Python.
- Domain code never imports from `infrastructure` or `use_cases`.
- After each task, commit with a focused message ending in `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>`.
- TDD: failing test → RED → minimal impl → GREEN → commit.
- Mutators with state transitions return `Result[None]`; aggregate factories that take already-validated VOs and have no failure mode return the entity directly (e.g., `Rating.create` returns `Rating`, not `Result[Rating]`).
- pt-BR error mappings live exclusively in `app/api/error_codes.py`. New stable codes also need entries in `tests/unit/architecture/test_error_code_coverage.py` `handler_level_allowlist` (or are entity-level constants the arch test discovers automatically).
- Plan 08 lessons folded in: pre-flight verify VO factory signatures (`TimeWindow.create(time, time)`, `WeeklySchedule.create(...)` wrapper for `Resource.create`); `IResourceRepository.get_by_id` returns `Resource | None` directly (not `Result`). Apply these adaptations when writing tests/handlers.
- Mutation handlers that compare against `now()` take a `clock: Callable[[], datetime] = _utcnow` constructor arg so tests can pin time (Plan 08 polish pattern).

---

## File structure (created or modified over the plan)

```
app/domain/ratings/
├── __init__.py                          NEW (empty)
├── aggregate.py                         NEW — RatingAggregate value type
├── rating.py                            NEW — Rating aggregate
└── repository.py                        NEW — IRatingRepository Protocol

app/use_cases/ratings/
├── __init__.py                          NEW (empty)
├── dtos.py                              NEW — RatingDto / RatingListDto / PublicRatingDto / PublicRatingListDto
├── commands/
│   ├── __init__.py                      NEW
│   ├── create_rating.py                 NEW
│   └── update_rating.py                 NEW
└── queries/
    ├── __init__.py                      NEW
    ├── list_my_ratings.py               NEW
    └── list_public_ratings.py           NEW

app/use_cases/resources/dtos.py          MODIFIED — adds rating_avg + rating_count to ResourceDto
app/use_cases/resources/queries/         MODIFIED — 5 handlers gain IRatingRepository dep
app/use_cases/accounts/queries/get_owner_public_page.py  MODIFIED — owner_rating_avg + owner_rating_count

app/infrastructure/db/mappings/rating.py NEW — RatingModel
app/infrastructure/repositories/rating_repository.py  NEW — SQLAlchemyRatingRepository

app/api/v1/me_ratings/
├── __init__.py                          NEW (empty)
├── deps.py                              NEW
├── routes.py                            NEW
└── schemas.py                           NEW

app/api/v1/public_resources/routes.py    MODIFIED — adds public ratings list route + wires aggregates into resource detail/listing/owner page
app/api/v1/me_resources/routes.py        MODIFIED — wires aggregates into owner resource list/detail
app/api/v1/me_resources/schemas.py       MODIFIED — adds rating_avg + rating_count to ResourceResponse
app/api/v1/public_resources/deps.py      MODIFIED — DI for ratings repo into resource handlers
app/api/v1/me_resources/deps.py          MODIFIED — DI for ratings repo into resource handlers
app/api/v1/router.py                     MODIFIED — includes me_ratings_router
app/api/error_codes.py                   MODIFIED — registers Plan 09 codes
app/migrations/env.py                    MODIFIED — registers RatingModel
app/migrations/versions/<ts>_ratings_table.py    NEW

tests/unit/domain/ratings/
├── __init__.py                          NEW
├── test_rating_aggregate.py             NEW
└── test_rating.py                       NEW

tests/unit/use_cases/ratings/
├── __init__.py                          NEW
├── fakes/
│   ├── __init__.py                      NEW
│   └── in_memory_rating_repository.py   NEW
├── commands/                            NEW (2 test files)
└── queries/                             NEW (2 test files)

tests/integration/ratings/
├── __init__.py                          NEW
└── test_rating_repository.py            NEW

tests/integration/conftest.py            MODIFIED — registers rating mapping import
tests/unit/architecture/test_error_code_coverage.py    MODIFIED — extends allowlist

tests/e2e/ratings/
├── __init__.py                          NEW
└── test_ratings_happy_path.py           NEW

docs/superpowers/specs/2026-04-25-venue-backend-design.md   MODIFIED — refreshes §3 #20 (drop), §4.2, §5.7, §7.1, §7.4, §7.5, §8
```

---

## Task 1: `Rating` aggregate + `RatingAggregate` value type

**Files:**
- Create: `app/domain/ratings/__init__.py` (empty)
- Create: `app/domain/ratings/aggregate.py`
- Create: `app/domain/ratings/rating.py`
- Create: `tests/unit/domain/ratings/__init__.py` (empty)
- Create: `tests/unit/domain/ratings/test_rating_aggregate.py`
- Create: `tests/unit/domain/ratings/test_rating.py`

- [ ] **Step 1: Write failing tests for `RatingAggregate`**

`tests/unit/domain/ratings/test_rating_aggregate.py`:

```python
from __future__ import annotations
from decimal import Decimal

from app.domain.ratings.aggregate import RatingAggregate


def test_zero_count_aggregate():
    agg = RatingAggregate(avg_score=None, count=0)
    assert agg.avg_score is None
    assert agg.count == 0


def test_with_ratings():
    agg = RatingAggregate(avg_score=Decimal("4.3"), count=10)
    assert agg.avg_score == Decimal("4.3")
    assert agg.count == 10


def test_is_frozen():
    import dataclasses
    agg = RatingAggregate(avg_score=Decimal("4.0"), count=2)
    with __import__("pytest").raises(dataclasses.FrozenInstanceError):
        agg.count = 3  # type: ignore[misc]
```

- [ ] **Step 2: Write failing tests for `Rating`**

`tests/unit/domain/ratings/test_rating.py`:

```python
from __future__ import annotations
from datetime import datetime, timezone
from uuid import uuid4

from app.domain.ratings.rating import Rating
from app.domain.shared.value_objects.rating_score import RatingScore
from app.domain.shared.value_objects.short_description import ShortDescription


def _now() -> datetime:
    return datetime(2026, 4, 28, 12, 0, 0, tzinfo=timezone.utc)


def _score(v: int = 5) -> RatingScore:
    return RatingScore.create(v).value


def test_create_sets_initial_state():
    bid, rid, cid = uuid4(), uuid4(), uuid4()
    r = Rating.create(
        booking_id=bid, resource_id=rid, customer_id=cid,
        score=_score(5), comment=None, now=_now(),
    )
    assert r.booking_id == bid
    assert r.resource_id == rid
    assert r.customer_id == cid
    assert r.score.value == 5
    assert r.comment is None
    assert r.created_at == _now()
    assert r.updated_at == _now()


def test_create_with_comment():
    note = ShortDescription.create("Excelente").value
    r = Rating.create(
        booking_id=uuid4(), resource_id=uuid4(), customer_id=uuid4(),
        score=_score(4), comment=note, now=_now(),
    )
    assert r.comment is note


def test_create_generates_unique_ids():
    a = Rating.create(
        booking_id=uuid4(), resource_id=uuid4(), customer_id=uuid4(),
        score=_score(), comment=None, now=_now(),
    )
    b = Rating.create(
        booking_id=uuid4(), resource_id=uuid4(), customer_id=uuid4(),
        score=_score(), comment=None, now=_now(),
    )
    assert a.id != b.id


def test_update_text_changes_score_and_comment():
    note_old = ShortDescription.create("primeiro").value
    note_new = ShortDescription.create("segundo").value
    r = Rating.create(
        booking_id=uuid4(), resource_id=uuid4(), customer_id=uuid4(),
        score=_score(3), comment=note_old, now=_now(),
    )
    r.update_text(score=_score(5), comment=note_new, now=_now())
    assert r.score.value == 5
    assert r.comment is note_new


def test_update_text_can_clear_comment():
    note = ShortDescription.create("será apagado").value
    r = Rating.create(
        booking_id=uuid4(), resource_id=uuid4(), customer_id=uuid4(),
        score=_score(4), comment=note, now=_now(),
    )
    r.update_text(score=_score(4), comment=None, now=_now())
    assert r.comment is None


def test_update_text_bumps_updated_at():
    from datetime import timedelta
    r = Rating.create(
        booking_id=uuid4(), resource_id=uuid4(), customer_id=uuid4(),
        score=_score(5), comment=None, now=_now(),
    )
    later = _now() + timedelta(days=1)
    r.update_text(score=_score(4), comment=None, now=later)
    assert r.updated_at == later
    assert r.created_at == _now()
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/unit/domain/ratings/ -v`
Expected: import errors (`cannot import name 'RatingAggregate'`, `cannot import name 'Rating'`).

- [ ] **Step 4: Create `app/domain/ratings/__init__.py`** (empty file).

- [ ] **Step 5: Create `app/domain/ratings/aggregate.py`**

```python
from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class RatingAggregate:
    """Read-side projection: average score (rounded to one decimal) + count.

    `avg_score` is `None` exactly when `count == 0`. Used by every endpoint
    that returns a Resource (or owner page) to surface aggregate ratings
    without storing denormalized fields on the Resource aggregate.
    """

    avg_score: Decimal | None
    count: int
```

- [ ] **Step 6: Create `app/domain/ratings/rating.py`**

```python
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4

from app.domain.shared.entity import BaseEntity
from app.domain.shared.value_objects.rating_score import RatingScore
from app.domain.shared.value_objects.short_description import ShortDescription


@dataclass(slots=True, kw_only=True)
class Rating(BaseEntity):
    booking_id: UUID
    resource_id: UUID
    customer_id: UUID
    score: RatingScore
    comment: ShortDescription | None = None

    @classmethod
    def create(
        cls,
        *,
        booking_id: UUID,
        resource_id: UUID,
        customer_id: UUID,
        score: RatingScore,
        comment: ShortDescription | None,
        now: datetime,
    ) -> "Rating":
        """Factory. All eligibility validation lives in CreateRatingHandler
        (it requires Booking context). Sets created_at == updated_at == now.
        """
        return cls(
            id=uuid4(),
            booking_id=booking_id,
            resource_id=resource_id,
            customer_id=customer_id,
            score=score,
            comment=comment,
            created_at=now,
            updated_at=now,
        )

    def update_text(
        self,
        *,
        score: RatingScore,
        comment: ShortDescription | None,
        now: datetime,
    ) -> None:
        """Replace score (required) and comment (optional). Bumps updated_at.
        7-day window check lives in UpdateRatingHandler — this aggregate has
        no failure mode at the entity level."""
        self.score = score
        self.comment = comment
        self.updated_at = now
```

- [ ] **Step 7: Run tests**

Run: `.venv/bin/pytest tests/unit/domain/ratings/ -v`
Expected: 9 PASSED (3 aggregate + 6 rating).

- [ ] **Step 8: Run full unit suite**

Run: `.venv/bin/pytest tests/unit/ -q`
Expected: green (no regression).

- [ ] **Step 9: Commit**

```bash
git add app/domain/ratings/__init__.py app/domain/ratings/aggregate.py app/domain/ratings/rating.py \
        tests/unit/domain/ratings/__init__.py \
        tests/unit/domain/ratings/test_rating_aggregate.py \
        tests/unit/domain/ratings/test_rating.py
git commit -m "$(cat <<'EOF'
feat(ratings): Rating aggregate + RatingAggregate value type

Plan 09 task 1. Rating is a BaseEntity-backed aggregate with three
denormalized FK fields (booking_id, resource_id, customer_id),
RatingScore VO score, optional ShortDescription comment, and a
single update_text mutator. RatingAggregate is the frozen-dataclass
read-side projection (avg_score: Decimal | None, count: int) used
by resource listings.

No state machine, no moderation, no failure-mode mutator —
entity-layer simplicity reflects the spec's deliberate scope cuts.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: `IRatingRepository` Protocol

**Files:**
- Create: `app/domain/ratings/repository.py`

No production tests (Protocols are structural). Smoke import only.

- [ ] **Step 1: Create `app/domain/ratings/repository.py`**

```python
from __future__ import annotations
from typing import Protocol
from uuid import UUID

from app.domain.ratings.aggregate import RatingAggregate
from app.domain.ratings.rating import Rating
from app.domain.shared.result import Result


class IRatingRepository(Protocol):
    """Persistence port for the ratings feature."""

    async def add(self, rating: Rating) -> Result[None]:
        """Inserts a new rating. Translates UNIQUE(booking_id) violations
        from the database into Result.failure('RatingAlreadyExists', 409)."""
        ...

    async def update(self, rating: Rating) -> Result[None]:
        """Persists score/comment/updated_at changes. Returns
        Result.failure('RatingNotFound', 404) if the id is absent."""
        ...

    async def get_by_id(self, rating_id: UUID) -> Result[Rating | None]:
        ...

    async def get_by_booking_id(self, booking_id: UUID) -> Result[Rating | None]:
        """Used by CreateRatingHandler for the existence/dedup check before
        attempting an insert that could collide with the UNIQUE constraint."""
        ...

    async def list_by_customer(
        self,
        customer_id: UUID,
        *,
        page: int,
        page_size: int,
    ) -> Result[list[Rating]]:
        """Customer's own ratings, newest first."""
        ...

    async def list_with_comment_for_resource(
        self,
        resource_id: UUID,
        *,
        page: int,
        page_size: int,
    ) -> Result[list[Rating]]:
        """Public listing — only ratings whose comment is non-NULL,
        newest first."""
        ...

    async def get_aggregates_for_resources(
        self,
        resource_ids: list[UUID],
    ) -> Result[dict[UUID, RatingAggregate]]:
        """Batch aggregate. For each resource_id provided, returns the
        (avg_score, count) pair. Resources with zero ratings are present
        in the dict with RatingAggregate(None, 0). Used by every resource
        listing/detail endpoint to avoid N+1."""
        ...
```

- [ ] **Step 2: Smoke import**

Run: `.venv/bin/python -c "from app.domain.ratings.repository import IRatingRepository; print('ok')"`
Expected: `ok`.

- [ ] **Step 3: Run unit suite**

Run: `.venv/bin/pytest tests/unit/ -q`
Expected: green.

- [ ] **Step 4: Commit**

```bash
git add app/domain/ratings/repository.py
git commit -m "$(cat <<'EOF'
feat(ratings): IRatingRepository Protocol

Plan 09 task 2. Seven methods: add, update, get_by_id,
get_by_booking_id, list_by_customer, list_with_comment_for_resource,
get_aggregates_for_resources. Aggregate method is batch-by-design
(takes a list, returns a full-coverage dict) so resource listing
handlers avoid N+1.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: `RatingModel` SQLAlchemy mapping

**Files:**
- Create: `app/infrastructure/db/mappings/rating.py`
- Modify: `app/migrations/env.py`
- Modify: `tests/integration/conftest.py`

- [ ] **Step 1: Create the mapping file**

`app/infrastructure/db/mappings/rating.py`:

```python
from __future__ import annotations
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Index, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import CHAR, Integer

from app.infrastructure.db.base import Base, TimestampMixin


class RatingModel(Base, TimestampMixin):
    __tablename__ = "ratings"
    __table_args__ = (
        CheckConstraint(
            "score BETWEEN 1 AND 5", name="ck_ratings_score_range",
        ),
        Index("idx_ratings_resource", "resource_id"),
        Index(
            "idx_ratings_customer_created",
            "customer_id", "created_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(CHAR(36), primary_key=True)
    booking_id: Mapped[UUID] = mapped_column(
        CHAR(36),
        ForeignKey("bookings.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    )
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
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
```

- [ ] **Step 2: Wire into Alembic env**

Edit `app/migrations/env.py`. Find the existing block of mapping imports (Plan 06/07/08 have all wired theirs in). Add a `rating` import alphabetically (between `owner_subscription` and `resource`, or wherever it sorts):

```python
from app.infrastructure.db.mappings import rating  # noqa: F401
```

- [ ] **Step 3: Wire into integration conftest**

Edit `tests/integration/conftest.py`. Find the tuple import that includes Plan 06/07/08 mappings (`booking, notification, owner_subscription, resource, resource_type, user`) and add `rating` alphabetically:

```python
from app.infrastructure.db.mappings import (  # noqa: F401
    booking, notification, owner_subscription, rating, resource, resource_type, user,
)
```

If the conftest's import shape differs, adapt while preserving the alphabetical convention.

- [ ] **Step 4: Smoke-test the mapping**

Run:
```
.venv/bin/python -c "
from app.infrastructure.db.mappings.rating import RatingModel
print(RatingModel.__tablename__)
print(sorted(c.name for c in RatingModel.__table__.columns))
print(sorted(i.name for i in RatingModel.__table__.indexes))
print(sorted(c.name for c in RatingModel.__table__.constraints if c.name))
"
```

Expected output:

```
ratings
['booking_id', 'comment', 'created_at', 'customer_id', 'id', 'resource_id', 'score', 'updated_at']
['idx_ratings_customer_created', 'idx_ratings_resource']
['ck_ratings_score_range', 'pk_ratings', ...]  # exact constraint set varies; ck_ratings_score_range MUST be present
```

- [ ] **Step 5: Run unit + integration suites**

Run: `.venv/bin/pytest tests/unit/ tests/integration/ -q`
Expected: green.

- [ ] **Step 6: Commit**

```bash
git add app/infrastructure/db/mappings/rating.py app/migrations/env.py tests/integration/conftest.py
git commit -m "$(cat <<'EOF'
feat(ratings): RatingModel mapping

Plan 09 task 3. Declarative model with three FKs (bookings.id UNIQUE,
resources.id, users.id) all ON DELETE RESTRICT. CHECK constraint
on score range (1..5) as belt-and-suspenders to the domain VO.
Two b-tree indexes: (resource_id) for the aggregate query +
list-with-comment-for-resource, (customer_id, created_at) for
the my-ratings paginated list. No Postgres-specific extensions.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Alembic migration for `ratings` table

**Files:**
- Create: `app/migrations/versions/<auto-timestamp>_ratings_table.py`

- [ ] **Step 1: Generate the migration**

Run: `make migrate-new msg="ratings_table"`

If `make migrate-new` fails (no Postgres locally), author the file by hand following Plan 07/08 precedent. Find the latest existing revision via `ls app/migrations/versions/ | sort | tail -1` and read its `revision` string — that becomes the new file's `down_revision`. Match the existing filename convention (`YYYYMMDD_HHMM_<name>.py`).

- [ ] **Step 2: Replace the migration body with the schema below**

```python
"""ratings table

Revision ID: <keep autogen value>
Revises: <set to latest existing revision — likely c7d4e8f92a1b from Plan 08>
Create Date: 2026-04-28 ...

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '<autogen>'
down_revision: Union[str, None] = 'c7d4e8f92a1b'  # bookings table; verify
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'ratings',
        sa.Column('id', sa.CHAR(length=36), nullable=False),
        sa.Column('booking_id', sa.CHAR(length=36), nullable=False),
        sa.Column('resource_id', sa.CHAR(length=36), nullable=False),
        sa.Column('customer_id', sa.CHAR(length=36), nullable=False),
        sa.Column('score', sa.Integer(), nullable=False),
        sa.Column('comment', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['booking_id'], ['bookings.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['resource_id'], ['resources.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['customer_id'], ['users.id'], ondelete='RESTRICT'),
        sa.UniqueConstraint('booking_id', name='uq_ratings_booking'),
        sa.CheckConstraint('score BETWEEN 1 AND 5', name='ck_ratings_score_range'),
    )
    op.create_index(
        'idx_ratings_resource', 'ratings', ['resource_id'], unique=False,
    )
    op.create_index(
        'idx_ratings_customer_created', 'ratings',
        ['customer_id', 'created_at'], unique=False,
    )


def downgrade() -> None:
    op.drop_index('idx_ratings_customer_created', table_name='ratings')
    op.drop_index('idx_ratings_resource', table_name='ratings')
    op.drop_table('ratings')
```

- [ ] **Step 3: Run migrations against the dev DB if Postgres is available**

Run: `make migrate-up`
Expected: applies cleanly. If Postgres isn't running locally, skip this step — integration tests on SQLite will validate the schema via `Base.metadata.create_all`.

- [ ] **Step 4: Run unit + integration suites**

Run: `.venv/bin/pytest tests/unit/ tests/integration/ -q`
Expected: green.

- [ ] **Step 5: Commit**

```bash
git add app/migrations/versions/
git commit -m "$(cat <<'EOF'
feat(ratings): alembic migration for ratings table

Plan 09 task 4. Creates table + UNIQUE on booking_id + CHECK on
score range (1..5) + 2 b-tree indexes. Down_revision chains from
the Plan 08 bookings table. No Postgres-specific extensions —
schema is portable to SQLite for tests.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: `SQLAlchemyRatingRepository` (full impl + integration tests)

**Files:**
- Create: `app/infrastructure/repositories/rating_repository.py`
- Create: `tests/integration/ratings/__init__.py` (empty)
- Create: `tests/integration/ratings/test_rating_repository.py`

- [ ] **Step 1: Write failing integration tests**

`tests/integration/ratings/test_rating_repository.py`:

```python
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from app.domain.ratings.rating import Rating
from app.domain.shared.value_objects.rating_score import RatingScore
from app.domain.shared.value_objects.short_description import ShortDescription
from app.infrastructure.db.mappings.user import UserModel
from app.infrastructure.db.mappings.resource import ResourceModel
from app.infrastructure.db.mappings.resource_type import ResourceTypeModel
from app.infrastructure.db.mappings.booking import BookingModel
from app.infrastructure.repositories.rating_repository import (
    SQLAlchemyRatingRepository,
)


pytestmark = pytest.mark.asyncio


def _now() -> datetime:
    return datetime(2026, 4, 28, 12, 0, 0, tzinfo=timezone.utc)


def _score(v: int = 5) -> RatingScore:
    return RatingScore.create(v).value


async def _seed_booking_for_rating(db_session) -> tuple[UUID, UUID, UUID]:
    """Insert a user, resource_type, resource, and APPROVED booking so
    a rating can be inserted with valid FKs. Returns (booking_id,
    resource_id, customer_id)."""
    rt = ResourceTypeModel(
        id=str(uuid4()), slug="football-field", name="Football Field",
        description="", attribute_schema=[], is_active=True,
        created_at=_now(), updated_at=_now(),
    )
    owner = UserModel(
        id=str(uuid4()), email="o@example.com", full_name="Owner",
        password_hash="x", role="owner", is_active=True,
        public_slug="owner", phone_number=None,
        created_at=_now(), updated_at=_now(),
    )
    customer = UserModel(
        id=str(uuid4()), email="c@example.com", full_name="Customer",
        password_hash="x", role="customer", is_active=True,
        public_slug=None, phone_number=None,
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
    booking = BookingModel(
        id=str(uuid4()), resource_id=res.id, customer_id=customer.id,
        slot_start_at=_now() - timedelta(days=1, hours=1),
        slot_end_at=_now() - timedelta(days=1),
        status="APPROVED",
        customer_note=None, total_price_cents=8000,
        status_history=[],
        created_at=_now() - timedelta(days=2), updated_at=_now() - timedelta(days=2),
    )
    db_session.add_all([rt, owner, customer, res, booking])
    await db_session.flush()
    return UUID(booking.id), UUID(res.id), UUID(customer.id)


async def test_add_and_get_round_trip(db_session):
    booking_id, resource_id, customer_id = await _seed_booking_for_rating(db_session)
    repo = SQLAlchemyRatingRepository(db_session)
    note = ShortDescription.create("ótimo lugar").value
    rating = Rating.create(
        booking_id=booking_id, resource_id=resource_id, customer_id=customer_id,
        score=_score(5), comment=note, now=_now(),
    )
    add_r = await repo.add(rating)
    assert add_r.is_success

    fetched = (await repo.get_by_id(rating.id)).value
    assert fetched is not None
    assert fetched.id == rating.id
    assert fetched.score.value == 5
    assert fetched.comment is not None
    assert fetched.comment.value == "ótimo lugar"

    by_booking = (await repo.get_by_booking_id(booking_id)).value
    assert by_booking is not None
    assert by_booking.id == rating.id


async def test_unique_booking_id_rejected(db_session):
    booking_id, resource_id, customer_id = await _seed_booking_for_rating(db_session)
    repo = SQLAlchemyRatingRepository(db_session)
    a = Rating.create(
        booking_id=booking_id, resource_id=resource_id, customer_id=customer_id,
        score=_score(5), comment=None, now=_now(),
    )
    b = Rating.create(
        booking_id=booking_id, resource_id=resource_id, customer_id=customer_id,
        score=_score(3), comment=None, now=_now(),
    )
    await repo.add(a)
    second = await repo.add(b)
    assert second.is_failure
    assert second.error == "RatingAlreadyExists"
    assert second.status_code == 409


async def test_list_with_comment_excludes_null_comments(db_session):
    booking_id, resource_id, customer_id = await _seed_booking_for_rating(db_session)
    repo = SQLAlchemyRatingRepository(db_session)
    # Same booking can only host one rating; create two by inserting a
    # second booking row through the same fixture? Simplest: skip that and
    # just validate the filter on a single-row case where comment is null.
    no_comment = Rating.create(
        booking_id=booking_id, resource_id=resource_id, customer_id=customer_id,
        score=_score(5), comment=None, now=_now(),
    )
    await repo.add(no_comment)

    items = (await repo.list_with_comment_for_resource(
        resource_id, page=1, page_size=10,
    )).value
    assert items == []


async def test_list_by_customer_orders_desc(db_session):
    """Insert two ratings for the same customer across different bookings;
    verify newest-first ordering."""
    # Need two bookings → seed twice via inline construction.
    rt = ResourceTypeModel(
        id=str(uuid4()), slug="court", name="Court",
        description="", attribute_schema=[], is_active=True,
        created_at=_now(), updated_at=_now(),
    )
    owner = UserModel(
        id=str(uuid4()), email="o2@example.com", full_name="Owner2",
        password_hash="x", role="owner", is_active=True,
        public_slug="owner2", phone_number=None,
        created_at=_now(), updated_at=_now(),
    )
    customer = UserModel(
        id=str(uuid4()), email="c2@example.com", full_name="Customer2",
        password_hash="x", role="customer", is_active=True,
        public_slug=None, phone_number=None,
        created_at=_now(), updated_at=_now(),
    )
    res = ResourceModel(
        id=str(uuid4()), owner_id=owner.id, resource_type_id=rt.id,
        slug="court-1", name="Court 1", description="",
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
    customer_id = UUID(customer.id)
    resource_id = UUID(res.id)

    # Two distinct bookings + two distinct ratings.
    bookings_pairs = []
    for i in range(2):
        b = BookingModel(
            id=str(uuid4()), resource_id=res.id, customer_id=customer.id,
            slot_start_at=_now() - timedelta(days=2 * (i + 1), hours=1),
            slot_end_at=_now() - timedelta(days=2 * (i + 1)),
            status="APPROVED",
            customer_note=None, total_price_cents=8000,
            status_history=[],
            created_at=_now() - timedelta(days=2 * (i + 1) + 1),
            updated_at=_now() - timedelta(days=2 * (i + 1) + 1),
        )
        db_session.add(b)
        bookings_pairs.append((UUID(b.id), b))
    await db_session.flush()

    repo = SQLAlchemyRatingRepository(db_session)
    older = Rating.create(
        booking_id=bookings_pairs[0][0],
        resource_id=resource_id, customer_id=customer_id,
        score=_score(4), comment=None,
        now=_now() - timedelta(days=3),
    )
    newer = Rating.create(
        booking_id=bookings_pairs[1][0],
        resource_id=resource_id, customer_id=customer_id,
        score=_score(5), comment=None, now=_now(),
    )
    await repo.add(older)
    await repo.add(newer)

    items = (await repo.list_by_customer(
        customer_id, page=1, page_size=10,
    )).value
    assert [r.id for r in items] == [newer.id, older.id]


async def test_get_aggregates_for_resources_full_coverage(db_session):
    booking_id, resource_id, customer_id = await _seed_booking_for_rating(db_session)
    repo = SQLAlchemyRatingRepository(db_session)
    rating = Rating.create(
        booking_id=booking_id, resource_id=resource_id, customer_id=customer_id,
        score=_score(4), comment=None, now=_now(),
    )
    await repo.add(rating)

    other_resource_id = uuid4()  # never seeded; should appear with (None, 0)
    aggs = (await repo.get_aggregates_for_resources(
        [resource_id, other_resource_id],
    )).value
    assert resource_id in aggs
    assert other_resource_id in aggs
    assert aggs[resource_id].count == 1
    assert aggs[resource_id].avg_score == Decimal("4.0")
    assert aggs[other_resource_id].count == 0
    assert aggs[other_resource_id].avg_score is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/integration/ratings/ -v`
Expected: import error — `cannot import name 'SQLAlchemyRatingRepository'`.

- [ ] **Step 3: Create `app/infrastructure/repositories/rating_repository.py`**

```python
from __future__ import annotations
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.ratings.aggregate import RatingAggregate
from app.domain.ratings.rating import Rating
from app.domain.ratings.repository import IRatingRepository
from app.domain.shared.result import Result
from app.domain.shared.value_objects.rating_score import RatingScore
from app.domain.shared.value_objects.short_description import ShortDescription
from app.infrastructure.db.mappings.rating import RatingModel


def _ensure_utc(dt: datetime | None) -> datetime | None:
    """SQLite drops tzinfo on roundtrip; assume stored values are UTC."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _to_model_kwargs(r: Rating) -> dict:
    return {
        "id": str(r.id),
        "booking_id": str(r.booking_id),
        "resource_id": str(r.resource_id),
        "customer_id": str(r.customer_id),
        "score": r.score.value,
        "comment": r.comment.value if r.comment is not None else None,
        "created_at": r.created_at,
        "updated_at": r.updated_at,
    }


def _to_entity(m: RatingModel) -> Rating:
    return Rating(
        id=UUID(str(m.id)),
        booking_id=UUID(str(m.booking_id)),
        resource_id=UUID(str(m.resource_id)),
        customer_id=UUID(str(m.customer_id)),
        score=RatingScore.create(m.score).value,
        comment=(
            ShortDescription.create(m.comment).value
            if m.comment is not None else None
        ),
        created_at=_ensure_utc(m.created_at),
        updated_at=_ensure_utc(m.updated_at),
    )


class SQLAlchemyRatingRepository(IRatingRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, rating: Rating) -> Result[None]:
        self._session.add(RatingModel(**_to_model_kwargs(rating)))
        try:
            await self._session.flush()
        except IntegrityError:
            await self._session.rollback()
            return Result.failure("RatingAlreadyExists", status_code=409)
        return Result.success(None)

    async def update(self, rating: Rating) -> Result[None]:
        stmt = select(RatingModel).where(RatingModel.id == str(rating.id))
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        if row is None:
            return Result.failure("RatingNotFound", status_code=404)
        kwargs = _to_model_kwargs(rating)
        for k, v in kwargs.items():
            if k == "id":
                continue
            setattr(row, k, v)
        await self._session.flush()
        return Result.success(None)

    async def get_by_id(self, rating_id: UUID) -> Result[Rating | None]:
        stmt = select(RatingModel).where(RatingModel.id == str(rating_id))
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return Result.success(_to_entity(row) if row else None)

    async def get_by_booking_id(
        self, booking_id: UUID,
    ) -> Result[Rating | None]:
        stmt = select(RatingModel).where(
            RatingModel.booking_id == str(booking_id),
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return Result.success(_to_entity(row) if row else None)

    async def list_by_customer(
        self,
        customer_id: UUID,
        *,
        page: int,
        page_size: int,
    ) -> Result[list[Rating]]:
        stmt = (
            select(RatingModel)
            .where(RatingModel.customer_id == str(customer_id))
            .order_by(RatingModel.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return Result.success([_to_entity(r) for r in rows])

    async def list_with_comment_for_resource(
        self,
        resource_id: UUID,
        *,
        page: int,
        page_size: int,
    ) -> Result[list[Rating]]:
        stmt = (
            select(RatingModel)
            .where(
                RatingModel.resource_id == str(resource_id),
                RatingModel.comment.isnot(None),
            )
            .order_by(RatingModel.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return Result.success([_to_entity(r) for r in rows])

    async def get_aggregates_for_resources(
        self,
        resource_ids: list[UUID],
    ) -> Result[dict[UUID, RatingAggregate]]:
        out: dict[UUID, RatingAggregate] = {
            rid: RatingAggregate(avg_score=None, count=0)
            for rid in resource_ids
        }
        if not resource_ids:
            return Result.success(out)

        str_ids = [str(rid) for rid in resource_ids]
        stmt = (
            select(
                RatingModel.resource_id,
                func.avg(RatingModel.score).label("avg"),
                func.count(RatingModel.id).label("count"),
            )
            .where(RatingModel.resource_id.in_(str_ids))
            .group_by(RatingModel.resource_id)
        )
        rows = (await self._session.execute(stmt)).all()
        for r in rows:
            avg_value: Decimal | None = (
                Decimal(str(r.avg)).quantize(Decimal("0.1"))
                if r.avg is not None else None
            )
            count_value = int(r.count) if r.count is not None else 0
            out[UUID(str(r.resource_id))] = RatingAggregate(
                avg_score=avg_value, count=count_value,
            )
        return Result.success(out)
```

- [ ] **Step 4: Run integration tests**

Run: `.venv/bin/pytest tests/integration/ratings/ -v`
Expected: 5 PASSED.

- [ ] **Step 5: Run full unit + integration**

Run: `.venv/bin/pytest tests/unit/ tests/integration/ -q`
Expected: green.

- [ ] **Step 6: Commit**

```bash
git add app/infrastructure/repositories/rating_repository.py tests/integration/ratings/
git commit -m "$(cat <<'EOF'
feat(ratings): SQLAlchemyRatingRepository

Plan 09 task 5. Implements all 7 methods of IRatingRepository over
AsyncSession. add() catches the UNIQUE(booking_id) IntegrityError
and translates to Result.failure('RatingAlreadyExists', 409) — this
is the sole race protection for concurrent rating submissions.
get_aggregates_for_resources returns a full-coverage dict (input
ids without ratings present with RatingAggregate(None, 0)) so
listing handlers can merge without zip/lookup ceremony.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Use case DTOs

**Files:**
- Create: `app/use_cases/ratings/__init__.py` (empty)
- Create: `app/use_cases/ratings/dtos.py`

- [ ] **Step 1: Create the package init** (empty file).

- [ ] **Step 2: Create `app/use_cases/ratings/dtos.py`**

```python
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.domain.ratings.rating import Rating


@dataclass(frozen=True, kw_only=True, slots=True)
class RatingDto:
    """Customer-facing rating shape (includes own customer_id, comment if any)."""
    id: UUID
    booking_id: UUID
    resource_id: UUID
    customer_id: UUID
    score: int
    comment: str | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_entity(cls, r: Rating) -> "RatingDto":
        return cls(
            id=r.id,
            booking_id=r.booking_id,
            resource_id=r.resource_id,
            customer_id=r.customer_id,
            score=r.score.value,
            comment=r.comment.value if r.comment is not None else None,
            created_at=r.created_at,
            updated_at=r.updated_at,
        )


@dataclass(frozen=True, kw_only=True, slots=True)
class RatingListDto:
    items: tuple[RatingDto, ...]
    page: int
    page_size: int


@dataclass(frozen=True, kw_only=True, slots=True)
class PublicRatingDto:
    """Privacy-filtered: omits customer_id and booking_id. Only used by the
    public ratings list, where comment is non-NULL by query construction."""
    score: int
    comment: str
    created_at: datetime

    @classmethod
    def from_entity(cls, r: Rating) -> "PublicRatingDto":
        # Caller has already filtered to comment-bearing ratings; if a
        # caller passes a comment-less rating the empty string is intentional
        # (still filterable downstream, but should not occur in practice).
        return cls(
            score=r.score.value,
            comment=r.comment.value if r.comment is not None else "",
            created_at=r.created_at,
        )


@dataclass(frozen=True, kw_only=True, slots=True)
class PublicRatingListDto:
    items: tuple[PublicRatingDto, ...]
    page: int
    page_size: int
```

- [ ] **Step 3: Smoke import**

Run: `.venv/bin/python -c "from app.use_cases.ratings.dtos import RatingDto, RatingListDto, PublicRatingDto, PublicRatingListDto; print('ok')"`
Expected: `ok`.

- [ ] **Step 4: Commit**

```bash
git add app/use_cases/ratings/__init__.py app/use_cases/ratings/dtos.py
git commit -m "$(cat <<'EOF'
feat(ratings): use case DTOs

Plan 09 task 6. RatingDto for customer-facing reads (full shape).
PublicRatingDto strips customer_id and booking_id for the public
list per spec §3.7 privacy filter. Both wrapped by *ListDto for
paginated responses.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: Test fake — `InMemoryRatingRepository`

**Files:**
- Create: `tests/unit/use_cases/ratings/__init__.py` (empty)
- Create: `tests/unit/use_cases/ratings/fakes/__init__.py` (empty)
- Create: `tests/unit/use_cases/ratings/fakes/in_memory_rating_repository.py`

Test-only support file. Exercised implicitly by handler tests in Tasks 8-10.

- [ ] **Step 1: Create the in-memory repository fake**

`tests/unit/use_cases/ratings/fakes/in_memory_rating_repository.py`:

```python
from __future__ import annotations
from collections import defaultdict
from decimal import Decimal
from uuid import UUID

from app.domain.ratings.aggregate import RatingAggregate
from app.domain.ratings.rating import Rating
from app.domain.ratings.repository import IRatingRepository
from app.domain.shared.result import Result


class InMemoryRatingRepository(IRatingRepository):
    def __init__(self) -> None:
        self._rows: list[Rating] = []

    async def add(self, rating: Rating) -> Result[None]:
        if any(r.booking_id == rating.booking_id for r in self._rows):
            return Result.failure("RatingAlreadyExists", status_code=409)
        self._rows.append(rating)
        return Result.success(None)

    async def update(self, rating: Rating) -> Result[None]:
        for i, existing in enumerate(self._rows):
            if existing.id == rating.id:
                self._rows[i] = rating
                return Result.success(None)
        return Result.failure("RatingNotFound", status_code=404)

    async def get_by_id(self, rating_id: UUID) -> Result[Rating | None]:
        for r in self._rows:
            if r.id == rating_id:
                return Result.success(r)
        return Result.success(None)

    async def get_by_booking_id(
        self, booking_id: UUID,
    ) -> Result[Rating | None]:
        for r in self._rows:
            if r.booking_id == booking_id:
                return Result.success(r)
        return Result.success(None)

    async def list_by_customer(
        self,
        customer_id: UUID,
        *,
        page: int,
        page_size: int,
    ) -> Result[list[Rating]]:
        filtered = [r for r in self._rows if r.customer_id == customer_id]
        filtered.sort(key=lambda r: r.created_at, reverse=True)
        offset = (page - 1) * page_size
        return Result.success(filtered[offset:offset + page_size])

    async def list_with_comment_for_resource(
        self,
        resource_id: UUID,
        *,
        page: int,
        page_size: int,
    ) -> Result[list[Rating]]:
        filtered = [
            r for r in self._rows
            if r.resource_id == resource_id and r.comment is not None
        ]
        filtered.sort(key=lambda r: r.created_at, reverse=True)
        offset = (page - 1) * page_size
        return Result.success(filtered[offset:offset + page_size])

    async def get_aggregates_for_resources(
        self,
        resource_ids: list[UUID],
    ) -> Result[dict[UUID, RatingAggregate]]:
        out: dict[UUID, RatingAggregate] = {
            rid: RatingAggregate(avg_score=None, count=0)
            for rid in resource_ids
        }
        groups: dict[UUID, list[int]] = defaultdict(list)
        for r in self._rows:
            if r.resource_id in out:
                groups[r.resource_id].append(r.score.value)
        for rid, scores in groups.items():
            avg = (Decimal(sum(scores)) / Decimal(len(scores))).quantize(
                Decimal("0.1"),
            )
            out[rid] = RatingAggregate(avg_score=avg, count=len(scores))
        return Result.success(out)
```

- [ ] **Step 2: Smoke import**

Run:
```
.venv/bin/python -c "
from tests.unit.use_cases.ratings.fakes.in_memory_rating_repository import InMemoryRatingRepository
print('ok')
"
```
Expected: `ok`.

- [ ] **Step 3: Run unit suite**

Run: `.venv/bin/pytest tests/unit/ -q`
Expected: green.

- [ ] **Step 4: Commit**

```bash
git add tests/unit/use_cases/ratings/
git commit -m "$(cat <<'EOF'
test(ratings): InMemoryRatingRepository fake

Plan 09 task 7. List-backed repo mirrors all 7 SQL repo methods
(including the duplicate-booking dedup in add() and the
quantize-to-one-decimal in get_aggregates_for_resources). Used by
handler unit tests in Tasks 8-10.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: `CreateRatingHandler`

**Files:**
- Create: `app/use_cases/ratings/commands/__init__.py` (empty)
- Create: `app/use_cases/ratings/commands/create_rating.py`
- Create: `tests/unit/use_cases/ratings/commands/__init__.py` (empty)
- Create: `tests/unit/use_cases/ratings/commands/test_create_rating.py`

- [ ] **Step 1: Write failing tests**

`tests/unit/use_cases/ratings/commands/test_create_rating.py`:

```python
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.domain.bookings.booking import Booking
from app.domain.bookings.booking_status import BookingStatus
from app.domain.shared.value_objects.date_time_range import DateTimeRange
from app.domain.shared.value_objects.money import Money
from app.use_cases.ratings.commands.create_rating import (
    CreateRatingCommand,
    CreateRatingHandler,
)
from tests.unit.use_cases.bookings.fakes.in_memory_booking_repository import (
    InMemoryBookingRepository,
)
from tests.unit.use_cases.ratings.fakes.in_memory_rating_repository import (
    InMemoryRatingRepository,
)


pytestmark = pytest.mark.asyncio


def _now() -> datetime:
    return datetime(2026, 4, 28, 12, 0, 0, tzinfo=timezone.utc)


def _build_approved_ended(*, customer_id, days_ago: int = 1) -> Booking:
    """Build a Booking that's APPROVED and whose slot ended `days_ago` ago."""
    end = _now() - timedelta(days=days_ago)
    start = end - timedelta(hours=1)
    sr = DateTimeRange.create(start_at=start, end_at=end).value
    b = Booking.create_pending(
        resource_id=uuid4(), customer_id=customer_id,
        slot_range=sr, total_price_cents=Money.create(8000).value,
        customer_note=None, now=_now() - timedelta(days=days_ago + 1),
    )
    b.approve(actor_id=uuid4(), now=_now() - timedelta(days=days_ago + 1))
    return b


async def test_happy_path_creates_rating():
    customer_id = uuid4()
    booking = _build_approved_ended(customer_id=customer_id)
    bookings = InMemoryBookingRepository()
    ratings = InMemoryRatingRepository()
    await bookings.add(booking)
    handler = CreateRatingHandler(
        ratings=ratings, bookings=bookings, clock=_now,
    )
    cmd = CreateRatingCommand(
        actor_id=customer_id, booking_id=booking.id,
        score=5, comment="excelente",
    )
    r = await handler.handle(cmd)
    assert r.is_success, r.error
    dto = r.value
    assert dto.score == 5
    assert dto.comment == "excelente"
    assert dto.booking_id == booking.id
    assert dto.customer_id == customer_id


async def test_creates_without_comment():
    customer_id = uuid4()
    booking = _build_approved_ended(customer_id=customer_id)
    bookings = InMemoryBookingRepository()
    ratings = InMemoryRatingRepository()
    await bookings.add(booking)
    handler = CreateRatingHandler(
        ratings=ratings, bookings=bookings, clock=_now,
    )
    r = await handler.handle(CreateRatingCommand(
        actor_id=customer_id, booking_id=booking.id, score=4, comment=None,
    ))
    assert r.is_success
    assert r.value.comment is None


async def test_unknown_booking_returns_404():
    handler = CreateRatingHandler(
        ratings=InMemoryRatingRepository(),
        bookings=InMemoryBookingRepository(),
        clock=_now,
    )
    r = await handler.handle(CreateRatingCommand(
        actor_id=uuid4(), booking_id=uuid4(), score=5, comment=None,
    ))
    assert r.is_failure
    assert r.error == "BookingNotFound"
    assert r.status_code == 404


async def test_other_customers_booking_rejected():
    real_customer = uuid4()
    booking = _build_approved_ended(customer_id=real_customer)
    bookings = InMemoryBookingRepository()
    ratings = InMemoryRatingRepository()
    await bookings.add(booking)
    handler = CreateRatingHandler(
        ratings=ratings, bookings=bookings, clock=_now,
    )
    r = await handler.handle(CreateRatingCommand(
        actor_id=uuid4(),  # not real_customer
        booking_id=booking.id, score=5, comment=None,
    ))
    assert r.is_failure
    assert r.error == "BookingNotEligibleForRating"
    assert r.status_code == 422


async def test_pending_booking_rejected():
    customer_id = uuid4()
    end = _now() - timedelta(days=1)
    start = end - timedelta(hours=1)
    sr = DateTimeRange.create(start_at=start, end_at=end).value
    pending = Booking.create_pending(
        resource_id=uuid4(), customer_id=customer_id,
        slot_range=sr, total_price_cents=Money.create(8000).value,
        customer_note=None, now=_now() - timedelta(days=2),
    )
    bookings = InMemoryBookingRepository()
    ratings = InMemoryRatingRepository()
    await bookings.add(pending)
    handler = CreateRatingHandler(
        ratings=ratings, bookings=bookings, clock=_now,
    )
    r = await handler.handle(CreateRatingCommand(
        actor_id=customer_id, booking_id=pending.id, score=5, comment=None,
    ))
    assert r.is_failure
    assert r.error == "BookingNotEligibleForRating"


async def test_future_slot_rejected():
    """APPROVED but slot end is still in the future → ineligible."""
    customer_id = uuid4()
    end = _now() + timedelta(hours=1)
    start = _now()
    sr = DateTimeRange.create(start_at=start, end_at=end).value
    booking = Booking.create_pending(
        resource_id=uuid4(), customer_id=customer_id,
        slot_range=sr, total_price_cents=Money.create(8000).value,
        customer_note=None, now=_now(),
    )
    booking.approve(actor_id=uuid4(), now=_now())
    bookings = InMemoryBookingRepository()
    ratings = InMemoryRatingRepository()
    await bookings.add(booking)
    handler = CreateRatingHandler(
        ratings=ratings, bookings=bookings, clock=_now,
    )
    r = await handler.handle(CreateRatingCommand(
        actor_id=customer_id, booking_id=booking.id, score=5, comment=None,
    ))
    assert r.is_failure
    assert r.error == "BookingNotEligibleForRating"


async def test_past_90day_window_rejected():
    customer_id = uuid4()
    booking = _build_approved_ended(customer_id=customer_id, days_ago=91)
    bookings = InMemoryBookingRepository()
    ratings = InMemoryRatingRepository()
    await bookings.add(booking)
    handler = CreateRatingHandler(
        ratings=ratings, bookings=bookings, clock=_now,
    )
    r = await handler.handle(CreateRatingCommand(
        actor_id=customer_id, booking_id=booking.id, score=5, comment=None,
    ))
    assert r.is_failure
    assert r.error == "BookingNotEligibleForRating"


async def test_existing_rating_returns_409():
    customer_id = uuid4()
    booking = _build_approved_ended(customer_id=customer_id)
    bookings = InMemoryBookingRepository()
    ratings = InMemoryRatingRepository()
    await bookings.add(booking)
    handler = CreateRatingHandler(
        ratings=ratings, bookings=bookings, clock=_now,
    )
    cmd = CreateRatingCommand(
        actor_id=customer_id, booking_id=booking.id, score=5, comment=None,
    )
    first = await handler.handle(cmd)
    assert first.is_success
    second = await handler.handle(cmd)
    assert second.is_failure
    assert second.error == "RatingAlreadyExists"
    assert second.status_code == 409


async def test_invalid_score_returns_422():
    customer_id = uuid4()
    booking = _build_approved_ended(customer_id=customer_id)
    bookings = InMemoryBookingRepository()
    ratings = InMemoryRatingRepository()
    await bookings.add(booking)
    handler = CreateRatingHandler(
        ratings=ratings, bookings=bookings, clock=_now,
    )
    r = await handler.handle(CreateRatingCommand(
        actor_id=customer_id, booking_id=booking.id, score=0, comment=None,
    ))
    assert r.is_failure
    assert r.status_code == 422
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/unit/use_cases/ratings/commands/test_create_rating.py -v`
Expected: import error.

- [ ] **Step 3: Implement the handler**

`app/use_cases/ratings/commands/__init__.py` (empty).

`app/use_cases/ratings/commands/create_rating.py`:

```python
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable
from uuid import UUID

from app.domain.bookings.booking_status import BookingStatus
from app.domain.bookings.repository import IBookingRepository
from app.domain.ratings.rating import Rating
from app.domain.ratings.repository import IRatingRepository
from app.domain.shared.field_error import FieldError
from app.domain.shared.result import Result
from app.domain.shared.value_objects.rating_score import RatingScore
from app.domain.shared.value_objects.short_description import ShortDescription
from app.use_cases.ratings.dtos import RatingDto


_RATING_WINDOW_DAYS = 90


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True, kw_only=True, slots=True)
class CreateRatingCommand:
    actor_id: UUID
    booking_id: UUID
    score: int
    comment: str | None


class CreateRatingHandler:
    def __init__(
        self,
        *,
        ratings: IRatingRepository,
        bookings: IBookingRepository,
        clock: Callable[[], datetime] = _utcnow,
    ) -> None:
        self._ratings = ratings
        self._bookings = bookings
        self._clock = clock

    async def handle(self, cmd: CreateRatingCommand) -> Result[RatingDto]:
        # 1. VO-validate inputs.
        errors: list[FieldError] = []
        score_r = RatingScore.create(cmd.score)
        if score_r.is_failure:
            errors.append(FieldError(field="score", code=score_r.error))
        comment: ShortDescription | None = None
        if cmd.comment is not None and cmd.comment != "":
            note_r = ShortDescription.create(cmd.comment)
            if note_r.is_failure:
                errors.append(FieldError(field="comment", code=note_r.error))
            else:
                comment = note_r.value
        if errors:
            return Result.failure_many(errors, status_code=422)
        score = score_r.value

        # 2. Load booking; verify eligibility.
        booking_r = await self._bookings.get_by_id(cmd.booking_id)
        if booking_r.is_failure:
            return Result.from_failure(booking_r)
        booking = booking_r.value
        if booking is None:
            return Result.failure("BookingNotFound", status_code=404)

        if booking.customer_id != cmd.actor_id:
            return Result.failure("BookingNotEligibleForRating", status_code=422)
        if booking.status is not BookingStatus.APPROVED:
            return Result.failure("BookingNotEligibleForRating", status_code=422)

        now = self._clock()
        if booking.slot_range.end_at >= now:
            return Result.failure("BookingNotEligibleForRating", status_code=422)
        if now > booking.slot_range.end_at + timedelta(days=_RATING_WINDOW_DAYS):
            return Result.failure("BookingNotEligibleForRating", status_code=422)

        # 3. Dedup check (UNIQUE booking_id at the DB layer is the actual
        # race protection — this short-circuits the common single-shot case).
        existing = await self._ratings.get_by_booking_id(cmd.booking_id)
        if existing.is_failure:
            return Result.from_failure(existing)
        if existing.value is not None:
            return Result.failure("RatingAlreadyExists", status_code=409)

        # 4. Persist.
        rating = Rating.create(
            booking_id=booking.id,
            resource_id=booking.resource_id,
            customer_id=booking.customer_id,
            score=score,
            comment=comment,
            now=now,
        )
        add_r = await self._ratings.add(rating)
        if add_r.is_failure:
            return Result.from_failure(add_r)
        return Result.success(RatingDto.from_entity(rating))
```

- [ ] **Step 4: Run tests**

Run: `.venv/bin/pytest tests/unit/use_cases/ratings/commands/test_create_rating.py -v`
Expected: 9 PASSED.

- [ ] **Step 5: Run full unit + integration**

Run: `.venv/bin/pytest tests/unit/ tests/integration/ -q`
Expected: green.

- [ ] **Step 6: Commit**

```bash
git add app/use_cases/ratings/commands/__init__.py \
        app/use_cases/ratings/commands/create_rating.py \
        tests/unit/use_cases/ratings/commands/__init__.py \
        tests/unit/use_cases/ratings/commands/test_create_rating.py
git commit -m "$(cat <<'EOF'
feat(ratings): CreateRatingHandler

Plan 09 task 8. 4-step pipeline: VO-validate inputs (failure_many
422 envelope on score/comment), load booking + 4-clause eligibility
gate (customer match, APPROVED status, slot ended, ≤ 90d after end),
dedup pre-check (DB UNIQUE backstop catches races), persist + return
DTO. Clock-injected per Plan 08 polish pattern.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 9: `UpdateRatingHandler`

**Files:**
- Create: `app/use_cases/ratings/commands/update_rating.py`
- Create: `tests/unit/use_cases/ratings/commands/test_update_rating.py`

- [ ] **Step 1: Write failing tests**

`tests/unit/use_cases/ratings/commands/test_update_rating.py`:

```python
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.domain.ratings.rating import Rating
from app.domain.shared.value_objects.rating_score import RatingScore
from app.domain.shared.value_objects.short_description import ShortDescription
from app.use_cases.ratings.commands.update_rating import (
    UpdateRatingCommand,
    UpdateRatingHandler,
)
from tests.unit.use_cases.ratings.fakes.in_memory_rating_repository import (
    InMemoryRatingRepository,
)


pytestmark = pytest.mark.asyncio


def _now() -> datetime:
    return datetime(2026, 4, 28, 12, 0, 0, tzinfo=timezone.utc)


def _seed_rating(*, customer_id, age_days: int = 0) -> Rating:
    return Rating.create(
        booking_id=uuid4(), resource_id=uuid4(), customer_id=customer_id,
        score=RatingScore.create(3).value,
        comment=ShortDescription.create("inicial").value,
        now=_now() - timedelta(days=age_days),
    )


async def test_happy_path_updates_score_and_comment():
    customer_id = uuid4()
    rating = _seed_rating(customer_id=customer_id)
    repo = InMemoryRatingRepository()
    await repo.add(rating)
    handler = UpdateRatingHandler(ratings=repo, clock=_now)
    cmd = UpdateRatingCommand(
        actor_id=customer_id, booking_id=rating.booking_id,
        score=5, comment="atualizado",
    )
    r = await handler.handle(cmd)
    assert r.is_success
    assert r.value.score == 5
    assert r.value.comment == "atualizado"


async def test_can_clear_comment():
    customer_id = uuid4()
    rating = _seed_rating(customer_id=customer_id)
    repo = InMemoryRatingRepository()
    await repo.add(rating)
    handler = UpdateRatingHandler(ratings=repo, clock=_now)
    r = await handler.handle(UpdateRatingCommand(
        actor_id=customer_id, booking_id=rating.booking_id,
        score=4, comment=None,
    ))
    assert r.is_success
    assert r.value.comment is None


async def test_unknown_booking_returns_404():
    handler = UpdateRatingHandler(
        ratings=InMemoryRatingRepository(), clock=_now,
    )
    r = await handler.handle(UpdateRatingCommand(
        actor_id=uuid4(), booking_id=uuid4(), score=5, comment=None,
    ))
    assert r.is_failure
    assert r.error == "RatingNotFound"
    assert r.status_code == 404


async def test_other_customer_returns_404():
    """Cross-customer access should look identical to "not found" — no leak."""
    real_customer = uuid4()
    rating = _seed_rating(customer_id=real_customer)
    repo = InMemoryRatingRepository()
    await repo.add(rating)
    handler = UpdateRatingHandler(ratings=repo, clock=_now)
    r = await handler.handle(UpdateRatingCommand(
        actor_id=uuid4(), booking_id=rating.booking_id,
        score=5, comment=None,
    ))
    assert r.is_failure
    assert r.error == "RatingNotFound"


async def test_past_7day_window_rejected():
    customer_id = uuid4()
    rating = _seed_rating(customer_id=customer_id, age_days=8)
    repo = InMemoryRatingRepository()
    await repo.add(rating)
    handler = UpdateRatingHandler(ratings=repo, clock=_now)
    r = await handler.handle(UpdateRatingCommand(
        actor_id=customer_id, booking_id=rating.booking_id,
        score=5, comment=None,
    ))
    assert r.is_failure
    assert r.error == "RatingEditWindowExpired"
    assert r.status_code == 403


async def test_invalid_score_returns_422():
    customer_id = uuid4()
    rating = _seed_rating(customer_id=customer_id)
    repo = InMemoryRatingRepository()
    await repo.add(rating)
    handler = UpdateRatingHandler(ratings=repo, clock=_now)
    r = await handler.handle(UpdateRatingCommand(
        actor_id=customer_id, booking_id=rating.booking_id,
        score=99, comment=None,
    ))
    assert r.is_failure
    assert r.status_code == 422
```

- [ ] **Step 2: RED.**

Run: `.venv/bin/pytest tests/unit/use_cases/ratings/commands/test_update_rating.py -v`
Expected: import error.

- [ ] **Step 3: Implement the handler**

`app/use_cases/ratings/commands/update_rating.py`:

```python
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable
from uuid import UUID

from app.domain.ratings.repository import IRatingRepository
from app.domain.shared.field_error import FieldError
from app.domain.shared.result import Result
from app.domain.shared.value_objects.rating_score import RatingScore
from app.domain.shared.value_objects.short_description import ShortDescription
from app.use_cases.ratings.dtos import RatingDto


_EDIT_WINDOW_DAYS = 7


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True, kw_only=True, slots=True)
class UpdateRatingCommand:
    actor_id: UUID
    booking_id: UUID         # route is booking-keyed; handler resolves to rating
    score: int
    comment: str | None


class UpdateRatingHandler:
    def __init__(
        self,
        *,
        ratings: IRatingRepository,
        clock: Callable[[], datetime] = _utcnow,
    ) -> None:
        self._ratings = ratings
        self._clock = clock

    async def handle(self, cmd: UpdateRatingCommand) -> Result[RatingDto]:
        # 1. VO-validate inputs.
        errors: list[FieldError] = []
        score_r = RatingScore.create(cmd.score)
        if score_r.is_failure:
            errors.append(FieldError(field="score", code=score_r.error))
        comment: ShortDescription | None = None
        if cmd.comment is not None and cmd.comment != "":
            note_r = ShortDescription.create(cmd.comment)
            if note_r.is_failure:
                errors.append(FieldError(field="comment", code=note_r.error))
            else:
                comment = note_r.value
        if errors:
            return Result.failure_many(errors, status_code=422)

        # 2. Load rating by booking; verify ownership + edit window.
        rating_r = await self._ratings.get_by_booking_id(cmd.booking_id)
        if rating_r.is_failure:
            return Result.from_failure(rating_r)
        rating = rating_r.value
        if rating is None or rating.customer_id != cmd.actor_id:
            # Cross-customer access masked as not-found per spec §3.9 privacy
            # convention (matches Plan 08 BookingNotFound pattern).
            return Result.failure("RatingNotFound", status_code=404)

        now = self._clock()
        if now > rating.created_at + timedelta(days=_EDIT_WINDOW_DAYS):
            return Result.failure("RatingEditWindowExpired", status_code=403)

        # 3. Mutate + persist.
        rating.update_text(score=score_r.value, comment=comment, now=now)
        update_r = await self._ratings.update(rating)
        if update_r.is_failure:
            return Result.from_failure(update_r)
        return Result.success(RatingDto.from_entity(rating))
```

- [ ] **Step 4: Run tests**

Run: `.venv/bin/pytest tests/unit/use_cases/ratings/commands/test_update_rating.py -v`
Expected: 6 PASSED.

- [ ] **Step 5: Run full unit + integration**

Run: `.venv/bin/pytest tests/unit/ tests/integration/ -q`
Expected: green.

- [ ] **Step 6: Commit**

```bash
git add app/use_cases/ratings/commands/update_rating.py \
        tests/unit/use_cases/ratings/commands/test_update_rating.py
git commit -m "$(cat <<'EOF'
feat(ratings): UpdateRatingHandler

Plan 09 task 9. Validates score/comment VO, loads rating, masks
cross-customer access as RatingNotFound (404, no leak), enforces
7-day edit window (403 RatingEditWindowExpired), mutates aggregate
+ persists. Clock-injected.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 10: Query handlers — `ListMyRatingsHandler` + `ListPublicRatingsForResourceHandler`

**Files:**
- Create: `app/use_cases/ratings/queries/__init__.py` (empty)
- Create: `app/use_cases/ratings/queries/list_my_ratings.py`
- Create: `app/use_cases/ratings/queries/list_public_ratings.py`
- Create: `tests/unit/use_cases/ratings/queries/__init__.py` (empty)
- Create: `tests/unit/use_cases/ratings/queries/test_list_my_ratings.py`
- Create: `tests/unit/use_cases/ratings/queries/test_list_public_ratings.py`

- [ ] **Step 1: Write failing tests for `ListMyRatingsHandler`**

`tests/unit/use_cases/ratings/queries/test_list_my_ratings.py`:

```python
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.domain.ratings.rating import Rating
from app.domain.shared.value_objects.rating_score import RatingScore
from app.use_cases.ratings.queries.list_my_ratings import (
    ListMyRatingsHandler,
    ListMyRatingsQuery,
)
from tests.unit.use_cases.ratings.fakes.in_memory_rating_repository import (
    InMemoryRatingRepository,
)


pytestmark = pytest.mark.asyncio


def _now() -> datetime:
    return datetime(2026, 4, 28, 12, 0, 0, tzinfo=timezone.utc)


def _rating(*, customer_id, days_ago: int = 0) -> Rating:
    return Rating.create(
        booking_id=uuid4(), resource_id=uuid4(), customer_id=customer_id,
        score=RatingScore.create(5).value, comment=None,
        now=_now() - timedelta(days=days_ago),
    )


async def test_returns_only_my_ratings():
    me = uuid4()
    other = uuid4()
    repo = InMemoryRatingRepository()
    mine = _rating(customer_id=me)
    theirs = _rating(customer_id=other)
    await repo.add(mine)
    await repo.add(theirs)
    handler = ListMyRatingsHandler(ratings=repo)
    r = await handler.handle(ListMyRatingsQuery(actor_id=me))
    assert r.is_success
    assert [it.id for it in r.value.items] == [mine.id]


async def test_orders_newest_first():
    me = uuid4()
    repo = InMemoryRatingRepository()
    older = _rating(customer_id=me, days_ago=10)
    newer = _rating(customer_id=me, days_ago=1)
    await repo.add(older)
    await repo.add(newer)
    handler = ListMyRatingsHandler(ratings=repo)
    r = await handler.handle(ListMyRatingsQuery(actor_id=me))
    assert [it.id for it in r.value.items] == [newer.id, older.id]


async def test_clamps_page_size_to_100():
    handler = ListMyRatingsHandler(ratings=InMemoryRatingRepository())
    r = await handler.handle(ListMyRatingsQuery(actor_id=uuid4(), page_size=500))
    assert r.is_success
    assert r.value.page_size == 100


async def test_clamps_page_min_1():
    handler = ListMyRatingsHandler(ratings=InMemoryRatingRepository())
    r = await handler.handle(ListMyRatingsQuery(actor_id=uuid4(), page=0))
    assert r.is_success
    assert r.value.page == 1
```

- [ ] **Step 2: Write failing tests for `ListPublicRatingsForResourceHandler`**

`tests/unit/use_cases/ratings/queries/test_list_public_ratings.py`:

```python
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.domain.ratings.rating import Rating
from app.domain.resources.resource import Resource
from app.domain.shared.value_objects.rating_score import RatingScore
from app.domain.shared.value_objects.short_description import ShortDescription
from app.domain.resources.weekly_schedule import WeeklySchedule
from app.domain.shared.value_objects.time_window import TimeWindow
from app.domain.shared.weekday import Weekday
from app.use_cases.ratings.queries.list_public_ratings import (
    ListPublicRatingsForResourceHandler,
    ListPublicRatingsForResourceQuery,
)
from tests.unit.use_cases.ratings.fakes.in_memory_rating_repository import (
    InMemoryRatingRepository,
)


pytestmark = pytest.mark.asyncio


def _now() -> datetime:
    return datetime(2026, 4, 28, 12, 0, 0, tzinfo=timezone.utc)


def _build_resource(*, owner_slug: str = "owner", resource_slug: str = "campo") -> Resource:
    """Plan 08 lessons: use time(...) and WeeklySchedule wrapper for Resource.create."""
    from datetime import time
    operating = {wd: [TimeWindow.create(time(6, 0), time(22, 0)).value] for wd in Weekday}
    schedule = WeeklySchedule.create(slot_duration_minutes=60, days=operating).value
    r = Resource.create(
        owner_id=uuid4(), resource_type_id=uuid4(),
        slug=resource_slug, name="Campo", description="",
        city="SP", region="SP", timezone="America/Sao_Paulo",
        slot_duration_minutes=60, base_price_cents=8000,
        customer_cancellation_cutoff_hours=24,
        operating_hours=schedule, pricing_rules=[],
        custom_attributes=[], base_attributes={},
    ).value
    r.publish()
    return r


class _FakeResourceRepo:
    """Adapts the get-by-(owner_slug, resource_slug) shape used by Plan 08 Task 20."""
    def __init__(self, resource: Resource | None):
        self._r = resource

    async def get_by_owner_slug_and_resource_slug(self, owner_slug, resource_slug):
        return self._r


async def test_returns_only_comment_bearing_for_resource():
    res = _build_resource()
    repo = InMemoryRatingRepository()
    note = ShortDescription.create("ótimo").value
    with_comment = Rating.create(
        booking_id=uuid4(), resource_id=res.id, customer_id=uuid4(),
        score=RatingScore.create(5).value, comment=note, now=_now(),
    )
    no_comment = Rating.create(
        booking_id=uuid4(), resource_id=res.id, customer_id=uuid4(),
        score=RatingScore.create(4).value, comment=None,
        now=_now() - timedelta(days=1),
    )
    other_resource = Rating.create(
        booking_id=uuid4(), resource_id=uuid4(), customer_id=uuid4(),
        score=RatingScore.create(5).value, comment=note, now=_now(),
    )
    await repo.add(with_comment)
    await repo.add(no_comment)
    await repo.add(other_resource)
    handler = ListPublicRatingsForResourceHandler(
        ratings=repo, resources=_FakeResourceRepo(res),
    )
    r = await handler.handle(ListPublicRatingsForResourceQuery(
        owner_slug="owner", resource_slug="campo",
    ))
    assert r.is_success
    items = r.value.items
    assert len(items) == 1
    assert items[0].score == 5
    assert items[0].comment == "ótimo"


async def test_unknown_resource_returns_404():
    handler = ListPublicRatingsForResourceHandler(
        ratings=InMemoryRatingRepository(),
        resources=_FakeResourceRepo(None),
    )
    r = await handler.handle(ListPublicRatingsForResourceQuery(
        owner_slug="missing", resource_slug="missing",
    ))
    assert r.is_failure
    assert r.error == "ResourceNotFound"
    assert r.status_code == 404


async def test_soft_deleted_resource_returns_404():
    res = _build_resource()
    res.soft_delete(now=_now() - timedelta(days=1))
    handler = ListPublicRatingsForResourceHandler(
        ratings=InMemoryRatingRepository(),
        resources=_FakeResourceRepo(res),
    )
    r = await handler.handle(ListPublicRatingsForResourceQuery(
        owner_slug="owner", resource_slug="campo",
    ))
    assert r.is_failure
    assert r.error == "ResourceNotFound"


async def test_clamps_page_size():
    res = _build_resource()
    handler = ListPublicRatingsForResourceHandler(
        ratings=InMemoryRatingRepository(),
        resources=_FakeResourceRepo(res),
    )
    r = await handler.handle(ListPublicRatingsForResourceQuery(
        owner_slug="owner", resource_slug="campo", page_size=500,
    ))
    assert r.is_success
    assert r.value.page_size == 100
```

- [ ] **Step 3: RED.**

Run: `.venv/bin/pytest tests/unit/use_cases/ratings/queries/ -v`
Expected: import errors.

- [ ] **Step 4: Implement `ListMyRatingsHandler`**

`app/use_cases/ratings/queries/__init__.py` (empty).

`app/use_cases/ratings/queries/list_my_ratings.py`:

```python
from __future__ import annotations
from dataclasses import dataclass
from uuid import UUID

from app.domain.ratings.repository import IRatingRepository
from app.domain.shared.result import Result
from app.use_cases.ratings.dtos import RatingDto, RatingListDto


_MAX_PAGE_SIZE = 100


@dataclass(frozen=True, kw_only=True, slots=True)
class ListMyRatingsQuery:
    actor_id: UUID
    page: int = 1
    page_size: int = 50


class ListMyRatingsHandler:
    def __init__(self, *, ratings: IRatingRepository) -> None:
        self._ratings = ratings

    async def handle(
        self, query: ListMyRatingsQuery,
    ) -> Result[RatingListDto]:
        page = max(1, query.page)
        page_size = max(1, min(query.page_size, _MAX_PAGE_SIZE))
        rows_r = await self._ratings.list_by_customer(
            query.actor_id, page=page, page_size=page_size,
        )
        if rows_r.is_failure:
            return Result.from_failure(rows_r)
        items = tuple(RatingDto.from_entity(r) for r in rows_r.value)
        return Result.success(RatingListDto(
            items=items, page=page, page_size=page_size,
        ))
```

- [ ] **Step 5: Implement `ListPublicRatingsForResourceHandler`**

`app/use_cases/ratings/queries/list_public_ratings.py`:

```python
from __future__ import annotations
from dataclasses import dataclass

from app.domain.ratings.repository import IRatingRepository
from app.domain.resources.repository import IResourceRepository
from app.domain.shared.result import Result
from app.use_cases.ratings.dtos import PublicRatingDto, PublicRatingListDto


_MAX_PAGE_SIZE = 100


@dataclass(frozen=True, kw_only=True, slots=True)
class ListPublicRatingsForResourceQuery:
    owner_slug: str
    resource_slug: str
    page: int = 1
    page_size: int = 50


class ListPublicRatingsForResourceHandler:
    def __init__(
        self,
        *,
        ratings: IRatingRepository,
        resources: IResourceRepository,
    ) -> None:
        self._ratings = ratings
        self._resources = resources

    async def handle(
        self, query: ListPublicRatingsForResourceQuery,
    ) -> Result[PublicRatingListDto]:
        # IResourceRepository.get_by_owner_slug_and_resource_slug returns
        # Resource | None directly per Plan 08 Task 20 adaptation.
        resource = await self._resources.get_by_owner_slug_and_resource_slug(
            query.owner_slug, query.resource_slug,
        )
        if resource is None or resource.is_deleted():
            return Result.failure("ResourceNotFound", status_code=404)

        page = max(1, query.page)
        page_size = max(1, min(query.page_size, _MAX_PAGE_SIZE))
        rows_r = await self._ratings.list_with_comment_for_resource(
            resource.id, page=page, page_size=page_size,
        )
        if rows_r.is_failure:
            return Result.from_failure(rows_r)
        items = tuple(PublicRatingDto.from_entity(r) for r in rows_r.value)
        return Result.success(PublicRatingListDto(
            items=items, page=page, page_size=page_size,
        ))
```

- [ ] **Step 6: Run tests**

Run: `.venv/bin/pytest tests/unit/use_cases/ratings/queries/ -v`
Expected: 7 PASSED (4 list_my + 3 list_public... wait, it's 4 list_my + 4 list_public = 8). Verify by reading the test files; expected count is the actual count.

- [ ] **Step 7: Run full unit + integration**

Run: `.venv/bin/pytest tests/unit/ tests/integration/ -q`
Expected: green.

- [ ] **Step 8: Commit**

```bash
git add app/use_cases/ratings/queries/__init__.py \
        app/use_cases/ratings/queries/list_my_ratings.py \
        app/use_cases/ratings/queries/list_public_ratings.py \
        tests/unit/use_cases/ratings/queries/__init__.py \
        tests/unit/use_cases/ratings/queries/test_list_my_ratings.py \
        tests/unit/use_cases/ratings/queries/test_list_public_ratings.py
git commit -m "$(cat <<'EOF'
feat(ratings): query handlers (list-mine + list-public-for-resource)

Plan 09 task 10. ListMyRatingsHandler clamps page/page_size, returns
the customer's own ratings newest-first.
ListPublicRatingsForResourceHandler resolves resource by
(owner_slug, resource_slug), returns ResourceNotFound 404 if missing
or soft-deleted, then lists comment-bearing ratings only via
PublicRatingDto (no customer_id, no booking_id — privacy filter).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 11: Resource listing retrofit — wire `IRatingRepository` into 5 resource handlers

**Files:**
- Modify: `app/use_cases/resources/dtos.py`
- Modify: `app/use_cases/resources/queries/list_my_resources.py`
- Modify: `app/use_cases/resources/queries/get_my_resource.py`
- Modify: `app/use_cases/resources/queries/list_public_resources.py`
- Modify: `app/use_cases/resources/queries/get_public_resource.py`
- Modify: `app/use_cases/accounts/queries/get_owner_public_page.py`
- Modify: `app/api/v1/me_resources/schemas.py` (add fields to `ResourceResponse` + `OwnerPublicPageResponse`)
- Modify: `app/api/v1/public_resources/schemas.py` (same)
- Modify: `app/api/v1/me_resources/deps.py` + `app/api/v1/public_resources/deps.py` — pass `IRatingRepository` to the 5 handler factories
- Modify existing tests for the 5 handlers if any assert on DTO field set (must stay green by inspecting the DTO doesn't fail on new optional fields).

This is the largest task in Plan 09. Read each existing handler before editing.

- [ ] **Step 1: Extend `ResourceDto` with optional rating fields**

In `app/use_cases/resources/dtos.py`, add two fields to `ResourceDto` (which is `@dataclass(frozen=True, slots=True)`). Append after the existing fields, BEFORE the `from_entity` classmethod:

```python
rating_avg: Decimal | None = None
rating_count: int = 0
```

Add `from decimal import Decimal` to imports. Both fields default to `None`/`0` so existing `from_entity(res)` call sites still work without modification. Add a new constructor that uses `dataclasses.replace` to layer the aggregate fields onto the base DTO:

```python
@classmethod
def from_entity_with_aggregate(
    cls,
    res,  # Resource
    aggregate,  # RatingAggregate
) -> "ResourceDto":
    """Build ResourceDto with rating fields populated from a RatingAggregate.
    All non-rating fields come from the existing from_entity path."""
    return dataclasses.replace(
        cls.from_entity(res),
        rating_avg=aggregate.avg_score,
        rating_count=aggregate.count,
    )
```

(Add `import dataclasses` if not already imported; the file may already import `dataclass` from `dataclasses` — augment to `from dataclasses import dataclass, replace` or use the module form `dataclasses.replace`.)

- [ ] **Step 2: Modify `ListPublicResourcesHandler`**

`app/use_cases/resources/queries/list_public_resources.py`:

Add `IRatingRepository` to the constructor, then after fetching resources call `get_aggregates_for_resources(ids)` and merge:

```python
# At top of file, add imports:
from app.domain.ratings.aggregate import RatingAggregate
from app.domain.ratings.repository import IRatingRepository

# In handler __init__, add the new dep:
def __init__(
    self,
    *,
    resources: IResourceRepository,
    ratings: IRatingRepository,
) -> None:
    self._resources = resources
    self._ratings = ratings

# In handle(), after loading resources, before returning:
resource_ids = [r.id for r in res_list]
aggs_r = await self._ratings.get_aggregates_for_resources(resource_ids)
if aggs_r.is_failure:
    return Result.from_failure(aggs_r)
aggs = aggs_r.value
return Result.success([
    ResourceDto.from_entity_with_aggregate(r, aggs[r.id])
    for r in res_list
])
```

Adapt the variable name `res_list` to whatever the existing handler uses internally.

- [ ] **Step 3: Modify `GetPublicResourceHandler`**

Same pattern: add `ratings: IRatingRepository` dep; after loading the single resource, call `get_aggregates_for_resources([resource.id])` and use `from_entity_with_aggregate(resource, aggs[resource.id])`.

- [ ] **Step 4: Modify `ListMyResourcesHandler`**

Same pattern.

- [ ] **Step 5: Modify `GetMyResourceHandler`**

Same pattern.

- [ ] **Step 6: Modify `GetOwnerPublicPageHandler`**

This handler also needs the count-weighted average across the owner's resources. Add `ratings: IRatingRepository` dep, then:

```python
# After loading the owner's resources:
resource_ids = [r.id for r in resources]
aggs_r = await self._ratings.get_aggregates_for_resources(resource_ids)
if aggs_r.is_failure:
    return Result.from_failure(aggs_r)
aggs = aggs_r.value

# Per-resource DTOs:
resource_dtos = [
    ResourceDto.from_entity_with_aggregate(r, aggs[r.id])
    for r in resources
]

# Owner-level rolled-up aggregate (count-weighted average):
total_count = sum(a.count for a in aggs.values())
if total_count == 0:
    owner_avg = None
else:
    weighted_sum = sum(
        (a.avg_score * a.count if a.avg_score is not None else Decimal(0))
        for a in aggs.values()
    )
    owner_avg = (weighted_sum / Decimal(total_count)).quantize(Decimal("0.1"))
```

Update `OwnerPublicPageDto` to include `owner_rating_avg: Decimal | None` and `owner_rating_count: int`. The DTO definition is in the same file — add the two fields with default `None`/`0`. Wire the computed values into the DTO at the return site.

- [ ] **Step 7: Update Pydantic response schemas**

In `app/api/v1/me_resources/schemas.py`, modify `ResourceResponse` to add:

```python
rating_avg: Decimal | None = None
rating_count: int = 0
```

(Add `from decimal import Decimal` if missing.) Update the `from_dto` classmethod to copy these two fields from the DTO.

In `app/api/v1/public_resources/schemas.py`, modify `OwnerPublicPageResponse` to add:

```python
owner_rating_avg: Decimal | None = None
owner_rating_count: int = 0
```

Wire from the DTO in the route layer (in `public_resources/routes.py`'s `get_owner_page`, the return statement currently builds `OwnerPublicPageResponse(...)` — add the two new fields).

- [ ] **Step 8: Update DI providers in `app/api/v1/me_resources/deps.py` and `app/api/v1/public_resources/deps.py`**

Each of the 5 handler factories needs to instantiate `SQLAlchemyRatingRepository(session)` and pass it as `ratings=...`. Pattern:

```python
from app.infrastructure.repositories.rating_repository import (
    SQLAlchemyRatingRepository,
)


# In each handler-factory function (5 total):
async def get_list_public_handler(...) -> ListPublicResourcesHandler:
    return ListPublicResourcesHandler(
        resources=SQLAlchemyResourceRepository(session),
        ratings=SQLAlchemyRatingRepository(session),
    )
```

- [ ] **Step 9: Update existing handler unit tests**

Search for instantiations of the 5 handlers in `tests/unit/use_cases/resources/queries/` and `tests/unit/use_cases/accounts/queries/`. Each test that constructs one of the handlers needs to add `ratings=InMemoryRatingRepository()`. For tests that don't assert on rating fields, an empty repo is fine — defaults to `(None, 0)`.

If any tests assert on the DTO shape via `asdict` or `==`, they may fail because the DTO grew two fields. Update those assertions accordingly.

- [ ] **Step 10: Add a new test verifying the retrofit**

Add to `tests/unit/use_cases/resources/queries/test_list_public_resources.py` (or similar):

```python
async def test_list_public_resources_includes_rating_aggregate(...):
    """Inserts a rating, then asserts list response includes rating_avg/count."""
    # Detailed setup follows the handler's existing test pattern;
    # exact code depends on what fixtures the file already has.
```

Concretely, build a resource via the existing helper, attach a rating to it via `InMemoryRatingRepository`, run the handler with both repos wired, and assert `dto.rating_avg == Decimal("5.0")` (or whatever score), `dto.rating_count == 1`. If a similar test would need substantial fixture rebuilds, the integration-tier test in Task 5 (`test_get_aggregates_for_resources_full_coverage`) already covers the persistence side; you can skip a parallel unit test as long as one of the e2e tests in Task 14 hits the retrofit.

- [ ] **Step 11: Run full unit + integration**

Run: `.venv/bin/pytest tests/unit/ tests/integration/ -q`
Expected: green.

- [ ] **Step 12: Smoke-boot the FastAPI app**

Run:
```
.venv/bin/python -c "
from app.main import app
print('boot ok')
"
```
Expected: `boot ok`. (Verifies the DI changes don't break import-time wiring.)

- [ ] **Step 13: Commit**

```bash
git add app/use_cases/resources/ \
        app/use_cases/accounts/queries/get_owner_public_page.py \
        app/api/v1/me_resources/schemas.py \
        app/api/v1/public_resources/schemas.py \
        app/api/v1/me_resources/deps.py \
        app/api/v1/public_resources/deps.py \
        tests/unit/use_cases/
git commit -m "$(cat <<'EOF'
feat(resources): retrofit listings with rating_avg + rating_count

Plan 09 task 11. ResourceDto + ResourceResponse + OwnerPublicPageDto/
Response gain optional rating_avg (Decimal | None, one decimal) and
rating_count (int, default 0). 5 query handlers (list_my, get_my,
list_public, get_public, get_owner_public_page) each take a new
ratings: IRatingRepository dep and merge aggregates via the
get_aggregates_for_resources batch call (single roundtrip per page).
Owner page additionally computes a count-weighted average across
the owner's published resources.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 12: Register Plan 09 stable error codes

**Files:**
- Modify: `app/api/error_codes.py`
- Modify: `tests/unit/architecture/test_error_code_coverage.py`

- [ ] **Step 1: Add pt-BR mappings**

In `app/api/error_codes.py`, append a new section just before the closing `}` of `ERROR_MESSAGES_PT_BR`:

```python
    # --- Plan 09 — ratings (handler-level) ---
    "RatingNotFound": "Avaliação não encontrada.",
    "RatingAlreadyExists": "Já existe uma avaliação para esta reserva.",
    "BookingNotEligibleForRating": "Reserva não é elegível para avaliação.",
    "RatingEditWindowExpired": "Prazo para editar a avaliação expirou.",
```

- [ ] **Step 2: Update arch test allowlist**

Open `tests/unit/architecture/test_error_code_coverage.py`. Find the `handler_level_allowlist`. Append:

```python
        # Plan 09 — ratings handler-level
        "RatingNotFound",
        "RatingAlreadyExists",
        "BookingNotEligibleForRating",
        "RatingEditWindowExpired",
```

- [ ] **Step 3: Run the architecture test**

Run: `.venv/bin/pytest tests/unit/architecture/test_error_code_coverage.py -v`
Expected: PASS.

- [ ] **Step 4: Run full unit + integration**

Run: `.venv/bin/pytest tests/unit/ tests/integration/ -q`
Expected: green.

- [ ] **Step 5: Commit**

```bash
git add app/api/error_codes.py tests/unit/architecture/test_error_code_coverage.py
git commit -m "$(cat <<'EOF'
feat(ratings): register Plan 09 stable error codes

Plan 09 task 12. 4 handler-level codes added to ERROR_MESSAGES_PT_BR
and the architecture allowlist: RatingNotFound (404),
RatingAlreadyExists (409), BookingNotEligibleForRating (422 —
collapses booking-status/customer-mismatch/window-expired into one
code per spec §3.9), RatingEditWindowExpired (403).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 13: API schemas + DI deps + 4 routes + router wiring

**Files:**
- Create: `app/api/v1/me_ratings/__init__.py` (empty)
- Create: `app/api/v1/me_ratings/schemas.py`
- Create: `app/api/v1/me_ratings/deps.py`
- Create: `app/api/v1/me_ratings/routes.py`
- Modify: `app/api/v1/public_resources/routes.py` (add 1 new public ratings list route)
- Modify: `app/api/v1/router.py` (include `me_ratings_router`)

- [ ] **Step 1: Create `app/api/v1/me_ratings/schemas.py`**

```python
from __future__ import annotations
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.use_cases.ratings.dtos import (
    PublicRatingDto, PublicRatingListDto, RatingDto, RatingListDto,
)


class CreateRatingBody(BaseModel):
    score: int
    comment: str | None = None


class UpdateRatingBody(BaseModel):
    """Both fields required: score must be present, comment is null|string.
    PATCH semantics here are PUT-like (whole-document replace of the two
    customer-mutable fields). See plan 09 design §3.4."""
    score: int
    comment: str | None = None


class RatingResponse(BaseModel):
    id: UUID
    booking_id: UUID
    resource_id: UUID
    customer_id: UUID
    score: int
    comment: str | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_dto(cls, dto: RatingDto) -> "RatingResponse":
        return cls(
            id=dto.id, booking_id=dto.booking_id,
            resource_id=dto.resource_id, customer_id=dto.customer_id,
            score=dto.score, comment=dto.comment,
            created_at=dto.created_at, updated_at=dto.updated_at,
        )


class RatingListResponse(BaseModel):
    items: list[RatingResponse]
    page: int
    page_size: int

    @classmethod
    def from_dto(cls, dto: RatingListDto) -> "RatingListResponse":
        return cls(
            items=[RatingResponse.from_dto(r) for r in dto.items],
            page=dto.page, page_size=dto.page_size,
        )


class PublicRatingResponse(BaseModel):
    score: int
    comment: str
    created_at: datetime

    @classmethod
    def from_dto(cls, dto: PublicRatingDto) -> "PublicRatingResponse":
        return cls(
            score=dto.score, comment=dto.comment,
            created_at=dto.created_at,
        )


class PublicRatingListResponse(BaseModel):
    items: list[PublicRatingResponse]
    page: int
    page_size: int

    @classmethod
    def from_dto(cls, dto: PublicRatingListDto) -> "PublicRatingListResponse":
        return cls(
            items=[PublicRatingResponse.from_dto(r) for r in dto.items],
            page=dto.page, page_size=dto.page_size,
        )
```

- [ ] **Step 2: Create `app/api/v1/me_ratings/deps.py`**

```python
from __future__ import annotations
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.session import get_session
from app.infrastructure.repositories.booking_repository import (
    SQLAlchemyBookingRepository,
)
from app.infrastructure.repositories.rating_repository import (
    SQLAlchemyRatingRepository,
)
from app.infrastructure.repositories.resource_repository import (
    SQLAlchemyResourceRepository,
)
from app.use_cases.ratings.commands.create_rating import CreateRatingHandler
from app.use_cases.ratings.commands.update_rating import UpdateRatingHandler
from app.use_cases.ratings.queries.list_my_ratings import ListMyRatingsHandler
from app.use_cases.ratings.queries.list_public_ratings import (
    ListPublicRatingsForResourceHandler,
)


async def get_create_rating_handler(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CreateRatingHandler:
    return CreateRatingHandler(
        ratings=SQLAlchemyRatingRepository(session),
        bookings=SQLAlchemyBookingRepository(session),
    )


async def get_update_rating_handler(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> UpdateRatingHandler:
    return UpdateRatingHandler(
        ratings=SQLAlchemyRatingRepository(session),
    )


async def get_list_my_ratings_handler(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ListMyRatingsHandler:
    return ListMyRatingsHandler(
        ratings=SQLAlchemyRatingRepository(session),
    )


async def get_list_public_ratings_handler(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ListPublicRatingsForResourceHandler:
    return ListPublicRatingsForResourceHandler(
        ratings=SQLAlchemyRatingRepository(session),
        resources=SQLAlchemyResourceRepository(session),
    )
```

- [ ] **Step 3: Create `app/api/v1/me_ratings/routes.py`**

The customer-facing POST/PATCH/GET endpoints are keyed by `booking_id` (per spec §7.3 + §3.6). Both `CreateRatingCommand` and `UpdateRatingCommand` take `booking_id` as the primary identifier — handlers do the booking↔rating resolution internally — so the route layer is a simple thin pass-through.

```python
from __future__ import annotations
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import CurrentUser
from app.api.error_handler import unwrap
from app.api.v1.me_ratings.deps import (
    get_create_rating_handler,
    get_list_my_ratings_handler,
    get_update_rating_handler,
)
from app.api.v1.me_ratings.schemas import (
    CreateRatingBody,
    RatingListResponse,
    RatingResponse,
    UpdateRatingBody,
)
from app.use_cases.ratings.commands.create_rating import (
    CreateRatingCommand, CreateRatingHandler,
)
from app.use_cases.ratings.commands.update_rating import (
    UpdateRatingCommand, UpdateRatingHandler,
)
from app.use_cases.ratings.queries.list_my_ratings import (
    ListMyRatingsHandler, ListMyRatingsQuery,
)


router = APIRouter(prefix="/v1/me", tags=["me:ratings"])


@router.post(
    "/bookings/{booking_id}/rating",
    response_model=RatingResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_rating(
    booking_id: UUID,
    body: CreateRatingBody,
    user: CurrentUser,
    handler: Annotated[
        CreateRatingHandler, Depends(get_create_rating_handler),
    ],
):
    dto = unwrap(await handler.handle(CreateRatingCommand(
        actor_id=user.user_id,
        booking_id=booking_id,
        score=body.score,
        comment=body.comment,
    )))
    return RatingResponse.from_dto(dto)


@router.patch(
    "/bookings/{booking_id}/rating",
    response_model=RatingResponse,
)
async def update_rating(
    booking_id: UUID,
    body: UpdateRatingBody,
    user: CurrentUser,
    handler: Annotated[
        UpdateRatingHandler, Depends(get_update_rating_handler),
    ],
):
    # Handler resolves rating from booking_id internally — the route stays
    # booking-keyed (per spec §7.3), handler does the lookup + ownership +
    # edit-window check in one place.
    dto = unwrap(await handler.handle(UpdateRatingCommand(
        actor_id=user.user_id,
        booking_id=booking_id,
        score=body.score,
        comment=body.comment,
    )))
    return RatingResponse.from_dto(dto)


@router.get("/ratings", response_model=RatingListResponse)
async def list_my_ratings(
    user: CurrentUser,
    handler: Annotated[
        ListMyRatingsHandler, Depends(get_list_my_ratings_handler),
    ],
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
):
    dto = unwrap(await handler.handle(ListMyRatingsQuery(
        actor_id=user.user_id, page=page, page_size=page_size,
    )))
    return RatingListResponse.from_dto(dto)
```

Note on the inline `unwrap(Result.failure(...))` pattern: `unwrap` raises `HTTPException` from a failed `Result`, so the import + call short-circuits the request. If the project pattern is to `raise HTTPException` directly, adapt. Read `app/api/error_handler.py` to confirm `unwrap`'s actual signature.

- [ ] **Step 4: Add the public ratings route to `app/api/v1/public_resources/routes.py`**

Append imports as needed:

```python
from app.api.v1.me_ratings.deps import get_list_public_ratings_handler
from app.api.v1.me_ratings.schemas import PublicRatingListResponse
from app.use_cases.ratings.queries.list_public_ratings import (
    ListPublicRatingsForResourceHandler,
    ListPublicRatingsForResourceQuery,
)
```

Append the new route at the end of the file:

```python
@router.get(
    "/owners/{owner_slug}/resources/{resource_slug}/ratings",
    response_model=PublicRatingListResponse,
)
async def list_public_ratings(
    owner_slug: str,
    resource_slug: str,
    handler: Annotated[
        ListPublicRatingsForResourceHandler,
        Depends(get_list_public_ratings_handler),
    ],
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
):
    dto = unwrap(await handler.handle(ListPublicRatingsForResourceQuery(
        owner_slug=owner_slug, resource_slug=resource_slug,
        page=page, page_size=page_size,
    )))
    return PublicRatingListResponse.from_dto(dto)
```

- [ ] **Step 5: Wire `me_ratings_router` into `app/api/v1/router.py`**

Add the import alphabetically:

```python
from app.api.v1.me_ratings.routes import router as me_ratings_router
```

Add the include alongside existing includes:

```python
api_router.include_router(me_ratings_router)
```

(Adapt `api_router` → actual variable name.)

- [ ] **Step 6: Smoke-boot**

Run:
```
.venv/bin/python -c "
from app.main import app
unique = sorted({r.path for r in app.routes})
ratings_paths = [p for p in unique if 'rating' in p.lower()]
print('total unique paths:', len(unique))
print('rating-related paths:')
for p in ratings_paths:
    print(' ', p)
"
```

Expected: 4 rating-related paths printed, including:
```
/v1/me/bookings/{booking_id}/rating
/v1/me/ratings
/v1/owners/{owner_slug}/resources/{resource_slug}/ratings
```

(POST + PATCH on the same path counts as one unique path from FastAPI's perspective when listing `r.path` — verify by inspecting if the count is 3 unique paths but 4 endpoints.)

- [ ] **Step 7: Run full unit + integration**

Run: `.venv/bin/pytest tests/unit/ tests/integration/ -q`
Expected: green.

- [ ] **Step 8: Commit**

```bash
git add app/api/v1/me_ratings/ \
        app/api/v1/public_resources/routes.py \
        app/api/v1/router.py
git commit -m "$(cat <<'EOF'
feat(ratings): API schemas + 4 endpoints + router wiring

Plan 09 task 13. Three customer endpoints (POST + PATCH on
/me/bookings/{id}/rating, GET /me/ratings) + one public endpoint
(GET /owners/{owner_slug}/resources/{resource_slug}/ratings).
Both POST and PATCH commands take booking_id; handlers resolve
to the rating internally. Public response uses PublicRatingResponse
which omits customer_id and booking_id.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 14: E2E happy path + canonical spec refresh

**Files:**
- Create: `tests/e2e/ratings/__init__.py` (empty)
- Create: `tests/e2e/ratings/test_ratings_happy_path.py`
- Modify: `docs/superpowers/specs/2026-04-25-venue-backend-design.md`

- [ ] **Step 1: Write the e2e tests**

Use Plan 08's e2e fixture pattern (`client`, `customer_token`, `admin_token`). The happy path needs an APPROVED booking with an ended slot — but the API rejects bookings with past slot_start_at. Use the same direct-DB-poke trick Plan 08 task 30 used in `test_cron_expires_past_pendings`.

`tests/e2e/ratings/test_ratings_happy_path.py`:

```python
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from urllib.parse import quote
from uuid import UUID, uuid4

import pytest

from app.domain.bookings.booking import Booking
from app.domain.bookings.booking_status import BookingStatus
from app.domain.shared.value_objects.date_time_range import DateTimeRange
from app.domain.shared.value_objects.money import Money
from app.infrastructure.repositories.booking_repository import (
    SQLAlchemyBookingRepository,
)
# Reuse the helper from Plan 08 e2e:
from tests.e2e.bookings.test_happy_path import (
    _register_owner_with_resource,
)


pytestmark = pytest.mark.asyncio


def _q(dt: datetime) -> str:
    """URL-encode datetime for query params (Plan 08 task 31 fix)."""
    return quote(dt.isoformat(), safe="")


async def _seed_approved_ended_booking(
    db_session, *, resource_id: str, customer_id: UUID,
) -> UUID:
    """Insert an APPROVED booking whose slot already ended (bypasses the
    request-API's future-only check). Returns the booking.id."""
    now = datetime.now(timezone.utc)
    end = now - timedelta(hours=1)
    start = end - timedelta(hours=1)
    sr = DateTimeRange.create(start_at=start, end_at=end).value
    b = Booking.create_pending(
        resource_id=UUID(resource_id), customer_id=customer_id,
        slot_range=sr, total_price_cents=Money.create(8000).value,
        customer_note=None, now=start - timedelta(days=1),
    )
    b.approve(actor_id=uuid4(), now=start - timedelta(days=1))
    repo = SQLAlchemyBookingRepository(db_session)
    await repo.add(b)
    await db_session.commit()
    return b.id


async def test_happy_path_rate_appears_in_listings(
    client, admin_token, customer_token, db_session,
):
    owner_token, owner_id, resource_id = await _register_owner_with_resource(
        client, admin_token,
    )
    me_resp = await client.get(
        "/v1/me", headers={"Authorization": f"Bearer {customer_token}"},
    )
    customer_id = UUID(me_resp.json()["id"])
    booking_id = await _seed_approved_ended_booking(
        db_session, resource_id=resource_id, customer_id=customer_id,
    )

    # 1. Customer creates a rating.
    create = await client.post(
        f"/v1/me/bookings/{booking_id}/rating",
        headers={"Authorization": f"Bearer {customer_token}"},
        json={"score": 5, "comment": "ótimo lugar"},
    )
    assert create.status_code == 201, create.text
    body = create.json()
    assert body["score"] == 5
    assert body["comment"] == "ótimo lugar"

    # 2. Customer's /me/ratings includes it.
    mine = await client.get(
        "/v1/me/ratings",
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert mine.status_code == 200
    items = mine.json()["items"]
    assert any(it["score"] == 5 and it["comment"] == "ótimo lugar" for it in items)

    # 3. Public ratings listing for the resource includes it.
    # First fetch the public resource detail to get the slugs:
    listing = await client.get("/v1/resources")
    target = next(
        (i for i in listing.json()["items"] if i["id"] == resource_id),
        None,
    )
    assert target is not None
    owner_slug = target["owner_slug"]
    resource_slug = target["slug"]

    pub = await client.get(
        f"/v1/owners/{owner_slug}/resources/{resource_slug}/ratings",
    )
    assert pub.status_code == 200
    pub_items = pub.json()["items"]
    assert len(pub_items) == 1
    assert pub_items[0]["score"] == 5
    assert pub_items[0]["comment"] == "ótimo lugar"
    # Privacy: public response must NOT carry customer_id or booking_id.
    assert "customer_id" not in pub_items[0]
    assert "booking_id" not in pub_items[0]

    # 4. Public resource list reflects rating_avg + rating_count.
    listing_after = await client.get("/v1/resources")
    target_after = next(
        (i for i in listing_after.json()["items"] if i["id"] == resource_id),
        None,
    )
    assert target_after is not None
    assert target_after["rating_count"] == 1
    # rating_avg may be float or string depending on Pydantic Decimal handling.
    assert str(target_after["rating_avg"]) == "5.0"

    # 5. Customer updates the rating.
    upd = await client.patch(
        f"/v1/me/bookings/{booking_id}/rating",
        headers={"Authorization": f"Bearer {customer_token}"},
        json={"score": 4, "comment": "bom"},
    )
    assert upd.status_code == 200
    assert upd.json()["score"] == 4

    # 6. Public list reflects update.
    pub2 = await client.get(
        f"/v1/owners/{owner_slug}/resources/{resource_slug}/ratings",
    )
    assert pub2.json()["items"][0]["score"] == 4


async def test_cannot_rate_pending_booking(
    client, admin_token, customer_token, db_session,
):
    """Booking still PENDING → 422 BookingNotEligibleForRating."""
    owner_token, _, resource_id = await _register_owner_with_resource(
        client, admin_token,
    )
    me_resp = await client.get(
        "/v1/me", headers={"Authorization": f"Bearer {customer_token}"},
    )
    customer_id = UUID(me_resp.json()["id"])
    # Insert PENDING booking with past end_at directly.
    now = datetime.now(timezone.utc)
    end = now - timedelta(hours=1)
    start = end - timedelta(hours=1)
    sr = DateTimeRange.create(start_at=start, end_at=end).value
    b = Booking.create_pending(
        resource_id=UUID(resource_id), customer_id=customer_id,
        slot_range=sr, total_price_cents=Money.create(8000).value,
        customer_note=None, now=start - timedelta(days=1),
    )
    repo = SQLAlchemyBookingRepository(db_session)
    await repo.add(b)
    await db_session.commit()

    r = await client.post(
        f"/v1/me/bookings/{b.id}/rating",
        headers={"Authorization": f"Bearer {customer_token}"},
        json={"score": 5},
    )
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "BookingNotEligibleForRating"


async def test_cannot_rate_someone_elses_booking(
    client, admin_token, customer_token, db_session,
):
    owner_token, _, resource_id = await _register_owner_with_resource(
        client, admin_token,
    )
    # Seed booking under a DIFFERENT customer (random uuid).
    booking_id = await _seed_approved_ended_booking(
        db_session, resource_id=resource_id, customer_id=uuid4(),
    )
    r = await client.post(
        f"/v1/me/bookings/{booking_id}/rating",
        headers={"Authorization": f"Bearer {customer_token}"},
        json={"score": 5},
    )
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "BookingNotEligibleForRating"


async def test_double_rate_returns_409(
    client, admin_token, customer_token, db_session,
):
    owner_token, _, resource_id = await _register_owner_with_resource(
        client, admin_token,
    )
    me_resp = await client.get(
        "/v1/me", headers={"Authorization": f"Bearer {customer_token}"},
    )
    customer_id = UUID(me_resp.json()["id"])
    booking_id = await _seed_approved_ended_booking(
        db_session, resource_id=resource_id, customer_id=customer_id,
    )

    first = await client.post(
        f"/v1/me/bookings/{booking_id}/rating",
        headers={"Authorization": f"Bearer {customer_token}"},
        json={"score": 5},
    )
    assert first.status_code == 201
    second = await client.post(
        f"/v1/me/bookings/{booking_id}/rating",
        headers={"Authorization": f"Bearer {customer_token}"},
        json={"score": 4},
    )
    assert second.status_code == 409
    assert second.json()["detail"]["code"] == "RatingAlreadyExists"
```

- [ ] **Step 2: Run the e2e tests**

Run: `.venv/bin/pytest tests/e2e/ratings/ -v`
Expected: 4 PASSED.

- [ ] **Step 3: Run full suite**

Run: `.venv/bin/pytest -q`
Expected: green; total ~600+ tests.

- [ ] **Step 4: Refresh the canonical spec**

Edit `docs/superpowers/specs/2026-04-25-venue-backend-design.md`:

**§3 #20** — drop entirely. The whole row about admin moderation goes away. Also drop the relevant decision narrative if mentioned in §3 prose.

**§4.2 — booking + rating handler rows.** Drop the `HideRatingHandler` row from the table.

**§5.7 — Rating aggregate.** Drop `is_hidden` and `hidden_reason` from the field diagram. Drop the moderation invariants from the bullet list. Drop the `WHERE is_hidden = FALSE` clause from the aggregation SQL snippet. Append a "Plan 09 deliberate cuts" callout:

```markdown
**Plan 09 deliberate cuts (see `docs/superpowers/specs/2026-04-28-plan-09-ratings-design.md`):**
- Admin moderation removed from MVP — `is_hidden`, `hidden_reason`, `HideRatingHandler`, and the three `/admin/ratings` endpoints are deferred. Reintroducible as one-column Alembic + filter clause + admin endpoint pair.
- Rating survives owner-side post-rating cancellation — owner-cancelling an APPROVED booking after the customer has rated leaves the rating intact (audit-honest, no cascade).
- Owner per-resource ratings list (`GET /me/resources/{id}/ratings`) dropped from MVP — owners see the rolled-up `rating_avg`/`rating_count` on resource listings, no per-rating drill-down.
```

**§7.1** — change `GET /resources/{slug}/ratings` to `GET /owners/{owner_slug}/resources/{resource_slug}/ratings` (matches the existing public resource detail prefix). Note that the agenda path remains `/resources/{owner_slug}/{resource_slug}/agenda` (Plan 08 — alignment tracked in polish backlog).

**§7.4** — drop the `GET /me/resources/{id}/ratings` route (out of MVP).

**§7.5** — drop the entire "Ratings (moderation)" block (3 endpoints).

**§8 — Plan 09 description.** Replace whatever's there with what actually shipped:

```markdown
9. **Plan 09 — Ratings.** `Rating` aggregate (per-booking, score 1-5 via `RatingScore` VO, optional `ShortDescription` comment, no moderation in MVP) + `IRatingRepository` (7 methods including batch `get_aggregates_for_resources`). 4 handlers: `CreateRatingHandler` (eligibility gate: APPROVED booking, slot ended, customer match, ≤90d window), `UpdateRatingHandler` (7d edit window), `ListMyRatingsHandler`, `ListPublicRatingsForResourceHandler` (comment-only filter). `Resource` GETs gain `rating_avg`/`rating_count` aggregates merged via a single batch query per page (no N+1). Owner page (`GET /owners/{slug}`) computes a count-weighted average. 4 new endpoints (3 customer + 1 public). Concurrency: DB UNIQUE on `booking_id` is the sole race protection. No moderation surface — see plan-09 design §1.
```

- [ ] **Step 5: Sanity check the refresh**

Run:
```
.venv/bin/python -c "
from pathlib import Path
text = Path('docs/superpowers/specs/2026-04-25-venue-backend-design.md').read_text()
hidden_lines = [l for l in text.splitlines() if 'is_hidden' in l or 'hidden_reason' in l]
print('hidden lines:', len(hidden_lines))
for l in hidden_lines:
    print(' ', l[:140])
hide_handler_lines = [l for l in text.splitlines() if 'HideRatingHandler' in l]
print('HideRatingHandler lines:', len(hide_handler_lines))
"
```

Expected: any remaining `is_hidden`/`hidden_reason` is in the "deliberate cuts" callout; `HideRatingHandler` lines = 0.

- [ ] **Step 6: Run pytest to ensure no doc-driven test broke**

Run: `.venv/bin/pytest -q`
Expected: green.

- [ ] **Step 7: Commit**

```bash
git add tests/e2e/ratings/ \
        docs/superpowers/specs/2026-04-25-venue-backend-design.md
git commit -m "$(cat <<'EOF'
test(e2e) + docs(spec): Plan 09 ratings happy-path + canonical refresh

Plan 09 task 14. Four e2e tests cover: (1) full happy path (book →
seed approved+ended via direct DB poke → rate → /me/ratings reflects
→ public ratings list reflects → resource list rating_avg/count
reflects → update → public list reflects update); (2) PENDING
booking ineligible; (3) other customer's booking ineligible;
(4) duplicate rate returns 409.

Canonical spec refresh: drop §3 #20 (moderation), drop
HideRatingHandler from §4.2, simplify §5.7 (drop is_hidden/
hidden_reason fields + invariants + filter clause; add Plan 09
deliberate cuts callout), §7.1 path moved to owners-prefixed
two-slug shape, §7.4 drops /me/resources/{id}/ratings, §7.5
drops the entire admin moderation block, §8 refreshed with what
actually shipped.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Final verification

- [ ] **Step 1: Run the entire test suite**

Run: `.venv/bin/pytest -q`
Expected: all green. Total count should be ~600+ (Plan 08 closed at 576; Plan 09 adds ~22 unit + 5 integration + 4 e2e ≈ 31 new tests).

- [ ] **Step 2: Smoke-boot the FastAPI app**

Run:
```
.venv/bin/python -c "
from app.main import app
unique = sorted({r.path for r in app.routes})
print('total unique paths:', len(unique))
ratings_paths = [p for p in unique if 'rating' in p.lower()]
print('rating paths:')
for p in ratings_paths:
    print(' ', p)
"
```

Expected: 3 unique paths printed (POST + PATCH share a path):
```
/v1/me/bookings/{booking_id}/rating
/v1/me/ratings
/v1/owners/{owner_slug}/resources/{resource_slug}/ratings
```

- [ ] **Step 3: Confirm moderation is fully absent from production code**

Run: `grep -rn "is_hidden\|hidden_reason\|HideRatingHandler" app/ tests/ 2>&1 | grep -v __pycache__`
Expected: no matches in production code (`app/`); some doc/spec references in deferred callouts are acceptable.

---

End of plan. Refer to the design doc (`docs/superpowers/specs/2026-04-28-plan-09-ratings-design.md`) for any judgment calls not captured here. If a Plan 06/07/08 pattern doesn't match a hint in this plan (file paths, fixture names, accessor shapes), trust the existing code — Plans 06-08 absorbed many adaptations during execution and the plan templates may have drifted.
