# Plan 06 — Resource Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the `Resource` aggregate (per-owner slug, weekly schedule with multi-window per day, pricing rules with strict no-overlap + alignment + containment, custom attributes), the owner-scoped command/query handlers, the public reads with `is_owner_operational` gate, JSONB persistence, the `User.public_slug` extension that makes `/owners/{owner_slug}` URLs work, and folds in Plan 05 follow-ups #5 (raw-pt-BR codes → stable codes in `RegisterUserHandler`) and #6 (canonical spec §5.5 refresh).

**Architecture:** Aggregate in `app/domain/resources/`. Three composite VOs (`WeeklySchedule`, `PricingRule`, `CustomAttribute`) + shared `Weekday` enum. Cross-rule validation (pricing overlap / alignment / containment) lives on `Resource` since it needs `slot_duration_minutes` and `operating_hours`. Storage: one `resources` row per resource with `operating_hours`, `pricing_rules`, `custom_attributes`, `base_attributes` as JSONB. Handlers always reload via `get_by_id` + check `resource.owner_id == cmd.actor_id` + `not res.is_deleted()`; mismatch returns `ResourceNotFound` (404, no leakage). `CreateResourceHandler` injects `IResourceTypeRepository` to call `rt.validate_attributes(...)` and merges its errors into the same envelope as `Resource.create`. Public reads inject `ISubscriptionRepository` + `IUserRepository` and apply the `is_operational(owner) = sub.is_operational() AND user.is_active` gate (Plan 05 §7 pattern). `User.public_slug` is added to accounts; `RegisterUserHandler` generates it for OWNER on registration with linear suffix collision-resolution (5 retries, then 409).

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2 async, Alembic, Pydantic, pytest. No new dependencies (only stdlib `unicodedata` for slugify).

**Reference spec:** `docs/superpowers/specs/2026-04-26-plan-06-resource-design.md`.

**Conventions reminders:**
- Always invoke Python via venv: `.venv/bin/python` or `.venv/bin/pytest`. Never use the global Python.
- Domain code never imports from `infrastructure` or `use_cases`.
- After each task, commit with a focused message ending in `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>`.
- TDD: write failing test, run to confirm RED, write minimal impl, run to confirm GREEN, commit.
- Composite VOs that aggregate over multiple sub-VOs use `Result.failure_many(errors)`. Single-rule VOs use `Result.failure(code)`.
- Aggregate roots emit `failure_many` for `create` (multi-field aggregation) and `Result[None]` for mutators with state-transition rules; mutators without rules return `None`.

---

## File structure (created or modified over the plan)

```
app/domain/shared/
└── weekday.py                                    NEW — Weekday enum

app/domain/resources/
├── __init__.py                                   NEW
├── weekly_schedule.py                            NEW — WeeklySchedule composite VO
├── pricing_rule.py                               NEW — PricingRule composite VO
├── custom_attribute.py                           NEW — CustomAttribute composite VO
├── resource.py                                   NEW — Resource aggregate root
└── repository.py                                 NEW — IResourceRepository Protocol

app/domain/accounts/
├── user.py                                       MODIFIED — adds public_slug field + invariants
└── repository.py                                 MODIFIED — adds get_by_public_slug

app/domain/subscriptions/
└── repository.py                                 MODIFIED — adds list_by_owner_ids batch helper

app/use_cases/resources/
├── __init__.py                                   NEW
├── dtos.py                                       NEW — ResourceDto, WeeklyScheduleDto, etc.
├── _common.py                                    NEW — load_owned_resource helper
├── commands/
│   ├── __init__.py                               NEW
│   ├── create_resource.py                        NEW
│   ├── update_resource_metadata.py               NEW
│   ├── replace_operating_hours.py                NEW
│   ├── replace_pricing_rules.py                  NEW
│   ├── replace_base_attributes.py                NEW
│   ├── replace_custom_attributes.py              NEW
│   ├── set_base_price.py                         NEW
│   ├── set_cancellation_cutoff.py                NEW
│   ├── set_slot_duration.py                      NEW
│   ├── publish_resource.py                       NEW (publish + unpublish)
│   └── soft_delete_resource.py                   NEW
└── queries/
    ├── __init__.py                               NEW
    ├── get_my_resource.py                        NEW
    ├── list_my_resources.py                      NEW
    ├── get_public_resource.py                    NEW
    └── list_public_resources.py                  NEW

app/use_cases/accounts/
├── commands/register_user.py                     MODIFIED — generates public_slug; uses stable codes
└── queries/get_owner_public_page.py              NEW — cross-feature handler (lives in accounts)

app/infrastructure/db/mappings/
├── user.py                                       MODIFIED — adds public_slug column
└── resource.py                                   NEW — ResourceModel + JSONB columns

app/infrastructure/repositories/
├── user_repository.py                            MODIFIED — adds get_by_public_slug + list_by_ids
├── owner_subscription_repository.py              MODIFIED — adds list_by_owner_ids
└── resource_repository.py                        NEW — SQLAlchemyResourceRepository

app/api/v1/
├── me_resources/                                 NEW package (deps, schemas, routes)
├── public_resources/                             NEW package (deps, schemas, routes)
└── router.py                                     MODIFIED — include new routers

app/api/error_codes.py                            MODIFIED — adds Plan 06 + follow-up codes
app/migrations/env.py                             MODIFIED — registers ResourceModel
app/migrations/versions/<ts>_users_add_public_slug.py     NEW
app/migrations/versions/<ts>_resources_table.py            NEW

tests/unit/domain/shared/test_weekday.py          NEW
tests/unit/domain/resources/                      NEW (test_weekly_schedule, test_pricing_rule, test_custom_attribute, test_resource)
tests/unit/use_cases/resources/                   NEW (commands + queries + fakes)
tests/unit/use_cases/accounts/                    NEW (test_get_owner_public_page; modified test_register_user)
tests/unit/architecture/test_error_code_coverage.py        MODIFIED — extends allowlist
tests/integration/resources/test_resource_repository.py    NEW
tests/integration/accounts/test_user_repository_public_slug.py  NEW
tests/e2e/resources/                              NEW (test_owner_lifecycle, test_inactive_owner_filter, test_create_resource_validation_envelope)

docs/superpowers/specs/2026-04-25-venue-backend-design.md  MODIFIED — Plan 05 follow-up #6 (§5.5 refresh)
```

---

## Task 1: `Weekday` enum

**Files:**
- Create: `app/domain/shared/weekday.py`
- Test: `tests/unit/domain/shared/test_weekday.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/domain/shared/test_weekday.py`:

```python
from __future__ import annotations
from app.domain.shared.weekday import Weekday


def test_weekday_values():
    assert Weekday.MONDAY.value == "MONDAY"
    assert Weekday.TUESDAY.value == "TUESDAY"
    assert Weekday.WEDNESDAY.value == "WEDNESDAY"
    assert Weekday.THURSDAY.value == "THURSDAY"
    assert Weekday.FRIDAY.value == "FRIDAY"
    assert Weekday.SATURDAY.value == "SATURDAY"
    assert Weekday.SUNDAY.value == "SUNDAY"


def test_weekday_is_str_enum():
    # str enum so JSON serialization is the value directly.
    assert Weekday.MONDAY == "MONDAY"
    assert isinstance(Weekday.MONDAY, str)


def test_weekday_count():
    assert len(list(Weekday)) == 7
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/unit/domain/shared/test_weekday.py -v`
Expected: `ModuleNotFoundError: No module named 'app.domain.shared.weekday'`.

- [ ] **Step 3: Write the implementation**

Create `app/domain/shared/weekday.py`:

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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/unit/domain/shared/test_weekday.py -v`
Expected: 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add app/domain/shared/weekday.py tests/unit/domain/shared/test_weekday.py
git commit -m "$(cat <<'EOF'
feat(shared): Weekday str-Enum for resources feature

Plain Python enum, not a Value Object. Used by WeeklySchedule and
PricingRule. Living in app/domain/shared/ keeps it accessible without
forcing a cross-feature import path.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: `WeeklySchedule` composite VO

**Files:**
- Create: `app/domain/resources/__init__.py` (empty)
- Create: `app/domain/resources/weekly_schedule.py`
- Create: `tests/unit/domain/resources/__init__.py` (empty)
- Test: `tests/unit/domain/resources/test_weekly_schedule.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/domain/resources/__init__.py` (empty file).

Create `tests/unit/domain/resources/test_weekly_schedule.py`:

```python
from __future__ import annotations
from datetime import time

from app.domain.resources.weekly_schedule import WeeklySchedule
from app.domain.shared.value_objects.time_window import TimeWindow
from app.domain.shared.weekday import Weekday


def _w(start_h: int, start_m: int, end_h: int, end_m: int) -> TimeWindow:
    r = TimeWindow.create(time(start_h, start_m), time(end_h, end_m))
    assert r.is_success
    return r.value


# --- happy paths ---

def test_create_empty_schedule():
    r = WeeklySchedule.create(slot_duration_minutes=60, days={})
    assert r.is_success
    sched = r.value
    assert sched.monday == ()
    assert sched.sunday == ()


def test_create_single_window_per_day():
    r = WeeklySchedule.create(
        slot_duration_minutes=60,
        days={
            Weekday.MONDAY: [_w(8, 0, 22, 0)],
            Weekday.SATURDAY: [_w(9, 0, 23, 0)],
        },
    )
    assert r.is_success
    sched = r.value
    assert len(sched.monday) == 1
    assert sched.monday[0].start == time(8, 0)
    assert sched.tuesday == ()
    assert len(sched.saturday) == 1


def test_create_multiple_windows_per_day():
    r = WeeklySchedule.create(
        slot_duration_minutes=60,
        days={
            Weekday.MONDAY: [_w(8, 0, 12, 0), _w(14, 0, 22, 0)],
        },
    )
    assert r.is_success
    sched = r.value
    assert len(sched.monday) == 2


def test_for_weekday_returns_windows():
    r = WeeklySchedule.create(
        slot_duration_minutes=60,
        days={Weekday.FRIDAY: [_w(18, 0, 23, 0)]},
    )
    sched = r.value
    assert sched.for_weekday(Weekday.FRIDAY) == (_w(18, 0, 23, 0),)
    assert sched.for_weekday(Weekday.MONDAY) == ()


# --- ordering / overlap / alignment ---

def test_create_rejects_unordered_windows():
    r = WeeklySchedule.create(
        slot_duration_minutes=60,
        days={
            Weekday.MONDAY: [_w(14, 0, 18, 0), _w(8, 0, 12, 0)],  # second starts before first
        },
    )
    assert r.is_failure
    assert r.details is not None
    codes = {(e.field, e.code) for e in r.details}
    assert ("days.monday[1]", WeeklySchedule.WINDOWS_NOT_ORDERED) in codes


def test_create_rejects_overlapping_windows():
    r = WeeklySchedule.create(
        slot_duration_minutes=60,
        days={
            Weekday.MONDAY: [_w(8, 0, 14, 0), _w(13, 0, 22, 0)],  # 13:00 inside 8-14
        },
    )
    assert r.is_failure
    codes = {(e.field, e.code) for e in r.details}
    assert ("days.monday[1]", WeeklySchedule.WINDOWS_OVERLAP) in codes


def test_create_rejects_misaligned_start():
    r = WeeklySchedule.create(
        slot_duration_minutes=60,
        days={Weekday.MONDAY: [_w(8, 30, 14, 0)]},  # 8:30 not aligned to 60min slots
    )
    assert r.is_failure
    codes = {(e.field, e.code) for e in r.details}
    assert ("days.monday[0]", WeeklySchedule.WINDOW_NOT_ALIGNED_TO_SLOT_GRID) in codes


def test_create_rejects_misaligned_duration():
    # 60-min slot, 8:00-13:30 = 330 minutes (not divisible by 60)
    r = WeeklySchedule.create(
        slot_duration_minutes=60,
        days={Weekday.MONDAY: [_w(8, 0, 13, 30)]},
    )
    assert r.is_failure
    codes = {(e.field, e.code) for e in r.details}
    assert ("days.monday[0]", WeeklySchedule.WINDOW_NOT_ALIGNED_TO_SLOT_GRID) in codes


def test_create_aggregates_errors_across_weekdays():
    r = WeeklySchedule.create(
        slot_duration_minutes=60,
        days={
            Weekday.MONDAY: [_w(8, 30, 14, 0)],   # misaligned
            Weekday.FRIDAY: [_w(18, 0, 22, 0), _w(20, 0, 23, 0)],  # overlap
        },
    )
    assert r.is_failure
    fields = {e.field for e in r.details}
    assert "days.monday[0]" in fields
    assert "days.friday[1]" in fields
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/unit/domain/resources/test_weekly_schedule.py -v`
Expected: `ModuleNotFoundError: No module named 'app.domain.resources'`.

- [ ] **Step 3: Write the implementation**

Create `app/domain/resources/__init__.py` (empty file).

Create `app/domain/resources/weekly_schedule.py`:

```python
from __future__ import annotations
from dataclasses import dataclass
from typing import Self

from app.domain.shared.field_error import FieldError
from app.domain.shared.result import Result
from app.domain.shared.value_object import BaseValueObject
from app.domain.shared.value_objects.time_window import TimeWindow
from app.domain.shared.weekday import Weekday


@dataclass(frozen=True, slots=True)
class WeeklySchedule(BaseValueObject):
    """Operating hours per weekday. 0..N TimeWindow per day; ordered, non-
    overlapping, slot-grid-aligned. Closed days are an empty tuple.

    Built via WeeklySchedule.create(slot_duration_minutes=..., days={...}). The
    factory takes a dict of Weekday → list[TimeWindow] for ergonomics; the
    storage shape is seven explicit tuple fields.
    """

    WINDOWS_NOT_ORDERED = "WeeklyScheduleWindowsNotOrdered"
    WINDOWS_OVERLAP = "WeeklyScheduleWindowsOverlap"
    WINDOW_NOT_ALIGNED_TO_SLOT_GRID = "WeeklyScheduleWindowNotAlignedToSlotGrid"

    monday: tuple[TimeWindow, ...] = ()
    tuesday: tuple[TimeWindow, ...] = ()
    wednesday: tuple[TimeWindow, ...] = ()
    thursday: tuple[TimeWindow, ...] = ()
    friday: tuple[TimeWindow, ...] = ()
    saturday: tuple[TimeWindow, ...] = ()
    sunday: tuple[TimeWindow, ...] = ()

    @classmethod
    def create(
        cls,
        *,
        slot_duration_minutes: int,
        days: dict[Weekday, list[TimeWindow]],
    ) -> Result[Self]:
        errors: list[FieldError] = []
        per_day: dict[Weekday, tuple[TimeWindow, ...]] = {}

        for wd in Weekday:
            windows = days.get(wd, [])
            field_prefix = f"days.{wd.value.lower()}"

            for idx, w in enumerate(windows):
                # Alignment check (independent per window).
                start_minutes = w.start.hour * 60 + w.start.minute
                duration = w.duration_minutes()
                if (start_minutes % slot_duration_minutes) != 0 or (duration % slot_duration_minutes) != 0:
                    errors.append(FieldError(
                        code=cls.WINDOW_NOT_ALIGNED_TO_SLOT_GRID,
                        field=f"{field_prefix}[{idx}]",
                    ))

                # Ordering + overlap (compare with previous window).
                if idx > 0:
                    prev = windows[idx - 1]
                    if w.start < prev.start:
                        errors.append(FieldError(
                            code=cls.WINDOWS_NOT_ORDERED,
                            field=f"{field_prefix}[{idx}]",
                        ))
                    elif w.start < prev.end:
                        # prev.start <= w.start < prev.end → overlap
                        errors.append(FieldError(
                            code=cls.WINDOWS_OVERLAP,
                            field=f"{field_prefix}[{idx}]",
                        ))

            per_day[wd] = tuple(windows)

        if errors:
            return Result.failure_many(errors)

        return Result.success(cls(
            monday=per_day[Weekday.MONDAY],
            tuesday=per_day[Weekday.TUESDAY],
            wednesday=per_day[Weekday.WEDNESDAY],
            thursday=per_day[Weekday.THURSDAY],
            friday=per_day[Weekday.FRIDAY],
            saturday=per_day[Weekday.SATURDAY],
            sunday=per_day[Weekday.SUNDAY],
        ))

    def for_weekday(self, day: Weekday) -> tuple[TimeWindow, ...]:
        return getattr(self, day.value.lower())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/unit/domain/resources/test_weekly_schedule.py -v`
Expected: 8 PASS.

- [ ] **Step 5: Commit**

```bash
git add app/domain/resources/__init__.py app/domain/resources/weekly_schedule.py tests/unit/domain/resources/__init__.py tests/unit/domain/resources/test_weekly_schedule.py
git commit -m "$(cat <<'EOF'
feat(resources): WeeklySchedule composite VO

Seven tuple fields (one per weekday) of TimeWindow. Factory aggregates
ordering, overlap, and slot-grid alignment errors via failure_many,
prefixing field paths with days.<weekday>[<idx>].

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: `PricingRule` composite VO

**Files:**
- Create: `app/domain/resources/pricing_rule.py`
- Test: `tests/unit/domain/resources/test_pricing_rule.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/domain/resources/test_pricing_rule.py`:

```python
from __future__ import annotations
from datetime import time

from app.domain.resources.pricing_rule import PricingRule
from app.domain.shared.value_objects.money import Money
from app.domain.shared.value_objects.time_window import TimeWindow
from app.domain.shared.weekday import Weekday


def _money(cents: int) -> Money:
    r = Money.create(cents)
    assert r.is_success
    return r.value


def _window(start_h: int, end_h: int) -> TimeWindow:
    r = TimeWindow.create(time(start_h, 0), time(end_h, 0))
    assert r.is_success
    return r.value


def test_create_happy_path():
    r = PricingRule.create(
        weekdays=[Weekday.FRIDAY, Weekday.SATURDAY],
        window=_window(18, 23),
        price=_money(12000),
    )
    assert r.is_success
    rule = r.value
    assert rule.weekdays == frozenset({Weekday.FRIDAY, Weekday.SATURDAY})
    assert rule.window.start == time(18, 0)
    assert rule.price.cents == 12000


def test_create_rejects_empty_weekdays():
    r = PricingRule.create(
        weekdays=[],
        window=_window(18, 23),
        price=_money(12000),
    )
    assert r.is_failure
    assert r.error == PricingRule.EMPTY_WEEKDAYS


def test_equality_by_value():
    a = PricingRule.create(weekdays=[Weekday.MONDAY], window=_window(9, 17), price=_money(5000)).value
    b = PricingRule.create(weekdays=[Weekday.MONDAY], window=_window(9, 17), price=_money(5000)).value
    assert a == b
    assert hash(a) == hash(b)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/unit/domain/resources/test_pricing_rule.py -v`
Expected: `ModuleNotFoundError: No module named 'app.domain.resources.pricing_rule'`.

- [ ] **Step 3: Write the implementation**

Create `app/domain/resources/pricing_rule.py`:

```python
from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable, Self

from app.domain.shared.result import Result
from app.domain.shared.value_object import BaseValueObject
from app.domain.shared.value_objects.money import Money
from app.domain.shared.value_objects.time_window import TimeWindow
from app.domain.shared.weekday import Weekday


@dataclass(frozen=True, slots=True)
class PricingRule(BaseValueObject):
    """A price applied to slots matching a weekday set inside a time window.

    Cross-rule validation (overlap, alignment to slot grid, containment in
    operating hours) is done at the Resource aggregate level — it requires
    slot_duration_minutes and operating_hours that PricingRule alone does not
    have.
    """

    EMPTY_WEEKDAYS = "PricingRuleEmptyWeekdays"

    weekdays: frozenset[Weekday]
    window: TimeWindow
    price: Money

    @classmethod
    def create(
        cls,
        *,
        weekdays: Iterable[Weekday],
        window: TimeWindow,
        price: Money,
    ) -> Result[Self]:
        ws = frozenset(weekdays)
        if not ws:
            return Result.failure(cls.EMPTY_WEEKDAYS)
        return Result.success(cls(weekdays=ws, window=window, price=price))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/unit/domain/resources/test_pricing_rule.py -v`
Expected: 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add app/domain/resources/pricing_rule.py tests/unit/domain/resources/test_pricing_rule.py
git commit -m "$(cat <<'EOF'
feat(resources): PricingRule composite VO

frozenset of weekdays + TimeWindow + Money. Empty-weekdays is the only
rule the VO enforces alone; overlap, alignment, and containment depend
on the Resource's slot_duration and operating_hours and live there.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: `CustomAttribute` composite VO

**Files:**
- Create: `app/domain/resources/custom_attribute.py`
- Test: `tests/unit/domain/resources/test_custom_attribute.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/domain/resources/test_custom_attribute.py`:

```python
from __future__ import annotations

from app.domain.resources.custom_attribute import CustomAttribute
from app.domain.shared.value_objects.attribute_key import AttributeKey
from app.domain.shared.value_objects.short_description import ShortDescription
from app.domain.shared.value_objects.short_name import ShortName


def test_create_happy_path():
    r = CustomAttribute.create(key="wifi", label="Wi-Fi", value="Sim, gratuito")
    assert r.is_success
    attr = r.value
    assert attr.key.value == "wifi"
    assert attr.label.value == "Wi-Fi"
    assert attr.value.value == "Sim, gratuito"


def test_create_aggregates_field_errors():
    r = CustomAttribute.create(
        key="WIFI",       # uppercase forbidden by AttributeKey snake_case rule
        label="",          # empty short_name forbidden
        value="",          # ShortDescription allows empty — should NOT error
    )
    assert r.is_failure
    fields = {e.field for e in r.details}
    assert "key" in fields
    assert "label" in fields
    assert "value" not in fields  # empty description is allowed


def test_create_aggregates_all_three_fields():
    r = CustomAttribute.create(
        key="!!!invalid!!!",
        label="",
        value="X" * 600,   # exceeds ShortDescription max length
    )
    assert r.is_failure
    fields = {e.field for e in r.details}
    assert fields == {"key", "label", "value"}


def test_equality_by_value():
    a = CustomAttribute.create(key="wifi", label="Wi-Fi", value="ok").value
    b = CustomAttribute.create(key="wifi", label="Wi-Fi", value="ok").value
    assert a == b
    assert hash(a) == hash(b)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/unit/domain/resources/test_custom_attribute.py -v`
Expected: ModuleNotFoundError.

- [ ] **Step 3: Write the implementation**

Create `app/domain/resources/custom_attribute.py`:

```python
from __future__ import annotations
from dataclasses import dataclass
from typing import Self

from app.domain.shared.field_error import FieldError
from app.domain.shared.result import Result
from app.domain.shared.value_object import BaseValueObject
from app.domain.shared.value_objects.attribute_key import AttributeKey
from app.domain.shared.value_objects.short_description import ShortDescription
from app.domain.shared.value_objects.short_name import ShortName


@dataclass(frozen=True, slots=True)
class CustomAttribute(BaseValueObject):
    """Owner-defined freeform attribute on a Resource.

    Values are always strings (ShortDescription). Owners who want typed/
    filterable attributes request the admin to add them to
    ResourceType.attribute_schema (which becomes Resource.base_attributes).
    """

    key: AttributeKey
    label: ShortName
    value: ShortDescription

    @classmethod
    def create(cls, *, key: str, label: str, value: str) -> Result[Self]:
        errors: list[FieldError] = []

        key_r = AttributeKey.create(key)
        if key_r.is_failure:
            errors.append(FieldError(code=key_r.error, field="key"))

        label_r = ShortName.create(label)
        if label_r.is_failure:
            errors.append(FieldError(code=label_r.error, field="label"))

        value_r = ShortDescription.create(value)
        if value_r.is_failure:
            errors.append(FieldError(code=value_r.error, field="value"))

        if errors:
            return Result.failure_many(errors)

        return Result.success(cls(
            key=key_r.value,
            label=label_r.value,
            value=value_r.value,
        ))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/unit/domain/resources/test_custom_attribute.py -v`
Expected: 4 PASS.

- [ ] **Step 5: Commit**

```bash
git add app/domain/resources/custom_attribute.py tests/unit/domain/resources/test_custom_attribute.py
git commit -m "$(cat <<'EOF'
feat(resources): CustomAttribute composite VO

key + label + value triple, all string-typed VOs. Aggregates errors over
the three sub-VO factories via failure_many.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: `Resource` aggregate — happy path + scalar VOs

**Files:**
- Create: `app/domain/resources/resource.py`
- Test: `tests/unit/domain/resources/test_resource.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/domain/resources/test_resource.py`:

```python
from __future__ import annotations
from datetime import datetime, time, timezone
from uuid import uuid4

from app.domain.resources.custom_attribute import CustomAttribute
from app.domain.resources.pricing_rule import PricingRule
from app.domain.resources.resource import Resource
from app.domain.resources.weekly_schedule import WeeklySchedule
from app.domain.shared.value_objects.money import Money
from app.domain.shared.value_objects.time_window import TimeWindow
from app.domain.shared.weekday import Weekday


def _w(sh: int, eh: int) -> TimeWindow:
    return TimeWindow.create(time(sh, 0), time(eh, 0)).value


def _money(cents: int) -> Money:
    return Money.create(cents).value


def _ws(slot=60, days=None) -> WeeklySchedule:
    return WeeklySchedule.create(
        slot_duration_minutes=slot,
        days=days or {Weekday.MONDAY: [_w(8, 22)]},
    ).value


def _valid_kwargs(**overrides):
    base = dict(
        owner_id=uuid4(),
        resource_type_id=uuid4(),
        slug="arena-zona-leste",
        name="Arena Zona Leste",
        description="Campo society",
        city="São Paulo",
        region="SP",
        timezone="America/Sao_Paulo",
        slot_duration_minutes=60,
        operating_hours=_ws(),
        base_price_cents=8000,
        customer_cancellation_cutoff_hours=24,
        base_attributes={},
        pricing_rules=[],
        custom_attributes=[],
        is_published=False,
    )
    base.update(overrides)
    return base


# --- happy path ---

def test_create_happy_path():
    r = Resource.create(**_valid_kwargs())
    assert r.is_success
    res = r.value
    assert res.slug.value == "arena-zona-leste"
    assert res.name.value == "Arena Zona Leste"
    assert res.timezone.value == "America/Sao_Paulo"
    assert res.slot_duration_minutes.minutes == 60
    assert res.base_price_cents.cents == 8000
    assert res.is_published is False
    assert res.deleted_at is None
    assert res.pricing_rules == ()
    assert res.custom_attributes == ()


# --- aggregated scalar VO failures ---

def test_create_aggregates_scalar_vo_errors():
    r = Resource.create(**_valid_kwargs(
        slug="UPPER!!!",        # SlugInvalidFormat
        name="",                # NameCannotBeEmpty
        timezone="Mars/Olympus",  # IanaTimezoneUnknown
        base_price_cents=-100,   # MoneyCannotBeNegative
    ))
    assert r.is_failure
    fields = {e.field for e in r.details}
    assert "slug" in fields
    assert "name" in fields
    assert "timezone" in fields
    assert "base_price_cents" in fields
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/unit/domain/resources/test_resource.py -v`
Expected: ModuleNotFoundError.

- [ ] **Step 3: Write the implementation**

Create `app/domain/resources/resource.py`:

```python
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Self
from uuid import UUID

from app.domain.resources.custom_attribute import CustomAttribute
from app.domain.resources.pricing_rule import PricingRule
from app.domain.resources.weekly_schedule import WeeklySchedule
from app.domain.shared.entity import BaseEntity
from app.domain.shared.field_error import FieldError
from app.domain.shared.result import Result
from app.domain.shared.value_objects.cancellation_cutoff import CancellationCutoff
from app.domain.shared.value_objects.iana_timezone import IanaTimezone
from app.domain.shared.value_objects.money import Money
from app.domain.shared.value_objects.name import Name
from app.domain.shared.value_objects.short_description import ShortDescription
from app.domain.shared.value_objects.slot_duration import SlotDuration
from app.domain.shared.value_objects.slug import Slug


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(slots=True, kw_only=True)
class Resource(BaseEntity):
    """Owner-managed rentable resource.

    Cross-rule invariants on pricing_rules (overlap / alignment / containment)
    plus custom_attributes vs base_attributes disjointness are enforced in
    create() and the relevant mutators. base_attributes type validation
    against ResourceType.attribute_schema is the HANDLER's job (cross-feature).
    """

    PRICING_RULES_OVERLAP = "PricingRulesOverlap"
    PRICING_RULE_NOT_ALIGNED_TO_SLOT_GRID = "PricingRuleNotAlignedToSlotGrid"
    PRICING_RULE_OUTSIDE_OPERATING_HOURS = "PricingRuleOutsideOperatingHours"
    DUPLICATE_CUSTOM_ATTRIBUTE_KEY = "DuplicateCustomAttributeKey"
    CUSTOM_ATTRIBUTE_KEY_CONFLICTS_WITH_BASE = "CustomAttributeKeyConflictsWithBase"
    RESOURCE_ALREADY_DELETED = "ResourceAlreadyDeleted"
    DELETED_AT_NOT_TZ_AWARE = "ResourceDeletedAtNotTzAware"

    owner_id: UUID
    resource_type_id: UUID

    slug: Slug
    name: Name
    description: ShortDescription
    city: Name
    region: Name
    timezone: IanaTimezone
    slot_duration_minutes: SlotDuration
    operating_hours: WeeklySchedule
    base_price_cents: Money
    customer_cancellation_cutoff_hours: CancellationCutoff

    base_attributes: dict[str, Any] = field(default_factory=dict)

    is_published: bool = False
    deleted_at: datetime | None = None

    _pricing_rules: list[PricingRule] = field(default_factory=list, repr=False)
    _custom_attributes: list[CustomAttribute] = field(default_factory=list, repr=False)

    @classmethod
    def create(
        cls,
        *,
        owner_id: UUID,
        resource_type_id: UUID,
        slug: str,
        name: str,
        description: str,
        city: str,
        region: str,
        timezone: str,
        slot_duration_minutes: int,
        operating_hours: WeeklySchedule,
        base_price_cents: int,
        customer_cancellation_cutoff_hours: int,
        base_attributes: dict[str, Any],
        pricing_rules: list[PricingRule],
        custom_attributes: list[CustomAttribute],
        is_published: bool = False,
    ) -> Result[Self]:
        errors: list[FieldError] = []

        slug_r = Slug.create(slug)
        if slug_r.is_failure:
            errors.append(FieldError(code=slug_r.error, field="slug"))

        name_r = Name.create(name)
        if name_r.is_failure:
            errors.append(FieldError(code=name_r.error, field="name"))

        desc_r = ShortDescription.create(description)
        if desc_r.is_failure:
            errors.append(FieldError(code=desc_r.error, field="description"))

        city_r = Name.create(city)
        if city_r.is_failure:
            errors.append(FieldError(code=city_r.error, field="city"))

        region_r = Name.create(region)
        if region_r.is_failure:
            errors.append(FieldError(code=region_r.error, field="region"))

        tz_r = IanaTimezone.create(timezone)
        if tz_r.is_failure:
            errors.append(FieldError(code=tz_r.error, field="timezone"))

        slot_r = SlotDuration.create(slot_duration_minutes)
        if slot_r.is_failure:
            errors.append(FieldError(code=slot_r.error, field="slot_duration_minutes"))

        price_r = Money.create(base_price_cents)
        if price_r.is_failure:
            errors.append(FieldError(code=price_r.error, field="base_price_cents"))

        cutoff_r = CancellationCutoff.create(customer_cancellation_cutoff_hours)
        if cutoff_r.is_failure:
            errors.append(FieldError(code=cutoff_r.error, field="customer_cancellation_cutoff_hours"))

        # Cross-rule pricing checks happen AFTER scalar VO validation succeeds
        # because they need slot_r.value and operating_hours intact.
        # Implemented in Task 6.

        # Custom attributes uniqueness + disjoint-with-base
        # Implemented in Task 6.

        if errors:
            return Result.failure_many(errors)

        return Result.success(cls(
            owner_id=owner_id,
            resource_type_id=resource_type_id,
            slug=slug_r.value,
            name=name_r.value,
            description=desc_r.value,
            city=city_r.value,
            region=region_r.value,
            timezone=tz_r.value,
            slot_duration_minutes=slot_r.value,
            operating_hours=operating_hours,
            base_price_cents=price_r.value,
            customer_cancellation_cutoff_hours=cutoff_r.value,
            base_attributes=dict(base_attributes),
            is_published=is_published,
            _pricing_rules=list(pricing_rules),
            _custom_attributes=list(custom_attributes),
        ))

    @property
    def pricing_rules(self) -> tuple[PricingRule, ...]:
        return tuple(self._pricing_rules)

    @property
    def custom_attributes(self) -> tuple[CustomAttribute, ...]:
        return tuple(self._custom_attributes)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/unit/domain/resources/test_resource.py -v`
Expected: 2 PASS (happy path + aggregated scalar errors).

- [ ] **Step 5: Commit**

```bash
git add app/domain/resources/resource.py tests/unit/domain/resources/test_resource.py
git commit -m "$(cat <<'EOF'
feat(resources): Resource aggregate scaffolding + scalar VO aggregation

Identity (owner_id, resource_type_id), scalar VO fields, lifecycle flags,
private collections with tuple views. Resource.create aggregates scalar
VO factory failures via failure_many. Cross-rule pricing checks and
custom-attribute disjointness land in the next task.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: `Resource.create` — cross-rule pricing + custom-attribute checks

**Files:**
- Modify: `app/domain/resources/resource.py`
- Modify: `tests/unit/domain/resources/test_resource.py`

- [ ] **Step 1: Add failing tests for cross-rule invariants**

Append to `tests/unit/domain/resources/test_resource.py`:

```python
def test_create_rejects_overlapping_pricing_rules():
    rule_a = PricingRule.create(
        weekdays=[Weekday.FRIDAY], window=_w(18, 22), price=_money(12000),
    ).value
    rule_b = PricingRule.create(
        weekdays=[Weekday.FRIDAY], window=_w(20, 23), price=_money(15000),
    ).value
    r = Resource.create(**_valid_kwargs(
        operating_hours=_ws(days={Weekday.FRIDAY: [_w(8, 23)]}),
        pricing_rules=[rule_a, rule_b],
    ))
    assert r.is_failure
    codes = {(e.field, e.code) for e in r.details}
    assert ("pricing_rules[1]", Resource.PRICING_RULES_OVERLAP) in codes


def test_create_rejects_pricing_rule_misaligned():
    rule = PricingRule.create(
        weekdays=[Weekday.FRIDAY], window=_w_min(18, 30, 22, 0), price=_money(12000),
    ).value
    r = Resource.create(**_valid_kwargs(
        operating_hours=_ws(days={Weekday.FRIDAY: [_w(8, 23)]}),
        pricing_rules=[rule],
    ))
    assert r.is_failure
    codes = {(e.field, e.code) for e in r.details}
    assert ("pricing_rules[0]", Resource.PRICING_RULE_NOT_ALIGNED_TO_SLOT_GRID) in codes


def test_create_rejects_pricing_rule_outside_operating_hours():
    rule = PricingRule.create(
        weekdays=[Weekday.FRIDAY], window=_w(2, 4), price=_money(12000),
    ).value
    r = Resource.create(**_valid_kwargs(
        operating_hours=_ws(days={Weekday.FRIDAY: [_w(18, 23)]}),
        pricing_rules=[rule],
    ))
    assert r.is_failure
    codes = {(e.field, e.code) for e in r.details}
    assert ("pricing_rules[0]", Resource.PRICING_RULE_OUTSIDE_OPERATING_HOURS) in codes


def test_create_rejects_duplicate_custom_attribute_keys():
    a = CustomAttribute.create(key="wifi", label="Wi-Fi", value="sim").value
    b = CustomAttribute.create(key="wifi", label="Wi-Fi 5G", value="sim").value
    r = Resource.create(**_valid_kwargs(custom_attributes=[a, b]))
    assert r.is_failure
    codes = {(e.field, e.code) for e in r.details}
    assert ("custom_attributes[1]", Resource.DUPLICATE_CUSTOM_ATTRIBUTE_KEY) in codes


def test_create_rejects_custom_attribute_key_conflicting_with_base():
    a = CustomAttribute.create(key="wifi", label="Wi-Fi", value="sim").value
    r = Resource.create(**_valid_kwargs(
        base_attributes={"wifi": True},
        custom_attributes=[a],
    ))
    assert r.is_failure
    codes = {(e.field, e.code) for e in r.details}
    assert ("custom_attributes[0]", Resource.CUSTOM_ATTRIBUTE_KEY_CONFLICTS_WITH_BASE) in codes
```

Also add the helper near the top of the test file (next to `_w`):

```python
def _w_min(sh: int, sm: int, eh: int, em: int) -> TimeWindow:
    return TimeWindow.create(time(sh, sm), time(eh, em)).value
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/unit/domain/resources/test_resource.py -v`
Expected: 5 FAIL (cross-rule checks unimplemented).

- [ ] **Step 3: Implement cross-rule checks**

Replace the cross-rule placeholder block in `Resource.create` with the actual checks. Add this after the existing scalar VO validation block but before the `if errors: return Result.failure_many(errors)` line:

```python
        # Cross-rule pricing checks (only run if scalars are sane enough to compute).
        if slot_r.is_success:
            errors.extend(cls._validate_pricing_rules(
                slot_duration_minutes=slot_r.value.minutes,
                hours=operating_hours,
                rules=pricing_rules,
            ))

        # Custom attribute uniqueness + disjoint-with-base.
        errors.extend(cls._validate_custom_attributes(
            base_attributes=base_attributes,
            customs=custom_attributes,
        ))
```

Add these two private static helpers to the `Resource` class (place them after the `custom_attributes` property):

```python
    @staticmethod
    def _validate_pricing_rules(
        *,
        slot_duration_minutes: int,
        hours: WeeklySchedule,
        rules: list[PricingRule],
    ) -> list[FieldError]:
        errors: list[FieldError] = []

        for idx, rule in enumerate(rules):
            field = f"pricing_rules[{idx}]"

            # Alignment.
            start_min = rule.window.start.hour * 60 + rule.window.start.minute
            duration = rule.window.duration_minutes()
            if (start_min % slot_duration_minutes) != 0 or (duration % slot_duration_minutes) != 0:
                errors.append(FieldError(
                    code=Resource.PRICING_RULE_NOT_ALIGNED_TO_SLOT_GRID,
                    field=field,
                ))

            # Containment: for each weekday in this rule, the rule's window must
            # fit inside at least one operating window for that weekday.
            for wd in rule.weekdays:
                day_windows = hours.for_weekday(wd)
                contained = any(
                    op.start <= rule.window.start and rule.window.end <= op.end
                    for op in day_windows
                )
                if not contained:
                    errors.append(FieldError(
                        code=Resource.PRICING_RULE_OUTSIDE_OPERATING_HOURS,
                        field=field,
                    ))
                    break  # one error per rule is enough

            # Overlap: this rule vs every previous rule on a shared weekday.
            for prev_idx in range(idx):
                prev = rules[prev_idx]
                shared = rule.weekdays & prev.weekdays
                if not shared:
                    continue
                # Time overlap: half-open intersection
                if rule.window.start < prev.window.end and prev.window.start < rule.window.end:
                    errors.append(FieldError(
                        code=Resource.PRICING_RULES_OVERLAP,
                        field=field,
                    ))
                    break

        return errors

    @staticmethod
    def _validate_custom_attributes(
        *,
        base_attributes: dict[str, Any],
        customs: list[CustomAttribute],
    ) -> list[FieldError]:
        errors: list[FieldError] = []
        seen: set[str] = set()
        base_keys = set(base_attributes.keys())

        for idx, attr in enumerate(customs):
            field = f"custom_attributes[{idx}]"
            key = attr.key.value
            if key in seen:
                errors.append(FieldError(
                    code=Resource.DUPLICATE_CUSTOM_ATTRIBUTE_KEY, field=field,
                ))
            seen.add(key)
            if key in base_keys:
                errors.append(FieldError(
                    code=Resource.CUSTOM_ATTRIBUTE_KEY_CONFLICTS_WITH_BASE, field=field,
                ))

        return errors
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/unit/domain/resources/test_resource.py -v`
Expected: 7 PASS (2 from Task 5 + 5 new).

- [ ] **Step 5: Commit**

```bash
git add app/domain/resources/resource.py tests/unit/domain/resources/test_resource.py
git commit -m "$(cat <<'EOF'
feat(resources): Resource cross-rule validation

PricingRule alignment, containment in operating hours, and pairwise
overlap on shared weekdays. CustomAttribute key uniqueness +
disjointness with base_attributes. All emitted as FieldError aggregated
into Resource.create's failure_many envelope.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: `Resource` mutators (metadata, replace-collections, set-scalar, publish/unpublish)

**Files:**
- Modify: `app/domain/resources/resource.py`
- Modify: `tests/unit/domain/resources/test_resource.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/unit/domain/resources/test_resource.py`:

```python
def test_update_metadata_partial():
    res = Resource.create(**_valid_kwargs()).value
    r = res.update_metadata(name="Novo Nome", city="Rio de Janeiro")
    assert r.is_success
    assert res.name.value == "Novo Nome"
    assert res.city.value == "Rio de Janeiro"


def test_update_metadata_aggregates_failures():
    res = Resource.create(**_valid_kwargs()).value
    r = res.update_metadata(name="", city="")
    assert r.is_failure
    fields = {e.field for e in r.details}
    assert "name" in fields
    assert "city" in fields


def test_replace_operating_hours_revalidates_pricing_rules():
    rule = PricingRule.create(
        weekdays=[Weekday.MONDAY], window=_w(18, 22), price=_money(10000),
    ).value
    res = Resource.create(**_valid_kwargs(
        operating_hours=_ws(days={Weekday.MONDAY: [_w(8, 23)]}),
        pricing_rules=[rule],
    )).value

    new_hours = WeeklySchedule.create(
        slot_duration_minutes=60,
        days={Weekday.MONDAY: [_w(8, 12)]},  # rule no longer fits
    ).value
    r = res.replace_operating_hours(new_hours)
    assert r.is_failure
    codes = {e.code for e in r.details}
    assert Resource.PRICING_RULE_OUTSIDE_OPERATING_HOURS in codes


def test_replace_pricing_rules_overlaps():
    res = Resource.create(**_valid_kwargs(
        operating_hours=_ws(days={Weekday.MONDAY: [_w(8, 23)]}),
    )).value
    a = PricingRule.create(weekdays=[Weekday.MONDAY], window=_w(8, 14), price=_money(5000)).value
    b = PricingRule.create(weekdays=[Weekday.MONDAY], window=_w(13, 22), price=_money(10000)).value
    r = res.replace_pricing_rules([a, b])
    assert r.is_failure
    codes = {e.code for e in r.details}
    assert Resource.PRICING_RULES_OVERLAP in codes


def test_replace_base_attributes_conflict_with_custom():
    custom = CustomAttribute.create(key="wifi", label="Wi-Fi", value="sim").value
    res = Resource.create(**_valid_kwargs(custom_attributes=[custom])).value
    r = res.replace_base_attributes({"wifi": True})
    assert r.is_failure
    codes = {e.code for e in r.details}
    assert Resource.CUSTOM_ATTRIBUTE_KEY_CONFLICTS_WITH_BASE in codes


def test_replace_custom_attributes_disjoint_with_base():
    res = Resource.create(**_valid_kwargs(base_attributes={"wifi": True})).value
    custom = CustomAttribute.create(key="wifi", label="Wi-Fi", value="sim").value
    r = res.replace_custom_attributes([custom])
    assert r.is_failure
    codes = {e.code for e in r.details}
    assert Resource.CUSTOM_ATTRIBUTE_KEY_CONFLICTS_WITH_BASE in codes


def test_set_base_price_no_invariant():
    res = Resource.create(**_valid_kwargs()).value
    res.set_base_price(_money(15000))
    assert res.base_price_cents.cents == 15000


def test_set_cancellation_cutoff_no_invariant():
    res = Resource.create(**_valid_kwargs()).value
    new_cutoff = CancellationCutoff.create(48).value
    res.set_cancellation_cutoff(new_cutoff)
    assert res.customer_cancellation_cutoff_hours.hours == 48


def test_set_slot_duration_revalidates_hours_and_rules():
    rule = PricingRule.create(
        weekdays=[Weekday.MONDAY], window=_w(8, 12), price=_money(8000),
    ).value
    res = Resource.create(**_valid_kwargs(
        operating_hours=_ws(slot=60, days={Weekday.MONDAY: [_w(8, 22)]}),
        pricing_rules=[rule],
    )).value

    new_dur = SlotDuration.create(45).value  # neither hours nor rule align
    r = res.set_slot_duration(new_dur)
    assert r.is_failure


def test_publish_unpublish_toggle():
    res = Resource.create(**_valid_kwargs()).value
    assert res.is_published is False
    res.publish()
    assert res.is_published is True
    res.unpublish()
    assert res.is_published is False
```

Add the import at the top of the test file: `from app.domain.shared.value_objects.cancellation_cutoff import CancellationCutoff` and `from app.domain.shared.value_objects.slot_duration import SlotDuration`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/unit/domain/resources/test_resource.py -v`
Expected: New tests FAIL (`AttributeError: 'Resource' object has no attribute 'update_metadata'` etc.).

- [ ] **Step 3: Implement mutators**

In `app/domain/resources/resource.py`, append the following methods to the `Resource` class (after the two `_validate_*` static methods):

```python
    def update_metadata(
        self,
        *,
        name: str | None = None,
        description: str | None = None,
        city: str | None = None,
        region: str | None = None,
    ) -> Result[None]:
        if name is None and description is None and city is None and region is None:
            return Result.success(None)

        errors: list[FieldError] = []
        new_name = self.name
        new_desc = self.description
        new_city = self.city
        new_region = self.region

        if name is not None:
            r = Name.create(name)
            if r.is_failure:
                errors.append(FieldError(code=r.error, field="name"))
            else:
                new_name = r.value

        if description is not None:
            r = ShortDescription.create(description)
            if r.is_failure:
                errors.append(FieldError(code=r.error, field="description"))
            else:
                new_desc = r.value

        if city is not None:
            r = Name.create(city)
            if r.is_failure:
                errors.append(FieldError(code=r.error, field="city"))
            else:
                new_city = r.value

        if region is not None:
            r = Name.create(region)
            if r.is_failure:
                errors.append(FieldError(code=r.error, field="region"))
            else:
                new_region = r.value

        if errors:
            return Result.failure_many(errors)

        self.name = new_name
        self.description = new_desc
        self.city = new_city
        self.region = new_region
        self.updated_at = _utcnow()
        return Result.success(None)

    def replace_operating_hours(self, hours: WeeklySchedule) -> Result[None]:
        errors = self._validate_pricing_rules(
            slot_duration_minutes=self.slot_duration_minutes.minutes,
            hours=hours,
            rules=self._pricing_rules,
        )
        if errors:
            return Result.failure_many(errors)
        self.operating_hours = hours
        self.updated_at = _utcnow()
        return Result.success(None)

    def replace_pricing_rules(self, rules: list[PricingRule]) -> Result[None]:
        errors = self._validate_pricing_rules(
            slot_duration_minutes=self.slot_duration_minutes.minutes,
            hours=self.operating_hours,
            rules=rules,
        )
        if errors:
            return Result.failure_many(errors)
        self._pricing_rules = list(rules)
        self.updated_at = _utcnow()
        return Result.success(None)

    def replace_base_attributes(self, attrs: dict[str, Any]) -> Result[None]:
        errors = self._validate_custom_attributes(
            base_attributes=attrs,
            customs=self._custom_attributes,
        )
        if errors:
            return Result.failure_many(errors)
        self.base_attributes = dict(attrs)
        self.updated_at = _utcnow()
        return Result.success(None)

    def replace_custom_attributes(self, attrs: list[CustomAttribute]) -> Result[None]:
        errors = self._validate_custom_attributes(
            base_attributes=self.base_attributes,
            customs=attrs,
        )
        if errors:
            return Result.failure_many(errors)
        self._custom_attributes = list(attrs)
        self.updated_at = _utcnow()
        return Result.success(None)

    def set_base_price(self, price: Money) -> None:
        self.base_price_cents = price
        self.updated_at = _utcnow()

    def set_cancellation_cutoff(self, cutoff: CancellationCutoff) -> None:
        self.customer_cancellation_cutoff_hours = cutoff
        self.updated_at = _utcnow()

    def set_slot_duration(self, duration: SlotDuration) -> Result[None]:
        from app.domain.shared.weekday import Weekday as _Wd
        rebuilt = WeeklySchedule.create(
            slot_duration_minutes=duration.minutes,
            days={wd: list(self.operating_hours.for_weekday(wd)) for wd in _Wd},
        )
        if rebuilt.is_failure:
            return Result.from_failure(rebuilt)

        errors = self._validate_pricing_rules(
            slot_duration_minutes=duration.minutes,
            hours=rebuilt.value,
            rules=self._pricing_rules,
        )
        if errors:
            return Result.failure_many(errors)

        self.slot_duration_minutes = duration
        self.operating_hours = rebuilt.value
        self.updated_at = _utcnow()
        return Result.success(None)

    def publish(self) -> None:
        self.is_published = True
        self.updated_at = _utcnow()

    def unpublish(self) -> None:
        self.is_published = False
        self.updated_at = _utcnow()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/unit/domain/resources/test_resource.py -v`
Expected: 17 PASS.

- [ ] **Step 5: Commit**

```bash
git add app/domain/resources/resource.py tests/unit/domain/resources/test_resource.py
git commit -m "$(cat <<'EOF'
feat(resources): Resource mutators (metadata + replace + set + publish)

update_metadata aggregates per-field errors. replace_operating_hours,
replace_pricing_rules, replace_base_attributes, replace_custom_attributes
re-run cross-rule validation. set_slot_duration rebuilds hours under
the new grid and re-validates pricing rules. set_base_price /
set_cancellation_cutoff have no invariants. publish/unpublish toggle.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: `Resource.soft_delete` + `is_deleted`

**Files:**
- Modify: `app/domain/resources/resource.py`
- Modify: `tests/unit/domain/resources/test_resource.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/unit/domain/resources/test_resource.py`:

```python
def test_soft_delete_sets_deleted_at():
    res = Resource.create(**_valid_kwargs()).value
    now = datetime(2026, 4, 26, 12, 0, 0, tzinfo=timezone.utc)
    r = res.soft_delete(now=now)
    assert r.is_success
    assert res.deleted_at == now
    assert res.is_deleted() is True


def test_soft_delete_already_deleted_returns_failure():
    res = Resource.create(**_valid_kwargs()).value
    now = datetime(2026, 4, 26, 12, 0, 0, tzinfo=timezone.utc)
    res.soft_delete(now=now)
    r = res.soft_delete(now=now)
    assert r.is_failure
    assert r.error == Resource.RESOURCE_ALREADY_DELETED


def test_soft_delete_naive_datetime_rejected():
    res = Resource.create(**_valid_kwargs()).value
    naive = datetime(2026, 4, 26, 12, 0, 0)
    r = res.soft_delete(now=naive)
    assert r.is_failure
    assert r.error == Resource.DELETED_AT_NOT_TZ_AWARE
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/unit/domain/resources/test_resource.py -v`
Expected: 3 new tests FAIL.

- [ ] **Step 3: Implement soft_delete + is_deleted**

In `app/domain/resources/resource.py`, append to the `Resource` class (after `unpublish`):

```python
    def soft_delete(self, *, now: datetime) -> Result[None]:
        if now.tzinfo is None:
            return Result.failure(self.DELETED_AT_NOT_TZ_AWARE)
        if self.deleted_at is not None:
            return Result.failure(self.RESOURCE_ALREADY_DELETED)
        self.deleted_at = now
        self.updated_at = now
        return Result.success(None)

    def is_deleted(self) -> bool:
        return self.deleted_at is not None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/unit/domain/resources/test_resource.py -v`
Expected: 20 PASS.

- [ ] **Step 5: Commit**

```bash
git add app/domain/resources/resource.py tests/unit/domain/resources/test_resource.py
git commit -m "$(cat <<'EOF'
feat(resources): Resource.soft_delete + is_deleted

Plan 06 has no booking checks here — Plan 08 will extend the handler
to inject IBookingRepository and reject soft-delete when an APPROVED
future booking exists, plus auto-reject PENDINGs in the same transaction.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 9: `Resource.compute_price`

**Files:**
- Modify: `app/domain/resources/resource.py`
- Modify: `tests/unit/domain/resources/test_resource.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/unit/domain/resources/test_resource.py`:

```python
from datetime import timedelta
from zoneinfo import ZoneInfo

from app.domain.shared.value_objects.date_time_range import DateTimeRange


def _utc(year, month, day, hour=0, minute=0):
    return datetime(year, month, day, hour, minute, tzinfo=timezone.utc)


def test_compute_price_falls_back_to_base():
    # No pricing rules → every slot uses base_price_cents.
    res = Resource.create(**_valid_kwargs(
        operating_hours=_ws(days={Weekday.MONDAY: [_w(8, 22)]}),
        base_price_cents=8000,
    )).value
    # Monday 2026-04-27 in São Paulo, 09:00-11:00 local = 12:00-14:00 UTC.
    sao_paulo = ZoneInfo("America/Sao_Paulo")
    start_local = datetime(2026, 4, 27, 9, 0, tzinfo=sao_paulo)
    end_local = datetime(2026, 4, 27, 11, 0, tzinfo=sao_paulo)
    rng = DateTimeRange.create(start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)).value
    total = res.compute_price(rng)
    assert total.cents == 8000 * 2  # 2 slots × R$ 80


def test_compute_price_uses_matching_rule():
    rule = PricingRule.create(
        weekdays=[Weekday.MONDAY],
        window=_w(18, 22),
        price=_money(12000),
    ).value
    res = Resource.create(**_valid_kwargs(
        operating_hours=_ws(days={Weekday.MONDAY: [_w(8, 22)]}),
        base_price_cents=8000,
        pricing_rules=[rule],
    )).value
    # Monday local 18:00-20:00 → 2 slots × R$ 120
    sao_paulo = ZoneInfo("America/Sao_Paulo")
    start_local = datetime(2026, 4, 27, 18, 0, tzinfo=sao_paulo)
    end_local = datetime(2026, 4, 27, 20, 0, tzinfo=sao_paulo)
    rng = DateTimeRange.create(start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)).value
    total = res.compute_price(rng)
    assert total.cents == 12000 * 2


def test_compute_price_mixed_rule_and_fallback():
    rule = PricingRule.create(
        weekdays=[Weekday.MONDAY],
        window=_w(18, 22),
        price=_money(12000),
    ).value
    res = Resource.create(**_valid_kwargs(
        operating_hours=_ws(days={Weekday.MONDAY: [_w(8, 22)]}),
        base_price_cents=8000,
        pricing_rules=[rule],
    )).value
    # Monday local 17:00-19:00 → slot 17 falls outside rule (rule starts 18) → base; slot 18 → rule.
    sao_paulo = ZoneInfo("America/Sao_Paulo")
    start_local = datetime(2026, 4, 27, 17, 0, tzinfo=sao_paulo)
    end_local = datetime(2026, 4, 27, 19, 0, tzinfo=sao_paulo)
    rng = DateTimeRange.create(start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)).value
    total = res.compute_price(rng)
    assert total.cents == 8000 + 12000
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/unit/domain/resources/test_resource.py -v`
Expected: 3 new tests FAIL with `AttributeError: 'Resource' object has no attribute 'compute_price'`.

- [ ] **Step 3: Implement compute_price**

Add the import at the top of `app/domain/resources/resource.py`:

```python
from datetime import timedelta
from zoneinfo import ZoneInfo

from app.domain.shared.value_objects.date_time_range import DateTimeRange
```

And the helper to import `Weekday`:

```python
from app.domain.shared.weekday import Weekday
```

Append to the `Resource` class:

```python
    def compute_price(self, slot_range: DateTimeRange) -> Money:
        """Sum of per-slot prices.

        For each slot inside slot_range:
          - Convert slot_start (UTC) to the resource's timezone via astimezone.
          - Match a PricingRule when: weekday in rule.weekdays AND
            rule.window.start <= local_time_of_day < rule.window.end (half-open).
            The no-overlap invariant guarantees at most one rule matches.
          - Fall back to base_price_cents when no rule matches.
        """
        tz = ZoneInfo(self.timezone.value)
        slot_minutes = self.slot_duration_minutes.minutes
        delta = timedelta(minutes=slot_minutes)
        total = 0

        cursor = slot_range.start_at
        while cursor < slot_range.end_at:
            local = cursor.astimezone(tz)
            wd_local = _PYTHON_WD_TO_VO[local.weekday()]
            tod = local.time()

            matched: PricingRule | None = None
            for rule in self._pricing_rules:
                if wd_local not in rule.weekdays:
                    continue
                if rule.window.start <= tod < rule.window.end:
                    matched = rule
                    break

            total += matched.price.cents if matched else self.base_price_cents.cents
            cursor += delta

        return Money.create(total).value
```

Add at the bottom of the same module (after the `Resource` class definition):

```python
# Map Python's datetime.weekday() (Mon=0..Sun=6) to our Weekday VO.
_PYTHON_WD_TO_VO = {
    0: Weekday.MONDAY,
    1: Weekday.TUESDAY,
    2: Weekday.WEDNESDAY,
    3: Weekday.THURSDAY,
    4: Weekday.FRIDAY,
    5: Weekday.SATURDAY,
    6: Weekday.SUNDAY,
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/unit/domain/resources/test_resource.py -v`
Expected: 23 PASS.

- [ ] **Step 5: Commit**

```bash
git add app/domain/resources/resource.py tests/unit/domain/resources/test_resource.py
git commit -m "$(cat <<'EOF'
feat(resources): Resource.compute_price (per-slot pricing)

Iterates slots in slot_range, converts each slot start to the resource's
timezone, matches a PricingRule (half-open [start, end)) or falls back
to base_price_cents. Returns aggregate Money. Used by Plan 08's
RequestBookingHandler.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 10: `IResourceRepository` Protocol

**Files:**
- Create: `app/domain/resources/repository.py`

- [ ] **Step 1: Write the protocol**

Create `app/domain/resources/repository.py`:

```python
from __future__ import annotations
from typing import Iterable, Protocol
from uuid import UUID

from app.domain.resources.resource import Resource
from app.domain.shared.result import Result


class IResourceRepository(Protocol):
    """Persistence port for the resources feature."""

    async def add(self, resource: Resource) -> Result[None]:
        """Persist a new Resource. Returns SlugAlreadyTaken (409) on
        (owner_id, slug) conflict."""
        ...

    async def update(self, resource: Resource) -> Result[None]:
        """Persist changes. Returns ResourceNotFound (404) if missing."""
        ...

    async def get_by_id(self, resource_id: UUID) -> Resource | None:
        ...

    async def get_by_owner_and_slug(
        self, owner_id: UUID, slug: str,
    ) -> Resource | None:
        ...

    async def list_by_owner(
        self,
        owner_id: UUID,
        *,
        include_deleted: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Resource]:
        ...

    async def list_published(
        self,
        *,
        resource_type_slug: str | None = None,
        city: str | None = None,
        region: str | None = None,
        owner_ids_filter: Iterable[UUID] | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Resource]:
        """Excludes deleted and unpublished. Owner-operational filter is at
        HANDLER level — pass via owner_ids_filter."""
        ...

    async def list_published_by_owner(
        self,
        owner_id: UUID,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Resource]:
        ...
```

This is a Protocol — no test on its own; tests come with the SQLAlchemy implementation in Task 16.

- [ ] **Step 2: Sanity-import to ensure module loads**

Run: `.venv/bin/python -c "from app.domain.resources.repository import IResourceRepository; print(IResourceRepository)"`
Expected: prints the Protocol class.

- [ ] **Step 3: Commit**

```bash
git add app/domain/resources/repository.py
git commit -m "$(cat <<'EOF'
feat(resources): IResourceRepository Protocol

Persistence port for the resources feature. Concrete SQLAlchemy
implementation lands in a later task; this is the contract the
domain/use_cases layers depend on.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 11: `User.public_slug` domain extension

**Files:**
- Modify: `app/domain/accounts/user.py`
- Modify: `tests/unit/domain/accounts/test_user.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/unit/domain/accounts/test_user.py` (create test if file structure differs — confirm location with `ls tests/unit/domain/accounts/`):

```python
def test_owner_requires_public_slug():
    r = User.create(
        email="o@example.com",
        password_hash="hash",
        role=Role.OWNER,
        full_name="Joana Silva",
        phone=None,
        public_slug=None,
    )
    assert r.is_failure
    codes = {e.code for e in r.details}
    assert User.PUBLIC_SLUG_REQUIRED_FOR_OWNER in codes


def test_non_owner_forbids_public_slug():
    r = User.create(
        email="c@example.com",
        password_hash="hash",
        role=Role.CUSTOMER,
        full_name="Bruno Lima",
        phone=None,
        public_slug="bruno-lima",
    )
    assert r.is_failure
    codes = {e.code for e in r.details}
    assert User.PUBLIC_SLUG_FORBIDDEN_FOR_NON_OWNER in codes


def test_owner_accepts_valid_slug():
    r = User.create(
        email="o@example.com",
        password_hash="hash",
        role=Role.OWNER,
        full_name="Joana Silva",
        phone=None,
        public_slug="joana-silva",
    )
    assert r.is_success
    assert r.value.public_slug.value == "joana-silva"


def test_customer_accepts_no_slug():
    r = User.create(
        email="c@example.com",
        password_hash="hash",
        role=Role.CUSTOMER,
        full_name="Bruno Lima",
        phone=None,
        public_slug=None,
    )
    assert r.is_success
    assert r.value.public_slug is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/unit/domain/accounts/test_user.py -v`
Expected: New tests FAIL — `User.create` doesn't accept `public_slug`.

- [ ] **Step 3: Modify the User entity**

Replace `app/domain/accounts/user.py` with:

```python
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Self
from app.domain.accounts.role import Role
from app.domain.shared.entity import BaseEntity
from app.domain.shared.field_error import FieldError
from app.domain.shared.result import Result
from app.domain.shared.value_objects.brazilian_phone import BrazilianPhone
from app.domain.shared.value_objects.email import Email
from app.domain.shared.value_objects.name import Name
from app.domain.shared.value_objects.slug import Slug


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(slots=True, kw_only=True)
class User(BaseEntity):
    PUBLIC_SLUG_REQUIRED_FOR_OWNER = "PublicSlugRequiredForOwner"
    PUBLIC_SLUG_FORBIDDEN_FOR_NON_OWNER = "PublicSlugForbiddenForNonOwner"

    email: Email
    password_hash: str
    role: Role
    full_name: Name
    phone: BrazilianPhone | None = None
    is_active: bool = True
    public_slug: Slug | None = None

    @classmethod
    def create(
        cls,
        *,
        email: str,
        password_hash: str,
        role: Role,
        full_name: str,
        phone: str | None,
        public_slug: str | None = None,
    ) -> Result[Self]:
        errors: list[FieldError] = []

        email_r = Email.create(email)
        if email_r.is_failure:
            errors.append(FieldError(code=email_r.error, field="email"))

        name_r = Name.create(full_name)
        if name_r.is_failure:
            errors.append(FieldError(code=name_r.error, field="full_name"))

        if not password_hash:
            errors.append(FieldError(code="PasswordHashCannotBeEmpty", field="password_hash"))

        phone_r = BrazilianPhone.create_if_not_empty(phone)
        if phone_r.is_failure:
            errors.append(FieldError(code=phone_r.error, field="phone"))

        slug_vo: Slug | None = None
        if public_slug is not None:
            slug_r = Slug.create(public_slug)
            if slug_r.is_failure:
                errors.append(FieldError(code=slug_r.error, field="public_slug"))
            else:
                slug_vo = slug_r.value

        # Cross-field invariant: OWNER ⇔ public_slug is not None.
        if role is Role.OWNER and public_slug is None:
            errors.append(FieldError(code=cls.PUBLIC_SLUG_REQUIRED_FOR_OWNER, field="public_slug"))
        if role is not Role.OWNER and public_slug is not None:
            errors.append(FieldError(code=cls.PUBLIC_SLUG_FORBIDDEN_FOR_NON_OWNER, field="public_slug"))

        if errors:
            return Result.failure_many(errors)

        return Result.success(cls(
            email=email_r.value,
            password_hash=password_hash,
            role=role,
            full_name=name_r.value,
            phone=phone_r.value,
            public_slug=slug_vo,
        ))

    def change_password_hash(self, new_hash: str) -> None:
        self.password_hash = new_hash
        self.updated_at = _utcnow()

    def set_role(self, new_role: Role) -> None:
        self.role = new_role
        self.updated_at = _utcnow()

    def deactivate(self) -> None:
        self.is_active = False
        self.updated_at = _utcnow()

    def activate(self) -> None:
        self.is_active = True
        self.updated_at = _utcnow()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/unit/domain/accounts/test_user.py -v`
Expected: All existing PASS + new 4 PASS.

Run: `.venv/bin/pytest tests/unit/domain/accounts/ -v` to check nothing else broke (existing tests likely pass user.create without `public_slug` because Role isn't OWNER — but if any existing test creates an OWNER user, it'll start failing). Fix any test that creates an OWNER without `public_slug` by adding `public_slug="some-slug"`.

- [ ] **Step 5: Commit**

```bash
git add app/domain/accounts/user.py tests/unit/domain/accounts/test_user.py
git commit -m "$(cat <<'EOF'
feat(accounts): User.public_slug field + role invariant

Slug is mandatory for OWNER (drives /v1/owners/{owner_slug}) and
forbidden for ADMIN/CUSTOMER. Cross-field rule emitted in User.create
via failure_many.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 12: `UserModel.public_slug` column + migration + repo extension

**Files:**
- Modify: `app/infrastructure/db/mappings/user.py`
- Create: `app/migrations/versions/<ts>_users_add_public_slug.py` (via Alembic)
- Modify: `app/domain/accounts/repository.py`
- Modify: `app/infrastructure/repositories/user_repository.py`
- Test: `tests/integration/accounts/test_user_repository_public_slug.py`

- [ ] **Step 1: Add column to UserModel**

Read the current `app/infrastructure/db/mappings/user.py` and add the `public_slug` column. Add an import for `Text` if not already there. Add:

```python
public_slug: Mapped[str | None] = mapped_column(
    Text, nullable=True, unique=True, index=True,
)
```

(Place it next to other optional fields like `phone_number`.)

- [ ] **Step 2: Generate the Alembic migration**

Run:

```bash
make migrate-new msg="users add public_slug"
```

Expected: a new file like `app/migrations/versions/<timestamp>_users_add_public_slug.py` is created with `op.add_column(...)` and a unique constraint. Verify the generated content includes:
- `op.add_column("users", sa.Column("public_slug", sa.Text(), nullable=True))`
- `op.create_unique_constraint("uq_users_public_slug", "users", ["public_slug"])` (or similar)
- `op.create_index("ix_users_public_slug", "users", ["public_slug"], unique=False)` if Alembic emits it

If Alembic doesn't auto-generate the unique constraint, add it manually inside the `upgrade()` body.

- [ ] **Step 3: Apply the migration**

Run:

```bash
make migrate-up
```

Expected: migration applies cleanly to the dev DB.

- [ ] **Step 4: Add `get_by_public_slug` to the repository protocol + impl**

Modify `app/domain/accounts/repository.py`:

```python
class IUserRepository(Protocol):
    async def get_by_id(self, user_id: UUID) -> User | None: ...
    async def get_by_email(self, email: str) -> User | None: ...
    async def get_by_public_slug(self, public_slug: str) -> User | None: ...
    async def list_by_ids(self, ids: Iterable[UUID]) -> list[User]: ...
    async def list_active(
        self, *, limit: int = 50, offset: int = 0
    ) -> Sequence[User]: ...
    async def add(self, user: User) -> None: ...
    async def update(self, user: User) -> None: ...
```

Add `Iterable` to the imports.

Modify `app/infrastructure/repositories/user_repository.py`:

- Add the import: `from app.domain.shared.value_objects.slug import Slug`.
- In `_to_entity`, build `public_slug=Slug(value=row.public_slug) if row.public_slug else None` and include it in the `User(...)` constructor call.
- In `_to_model`, include `public_slug=u.public_slug.value if u.public_slug else None`.
- In `update`, include `row.public_slug = user.public_slug.value if user.public_slug else None`.
- Add new methods:

```python
    async def get_by_public_slug(self, public_slug: str) -> User | None:
        stmt = select(UserModel).where(UserModel.public_slug == public_slug)
        row = await self._first_or_default(stmt)
        return self._to_entity(row) if row else None

    async def list_by_ids(self, ids):
        ids_list = [str(i) for i in ids]
        if not ids_list:
            return []
        stmt = select(UserModel).where(UserModel.id.in_(ids_list))
        rows = await self._to_list(stmt)
        return [self._to_entity(r) for r in rows]
```

- [ ] **Step 5: Write the integration test**

Create `tests/integration/accounts/test_user_repository_public_slug.py`:

```python
from __future__ import annotations
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.accounts.role import Role
from app.domain.accounts.user import User
from app.infrastructure.repositories.user_repository import UserRepository


@pytest.mark.asyncio
async def test_unique_public_slug_allows_multiple_nulls(db_session: AsyncSession):
    repo = UserRepository(db_session)
    # Two CUSTOMERs both with public_slug=None should coexist.
    a = User.create(
        email="a@example.com", password_hash="x", role=Role.CUSTOMER,
        full_name="A B", phone=None, public_slug=None,
    ).value
    b = User.create(
        email="b@example.com", password_hash="x", role=Role.CUSTOMER,
        full_name="C D", phone=None, public_slug=None,
    ).value
    await repo.add(a)
    await repo.add(b)
    await db_session.flush()


@pytest.mark.asyncio
async def test_get_by_public_slug_returns_owner(db_session: AsyncSession):
    repo = UserRepository(db_session)
    owner = User.create(
        email="o@example.com", password_hash="x", role=Role.OWNER,
        full_name="O Owner", phone=None, public_slug="o-owner",
    ).value
    await repo.add(owner)
    await db_session.flush()

    found = await repo.get_by_public_slug("o-owner")
    assert found is not None
    assert found.id == owner.id

    missing = await repo.get_by_public_slug("nope")
    assert missing is None
```

- [ ] **Step 6: Extend the in-memory fake**

Modify `tests/unit/use_cases/accounts/fakes/in_memory_user_repository.py` to add the two new methods (matching the Protocol added in Step 4):

```python
    async def get_by_public_slug(self, public_slug: str) -> User | None:
        for u in self._by_id.values():
            if u.public_slug is not None and u.public_slug.value == public_slug:
                return u
        return None

    async def list_by_ids(self, ids):
        ids_set = set(ids)
        return [u for u in self._by_id.values() if u.id in ids_set]
```

Add the import for `Iterable` to the typing line: `from typing import Iterable, Sequence`.

- [ ] **Step 7: Run integration tests + verify in-memory still works**

Run: `.venv/bin/pytest tests/integration/accounts/test_user_repository_public_slug.py tests/unit/use_cases/accounts/ -v`
Expected: existing PASS + 2 new PASS.

- [ ] **Step 8: Commit**

```bash
git add app/infrastructure/db/mappings/user.py app/migrations/versions/*users_add_public_slug.py app/domain/accounts/repository.py app/infrastructure/repositories/user_repository.py tests/unit/use_cases/accounts/fakes/in_memory_user_repository.py tests/integration/accounts/test_user_repository_public_slug.py
git commit -m "$(cat <<'EOF'
feat(accounts): persist User.public_slug + repo helpers

Adds users.public_slug TEXT NULL UNIQUE column + Alembic migration.
IUserRepository gains get_by_public_slug and list_by_ids (the latter
used by ListPublicResourcesHandler for batch operational filtering).
SQLAlchemy + in-memory implementations both updated.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 13: `RegisterUserHandler` slug generation for OWNER + retry

**Files:**
- Modify: `app/use_cases/accounts/commands/register_user.py`
- Modify: `tests/unit/use_cases/accounts/commands/test_register_user.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/unit/use_cases/accounts/commands/test_register_user.py`:

```python
@pytest.mark.asyncio
async def test_owner_registration_generates_public_slug(
    user_repo, sub_repo, hasher, settings,
):
    handler = RegisterUserHandler(user_repo, hasher, sub_repo, settings)
    cmd = RegisterUserCommand(
        email="o@example.com",
        password="senha-forte-1",
        role=Role.OWNER,
        full_name="João da Silva",
        phone=None,
    )
    r = await handler.handle(cmd)
    assert r.is_success
    user = await user_repo.get_by_id(r.value.id)
    assert user.public_slug is not None
    assert user.public_slug.value == "joao-da-silva"


@pytest.mark.asyncio
async def test_owner_registration_collision_appends_suffix(
    user_repo, sub_repo, hasher, settings,
):
    handler = RegisterUserHandler(user_repo, hasher, sub_repo, settings)
    # Pre-seed an OWNER with slug "joao-da-silva"
    existing = User.create(
        email="first@example.com", password_hash="x", role=Role.OWNER,
        full_name="First", phone=None, public_slug="joao-da-silva",
    ).value
    await user_repo.add(existing)

    cmd = RegisterUserCommand(
        email="o@example.com",
        password="senha-forte-1",
        role=Role.OWNER,
        full_name="João da Silva",
        phone=None,
    )
    r = await handler.handle(cmd)
    assert r.is_success
    user = await user_repo.get_by_id(r.value.id)
    assert user.public_slug.value == "joao-da-silva-2"


@pytest.mark.asyncio
async def test_customer_registration_no_slug(
    user_repo, sub_repo, hasher, settings,
):
    handler = RegisterUserHandler(user_repo, hasher, sub_repo, settings)
    cmd = RegisterUserCommand(
        email="c@example.com",
        password="senha-forte-1",
        role=Role.CUSTOMER,
        full_name="Bruno Lima",
        phone=None,
    )
    r = await handler.handle(cmd)
    assert r.is_success
    user = await user_repo.get_by_id(r.value.id)
    assert user.public_slug is None
```

(If the existing test file uses fixtures with different names, adapt to match. The fakes used must support `get_by_public_slug` and `list_by_ids` — extend `InMemoryUserRepository` if needed.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/unit/use_cases/accounts/commands/test_register_user.py -v`
Expected: New tests FAIL — handler doesn't generate slug.

- [ ] **Step 3: Add a slugify helper**

Create `app/use_cases/accounts/commands/_slugify.py` (or place inline in the handler if preferred):

```python
from __future__ import annotations
import re
import unicodedata
from uuid import uuid4


_NON_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(raw: str) -> str:
    """Return a kebab-case slug derived from `raw`. Always returns a non-empty
    Slug-VO-valid string (length >= 2, starts with a letter or digit).
    """
    s = unicodedata.normalize("NFKD", raw).encode("ascii", "ignore").decode("ascii")
    s = s.lower()
    s = _NON_SLUG_RE.sub("-", s).strip("-")
    s = re.sub(r"-{2,}", "-", s)
    # Slug VO requires ^[a-z][a-z0-9-]*[a-z0-9]$ — must start with a letter.
    if not s or len(s) < 2 or not s[0].isalpha():
        s = f"u-{uuid4().hex[:8]}"
    return s
```

- [ ] **Step 4: Modify `RegisterUserHandler`**

Update `app/use_cases/accounts/commands/register_user.py`:

- Import: `from app.use_cases.accounts.commands._slugify import slugify`.
- Import: `from app.domain.shared.value_objects.slug import Slug`.
- Add a constant: `MAX_SLUG_RETRIES = 5`.
- Modify `handle` to generate the slug for OWNER. Insert this block **before** the `User.create(...)` call:

```python
        public_slug: str | None = None
        if cmd.role is Role.OWNER:
            base = slugify(cmd.full_name)
            candidate = base
            for attempt in range(MAX_SLUG_RETRIES):
                existing = await self._users.get_by_public_slug(candidate)
                if existing is None:
                    public_slug = candidate
                    break
                candidate = f"{base}-{attempt + 2}"
            if public_slug is None:
                return Result.failure(
                    "PublicSlugAlreadyTaken", status_code=409,
                )
```

- Pass `public_slug=public_slug` into `User.create(...)`.

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/unit/use_cases/accounts/commands/test_register_user.py -v`
Expected: existing PASS + 3 new PASS.

- [ ] **Step 6: Commit**

```bash
git add app/use_cases/accounts/commands/_slugify.py app/use_cases/accounts/commands/register_user.py tests/unit/use_cases/accounts/commands/test_register_user.py
git commit -m "$(cat <<'EOF'
feat(accounts): RegisterUserHandler generates owner public_slug

Slugify(full_name) with linear suffix collision-resolution; 5 retry
budget then PublicSlugAlreadyTaken (409). CUSTOMER/ADMIN registrations
still leave public_slug=None per User cross-field invariant.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 14: Subscription repo `list_by_owner_ids` batch helper

**Files:**
- Modify: `app/domain/subscriptions/repository.py`
- Modify: `app/infrastructure/repositories/owner_subscription_repository.py`
- Modify: `tests/integration/subscriptions/test_owner_subscription_repository.py`

- [ ] **Step 1: Add the failing integration test**

Append to `tests/integration/subscriptions/test_owner_subscription_repository.py`:

```python
@pytest.mark.asyncio
async def test_list_by_owner_ids(db_session):
    repo = SQLAlchemyOwnerSubscriptionRepository(db_session)
    a_id, b_id, c_id = uuid4(), uuid4(), uuid4()
    sub_a = OwnerSubscription.create_trialing(
        owner_id=a_id, trial_duration_days=3, now=_now(),
    ).value
    sub_b = OwnerSubscription.create_trialing(
        owner_id=b_id, trial_duration_days=3, now=_now(),
    ).value
    await repo.add(sub_a)
    await repo.add(sub_b)
    await db_session.flush()

    found = await repo.list_by_owner_ids([a_id, b_id, c_id])
    assert {s.owner_id for s in found} == {a_id, b_id}

    empty = await repo.list_by_owner_ids([])
    assert empty == []
```

(Adapt imports / fixture names to existing file. `_now()` is the helper already used in that test file.)

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/integration/subscriptions/test_owner_subscription_repository.py::test_list_by_owner_ids -v`
Expected: `AttributeError: ... has no attribute 'list_by_owner_ids'`.

- [ ] **Step 3: Implement the method**

Modify `app/domain/subscriptions/repository.py` — add to the `ISubscriptionRepository` Protocol:

```python
    async def list_by_owner_ids(
        self, owner_ids: Iterable[UUID],
    ) -> list[OwnerSubscription]: ...
```

Add `Iterable` to imports.

Modify `app/infrastructure/repositories/owner_subscription_repository.py` — add the method to `SQLAlchemyOwnerSubscriptionRepository`:

```python
    async def list_by_owner_ids(self, owner_ids):
        ids_list = [str(i) for i in owner_ids]
        if not ids_list:
            return []
        stmt = select(OwnerSubscriptionModel).where(
            OwnerSubscriptionModel.owner_id.in_(ids_list),
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_entity(r) for r in rows]
```

Modify `tests/unit/use_cases/subscriptions/fakes/in_memory_subscription_repository.py` — add the same method to `InMemorySubscriptionRepository`:

```python
    async def list_by_owner_ids(self, owner_ids):
        ids_set = set(owner_ids)
        return [s for s in self._by_id.values() if s.owner_id in ids_set]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/integration/subscriptions/test_owner_subscription_repository.py tests/unit/use_cases/subscriptions/ -v`
Expected: existing PASS + new test PASS.

- [ ] **Step 5: Commit**

```bash
git add app/domain/subscriptions/repository.py app/infrastructure/repositories/owner_subscription_repository.py tests/unit/use_cases/subscriptions/fakes/in_memory_subscription_repository.py tests/integration/subscriptions/test_owner_subscription_repository.py
git commit -m "$(cat <<'EOF'
feat(subscriptions): list_by_owner_ids batch helper

Used by ListPublicResourcesHandler to compute the operational owner
allow-list once per request without N+1 queries. Both SQLAlchemy and
in-memory implementations updated.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 15: `ResourceModel` mapping + Alembic migration

**Files:**
- Create: `app/infrastructure/db/mappings/resource.py`
- Modify: `app/migrations/env.py`
- Create: `app/migrations/versions/<ts>_resources_table.py` (via Alembic)

- [ ] **Step 1: Write the SQLAlchemy mapping**

Create `app/infrastructure/db/mappings/resource.py`:

```python
from __future__ import annotations
from datetime import datetime
from uuid import UUID

from sqlalchemy import BigInteger, Boolean, ForeignKey, Index, Integer, JSON, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import CHAR, DateTime

from app.infrastructure.db.base import Base, TimestampMixin


class ResourceModel(Base, TimestampMixin):
    __tablename__ = "resources"
    __table_args__ = (
        UniqueConstraint("owner_id", "slug", name="uq_resources_owner_slug"),
        Index("idx_resources_published", "is_published", "deleted_at"),
        Index("idx_resources_owner", "owner_id"),
        Index("idx_resources_type", "resource_type_id"),
    )

    id: Mapped[UUID] = mapped_column(CHAR(36), primary_key=True)
    owner_id: Mapped[UUID] = mapped_column(
        CHAR(36),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    resource_type_id: Mapped[UUID] = mapped_column(
        CHAR(36),
        ForeignKey("resource_types.id", ondelete="RESTRICT"),
        nullable=False,
    )

    slug: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    city: Mapped[str] = mapped_column(Text, nullable=False)
    region: Mapped[str] = mapped_column(Text, nullable=False)
    timezone: Mapped[str] = mapped_column(Text, nullable=False)
    slot_duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    base_price_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    customer_cancellation_cutoff_hours: Mapped[int] = mapped_column(Integer, nullable=False)

    operating_hours: Mapped[dict] = mapped_column(JSON, nullable=False)
    pricing_rules: Mapped[list] = mapped_column(JSON, nullable=False)
    custom_attributes: Mapped[list] = mapped_column(JSON, nullable=False)
    base_attributes: Mapped[dict] = mapped_column(JSON, nullable=False)

    is_published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

- [ ] **Step 2: Register the mapping in env.py**

Modify `app/migrations/env.py`. Add the import alongside the others:

```python
from app.infrastructure.db.mappings import resource  # noqa: F401
```

- [ ] **Step 3: Generate the migration**

Run:

```bash
make migrate-new msg="resources table"
```

Expected: a new file `app/migrations/versions/<timestamp>_resources_table.py` is created with `op.create_table("resources", ...)` containing all columns + indexes + unique constraint + foreign keys.

Inspect the generated file. If Alembic auto-generated the JSON columns as `sa.JSON()` — fine. If it missed any constraint (UniqueConstraint, Index), edit the migration to add them inside `upgrade()`.

- [ ] **Step 4: Apply the migration**

Run:

```bash
make migrate-up
```

Expected: clean apply on dev DB.

- [ ] **Step 5: Sanity-check round-trip**

Run a quick Python REPL probe:

```bash
.venv/bin/python -c "
from sqlalchemy import inspect
from app.infrastructure.db.base import Base
from app.infrastructure.db.mappings.resource import ResourceModel
print(ResourceModel.__tablename__)
print([c.name for c in ResourceModel.__table__.columns])
"
```

Expected: prints `resources` and the full column list.

- [ ] **Step 6: Commit**

```bash
git add app/infrastructure/db/mappings/resource.py app/migrations/env.py app/migrations/versions/*resources_table.py
git commit -m "$(cat <<'EOF'
feat(resources): ResourceModel + Alembic migration

One row per resource. Composite VOs (operating_hours, pricing_rules,
custom_attributes, base_attributes) live as JSON columns. UNIQUE
(owner_id, slug) implements per-owner slug. RESTRICT FKs on owner +
resource_type so neither can be hard-deleted while resources reference
them.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 16: `SQLAlchemyResourceRepository` (CRUD + integration tests)

**Files:**
- Create: `app/infrastructure/repositories/resource_repository.py`
- Test: `tests/integration/resources/__init__.py` (empty)
- Test: `tests/integration/resources/test_resource_repository.py`

- [ ] **Step 1: Write the failing integration tests**

Create `tests/integration/resources/__init__.py` (empty).

Create `tests/integration/resources/test_resource_repository.py`:

```python
from __future__ import annotations
from datetime import datetime, time, timezone
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.accounts.role import Role
from app.domain.accounts.user import User
from app.domain.catalog.resource_type import ResourceType
from app.domain.resources.custom_attribute import CustomAttribute
from app.domain.resources.pricing_rule import PricingRule
from app.domain.resources.resource import Resource
from app.domain.resources.weekly_schedule import WeeklySchedule
from app.domain.shared.value_objects.money import Money
from app.domain.shared.value_objects.time_window import TimeWindow
from app.domain.shared.weekday import Weekday
from app.infrastructure.repositories.resource_repository import SQLAlchemyResourceRepository
from app.infrastructure.repositories.resource_type_repository import SQLAlchemyResourceTypeRepository
from app.infrastructure.repositories.user_repository import UserRepository


def _w(sh: int, eh: int) -> TimeWindow:
    return TimeWindow.create(time(sh, 0), time(eh, 0)).value


def _ws() -> WeeklySchedule:
    return WeeklySchedule.create(
        slot_duration_minutes=60,
        days={Weekday.MONDAY: [_w(8, 22)]},
    ).value


async def _seed_owner_and_type(db_session: AsyncSession) -> tuple[User, ResourceType]:
    users = UserRepository(db_session)
    rts = SQLAlchemyResourceTypeRepository(db_session)
    owner = User.create(
        email=f"{uuid4().hex}@example.com", password_hash="x", role=Role.OWNER,
        full_name="Owner Name", phone=None, public_slug=f"owner-{uuid4().hex[:6]}",
    ).value
    await users.add(owner)
    rt = ResourceType.create(
        slug=f"type-{uuid4().hex[:6]}", name="Type", description="",
        attribute_schema=[],
    ).value
    await rts.add(rt)
    await db_session.flush()
    return owner, rt


def _make_resource(owner_id, rt_id, slug="arena-x") -> Resource:
    return Resource.create(
        owner_id=owner_id,
        resource_type_id=rt_id,
        slug=slug,
        name="Arena X",
        description="campo society",
        city="São Paulo",
        region="SP",
        timezone="America/Sao_Paulo",
        slot_duration_minutes=60,
        operating_hours=_ws(),
        base_price_cents=8000,
        customer_cancellation_cutoff_hours=24,
        base_attributes={},
        pricing_rules=[],
        custom_attributes=[],
    ).value


@pytest.mark.asyncio
async def test_add_and_get_by_id(db_session: AsyncSession):
    owner, rt = await _seed_owner_and_type(db_session)
    repo = SQLAlchemyResourceRepository(db_session)
    res = _make_resource(owner.id, rt.id)
    add_r = await repo.add(res)
    assert add_r.is_success
    await db_session.flush()

    fetched = await repo.get_by_id(res.id)
    assert fetched is not None
    assert fetched.slug.value == "arena-x"
    assert fetched.owner_id == owner.id


@pytest.mark.asyncio
async def test_unique_owner_slug_constraint(db_session: AsyncSession):
    owner, rt = await _seed_owner_and_type(db_session)
    repo = SQLAlchemyResourceRepository(db_session)
    a = _make_resource(owner.id, rt.id, slug="arena-zl")
    b = _make_resource(owner.id, rt.id, slug="arena-zl")
    assert (await repo.add(a)).is_success
    await db_session.flush()
    r = await repo.add(b)
    assert r.is_failure
    assert r.error == "SlugAlreadyTaken"


@pytest.mark.asyncio
async def test_two_owners_can_share_slug(db_session: AsyncSession):
    owner_a, rt = await _seed_owner_and_type(db_session)
    owner_b, _ = await _seed_owner_and_type(db_session)
    repo = SQLAlchemyResourceRepository(db_session)
    a = _make_resource(owner_a.id, rt.id, slug="arena")
    b = _make_resource(owner_b.id, rt.id, slug="arena")
    assert (await repo.add(a)).is_success
    assert (await repo.add(b)).is_success
    await db_session.flush()


@pytest.mark.asyncio
async def test_round_trip_composites(db_session: AsyncSession):
    owner, rt = await _seed_owner_and_type(db_session)
    repo = SQLAlchemyResourceRepository(db_session)
    rule = PricingRule.create(
        weekdays=[Weekday.FRIDAY], window=_w(18, 22), price=Money.create(12000).value,
    ).value
    custom = CustomAttribute.create(key="wifi", label="Wi-Fi", value="sim").value
    res = Resource.create(
        owner_id=owner.id, resource_type_id=rt.id,
        slug="arena-rt", name="Arena RT", description="",
        city="São Paulo", region="SP", timezone="America/Sao_Paulo",
        slot_duration_minutes=60,
        operating_hours=WeeklySchedule.create(
            slot_duration_minutes=60,
            days={Weekday.FRIDAY: [_w(8, 23)]},
        ).value,
        base_price_cents=8000, customer_cancellation_cutoff_hours=24,
        base_attributes={"surface_type": "GRASS"},
        pricing_rules=[rule],
        custom_attributes=[custom],
    ).value
    await repo.add(res)
    await db_session.flush()

    fetched = await repo.get_by_id(res.id)
    assert fetched.pricing_rules[0].price.cents == 12000
    assert fetched.custom_attributes[0].key.value == "wifi"
    assert fetched.base_attributes == {"surface_type": "GRASS"}
    assert fetched.operating_hours.for_weekday(Weekday.FRIDAY)[0].start == time(8, 0)


@pytest.mark.asyncio
async def test_list_published_excludes_deleted_and_unpublished(db_session: AsyncSession):
    owner, rt = await _seed_owner_and_type(db_session)
    repo = SQLAlchemyResourceRepository(db_session)

    draft = _make_resource(owner.id, rt.id, slug="draft")  # not published
    published = _make_resource(owner.id, rt.id, slug="public")
    published.publish()
    deleted = _make_resource(owner.id, rt.id, slug="deleted")
    deleted.publish()
    deleted.soft_delete(now=datetime.now(timezone.utc))

    for r in (draft, published, deleted):
        await repo.add(r)
    await db_session.flush()
    for r in (draft, published, deleted):
        await repo.update(r)
    await db_session.flush()

    listed = await repo.list_published()
    slugs = {r.slug.value for r in listed}
    assert "public" in slugs
    assert "draft" not in slugs
    assert "deleted" not in slugs


@pytest.mark.asyncio
async def test_list_published_filters_by_owner_ids(db_session: AsyncSession):
    owner_a, rt = await _seed_owner_and_type(db_session)
    owner_b, _ = await _seed_owner_and_type(db_session)
    repo = SQLAlchemyResourceRepository(db_session)
    ra = _make_resource(owner_a.id, rt.id, slug="from-a")
    ra.publish()
    rb = _make_resource(owner_b.id, rt.id, slug="from-b")
    rb.publish()
    for r in (ra, rb):
        await repo.add(r)
    await db_session.flush()
    for r in (ra, rb):
        await repo.update(r)
    await db_session.flush()

    listed = await repo.list_published(owner_ids_filter=[owner_a.id])
    slugs = {r.slug.value for r in listed}
    assert slugs == {"from-a"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/integration/resources/test_resource_repository.py -v`
Expected: ImportError on `SQLAlchemyResourceRepository`.

- [ ] **Step 3: Implement the repository**

Create `app/infrastructure/repositories/resource_repository.py`:

```python
from __future__ import annotations
from datetime import datetime, time, timezone
from typing import Iterable
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.resources.custom_attribute import CustomAttribute
from app.domain.resources.pricing_rule import PricingRule
from app.domain.resources.repository import IResourceRepository
from app.domain.resources.resource import Resource
from app.domain.resources.weekly_schedule import WeeklySchedule
from app.domain.shared.result import Result
from app.domain.shared.value_objects.attribute_key import AttributeKey
from app.domain.shared.value_objects.cancellation_cutoff import CancellationCutoff
from app.domain.shared.value_objects.iana_timezone import IanaTimezone
from app.domain.shared.value_objects.money import Money
from app.domain.shared.value_objects.name import Name
from app.domain.shared.value_objects.short_description import ShortDescription
from app.domain.shared.value_objects.short_name import ShortName
from app.domain.shared.value_objects.slot_duration import SlotDuration
from app.domain.shared.value_objects.slug import Slug
from app.domain.shared.value_objects.time_window import TimeWindow
from app.domain.shared.weekday import Weekday
from app.infrastructure.db.mappings.resource import ResourceModel


def _ensure_utc(dt: datetime | None) -> datetime | None:
    """SQLite + aiosqlite drop tzinfo on roundtrip; assume stored values are UTC."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _time_to_str(t: time) -> str:
    return f"{t.hour:02d}:{t.minute:02d}"


def _str_to_time(s: str) -> time:
    h, m = s.split(":")
    return time(int(h), int(m))


def _serialize_schedule(ws: WeeklySchedule) -> dict:
    return {
        wd.value.lower(): [
            {"start": _time_to_str(w.start), "end": _time_to_str(w.end)}
            for w in ws.for_weekday(wd)
        ]
        for wd in Weekday
    }


def _deserialize_schedule(payload: dict) -> WeeklySchedule:
    fields: dict[str, tuple[TimeWindow, ...]] = {}
    for wd in Weekday:
        windows_payload = payload.get(wd.value.lower(), [])
        windows = tuple(
            TimeWindow(start=_str_to_time(w["start"]), end=_str_to_time(w["end"]))
            for w in windows_payload
        )
        fields[wd.value.lower()] = windows
    return WeeklySchedule(**fields)


def _serialize_pricing_rules(rules: tuple[PricingRule, ...]) -> list[dict]:
    return [
        {
            "weekdays": sorted(wd.value for wd in r.weekdays),
            "window": {"start": _time_to_str(r.window.start), "end": _time_to_str(r.window.end)},
            "price_cents": r.price.cents,
        }
        for r in rules
    ]


def _deserialize_pricing_rules(payload: list[dict]) -> list[PricingRule]:
    return [
        PricingRule(
            weekdays=frozenset(Weekday(w) for w in r["weekdays"]),
            window=TimeWindow(
                start=_str_to_time(r["window"]["start"]),
                end=_str_to_time(r["window"]["end"]),
            ),
            price=Money(cents=r["price_cents"]),
        )
        for r in payload
    ]


def _serialize_custom_attrs(attrs: tuple[CustomAttribute, ...]) -> list[dict]:
    return [
        {"key": a.key.value, "label": a.label.value, "value": a.value.value}
        for a in attrs
    ]


def _deserialize_custom_attrs(payload: list[dict]) -> list[CustomAttribute]:
    return [
        CustomAttribute(
            key=AttributeKey(value=a["key"]),
            label=ShortName(value=a["label"]),
            value=ShortDescription(value=a["value"]),
        )
        for a in payload
    ]


def _to_entity(model: ResourceModel) -> Resource:
    res = Resource(
        id=UUID(str(model.id)),
        owner_id=UUID(str(model.owner_id)),
        resource_type_id=UUID(str(model.resource_type_id)),
        slug=Slug(value=model.slug),
        name=Name(value=model.name),
        description=ShortDescription(value=model.description),
        city=Name(value=model.city),
        region=Name(value=model.region),
        timezone=IanaTimezone(value=model.timezone),
        slot_duration_minutes=SlotDuration(minutes=model.slot_duration_minutes),
        operating_hours=_deserialize_schedule(model.operating_hours),
        base_price_cents=Money(cents=model.base_price_cents),
        customer_cancellation_cutoff_hours=CancellationCutoff(hours=model.customer_cancellation_cutoff_hours),
        base_attributes=dict(model.base_attributes or {}),
        is_published=model.is_published,
        deleted_at=_ensure_utc(model.deleted_at),
        _pricing_rules=_deserialize_pricing_rules(model.pricing_rules or []),
        _custom_attributes=_deserialize_custom_attrs(model.custom_attributes or []),
    )
    res.created_at = _ensure_utc(model.created_at)
    res.updated_at = _ensure_utc(model.updated_at)
    return res


def _to_model_kwargs(res: Resource) -> dict:
    return {
        "id": str(res.id),
        "owner_id": str(res.owner_id),
        "resource_type_id": str(res.resource_type_id),
        "slug": res.slug.value,
        "name": res.name.value,
        "description": res.description.value,
        "city": res.city.value,
        "region": res.region.value,
        "timezone": res.timezone.value,
        "slot_duration_minutes": res.slot_duration_minutes.minutes,
        "base_price_cents": res.base_price_cents.cents,
        "customer_cancellation_cutoff_hours": res.customer_cancellation_cutoff_hours.hours,
        "operating_hours": _serialize_schedule(res.operating_hours),
        "pricing_rules": _serialize_pricing_rules(res.pricing_rules),
        "custom_attributes": _serialize_custom_attrs(res.custom_attributes),
        "base_attributes": dict(res.base_attributes),
        "is_published": res.is_published,
        "deleted_at": res.deleted_at,
        "created_at": res.created_at,
        "updated_at": res.updated_at,
    }


class SQLAlchemyResourceRepository(IResourceRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def add(self, resource: Resource) -> Result[None]:
        model = ResourceModel(**_to_model_kwargs(resource))
        self._session.add(model)
        try:
            await self._session.flush()
        except IntegrityError:
            await self._session.rollback()
            return Result.failure("SlugAlreadyTaken", status_code=409)
        return Result.success(None)

    async def update(self, resource: Resource) -> Result[None]:
        stmt = select(ResourceModel).where(ResourceModel.id == str(resource.id))
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        if row is None:
            return Result.failure("ResourceNotFound", status_code=404)
        kwargs = _to_model_kwargs(resource)
        for k, v in kwargs.items():
            if k == "id":
                continue
            setattr(row, k, v)
        await self._session.flush()
        return Result.success(None)

    async def get_by_id(self, resource_id: UUID) -> Resource | None:
        stmt = select(ResourceModel).where(ResourceModel.id == str(resource_id))
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return _to_entity(row) if row else None

    async def get_by_owner_and_slug(self, owner_id: UUID, slug: str) -> Resource | None:
        stmt = select(ResourceModel).where(
            ResourceModel.owner_id == str(owner_id),
            ResourceModel.slug == slug,
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return _to_entity(row) if row else None

    async def list_by_owner(
        self, owner_id, *, include_deleted=False, limit=50, offset=0,
    ):
        stmt = select(ResourceModel).where(ResourceModel.owner_id == str(owner_id))
        if not include_deleted:
            stmt = stmt.where(ResourceModel.deleted_at.is_(None))
        stmt = stmt.order_by(ResourceModel.created_at.desc()).limit(limit).offset(offset)
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_entity(r) for r in rows]

    async def list_published(
        self,
        *,
        resource_type_slug: str | None = None,
        city: str | None = None,
        region: str | None = None,
        owner_ids_filter: Iterable[UUID] | None = None,
        limit: int = 50,
        offset: int = 0,
    ):
        stmt = select(ResourceModel).where(
            ResourceModel.is_published.is_(True),
            ResourceModel.deleted_at.is_(None),
        )
        if city is not None:
            stmt = stmt.where(ResourceModel.city == city)
        if region is not None:
            stmt = stmt.where(ResourceModel.region == region)
        if owner_ids_filter is not None:
            ids_list = [str(i) for i in owner_ids_filter]
            if not ids_list:
                return []
            stmt = stmt.where(ResourceModel.owner_id.in_(ids_list))
        if resource_type_slug is not None:
            # Join through ResourceTypeModel table to filter by slug.
            from app.infrastructure.db.mappings.resource_type import ResourceTypeModel
            stmt = stmt.join(
                ResourceTypeModel,
                ResourceTypeModel.id == ResourceModel.resource_type_id,
            ).where(ResourceTypeModel.slug == resource_type_slug)
        stmt = stmt.order_by(ResourceModel.created_at.desc()).limit(limit).offset(offset)
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_entity(r) for r in rows]

    async def list_published_by_owner(self, owner_id, *, limit=50, offset=0):
        stmt = (
            select(ResourceModel)
            .where(
                ResourceModel.owner_id == str(owner_id),
                ResourceModel.is_published.is_(True),
                ResourceModel.deleted_at.is_(None),
            )
            .order_by(ResourceModel.created_at.desc())
            .limit(limit).offset(offset)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_entity(r) for r in rows]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/integration/resources/ -v`
Expected: 6 PASS.

- [ ] **Step 5: Commit**

```bash
git add app/infrastructure/repositories/resource_repository.py tests/integration/resources/__init__.py tests/integration/resources/test_resource_repository.py
git commit -m "$(cat <<'EOF'
feat(resources): SQLAlchemyResourceRepository

CRUD + per-owner slug constraint + list_published with optional
type/city/region/owner_ids_filter filters. JSON serialization for the
three composite VOs (operating_hours, pricing_rules, custom_attributes)
plus base_attributes. _ensure_utc helper applied to deleted_at and
timestamps for SQLite tz-roundtrip compatibility.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 17: Resource DTOs + `_common.load_owned_resource` helper

**Files:**
- Create: `app/use_cases/resources/__init__.py` (empty)
- Create: `app/use_cases/resources/dtos.py`
- Create: `app/use_cases/resources/_common.py`

- [ ] **Step 1: Write the DTOs (no test — these are pure data classes; tests come with handler tests)**

Create `app/use_cases/resources/__init__.py` (empty).

Create `app/use_cases/resources/dtos.py`:

```python
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Self
from uuid import UUID

from app.domain.resources.resource import Resource


@dataclass(frozen=True, slots=True)
class TimeWindowDto:
    start: str  # "HH:MM"
    end: str


@dataclass(frozen=True, slots=True)
class WeeklyScheduleDto:
    monday: list[TimeWindowDto]
    tuesday: list[TimeWindowDto]
    wednesday: list[TimeWindowDto]
    thursday: list[TimeWindowDto]
    friday: list[TimeWindowDto]
    saturday: list[TimeWindowDto]
    sunday: list[TimeWindowDto]


@dataclass(frozen=True, slots=True)
class PricingRuleDto:
    weekdays: list[str]
    window: TimeWindowDto
    price_cents: int


@dataclass(frozen=True, slots=True)
class CustomAttributeDto:
    key: str
    label: str
    value: str


@dataclass(frozen=True, slots=True)
class ResourceDto:
    id: UUID
    owner_id: UUID
    owner_slug: str
    resource_type_id: UUID
    resource_type_slug: str
    slug: str
    name: str
    description: str
    city: str
    region: str
    timezone: str
    slot_duration_minutes: int
    operating_hours: WeeklyScheduleDto
    pricing_rules: list[PricingRuleDto]
    base_price_cents: int
    customer_cancellation_cutoff_hours: int
    base_attributes: dict[str, Any]
    custom_attributes: list[CustomAttributeDto]
    is_published: bool
    deleted_at: datetime | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_entity(
        cls,
        res: Resource,
        *,
        owner_slug: str,
        resource_type_slug: str,
    ) -> Self:
        def _t(t):
            return f"{t.hour:02d}:{t.minute:02d}"

        from app.domain.shared.weekday import Weekday
        sched = WeeklyScheduleDto(
            **{
                wd.value.lower(): [
                    TimeWindowDto(start=_t(w.start), end=_t(w.end))
                    for w in res.operating_hours.for_weekday(wd)
                ]
                for wd in Weekday
            }
        )
        return cls(
            id=res.id,
            owner_id=res.owner_id,
            owner_slug=owner_slug,
            resource_type_id=res.resource_type_id,
            resource_type_slug=resource_type_slug,
            slug=res.slug.value,
            name=res.name.value,
            description=res.description.value,
            city=res.city.value,
            region=res.region.value,
            timezone=res.timezone.value,
            slot_duration_minutes=res.slot_duration_minutes.minutes,
            operating_hours=sched,
            pricing_rules=[
                PricingRuleDto(
                    weekdays=sorted(w.value for w in r.weekdays),
                    window=TimeWindowDto(start=_t(r.window.start), end=_t(r.window.end)),
                    price_cents=r.price.cents,
                )
                for r in res.pricing_rules
            ],
            base_price_cents=res.base_price_cents.cents,
            customer_cancellation_cutoff_hours=res.customer_cancellation_cutoff_hours.hours,
            base_attributes=dict(res.base_attributes),
            custom_attributes=[
                CustomAttributeDto(key=a.key.value, label=a.label.value, value=a.value.value)
                for a in res.custom_attributes
            ],
            is_published=res.is_published,
            deleted_at=res.deleted_at,
            created_at=res.created_at,
            updated_at=res.updated_at,
        )
```

Create `app/use_cases/resources/_common.py`:

```python
from __future__ import annotations
from typing import Awaitable, Callable
from uuid import UUID

from app.domain.resources.repository import IResourceRepository
from app.domain.resources.resource import Resource
from app.domain.shared.result import Result


async def load_owned_resource(
    repo: IResourceRepository,
    *,
    resource_id: UUID,
    actor_id: UUID,
) -> Result[Resource]:
    """Load a Resource and confirm `actor_id` owns it.

    Returns ResourceNotFound (404) for: missing, owned-by-someone-else,
    or already-deleted resources. Treating the three cases identically
    avoids leaking existence to non-owners.
    """
    res = await repo.get_by_id(resource_id)
    if res is None or res.owner_id != actor_id or res.is_deleted():
        return Result.failure("ResourceNotFound", status_code=404)
    return Result.success(res)
```

- [ ] **Step 2: Sanity-import**

Run:

```bash
.venv/bin/python -c "from app.use_cases.resources.dtos import ResourceDto; print(ResourceDto)"
.venv/bin/python -c "from app.use_cases.resources._common import load_owned_resource; print(load_owned_resource)"
```

Expected: prints both objects.

- [ ] **Step 3: Commit**

```bash
git add app/use_cases/resources/__init__.py app/use_cases/resources/dtos.py app/use_cases/resources/_common.py
git commit -m "$(cat <<'EOF'
feat(resources): use_cases DTOs + load_owned_resource helper

ResourceDto.from_entity needs owner_slug + resource_type_slug joined
in by handlers (the entity doesn't carry them). load_owned_resource is
the shared 404-on-mismatch ownership pattern used by every owner-scoped
command and query.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 18: `InMemoryResourceRepository` + `InMemoryResourceTypeRepository` for handler tests

**Files:**
- Create: `tests/unit/use_cases/resources/__init__.py` (empty)
- Create: `tests/unit/use_cases/resources/fakes/__init__.py` (empty)
- Create: `tests/unit/use_cases/resources/fakes/in_memory_resource_repository.py`

- [ ] **Step 1: Write the in-memory fake**

Create `tests/unit/use_cases/resources/fakes/in_memory_resource_repository.py`:

```python
from __future__ import annotations
from typing import Iterable
from uuid import UUID

from app.domain.resources.repository import IResourceRepository
from app.domain.resources.resource import Resource
from app.domain.shared.result import Result


class InMemoryResourceRepository(IResourceRepository):
    def __init__(self) -> None:
        self._items: dict[UUID, Resource] = {}

    async def add(self, resource: Resource) -> Result[None]:
        for existing in self._items.values():
            if existing.owner_id == resource.owner_id and existing.slug.value == resource.slug.value:
                return Result.failure("SlugAlreadyTaken", status_code=409)
        self._items[resource.id] = resource
        return Result.success(None)

    async def update(self, resource: Resource) -> Result[None]:
        if resource.id not in self._items:
            return Result.failure("ResourceNotFound", status_code=404)
        self._items[resource.id] = resource
        return Result.success(None)

    async def get_by_id(self, resource_id: UUID) -> Resource | None:
        return self._items.get(resource_id)

    async def get_by_owner_and_slug(self, owner_id, slug):
        for r in self._items.values():
            if r.owner_id == owner_id and r.slug.value == slug:
                return r
        return None

    async def list_by_owner(
        self, owner_id, *, include_deleted=False, limit=50, offset=0,
    ):
        items = [r for r in self._items.values() if r.owner_id == owner_id]
        if not include_deleted:
            items = [r for r in items if not r.is_deleted()]
        items.sort(key=lambda r: r.created_at, reverse=True)
        return items[offset:offset + limit]

    async def list_published(
        self,
        *,
        resource_type_slug: str | None = None,
        city: str | None = None,
        region: str | None = None,
        owner_ids_filter: Iterable[UUID] | None = None,
        limit: int = 50,
        offset: int = 0,
    ):
        items = [r for r in self._items.values() if r.is_published and not r.is_deleted()]
        if city is not None:
            items = [r for r in items if r.city.value == city]
        if region is not None:
            items = [r for r in items if r.region.value == region]
        if owner_ids_filter is not None:
            allow = set(owner_ids_filter)
            items = [r for r in items if r.owner_id in allow]
        # resource_type_slug filter is handled via cross-feature lookup; the
        # handler tests for ListPublicResourcesHandler don't use this filter
        # directly. Tests that need it can extend by injecting a fake
        # ResourceTypeRepository alongside.
        items.sort(key=lambda r: r.created_at, reverse=True)
        return items[offset:offset + limit]

    async def list_published_by_owner(self, owner_id, *, limit=50, offset=0):
        items = [
            r for r in self._items.values()
            if r.owner_id == owner_id and r.is_published and not r.is_deleted()
        ]
        items.sort(key=lambda r: r.created_at, reverse=True)
        return items[offset:offset + limit]
```

- [ ] **Step 2: Sanity-import**

Run: `.venv/bin/python -c "from tests.unit.use_cases.resources.fakes.in_memory_resource_repository import InMemoryResourceRepository; print(InMemoryResourceRepository)"`
Expected: prints class.

- [ ] **Step 3: Commit**

```bash
git add tests/unit/use_cases/resources/__init__.py tests/unit/use_cases/resources/fakes/__init__.py tests/unit/use_cases/resources/fakes/in_memory_resource_repository.py
git commit -m "$(cat <<'EOF'
test(resources): in-memory InMemoryResourceRepository

Mirrors the IResourceRepository contract for handler unit tests.
Implements (owner_id, slug) uniqueness and the list-published filters
without depending on SQL.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 19: `CreateResourceHandler`

**Files:**
- Create: `app/use_cases/resources/commands/__init__.py` (empty)
- Create: `app/use_cases/resources/commands/create_resource.py`
- Create: `tests/unit/use_cases/resources/commands/__init__.py` (empty)
- Test: `tests/unit/use_cases/resources/commands/test_create_resource.py`

- [ ] **Step 1: Write the failing tests**

Create both `__init__.py` empties.

Create `tests/unit/use_cases/resources/commands/test_create_resource.py`:

```python
from __future__ import annotations
from datetime import time
from uuid import uuid4

import pytest

from app.domain.accounts.role import Role
from app.domain.accounts.user import User
from app.domain.catalog.attribute import AttrType, AttributeDefinition
from app.domain.catalog.resource_type import ResourceType
from app.domain.shared.weekday import Weekday
from app.use_cases.resources.commands.create_resource import (
    CreateResourceCommand,
    CreateResourceHandler,
    PricingRuleInput,
    CustomAttributeInput,
    OperatingHoursInput,
    TimeWindowInput,
)
from tests.unit.use_cases.resources.fakes.in_memory_resource_repository import InMemoryResourceRepository
from tests.unit.use_cases.catalog.fakes.in_memory_resource_type_repository import (
    InMemoryResourceTypeRepository,
)
from tests.unit.use_cases.accounts.fakes.in_memory_user_repository import InMemoryUserRepository


def _hours_dict_full_open() -> dict[str, list[dict]]:
    return {wd.value.lower(): [{"start": "08:00", "end": "22:00"}] for wd in Weekday}


def _make_owner_and_type():
    owner = User.create(
        email="o@example.com", password_hash="x", role=Role.OWNER,
        full_name="O", phone=None, public_slug="o-owner",
    ).value
    rt = ResourceType.create(
        slug="football-field", name="Football", description="",
        attribute_schema=[
            AttributeDefinition.create(
                key="surface_type", label="Surface", data_type=AttrType.ENUM,
                required=True, enum_values=["GRASS", "SAND"],
            ).value,
        ],
    ).value
    return owner, rt


@pytest.mark.asyncio
async def test_create_resource_happy_path():
    owner, rt = _make_owner_and_type()
    users = InMemoryUserRepository()
    rts = InMemoryResourceTypeRepository()
    resources = InMemoryResourceRepository()
    await users.add(owner)
    await rts.add(rt)

    handler = CreateResourceHandler(resources, rts, users)
    cmd = CreateResourceCommand(
        actor_id=owner.id,
        resource_type_id=rt.id,
        slug="arena-zl",
        name="Arena ZL",
        description="campo society",
        city="São Paulo",
        region="SP",
        timezone="America/Sao_Paulo",
        slot_duration_minutes=60,
        operating_hours=OperatingHoursInput(
            days={Weekday.MONDAY: [TimeWindowInput(start="08:00", end="22:00")]},
        ),
        base_price_cents=8000,
        customer_cancellation_cutoff_hours=24,
        base_attributes={"surface_type": "GRASS"},
        pricing_rules=[],
        custom_attributes=[],
    )
    r = await handler.handle(cmd)
    assert r.is_success
    dto = r.value
    assert dto.slug == "arena-zl"
    assert dto.owner_slug == "o-owner"
    assert dto.resource_type_slug == "football-field"


@pytest.mark.asyncio
async def test_create_resource_validates_base_attributes_against_schema():
    owner, rt = _make_owner_and_type()
    users = InMemoryUserRepository()
    rts = InMemoryResourceTypeRepository()
    await users.add(owner)
    await rts.add(rt)
    handler = CreateResourceHandler(InMemoryResourceRepository(), rts, users)
    cmd = CreateResourceCommand(
        actor_id=owner.id,
        resource_type_id=rt.id,
        slug="arena",
        name="Arena",
        description="",
        city="SP",
        region="SP",
        timezone="America/Sao_Paulo",
        slot_duration_minutes=60,
        operating_hours=OperatingHoursInput(
            days={Weekday.MONDAY: [TimeWindowInput(start="08:00", end="22:00")]},
        ),
        base_price_cents=8000,
        customer_cancellation_cutoff_hours=24,
        base_attributes={},  # surface_type required by schema → should fail
        pricing_rules=[],
        custom_attributes=[],
    )
    r = await handler.handle(cmd)
    assert r.is_failure
    fields = {e.field for e in r.details}
    assert "base_attributes.surface_type" in fields


@pytest.mark.asyncio
async def test_create_resource_aggregates_resource_and_attribute_errors():
    owner, rt = _make_owner_and_type()
    users = InMemoryUserRepository()
    rts = InMemoryResourceTypeRepository()
    await users.add(owner)
    await rts.add(rt)
    handler = CreateResourceHandler(InMemoryResourceRepository(), rts, users)
    cmd = CreateResourceCommand(
        actor_id=owner.id,
        resource_type_id=rt.id,
        slug="UPPER!!!",   # invalid slug
        name="",            # invalid name
        description="",
        city="SP",
        region="SP",
        timezone="America/Sao_Paulo",
        slot_duration_minutes=60,
        operating_hours=OperatingHoursInput(
            days={Weekday.MONDAY: [TimeWindowInput(start="08:00", end="22:00")]},
        ),
        base_price_cents=8000,
        customer_cancellation_cutoff_hours=24,
        base_attributes={},  # missing required surface_type
        pricing_rules=[],
        custom_attributes=[],
    )
    r = await handler.handle(cmd)
    assert r.is_failure
    fields = {e.field for e in r.details}
    assert "slug" in fields
    assert "name" in fields
    assert "base_attributes.surface_type" in fields


@pytest.mark.asyncio
async def test_create_resource_rejects_inactive_resource_type():
    owner, rt = _make_owner_and_type()
    rt.deactivate()
    users = InMemoryUserRepository()
    rts = InMemoryResourceTypeRepository()
    await users.add(owner)
    await rts.add(rt)
    handler = CreateResourceHandler(InMemoryResourceRepository(), rts, users)
    cmd = CreateResourceCommand(
        actor_id=owner.id,
        resource_type_id=rt.id,
        slug="arena",
        name="Arena", description="",
        city="SP", region="SP",
        timezone="America/Sao_Paulo",
        slot_duration_minutes=60,
        operating_hours=OperatingHoursInput(days={}),
        base_price_cents=8000,
        customer_cancellation_cutoff_hours=24,
        base_attributes={"surface_type": "GRASS"},
        pricing_rules=[],
        custom_attributes=[],
    )
    r = await handler.handle(cmd)
    assert r.is_failure
    assert r.error == "ResourceTypeInactive"
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_create_resource_rejects_non_owner_actor():
    customer = User.create(
        email="c@example.com", password_hash="x", role=Role.CUSTOMER,
        full_name="C", phone=None, public_slug=None,
    ).value
    _, rt = _make_owner_and_type()
    users = InMemoryUserRepository()
    rts = InMemoryResourceTypeRepository()
    await users.add(customer)
    await rts.add(rt)
    handler = CreateResourceHandler(InMemoryResourceRepository(), rts, users)
    cmd = CreateResourceCommand(
        actor_id=customer.id,
        resource_type_id=rt.id,
        slug="arena",
        name="Arena", description="",
        city="SP", region="SP",
        timezone="America/Sao_Paulo",
        slot_duration_minutes=60,
        operating_hours=OperatingHoursInput(days={}),
        base_price_cents=8000,
        customer_cancellation_cutoff_hours=24,
        base_attributes={"surface_type": "GRASS"},
        pricing_rules=[],
        custom_attributes=[],
    )
    r = await handler.handle(cmd)
    assert r.is_failure
    assert r.error == "UserIsNotOwner"
    assert r.status_code == 403
```

(Note: `InMemoryResourceTypeRepository` and `InMemoryUserRepository` should already exist from Plans 04 and 02. If their interfaces don't yet expose `add` and `get_by_id`, extend them. If `InMemoryUserRepository` doesn't have `get_by_public_slug` or `list_by_ids`, extend it now — needed by later handler tests too.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/unit/use_cases/resources/commands/test_create_resource.py -v`
Expected: ImportError on `CreateResourceCommand`.

- [ ] **Step 3: Write the handler**

Create `app/use_cases/resources/commands/create_resource.py`:

```python
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from app.domain.accounts.repository import IUserRepository
from app.domain.accounts.role import Role
from app.domain.catalog.repository import IResourceTypeRepository
from app.domain.resources.custom_attribute import CustomAttribute
from app.domain.resources.pricing_rule import PricingRule
from app.domain.resources.repository import IResourceRepository
from app.domain.resources.resource import Resource
from app.domain.resources.weekly_schedule import WeeklySchedule
from app.domain.shared.field_error import FieldError
from app.domain.shared.result import Result
from app.domain.shared.value_objects.money import Money
from app.domain.shared.value_objects.time_window import TimeWindow
from app.domain.shared.weekday import Weekday
from app.use_cases.resources.dtos import ResourceDto


@dataclass(frozen=True, slots=True)
class TimeWindowInput:
    start: str  # "HH:MM"
    end: str


@dataclass(frozen=True, slots=True)
class OperatingHoursInput:
    days: dict[Weekday, list[TimeWindowInput]]


@dataclass(frozen=True, slots=True)
class PricingRuleInput:
    weekdays: list[Weekday]
    window: TimeWindowInput
    price_cents: int


@dataclass(frozen=True, slots=True)
class CustomAttributeInput:
    key: str
    label: str
    value: str


@dataclass(frozen=True, slots=True)
class CreateResourceCommand:
    actor_id: UUID
    resource_type_id: UUID
    slug: str
    name: str
    description: str
    city: str
    region: str
    timezone: str
    slot_duration_minutes: int
    operating_hours: OperatingHoursInput
    base_price_cents: int
    customer_cancellation_cutoff_hours: int
    base_attributes: dict[str, Any]
    pricing_rules: list[PricingRuleInput]
    custom_attributes: list[CustomAttributeInput]


def _parse_time_window(tw: TimeWindowInput, *, field_path: str) -> tuple[TimeWindow | None, FieldError | None]:
    from datetime import time
    try:
        sh, sm = tw.start.split(":")
        eh, em = tw.end.split(":")
        r = TimeWindow.create(time(int(sh), int(sm)), time(int(eh), int(em)))
    except (ValueError, AttributeError):
        return None, FieldError(code="TimeWindowInvalidType", field=field_path)
    if r.is_failure:
        return None, FieldError(code=r.error, field=field_path)
    return r.value, None


class CreateResourceHandler:
    def __init__(
        self,
        resources: IResourceRepository,
        resource_types: IResourceTypeRepository,
        users: IUserRepository,
    ) -> None:
        self._resources = resources
        self._resource_types = resource_types
        self._users = users

    async def handle(self, cmd: CreateResourceCommand) -> Result[ResourceDto]:
        # 1. Actor must be OWNER.
        user = await self._users.get_by_id(cmd.actor_id)
        if user is None or user.role is not Role.OWNER:
            return Result.failure("UserIsNotOwner", status_code=403)

        # 2. ResourceType lookup + active check.
        rt = await self._resource_types.get_by_id(cmd.resource_type_id)
        if rt is None:
            return Result.failure("ResourceTypeNotFound", status_code=404)
        if not rt.is_active:
            return Result.failure("ResourceTypeInactive", status_code=422)

        errors: list[FieldError] = []

        # 3. Build composite VOs.
        # 3a. WeeklySchedule
        days_built: dict[Weekday, list[TimeWindow]] = {}
        for wd, windows_in in cmd.operating_hours.days.items():
            built: list[TimeWindow] = []
            for idx, tw_in in enumerate(windows_in):
                tw, err = _parse_time_window(
                    tw_in, field_path=f"operating_hours.days.{wd.value.lower()}[{idx}]",
                )
                if err is not None:
                    errors.append(err)
                else:
                    built.append(tw)
            days_built[wd] = built
        ws_r = WeeklySchedule.create(
            slot_duration_minutes=cmd.slot_duration_minutes,
            days=days_built,
        )
        if ws_r.is_failure and ws_r.details is not None:
            errors.extend(
                FieldError(code=e.code, field=f"operating_hours.{e.field}")
                for e in ws_r.details
            )

        # 3b. PricingRules
        rules_built: list[PricingRule] = []
        for idx, p_in in enumerate(cmd.pricing_rules):
            tw, tw_err = _parse_time_window(
                p_in.window, field_path=f"pricing_rules[{idx}].window",
            )
            if tw_err is not None:
                errors.append(tw_err)
                continue
            money_r = Money.create(p_in.price_cents)
            if money_r.is_failure:
                errors.append(FieldError(code=money_r.error, field=f"pricing_rules[{idx}].price_cents"))
                continue
            rule_r = PricingRule.create(
                weekdays=p_in.weekdays, window=tw, price=money_r.value,
            )
            if rule_r.is_failure:
                errors.append(FieldError(code=rule_r.error, field=f"pricing_rules[{idx}]"))
                continue
            rules_built.append(rule_r.value)

        # 3c. CustomAttributes
        customs_built: list[CustomAttribute] = []
        for idx, c_in in enumerate(cmd.custom_attributes):
            ca_r = CustomAttribute.create(key=c_in.key, label=c_in.label, value=c_in.value)
            if ca_r.is_failure and ca_r.details is not None:
                errors.extend(
                    FieldError(code=e.code, field=f"custom_attributes[{idx}].{e.field}")
                    for e in ca_r.details
                )
                continue
            customs_built.append(ca_r.value)

        # 4. ResourceType.validate_attributes against base_attributes.
        attr_r = rt.validate_attributes(cmd.base_attributes)
        if attr_r.is_failure and attr_r.details is not None:
            errors.extend(
                FieldError(code=e.code, field=f"base_attributes.{e.field}")
                for e in attr_r.details
            )

        # 5. Bail if anything failed before we try Resource.create.
        if errors:
            return Result.failure_many(errors, status_code=400)

        # 6. Resource.create with pre-built composites.
        res_r = Resource.create(
            owner_id=cmd.actor_id,
            resource_type_id=cmd.resource_type_id,
            slug=cmd.slug,
            name=cmd.name,
            description=cmd.description,
            city=cmd.city,
            region=cmd.region,
            timezone=cmd.timezone,
            slot_duration_minutes=cmd.slot_duration_minutes,
            operating_hours=ws_r.value,
            base_price_cents=cmd.base_price_cents,
            customer_cancellation_cutoff_hours=cmd.customer_cancellation_cutoff_hours,
            base_attributes=cmd.base_attributes,
            pricing_rules=rules_built,
            custom_attributes=customs_built,
            is_published=False,
        )
        if res_r.is_failure:
            return Result.from_failure(res_r, status_code=400)

        # 7. Persist.
        add_r = await self._resources.add(res_r.value)
        if add_r.is_failure:
            return Result.from_failure(add_r)

        return Result.success(
            ResourceDto.from_entity(
                res_r.value,
                owner_slug=user.public_slug.value,
                resource_type_slug=rt.slug.value,
            )
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/unit/use_cases/resources/commands/test_create_resource.py -v`
Expected: 5 PASS.

- [ ] **Step 5: Commit**

```bash
git add app/use_cases/resources/commands/__init__.py app/use_cases/resources/commands/create_resource.py tests/unit/use_cases/resources/commands/__init__.py tests/unit/use_cases/resources/commands/test_create_resource.py
git commit -m "$(cat <<'EOF'
feat(resources): CreateResourceHandler

Verifies actor is OWNER, ResourceType is active, then aggregates
composite-VO build errors + Resource.create errors + rt.validate_attributes
errors into a single failure_many envelope. base_attributes errors are
prefixed with base_attributes.<key>; pricing/custom errors with their
indexed paths. Persists via repo and returns ResourceDto with joined
owner_slug + resource_type_slug.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 20: `UpdateResourceMetadataHandler`

**Files:**
- Create: `app/use_cases/resources/commands/update_resource_metadata.py`
- Test: `tests/unit/use_cases/resources/commands/test_update_resource_metadata.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/use_cases/resources/commands/test_update_resource_metadata.py`:

```python
from __future__ import annotations
from uuid import uuid4

import pytest

from app.use_cases.resources.commands.update_resource_metadata import (
    UpdateResourceMetadataCommand,
    UpdateResourceMetadataHandler,
)
from tests.unit.use_cases.resources.fakes.in_memory_resource_repository import InMemoryResourceRepository
from tests.unit.use_cases.resources.fixtures import seed_resource  # helper introduced below


@pytest.mark.asyncio
async def test_update_metadata_happy_path():
    repo = InMemoryResourceRepository()
    res, owner_slug, rt_slug = await seed_resource(repo)
    handler = UpdateResourceMetadataHandler(repo)
    cmd = UpdateResourceMetadataCommand(
        actor_id=res.owner_id,
        resource_id=res.id,
        name="Novo Nome",
        city=None,
        region=None,
        description=None,
    )
    # owner_slug + rt_slug returned through DTO assembly via separate join helper
    # — for this test we use a passthrough fixture inside the handler.
    r = await handler.handle(cmd)
    assert r.is_success


@pytest.mark.asyncio
async def test_update_metadata_404_for_non_owner():
    repo = InMemoryResourceRepository()
    res, _, _ = await seed_resource(repo)
    handler = UpdateResourceMetadataHandler(repo)
    cmd = UpdateResourceMetadataCommand(
        actor_id=uuid4(),  # different actor
        resource_id=res.id,
        name="X", city=None, region=None, description=None,
    )
    r = await handler.handle(cmd)
    assert r.is_failure
    assert r.error == "ResourceNotFound"
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_update_metadata_aggregates_field_errors():
    repo = InMemoryResourceRepository()
    res, _, _ = await seed_resource(repo)
    handler = UpdateResourceMetadataHandler(repo)
    cmd = UpdateResourceMetadataCommand(
        actor_id=res.owner_id,
        resource_id=res.id,
        name="",
        city="",
        region=None,
        description=None,
    )
    r = await handler.handle(cmd)
    assert r.is_failure
    fields = {e.field for e in r.details}
    assert "name" in fields
    assert "city" in fields
```

Create `tests/unit/use_cases/resources/fixtures.py` (shared helper for handler tests):

```python
from __future__ import annotations
from datetime import time
from uuid import uuid4

from app.domain.resources.resource import Resource
from app.domain.resources.weekly_schedule import WeeklySchedule
from app.domain.shared.value_objects.time_window import TimeWindow
from app.domain.shared.weekday import Weekday
from tests.unit.use_cases.resources.fakes.in_memory_resource_repository import InMemoryResourceRepository


def _w(sh: int, eh: int) -> TimeWindow:
    return TimeWindow.create(time(sh, 0), time(eh, 0)).value


async def seed_resource(repo: InMemoryResourceRepository, *, owner_id=None, slug="arena-zl"):
    """Insert a valid Resource and return (resource, owner_slug, rt_slug)."""
    owner_id = owner_id or uuid4()
    rt_id = uuid4()
    ws = WeeklySchedule.create(
        slot_duration_minutes=60,
        days={Weekday.MONDAY: [_w(8, 22)]},
    ).value
    res = Resource.create(
        owner_id=owner_id, resource_type_id=rt_id,
        slug=slug, name="Arena", description="",
        city="São Paulo", region="SP",
        timezone="America/Sao_Paulo",
        slot_duration_minutes=60,
        operating_hours=ws,
        base_price_cents=8000,
        customer_cancellation_cutoff_hours=24,
        base_attributes={},
        pricing_rules=[],
        custom_attributes=[],
    ).value
    await repo.add(res)
    return res, "owner-slug", "type-slug"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/unit/use_cases/resources/commands/test_update_resource_metadata.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement the handler**

Create `app/use_cases/resources/commands/update_resource_metadata.py`:

```python
from __future__ import annotations
from dataclasses import dataclass
from uuid import UUID

from app.domain.resources.repository import IResourceRepository
from app.domain.shared.result import Result
from app.use_cases.resources._common import load_owned_resource


@dataclass(frozen=True, slots=True)
class UpdateResourceMetadataCommand:
    actor_id: UUID
    resource_id: UUID
    name: str | None
    description: str | None
    city: str | None
    region: str | None


class UpdateResourceMetadataHandler:
    def __init__(self, resources: IResourceRepository) -> None:
        self._resources = resources

    async def handle(self, cmd: UpdateResourceMetadataCommand) -> Result[None]:
        loaded = await load_owned_resource(
            self._resources, resource_id=cmd.resource_id, actor_id=cmd.actor_id,
        )
        if loaded.is_failure:
            return Result.from_failure(loaded)
        res = loaded.value

        upd = res.update_metadata(
            name=cmd.name, description=cmd.description,
            city=cmd.city, region=cmd.region,
        )
        if upd.is_failure:
            return Result.from_failure(upd, status_code=400)

        save = await self._resources.update(res)
        if save.is_failure:
            return Result.from_failure(save)
        return Result.success(None)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/unit/use_cases/resources/commands/test_update_resource_metadata.py -v`
Expected: 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add app/use_cases/resources/commands/update_resource_metadata.py tests/unit/use_cases/resources/commands/test_update_resource_metadata.py tests/unit/use_cases/resources/fixtures.py
git commit -m "$(cat <<'EOF'
feat(resources): UpdateResourceMetadataHandler

Owner-only edit of name/description/city/region. 404-on-mismatch via
load_owned_resource helper. Aggregated field errors propagate up via
Result.from_failure (preserves details).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 21: `ReplaceOperatingHoursHandler`

**Files:**
- Create: `app/use_cases/resources/commands/replace_operating_hours.py`
- Test: `tests/unit/use_cases/resources/commands/test_replace_operating_hours.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/use_cases/resources/commands/test_replace_operating_hours.py`:

```python
from __future__ import annotations
import pytest

from app.domain.shared.weekday import Weekday
from app.use_cases.resources.commands.replace_operating_hours import (
    ReplaceOperatingHoursCommand,
    ReplaceOperatingHoursHandler,
)
from app.use_cases.resources.commands.create_resource import (
    OperatingHoursInput, TimeWindowInput,
)
from tests.unit.use_cases.resources.fakes.in_memory_resource_repository import InMemoryResourceRepository
from tests.unit.use_cases.resources.fixtures import seed_resource


@pytest.mark.asyncio
async def test_replace_hours_happy():
    repo = InMemoryResourceRepository()
    res, _, _ = await seed_resource(repo)
    handler = ReplaceOperatingHoursHandler(repo)
    cmd = ReplaceOperatingHoursCommand(
        actor_id=res.owner_id, resource_id=res.id,
        operating_hours=OperatingHoursInput(days={
            Weekday.FRIDAY: [TimeWindowInput(start="18:00", end="23:00")],
        }),
    )
    r = await handler.handle(cmd)
    assert r.is_success
    fetched = await repo.get_by_id(res.id)
    assert len(fetched.operating_hours.for_weekday(Weekday.FRIDAY)) == 1


@pytest.mark.asyncio
async def test_replace_hours_invalid_alignment():
    repo = InMemoryResourceRepository()
    res, _, _ = await seed_resource(repo)
    handler = ReplaceOperatingHoursHandler(repo)
    cmd = ReplaceOperatingHoursCommand(
        actor_id=res.owner_id, resource_id=res.id,
        operating_hours=OperatingHoursInput(days={
            Weekday.FRIDAY: [TimeWindowInput(start="08:30", end="22:00")],  # misaligned to 60min
        }),
    )
    r = await handler.handle(cmd)
    assert r.is_failure
    fields = {e.field for e in r.details}
    assert any(f.startswith("operating_hours.") for f in fields)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/unit/use_cases/resources/commands/test_replace_operating_hours.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement the handler**

Create `app/use_cases/resources/commands/replace_operating_hours.py`:

```python
from __future__ import annotations
from dataclasses import dataclass
from uuid import UUID

from app.domain.resources.repository import IResourceRepository
from app.domain.resources.weekly_schedule import WeeklySchedule
from app.domain.shared.field_error import FieldError
from app.domain.shared.result import Result
from app.domain.shared.value_objects.time_window import TimeWindow
from app.use_cases.resources._common import load_owned_resource
from app.use_cases.resources.commands.create_resource import (
    OperatingHoursInput, _parse_time_window,
)


@dataclass(frozen=True, slots=True)
class ReplaceOperatingHoursCommand:
    actor_id: UUID
    resource_id: UUID
    operating_hours: OperatingHoursInput


class ReplaceOperatingHoursHandler:
    def __init__(self, resources: IResourceRepository) -> None:
        self._resources = resources

    async def handle(self, cmd: ReplaceOperatingHoursCommand) -> Result[None]:
        loaded = await load_owned_resource(
            self._resources, resource_id=cmd.resource_id, actor_id=cmd.actor_id,
        )
        if loaded.is_failure:
            return Result.from_failure(loaded)
        res = loaded.value

        errors: list[FieldError] = []
        days_built: dict = {}
        for wd, windows_in in cmd.operating_hours.days.items():
            built: list[TimeWindow] = []
            for idx, tw_in in enumerate(windows_in):
                tw, err = _parse_time_window(
                    tw_in, field_path=f"operating_hours.days.{wd.value.lower()}[{idx}]",
                )
                if err is not None:
                    errors.append(err)
                else:
                    built.append(tw)
            days_built[wd] = built

        ws_r = WeeklySchedule.create(
            slot_duration_minutes=res.slot_duration_minutes.minutes,
            days=days_built,
        )
        if ws_r.is_failure and ws_r.details is not None:
            errors.extend(
                FieldError(code=e.code, field=f"operating_hours.{e.field}")
                for e in ws_r.details
            )
        if errors:
            return Result.failure_many(errors, status_code=400)

        repl = res.replace_operating_hours(ws_r.value)
        if repl.is_failure:
            return Result.from_failure(repl, status_code=400)

        save = await self._resources.update(res)
        if save.is_failure:
            return Result.from_failure(save)
        return Result.success(None)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/unit/use_cases/resources/commands/test_replace_operating_hours.py -v`
Expected: 2 PASS.

- [ ] **Step 5: Commit**

```bash
git add app/use_cases/resources/commands/replace_operating_hours.py tests/unit/use_cases/resources/commands/test_replace_operating_hours.py
git commit -m "$(cat <<'EOF'
feat(resources): ReplaceOperatingHoursHandler

Builds WeeklySchedule from input, prefixes errors with operating_hours.,
and Resource.replace_operating_hours re-runs cross-rule pricing checks
under the new hours.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 22: `ReplacePricingRulesHandler`

**Files:**
- Create: `app/use_cases/resources/commands/replace_pricing_rules.py`
- Test: `tests/unit/use_cases/resources/commands/test_replace_pricing_rules.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/use_cases/resources/commands/test_replace_pricing_rules.py`:

```python
from __future__ import annotations
import pytest

from app.domain.resources.resource import Resource
from app.domain.shared.weekday import Weekday
from app.use_cases.resources.commands.create_resource import (
    PricingRuleInput, TimeWindowInput,
)
from app.use_cases.resources.commands.replace_pricing_rules import (
    ReplacePricingRulesCommand,
    ReplacePricingRulesHandler,
)
from tests.unit.use_cases.resources.fakes.in_memory_resource_repository import InMemoryResourceRepository
from tests.unit.use_cases.resources.fixtures import seed_resource


@pytest.mark.asyncio
async def test_replace_rules_happy():
    repo = InMemoryResourceRepository()
    res, _, _ = await seed_resource(repo)
    handler = ReplacePricingRulesHandler(repo)
    cmd = ReplacePricingRulesCommand(
        actor_id=res.owner_id, resource_id=res.id,
        pricing_rules=[
            PricingRuleInput(
                weekdays=[Weekday.MONDAY],
                window=TimeWindowInput(start="18:00", end="22:00"),
                price_cents=12000,
            ),
        ],
    )
    r = await handler.handle(cmd)
    assert r.is_success
    fetched = await repo.get_by_id(res.id)
    assert len(fetched.pricing_rules) == 1


@pytest.mark.asyncio
async def test_replace_rules_overlap_rejected():
    repo = InMemoryResourceRepository()
    res, _, _ = await seed_resource(repo)
    handler = ReplacePricingRulesHandler(repo)
    cmd = ReplacePricingRulesCommand(
        actor_id=res.owner_id, resource_id=res.id,
        pricing_rules=[
            PricingRuleInput(
                weekdays=[Weekday.MONDAY],
                window=TimeWindowInput(start="08:00", end="14:00"),
                price_cents=5000,
            ),
            PricingRuleInput(
                weekdays=[Weekday.MONDAY],
                window=TimeWindowInput(start="13:00", end="22:00"),
                price_cents=10000,
            ),
        ],
    )
    r = await handler.handle(cmd)
    assert r.is_failure
    codes = {e.code for e in r.details}
    assert Resource.PRICING_RULES_OVERLAP in codes
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/unit/use_cases/resources/commands/test_replace_pricing_rules.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement the handler**

Create `app/use_cases/resources/commands/replace_pricing_rules.py`:

```python
from __future__ import annotations
from dataclasses import dataclass
from uuid import UUID

from app.domain.resources.pricing_rule import PricingRule
from app.domain.resources.repository import IResourceRepository
from app.domain.shared.field_error import FieldError
from app.domain.shared.result import Result
from app.domain.shared.value_objects.money import Money
from app.use_cases.resources._common import load_owned_resource
from app.use_cases.resources.commands.create_resource import (
    PricingRuleInput, _parse_time_window,
)


@dataclass(frozen=True, slots=True)
class ReplacePricingRulesCommand:
    actor_id: UUID
    resource_id: UUID
    pricing_rules: list[PricingRuleInput]


class ReplacePricingRulesHandler:
    def __init__(self, resources: IResourceRepository) -> None:
        self._resources = resources

    async def handle(self, cmd: ReplacePricingRulesCommand) -> Result[None]:
        loaded = await load_owned_resource(
            self._resources, resource_id=cmd.resource_id, actor_id=cmd.actor_id,
        )
        if loaded.is_failure:
            return Result.from_failure(loaded)
        res = loaded.value

        errors: list[FieldError] = []
        rules_built: list[PricingRule] = []
        for idx, p_in in enumerate(cmd.pricing_rules):
            tw, tw_err = _parse_time_window(
                p_in.window, field_path=f"pricing_rules[{idx}].window",
            )
            if tw_err is not None:
                errors.append(tw_err)
                continue
            money_r = Money.create(p_in.price_cents)
            if money_r.is_failure:
                errors.append(FieldError(code=money_r.error, field=f"pricing_rules[{idx}].price_cents"))
                continue
            rule_r = PricingRule.create(
                weekdays=p_in.weekdays, window=tw, price=money_r.value,
            )
            if rule_r.is_failure:
                errors.append(FieldError(code=rule_r.error, field=f"pricing_rules[{idx}]"))
                continue
            rules_built.append(rule_r.value)
        if errors:
            return Result.failure_many(errors, status_code=400)

        repl = res.replace_pricing_rules(rules_built)
        if repl.is_failure:
            return Result.from_failure(repl, status_code=400)

        save = await self._resources.update(res)
        if save.is_failure:
            return Result.from_failure(save)
        return Result.success(None)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/unit/use_cases/resources/commands/test_replace_pricing_rules.py -v`
Expected: 2 PASS.

- [ ] **Step 5: Commit**

```bash
git add app/use_cases/resources/commands/replace_pricing_rules.py tests/unit/use_cases/resources/commands/test_replace_pricing_rules.py
git commit -m "$(cat <<'EOF'
feat(resources): ReplacePricingRulesHandler

Builds PricingRule list from input with indexed FieldError prefixes,
then Resource.replace_pricing_rules re-runs overlap/alignment/containment.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 23: `ReplaceBaseAttributesHandler`

**Files:**
- Create: `app/use_cases/resources/commands/replace_base_attributes.py`
- Test: `tests/unit/use_cases/resources/commands/test_replace_base_attributes.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/use_cases/resources/commands/test_replace_base_attributes.py`:

```python
from __future__ import annotations
import pytest

from app.domain.catalog.attribute import AttrType, AttributeDefinition
from app.domain.catalog.resource_type import ResourceType
from app.use_cases.resources.commands.replace_base_attributes import (
    ReplaceBaseAttributesCommand,
    ReplaceBaseAttributesHandler,
)
from tests.unit.use_cases.catalog.fakes.in_memory_resource_type_repository import InMemoryResourceTypeRepository
from tests.unit.use_cases.resources.fakes.in_memory_resource_repository import InMemoryResourceRepository
from tests.unit.use_cases.resources.fixtures import seed_resource


def _rt_with_required_surface() -> ResourceType:
    return ResourceType.create(
        slug="football-field", name="Football", description="",
        attribute_schema=[
            AttributeDefinition.create(
                key="surface_type", label="Surface", data_type=AttrType.ENUM,
                required=True, enum_values=["GRASS", "SAND"],
            ).value,
        ],
    ).value


@pytest.mark.asyncio
async def test_replace_base_attributes_happy():
    rts = InMemoryResourceTypeRepository()
    rt = _rt_with_required_surface()
    await rts.add(rt)
    repo = InMemoryResourceRepository()
    res, _, _ = await seed_resource(repo)
    # Replace resource_type_id to match `rt` for this test:
    res.resource_type_id = rt.id

    handler = ReplaceBaseAttributesHandler(repo, rts)
    cmd = ReplaceBaseAttributesCommand(
        actor_id=res.owner_id, resource_id=res.id,
        base_attributes={"surface_type": "GRASS"},
    )
    r = await handler.handle(cmd)
    assert r.is_success
    fetched = await repo.get_by_id(res.id)
    assert fetched.base_attributes == {"surface_type": "GRASS"}


@pytest.mark.asyncio
async def test_replace_base_attributes_schema_violation():
    rts = InMemoryResourceTypeRepository()
    rt = _rt_with_required_surface()
    await rts.add(rt)
    repo = InMemoryResourceRepository()
    res, _, _ = await seed_resource(repo)
    res.resource_type_id = rt.id

    handler = ReplaceBaseAttributesHandler(repo, rts)
    cmd = ReplaceBaseAttributesCommand(
        actor_id=res.owner_id, resource_id=res.id,
        base_attributes={"surface_type": "MARS_DUST"},  # not in enum
    )
    r = await handler.handle(cmd)
    assert r.is_failure
    fields = {e.field for e in r.details}
    assert "base_attributes.surface_type" in fields
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/unit/use_cases/resources/commands/test_replace_base_attributes.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement the handler**

Create `app/use_cases/resources/commands/replace_base_attributes.py`:

```python
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from app.domain.catalog.repository import IResourceTypeRepository
from app.domain.resources.repository import IResourceRepository
from app.domain.shared.field_error import FieldError
from app.domain.shared.result import Result
from app.use_cases.resources._common import load_owned_resource


@dataclass(frozen=True, slots=True)
class ReplaceBaseAttributesCommand:
    actor_id: UUID
    resource_id: UUID
    base_attributes: dict[str, Any]


class ReplaceBaseAttributesHandler:
    def __init__(
        self,
        resources: IResourceRepository,
        resource_types: IResourceTypeRepository,
    ) -> None:
        self._resources = resources
        self._resource_types = resource_types

    async def handle(self, cmd: ReplaceBaseAttributesCommand) -> Result[None]:
        loaded = await load_owned_resource(
            self._resources, resource_id=cmd.resource_id, actor_id=cmd.actor_id,
        )
        if loaded.is_failure:
            return Result.from_failure(loaded)
        res = loaded.value

        rt = await self._resource_types.get_by_id(res.resource_type_id)
        if rt is None:
            return Result.failure("ResourceTypeNotFound", status_code=404)

        attr_r = rt.validate_attributes(cmd.base_attributes)
        if attr_r.is_failure and attr_r.details is not None:
            return Result.failure_many(
                [
                    FieldError(code=e.code, field=f"base_attributes.{e.field}")
                    for e in attr_r.details
                ],
                status_code=400,
            )

        repl = res.replace_base_attributes(cmd.base_attributes)
        if repl.is_failure:
            return Result.from_failure(repl, status_code=400)

        save = await self._resources.update(res)
        if save.is_failure:
            return Result.from_failure(save)
        return Result.success(None)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/unit/use_cases/resources/commands/test_replace_base_attributes.py -v`
Expected: 2 PASS.

- [ ] **Step 5: Commit**

```bash
git add app/use_cases/resources/commands/replace_base_attributes.py tests/unit/use_cases/resources/commands/test_replace_base_attributes.py
git commit -m "$(cat <<'EOF'
feat(resources): ReplaceBaseAttributesHandler

Loads ResourceType, runs validate_attributes (cross-feature), prefixes
errors with base_attributes.<key>, then mutates Resource. Disjointness
with custom_attributes is enforced inside Resource.replace_base_attributes.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 24: `ReplaceCustomAttributesHandler`

**Files:**
- Create: `app/use_cases/resources/commands/replace_custom_attributes.py`
- Test: `tests/unit/use_cases/resources/commands/test_replace_custom_attributes.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/use_cases/resources/commands/test_replace_custom_attributes.py`:

```python
from __future__ import annotations
import pytest

from app.use_cases.resources.commands.create_resource import CustomAttributeInput
from app.use_cases.resources.commands.replace_custom_attributes import (
    ReplaceCustomAttributesCommand,
    ReplaceCustomAttributesHandler,
)
from tests.unit.use_cases.resources.fakes.in_memory_resource_repository import InMemoryResourceRepository
from tests.unit.use_cases.resources.fixtures import seed_resource


@pytest.mark.asyncio
async def test_replace_custom_attributes_happy():
    repo = InMemoryResourceRepository()
    res, _, _ = await seed_resource(repo)
    handler = ReplaceCustomAttributesHandler(repo)
    cmd = ReplaceCustomAttributesCommand(
        actor_id=res.owner_id, resource_id=res.id,
        custom_attributes=[
            CustomAttributeInput(key="wifi", label="Wi-Fi", value="sim"),
            CustomAttributeInput(key="parking", label="Estacionamento", value="50 vagas"),
        ],
    )
    r = await handler.handle(cmd)
    assert r.is_success
    fetched = await repo.get_by_id(res.id)
    assert len(fetched.custom_attributes) == 2


@pytest.mark.asyncio
async def test_replace_custom_attributes_aggregates_errors():
    repo = InMemoryResourceRepository()
    res, _, _ = await seed_resource(repo)
    handler = ReplaceCustomAttributesHandler(repo)
    cmd = ReplaceCustomAttributesCommand(
        actor_id=res.owner_id, resource_id=res.id,
        custom_attributes=[
            CustomAttributeInput(key="!!!", label="", value=""),  # invalid key/label
            CustomAttributeInput(key="wifi", label="Wi-Fi", value="x" * 600),  # value too long
        ],
    )
    r = await handler.handle(cmd)
    assert r.is_failure
    fields = {e.field for e in r.details}
    assert any(f.startswith("custom_attributes[0]") for f in fields)
    assert any(f.startswith("custom_attributes[1]") for f in fields)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/unit/use_cases/resources/commands/test_replace_custom_attributes.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement the handler**

Create `app/use_cases/resources/commands/replace_custom_attributes.py`:

```python
from __future__ import annotations
from dataclasses import dataclass
from uuid import UUID

from app.domain.resources.custom_attribute import CustomAttribute
from app.domain.resources.repository import IResourceRepository
from app.domain.shared.field_error import FieldError
from app.domain.shared.result import Result
from app.use_cases.resources._common import load_owned_resource
from app.use_cases.resources.commands.create_resource import CustomAttributeInput


@dataclass(frozen=True, slots=True)
class ReplaceCustomAttributesCommand:
    actor_id: UUID
    resource_id: UUID
    custom_attributes: list[CustomAttributeInput]


class ReplaceCustomAttributesHandler:
    def __init__(self, resources: IResourceRepository) -> None:
        self._resources = resources

    async def handle(self, cmd: ReplaceCustomAttributesCommand) -> Result[None]:
        loaded = await load_owned_resource(
            self._resources, resource_id=cmd.resource_id, actor_id=cmd.actor_id,
        )
        if loaded.is_failure:
            return Result.from_failure(loaded)
        res = loaded.value

        errors: list[FieldError] = []
        built: list[CustomAttribute] = []
        for idx, c_in in enumerate(cmd.custom_attributes):
            ca_r = CustomAttribute.create(key=c_in.key, label=c_in.label, value=c_in.value)
            if ca_r.is_failure and ca_r.details is not None:
                errors.extend(
                    FieldError(code=e.code, field=f"custom_attributes[{idx}].{e.field}")
                    for e in ca_r.details
                )
                continue
            built.append(ca_r.value)
        if errors:
            return Result.failure_many(errors, status_code=400)

        repl = res.replace_custom_attributes(built)
        if repl.is_failure:
            return Result.from_failure(repl, status_code=400)

        save = await self._resources.update(res)
        if save.is_failure:
            return Result.from_failure(save)
        return Result.success(None)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/unit/use_cases/resources/commands/test_replace_custom_attributes.py -v`
Expected: 2 PASS.

- [ ] **Step 5: Commit**

```bash
git add app/use_cases/resources/commands/replace_custom_attributes.py tests/unit/use_cases/resources/commands/test_replace_custom_attributes.py
git commit -m "$(cat <<'EOF'
feat(resources): ReplaceCustomAttributesHandler

Builds CustomAttribute list with indexed FieldError prefixes, then
Resource.replace_custom_attributes enforces uniqueness + disjointness
with base_attributes.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 25: `SetBasePriceHandler` + `SetCancellationCutoffHandler` (bundled)

**Files:**
- Create: `app/use_cases/resources/commands/set_base_price.py`
- Create: `app/use_cases/resources/commands/set_cancellation_cutoff.py`
- Test: `tests/unit/use_cases/resources/commands/test_set_base_price.py`
- Test: `tests/unit/use_cases/resources/commands/test_set_cancellation_cutoff.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/use_cases/resources/commands/test_set_base_price.py`:

```python
import pytest

from app.use_cases.resources.commands.set_base_price import (
    SetBasePriceCommand, SetBasePriceHandler,
)
from tests.unit.use_cases.resources.fakes.in_memory_resource_repository import InMemoryResourceRepository
from tests.unit.use_cases.resources.fixtures import seed_resource


@pytest.mark.asyncio
async def test_set_base_price_happy():
    repo = InMemoryResourceRepository()
    res, _, _ = await seed_resource(repo)
    handler = SetBasePriceHandler(repo)
    r = await handler.handle(SetBasePriceCommand(
        actor_id=res.owner_id, resource_id=res.id, base_price_cents=15000,
    ))
    assert r.is_success
    fetched = await repo.get_by_id(res.id)
    assert fetched.base_price_cents.cents == 15000


@pytest.mark.asyncio
async def test_set_base_price_invalid_money():
    repo = InMemoryResourceRepository()
    res, _, _ = await seed_resource(repo)
    handler = SetBasePriceHandler(repo)
    r = await handler.handle(SetBasePriceCommand(
        actor_id=res.owner_id, resource_id=res.id, base_price_cents=-1,
    ))
    assert r.is_failure
    assert r.status_code == 400
```

Create `tests/unit/use_cases/resources/commands/test_set_cancellation_cutoff.py`:

```python
import pytest

from app.use_cases.resources.commands.set_cancellation_cutoff import (
    SetCancellationCutoffCommand, SetCancellationCutoffHandler,
)
from tests.unit.use_cases.resources.fakes.in_memory_resource_repository import InMemoryResourceRepository
from tests.unit.use_cases.resources.fixtures import seed_resource


@pytest.mark.asyncio
async def test_set_cutoff_happy():
    repo = InMemoryResourceRepository()
    res, _, _ = await seed_resource(repo)
    handler = SetCancellationCutoffHandler(repo)
    r = await handler.handle(SetCancellationCutoffCommand(
        actor_id=res.owner_id, resource_id=res.id, hours=48,
    ))
    assert r.is_success
    fetched = await repo.get_by_id(res.id)
    assert fetched.customer_cancellation_cutoff_hours.hours == 48


@pytest.mark.asyncio
async def test_set_cutoff_out_of_range():
    repo = InMemoryResourceRepository()
    res, _, _ = await seed_resource(repo)
    handler = SetCancellationCutoffHandler(repo)
    r = await handler.handle(SetCancellationCutoffCommand(
        actor_id=res.owner_id, resource_id=res.id, hours=999,
    ))
    assert r.is_failure
    assert r.status_code == 400
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/unit/use_cases/resources/commands/test_set_base_price.py tests/unit/use_cases/resources/commands/test_set_cancellation_cutoff.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement both handlers**

Create `app/use_cases/resources/commands/set_base_price.py`:

```python
from __future__ import annotations
from dataclasses import dataclass
from uuid import UUID

from app.domain.resources.repository import IResourceRepository
from app.domain.shared.result import Result
from app.domain.shared.value_objects.money import Money
from app.use_cases.resources._common import load_owned_resource


@dataclass(frozen=True, slots=True)
class SetBasePriceCommand:
    actor_id: UUID
    resource_id: UUID
    base_price_cents: int


class SetBasePriceHandler:
    def __init__(self, resources: IResourceRepository) -> None:
        self._resources = resources

    async def handle(self, cmd: SetBasePriceCommand) -> Result[None]:
        loaded = await load_owned_resource(
            self._resources, resource_id=cmd.resource_id, actor_id=cmd.actor_id,
        )
        if loaded.is_failure:
            return Result.from_failure(loaded)
        res = loaded.value

        money_r = Money.create(cmd.base_price_cents)
        if money_r.is_failure:
            return Result.failure(money_r.error, status_code=400)

        res.set_base_price(money_r.value)
        save = await self._resources.update(res)
        if save.is_failure:
            return Result.from_failure(save)
        return Result.success(None)
```

Create `app/use_cases/resources/commands/set_cancellation_cutoff.py`:

```python
from __future__ import annotations
from dataclasses import dataclass
from uuid import UUID

from app.domain.resources.repository import IResourceRepository
from app.domain.shared.result import Result
from app.domain.shared.value_objects.cancellation_cutoff import CancellationCutoff
from app.use_cases.resources._common import load_owned_resource


@dataclass(frozen=True, slots=True)
class SetCancellationCutoffCommand:
    actor_id: UUID
    resource_id: UUID
    hours: int


class SetCancellationCutoffHandler:
    def __init__(self, resources: IResourceRepository) -> None:
        self._resources = resources

    async def handle(self, cmd: SetCancellationCutoffCommand) -> Result[None]:
        loaded = await load_owned_resource(
            self._resources, resource_id=cmd.resource_id, actor_id=cmd.actor_id,
        )
        if loaded.is_failure:
            return Result.from_failure(loaded)
        res = loaded.value

        cutoff_r = CancellationCutoff.create(cmd.hours)
        if cutoff_r.is_failure:
            return Result.failure(cutoff_r.error, status_code=400)

        res.set_cancellation_cutoff(cutoff_r.value)
        save = await self._resources.update(res)
        if save.is_failure:
            return Result.from_failure(save)
        return Result.success(None)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/unit/use_cases/resources/commands/test_set_base_price.py tests/unit/use_cases/resources/commands/test_set_cancellation_cutoff.py -v`
Expected: 4 PASS.

- [ ] **Step 5: Commit**

```bash
git add app/use_cases/resources/commands/set_base_price.py app/use_cases/resources/commands/set_cancellation_cutoff.py tests/unit/use_cases/resources/commands/test_set_base_price.py tests/unit/use_cases/resources/commands/test_set_cancellation_cutoff.py
git commit -m "$(cat <<'EOF'
feat(resources): SetBasePrice + SetCancellationCutoff handlers

Single-VO mutators with no aggregate-level invariants. VO factory
failures surface as Result.failure(code, status_code=400).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 26: `SetSlotDurationHandler` + `Publish/UnpublishHandler` + `SoftDeleteResourceHandler` (bundled)

**Files:**
- Create: `app/use_cases/resources/commands/set_slot_duration.py`
- Create: `app/use_cases/resources/commands/publish_resource.py`
- Create: `app/use_cases/resources/commands/soft_delete_resource.py`
- Test: `tests/unit/use_cases/resources/commands/test_set_slot_duration.py`
- Test: `tests/unit/use_cases/resources/commands/test_publish_resource.py`
- Test: `tests/unit/use_cases/resources/commands/test_soft_delete_resource.py`

- [ ] **Step 1: Write the failing tests (3 small files)**

Create `tests/unit/use_cases/resources/commands/test_set_slot_duration.py`:

```python
import pytest

from app.use_cases.resources.commands.set_slot_duration import (
    SetSlotDurationCommand, SetSlotDurationHandler,
)
from tests.unit.use_cases.resources.fakes.in_memory_resource_repository import InMemoryResourceRepository
from tests.unit.use_cases.resources.fixtures import seed_resource


@pytest.mark.asyncio
async def test_set_slot_duration_happy():
    repo = InMemoryResourceRepository()
    res, _, _ = await seed_resource(repo)
    handler = SetSlotDurationHandler(repo)
    # 60 → 120 keeps the 8-22 hours aligned (14h % 120min == ?? actually 14h=840min, 840/120=7 → ok)
    r = await handler.handle(SetSlotDurationCommand(
        actor_id=res.owner_id, resource_id=res.id, minutes=120,
    ))
    assert r.is_success
    fetched = await repo.get_by_id(res.id)
    assert fetched.slot_duration_minutes.minutes == 120


@pytest.mark.asyncio
async def test_set_slot_duration_invalid_value():
    repo = InMemoryResourceRepository()
    res, _, _ = await seed_resource(repo)
    handler = SetSlotDurationHandler(repo)
    r = await handler.handle(SetSlotDurationCommand(
        actor_id=res.owner_id, resource_id=res.id, minutes=37,  # not in {30,45,60,90,120}
    ))
    assert r.is_failure
    assert r.status_code == 400
```

Create `tests/unit/use_cases/resources/commands/test_publish_resource.py`:

```python
import pytest

from app.use_cases.resources.commands.publish_resource import (
    PublishResourceCommand, PublishResourceHandler,
    UnpublishResourceCommand, UnpublishResourceHandler,
)
from tests.unit.use_cases.resources.fakes.in_memory_resource_repository import InMemoryResourceRepository
from tests.unit.use_cases.resources.fixtures import seed_resource


@pytest.mark.asyncio
async def test_publish_then_unpublish():
    repo = InMemoryResourceRepository()
    res, _, _ = await seed_resource(repo)
    pub = PublishResourceHandler(repo)
    unpub = UnpublishResourceHandler(repo)

    r = await pub.handle(PublishResourceCommand(actor_id=res.owner_id, resource_id=res.id))
    assert r.is_success
    fetched = await repo.get_by_id(res.id)
    assert fetched.is_published is True

    r = await unpub.handle(UnpublishResourceCommand(actor_id=res.owner_id, resource_id=res.id))
    assert r.is_success
    fetched = await repo.get_by_id(res.id)
    assert fetched.is_published is False
```

Create `tests/unit/use_cases/resources/commands/test_soft_delete_resource.py`:

```python
import pytest

from app.use_cases.resources.commands.soft_delete_resource import (
    SoftDeleteResourceCommand, SoftDeleteResourceHandler,
)
from tests.unit.use_cases.resources.fakes.in_memory_resource_repository import InMemoryResourceRepository
from tests.unit.use_cases.resources.fixtures import seed_resource


@pytest.mark.asyncio
async def test_soft_delete_happy():
    repo = InMemoryResourceRepository()
    res, _, _ = await seed_resource(repo)
    handler = SoftDeleteResourceHandler(repo)
    r = await handler.handle(SoftDeleteResourceCommand(
        actor_id=res.owner_id, resource_id=res.id,
    ))
    assert r.is_success
    # After soft-delete, load_owned_resource treats it as 404.
    r2 = await handler.handle(SoftDeleteResourceCommand(
        actor_id=res.owner_id, resource_id=res.id,
    ))
    assert r2.is_failure
    assert r2.error == "ResourceNotFound"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/unit/use_cases/resources/commands/test_set_slot_duration.py tests/unit/use_cases/resources/commands/test_publish_resource.py tests/unit/use_cases/resources/commands/test_soft_delete_resource.py -v`
Expected: ImportError on each.

- [ ] **Step 3: Implement the three handlers**

Create `app/use_cases/resources/commands/set_slot_duration.py`:

```python
from __future__ import annotations
from dataclasses import dataclass
from uuid import UUID

from app.domain.resources.repository import IResourceRepository
from app.domain.shared.result import Result
from app.domain.shared.value_objects.slot_duration import SlotDuration
from app.use_cases.resources._common import load_owned_resource


@dataclass(frozen=True, slots=True)
class SetSlotDurationCommand:
    actor_id: UUID
    resource_id: UUID
    minutes: int


class SetSlotDurationHandler:
    def __init__(self, resources: IResourceRepository) -> None:
        self._resources = resources

    async def handle(self, cmd: SetSlotDurationCommand) -> Result[None]:
        loaded = await load_owned_resource(
            self._resources, resource_id=cmd.resource_id, actor_id=cmd.actor_id,
        )
        if loaded.is_failure:
            return Result.from_failure(loaded)
        res = loaded.value

        slot_r = SlotDuration.create(cmd.minutes)
        if slot_r.is_failure:
            return Result.failure(slot_r.error, status_code=400)

        upd = res.set_slot_duration(slot_r.value)
        if upd.is_failure:
            return Result.from_failure(upd, status_code=400)

        save = await self._resources.update(res)
        if save.is_failure:
            return Result.from_failure(save)
        return Result.success(None)
```

Create `app/use_cases/resources/commands/publish_resource.py`:

```python
from __future__ import annotations
from dataclasses import dataclass
from uuid import UUID

from app.domain.resources.repository import IResourceRepository
from app.domain.shared.result import Result
from app.use_cases.resources._common import load_owned_resource


@dataclass(frozen=True, slots=True)
class PublishResourceCommand:
    actor_id: UUID
    resource_id: UUID


@dataclass(frozen=True, slots=True)
class UnpublishResourceCommand:
    actor_id: UUID
    resource_id: UUID


class PublishResourceHandler:
    def __init__(self, resources: IResourceRepository) -> None:
        self._resources = resources

    async def handle(self, cmd: PublishResourceCommand) -> Result[None]:
        loaded = await load_owned_resource(
            self._resources, resource_id=cmd.resource_id, actor_id=cmd.actor_id,
        )
        if loaded.is_failure:
            return Result.from_failure(loaded)
        res = loaded.value
        res.publish()
        save = await self._resources.update(res)
        if save.is_failure:
            return Result.from_failure(save)
        return Result.success(None)


class UnpublishResourceHandler:
    def __init__(self, resources: IResourceRepository) -> None:
        self._resources = resources

    async def handle(self, cmd: UnpublishResourceCommand) -> Result[None]:
        loaded = await load_owned_resource(
            self._resources, resource_id=cmd.resource_id, actor_id=cmd.actor_id,
        )
        if loaded.is_failure:
            return Result.from_failure(loaded)
        res = loaded.value
        res.unpublish()
        save = await self._resources.update(res)
        if save.is_failure:
            return Result.from_failure(save)
        return Result.success(None)
```

Create `app/use_cases/resources/commands/soft_delete_resource.py`:

```python
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

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
    """Plan 06 ships the plumbing only. Plan 08 will inject IBookingRepository
    to (a) reject when an APPROVED future booking exists and (b) auto-reject
    PENDING bookings on the resource in the same transaction.
    """

    def __init__(self, resources: IResourceRepository) -> None:
        self._resources = resources

    async def handle(self, cmd: SoftDeleteResourceCommand) -> Result[None]:
        loaded = await load_owned_resource(
            self._resources, resource_id=cmd.resource_id, actor_id=cmd.actor_id,
        )
        if loaded.is_failure:
            return Result.from_failure(loaded)
        res = loaded.value

        del_r = res.soft_delete(now=_utcnow())
        if del_r.is_failure:
            return Result.from_failure(del_r, status_code=400)

        save = await self._resources.update(res)
        if save.is_failure:
            return Result.from_failure(save)
        return Result.success(None)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/unit/use_cases/resources/commands/ -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add app/use_cases/resources/commands/set_slot_duration.py app/use_cases/resources/commands/publish_resource.py app/use_cases/resources/commands/soft_delete_resource.py tests/unit/use_cases/resources/commands/test_set_slot_duration.py tests/unit/use_cases/resources/commands/test_publish_resource.py tests/unit/use_cases/resources/commands/test_soft_delete_resource.py
git commit -m "$(cat <<'EOF'
feat(resources): SetSlotDuration + Publish/Unpublish + SoftDelete handlers

set_slot_duration rebuilds operating_hours under the new grid and
re-validates pricing rules. publish/unpublish toggle visibility.
soft_delete is idempotent — second call returns ResourceNotFound (404)
because load_owned_resource treats deleted as missing.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 27: Owner-scoped query handlers (`GetMy` + `ListMy`) (bundled)

**Files:**
- Create: `app/use_cases/resources/queries/__init__.py` (empty)
- Create: `app/use_cases/resources/queries/get_my_resource.py`
- Create: `app/use_cases/resources/queries/list_my_resources.py`
- Test: `tests/unit/use_cases/resources/queries/__init__.py` (empty)
- Test: `tests/unit/use_cases/resources/queries/test_get_my_resource.py`
- Test: `tests/unit/use_cases/resources/queries/test_list_my_resources.py`

To return `ResourceDto` from these queries, we need owner+resource_type slug joins. The query handlers inject `IUserRepository` and `IResourceTypeRepository` for the lookup.

- [ ] **Step 1: Write the failing tests**

Create both `__init__.py` empties.

Create `tests/unit/use_cases/resources/queries/test_get_my_resource.py`:

```python
from __future__ import annotations
from uuid import uuid4

import pytest

from app.domain.accounts.role import Role
from app.domain.accounts.user import User
from app.domain.catalog.resource_type import ResourceType
from app.use_cases.resources.queries.get_my_resource import (
    GetMyResourceHandler, GetMyResourceQuery,
)
from tests.unit.use_cases.accounts.fakes.in_memory_user_repository import InMemoryUserRepository
from tests.unit.use_cases.catalog.fakes.in_memory_resource_type_repository import InMemoryResourceTypeRepository
from tests.unit.use_cases.resources.fakes.in_memory_resource_repository import InMemoryResourceRepository
from tests.unit.use_cases.resources.fixtures import seed_resource


@pytest.mark.asyncio
async def test_get_my_resource_returns_dto():
    repo = InMemoryResourceRepository()
    res, _, _ = await seed_resource(repo)

    users = InMemoryUserRepository()
    owner = User.create(
        id=res.owner_id,
        email="o@example.com", password_hash="x", role=Role.OWNER,
        full_name="O", phone=None, public_slug="my-owner",
    ).value
    # If User.create doesn't accept id, build via constructor + reset id; easier:
    owner.id = res.owner_id
    await users.add(owner)

    rts = InMemoryResourceTypeRepository()
    rt = ResourceType.create(
        slug="my-type", name="T", description="", attribute_schema=[],
    ).value
    rt.id = res.resource_type_id  # match seeded resource
    await rts.add(rt)

    handler = GetMyResourceHandler(repo, users, rts)
    r = await handler.handle(GetMyResourceQuery(actor_id=res.owner_id, resource_id=res.id))
    assert r.is_success
    assert r.value.owner_slug == "my-owner"
    assert r.value.resource_type_slug == "my-type"


@pytest.mark.asyncio
async def test_get_my_resource_not_owned_returns_404():
    repo = InMemoryResourceRepository()
    res, _, _ = await seed_resource(repo)
    handler = GetMyResourceHandler(repo, InMemoryUserRepository(), InMemoryResourceTypeRepository())
    r = await handler.handle(GetMyResourceQuery(actor_id=uuid4(), resource_id=res.id))
    assert r.is_failure
    assert r.error == "ResourceNotFound"
    assert r.status_code == 404
```

Create `tests/unit/use_cases/resources/queries/test_list_my_resources.py`:

```python
from __future__ import annotations
import pytest

from app.domain.accounts.role import Role
from app.domain.accounts.user import User
from app.domain.catalog.resource_type import ResourceType
from app.use_cases.resources.queries.list_my_resources import (
    ListMyResourcesHandler, ListMyResourcesQuery,
)
from tests.unit.use_cases.accounts.fakes.in_memory_user_repository import InMemoryUserRepository
from tests.unit.use_cases.catalog.fakes.in_memory_resource_type_repository import InMemoryResourceTypeRepository
from tests.unit.use_cases.resources.fakes.in_memory_resource_repository import InMemoryResourceRepository
from tests.unit.use_cases.resources.fixtures import seed_resource


@pytest.mark.asyncio
async def test_list_my_resources_includes_drafts_excludes_deleted():
    repo = InMemoryResourceRepository()
    res_a, _, _ = await seed_resource(repo, slug="r-a")
    res_b, _, _ = await seed_resource(repo, owner_id=res_a.owner_id, slug="r-b")
    res_c, _, _ = await seed_resource(repo, owner_id=res_a.owner_id, slug="r-c")
    res_b.publish()
    from datetime import datetime, timezone
    res_c.soft_delete(now=datetime.now(timezone.utc))
    await repo.update(res_b)
    await repo.update(res_c)

    users = InMemoryUserRepository()
    owner = User.create(
        email="o@example.com", password_hash="x", role=Role.OWNER,
        full_name="O", phone=None, public_slug="o-slug",
    ).value
    owner.id = res_a.owner_id
    await users.add(owner)

    rts = InMemoryResourceTypeRepository()
    rt = ResourceType.create(
        slug="rt", name="RT", description="", attribute_schema=[],
    ).value
    rt.id = res_a.resource_type_id
    await rts.add(rt)

    handler = ListMyResourcesHandler(repo, users, rts)
    r = await handler.handle(ListMyResourcesQuery(actor_id=res_a.owner_id))
    assert r.is_success
    slugs = {dto.slug for dto in r.value}
    assert slugs == {"r-a", "r-b"}  # draft (r-a) included; deleted (r-c) excluded
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/unit/use_cases/resources/queries/ -v`
Expected: ImportError.

- [ ] **Step 3: Implement the handlers**

Create `app/use_cases/resources/queries/get_my_resource.py`:

```python
from __future__ import annotations
from dataclasses import dataclass
from uuid import UUID

from app.domain.accounts.repository import IUserRepository
from app.domain.catalog.repository import IResourceTypeRepository
from app.domain.resources.repository import IResourceRepository
from app.domain.shared.result import Result
from app.use_cases.resources._common import load_owned_resource
from app.use_cases.resources.dtos import ResourceDto


@dataclass(frozen=True, slots=True)
class GetMyResourceQuery:
    actor_id: UUID
    resource_id: UUID


class GetMyResourceHandler:
    def __init__(
        self,
        resources: IResourceRepository,
        users: IUserRepository,
        resource_types: IResourceTypeRepository,
    ) -> None:
        self._resources = resources
        self._users = users
        self._resource_types = resource_types

    async def handle(self, q: GetMyResourceQuery) -> Result[ResourceDto]:
        loaded = await load_owned_resource(
            self._resources, resource_id=q.resource_id, actor_id=q.actor_id,
        )
        if loaded.is_failure:
            return Result.from_failure(loaded)
        res = loaded.value

        owner = await self._users.get_by_id(res.owner_id)
        rt = await self._resource_types.get_by_id(res.resource_type_id)
        owner_slug = owner.public_slug.value if (owner and owner.public_slug) else ""
        rt_slug = rt.slug.value if rt else ""
        return Result.success(
            ResourceDto.from_entity(res, owner_slug=owner_slug, resource_type_slug=rt_slug)
        )
```

Create `app/use_cases/resources/queries/list_my_resources.py`:

```python
from __future__ import annotations
from dataclasses import dataclass
from uuid import UUID

from app.domain.accounts.repository import IUserRepository
from app.domain.catalog.repository import IResourceTypeRepository
from app.domain.resources.repository import IResourceRepository
from app.domain.shared.result import Result
from app.use_cases.resources.dtos import ResourceDto


@dataclass(frozen=True, slots=True)
class ListMyResourcesQuery:
    actor_id: UUID
    limit: int = 50
    offset: int = 0


class ListMyResourcesHandler:
    def __init__(
        self,
        resources: IResourceRepository,
        users: IUserRepository,
        resource_types: IResourceTypeRepository,
    ) -> None:
        self._resources = resources
        self._users = users
        self._resource_types = resource_types

    async def handle(self, q: ListMyResourcesQuery) -> Result[list[ResourceDto]]:
        items = await self._resources.list_by_owner(
            q.actor_id, include_deleted=False, limit=q.limit, offset=q.offset,
        )
        owner = await self._users.get_by_id(q.actor_id)
        owner_slug = owner.public_slug.value if (owner and owner.public_slug) else ""

        type_ids = {r.resource_type_id for r in items}
        rt_slugs: dict = {}
        for rt_id in type_ids:
            rt = await self._resource_types.get_by_id(rt_id)
            rt_slugs[rt_id] = rt.slug.value if rt else ""

        dtos = [
            ResourceDto.from_entity(
                r, owner_slug=owner_slug,
                resource_type_slug=rt_slugs.get(r.resource_type_id, ""),
            )
            for r in items
        ]
        return Result.success(dtos)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/unit/use_cases/resources/queries/ -v`
Expected: 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add app/use_cases/resources/queries/__init__.py app/use_cases/resources/queries/get_my_resource.py app/use_cases/resources/queries/list_my_resources.py tests/unit/use_cases/resources/queries/__init__.py tests/unit/use_cases/resources/queries/test_get_my_resource.py tests/unit/use_cases/resources/queries/test_list_my_resources.py
git commit -m "$(cat <<'EOF'
feat(resources): GetMyResource + ListMyResources query handlers

Owner-scoped reads. 404-on-mismatch via load_owned_resource. Both
inject IUserRepository + IResourceTypeRepository to join owner_slug
and resource_type_slug into the DTO. ListMy includes drafts and
excludes soft-deleted.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 28: `GetPublicResourceHandler`

**Files:**
- Create: `app/use_cases/resources/queries/get_public_resource.py`
- Test: `tests/unit/use_cases/resources/queries/test_get_public_resource.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/use_cases/resources/queries/test_get_public_resource.py`:

```python
from __future__ import annotations
from datetime import datetime, timezone

import pytest

from app.domain.accounts.role import Role
from app.domain.accounts.user import User
from app.domain.catalog.resource_type import ResourceType
from app.domain.subscriptions.owner_subscription import OwnerSubscription
from app.domain.subscriptions.sub_status import SubStatus
from app.use_cases.resources.queries.get_public_resource import (
    GetPublicResourceHandler, GetPublicResourceQuery,
)
from tests.unit.use_cases.accounts.fakes.in_memory_user_repository import InMemoryUserRepository
from tests.unit.use_cases.catalog.fakes.in_memory_resource_type_repository import InMemoryResourceTypeRepository
from tests.unit.use_cases.resources.fakes.in_memory_resource_repository import InMemoryResourceRepository
from tests.unit.use_cases.subscriptions.fakes.in_memory_subscription_repository import InMemorySubscriptionRepository
from tests.unit.use_cases.resources.fixtures import seed_resource


def _now() -> datetime:
    return datetime(2026, 4, 26, 12, 0, 0, tzinfo=timezone.utc)


async def _build_environment(*, sub_status=SubStatus.ACTIVE, user_active=True, published=True):
    repo = InMemoryResourceRepository()
    res, _, _ = await seed_resource(repo, slug="arena-zl")
    if published:
        res.publish()
        await repo.update(res)
    users = InMemoryUserRepository()
    owner = User.create(
        email="o@example.com", password_hash="x", role=Role.OWNER,
        full_name="Owner", phone=None, public_slug="o-slug",
    ).value
    owner.id = res.owner_id
    if not user_active:
        owner.deactivate()
    await users.add(owner)
    rts = InMemoryResourceTypeRepository()
    rt = ResourceType.create(
        slug="football-field", name="F", description="", attribute_schema=[],
    ).value
    rt.id = res.resource_type_id
    await rts.add(rt)
    subs = InMemorySubscriptionRepository()
    sub = OwnerSubscription.create_trialing(
        owner_id=res.owner_id, trial_duration_days=3, now=_now(),
    ).value
    if sub_status is not SubStatus.TRIALING:
        sub.transition_to(sub_status, now=_now(), trial_duration_days=3)
    await subs.add(sub)
    return repo, users, rts, subs, res


@pytest.mark.asyncio
async def test_get_public_resource_happy():
    repo, users, rts, subs, res = await _build_environment(sub_status=SubStatus.ACTIVE)
    handler = GetPublicResourceHandler(repo, users, rts, subs)
    r = await handler.handle(GetPublicResourceQuery(
        owner_slug="o-slug", resource_slug="arena-zl",
    ))
    assert r.is_success
    assert r.value.slug == "arena-zl"


@pytest.mark.asyncio
async def test_get_public_resource_404_when_owner_inactive_subscription():
    repo, users, rts, subs, res = await _build_environment(sub_status=SubStatus.INACTIVE)
    handler = GetPublicResourceHandler(repo, users, rts, subs)
    r = await handler.handle(GetPublicResourceQuery(
        owner_slug="o-slug", resource_slug="arena-zl",
    ))
    assert r.is_failure
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_get_public_resource_404_when_user_deactivated():
    repo, users, rts, subs, res = await _build_environment(user_active=False)
    handler = GetPublicResourceHandler(repo, users, rts, subs)
    r = await handler.handle(GetPublicResourceQuery(
        owner_slug="o-slug", resource_slug="arena-zl",
    ))
    assert r.is_failure
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_get_public_resource_404_when_unpublished():
    repo, users, rts, subs, res = await _build_environment(published=False)
    handler = GetPublicResourceHandler(repo, users, rts, subs)
    r = await handler.handle(GetPublicResourceQuery(
        owner_slug="o-slug", resource_slug="arena-zl",
    ))
    assert r.is_failure
    assert r.status_code == 404
```

(`InMemorySubscriptionRepository` exists from Plan 05; if it lacks `get_by_owner_id`, extend it. `InMemoryUserRepository` should have `get_by_public_slug` from Task 13's fakes update.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/unit/use_cases/resources/queries/test_get_public_resource.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement the handler**

Create `app/use_cases/resources/queries/get_public_resource.py`:

```python
from __future__ import annotations
from dataclasses import dataclass

from app.domain.accounts.repository import IUserRepository
from app.domain.accounts.role import Role
from app.domain.catalog.repository import IResourceTypeRepository
from app.domain.resources.repository import IResourceRepository
from app.domain.shared.result import Result
from app.domain.subscriptions.repository import ISubscriptionRepository
from app.use_cases.resources.dtos import ResourceDto


@dataclass(frozen=True, slots=True)
class GetPublicResourceQuery:
    owner_slug: str
    resource_slug: str


class GetPublicResourceHandler:
    def __init__(
        self,
        resources: IResourceRepository,
        users: IUserRepository,
        resource_types: IResourceTypeRepository,
        subscriptions: ISubscriptionRepository,
    ) -> None:
        self._resources = resources
        self._users = users
        self._resource_types = resource_types
        self._subscriptions = subscriptions

    async def handle(self, q: GetPublicResourceQuery) -> Result[ResourceDto]:
        owner = await self._users.get_by_public_slug(q.owner_slug)
        if owner is None or owner.role is not Role.OWNER or not owner.is_active:
            return Result.failure("ResourceNotFound", status_code=404)

        sub = await self._subscriptions.get_by_owner_id(owner.id)
        if sub is None or not sub.is_operational():
            return Result.failure("ResourceNotFound", status_code=404)

        res = await self._resources.get_by_owner_and_slug(owner.id, q.resource_slug)
        if res is None or not res.is_published or res.is_deleted():
            return Result.failure("ResourceNotFound", status_code=404)

        rt = await self._resource_types.get_by_id(res.resource_type_id)
        rt_slug = rt.slug.value if rt else ""
        return Result.success(
            ResourceDto.from_entity(
                res,
                owner_slug=owner.public_slug.value,
                resource_type_slug=rt_slug,
            )
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/unit/use_cases/resources/queries/test_get_public_resource.py -v`
Expected: 4 PASS.

- [ ] **Step 5: Commit**

```bash
git add app/use_cases/resources/queries/get_public_resource.py tests/unit/use_cases/resources/queries/test_get_public_resource.py
git commit -m "$(cat <<'EOF'
feat(resources): GetPublicResourceHandler

Looks up owner via public_slug, applies the is_owner_operational gate
(Plan 05 §7), then fetches the resource by (owner_id, slug). Returns
ResourceNotFound (404) for any failed gate to avoid leaking existence.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 29: `ListPublicResourcesHandler` (with batch operational filter)

**Files:**
- Create: `app/use_cases/resources/queries/list_public_resources.py`
- Test: `tests/unit/use_cases/resources/queries/test_list_public_resources.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/use_cases/resources/queries/test_list_public_resources.py`:

```python
from __future__ import annotations
from datetime import datetime, timezone

import pytest

from app.domain.accounts.role import Role
from app.domain.accounts.user import User
from app.domain.catalog.resource_type import ResourceType
from app.domain.subscriptions.owner_subscription import OwnerSubscription
from app.domain.subscriptions.sub_status import SubStatus
from app.use_cases.resources.queries.list_public_resources import (
    ListPublicResourcesHandler, ListPublicResourcesQuery,
)
from tests.unit.use_cases.accounts.fakes.in_memory_user_repository import InMemoryUserRepository
from tests.unit.use_cases.catalog.fakes.in_memory_resource_type_repository import InMemoryResourceTypeRepository
from tests.unit.use_cases.resources.fakes.in_memory_resource_repository import InMemoryResourceRepository
from tests.unit.use_cases.subscriptions.fakes.in_memory_subscription_repository import InMemorySubscriptionRepository
from tests.unit.use_cases.resources.fixtures import seed_resource


def _now() -> datetime:
    return datetime(2026, 4, 26, 12, 0, 0, tzinfo=timezone.utc)


async def _seed(*, owner_slug: str, sub_status: SubStatus, slug: str):
    """Helper that returns (owner, sub, res) for one owner."""
    user = User.create(
        email=f"{owner_slug}@example.com", password_hash="x", role=Role.OWNER,
        full_name="O", phone=None, public_slug=owner_slug,
    ).value
    sub = OwnerSubscription.create_trialing(
        owner_id=user.id, trial_duration_days=3, now=_now(),
    ).value
    if sub_status is not SubStatus.TRIALING:
        sub.transition_to(sub_status, now=_now(), trial_duration_days=3)
    return user, sub, slug


@pytest.mark.asyncio
async def test_list_public_filters_by_operational_owner():
    repo = InMemoryResourceRepository()
    users = InMemoryUserRepository()
    rts = InMemoryResourceTypeRepository()
    subs = InMemorySubscriptionRepository()

    rt = ResourceType.create(
        slug="football-field", name="F", description="", attribute_schema=[],
    ).value
    await rts.add(rt)

    # Owner A — ACTIVE
    owner_a, sub_a, slug_a = await _seed(owner_slug="owner-a", sub_status=SubStatus.ACTIVE, slug="arena-a")
    await users.add(owner_a)
    await subs.add(sub_a)
    res_a, _, _ = await seed_resource(repo, owner_id=owner_a.id, slug=slug_a)
    res_a.resource_type_id = rt.id
    res_a.publish()
    await repo.update(res_a)

    # Owner B — INACTIVE
    owner_b, sub_b, slug_b = await _seed(owner_slug="owner-b", sub_status=SubStatus.INACTIVE, slug="arena-b")
    await users.add(owner_b)
    await subs.add(sub_b)
    res_b, _, _ = await seed_resource(repo, owner_id=owner_b.id, slug=slug_b)
    res_b.resource_type_id = rt.id
    res_b.publish()
    await repo.update(res_b)

    handler = ListPublicResourcesHandler(repo, users, rts, subs)
    r = await handler.handle(ListPublicResourcesQuery())
    assert r.is_success
    slugs = {dto.slug for dto in r.value}
    assert slugs == {"arena-a"}  # only operational owner's resource appears
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/unit/use_cases/resources/queries/test_list_public_resources.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement the handler**

Create `app/use_cases/resources/queries/list_public_resources.py`:

```python
from __future__ import annotations
from dataclasses import dataclass

from app.domain.accounts.repository import IUserRepository
from app.domain.catalog.repository import IResourceTypeRepository
from app.domain.resources.repository import IResourceRepository
from app.domain.shared.result import Result
from app.domain.subscriptions.repository import ISubscriptionRepository
from app.domain.subscriptions.sub_status import SubStatus
from app.use_cases.resources.dtos import ResourceDto


@dataclass(frozen=True, slots=True)
class ListPublicResourcesQuery:
    resource_type_slug: str | None = None
    city: str | None = None
    region: str | None = None
    limit: int = 50
    offset: int = 0


class ListPublicResourcesHandler:
    def __init__(
        self,
        resources: IResourceRepository,
        users: IUserRepository,
        resource_types: IResourceTypeRepository,
        subscriptions: ISubscriptionRepository,
    ) -> None:
        self._resources = resources
        self._users = users
        self._resource_types = resource_types
        self._subscriptions = subscriptions

    async def handle(self, q: ListPublicResourcesQuery) -> Result[list[ResourceDto]]:
        # Compute operational owner allow-list (subs ACTIVE/TRIALING ∩ users active).
        ops_subs = await self._subscriptions.list_all(
            status=SubStatus.ACTIVE.value, limit=10_000,
        )
        ops_subs += await self._subscriptions.list_all(
            status=SubStatus.TRIALING.value, limit=10_000,
        )
        op_owner_ids = [s.owner_id for s in ops_subs]
        owners = await self._users.list_by_ids(op_owner_ids)
        owner_active_by_id = {u.id: u for u in owners if u.is_active}
        operational_ids = list(owner_active_by_id.keys())
        if not operational_ids:
            return Result.success([])

        # Fetch resources filtered by the allow-list + extra query filters.
        items = await self._resources.list_published(
            resource_type_slug=q.resource_type_slug,
            city=q.city,
            region=q.region,
            owner_ids_filter=operational_ids,
            limit=q.limit,
            offset=q.offset,
        )

        # Resolve type slugs in batch (one lookup per distinct type id).
        type_ids = {r.resource_type_id for r in items}
        type_slug_by_id: dict = {}
        for rt_id in type_ids:
            rt = await self._resource_types.get_by_id(rt_id)
            type_slug_by_id[rt_id] = rt.slug.value if rt else ""

        dtos = [
            ResourceDto.from_entity(
                r,
                owner_slug=owner_active_by_id[r.owner_id].public_slug.value,
                resource_type_slug=type_slug_by_id.get(r.resource_type_id, ""),
            )
            for r in items
            if r.owner_id in owner_active_by_id
        ]
        return Result.success(dtos)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/unit/use_cases/resources/queries/test_list_public_resources.py -v`
Expected: 1 PASS.

- [ ] **Step 5: Commit**

```bash
git add app/use_cases/resources/queries/list_public_resources.py tests/unit/use_cases/resources/queries/test_list_public_resources.py
git commit -m "$(cat <<'EOF'
feat(resources): ListPublicResourcesHandler

Computes operational owner allow-list once (two subscription queries +
one user batch fetch), passes the IDs as repo filter. Resources of
non-operational owners are excluded transparently.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 30: `GetOwnerPublicPageHandler` (lives in accounts feature)

**Files:**
- Create: `app/use_cases/accounts/queries/__init__.py` (empty if not present)
- Create: `app/use_cases/accounts/queries/get_owner_public_page.py`
- Create: `app/use_cases/accounts/dtos.py` extension (or new dto file) with `OwnerPublicPageDto`
- Test: `tests/unit/use_cases/accounts/queries/__init__.py` (empty)
- Test: `tests/unit/use_cases/accounts/queries/test_get_owner_public_page.py`

- [ ] **Step 1: Write the failing tests**

Create both test `__init__.py` empties.

Create `tests/unit/use_cases/accounts/queries/test_get_owner_public_page.py`:

```python
from __future__ import annotations
from datetime import datetime, timezone

import pytest

from app.domain.accounts.role import Role
from app.domain.accounts.user import User
from app.domain.catalog.resource_type import ResourceType
from app.domain.subscriptions.owner_subscription import OwnerSubscription
from app.domain.subscriptions.sub_status import SubStatus
from app.use_cases.accounts.queries.get_owner_public_page import (
    GetOwnerPublicPageHandler, GetOwnerPublicPageQuery,
)
from tests.unit.use_cases.accounts.fakes.in_memory_user_repository import InMemoryUserRepository
from tests.unit.use_cases.catalog.fakes.in_memory_resource_type_repository import InMemoryResourceTypeRepository
from tests.unit.use_cases.resources.fakes.in_memory_resource_repository import InMemoryResourceRepository
from tests.unit.use_cases.subscriptions.fakes.in_memory_subscription_repository import InMemorySubscriptionRepository
from tests.unit.use_cases.resources.fixtures import seed_resource


def _now() -> datetime:
    return datetime(2026, 4, 26, 12, 0, 0, tzinfo=timezone.utc)


async def _build():
    users = InMemoryUserRepository()
    subs = InMemorySubscriptionRepository()
    repo = InMemoryResourceRepository()
    rts = InMemoryResourceTypeRepository()
    owner = User.create(
        email="o@example.com", password_hash="x", role=Role.OWNER,
        full_name="Owner", phone=None, public_slug="o-slug",
    ).value
    await users.add(owner)
    sub = OwnerSubscription.create_trialing(
        owner_id=owner.id, trial_duration_days=3, now=_now(),
    ).value
    sub.transition_to(SubStatus.ACTIVE, now=_now(), trial_duration_days=3)
    await subs.add(sub)
    rt = ResourceType.create(
        slug="football-field", name="F", description="", attribute_schema=[],
    ).value
    await rts.add(rt)
    res, _, _ = await seed_resource(repo, owner_id=owner.id, slug="arena-1")
    res.resource_type_id = rt.id
    res.publish()
    await repo.update(res)
    return owner, repo, users, rts, subs


@pytest.mark.asyncio
async def test_get_owner_public_page_returns_owner_and_published_resources():
    owner, repo, users, rts, subs = await _build()
    handler = GetOwnerPublicPageHandler(users, subs, repo, rts)
    r = await handler.handle(GetOwnerPublicPageQuery(owner_slug="o-slug"))
    assert r.is_success
    page = r.value
    assert page.owner_slug == "o-slug"
    assert page.full_name == "Owner"
    assert len(page.resources) == 1


@pytest.mark.asyncio
async def test_get_owner_public_page_404_for_non_owner():
    users = InMemoryUserRepository()
    subs = InMemorySubscriptionRepository()
    repo = InMemoryResourceRepository()
    rts = InMemoryResourceTypeRepository()
    cust = User.create(
        email="c@example.com", password_hash="x", role=Role.CUSTOMER,
        full_name="C", phone=None, public_slug=None,
    ).value
    await users.add(cust)
    handler = GetOwnerPublicPageHandler(users, subs, repo, rts)
    r = await handler.handle(GetOwnerPublicPageQuery(owner_slug="not-found"))
    assert r.is_failure
    assert r.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/unit/use_cases/accounts/queries/test_get_owner_public_page.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement DTO + handler**

Create `app/use_cases/accounts/queries/__init__.py` (empty if missing).

Create `app/use_cases/accounts/queries/get_owner_public_page.py`:

```python
from __future__ import annotations
from dataclasses import dataclass
from typing import Self
from uuid import UUID

from app.domain.accounts.repository import IUserRepository
from app.domain.accounts.role import Role
from app.domain.accounts.user import User
from app.domain.catalog.repository import IResourceTypeRepository
from app.domain.resources.repository import IResourceRepository
from app.domain.shared.result import Result
from app.domain.subscriptions.repository import ISubscriptionRepository
from app.use_cases.resources.dtos import ResourceDto


@dataclass(frozen=True, slots=True)
class GetOwnerPublicPageQuery:
    owner_slug: str


@dataclass(frozen=True, slots=True)
class OwnerPublicPageDto:
    owner_id: UUID
    owner_slug: str
    full_name: str
    resources: list[ResourceDto]


class GetOwnerPublicPageHandler:
    def __init__(
        self,
        users: IUserRepository,
        subscriptions: ISubscriptionRepository,
        resources: IResourceRepository,
        resource_types: IResourceTypeRepository,
    ) -> None:
        self._users = users
        self._subscriptions = subscriptions
        self._resources = resources
        self._resource_types = resource_types

    async def handle(self, q: GetOwnerPublicPageQuery) -> Result[OwnerPublicPageDto]:
        owner = await self._users.get_by_public_slug(q.owner_slug)
        if owner is None or owner.role is not Role.OWNER or not owner.is_active:
            return Result.failure("ResourceNotFound", status_code=404)

        sub = await self._subscriptions.get_by_owner_id(owner.id)
        if sub is None or not sub.is_operational():
            return Result.failure("ResourceNotFound", status_code=404)

        items = await self._resources.list_published_by_owner(owner.id)
        type_ids = {r.resource_type_id for r in items}
        rt_slug_by_id: dict = {}
        for rt_id in type_ids:
            rt = await self._resource_types.get_by_id(rt_id)
            rt_slug_by_id[rt_id] = rt.slug.value if rt else ""

        dtos = [
            ResourceDto.from_entity(
                r,
                owner_slug=owner.public_slug.value,
                resource_type_slug=rt_slug_by_id.get(r.resource_type_id, ""),
            )
            for r in items
        ]
        return Result.success(OwnerPublicPageDto(
            owner_id=owner.id,
            owner_slug=owner.public_slug.value,
            full_name=owner.full_name.value,
            resources=dtos,
        ))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/unit/use_cases/accounts/queries/test_get_owner_public_page.py -v`
Expected: 2 PASS.

- [ ] **Step 5: Commit**

```bash
git add app/use_cases/accounts/queries/__init__.py app/use_cases/accounts/queries/get_owner_public_page.py tests/unit/use_cases/accounts/queries/__init__.py tests/unit/use_cases/accounts/queries/test_get_owner_public_page.py
git commit -m "$(cat <<'EOF'
feat(accounts): GetOwnerPublicPageHandler (cross-feature query)

Lives in accounts because the query keys off owner. Composes
IUserRepository + ISubscriptionRepository + IResourceRepository +
IResourceTypeRepository. Returns OwnerPublicPageDto with owner identity
+ list of published resource DTOs. 404 hides existence on any gate
failure.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 31: Stable error codes (Plan 06) + arch test allowlist update

**Files:**
- Modify: `app/api/error_codes.py`
- Modify: `tests/unit/architecture/test_error_code_coverage.py`

- [ ] **Step 1: Add the codes to `error_codes.py`**

Modify `app/api/error_codes.py`:

1. At the top of the file, add the imports needed for the new VOs:

```python
from app.domain.resources.weekly_schedule import WeeklySchedule
from app.domain.resources.pricing_rule import PricingRule
from app.domain.resources.resource import Resource
```

2. Inside `ERROR_MESSAGES_PT_BR`, add the new entries (after the existing Plan 05 block):

```python
    # WeeklySchedule
    WeeklySchedule.WINDOWS_NOT_ORDERED: "Janelas de horário fora de ordem.",
    WeeklySchedule.WINDOWS_OVERLAP: "Janelas de horário se sobrepõem.",
    WeeklySchedule.WINDOW_NOT_ALIGNED_TO_SLOT_GRID: "Janela de horário não alinhada à grade de slots.",

    # PricingRule
    PricingRule.EMPTY_WEEKDAYS: "Regra de preço precisa de pelo menos um dia da semana.",

    # Resource entity
    Resource.PRICING_RULES_OVERLAP: "Regras de preço se sobrepõem.",
    Resource.PRICING_RULE_NOT_ALIGNED_TO_SLOT_GRID: "Regra de preço não alinhada à grade de slots.",
    Resource.PRICING_RULE_OUTSIDE_OPERATING_HOURS: "Regra de preço fora do horário de funcionamento.",
    Resource.DUPLICATE_CUSTOM_ATTRIBUTE_KEY: "Atributo customizado duplicado.",
    Resource.CUSTOM_ATTRIBUTE_KEY_CONFLICTS_WITH_BASE: "Atributo customizado conflita com atributo base.",
    Resource.RESOURCE_ALREADY_DELETED: "Recurso já está deletado.",
    Resource.DELETED_AT_NOT_TZ_AWARE: "Data de exclusão precisa ser tz-aware UTC.",

    # User extension (accounts) — Plan 06
    "PublicSlugRequiredForOwner": "Owner precisa de slug público.",
    "PublicSlugForbiddenForNonOwner": "Slug público é exclusivo de owners.",
    "PublicSlugAlreadyTaken": "Slug público já em uso.",

    # Resource handler-level
    "ResourceNotFound": "Recurso não encontrado.",
    "ResourceTypeInactive": "Tipo de recurso está inativo.",
    "TimeWindowInvalidType": "Janela de horário em formato inválido.",
```

(`ResourceTypeNotFound` and `SlugAlreadyTaken` are already in the mapping from Plan 04.)

- [ ] **Step 2: Update the arch test allowlist**

In `tests/unit/architecture/test_error_code_coverage.py`, extend `handler_level_allowlist` inside `test_no_orphan_translations_in_mapping`:

```python
        # Plan 06 — resources + accounts extension
        "PublicSlugRequiredForOwner",
        "PublicSlugForbiddenForNonOwner",
        "PublicSlugAlreadyTaken",
        "PricingRulesOverlap",
        "PricingRuleNotAlignedToSlotGrid",
        "PricingRuleOutsideOperatingHours",
        "DuplicateCustomAttributeKey",
        "CustomAttributeKeyConflictsWithBase",
        "ResourceAlreadyDeleted",
        "ResourceDeletedAtNotTzAware",
        "ResourceNotFound",
        "ResourceTypeInactive",
        "TimeWindowInvalidType",
```

Note: `WeeklySchedule.WINDOWS_*`, `WeeklySchedule.WINDOW_NOT_ALIGNED_TO_SLOT_GRID`, and `PricingRule.EMPTY_WEEKDAYS` are class constants on `BaseValueObject` subclasses, so they're auto-discovered — they do NOT need to be in the allowlist. `Resource.*` constants ARE on a `BaseEntity` subclass and need allowlisting.

- [ ] **Step 3: Run the architecture test**

Run: `.venv/bin/pytest tests/unit/architecture/ -v`
Expected: PASS.

Run the full suite:

Run: `.venv/bin/pytest -x -q`
Expected: green (or only failures that come from missing routes / e2e in later tasks).

- [ ] **Step 4: Commit**

```bash
git add app/api/error_codes.py tests/unit/architecture/test_error_code_coverage.py
git commit -m "$(cat <<'EOF'
feat(api): register Plan 06 error codes + arch test allowlist

Resources + composite VOs + User.public_slug + handler-level. The
auto-scanner picks up VO subclasses; entity-level (Resource.*) and
handler-level codes are explicit allowlist entries.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 32: Owner routes (`me_resources` package)

**Files:**
- Create: `app/api/v1/me_resources/__init__.py` (empty)
- Create: `app/api/v1/me_resources/schemas.py`
- Create: `app/api/v1/me_resources/deps.py`
- Create: `app/api/v1/me_resources/routes.py`
- Modify: `app/api/v1/router.py`

This task is structural — no new business logic. The deps/schemas wire existing handlers to FastAPI. Tests come in the e2e tasks (35-37).

- [ ] **Step 1: Write Pydantic schemas**

Create `app/api/v1/me_resources/__init__.py` (empty).

Create `app/api/v1/me_resources/schemas.py`:

```python
from __future__ import annotations
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.use_cases.resources.dtos import (
    CustomAttributeDto, PricingRuleDto, ResourceDto, TimeWindowDto, WeeklyScheduleDto,
)


class TimeWindowSchema(BaseModel):
    start: str
    end: str


class WeeklyScheduleSchema(BaseModel):
    monday: list[TimeWindowSchema] = []
    tuesday: list[TimeWindowSchema] = []
    wednesday: list[TimeWindowSchema] = []
    thursday: list[TimeWindowSchema] = []
    friday: list[TimeWindowSchema] = []
    saturday: list[TimeWindowSchema] = []
    sunday: list[TimeWindowSchema] = []


class PricingRuleSchema(BaseModel):
    weekdays: list[str]
    window: TimeWindowSchema
    price_cents: int


class CustomAttributeSchema(BaseModel):
    key: str
    label: str
    value: str


class ResourceResponse(BaseModel):
    id: UUID
    owner_id: UUID
    owner_slug: str
    resource_type_id: UUID
    resource_type_slug: str
    slug: str
    name: str
    description: str
    city: str
    region: str
    timezone: str
    slot_duration_minutes: int
    operating_hours: WeeklyScheduleSchema
    pricing_rules: list[PricingRuleSchema]
    base_price_cents: int
    customer_cancellation_cutoff_hours: int
    base_attributes: dict[str, Any]
    custom_attributes: list[CustomAttributeSchema]
    is_published: bool
    deleted_at: datetime | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_dto(cls, dto: ResourceDto) -> "ResourceResponse":
        return cls(
            id=dto.id,
            owner_id=dto.owner_id,
            owner_slug=dto.owner_slug,
            resource_type_id=dto.resource_type_id,
            resource_type_slug=dto.resource_type_slug,
            slug=dto.slug,
            name=dto.name,
            description=dto.description,
            city=dto.city,
            region=dto.region,
            timezone=dto.timezone,
            slot_duration_minutes=dto.slot_duration_minutes,
            operating_hours=WeeklyScheduleSchema(**{
                "monday": [TimeWindowSchema(**w.__dict__) for w in dto.operating_hours.monday],
                "tuesday": [TimeWindowSchema(**w.__dict__) for w in dto.operating_hours.tuesday],
                "wednesday": [TimeWindowSchema(**w.__dict__) for w in dto.operating_hours.wednesday],
                "thursday": [TimeWindowSchema(**w.__dict__) for w in dto.operating_hours.thursday],
                "friday": [TimeWindowSchema(**w.__dict__) for w in dto.operating_hours.friday],
                "saturday": [TimeWindowSchema(**w.__dict__) for w in dto.operating_hours.saturday],
                "sunday": [TimeWindowSchema(**w.__dict__) for w in dto.operating_hours.sunday],
            }),
            pricing_rules=[
                PricingRuleSchema(
                    weekdays=p.weekdays,
                    window=TimeWindowSchema(start=p.window.start, end=p.window.end),
                    price_cents=p.price_cents,
                ) for p in dto.pricing_rules
            ],
            base_price_cents=dto.base_price_cents,
            customer_cancellation_cutoff_hours=dto.customer_cancellation_cutoff_hours,
            base_attributes=dto.base_attributes,
            custom_attributes=[CustomAttributeSchema(**c.__dict__) for c in dto.custom_attributes],
            is_published=dto.is_published,
            deleted_at=dto.deleted_at,
            created_at=dto.created_at,
            updated_at=dto.updated_at,
        )


class ResourceListResponse(BaseModel):
    items: list[ResourceResponse]
    limit: int
    offset: int


# --- Request bodies ---

class CreateResourceBody(BaseModel):
    resource_type_id: UUID
    slug: str
    name: str
    description: str = ""
    city: str
    region: str
    timezone: str
    slot_duration_minutes: int
    operating_hours: WeeklyScheduleSchema
    base_price_cents: int
    customer_cancellation_cutoff_hours: int
    base_attributes: dict[str, Any] = Field(default_factory=dict)
    pricing_rules: list[PricingRuleSchema] = Field(default_factory=list)
    custom_attributes: list[CustomAttributeSchema] = Field(default_factory=list)


class UpdateResourceBody(BaseModel):
    name: str | None = None
    description: str | None = None
    city: str | None = None
    region: str | None = None
    base_price_cents: int | None = None
    customer_cancellation_cutoff_hours: int | None = None
    base_attributes: dict[str, Any] | None = None
    custom_attributes: list[CustomAttributeSchema] | None = None


class ReplaceOperatingHoursBody(BaseModel):
    operating_hours: WeeklyScheduleSchema


class ReplacePricingRulesBody(BaseModel):
    pricing_rules: list[PricingRuleSchema]


class SetSlotDurationBody(BaseModel):
    minutes: int
```

- [ ] **Step 2: Write deps**

Create `app/api/v1/me_resources/deps.py`:

```python
from __future__ import annotations
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.session import get_session
from app.infrastructure.repositories.resource_repository import SQLAlchemyResourceRepository
from app.infrastructure.repositories.resource_type_repository import SQLAlchemyResourceTypeRepository
from app.infrastructure.repositories.user_repository import UserRepository
from app.use_cases.resources.commands.create_resource import CreateResourceHandler
from app.use_cases.resources.commands.update_resource_metadata import UpdateResourceMetadataHandler
from app.use_cases.resources.commands.replace_operating_hours import ReplaceOperatingHoursHandler
from app.use_cases.resources.commands.replace_pricing_rules import ReplacePricingRulesHandler
from app.use_cases.resources.commands.replace_base_attributes import ReplaceBaseAttributesHandler
from app.use_cases.resources.commands.replace_custom_attributes import ReplaceCustomAttributesHandler
from app.use_cases.resources.commands.set_base_price import SetBasePriceHandler
from app.use_cases.resources.commands.set_cancellation_cutoff import SetCancellationCutoffHandler
from app.use_cases.resources.commands.set_slot_duration import SetSlotDurationHandler
from app.use_cases.resources.commands.publish_resource import (
    PublishResourceHandler, UnpublishResourceHandler,
)
from app.use_cases.resources.commands.soft_delete_resource import SoftDeleteResourceHandler
from app.use_cases.resources.queries.get_my_resource import GetMyResourceHandler
from app.use_cases.resources.queries.list_my_resources import ListMyResourcesHandler


def _r(s: Annotated[AsyncSession, Depends(get_session)]):
    return SQLAlchemyResourceRepository(s)


def _u(s: Annotated[AsyncSession, Depends(get_session)]):
    return UserRepository(s)


def _rt(s: Annotated[AsyncSession, Depends(get_session)]):
    return SQLAlchemyResourceTypeRepository(s)


async def get_create_handler(
    res=Depends(_r), rt=Depends(_rt), users=Depends(_u),
) -> CreateResourceHandler:
    return CreateResourceHandler(res, rt, users)


async def get_update_metadata_handler(res=Depends(_r)):
    return UpdateResourceMetadataHandler(res)


async def get_replace_hours_handler(res=Depends(_r)):
    return ReplaceOperatingHoursHandler(res)


async def get_replace_rules_handler(res=Depends(_r)):
    return ReplacePricingRulesHandler(res)


async def get_replace_base_attrs_handler(res=Depends(_r), rt=Depends(_rt)):
    return ReplaceBaseAttributesHandler(res, rt)


async def get_replace_custom_attrs_handler(res=Depends(_r)):
    return ReplaceCustomAttributesHandler(res)


async def get_set_base_price_handler(res=Depends(_r)):
    return SetBasePriceHandler(res)


async def get_set_cutoff_handler(res=Depends(_r)):
    return SetCancellationCutoffHandler(res)


async def get_set_slot_duration_handler(res=Depends(_r)):
    return SetSlotDurationHandler(res)


async def get_publish_handler(res=Depends(_r)):
    return PublishResourceHandler(res)


async def get_unpublish_handler(res=Depends(_r)):
    return UnpublishResourceHandler(res)


async def get_soft_delete_handler(res=Depends(_r)):
    return SoftDeleteResourceHandler(res)


async def get_get_my_handler(res=Depends(_r), u=Depends(_u), rt=Depends(_rt)):
    return GetMyResourceHandler(res, u, rt)


async def get_list_my_handler(res=Depends(_r), u=Depends(_u), rt=Depends(_rt)):
    return ListMyResourcesHandler(res, u, rt)
```

- [ ] **Step 3: Write routes**

Create `app/api/v1/me_resources/routes.py`:

```python
from __future__ import annotations
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.api.deps import CurrentUser, require_role
from app.api.error_handler import unwrap
from app.api.v1.me_resources.deps import (
    get_create_handler, get_update_metadata_handler, get_replace_hours_handler,
    get_replace_rules_handler, get_replace_base_attrs_handler,
    get_replace_custom_attrs_handler, get_set_base_price_handler,
    get_set_cutoff_handler, get_set_slot_duration_handler,
    get_publish_handler, get_unpublish_handler, get_soft_delete_handler,
    get_get_my_handler, get_list_my_handler,
)
from app.api.v1.me_resources.schemas import (
    CreateResourceBody, UpdateResourceBody, ReplaceOperatingHoursBody,
    ReplacePricingRulesBody, SetSlotDurationBody,
    ResourceResponse, ResourceListResponse,
)
from app.domain.accounts.role import Role
from app.domain.shared.weekday import Weekday
from app.use_cases.resources.commands.create_resource import (
    CreateResourceCommand, CustomAttributeInput, OperatingHoursInput,
    PricingRuleInput, TimeWindowInput,
)
from app.use_cases.resources.commands.update_resource_metadata import UpdateResourceMetadataCommand
from app.use_cases.resources.commands.replace_operating_hours import ReplaceOperatingHoursCommand
from app.use_cases.resources.commands.replace_pricing_rules import ReplacePricingRulesCommand
from app.use_cases.resources.commands.replace_base_attributes import ReplaceBaseAttributesCommand
from app.use_cases.resources.commands.replace_custom_attributes import ReplaceCustomAttributesCommand
from app.use_cases.resources.commands.set_base_price import SetBasePriceCommand
from app.use_cases.resources.commands.set_cancellation_cutoff import SetCancellationCutoffCommand
from app.use_cases.resources.commands.set_slot_duration import SetSlotDurationCommand
from app.use_cases.resources.commands.publish_resource import (
    PublishResourceCommand, UnpublishResourceCommand,
)
from app.use_cases.resources.commands.soft_delete_resource import SoftDeleteResourceCommand
from app.use_cases.resources.queries.get_my_resource import GetMyResourceQuery
from app.use_cases.resources.queries.list_my_resources import ListMyResourcesQuery


router = APIRouter(
    prefix="/v1/me/resources",
    tags=["me:resources"],
    dependencies=[Depends(require_role(Role.OWNER))],
)


def _hours_from_schema(body) -> OperatingHoursInput:
    days_dict = body.dict() if hasattr(body, "dict") else body.model_dump()
    days: dict[Weekday, list[TimeWindowInput]] = {}
    for wd in Weekday:
        windows = days_dict.get(wd.value.lower(), []) or []
        days[wd] = [TimeWindowInput(start=w["start"], end=w["end"]) for w in windows]
    return OperatingHoursInput(days=days)


def _rules_from_schema(rules) -> list[PricingRuleInput]:
    return [
        PricingRuleInput(
            weekdays=[Weekday(w) for w in r.weekdays],
            window=TimeWindowInput(start=r.window.start, end=r.window.end),
            price_cents=r.price_cents,
        )
        for r in rules
    ]


def _customs_from_schema(customs) -> list[CustomAttributeInput]:
    return [
        CustomAttributeInput(key=c.key, label=c.label, value=c.value)
        for c in customs
    ]


@router.post("", response_model=ResourceResponse, status_code=201)
async def create_resource(
    body: CreateResourceBody,
    user: CurrentUser,
    handler=Depends(get_create_handler),
):
    cmd = CreateResourceCommand(
        actor_id=user.user_id,
        resource_type_id=body.resource_type_id,
        slug=body.slug, name=body.name, description=body.description,
        city=body.city, region=body.region, timezone=body.timezone,
        slot_duration_minutes=body.slot_duration_minutes,
        operating_hours=_hours_from_schema(body.operating_hours),
        base_price_cents=body.base_price_cents,
        customer_cancellation_cutoff_hours=body.customer_cancellation_cutoff_hours,
        base_attributes=body.base_attributes,
        pricing_rules=_rules_from_schema(body.pricing_rules),
        custom_attributes=_customs_from_schema(body.custom_attributes),
    )
    dto = unwrap(await handler.handle(cmd))
    return ResourceResponse.from_dto(dto)


@router.get("", response_model=ResourceListResponse)
async def list_my_resources(
    user: CurrentUser,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    handler=Depends(get_list_my_handler),
):
    dtos = unwrap(await handler.handle(ListMyResourcesQuery(
        actor_id=user.user_id, limit=limit, offset=offset,
    )))
    return ResourceListResponse(
        items=[ResourceResponse.from_dto(d) for d in dtos],
        limit=limit, offset=offset,
    )


@router.get("/{resource_id}", response_model=ResourceResponse)
async def get_my_resource(
    resource_id: UUID,
    user: CurrentUser,
    handler=Depends(get_get_my_handler),
):
    dto = unwrap(await handler.handle(GetMyResourceQuery(
        actor_id=user.user_id, resource_id=resource_id,
    )))
    return ResourceResponse.from_dto(dto)


@router.patch("/{resource_id}", response_model=ResourceResponse)
async def patch_resource(
    resource_id: UUID,
    body: UpdateResourceBody,
    user: CurrentUser,
    update_metadata=Depends(get_update_metadata_handler),
    set_base_price=Depends(get_set_base_price_handler),
    set_cutoff=Depends(get_set_cutoff_handler),
    replace_base_attrs=Depends(get_replace_base_attrs_handler),
    replace_custom_attrs=Depends(get_replace_custom_attrs_handler),
    get_my=Depends(get_get_my_handler),
):
    if any(v is not None for v in (body.name, body.description, body.city, body.region)):
        unwrap(await update_metadata.handle(UpdateResourceMetadataCommand(
            actor_id=user.user_id, resource_id=resource_id,
            name=body.name, description=body.description,
            city=body.city, region=body.region,
        )))
    if body.base_price_cents is not None:
        unwrap(await set_base_price.handle(SetBasePriceCommand(
            actor_id=user.user_id, resource_id=resource_id,
            base_price_cents=body.base_price_cents,
        )))
    if body.customer_cancellation_cutoff_hours is not None:
        unwrap(await set_cutoff.handle(SetCancellationCutoffCommand(
            actor_id=user.user_id, resource_id=resource_id,
            hours=body.customer_cancellation_cutoff_hours,
        )))
    if body.base_attributes is not None:
        unwrap(await replace_base_attrs.handle(ReplaceBaseAttributesCommand(
            actor_id=user.user_id, resource_id=resource_id,
            base_attributes=body.base_attributes,
        )))
    if body.custom_attributes is not None:
        unwrap(await replace_custom_attrs.handle(ReplaceCustomAttributesCommand(
            actor_id=user.user_id, resource_id=resource_id,
            custom_attributes=_customs_from_schema(body.custom_attributes),
        )))
    dto = unwrap(await get_my.handle(GetMyResourceQuery(
        actor_id=user.user_id, resource_id=resource_id,
    )))
    return ResourceResponse.from_dto(dto)


@router.patch("/{resource_id}/operating-hours", response_model=ResourceResponse)
async def replace_operating_hours(
    resource_id: UUID,
    body: ReplaceOperatingHoursBody,
    user: CurrentUser,
    handler=Depends(get_replace_hours_handler),
    get_my=Depends(get_get_my_handler),
):
    unwrap(await handler.handle(ReplaceOperatingHoursCommand(
        actor_id=user.user_id, resource_id=resource_id,
        operating_hours=_hours_from_schema(body.operating_hours),
    )))
    dto = unwrap(await get_my.handle(GetMyResourceQuery(
        actor_id=user.user_id, resource_id=resource_id,
    )))
    return ResourceResponse.from_dto(dto)


@router.patch("/{resource_id}/pricing-rules", response_model=ResourceResponse)
async def replace_pricing_rules(
    resource_id: UUID,
    body: ReplacePricingRulesBody,
    user: CurrentUser,
    handler=Depends(get_replace_rules_handler),
    get_my=Depends(get_get_my_handler),
):
    unwrap(await handler.handle(ReplacePricingRulesCommand(
        actor_id=user.user_id, resource_id=resource_id,
        pricing_rules=_rules_from_schema(body.pricing_rules),
    )))
    dto = unwrap(await get_my.handle(GetMyResourceQuery(
        actor_id=user.user_id, resource_id=resource_id,
    )))
    return ResourceResponse.from_dto(dto)


@router.patch("/{resource_id}/slot-duration", response_model=ResourceResponse)
async def set_slot_duration(
    resource_id: UUID,
    body: SetSlotDurationBody,
    user: CurrentUser,
    handler=Depends(get_set_slot_duration_handler),
    get_my=Depends(get_get_my_handler),
):
    unwrap(await handler.handle(SetSlotDurationCommand(
        actor_id=user.user_id, resource_id=resource_id, minutes=body.minutes,
    )))
    dto = unwrap(await get_my.handle(GetMyResourceQuery(
        actor_id=user.user_id, resource_id=resource_id,
    )))
    return ResourceResponse.from_dto(dto)


@router.post("/{resource_id}/publish", response_model=ResourceResponse)
async def publish(
    resource_id: UUID,
    user: CurrentUser,
    handler=Depends(get_publish_handler),
    get_my=Depends(get_get_my_handler),
):
    unwrap(await handler.handle(PublishResourceCommand(
        actor_id=user.user_id, resource_id=resource_id,
    )))
    dto = unwrap(await get_my.handle(GetMyResourceQuery(
        actor_id=user.user_id, resource_id=resource_id,
    )))
    return ResourceResponse.from_dto(dto)


@router.post("/{resource_id}/unpublish", response_model=ResourceResponse)
async def unpublish(
    resource_id: UUID,
    user: CurrentUser,
    handler=Depends(get_unpublish_handler),
    get_my=Depends(get_get_my_handler),
):
    unwrap(await handler.handle(UnpublishResourceCommand(
        actor_id=user.user_id, resource_id=resource_id,
    )))
    dto = unwrap(await get_my.handle(GetMyResourceQuery(
        actor_id=user.user_id, resource_id=resource_id,
    )))
    return ResourceResponse.from_dto(dto)


@router.delete("/{resource_id}", status_code=204)
async def soft_delete(
    resource_id: UUID,
    user: CurrentUser,
    handler=Depends(get_soft_delete_handler),
):
    unwrap(await handler.handle(SoftDeleteResourceCommand(
        actor_id=user.user_id, resource_id=resource_id,
    )))
    return None
```

- [ ] **Step 4: Mount the router**

Modify `app/api/v1/router.py`:

```python
from app.api.v1.me_resources.routes import router as me_resources_router
# ... existing imports ...

api_router = APIRouter()
# ... existing includes ...
api_router.include_router(me_resources_router)
```

- [ ] **Step 5: Smoke-test app boots**

Run: `.venv/bin/python -c "from app.main import app; print(app)"`
Expected: prints the FastAPI app instance without import errors.

- [ ] **Step 6: Commit**

```bash
git add app/api/v1/me_resources/ app/api/v1/router.py
git commit -m "$(cat <<'EOF'
feat(api): mount /v1/me/resources owner endpoints

Generic PATCH dispatches to up to five handlers depending on body
fields (metadata, base_price, cutoff, base_attributes, custom_attributes).
Dedicated endpoints for operating-hours, pricing-rules, slot-duration,
publish/unpublish, soft-delete. All require OWNER role via JWT
middleware. Each handler call propagates failures through unwrap; the
shared session middleware rolls back on any HTTPException, making the
PATCH effectively atomic.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 33: Public routes (`public_resources` package)

**Files:**
- Create: `app/api/v1/public_resources/__init__.py` (empty)
- Create: `app/api/v1/public_resources/schemas.py`
- Create: `app/api/v1/public_resources/deps.py`
- Create: `app/api/v1/public_resources/routes.py`
- Modify: `app/api/v1/router.py`

- [ ] **Step 1: Schemas + deps + routes**

Create `app/api/v1/public_resources/__init__.py` (empty).

Create `app/api/v1/public_resources/schemas.py`:

```python
from __future__ import annotations
from uuid import UUID

from pydantic import BaseModel

from app.api.v1.me_resources.schemas import ResourceResponse, ResourceListResponse


class OwnerPublicPageResponse(BaseModel):
    owner_id: UUID
    owner_slug: str
    full_name: str
    resources: list[ResourceResponse]
```

Create `app/api/v1/public_resources/deps.py`:

```python
from __future__ import annotations
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.session import get_session
from app.infrastructure.repositories.owner_subscription_repository import (
    SQLAlchemyOwnerSubscriptionRepository,
)
from app.infrastructure.repositories.resource_repository import SQLAlchemyResourceRepository
from app.infrastructure.repositories.resource_type_repository import SQLAlchemyResourceTypeRepository
from app.infrastructure.repositories.user_repository import UserRepository
from app.use_cases.accounts.queries.get_owner_public_page import GetOwnerPublicPageHandler
from app.use_cases.resources.queries.get_public_resource import GetPublicResourceHandler
from app.use_cases.resources.queries.list_public_resources import ListPublicResourcesHandler


def _r(s: Annotated[AsyncSession, Depends(get_session)]):
    return SQLAlchemyResourceRepository(s)


def _u(s: Annotated[AsyncSession, Depends(get_session)]):
    return UserRepository(s)


def _rt(s: Annotated[AsyncSession, Depends(get_session)]):
    return SQLAlchemyResourceTypeRepository(s)


def _sub(s: Annotated[AsyncSession, Depends(get_session)]):
    return SQLAlchemyOwnerSubscriptionRepository(s)


async def get_public_resource_handler(
    res=Depends(_r), u=Depends(_u), rt=Depends(_rt), sub=Depends(_sub),
):
    return GetPublicResourceHandler(res, u, rt, sub)


async def get_list_public_handler(
    res=Depends(_r), u=Depends(_u), rt=Depends(_rt), sub=Depends(_sub),
):
    return ListPublicResourcesHandler(res, u, rt, sub)


async def get_owner_page_handler(
    u=Depends(_u), sub=Depends(_sub), res=Depends(_r), rt=Depends(_rt),
):
    return GetOwnerPublicPageHandler(u, sub, res, rt)
```

Create `app/api/v1/public_resources/routes.py`:

```python
from __future__ import annotations
from fastapi import APIRouter, Depends, Query

from app.api.error_handler import unwrap
from app.api.v1.me_resources.schemas import ResourceListResponse, ResourceResponse
from app.api.v1.public_resources.deps import (
    get_list_public_handler, get_owner_page_handler, get_public_resource_handler,
)
from app.api.v1.public_resources.schemas import OwnerPublicPageResponse
from app.use_cases.accounts.queries.get_owner_public_page import GetOwnerPublicPageQuery
from app.use_cases.resources.queries.get_public_resource import GetPublicResourceQuery
from app.use_cases.resources.queries.list_public_resources import ListPublicResourcesQuery


router = APIRouter(prefix="/v1", tags=["public:resources"])


@router.get("/resources", response_model=ResourceListResponse)
async def list_public_resources(
    type: str | None = Query(default=None, description="ResourceType slug"),
    city: str | None = Query(default=None),
    region: str | None = Query(default=None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    handler=Depends(get_list_public_handler),
):
    dtos = unwrap(await handler.handle(ListPublicResourcesQuery(
        resource_type_slug=type, city=city, region=region,
        limit=limit, offset=offset,
    )))
    return ResourceListResponse(
        items=[ResourceResponse.from_dto(d) for d in dtos],
        limit=limit, offset=offset,
    )


@router.get("/owners/{owner_slug}", response_model=OwnerPublicPageResponse)
async def get_owner_page(
    owner_slug: str,
    handler=Depends(get_owner_page_handler),
):
    page = unwrap(await handler.handle(GetOwnerPublicPageQuery(owner_slug=owner_slug)))
    return OwnerPublicPageResponse(
        owner_id=page.owner_id,
        owner_slug=page.owner_slug,
        full_name=page.full_name,
        resources=[ResourceResponse.from_dto(d) for d in page.resources],
    )


@router.get(
    "/owners/{owner_slug}/resources/{resource_slug}",
    response_model=ResourceResponse,
)
async def get_public_resource(
    owner_slug: str,
    resource_slug: str,
    handler=Depends(get_public_resource_handler),
):
    dto = unwrap(await handler.handle(GetPublicResourceQuery(
        owner_slug=owner_slug, resource_slug=resource_slug,
    )))
    return ResourceResponse.from_dto(dto)
```

Mount the router in `app/api/v1/router.py`:

```python
from app.api.v1.public_resources.routes import router as public_resources_router
# ... existing includes ...
api_router.include_router(public_resources_router)
```

- [ ] **Step 2: Smoke test**

Run: `.venv/bin/python -c "from app.main import app; print([r.path for r in app.routes])"`
Expected: includes `/v1/resources`, `/v1/owners/{owner_slug}`, `/v1/owners/{owner_slug}/resources/{resource_slug}`.

- [ ] **Step 3: Commit**

```bash
git add app/api/v1/public_resources/ app/api/v1/router.py
git commit -m "$(cat <<'EOF'
feat(api): mount public resource + owner page endpoints

GET /v1/resources, GET /v1/owners/{owner_slug}, GET
/v1/owners/{owner_slug}/resources/{resource_slug}. All anonymous.
GetOwnerPublicPageHandler lives in accounts and is wired here because
it serves a public route.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 34: E2E — owner lifecycle happy path

**Files:**
- Create: `tests/e2e/resources/__init__.py` (empty)
- Test: `tests/e2e/resources/test_owner_lifecycle.py`

- [ ] **Step 1: Write the failing e2e test**

Create `tests/e2e/resources/__init__.py` (empty).

Create `tests/e2e/resources/test_owner_lifecycle.py`:

```python
from __future__ import annotations
import pytest


@pytest.mark.asyncio
async def test_owner_lifecycle_happy_path(client, db_session):
    # Register an owner.
    register = await client.post("/v1/auth/register", json={
        "email": "owner1@example.com",
        "password": "senha-forte-1",
        "role": "OWNER",
        "full_name": "Joana da Silva",
        "phone": None,
    })
    assert register.status_code == 201, register.text
    owner_dto = register.json()
    assert owner_dto["public_slug"] == "joana-da-silva"

    login = await client.post("/v1/auth/login", json={
        "email": "owner1@example.com",
        "password": "senha-forte-1",
    })
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Admin (or seed) creates a ResourceType. For e2e, easier: insert a type via raw fixture.
    # Use existing FootballField type if seeded by fixture, or POST to /v1/admin/resource-types
    # with admin credentials. Pseudo-step:
    rt_id = await _seed_resource_type(client, db_session, slug="football-field")

    # Create resource.
    create_body = {
        "resource_type_id": rt_id,
        "slug": "arena-zl",
        "name": "Arena Zona Leste",
        "description": "campo society",
        "city": "São Paulo",
        "region": "SP",
        "timezone": "America/Sao_Paulo",
        "slot_duration_minutes": 60,
        "operating_hours": {"monday": [{"start": "08:00", "end": "22:00"}]},
        "base_price_cents": 8000,
        "customer_cancellation_cutoff_hours": 24,
        "base_attributes": {},
        "pricing_rules": [],
        "custom_attributes": [],
    }
    created = await client.post("/v1/me/resources", json=create_body, headers=headers)
    assert created.status_code == 201, created.text
    res_id = created.json()["id"]

    # Publish.
    pub = await client.post(f"/v1/me/resources/{res_id}/publish", headers=headers)
    assert pub.status_code == 200
    assert pub.json()["is_published"] is True

    # Public listing (no auth) shows it.
    public_list = await client.get("/v1/resources")
    slugs = {r["slug"] for r in public_list.json()["items"]}
    assert "arena-zl" in slugs

    # Soft-delete.
    deleted = await client.delete(f"/v1/me/resources/{res_id}", headers=headers)
    assert deleted.status_code == 204

    # Public listing no longer includes it.
    public_list_after = await client.get("/v1/resources")
    slugs_after = {r["slug"] for r in public_list_after.json()["items"]}
    assert "arena-zl" not in slugs_after


async def _seed_resource_type(client, db_session, *, slug: str) -> str:
    """Seed a ResourceType directly via repo (avoids needing admin login).
    Returns the resource_type_id as a string (UUID).
    """
    from app.domain.catalog.resource_type import ResourceType
    from app.infrastructure.repositories.resource_type_repository import (
        SQLAlchemyResourceTypeRepository,
    )
    rt = ResourceType.create(
        slug=slug, name="Football Field", description="",
        attribute_schema=[],
    ).value
    repo = SQLAlchemyResourceTypeRepository(db_session)
    await repo.add(rt)
    await db_session.commit()
    return str(rt.id)
```

(Adapt fixture names to existing `tests/e2e/conftest.py`. The `client` and `db_session` fixtures should already be set up by Plan 02/04/05 e2e tests — confirm by reading `tests/e2e/conftest.py` and `tests/conftest.py`.)

- [ ] **Step 2: Run test to verify it works**

Run: `.venv/bin/pytest tests/e2e/resources/test_owner_lifecycle.py -v`
Expected: PASS.

If failures relate to:
- `public_slug` not in register response: ensure `UserDto` returned by `RegisterUserHandler` includes it. If not, extend the DTO and the auth response schema.
- Subscription auto-create blocking the create-resource step (`is_operational` gate): trial defaults to TRIALING which is operational, so the resource should appear. If it doesn't, debug the subscription seed in `RegisterUserHandler`.

- [ ] **Step 3: Commit**

```bash
git add tests/e2e/resources/__init__.py tests/e2e/resources/test_owner_lifecycle.py
git commit -m "$(cat <<'EOF'
test(e2e): owner lifecycle (register → create → publish → list → delete)

Exercises the full happy path through every owner endpoint. Confirms
public_slug generation on registration, /v1/me/resources POST + publish
toggle, /v1/resources public listing inclusion + exclusion after
soft-delete.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 35: E2E — INACTIVE owner filter

**Files:**
- Test: `tests/e2e/resources/test_inactive_owner_filter.py`

- [ ] **Step 1: Write the test**

Create `tests/e2e/resources/test_inactive_owner_filter.py`:

```python
from __future__ import annotations
import pytest


@pytest.mark.asyncio
async def test_inactive_owner_subscription_hides_resources_from_public(
    client, db_session, admin_token,
):
    """Owner registers, creates+publishes a resource. Admin sets sub INACTIVE.
    Public listing no longer shows it; /me/resources still does.
    """
    # Register owner.
    register = await client.post("/v1/auth/register", json={
        "email": "owner2@example.com",
        "password": "senha-forte-1",
        "role": "OWNER",
        "full_name": "Pedro Costa",
        "phone": None,
    })
    owner_id = register.json()["id"]
    login = await client.post("/v1/auth/login", json={
        "email": "owner2@example.com", "password": "senha-forte-1",
    })
    owner_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    # Seed type (helper from previous task).
    from tests.e2e.resources.test_owner_lifecycle import _seed_resource_type
    rt_id = await _seed_resource_type(client, db_session, slug="football-field-2")

    # Owner creates + publishes.
    body = {
        "resource_type_id": rt_id, "slug": "ar-2", "name": "Arena 2",
        "description": "", "city": "SP", "region": "SP",
        "timezone": "America/Sao_Paulo", "slot_duration_minutes": 60,
        "operating_hours": {"monday": [{"start": "08:00", "end": "22:00"}]},
        "base_price_cents": 8000, "customer_cancellation_cutoff_hours": 24,
        "base_attributes": {}, "pricing_rules": [], "custom_attributes": [],
    }
    created = await client.post("/v1/me/resources", json=body, headers=owner_headers)
    res_id = created.json()["id"]
    await client.post(f"/v1/me/resources/{res_id}/publish", headers=owner_headers)

    # Resource is initially visible (TRIALING is operational).
    pub1 = await client.get("/v1/resources")
    assert "ar-2" in {r["slug"] for r in pub1.json()["items"]}

    # Admin sets sub to INACTIVE.
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    deact = await client.post(
        f"/v1/admin/owners/{owner_id}/subscription",
        json={"status": "INACTIVE"},
        headers=admin_headers,
    )
    assert deact.status_code == 200

    # Public listing no longer shows.
    pub2 = await client.get("/v1/resources")
    assert "ar-2" not in {r["slug"] for r in pub2.json()["items"]}

    # /me/resources still shows.
    mine = await client.get("/v1/me/resources", headers=owner_headers)
    assert "ar-2" in {r["slug"] for r in mine.json()["items"]}

    # Admin reactivates.
    react = await client.post(
        f"/v1/admin/owners/{owner_id}/subscription",
        json={"status": "ACTIVE"},
        headers=admin_headers,
    )
    assert react.status_code == 200
    pub3 = await client.get("/v1/resources")
    assert "ar-2" in {r["slug"] for r in pub3.json()["items"]}
```

(`admin_token` fixture comes from Plan 05 e2e tests. If it doesn't exist, add it to `tests/e2e/conftest.py` — register an admin via fixture seeding, then login.)

- [ ] **Step 2: Run the test**

Run: `.venv/bin/pytest tests/e2e/resources/test_inactive_owner_filter.py -v`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/e2e/resources/test_inactive_owner_filter.py
git commit -m "$(cat <<'EOF'
test(e2e): subscription INACTIVE hides resources from public listing

Confirms the is_owner_operational gate composition: admin flips
subscription INACTIVE → /v1/resources excludes; /me/resources still
includes; reactivation brings the resource back.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 36: E2E — validation envelope on create-resource

**Files:**
- Test: `tests/e2e/resources/test_create_resource_validation_envelope.py`

- [ ] **Step 1: Write the test**

Create `tests/e2e/resources/test_create_resource_validation_envelope.py`:

```python
from __future__ import annotations
import pytest


@pytest.mark.asyncio
async def test_create_resource_validation_envelope_aggregates_errors(
    client, db_session,
):
    # Register OWNER.
    register = await client.post("/v1/auth/register", json={
        "email": "envelope-owner@example.com",
        "password": "senha-forte-1",
        "role": "OWNER",
        "full_name": "Envelope Tester",
        "phone": None,
    })
    login = await client.post("/v1/auth/login", json={
        "email": "envelope-owner@example.com", "password": "senha-forte-1",
    })
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    # Seed a type that requires surface_type.
    from app.domain.catalog.attribute import AttrType, AttributeDefinition
    from app.domain.catalog.resource_type import ResourceType
    from app.infrastructure.repositories.resource_type_repository import (
        SQLAlchemyResourceTypeRepository,
    )
    rt = ResourceType.create(
        slug="football-field-3", name="F", description="",
        attribute_schema=[
            AttributeDefinition.create(
                key="surface_type", label="Surface", data_type=AttrType.ENUM,
                required=True, enum_values=["GRASS", "SAND"],
            ).value,
        ],
    ).value
    repo = SQLAlchemyResourceTypeRepository(db_session)
    await repo.add(rt)
    await db_session.commit()

    # POST with multiple invalid fields: bad slug + empty name + missing surface_type.
    body = {
        "resource_type_id": str(rt.id),
        "slug": "INVALID!!!",
        "name": "",
        "description": "",
        "city": "São Paulo",
        "region": "SP",
        "timezone": "America/Sao_Paulo",
        "slot_duration_minutes": 60,
        "operating_hours": {"monday": [{"start": "08:00", "end": "22:00"}]},
        "base_price_cents": 8000,
        "customer_cancellation_cutoff_hours": 24,
        "base_attributes": {},
        "pricing_rules": [],
        "custom_attributes": [],
    }
    response = await client.post("/v1/me/resources", json=body, headers=headers)
    assert response.status_code == 400, response.text
    detail = response.json()["detail"]
    assert detail["code"] == "ValidationFailed"
    fields = {entry["field"] for entry in detail["details"]}
    assert "slug" in fields
    assert "name" in fields
    assert "base_attributes.surface_type" in fields
```

- [ ] **Step 2: Run the test**

Run: `.venv/bin/pytest tests/e2e/resources/test_create_resource_validation_envelope.py -v`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/e2e/resources/test_create_resource_validation_envelope.py
git commit -m "$(cat <<'EOF'
test(e2e): create-resource emits ValidationFailed envelope with details

POST with bad slug + empty name + missing required base_attribute
returns 400 ValidationFailed and details[] contains entries for slug,
name, and base_attributes.surface_type — proves the cross-feature
aggregation pattern works end to end.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 37: Plan 05 follow-up #5 — `RegisterUserHandler` raw-pt-BR codes → stable codes

**Files:**
- Modify: `app/api/error_codes.py`
- Modify: `tests/unit/architecture/test_error_code_coverage.py`
- Modify: `app/use_cases/accounts/commands/register_user.py`
- Modify: `tests/unit/use_cases/accounts/commands/test_register_user.py` (and any e2e that asserts on the raw strings)

The three codes are added in **the same commit** as the handler change so the arch test stays green. The codes themselves (entries in `ERROR_MESSAGES_PT_BR` + allowlist) and the handler edits ship together.

- [ ] **Step 1: Write/extend the failing test**

Modify `tests/unit/use_cases/accounts/commands/test_register_user.py`. Find the existing tests that assert `r.error == "Não é permitido registrar..."` (or similar pt-BR substrings) and replace with stable-code assertions. Add new tests if missing:

```python
@pytest.mark.asyncio
async def test_register_admin_via_public_endpoint_rejected(
    user_repo, sub_repo, hasher, settings,
):
    handler = RegisterUserHandler(user_repo, hasher, sub_repo, settings)
    cmd = RegisterUserCommand(
        email="a@example.com", password="senha-forte-1", role=Role.ADMIN,
        full_name="Admin", phone=None,
    )
    r = await handler.handle(cmd)
    assert r.is_failure
    assert r.error == "AdminRegistrationForbidden"
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_register_password_too_short(
    user_repo, sub_repo, hasher, settings,
):
    handler = RegisterUserHandler(user_repo, hasher, sub_repo, settings)
    cmd = RegisterUserCommand(
        email="x@example.com", password="123", role=Role.CUSTOMER,
        full_name="X", phone=None,
    )
    r = await handler.handle(cmd)
    assert r.is_failure
    assert r.error == "PasswordTooShort"
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_register_email_already_registered(
    user_repo, sub_repo, hasher, settings,
):
    existing = User.create(
        email="dup@example.com", password_hash="x", role=Role.CUSTOMER,
        full_name="Existing", phone=None, public_slug=None,
    ).value
    await user_repo.add(existing)
    handler = RegisterUserHandler(user_repo, hasher, sub_repo, settings)
    cmd = RegisterUserCommand(
        email="dup@example.com", password="senha-forte-1", role=Role.CUSTOMER,
        full_name="New", phone=None,
    )
    r = await handler.handle(cmd)
    assert r.is_failure
    assert r.error == "EmailAlreadyRegistered"
    assert r.status_code == 409
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/unit/use_cases/accounts/commands/test_register_user.py -v -k "admin_via_public or password_too_short or email_already_registered"`
Expected: FAIL.

- [ ] **Step 3: Modify the handler**

Update the three failure branches in `app/use_cases/accounts/commands/register_user.py`:

```python
        if not cmd.role.is_self_registerable():
            return Result.failure(
                "AdminRegistrationForbidden",
                status_code=403,
            )

        if len(cmd.password) < MIN_PASSWORD_LENGTH:
            return Result.failure(
                "PasswordTooShort",
                status_code=422,
            )

        existing = await self._users.get_by_email(cmd.email)
        if existing is not None:
            return Result.failure(
                "EmailAlreadyRegistered",
                status_code=409,
            )
```

- [ ] **Step 4: Add codes to error_codes.py + allowlist**

In `app/api/error_codes.py`, add to `ERROR_MESSAGES_PT_BR` (in the handler-level section):

```python
    # Plan 05 follow-up #5 — RegisterUserHandler stable codes
    "AdminRegistrationForbidden": "Não é permitido registrar contas admin via cadastro público.",
    "PasswordTooShort": f"Senha precisa ter ao menos {MIN_PASSWORD_LENGTH} caracteres.",
    "EmailAlreadyRegistered": "Email já cadastrado.",
```

Add the import for `MIN_PASSWORD_LENGTH` at the top:

```python
from app.use_cases.accounts.commands.register_user import MIN_PASSWORD_LENGTH
```

If circular import is a concern, hard-code the value `8` in the message string and add a comment cross-referencing the constant.

In `tests/unit/architecture/test_error_code_coverage.py`, extend `handler_level_allowlist`:

```python
        # Plan 05 follow-up #5
        "AdminRegistrationForbidden",
        "PasswordTooShort",
        "EmailAlreadyRegistered",
```

- [ ] **Step 5: Update any e2e tests that asserted on the old strings**

Run: `grep -rn "Não é permitido registrar\|Senha precisa ter ao menos\|Email já cadastrado:" tests/ app/`
Expected: only the entries in `error_codes.py`. If any e2e test asserts on the old pt-BR strings inside the `detail.message`, update them to assert `detail.code == "AdminRegistrationForbidden"` (or the relevant code) instead.

- [ ] **Step 6: Run the full suite**

Run: `.venv/bin/pytest -x -q`
Expected: green.

- [ ] **Step 7: Commit**

```bash
git add app/api/error_codes.py app/use_cases/accounts/commands/register_user.py tests/unit/architecture/test_error_code_coverage.py tests/unit/use_cases/accounts/commands/test_register_user.py
git commit -m "$(cat <<'EOF'
refactor(accounts): RegisterUserHandler stable error codes (Plan 05 #5)

Replaces three raw-pt-BR error strings with stable identifiers:
AdminRegistrationForbidden (403), PasswordTooShort (422),
EmailAlreadyRegistered (409). Codes registered in error_codes.py +
arch test allowlist. Fixes Plan 05 follow-up #5.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 38: Plan 05 follow-up #6 — refresh canonical spec §5.5

**Files:**
- Modify: `docs/superpowers/specs/2026-04-25-venue-backend-design.md` (section §5.5 only)

This is a doc-only edit. The Plan 05 design doc (`docs/superpowers/specs/2026-04-26-plan-05-owner-subscription-design.md`) is the source of truth for the deltas; copy them into the canonical spec.

- [ ] **Step 1: Read both files**

Open both:
- `docs/superpowers/specs/2026-04-25-venue-backend-design.md` — find §5.5 `subscriptions` — `OwnerSubscription`.
- `docs/superpowers/specs/2026-04-26-plan-05-owner-subscription-design.md` — sections §3.1, §3.2, §3.3, §4 cover the implemented schema.

- [ ] **Step 2: Apply the deltas to the canonical §5.5**

Edit the canonical spec §5.5 to match what Plan 05 actually shipped:

- **Drop** the `notes: ShortDescription` field.
- **Add** `trial_ends_at: datetime | None  # tz-aware UTC; required iff status=TRIALING`.
- Update the **Invariants** subsection:
  - Remove any reference to `notes`.
  - Add: "Cross-field invariant: `status == TRIALING` ⇔ `trial_ends_at is not None` (enforced in `__post_init__`)."
  - Add: "Auto-created in `TRIALING` status when a `User` registers with `role=OWNER` (atomic with the user insert, single AsyncSession). `trial_ends_at = registered_at + Settings.trial_duration_days` (default 3 days)."
  - Add: "Trial expiry: nightly cron handler `ExpireTrialingSubscriptionsHandler` flips `TRIALING → INACTIVE` for rows whose `trial_ends_at < now`. Stale-state window bounded by cron interval (acceptable per §3 decision 9 — soft subscription, no money at stake)."

The canonical §5.5 should end up looking roughly like (use this as the target):

```
### 5.5 `subscriptions` — `OwnerSubscription`

OwnerSubscription
├── id: UUID
├── owner_id: UUID (unique)
├── status: SubStatus (ACTIVE | TRIALING | PAST_DUE | INACTIVE)
├── status_changed_at: datetime          # tz-aware UTC
├── trial_ends_at: datetime | None       # tz-aware UTC; required iff status=TRIALING
└── created_at, updated_at

Invariants
- One row per owner.
- Cross-field: status == TRIALING ⇔ trial_ends_at is not None.
- Auto-created in TRIALING when User registers with role=OWNER (atomic with the user insert,
  shared AsyncSession). trial_ends_at = now + Settings.trial_duration_days (default 3).
- Only SetOwnerSubscriptionStatusHandler (admin-only) mutates status; idempotent on no-op.
- ExpireTrialingSubscriptionsHandler nightly cron flips TRIALING → INACTIVE for rows with
  trial_ends_at < now.
- is_operational() returns true when status ∈ {ACTIVE, TRIALING}. Plan 06 PublicListResources
  composes this with User.is_active for the operational gate.
```

(Refer to Plan 05 design §3 for the exact wording if any nuance is unclear; this version is concise but accurate.)

- [ ] **Step 3: Commit**

```bash
git add docs/superpowers/specs/2026-04-25-venue-backend-design.md
git commit -m "$(cat <<'EOF'
docs(spec): refresh canonical §5.5 with Plan 05 deltas

Drops `notes` field, adds `trial_ends_at`, documents auto-create on
owner registration + trial expiry cron + cross-field invariant. Fixes
Plan 05 follow-up #6.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 39: Final verification

**No file changes — verification + cleanup steps only.**

- [ ] **Step 1: Run the full test suite**

Run: `.venv/bin/pytest -x -q`
Expected: ALL PASS.

If any failures appear, triage:
- Architecture test failure → a code is in `ERROR_MESSAGES_PT_BR` without an allowlist entry, or vice versa. Add the missing entry.
- Type/import errors → fix and re-run.
- Repo round-trip issues → likely `_ensure_utc` missing somewhere; check the SQLite case for the affected field.

- [ ] **Step 2: Run the `; ` tripwire**

Run: `grep -rn '"; "' app/domain app/use_cases | grep -v __pycache__`
Expected: empty output (no `"; "` joined error strings remain).

- [ ] **Step 3: Run the linter / type-check if configured**

Run: `make lint` (if defined) or whichever the project uses.
Expected: clean.

- [ ] **Step 4: Smoke-test the API boots**

Run: `.venv/bin/python -c "from app.main import app; print('routes:', len(app.routes))"`
Expected: prints route count > 30 (rough sanity).

- [ ] **Step 5: Boot the app locally + curl one public endpoint**

Run in one terminal: `make run` (or `./start_services.sh`).
Run in another: `curl http://localhost:8000/v1/resources`
Expected: 200 with `{"items": [], "limit": 50, "offset": 0}` (no published resources yet).

Stop the dev server.

- [ ] **Step 6: Update memory `MEMORY.md`**

Append progress note (or update `project_plan_progress.md` directly):

```
| 06 | resources (Resource aggregate; depends on accounts + catalog; folds Plan 05 follow-ups #5 + #6) | ✅ done <YYYY-MM-DD> |
```

Record the final commit SHA in the memory entry.

- [ ] **Step 7: Optional — remove resolved follow-ups from `project_open_followups.md`**

Move items #5 and #6 to the "Resolved items" section with the implementation commit references.

- [ ] **Step 8: Final commit (if memory was edited inside the repo)**

Memory files live outside `app/`; no commit needed for those — they're in `~/.claude/projects/...`. If anything else changed (e.g., a stray import), commit it.

```bash
git status   # ensure clean
```

---

## Plan 06 — done.

The next plan in the roadmap is **Plan 07 — Notifications** (per the canonical spec §8).
