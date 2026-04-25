# Plan 04 — `catalog` feature (`ResourceType` aggregate)

> **STATUS: PRE-RELEASE / NEEDS REVISION.** Originally drafted as Plan 03 before the VO foundation work was inserted as the new Plan 03 (see `docs/superpowers/specs/2026-04-25-venue-backend-design.md` §8). The mechanical structure (file layout, task split, units A/B/C/D) is still valid, but the **content** must be revised after Plan 03 completes to use the VOs that ship there: `Slug`, `Name`, `ShortDescription`, `AttributeKey`, `ShortName`, plus the entity convention from spec §4.4. Do NOT execute this plan as-is.
>
> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the `catalog` feature from scratch — `ResourceType` aggregate with a list of `AttributeDefinition` VOs, admin CRUD endpoints (`POST/GET/PATCH/DELETE /v1/admin/resource-types`), public listing (`GET /v1/catalog/resource-types`), and a `validate_attributes(values)` helper that the future `resources` feature will use to validate `Resource.base_attributes`. Leave `feat/plan-04-catalog` ready to ff-merge into `main` with all tests green.

**Architecture:** New domain feature `catalog/` with one aggregate (`ResourceType`) and one port (`IResourceTypeRepository`). One new shared VO (`Slug`) lives in `app/domain/shared/value_objects/` because the future `resources` feature will reuse it. `attribute_schema` is persisted as a JSON column on the `resource_types` table (works on Postgres + SQLite). Admin endpoints reuse the existing `require_role(Role.ADMIN)` guard from `app/api/deps.py`; public listing has no auth gate. No cross-feature handlers in this plan — `catalog` has zero feature dependencies (per spec §8 "Bootstrap procedure").

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0 async, Alembic. No new third-party libraries — JSON storage uses SQLAlchemy's built-in `JSON` type which adapts to Postgres `JSON` and SQLite `TEXT`.

**Decisions pinned (do NOT re-debate during execution):**

| # | Decision | Rationale |
|---|---|---|
| 1 | `Slug` is a shared VO under `app/domain/shared/value_objects/slug.py`. | Resources will also have a slug; spec §5.3. |
| 2 | `AttrType` is a `str` Enum with values `string`, `int`, `bool`, `enum` (lowercase). | Matches JSON wire format; no need to translate at the API boundary. |
| 3 | `AttributeDefinition.enum_values` is non-None **iff** `data_type == AttrType.ENUM`. Validated in `AttributeDefinition.create()`. | Keeps the VO self-consistent; eliminates a class of "ENUM with no values" bugs. |
| 4 | `attribute_schema` is persisted as a JSON column (`sa.JSON()` — generic, dialect-portable). The repository serializes `AttributeDefinition` ↔ dict at the boundary. | Avoids a separate `attribute_definitions` table for what is conceptually a typed list; simple to query, simple to evolve. |
| 5 | `UpdateResourceTypeHandler` accepts partial updates (name/description/attribute_schema/is_active) but `attribute_schema` is REPLACED wholesale when provided (no per-key patching). | Per-key patching is harder to validate consistently; replacement is what the admin UI will do anyway. |
| 6 | `DeleteResourceTypeHandler` does **NOT** check whether any `Resource` references this type. The "blocked if referenced" invariant from spec §5.2 is deferred to Plan 04 (`resources`), which will inject `IResourceRepository` and add the check. A `# TODO(plan-04)` comment marks the gap. | `Resource` does not exist yet — the check would be vacuous now. Adding a Protocol stub now would just be ceremony. |
| 7 | Pagination uses `limit` + `offset` query params on list endpoints, mirroring `app/api/v1/admin_users/routes.py`. | Consistency with `accounts`. |
| 8 | Public list (`GET /v1/catalog/resource-types`) returns ONLY `is_active = True` rows. Admin list (`GET /v1/admin/resource-types`) returns all rows including inactive. | Public is for filter UI on the storefront; admin is for management. |
| 9 | Error messages in domain validation are Portuguese (matches `accounts/`). Error messages in handler-level errors are Portuguese. API field-validation errors stay in the language Pydantic produces (English) — no extra translation layer. | Project convention from Plan 02. |
| 10 | No `ListResourceTypesQuery` / `GetResourceTypeQuery` handlers. List + detail are pure DB reads; routes call the repo directly. | Mirrors `admin_users/routes.py` from Plan 02 — no business logic worth wrapping. |
| 11 | The `validate_attributes(values: dict[str, Any]) -> Result[None]` method lives on the `ResourceType` entity (not on a separate validator). | The schema lives on the entity; co-locating the validator keeps callers simple — `resource_type.validate_attributes(...)`. |

---

## File Structure

### New files

```
app/domain/shared/value_objects/
└── slug.py                                       # Slug VO (shared with future Resource)

app/domain/catalog/
├── __init__.py
├── attribute.py                                  # AttrType enum + AttributeDefinition VO
├── resource_type.py                              # ResourceType aggregate (incl. validate_attributes)
└── repository.py                                 # IResourceTypeRepository Protocol

app/use_cases/catalog/
├── __init__.py
├── dtos.py                                       # ResourceTypeDto + AttributeDefinitionDto
└── commands/
    ├── __init__.py
    ├── create_resource_type.py
    ├── update_resource_type.py
    └── delete_resource_type.py

app/infrastructure/db/mappings/
└── resource_type.py                              # ResourceTypeModel (resource_types table)

app/infrastructure/repositories/
└── resource_type_repository.py                   # SQLAlchemy adapter

app/api/v1/admin_resource_types/
├── __init__.py
├── deps.py                                       # handler DI
├── routes.py                                     # POST/GET/PATCH/DELETE /v1/admin/resource-types
└── schemas.py

app/api/v1/catalog/
├── __init__.py
├── routes.py                                     # GET /v1/catalog/resource-types
└── schemas.py

app/migrations/versions/
└── <timestamp>_catalog_resource_types_table.py   # creates resource_types table
```

### Modified files

```
app/api/v1/router.py                              # include admin_resource_types_router + catalog_router
app/migrations/env.py                             # import the new mapping module
```

### Test files (new)

```
tests/unit/domain/shared/value_objects/
└── test_slug.py

tests/unit/domain/catalog/
├── __init__.py
├── test_attribute.py
└── test_resource_type.py

tests/unit/use_cases/catalog/
├── __init__.py
├── commands/
│   ├── __init__.py
│   ├── test_create_resource_type.py
│   ├── test_update_resource_type.py
│   └── test_delete_resource_type.py
└── fakes/
    ├── __init__.py
    └── in_memory_resource_type_repository.py

tests/integration/catalog/
├── __init__.py
└── test_resource_type_repository.py

tests/e2e/catalog/
├── __init__.py
└── test_admin_and_public_flow.py
```

### Database migration

A single auto-generated Alembic revision creates the `resource_types` table:

| Column | Type | Constraints |
|---|---|---|
| `id` | CHAR(36) | PK |
| `slug` | VARCHAR(80) | NOT NULL, UNIQUE, indexed |
| `name` | VARCHAR(200) | NOT NULL |
| `description` | VARCHAR(1000) | NOT NULL, default `""` |
| `attribute_schema` | JSON | NOT NULL, default `[]` |
| `is_active` | BOOLEAN | NOT NULL, default TRUE, indexed |
| `created_at` | DATETIME | NOT NULL (from `TimestampMixin`) |
| `updated_at` | DATETIME | NOT NULL (from `TimestampMixin`) |

No foreign keys. No cross-table joins.

---

## Execution Plan — four units

Each unit is one implementer dispatch. Reviewers (spec compliance + code quality) run between units.

| Unit | Tasks | Approx commits |
|---|---|---|
| **A** | Domain layer | 4 |
| **B** | Infrastructure (mapping + repo + migration) | 3 |
| **C** | Use cases (Create / Update / Delete handlers + DTOs + fake repo) | 4 |
| **D** | API layer + e2e tests | 4 |

Total: **~15 commits**. Branch: `feat/plan-03-catalog`. ff-merges into `main` after final review.

---

## UNIT A — Domain layer

### Task A1 — `Slug` shared VO

**Files:** `app/domain/shared/value_objects/slug.py`, `tests/unit/domain/shared/value_objects/test_slug.py`.

- [ ] **Step 1: Failing test**

`tests/unit/domain/shared/value_objects/test_slug.py`:

```python
from __future__ import annotations
from app.domain.shared.value_objects.slug import Slug


def test_slug_create_success_lowercase():
    r = Slug.create("football-field")
    assert r.is_success
    assert r.value.value == "football-field"
    assert str(r.value) == "football-field"


def test_slug_create_strips_and_lowercases():
    r = Slug.create("  Football-Field  ")
    assert r.is_success
    assert r.value.value == "football-field"


def test_slug_create_rejects_empty():
    r = Slug.create("")
    assert r.is_failure
    assert "slug" in r.error.lower()


def test_slug_create_rejects_none():
    r = Slug.create(None)
    assert r.is_failure


def test_slug_create_rejects_invalid_chars():
    for bad in ["foo bar", "foo_bar", "foo.bar", "foo!bar", "ção"]:
        r = Slug.create(bad)
        assert r.is_failure, f"expected failure for {bad!r}"


def test_slug_create_rejects_leading_digit():
    r = Slug.create("1foo")
    assert r.is_failure


def test_slug_create_rejects_leading_or_trailing_dash():
    assert Slug.create("-foo").is_failure
    assert Slug.create("foo-").is_failure


def test_slug_create_accepts_digits_after_first_char():
    r = Slug.create("foo-123-bar")
    assert r.is_success
    assert r.value.value == "foo-123-bar"


def test_slug_create_rejects_too_long():
    r = Slug.create("a" + "b" * 80)
    assert r.is_failure


def test_slug_create_rejects_too_short():
    r = Slug.create("a")
    assert r.is_failure
    r = Slug.create("ab")
    assert r.is_success


def test_slug_value_object_equality():
    a = Slug.create("foo").value
    b = Slug.create("foo").value
    assert a == b
    assert hash(a) == hash(b)
```

- [ ] **Step 2: Run — expect FAIL.**

```bash
.venv/bin/pytest tests/unit/domain/shared/value_objects/test_slug.py -q
```

Expect: `ModuleNotFoundError: No module named 'app.domain.shared.value_objects.slug'`.

- [ ] **Step 3: Implement**

`app/domain/shared/value_objects/slug.py`:

```python
from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Self
from app.domain.shared.result import Result
from app.domain.shared.value_object import BaseValueObject

# 2-80 chars, must start with [a-z], remainder may contain [a-z0-9-],
# must not end with a dash. No consecutive dashes constraint — `foo--bar`
# is allowed (rare in practice).
SLUG_RE = re.compile(r"^[a-z][a-z0-9-]{0,78}[a-z0-9]$")


@dataclass(frozen=True, slots=True)
class Slug(BaseValueObject):
    value: str  # lowercase, no surrounding whitespace

    @classmethod
    def create(cls, raw) -> Result[Self]:
        if raw is None or not isinstance(raw, str):
            return Result.failure("Slug: valor obrigatório.")
        normalized = raw.strip().lower()
        if not normalized:
            return Result.failure("Slug: não pode ser vazio.")
        if len(normalized) < 2 or len(normalized) > 80:
            return Result.failure("Slug: deve ter entre 2 e 80 caracteres.")
        if not SLUG_RE.match(normalized):
            return Result.failure(
                f"Slug inválido: '{raw}'. Use apenas a-z, 0-9 e hífen; "
                "comece com letra; não termine com hífen."
            )
        return Result.success(cls(value=normalized))

    def __str__(self) -> str:
        return self.value
```

- [ ] **Step 4: Run — expect PASS.**

```bash
.venv/bin/pytest tests/unit/domain/shared/value_objects/test_slug.py -q
```

- [ ] **Step 5: Commit**

```bash
git add app/domain/shared/value_objects/slug.py tests/unit/domain/shared/value_objects/test_slug.py
git commit -m "$(cat <<'EOF'
feat(shared): add Slug value object

Slug enforces the URL-friendly format used by ResourceType.slug
(plan 03) and Resource.slug (plan 04 — design §5.3).

  - 2-80 chars, lowercase
  - must start with a-z
  - body may contain a-z0-9 and hyphens
  - must not end with a hyphen

Lives in shared/ because two features need it.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

### Task A2 — `AttrType` enum + `AttributeDefinition` VO

**Files:** `app/domain/catalog/__init__.py` (empty), `app/domain/catalog/attribute.py`, `tests/unit/domain/catalog/__init__.py` (empty), `tests/unit/domain/catalog/test_attribute.py`.

- [ ] **Step 1: Failing test**

`tests/unit/domain/catalog/test_attribute.py`:

```python
from __future__ import annotations
from app.domain.catalog.attribute import AttributeDefinition, AttrType


def test_attr_type_values():
    assert AttrType.STRING.value == "string"
    assert AttrType.INT.value == "int"
    assert AttrType.BOOL.value == "bool"
    assert AttrType.ENUM.value == "enum"


def test_attribute_definition_create_string():
    r = AttributeDefinition.create(
        key="surface",
        label="Tipo de piso",
        data_type=AttrType.STRING,
        required=True,
        enum_values=None,
    )
    assert r.is_success
    a = r.value
    assert a.key == "surface"
    assert a.label == "Tipo de piso"
    assert a.data_type is AttrType.STRING
    assert a.required is True
    assert a.enum_values is None


def test_attribute_definition_create_enum_with_values():
    r = AttributeDefinition.create(
        key="lighting",
        label="Iluminação",
        data_type=AttrType.ENUM,
        required=False,
        enum_values=["natural", "artificial", "mista"],
    )
    assert r.is_success
    a = r.value
    assert a.data_type is AttrType.ENUM
    assert a.enum_values == ("natural", "artificial", "mista")  # tuple — frozen


def test_attribute_definition_create_enum_without_values_fails():
    r = AttributeDefinition.create(
        key="lighting", label="X", data_type=AttrType.ENUM,
        required=False, enum_values=None,
    )
    assert r.is_failure
    assert "enum" in r.error.lower()


def test_attribute_definition_create_enum_empty_values_fails():
    r = AttributeDefinition.create(
        key="lighting", label="X", data_type=AttrType.ENUM,
        required=False, enum_values=[],
    )
    assert r.is_failure


def test_attribute_definition_create_enum_duplicate_values_fails():
    r = AttributeDefinition.create(
        key="lighting", label="X", data_type=AttrType.ENUM,
        required=False, enum_values=["a", "b", "a"],
    )
    assert r.is_failure
    assert "duplicad" in r.error.lower() or "duplicate" in r.error.lower()


def test_attribute_definition_create_non_enum_with_values_fails():
    r = AttributeDefinition.create(
        key="size", label="X", data_type=AttrType.INT,
        required=False, enum_values=["a", "b"],
    )
    assert r.is_failure


def test_attribute_definition_create_blank_key_fails():
    r = AttributeDefinition.create(
        key="", label="X", data_type=AttrType.STRING,
        required=False, enum_values=None,
    )
    assert r.is_failure


def test_attribute_definition_create_invalid_key_format_fails():
    for bad in ["Has Space", "UPPER", "1leading-digit", "with-dash", "with.dot"]:
        r = AttributeDefinition.create(
            key=bad, label="X", data_type=AttrType.STRING,
            required=False, enum_values=None,
        )
        assert r.is_failure, f"expected failure for {bad!r}"


def test_attribute_definition_create_blank_label_fails():
    r = AttributeDefinition.create(
        key="ok", label="   ", data_type=AttrType.STRING,
        required=False, enum_values=None,
    )
    assert r.is_failure
    assert "label" in r.error.lower()


def test_attribute_definition_equality():
    a = AttributeDefinition.create(
        key="k", label="L", data_type=AttrType.BOOL,
        required=True, enum_values=None,
    ).value
    b = AttributeDefinition.create(
        key="k", label="L", data_type=AttrType.BOOL,
        required=True, enum_values=None,
    ).value
    assert a == b
    assert hash(a) == hash(b)
```

- [ ] **Step 2: Run — expect FAIL.**

```bash
.venv/bin/pytest tests/unit/domain/catalog/test_attribute.py -q
```

- [ ] **Step 3: Implement**

`app/domain/catalog/__init__.py`: empty.

`app/domain/catalog/attribute.py`:

```python
from __future__ import annotations
import re
from dataclasses import dataclass
from enum import Enum
from typing import Self
from app.domain.shared.result import Result

# Same shape as Python identifiers but stricter: lowercase only, must
# start with a letter. Used as JSON keys + as part of API request keys.
ATTR_KEY_RE = re.compile(r"^[a-z][a-z0-9_]*$")


class AttrType(str, Enum):
    STRING = "string"
    INT = "int"
    BOOL = "bool"
    ENUM = "enum"


@dataclass(frozen=True, slots=True)
class AttributeDefinition:
    key: str
    label: str
    data_type: AttrType
    required: bool
    enum_values: tuple[str, ...] | None  # tuple so the dataclass is hashable

    @classmethod
    def create(
        cls,
        *,
        key: str,
        label: str,
        data_type: AttrType,
        required: bool,
        enum_values: list[str] | tuple[str, ...] | None,
    ) -> Result[Self]:
        errors: list[str] = []

        key_clean = (key or "").strip()
        if not key_clean:
            errors.append("AttributeDefinition.key: obrigatório.")
        elif not ATTR_KEY_RE.match(key_clean):
            errors.append(
                f"AttributeDefinition.key inválido: '{key}'. "
                "Use apenas a-z, 0-9 e _; comece com letra."
            )

        label_clean = (label or "").strip()
        if not label_clean:
            errors.append("AttributeDefinition.label: obrigatório.")

        if not isinstance(data_type, AttrType):
            errors.append(
                f"AttributeDefinition.data_type: deve ser AttrType, recebido {type(data_type).__name__}."
            )

        normalized_enum: tuple[str, ...] | None = None
        if data_type is AttrType.ENUM:
            if enum_values is None or len(list(enum_values)) == 0:
                errors.append(
                    "AttributeDefinition: enum_values é obrigatório quando data_type=ENUM."
                )
            else:
                values_list = [str(v).strip() for v in enum_values]
                if any(not v for v in values_list):
                    errors.append("AttributeDefinition.enum_values: nenhum valor pode ser vazio.")
                elif len(set(values_list)) != len(values_list):
                    errors.append("AttributeDefinition.enum_values: valores duplicados.")
                else:
                    normalized_enum = tuple(values_list)
        else:
            if enum_values is not None and len(list(enum_values)) > 0:
                errors.append(
                    "AttributeDefinition: enum_values só é permitido quando data_type=ENUM."
                )

        if errors:
            return Result.failure("; ".join(errors))

        return Result.success(cls(
            key=key_clean,
            label=label_clean,
            data_type=data_type,
            required=required,
            enum_values=normalized_enum,
        ))
```

- [ ] **Step 4: Run — expect PASS.**

```bash
.venv/bin/pytest tests/unit/domain/catalog/test_attribute.py -q
```

- [ ] **Step 5: Commit**

```bash
git add app/domain/catalog/__init__.py app/domain/catalog/attribute.py tests/unit/domain/catalog/__init__.py tests/unit/domain/catalog/test_attribute.py
git commit -m "$(cat <<'EOF'
feat(catalog): add AttrType enum and AttributeDefinition VO

AttributeDefinition.create() validates the key format (a-z0-9_, starts
with a letter), label non-empty, and the (data_type, enum_values)
consistency: enum_values must be present and unique iff data_type=ENUM.

enum_values is stored as a tuple[str, ...] so the VO stays hashable.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

### Task A3 — `ResourceType` aggregate

**Files:** `app/domain/catalog/resource_type.py`, `tests/unit/domain/catalog/test_resource_type.py`.

The aggregate covers: factory `create()`, partial-update mutators, activate/deactivate, and `validate_attributes(values: dict[str, Any]) -> Result[None]` for the future `resources` feature.

- [ ] **Step 1: Failing test**

`tests/unit/domain/catalog/test_resource_type.py`:

```python
from __future__ import annotations
from datetime import datetime, timezone
from app.domain.catalog.attribute import AttributeDefinition, AttrType
from app.domain.catalog.resource_type import ResourceType


def _enum_attr() -> AttributeDefinition:
    return AttributeDefinition.create(
        key="lighting", label="Iluminação", data_type=AttrType.ENUM,
        required=False, enum_values=["natural", "artificial"],
    ).value


def _string_attr(key: str = "surface", required: bool = True) -> AttributeDefinition:
    return AttributeDefinition.create(
        key=key, label="X", data_type=AttrType.STRING,
        required=required, enum_values=None,
    ).value


def _int_attr(key: str = "size_m2", required: bool = False) -> AttributeDefinition:
    return AttributeDefinition.create(
        key=key, label="X", data_type=AttrType.INT,
        required=required, enum_values=None,
    ).value


def _bool_attr(key: str = "covered", required: bool = False) -> AttributeDefinition:
    return AttributeDefinition.create(
        key=key, label="X", data_type=AttrType.BOOL,
        required=required, enum_values=None,
    ).value


def test_create_resource_type_success():
    r = ResourceType.create(
        slug="football-field",
        name="Campo de Futebol",
        description="Campo gramado oficial.",
        attribute_schema=[_string_attr(), _enum_attr()],
    )
    assert r.is_success
    rt = r.value
    assert str(rt.slug) == "football-field"
    assert rt.name == "Campo de Futebol"
    assert rt.description == "Campo gramado oficial."
    assert len(rt.attribute_schema) == 2
    assert rt.is_active is True


def test_create_resource_type_default_active_and_empty_schema():
    r = ResourceType.create(
        slug="court", name="Quadra", description="", attribute_schema=[],
    )
    assert r.is_success
    rt = r.value
    assert rt.attribute_schema == ()  # tuple — frozen post-creation
    assert rt.is_active is True


def test_create_resource_type_invalid_slug_fails():
    r = ResourceType.create(
        slug="Invalid Slug!", name="X", description="", attribute_schema=[],
    )
    assert r.is_failure


def test_create_resource_type_blank_name_fails():
    r = ResourceType.create(
        slug="football-field", name="   ", description="", attribute_schema=[],
    )
    assert r.is_failure
    assert "name" in r.error.lower() or "nome" in r.error.lower()


def test_create_resource_type_duplicate_attribute_keys_fails():
    a = _string_attr(key="x")
    b = _string_attr(key="x")
    r = ResourceType.create(
        slug="football-field", name="X", description="",
        attribute_schema=[a, b],
    )
    assert r.is_failure
    assert "duplicad" in r.error.lower() or "duplicate" in r.error.lower()


def test_update_metadata_changes_fields_and_timestamp():
    r = ResourceType.create(
        slug="football-field", name="Old", description="old",
        attribute_schema=[],
    )
    rt = r.value
    before = rt.updated_at
    rt.update_metadata(name="New", description="new desc")
    assert rt.name == "New"
    assert rt.description == "new desc"
    assert rt.updated_at > before
    # slug is immutable through this path
    assert str(rt.slug) == "football-field"


def test_replace_attribute_schema_validates_uniqueness():
    rt = ResourceType.create(
        slug="football-field", name="X", description="", attribute_schema=[],
    ).value
    a = _string_attr(key="x")
    b = _string_attr(key="x")
    r = rt.replace_attribute_schema([a, b])
    assert r.is_failure


def test_replace_attribute_schema_success_updates_timestamp():
    rt = ResourceType.create(
        slug="football-field", name="X", description="", attribute_schema=[],
    ).value
    before = rt.updated_at
    r = rt.replace_attribute_schema([_string_attr(), _enum_attr()])
    assert r.is_success
    assert len(rt.attribute_schema) == 2
    assert rt.updated_at > before


def test_deactivate_and_activate_toggle_flag_and_timestamp():
    rt = ResourceType.create(
        slug="x", name="X", description="", attribute_schema=[],
    ).value
    before = rt.updated_at
    rt.deactivate()
    assert rt.is_active is False
    assert rt.updated_at > before
    mid = rt.updated_at
    rt.activate()
    assert rt.is_active is True
    assert rt.updated_at >= mid


def test_validate_attributes_empty_schema_accepts_empty_dict():
    rt = ResourceType.create(
        slug="x", name="X", description="", attribute_schema=[],
    ).value
    r = rt.validate_attributes({})
    assert r.is_success


def test_validate_attributes_empty_schema_rejects_extra_keys():
    rt = ResourceType.create(
        slug="x", name="X", description="", attribute_schema=[],
    ).value
    r = rt.validate_attributes({"extra": "value"})
    assert r.is_failure
    assert "extra" in r.error or "desconhecid" in r.error.lower()


def test_validate_attributes_required_string_present():
    rt = ResourceType.create(
        slug="x", name="X", description="",
        attribute_schema=[_string_attr(key="surface", required=True)],
    ).value
    r = rt.validate_attributes({"surface": "grama"})
    assert r.is_success


def test_validate_attributes_required_string_missing_fails():
    rt = ResourceType.create(
        slug="x", name="X", description="",
        attribute_schema=[_string_attr(key="surface", required=True)],
    ).value
    r = rt.validate_attributes({})
    assert r.is_failure
    assert "surface" in r.error


def test_validate_attributes_optional_missing_is_ok():
    rt = ResourceType.create(
        slug="x", name="X", description="",
        attribute_schema=[_string_attr(key="surface", required=False)],
    ).value
    r = rt.validate_attributes({})
    assert r.is_success


def test_validate_attributes_int_type_check():
    rt = ResourceType.create(
        slug="x", name="X", description="",
        attribute_schema=[_int_attr(key="size_m2", required=True)],
    ).value
    assert rt.validate_attributes({"size_m2": 100}).is_success
    assert rt.validate_attributes({"size_m2": "not-int"}).is_failure
    # bool is a subtype of int in Python — explicitly reject
    assert rt.validate_attributes({"size_m2": True}).is_failure


def test_validate_attributes_bool_type_check():
    rt = ResourceType.create(
        slug="x", name="X", description="",
        attribute_schema=[_bool_attr(key="covered", required=True)],
    ).value
    assert rt.validate_attributes({"covered": True}).is_success
    assert rt.validate_attributes({"covered": False}).is_success
    assert rt.validate_attributes({"covered": "yes"}).is_failure
    assert rt.validate_attributes({"covered": 1}).is_failure


def test_validate_attributes_enum_value_must_be_in_set():
    rt = ResourceType.create(
        slug="x", name="X", description="",
        attribute_schema=[_enum_attr()],
    ).value
    assert rt.validate_attributes({"lighting": "natural"}).is_success
    assert rt.validate_attributes({"lighting": "infrared"}).is_failure


def test_validate_attributes_reports_all_errors_at_once():
    rt = ResourceType.create(
        slug="x", name="X", description="",
        attribute_schema=[
            _string_attr(key="surface", required=True),
            _int_attr(key="size_m2", required=True),
        ],
    ).value
    r = rt.validate_attributes({"surface": 123, "extra": "x"})
    assert r.is_failure
    # All three problems should be flagged
    assert "surface" in r.error
    assert "size_m2" in r.error
    assert "extra" in r.error
```

- [ ] **Step 2: Run — expect FAIL.**

```bash
.venv/bin/pytest tests/unit/domain/catalog/test_resource_type.py -q
```

- [ ] **Step 3: Implement**

`app/domain/catalog/resource_type.py`:

```python
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Self
from app.domain.catalog.attribute import AttributeDefinition, AttrType
from app.domain.shared.entity import BaseEntity
from app.domain.shared.result import Result
from app.domain.shared.value_objects.slug import Slug


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(slots=True, kw_only=True)
class ResourceType(BaseEntity):
    slug: Slug
    name: str
    description: str
    attribute_schema: tuple[AttributeDefinition, ...] = ()
    is_active: bool = True

    @classmethod
    def create(
        cls,
        *,
        slug: str,
        name: str,
        description: str,
        attribute_schema: list[AttributeDefinition] | tuple[AttributeDefinition, ...],
        is_active: bool = True,
    ) -> Result[Self]:
        errors: list[str] = []

        slug_r = Slug.create(slug)
        if slug_r.is_failure:
            errors.append(slug_r.error)

        name_clean = (name or "").strip()
        if not name_clean:
            errors.append("ResourceType.name: obrigatório.")

        description_clean = description if description is not None else ""

        schema_tuple = tuple(attribute_schema)
        keys = [a.key for a in schema_tuple]
        if len(set(keys)) != len(keys):
            errors.append("ResourceType.attribute_schema: chaves duplicadas.")

        if errors:
            return Result.failure("; ".join(errors))

        return Result.success(cls(
            slug=slug_r.value,
            name=name_clean,
            description=description_clean,
            attribute_schema=schema_tuple,
            is_active=is_active,
        ))

    def update_metadata(self, *, name: str, description: str) -> None:
        self.name = name.strip()
        self.description = description if description is not None else ""
        self.updated_at = _utcnow()

    def replace_attribute_schema(
        self, schema: list[AttributeDefinition] | tuple[AttributeDefinition, ...],
    ) -> Result[None]:
        schema_tuple = tuple(schema)
        keys = [a.key for a in schema_tuple]
        if len(set(keys)) != len(keys):
            return Result.failure("ResourceType.attribute_schema: chaves duplicadas.")
        self.attribute_schema = schema_tuple
        self.updated_at = _utcnow()
        return Result.success(None)

    def activate(self) -> None:
        self.is_active = True
        self.updated_at = _utcnow()

    def deactivate(self) -> None:
        self.is_active = False
        self.updated_at = _utcnow()

    def validate_attributes(self, values: dict[str, Any]) -> Result[None]:
        """Validate a dict of attribute values against this type's schema.

        Used by future Resource.create() to validate base_attributes.
        Reports all violations at once (joined with '; ').
        """
        errors: list[str] = []
        schema_by_key = {a.key: a for a in self.attribute_schema}

        # Unknown keys
        for key in values.keys():
            if key not in schema_by_key:
                errors.append(f"Chave desconhecida: '{key}'.")

        # Required missing + per-key type checks
        for key, defn in schema_by_key.items():
            if key not in values:
                if defn.required:
                    errors.append(f"'{key}': valor obrigatório.")
                continue
            v = values[key]
            type_err = _check_type(defn, v)
            if type_err:
                errors.append(type_err)

        if errors:
            return Result.failure("; ".join(errors))
        return Result.success(None)


def _check_type(defn: AttributeDefinition, value: Any) -> str | None:
    """Returns an error message if the value doesn't match the definition's type, else None."""
    if defn.data_type is AttrType.STRING:
        if not isinstance(value, str):
            return f"'{defn.key}': esperado string, recebido {type(value).__name__}."
        return None
    if defn.data_type is AttrType.INT:
        # bool is an int subclass in Python — explicitly reject
        if isinstance(value, bool) or not isinstance(value, int):
            return f"'{defn.key}': esperado int, recebido {type(value).__name__}."
        return None
    if defn.data_type is AttrType.BOOL:
        if not isinstance(value, bool):
            return f"'{defn.key}': esperado bool, recebido {type(value).__name__}."
        return None
    if defn.data_type is AttrType.ENUM:
        if not isinstance(value, str):
            return f"'{defn.key}': esperado string (enum), recebido {type(value).__name__}."
        if defn.enum_values is None or value not in defn.enum_values:
            allowed = ", ".join(defn.enum_values or ())
            return f"'{defn.key}': valor '{value}' não está em [{allowed}]."
        return None
    return f"'{defn.key}': data_type desconhecido."
```

- [ ] **Step 4: Run — expect PASS.**

```bash
.venv/bin/pytest tests/unit/domain/catalog/test_resource_type.py -q
```

- [ ] **Step 5: Commit**

```bash
git add app/domain/catalog/resource_type.py tests/unit/domain/catalog/test_resource_type.py
git commit -m "$(cat <<'EOF'
feat(catalog): add ResourceType aggregate with attribute validation

ResourceType.create() validates slug (via Slug VO), name non-empty,
and attribute_schema key uniqueness. update_metadata, activate,
deactivate, and replace_attribute_schema are simple mutators that
bump updated_at.

validate_attributes(values) is the validator the resources feature
will call to check Resource.base_attributes against the schema —
reports all violations at once for a useful error response.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

### Task A4 — `IResourceTypeRepository` Protocol

**Files:** `app/domain/catalog/repository.py`.

No test — Protocols are interfaces; the in-memory fake (Unit C, Task C1) is what verifies the contract holds.

- [ ] **Step 1: Implement**

`app/domain/catalog/repository.py`:

```python
from __future__ import annotations
from typing import Protocol, Sequence
from uuid import UUID
from app.domain.catalog.resource_type import ResourceType


class IResourceTypeRepository(Protocol):
    async def get_by_id(self, resource_type_id: UUID) -> ResourceType | None: ...
    async def get_by_slug(self, slug: str) -> ResourceType | None: ...
    async def list(
        self, *, limit: int = 50, offset: int = 0, only_active: bool = False,
    ) -> Sequence[ResourceType]: ...
    async def add(self, resource_type: ResourceType) -> None: ...
    async def update(self, resource_type: ResourceType) -> None: ...
    async def delete(self, resource_type_id: UUID) -> None: ...
```

- [ ] **Step 2: Verify it imports cleanly**

```bash
.venv/bin/python -c "from app.domain.catalog.repository import IResourceTypeRepository; print('ok')"
```

Expect: `ok`.

- [ ] **Step 3: Commit**

```bash
git add app/domain/catalog/repository.py
git commit -m "$(cat <<'EOF'
feat(catalog): add IResourceTypeRepository Protocol

list() takes only_active so the public route can show active-only
while admin sees everything. delete() takes an id (idempotent;
handler decides whether missing-id is an error).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

### Unit A — verification before handoff

- [ ] Run the affected suites.

```bash
.venv/bin/pytest tests/unit/domain/shared/value_objects/ tests/unit/domain/catalog/ -q
```

Expect: all passing, no skips, no warnings about new code.

- [ ] Run the full unit suite to confirm nothing else broke.

```bash
.venv/bin/pytest tests/unit/ -q
```

Expect: all green.

- [ ] Run ruff on the new code.

```bash
.venv/bin/python -m ruff check app/domain/catalog app/domain/shared/value_objects/slug.py tests/unit/domain/catalog tests/unit/domain/shared/value_objects/test_slug.py
```

Expect: clean.

---

## UNIT B — Infrastructure layer

### Task B1 — `ResourceTypeModel` mapping + register in `env.py`

**Files:** `app/infrastructure/db/mappings/resource_type.py`, `app/migrations/env.py` (modify).

- [ ] **Step 1: Implement the mapping**

`app/infrastructure/db/mappings/resource_type.py`:

```python
from __future__ import annotations
from typing import Any
from uuid import UUID
from sqlalchemy import JSON, Boolean, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import CHAR
from app.infrastructure.db.base import Base, TimestampMixin


class ResourceTypeModel(Base, TimestampMixin):
    __tablename__ = "resource_types"

    id: Mapped[UUID] = mapped_column(CHAR(36), primary_key=True)
    slug: Mapped[str] = mapped_column(String(80), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(String(1000), nullable=False, default="")
    # Generic JSON — Postgres stores as JSON, SQLite as TEXT, both work.
    # The repository serializes/deserializes list[AttributeDefinition] ↔ list[dict].
    attribute_schema: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, nullable=False, default=list,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
```

- [ ] **Step 2: Register the mapping with all `Base.metadata`-loading sites**

There are THREE places that import mapping modules to register them with `Base.metadata`. All of them must learn about `resource_type` so it appears in:
1. Alembic's autogenerate (so Task B3 picks up the new table)
2. The integration test DB (so `db_session` in `tests/integration/conftest.py` creates `resource_types`)
3. The e2e test DB (so `client` in `tests/e2e/conftest.py` creates `resource_types`)

The pattern in all three is `from app.infrastructure.db.mappings import user  # noqa: F401` (or a similar `import ...` form for `env.py`). Add a sibling line for `resource_type` in each.

**a) `app/migrations/env.py`**: locate the existing user mapping import and add right after it:

```python
from app.infrastructure.db.mappings import resource_type  # noqa: F401
```

(Match the existing convention — if env.py uses `import app.infrastructure.db.mappings.user`, mirror that form.)

**b) `tests/integration/conftest.py`**: locate `from app.infrastructure.db.mappings import user  # noqa: F401` and add:

```python
from app.infrastructure.db.mappings import resource_type  # noqa: F401
```

**c) `tests/e2e/conftest.py`**: locate `from app.infrastructure.db.mappings import user  # noqa: F401` and add:

```python
from app.infrastructure.db.mappings import resource_type  # noqa: F401
```

- [ ] **Step 3: Verify imports cleanly**

```bash
.venv/bin/python -c "from app.infrastructure.db.mappings.resource_type import ResourceTypeModel; print(ResourceTypeModel.__tablename__)"
```

Expect: `resource_types`.

```bash
.venv/bin/python -c "import app.migrations.env; print('ok')"
```

Expect: `ok` (import side-effect should register the new model with `Base.metadata`).

- [ ] **Step 4: Sanity check — `Base.metadata` knows about `resource_types`**

```bash
.venv/bin/python -c "
import app.migrations.env  # triggers all mapping imports
from app.infrastructure.db.base import Base
print(sorted(Base.metadata.tables.keys()))
"
```

Expect output to include `'resource_types'`.

- [ ] **Step 5: Commit**

```bash
git add app/infrastructure/db/mappings/resource_type.py app/migrations/env.py tests/integration/conftest.py tests/e2e/conftest.py
git commit -m "$(cat <<'EOF'
feat(db): add resource_types mapping for catalog feature

ResourceTypeModel uses generic sa.JSON for attribute_schema so the
column shape is identical on Postgres (JSON) and SQLite (TEXT).
Repository handles list[AttributeDefinition] ↔ list[dict]
serialization at the boundary.

Registers the mapping with alembic env.py + the integration and
e2e conftests so autogenerate and the per-test create_all both
see the new table.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

### Task B2 — `ResourceTypeRepository` (SQLAlchemy adapter)

**Files:** `app/infrastructure/repositories/resource_type_repository.py`, `tests/integration/catalog/__init__.py` (empty), `tests/integration/catalog/test_resource_type_repository.py`.

- [ ] **Step 1: Failing test**

`tests/integration/catalog/test_resource_type_repository.py`:

```python
from __future__ import annotations
from uuid import uuid4
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from app.domain.catalog.attribute import AttributeDefinition, AttrType
from app.domain.catalog.resource_type import ResourceType
from app.infrastructure.repositories.resource_type_repository import (
    ResourceTypeRepository,
)


def _rt(slug: str = "football-field", *, name: str = "Campo de Futebol",
        is_active: bool = True) -> ResourceType:
    return ResourceType.create(
        slug=slug, name=name, description="desc",
        attribute_schema=[
            AttributeDefinition.create(
                key="surface", label="Piso", data_type=AttrType.STRING,
                required=True, enum_values=None,
            ).value,
            AttributeDefinition.create(
                key="lighting", label="Iluminação", data_type=AttrType.ENUM,
                required=False, enum_values=["natural", "artificial"],
            ).value,
        ],
        is_active=is_active,
    ).value


@pytest.mark.asyncio
async def test_add_then_get_by_id_roundtrip(db_session: AsyncSession):
    repo = ResourceTypeRepository(db_session)
    rt = _rt()
    await repo.add(rt)
    await db_session.commit()

    found = await repo.get_by_id(rt.id)
    assert found is not None
    assert found.id == rt.id
    assert str(found.slug) == "football-field"
    assert found.name == "Campo de Futebol"
    assert found.is_active is True
    assert len(found.attribute_schema) == 2
    # The second attribute is ENUM and round-trips its values
    enum_attr = found.attribute_schema[1]
    assert enum_attr.key == "lighting"
    assert enum_attr.data_type is AttrType.ENUM
    assert enum_attr.enum_values == ("natural", "artificial")


@pytest.mark.asyncio
async def test_get_by_slug(db_session: AsyncSession):
    repo = ResourceTypeRepository(db_session)
    rt = _rt(slug="court")
    await repo.add(rt)
    await db_session.commit()

    found = await repo.get_by_slug("court")
    assert found is not None and found.id == rt.id
    assert await repo.get_by_slug("missing") is None


@pytest.mark.asyncio
async def test_get_by_id_missing_returns_none(db_session: AsyncSession):
    repo = ResourceTypeRepository(db_session)
    assert await repo.get_by_id(uuid4()) is None


@pytest.mark.asyncio
async def test_list_only_active_filter(db_session: AsyncSession):
    repo = ResourceTypeRepository(db_session)
    a = _rt(slug="active-1", is_active=True)
    b = _rt(slug="inactive-1", is_active=False)
    c = _rt(slug="active-2", is_active=True)
    await repo.add(a); await repo.add(b); await repo.add(c)
    await db_session.commit()

    all_rows = await repo.list(only_active=False)
    assert {str(r.slug) for r in all_rows} == {"active-1", "inactive-1", "active-2"}

    active_only = await repo.list(only_active=True)
    assert {str(r.slug) for r in active_only} == {"active-1", "active-2"}


@pytest.mark.asyncio
async def test_list_pagination(db_session: AsyncSession):
    repo = ResourceTypeRepository(db_session)
    for i in range(5):
        await repo.add(_rt(slug=f"rt-{i}"))
    await db_session.commit()

    page1 = await repo.list(limit=2, offset=0)
    page2 = await repo.list(limit=2, offset=2)
    page3 = await repo.list(limit=2, offset=4)
    assert len(page1) == 2
    assert len(page2) == 2
    assert len(page3) == 1
    seen = {str(r.slug) for r in page1} | {str(r.slug) for r in page2} | {str(r.slug) for r in page3}
    assert seen == {f"rt-{i}" for i in range(5)}


@pytest.mark.asyncio
async def test_update_persists_changes(db_session: AsyncSession):
    repo = ResourceTypeRepository(db_session)
    rt = _rt()
    await repo.add(rt)
    await db_session.commit()

    rt.update_metadata(name="Novo Nome", description="nova")
    rt.deactivate()
    await repo.update(rt)
    await db_session.commit()

    found = await repo.get_by_id(rt.id)
    assert found is not None
    assert found.name == "Novo Nome"
    assert found.description == "nova"
    assert found.is_active is False


@pytest.mark.asyncio
async def test_delete_removes_row(db_session: AsyncSession):
    repo = ResourceTypeRepository(db_session)
    rt = _rt()
    await repo.add(rt)
    await db_session.commit()

    await repo.delete(rt.id)
    await db_session.commit()

    assert await repo.get_by_id(rt.id) is None


@pytest.mark.asyncio
async def test_unique_slug_constraint(db_session: AsyncSession):
    from sqlalchemy.exc import IntegrityError
    repo = ResourceTypeRepository(db_session)
    a = _rt(slug="dup")
    b = _rt(slug="dup")
    await repo.add(a)
    await db_session.commit()

    await repo.add(b)
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()
```

The `db_session` fixture comes from `tests/integration/conftest.py` (already exists from the template). If the conftest is at `tests/conftest.py` and the integration suite uses a different fixture name, match what the existing `tests/integration/accounts/test_user_repository.py` uses — copy that fixture wiring exactly.

- [ ] **Step 2: Run — expect FAIL.**

```bash
.venv/bin/pytest tests/integration/catalog/ -q
```

Expect: `ModuleNotFoundError: No module named 'app.infrastructure.repositories.resource_type_repository'`.

- [ ] **Step 3: Implement**

`app/infrastructure/repositories/resource_type_repository.py`:

```python
from __future__ import annotations
from typing import Any, Sequence
from uuid import UUID
from sqlalchemy import select, delete as sa_delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.domain.catalog.attribute import AttributeDefinition, AttrType
from app.domain.catalog.repository import IResourceTypeRepository
from app.domain.catalog.resource_type import ResourceType
from app.domain.shared.value_objects.slug import Slug
from app.infrastructure.db.mappings.resource_type import ResourceTypeModel


class ResourceTypeRepository(IResourceTypeRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, resource_type_id: UUID) -> ResourceType | None:
        row = await self._session.get(ResourceTypeModel, str(resource_type_id))
        return self._to_entity(row) if row else None

    async def get_by_slug(self, slug: str) -> ResourceType | None:
        stmt = select(ResourceTypeModel).where(ResourceTypeModel.slug == slug)
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return self._to_entity(row) if row else None

    async def list(
        self, *, limit: int = 50, offset: int = 0, only_active: bool = False,
    ) -> Sequence[ResourceType]:
        stmt = select(ResourceTypeModel)
        if only_active:
            stmt = stmt.where(ResourceTypeModel.is_active.is_(True))
        stmt = stmt.order_by(ResourceTypeModel.slug).limit(limit).offset(offset)
        rows = (await self._session.execute(stmt)).scalars().all()
        return [self._to_entity(r) for r in rows]

    async def add(self, resource_type: ResourceType) -> None:
        self._session.add(self._to_model(resource_type))

    async def update(self, resource_type: ResourceType) -> None:
        existing = await self._session.get(ResourceTypeModel, str(resource_type.id))
        if existing is None:
            return
        existing.slug = str(resource_type.slug)
        existing.name = resource_type.name
        existing.description = resource_type.description
        existing.attribute_schema = [
            self._attr_to_dict(a) for a in resource_type.attribute_schema
        ]
        existing.is_active = resource_type.is_active
        existing.updated_at = resource_type.updated_at

    async def delete(self, resource_type_id: UUID) -> None:
        await self._session.execute(
            sa_delete(ResourceTypeModel).where(
                ResourceTypeModel.id == str(resource_type_id)
            )
        )

    @staticmethod
    def _to_model(rt: ResourceType) -> ResourceTypeModel:
        return ResourceTypeModel(
            id=str(rt.id),
            slug=str(rt.slug),
            name=rt.name,
            description=rt.description,
            attribute_schema=[
                ResourceTypeRepository._attr_to_dict(a) for a in rt.attribute_schema
            ],
            is_active=rt.is_active,
            created_at=rt.created_at,
            updated_at=rt.updated_at,
        )

    @staticmethod
    def _to_entity(row: ResourceTypeModel) -> ResourceType:
        # Direct dataclass construction for trusted DB rows; bypasses
        # ResourceType.create() so we don't re-run validation that
        # write paths already enforced.
        return ResourceType(
            id=UUID(str(row.id)),
            slug=Slug(value=row.slug),
            name=row.name,
            description=row.description,
            attribute_schema=tuple(
                ResourceTypeRepository._attr_from_dict(d)
                for d in (row.attribute_schema or [])
            ),
            is_active=row.is_active,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    @staticmethod
    def _attr_to_dict(a: AttributeDefinition) -> dict[str, Any]:
        return {
            "key": a.key,
            "label": a.label,
            "data_type": a.data_type.value,
            "required": a.required,
            "enum_values": list(a.enum_values) if a.enum_values is not None else None,
        }

    @staticmethod
    def _attr_from_dict(d: dict[str, Any]) -> AttributeDefinition:
        # Direct construction for trusted DB rows; bypasses .create() validation.
        return AttributeDefinition(
            key=d["key"],
            label=d["label"],
            data_type=AttrType(d["data_type"]),
            required=d["required"],
            enum_values=tuple(d["enum_values"]) if d.get("enum_values") is not None else None,
        )
```

- [ ] **Step 4: Run — expect PASS.**

```bash
.venv/bin/pytest tests/integration/catalog/ -q
```

If a fixture is missing or the test DB doesn't auto-create the table for tests, look at how `tests/integration/accounts/test_user_repository.py` handles it — it almost certainly relies on a fixture in `tests/conftest.py` that creates `Base.metadata.create_all` against the in-memory test DB. The catalog test should pick up the new table automatically because Task B1 registered it with `Base.metadata`.

- [ ] **Step 5: Commit**

```bash
git add app/infrastructure/repositories/resource_type_repository.py tests/integration/catalog/
git commit -m "$(cat <<'EOF'
feat(catalog): add ResourceTypeRepository SQLAlchemy adapter

list() supports limit/offset and an only_active filter. The repo
serializes AttributeDefinition VOs to/from list[dict] at the boundary,
keeping the JSON column shape stable.

Reconstitution via direct dataclass construction (no .create() call)
trusts the DB; write-path validation already happened.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

### Task B3 — Alembic migration

**Files:** new revision under `app/migrations/versions/`.

- [ ] **Step 1: Generate the migration**

```bash
.venv/bin/python -m alembic revision --autogenerate -m "catalog resource types table"
```

This creates a file like `app/migrations/versions/<timestamp>_catalog_resource_types_table.py`.

- [ ] **Step 2: Inspect the generated file**

Read the file. Expect to see:

```python
def upgrade() -> None:
    op.create_table(
        'resource_types',
        sa.Column('id', sa.CHAR(length=36), nullable=False),
        sa.Column('slug', sa.String(length=80), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('description', sa.String(length=1000), nullable=False),
        sa.Column('attribute_schema', sa.JSON(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('slug'),
    )
    op.create_index(op.f('ix_resource_types_is_active'), 'resource_types', ['is_active'], unique=False)
    op.create_index(op.f('ix_resource_types_slug'), 'resource_types', ['slug'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_resource_types_slug'), table_name='resource_types')
    op.drop_index(op.f('ix_resource_types_is_active'), table_name='resource_types')
    op.drop_table('resource_types')
```

If the autogenerate misses something, edit the file to match. Common gotchas:
- If the autogenerate output mentions ALTER TABLE on `users` (the accounts schema), reject the change — that means the `accounts` migration didn't capture the schema correctly. Diff against `app/migrations/versions/20260425_1414_accounts_users_schema.py` and figure out which mapping is out of sync.
- The column order should follow the mapping declaration order. Reorder if needed.

- [ ] **Step 3: Verify the migration runs against a fresh SQLite**

```bash
BACKEND_DATABASE_URL="sqlite+aiosqlite:///:memory:" \
  .venv/bin/python -c "
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
import app.migrations.env  # registers all mappings
from app.infrastructure.db.base import Base

async def main():
    engine = create_async_engine('sqlite+aiosqlite:///:memory:')
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        rows = await conn.exec_driver_sql(\"SELECT name FROM sqlite_master WHERE type='table' ORDER BY name\")
        print([r[0] for r in rows])

asyncio.run(main())
"
```

Expect output to include `'resource_types'` and `'users'` and the alembic version table.

- [ ] **Step 4: Run the FULL test suite to make sure nothing regressed**

```bash
.venv/bin/pytest -q
```

Expect: green.

- [ ] **Step 5: Commit**

```bash
git add app/migrations/versions/
git commit -m "$(cat <<'EOF'
feat(db): alembic migration creates resource_types table

Adds the catalog feature's only table. JSON column for the
attribute_schema list — adapts to Postgres JSON and SQLite TEXT
without a dialect-specific column type.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

### Unit B — verification before handoff

- [ ] Run all integration tests to confirm both `accounts` and `catalog` work.

```bash
.venv/bin/pytest tests/integration/ -q
```

- [ ] Run ruff over the new infra code.

```bash
.venv/bin/python -m ruff check app/infrastructure/db/mappings/resource_type.py app/infrastructure/repositories/resource_type_repository.py app/migrations/env.py app/migrations/versions/ tests/integration/catalog/
```

Expect: clean.

---

## UNIT C — Use cases (handlers)

### Task C1 — DTOs + in-memory fake repository

**Files:** `app/use_cases/catalog/__init__.py` (empty), `app/use_cases/catalog/dtos.py`, `app/use_cases/catalog/commands/__init__.py` (empty), `tests/unit/use_cases/catalog/__init__.py` (empty), `tests/unit/use_cases/catalog/commands/__init__.py` (empty), `tests/unit/use_cases/catalog/fakes/__init__.py` (empty), `tests/unit/use_cases/catalog/fakes/in_memory_resource_type_repository.py`.

- [ ] **Step 1: Implement the DTOs**

`app/use_cases/catalog/dtos.py`:

```python
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Self
from uuid import UUID
from app.domain.catalog.attribute import AttributeDefinition
from app.domain.catalog.resource_type import ResourceType


@dataclass(frozen=True, slots=True, kw_only=True)
class AttributeDefinitionDto:
    key: str
    label: str
    data_type: str  # AttrType.value (string|int|bool|enum)
    required: bool
    enum_values: tuple[str, ...] | None

    @classmethod
    def from_vo(cls, a: AttributeDefinition) -> Self:
        return cls(
            key=a.key,
            label=a.label,
            data_type=a.data_type.value,
            required=a.required,
            enum_values=a.enum_values,
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class ResourceTypeDto:
    id: UUID
    slug: str
    name: str
    description: str
    attribute_schema: tuple[AttributeDefinitionDto, ...]
    is_active: bool
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_entity(cls, rt: ResourceType) -> Self:
        return cls(
            id=rt.id,
            slug=str(rt.slug),
            name=rt.name,
            description=rt.description,
            attribute_schema=tuple(
                AttributeDefinitionDto.from_vo(a) for a in rt.attribute_schema
            ),
            is_active=rt.is_active,
            created_at=rt.created_at,
            updated_at=rt.updated_at,
        )
```

- [ ] **Step 2: Implement the in-memory fake repo**

`tests/unit/use_cases/catalog/fakes/in_memory_resource_type_repository.py`:

```python
from __future__ import annotations
from typing import Sequence
from uuid import UUID
from app.domain.catalog.repository import IResourceTypeRepository
from app.domain.catalog.resource_type import ResourceType


class InMemoryResourceTypeRepository(IResourceTypeRepository):
    def __init__(self) -> None:
        self._by_id: dict[UUID, ResourceType] = {}

    async def get_by_id(self, resource_type_id: UUID) -> ResourceType | None:
        return self._by_id.get(resource_type_id)

    async def get_by_slug(self, slug: str) -> ResourceType | None:
        for rt in self._by_id.values():
            if str(rt.slug) == slug:
                return rt
        return None

    async def list(
        self, *, limit: int = 50, offset: int = 0, only_active: bool = False,
    ) -> Sequence[ResourceType]:
        rows = sorted(self._by_id.values(), key=lambda r: str(r.slug))
        if only_active:
            rows = [r for r in rows if r.is_active]
        return rows[offset:offset + limit]

    async def add(self, resource_type: ResourceType) -> None:
        if resource_type.id in self._by_id:
            raise ValueError(f"ResourceType {resource_type.id} already exists.")
        # Mimic the unique slug constraint
        if any(str(r.slug) == str(resource_type.slug) for r in self._by_id.values()):
            from sqlalchemy.exc import IntegrityError
            raise IntegrityError("UNIQUE constraint failed: resource_types.slug", None, Exception())
        self._by_id[resource_type.id] = resource_type

    async def update(self, resource_type: ResourceType) -> None:
        if resource_type.id in self._by_id:
            self._by_id[resource_type.id] = resource_type

    async def delete(self, resource_type_id: UUID) -> None:
        self._by_id.pop(resource_type_id, None)
```

- [ ] **Step 3: Verify the fake imports cleanly + sanity test**

`tests/unit/use_cases/catalog/test_dtos.py`:

```python
from __future__ import annotations
from app.domain.catalog.attribute import AttributeDefinition, AttrType
from app.domain.catalog.resource_type import ResourceType
from app.use_cases.catalog.dtos import AttributeDefinitionDto, ResourceTypeDto


def test_resource_type_dto_round_trip():
    a = AttributeDefinition.create(
        key="lighting", label="Iluminação", data_type=AttrType.ENUM,
        required=False, enum_values=["natural", "artificial"],
    ).value
    rt = ResourceType.create(
        slug="court", name="Quadra", description="d", attribute_schema=[a],
    ).value
    dto = ResourceTypeDto.from_entity(rt)
    assert dto.id == rt.id
    assert dto.slug == "court"
    assert dto.name == "Quadra"
    assert dto.is_active is True
    assert len(dto.attribute_schema) == 1
    a_dto = dto.attribute_schema[0]
    assert a_dto.key == "lighting"
    assert a_dto.data_type == "enum"
    assert a_dto.enum_values == ("natural", "artificial")
```

```bash
.venv/bin/pytest tests/unit/use_cases/catalog/test_dtos.py -q
```

Expect: PASS.

- [ ] **Step 4: Commit**

```bash
git add app/use_cases/catalog/ tests/unit/use_cases/catalog/__init__.py tests/unit/use_cases/catalog/commands/__init__.py tests/unit/use_cases/catalog/fakes/ tests/unit/use_cases/catalog/test_dtos.py
git commit -m "$(cat <<'EOF'
feat(catalog): add DTOs + in-memory fake repository

ResourceTypeDto and AttributeDefinitionDto carry the entity shape
across the use-cases ↔ API boundary. The in-memory fake mimics the
unique-slug constraint by raising IntegrityError, so handler tests
exercise the same conflict path as integration tests.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

### Task C2 — `CreateResourceTypeHandler`

**Files:** `app/use_cases/catalog/commands/create_resource_type.py`, `tests/unit/use_cases/catalog/commands/test_create_resource_type.py`.

- [ ] **Step 1: Failing test**

`tests/unit/use_cases/catalog/commands/test_create_resource_type.py`:

```python
from __future__ import annotations
import pytest
from app.use_cases.catalog.commands.create_resource_type import (
    AttributeInput, CreateResourceTypeCommand, CreateResourceTypeHandler,
)
from tests.unit.use_cases.catalog.fakes.in_memory_resource_type_repository import (
    InMemoryResourceTypeRepository,
)


@pytest.mark.asyncio
async def test_create_resource_type_success():
    repo = InMemoryResourceTypeRepository()
    handler = CreateResourceTypeHandler(repo)
    cmd = CreateResourceTypeCommand(
        slug="football-field",
        name="Campo de Futebol",
        description="Campo gramado.",
        attribute_schema=[
            AttributeInput(
                key="surface", label="Piso", data_type="string",
                required=True, enum_values=None,
            ),
            AttributeInput(
                key="lighting", label="Iluminação", data_type="enum",
                required=False, enum_values=["natural", "artificial"],
            ),
        ],
    )
    r = await handler.handle(cmd)
    assert r.is_success
    dto = r.value
    assert dto.slug == "football-field"
    assert dto.name == "Campo de Futebol"
    assert dto.is_active is True
    assert len(dto.attribute_schema) == 2


@pytest.mark.asyncio
async def test_create_resource_type_invalid_slug_returns_422():
    repo = InMemoryResourceTypeRepository()
    handler = CreateResourceTypeHandler(repo)
    cmd = CreateResourceTypeCommand(
        slug="Invalid Slug!", name="X", description="",
        attribute_schema=[],
    )
    r = await handler.handle(cmd)
    assert r.is_failure
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_create_resource_type_invalid_attribute_returns_422():
    repo = InMemoryResourceTypeRepository()
    handler = CreateResourceTypeHandler(repo)
    cmd = CreateResourceTypeCommand(
        slug="x", name="X", description="",
        attribute_schema=[
            AttributeInput(
                key="bad",
                label="X",
                data_type="enum",
                required=False,
                enum_values=None,  # ENUM with no values — invalid
            ),
        ],
    )
    r = await handler.handle(cmd)
    assert r.is_failure
    assert r.status_code == 422
    assert "enum" in r.error.lower()


@pytest.mark.asyncio
async def test_create_resource_type_unknown_data_type_returns_422():
    repo = InMemoryResourceTypeRepository()
    handler = CreateResourceTypeHandler(repo)
    cmd = CreateResourceTypeCommand(
        slug="x", name="X", description="",
        attribute_schema=[
            AttributeInput(
                key="bad", label="X", data_type="float",  # not in AttrType
                required=False, enum_values=None,
            ),
        ],
    )
    r = await handler.handle(cmd)
    assert r.is_failure
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_create_resource_type_duplicate_slug_returns_409():
    repo = InMemoryResourceTypeRepository()
    handler = CreateResourceTypeHandler(repo)
    first = await handler.handle(CreateResourceTypeCommand(
        slug="dup", name="A", description="", attribute_schema=[],
    ))
    assert first.is_success
    second = await handler.handle(CreateResourceTypeCommand(
        slug="dup", name="B", description="", attribute_schema=[],
    ))
    assert second.is_failure
    assert second.status_code == 409
    assert "slug" in second.error.lower() or "dup" in second.error.lower()


@pytest.mark.asyncio
async def test_create_resource_type_success_carries_201():
    repo = InMemoryResourceTypeRepository()
    handler = CreateResourceTypeHandler(repo)
    r = await handler.handle(CreateResourceTypeCommand(
        slug="x", name="X", description="", attribute_schema=[],
    ))
    assert r.is_success
    assert r.status_code == 201
```

- [ ] **Step 2: Run — expect FAIL.**

```bash
.venv/bin/pytest tests/unit/use_cases/catalog/commands/test_create_resource_type.py -q
```

- [ ] **Step 3: Implement**

`app/use_cases/catalog/commands/create_resource_type.py`:

```python
from __future__ import annotations
from dataclasses import dataclass
from sqlalchemy.exc import IntegrityError
from app.domain.catalog.attribute import AttributeDefinition, AttrType
from app.domain.catalog.repository import IResourceTypeRepository
from app.domain.catalog.resource_type import ResourceType
from app.domain.shared.result import Result
from app.use_cases.catalog.dtos import ResourceTypeDto


@dataclass(frozen=True, slots=True, kw_only=True)
class AttributeInput:
    key: str
    label: str
    data_type: str  # raw string from API; converted to AttrType inside handler
    required: bool
    enum_values: list[str] | None


@dataclass(frozen=True, slots=True, kw_only=True)
class CreateResourceTypeCommand:
    slug: str
    name: str
    description: str
    attribute_schema: list[AttributeInput]


class CreateResourceTypeHandler:
    def __init__(self, repo: IResourceTypeRepository) -> None:
        self._repo = repo

    async def handle(self, cmd: CreateResourceTypeCommand) -> Result[ResourceTypeDto]:
        attrs_or_err = _build_attributes(cmd.attribute_schema)
        if attrs_or_err.is_failure:
            return Result.failure(attrs_or_err.error, status_code=422)

        rt_r = ResourceType.create(
            slug=cmd.slug,
            name=cmd.name,
            description=cmd.description,
            attribute_schema=attrs_or_err.value,
        )
        if rt_r.is_failure:
            return Result.failure(rt_r.error, status_code=422)
        rt = rt_r.value

        try:
            await self._repo.add(rt)
        except IntegrityError:
            return Result.failure(
                f"Já existe um ResourceType com slug '{cmd.slug}'.",
                status_code=409,
            )

        return Result.success(ResourceTypeDto.from_entity(rt), status_code=201)


def _build_attributes(
    inputs: list[AttributeInput],
) -> Result[list[AttributeDefinition]]:
    """Helper used by Create + Update handlers. The caller maps failures
    to a status code (422 in both current callers)."""
    errors: list[str] = []
    out: list[AttributeDefinition] = []
    for i, inp in enumerate(inputs):
        try:
            data_type = AttrType(inp.data_type)
        except ValueError:
            errors.append(
                f"attribute_schema[{i}].data_type inválido: '{inp.data_type}'. "
                f"Valores permitidos: {', '.join(t.value for t in AttrType)}."
            )
            continue
        a_r = AttributeDefinition.create(
            key=inp.key, label=inp.label, data_type=data_type,
            required=inp.required, enum_values=inp.enum_values,
        )
        if a_r.is_failure:
            errors.append(f"attribute_schema[{i}]: {a_r.error}")
            continue
        out.append(a_r.value)
    if errors:
        return Result.failure("; ".join(errors))
    return Result.success(out)
```

- [ ] **Step 4: Run — expect PASS.**

```bash
.venv/bin/pytest tests/unit/use_cases/catalog/commands/test_create_resource_type.py -q
```

- [ ] **Step 5: Commit**

```bash
git add app/use_cases/catalog/commands/create_resource_type.py tests/unit/use_cases/catalog/commands/test_create_resource_type.py
git commit -m "$(cat <<'EOF'
feat(catalog): add CreateResourceTypeHandler

Accepts an AttributeInput list (DTO from API), translates each entry
to an AttributeDefinition VO via .create(), then constructs the
aggregate via ResourceType.create(). Maps SQLAlchemy IntegrityError
on duplicate slug to a domain-language Result.failure.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

### Task C3 — `UpdateResourceTypeHandler`

**Files:** `app/use_cases/catalog/commands/update_resource_type.py`, `tests/unit/use_cases/catalog/commands/test_update_resource_type.py`.

Partial-update handler: any of `name`, `description`, `attribute_schema`, `is_active` may be None (not provided) or a value (apply). At least one must be provided.

- [ ] **Step 1: Failing test**

`tests/unit/use_cases/catalog/commands/test_update_resource_type.py`:

```python
from __future__ import annotations
from uuid import uuid4
import pytest
from app.domain.catalog.attribute import AttributeDefinition, AttrType
from app.domain.catalog.resource_type import ResourceType
from app.use_cases.catalog.commands.create_resource_type import AttributeInput
from app.use_cases.catalog.commands.update_resource_type import (
    UpdateResourceTypeCommand, UpdateResourceTypeHandler,
)
from tests.unit.use_cases.catalog.fakes.in_memory_resource_type_repository import (
    InMemoryResourceTypeRepository,
)


def _seed_rt(repo: InMemoryResourceTypeRepository, slug: str = "x") -> ResourceType:
    rt = ResourceType.create(
        slug=slug, name="Old", description="old desc",
        attribute_schema=[
            AttributeDefinition.create(
                key="surface", label="Piso", data_type=AttrType.STRING,
                required=True, enum_values=None,
            ).value,
        ],
    ).value
    repo._by_id[rt.id] = rt  # bypass add() to avoid the conflict path
    return rt


@pytest.mark.asyncio
async def test_update_name_and_description():
    repo = InMemoryResourceTypeRepository()
    rt = _seed_rt(repo)
    handler = UpdateResourceTypeHandler(repo)
    r = await handler.handle(UpdateResourceTypeCommand(
        resource_type_id=rt.id,
        name="New",
        description="new desc",
        attribute_schema=None,
        is_active=None,
    ))
    assert r.is_success
    dto = r.value
    assert dto.name == "New"
    assert dto.description == "new desc"
    # Untouched
    assert dto.is_active is True
    assert len(dto.attribute_schema) == 1


@pytest.mark.asyncio
async def test_update_attribute_schema_replaces_wholesale():
    repo = InMemoryResourceTypeRepository()
    rt = _seed_rt(repo)
    handler = UpdateResourceTypeHandler(repo)
    r = await handler.handle(UpdateResourceTypeCommand(
        resource_type_id=rt.id,
        name=None, description=None, is_active=None,
        attribute_schema=[
            AttributeInput(
                key="lighting", label="L", data_type="enum",
                required=False, enum_values=["a", "b"],
            ),
        ],
    ))
    assert r.is_success
    dto = r.value
    assert len(dto.attribute_schema) == 1
    assert dto.attribute_schema[0].key == "lighting"


@pytest.mark.asyncio
async def test_update_attribute_schema_invalid_returns_422():
    repo = InMemoryResourceTypeRepository()
    rt = _seed_rt(repo)
    handler = UpdateResourceTypeHandler(repo)
    r = await handler.handle(UpdateResourceTypeCommand(
        resource_type_id=rt.id,
        name=None, description=None, is_active=None,
        attribute_schema=[
            AttributeInput(
                key="bad", label="X", data_type="enum",
                required=False, enum_values=None,
            ),
        ],
    ))
    assert r.is_failure
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_update_is_active_toggle():
    repo = InMemoryResourceTypeRepository()
    rt = _seed_rt(repo)
    handler = UpdateResourceTypeHandler(repo)
    r = await handler.handle(UpdateResourceTypeCommand(
        resource_type_id=rt.id,
        name=None, description=None, attribute_schema=None,
        is_active=False,
    ))
    assert r.is_success
    assert r.value.is_active is False

    r = await handler.handle(UpdateResourceTypeCommand(
        resource_type_id=rt.id,
        name=None, description=None, attribute_schema=None,
        is_active=True,
    ))
    assert r.is_success
    assert r.value.is_active is True


@pytest.mark.asyncio
async def test_update_no_fields_provided_returns_400():
    repo = InMemoryResourceTypeRepository()
    rt = _seed_rt(repo)
    handler = UpdateResourceTypeHandler(repo)
    r = await handler.handle(UpdateResourceTypeCommand(
        resource_type_id=rt.id,
        name=None, description=None, attribute_schema=None, is_active=None,
    ))
    assert r.is_failure
    assert r.status_code == 400
    assert "campo" in r.error.lower() or "field" in r.error.lower()


@pytest.mark.asyncio
async def test_update_missing_resource_type_returns_404():
    repo = InMemoryResourceTypeRepository()
    handler = UpdateResourceTypeHandler(repo)
    r = await handler.handle(UpdateResourceTypeCommand(
        resource_type_id=uuid4(),
        name="X", description=None, attribute_schema=None, is_active=None,
    ))
    assert r.is_failure
    assert r.status_code == 404
    assert "encontrad" in r.error.lower() or "not found" in r.error.lower()
```

- [ ] **Step 2: Run — expect FAIL.**

- [ ] **Step 3: Implement**

`app/use_cases/catalog/commands/update_resource_type.py`:

```python
from __future__ import annotations
from dataclasses import dataclass
from uuid import UUID
from app.domain.catalog.repository import IResourceTypeRepository
from app.domain.shared.result import Result
from app.use_cases.catalog.commands.create_resource_type import (
    AttributeInput, _build_attributes,
)
from app.use_cases.catalog.dtos import ResourceTypeDto


@dataclass(frozen=True, slots=True, kw_only=True)
class UpdateResourceTypeCommand:
    resource_type_id: UUID
    name: str | None
    description: str | None
    attribute_schema: list[AttributeInput] | None
    is_active: bool | None


class UpdateResourceTypeHandler:
    def __init__(self, repo: IResourceTypeRepository) -> None:
        self._repo = repo

    async def handle(self, cmd: UpdateResourceTypeCommand) -> Result[ResourceTypeDto]:
        if (cmd.name is None and cmd.description is None
                and cmd.attribute_schema is None and cmd.is_active is None):
            return Result.failure(
                "Nenhum campo enviado para atualização.",
                status_code=400,
            )

        rt = await self._repo.get_by_id(cmd.resource_type_id)
        if rt is None:
            return Result.failure(
                f"ResourceType {cmd.resource_type_id} não encontrado.",
                status_code=404,
            )

        if cmd.name is not None or cmd.description is not None:
            rt.update_metadata(
                name=cmd.name if cmd.name is not None else rt.name,
                description=cmd.description if cmd.description is not None else rt.description,
            )

        if cmd.attribute_schema is not None:
            attrs_r = _build_attributes(cmd.attribute_schema)
            if attrs_r.is_failure:
                return Result.failure(attrs_r.error, status_code=422)
            replace_r = rt.replace_attribute_schema(attrs_r.value)
            if replace_r.is_failure:
                return Result.failure(replace_r.error, status_code=422)

        if cmd.is_active is not None:
            if cmd.is_active:
                rt.activate()
            else:
                rt.deactivate()

        await self._repo.update(rt)
        return Result.success(ResourceTypeDto.from_entity(rt))
```

- [ ] **Step 4: Run — expect PASS.**

```bash
.venv/bin/pytest tests/unit/use_cases/catalog/commands/test_update_resource_type.py -q
```

- [ ] **Step 5: Commit**

```bash
git add app/use_cases/catalog/commands/update_resource_type.py tests/unit/use_cases/catalog/commands/test_update_resource_type.py
git commit -m "$(cat <<'EOF'
feat(catalog): add UpdateResourceTypeHandler

Partial update — any field may be None (skip) or set (apply).
Reuses _build_attributes from create_resource_type.py to translate
AttributeInput → AttributeDefinition. attribute_schema is replaced
wholesale (no per-key patching).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

### Task C4 — `DeleteResourceTypeHandler`

**Files:** `app/use_cases/catalog/commands/delete_resource_type.py`, `tests/unit/use_cases/catalog/commands/test_delete_resource_type.py`.

Per Decision 6, this handler does NOT yet check whether `Resource` rows reference this type. A `# TODO(plan-04)` comment marks the gap.

- [ ] **Step 1: Failing test**

`tests/unit/use_cases/catalog/commands/test_delete_resource_type.py`:

```python
from __future__ import annotations
from uuid import uuid4
import pytest
from app.domain.catalog.resource_type import ResourceType
from app.use_cases.catalog.commands.delete_resource_type import (
    DeleteResourceTypeCommand, DeleteResourceTypeHandler,
)
from tests.unit.use_cases.catalog.fakes.in_memory_resource_type_repository import (
    InMemoryResourceTypeRepository,
)


@pytest.mark.asyncio
async def test_delete_existing_resource_type():
    repo = InMemoryResourceTypeRepository()
    rt = ResourceType.create(
        slug="x", name="X", description="", attribute_schema=[],
    ).value
    repo._by_id[rt.id] = rt
    handler = DeleteResourceTypeHandler(repo)

    r = await handler.handle(DeleteResourceTypeCommand(resource_type_id=rt.id))
    assert r.is_success
    assert await repo.get_by_id(rt.id) is None


@pytest.mark.asyncio
async def test_delete_missing_resource_type_returns_404():
    repo = InMemoryResourceTypeRepository()
    handler = DeleteResourceTypeHandler(repo)
    r = await handler.handle(DeleteResourceTypeCommand(resource_type_id=uuid4()))
    assert r.is_failure
    assert r.status_code == 404
    assert "encontrad" in r.error.lower() or "not found" in r.error.lower()
```

- [ ] **Step 2: Run — expect FAIL.**

- [ ] **Step 3: Implement**

`app/use_cases/catalog/commands/delete_resource_type.py`:

```python
from __future__ import annotations
from dataclasses import dataclass
from uuid import UUID
from app.domain.catalog.repository import IResourceTypeRepository
from app.domain.shared.result import Result


@dataclass(frozen=True, slots=True, kw_only=True)
class DeleteResourceTypeCommand:
    resource_type_id: UUID


class DeleteResourceTypeHandler:
    """Hard-delete a ResourceType.

    TODO(plan-04): inject IResourceRepository and reject deletion when
    any Resource references this type (spec §5.2 invariant
    "Deletion is allowed only if no Resource references the type").
    Resource doesn't exist yet, so the check would be vacuous now.
    """

    def __init__(self, repo: IResourceTypeRepository) -> None:
        self._repo = repo

    async def handle(self, cmd: DeleteResourceTypeCommand) -> Result[None]:
        existing = await self._repo.get_by_id(cmd.resource_type_id)
        if existing is None:
            return Result.failure(
                f"ResourceType {cmd.resource_type_id} não encontrado.",
                status_code=404,
            )
        await self._repo.delete(cmd.resource_type_id)
        return Result.success(None)
```

- [ ] **Step 4: Run — expect PASS.**

```bash
.venv/bin/pytest tests/unit/use_cases/catalog/commands/test_delete_resource_type.py -q
```

- [ ] **Step 5: Commit**

```bash
git add app/use_cases/catalog/commands/delete_resource_type.py tests/unit/use_cases/catalog/commands/test_delete_resource_type.py
git commit -m "$(cat <<'EOF'
feat(catalog): add DeleteResourceTypeHandler

Hard-delete with a 404-style check for missing rows. The "blocked
if Resource references this type" invariant from spec §5.2 is
deferred to plan-04 (resources) — marked with TODO(plan-04) in the
handler docstring.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

### Unit C — verification before handoff

- [ ] Run all unit tests for use cases.

```bash
.venv/bin/pytest tests/unit/use_cases/ -q
```

Expect: green.

- [ ] Run ruff over the new use-case code.

```bash
.venv/bin/python -m ruff check app/use_cases/catalog tests/unit/use_cases/catalog
```

Expect: clean.

---

## UNIT D — API layer + e2e

### Task D1 — `app/api/v1/admin_resource_types/` (deps + schemas)

**Files:** `app/api/v1/admin_resource_types/__init__.py`, `app/api/v1/admin_resource_types/deps.py`, `app/api/v1/admin_resource_types/schemas.py`.

- [ ] **Step 1: Implement deps**

`app/api/v1/admin_resource_types/__init__.py`:

```python
from app.api.v1.admin_resource_types.routes import router

__all__ = ["router"]
```

`app/api/v1/admin_resource_types/deps.py`:

```python
from __future__ import annotations
from typing import Annotated
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.catalog.repository import IResourceTypeRepository
from app.infrastructure.db.session import get_session
from app.infrastructure.repositories.resource_type_repository import (
    ResourceTypeRepository,
)
from app.use_cases.catalog.commands.create_resource_type import CreateResourceTypeHandler
from app.use_cases.catalog.commands.delete_resource_type import DeleteResourceTypeHandler
from app.use_cases.catalog.commands.update_resource_type import UpdateResourceTypeHandler


def get_resource_type_repository(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> IResourceTypeRepository:
    return ResourceTypeRepository(session)


ResourceTypeRepo = Annotated[IResourceTypeRepository, Depends(get_resource_type_repository)]


def get_create_resource_type_handler(repo: ResourceTypeRepo) -> CreateResourceTypeHandler:
    return CreateResourceTypeHandler(repo)


def get_update_resource_type_handler(repo: ResourceTypeRepo) -> UpdateResourceTypeHandler:
    return UpdateResourceTypeHandler(repo)


def get_delete_resource_type_handler(repo: ResourceTypeRepo) -> DeleteResourceTypeHandler:
    return DeleteResourceTypeHandler(repo)
```

`app/api/v1/admin_resource_types/schemas.py`:

```python
from __future__ import annotations
from datetime import datetime
from typing import Literal, Self
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field
from app.use_cases.catalog.commands.create_resource_type import AttributeInput
from app.use_cases.catalog.dtos import AttributeDefinitionDto, ResourceTypeDto


AttrTypeLiteral = Literal["string", "int", "bool", "enum"]


class AttributeDefinitionPayload(BaseModel):
    """Inbound + outbound shape for an attribute_schema entry."""
    model_config = ConfigDict(extra="forbid")

    key: str = Field(..., min_length=1, max_length=64)
    label: str = Field(..., min_length=1, max_length=200)
    data_type: AttrTypeLiteral
    required: bool
    enum_values: list[str] | None = None

    def to_input(self) -> AttributeInput:
        return AttributeInput(
            key=self.key,
            label=self.label,
            data_type=self.data_type,
            required=self.required,
            enum_values=self.enum_values,
        )

    @classmethod
    def from_dto(cls, a: AttributeDefinitionDto) -> Self:
        return cls(
            key=a.key, label=a.label, data_type=a.data_type,  # type: ignore[arg-type]
            required=a.required,
            enum_values=list(a.enum_values) if a.enum_values is not None else None,
        )


class CreateResourceTypeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slug: str = Field(..., min_length=2, max_length=80)
    name: str = Field(..., min_length=1, max_length=200)
    description: str = Field("", max_length=1000)
    attribute_schema: list[AttributeDefinitionPayload] = Field(default_factory=list)


class UpdateResourceTypeRequest(BaseModel):
    """All fields optional. Caller must send at least one."""
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = Field(None, max_length=1000)
    attribute_schema: list[AttributeDefinitionPayload] | None = None
    is_active: bool | None = None


class ResourceTypeResponse(BaseModel):
    id: UUID
    slug: str
    name: str
    description: str
    attribute_schema: list[AttributeDefinitionPayload]
    is_active: bool
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_dto(cls, dto: ResourceTypeDto) -> Self:
        return cls(
            id=dto.id,
            slug=dto.slug,
            name=dto.name,
            description=dto.description,
            attribute_schema=[
                AttributeDefinitionPayload.from_dto(a) for a in dto.attribute_schema
            ],
            is_active=dto.is_active,
            created_at=dto.created_at,
            updated_at=dto.updated_at,
        )


class ListResourceTypesResponse(BaseModel):
    items: list[ResourceTypeResponse]
```

- [ ] **Step 2: Verify imports**

```bash
.venv/bin/python -c "from app.api.v1.admin_resource_types.deps import get_create_resource_type_handler; print('ok')"
.venv/bin/python -c "from app.api.v1.admin_resource_types.schemas import ResourceTypeResponse; print('ok')"
```

Expect: `ok` on each.

- [ ] **Step 3: Commit (no commit yet — routes.py is missing; commit at end of D2)**

(Skip — combined commit at end of D2.)

### Task D2 — Admin routes (`POST/GET/PATCH/DELETE /v1/admin/resource-types`)

**Files:** `app/api/v1/admin_resource_types/routes.py`.

- [ ] **Step 1: Implement**

`app/api/v1/admin_resource_types/routes.py`:

```python
from __future__ import annotations
from typing import Annotated
from uuid import UUID
from fastapi import APIRouter, Depends, Query

from app.api.deps import require_role
from app.api.error_handler import unwrap
from app.api.v1.admin_resource_types.deps import (
    ResourceTypeRepo,
    get_create_resource_type_handler,
    get_delete_resource_type_handler,
    get_update_resource_type_handler,
)
from app.api.v1.admin_resource_types.schemas import (
    CreateResourceTypeRequest,
    ListResourceTypesResponse,
    ResourceTypeResponse,
    UpdateResourceTypeRequest,
)
from app.domain.accounts.role import Role
from app.use_cases.catalog.commands.create_resource_type import (
    CreateResourceTypeCommand, CreateResourceTypeHandler,
)
from app.use_cases.catalog.commands.delete_resource_type import (
    DeleteResourceTypeCommand, DeleteResourceTypeHandler,
)
from app.use_cases.catalog.commands.update_resource_type import (
    UpdateResourceTypeCommand, UpdateResourceTypeHandler,
)
from app.use_cases.catalog.dtos import ResourceTypeDto


router = APIRouter(
    prefix="/v1/admin/resource-types",
    tags=["admin", "catalog"],
    dependencies=[Depends(require_role(Role.ADMIN))],
)


@router.post("", response_model=ResourceTypeResponse, status_code=201)
async def create_resource_type(
    req: CreateResourceTypeRequest,
    handler: Annotated[CreateResourceTypeHandler, Depends(get_create_resource_type_handler)],
) -> ResourceTypeResponse:
    dto: ResourceTypeDto = unwrap(await handler.handle(CreateResourceTypeCommand(
        slug=req.slug,
        name=req.name,
        description=req.description,
        attribute_schema=[a.to_input() for a in req.attribute_schema],
    )))
    return ResourceTypeResponse.from_dto(dto)


@router.get("", response_model=ListResourceTypesResponse)
async def list_resource_types(
    repo: ResourceTypeRepo,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> ListResourceTypesResponse:
    rows = await repo.list(limit=limit, offset=offset, only_active=False)
    items = [ResourceTypeResponse.from_dto(ResourceTypeDto.from_entity(rt)) for rt in rows]
    return ListResourceTypesResponse(items=items)


@router.patch("/{resource_type_id}", response_model=ResourceTypeResponse)
async def update_resource_type(
    resource_type_id: UUID,
    req: UpdateResourceTypeRequest,
    handler: Annotated[UpdateResourceTypeHandler, Depends(get_update_resource_type_handler)],
) -> ResourceTypeResponse:
    cmd = UpdateResourceTypeCommand(
        resource_type_id=resource_type_id,
        name=req.name,
        description=req.description,
        attribute_schema=(
            [a.to_input() for a in req.attribute_schema]
            if req.attribute_schema is not None else None
        ),
        is_active=req.is_active,
    )
    dto: ResourceTypeDto = unwrap(await handler.handle(cmd))
    return ResourceTypeResponse.from_dto(dto)


@router.delete("/{resource_type_id}", status_code=204)
async def delete_resource_type(
    resource_type_id: UUID,
    handler: Annotated[DeleteResourceTypeHandler, Depends(get_delete_resource_type_handler)],
) -> None:
    unwrap(await handler.handle(DeleteResourceTypeCommand(
        resource_type_id=resource_type_id,
    )))
```

- [ ] **Step 2: Verify the router imports cleanly**

```bash
.venv/bin/python -c "from app.api.v1.admin_resource_types import router; print(router.routes)"
```

Expect: a list of 4 routes (POST, GET, PATCH, DELETE).

- [ ] **Step 3: Commit**

```bash
git add app/api/v1/admin_resource_types/
git commit -m "$(cat <<'EOF'
feat(api): add /v1/admin/resource-types CRUD routes

Admin-guarded endpoints for managing the catalog. Pydantic schemas
forbid extra fields; AttributeDefinitionPayload mirrors the domain
VO so the API contract is the canonical wire format.

POST returns 201 + body, PATCH/GET return 200 + body, DELETE returns
204 + empty.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

### Task D3 — Public route (`GET /v1/catalog/resource-types`) + wire routers

**Files:** `app/api/v1/catalog/__init__.py`, `app/api/v1/catalog/routes.py`, `app/api/v1/catalog/schemas.py`, `app/api/v1/router.py` (modify).

The public route shows ONLY active resource types and reuses a thinner response (no `is_active`, no `created_at`/`updated_at` — the public shape doesn't need them).

- [ ] **Step 1: Implement schemas**

`app/api/v1/catalog/__init__.py`:

```python
from app.api.v1.catalog.routes import router

__all__ = ["router"]
```

`app/api/v1/catalog/schemas.py`:

```python
from __future__ import annotations
from typing import Self
from uuid import UUID
from pydantic import BaseModel
from app.use_cases.catalog.dtos import ResourceTypeDto
from app.api.v1.admin_resource_types.schemas import AttributeDefinitionPayload


class PublicResourceTypeResponse(BaseModel):
    """Slimmed-down view of a ResourceType for public/storefront consumers."""
    id: UUID
    slug: str
    name: str
    description: str
    attribute_schema: list[AttributeDefinitionPayload]

    @classmethod
    def from_dto(cls, dto: ResourceTypeDto) -> Self:
        return cls(
            id=dto.id,
            slug=dto.slug,
            name=dto.name,
            description=dto.description,
            attribute_schema=[
                AttributeDefinitionPayload.from_dto(a) for a in dto.attribute_schema
            ],
        )


class PublicListResourceTypesResponse(BaseModel):
    items: list[PublicResourceTypeResponse]
```

- [ ] **Step 2: Implement routes**

`app/api/v1/catalog/routes.py`:

```python
from __future__ import annotations
from fastapi import APIRouter, Query

from app.api.v1.admin_resource_types.deps import ResourceTypeRepo
from app.api.v1.catalog.schemas import (
    PublicListResourceTypesResponse, PublicResourceTypeResponse,
)
from app.use_cases.catalog.dtos import ResourceTypeDto


router = APIRouter(prefix="/v1/catalog", tags=["catalog"])


@router.get("/resource-types", response_model=PublicListResourceTypesResponse)
async def list_active_resource_types(
    repo: ResourceTypeRepo,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> PublicListResourceTypesResponse:
    rows = await repo.list(limit=limit, offset=offset, only_active=True)
    items = [PublicResourceTypeResponse.from_dto(ResourceTypeDto.from_entity(rt)) for rt in rows]
    return PublicListResourceTypesResponse(items=items)
```

- [ ] **Step 3: Wire both routers into `app/api/v1/router.py`**

Read the current state of the file first:

```bash
.venv/bin/python -c "
with open('app/api/v1/router.py') as f:
    print(f.read())
"
```

Currently it should have (from Plan 02):

```python
from app.api.v1.admin_users import router as admin_users_router
from app.api.v1.auth import router as auth_router
...
api_router.include_router(auth_router)
api_router.include_router(admin_users_router)
```

Add the catalog routers in the same alphabetical-ish order. The final imports + `include_router` calls should be:

```python
from app.api.v1.admin_resource_types import router as admin_resource_types_router
from app.api.v1.admin_users import router as admin_users_router
from app.api.v1.auth import router as auth_router
from app.api.v1.catalog import router as catalog_router

api_router.include_router(auth_router)
api_router.include_router(admin_users_router)
api_router.include_router(admin_resource_types_router)
api_router.include_router(catalog_router)
```

(The exact existing arrangement may differ slightly — keep the existing two routers in their current positions and just add the two new lines. Don't reorder unrelated lines.)

- [ ] **Step 4: Smoke test that the app boots**

```bash
BACKEND_DATABASE_URL="sqlite+aiosqlite:///:memory:" \
  .venv/bin/python -c "
from app.main import app
routes = sorted(r.path for r in app.routes if hasattr(r, 'path'))
catalog_routes = [r for r in routes if 'catalog' in r or 'resource-types' in r]
for r in catalog_routes:
    print(r)
"
```

Expect output:
```
/v1/admin/resource-types
/v1/admin/resource-types/{resource_type_id}
/v1/catalog/resource-types
```

- [ ] **Step 5: Run the FULL test suite to confirm nothing regressed**

```bash
.venv/bin/pytest -q
```

Expect: green.

- [ ] **Step 6: Commit**

```bash
git add app/api/v1/catalog/ app/api/v1/router.py
git commit -m "$(cat <<'EOF'
feat(api): add public GET /v1/catalog/resource-types + wire routers

Public listing returns only active types and uses a slimmed-down
response shape (no is_active, no timestamps). Both the admin and
public routers are now registered in the v1 api router.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

### Task D4 — End-to-end tests

**Files:** `tests/e2e/catalog/__init__.py` (empty), `tests/e2e/catalog/conftest.py`, `tests/e2e/catalog/test_admin_and_public_flow.py`.

To exercise admin endpoints we need an admin token. Accounts only allows OWNER/CUSTOMER to self-register, so we seed an admin directly in the DB via the same sessionmaker that the `client` fixture wired up.

**Important fixture wiring detail:** `tests/e2e/conftest.py`'s `client` fixture sets `app.infrastructure.db.session._sessionmaker` to a real sessionmaker that points at the per-test in-memory SQLite engine. The `client` fixture also sets `_engine` and tears both down at the end. The `admin_token` fixture below depends on `client` (so the engine is already set up) and pulls a session out of that same sessionmaker.

The fixture also re-uses the existing `JoseJwtService.issue(...)` rather than constructing tokens manually — that path is already exercised by Plan 02's e2e tests, so it's known good.

- [ ] **Step 1: Implement the conftest**

`tests/e2e/catalog/__init__.py`: empty.

`tests/e2e/catalog/conftest.py`:

```python
from __future__ import annotations
import pytest_asyncio

from app.core.config import get_settings
from app.domain.accounts.role import Role
from app.domain.accounts.user import User
from app.infrastructure.auth.argon2_password_hasher import Argon2PasswordHasher
from app.infrastructure.auth.jose_jwt_service import JoseJwtService
from app.infrastructure.db import session as session_mod
from app.infrastructure.repositories.user_repository import UserRepository


@pytest_asyncio.fixture
async def admin_token(client) -> str:
    """Seed an admin user directly in the DB and mint a fresh access token.

    Depends on `client` so that `session_mod._sessionmaker` is wired to the
    per-test in-memory engine.
    """
    s = get_settings()
    hasher = Argon2PasswordHasher(
        time_cost=s.argon2_time_cost,
        memory_cost_kib=s.argon2_memory_cost_kib,
        parallelism=s.argon2_parallelism,
    )
    user_r = User.create(
        email="admin@example.com",
        password_hash=hasher.hash("irrelevant-since-we-mint-a-token"),
        role=Role.ADMIN,
        full_name="Root Admin",
        phone=None,
    )
    user = user_r.value

    assert session_mod._sessionmaker is not None, (
        "client fixture must run first to wire the sessionmaker"
    )
    async with session_mod._sessionmaker() as db:
        repo = UserRepository(db)
        await repo.add(user)
        await db.commit()

    jwt_svc = JoseJwtService(
        secret_key=s.jwt_secret_key.get_secret_value(),
        algorithm=s.jwt_algorithm,
        access_token_expires_seconds=s.jwt_access_token_expires_minutes * 60,
        refresh_token_expires_seconds=s.jwt_refresh_token_expires_days * 24 * 3600,
    )
    pair = jwt_svc.issue_pair(user_id=user.id, role=user.role)
    return pair.access_token
```

(The method is `issue_pair`, not `issue` — verified against `app/infrastructure/auth/jose_jwt_service.py:27` and `app/use_cases/accounts/commands/login.py:49`. The return type is `TokenPair` with `.access_token` and `.refresh_token` attributes.)

- [ ] **Step 2: Implement the e2e tests**

`tests/e2e/catalog/test_admin_and_public_flow.py`:

```python
from __future__ import annotations
import pytest


@pytest.mark.asyncio
async def test_admin_create_list_get_update_delete_flow(client, admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}

    # Create
    r = await client.post("/v1/admin/resource-types", headers=headers, json={
        "slug": "football-field",
        "name": "Campo de Futebol",
        "description": "Campo gramado.",
        "attribute_schema": [
            {"key": "surface", "label": "Piso", "data_type": "string",
             "required": True, "enum_values": None},
            {"key": "lighting", "label": "Iluminação", "data_type": "enum",
             "required": False, "enum_values": ["natural", "artificial"]},
        ],
    })
    assert r.status_code == 201, r.text
    body = r.json()
    rt_id = body["id"]
    assert body["slug"] == "football-field"
    assert body["is_active"] is True
    assert len(body["attribute_schema"]) == 2

    # Admin list — sees the row
    r = await client.get("/v1/admin/resource-types", headers=headers)
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    assert any(i["id"] == rt_id for i in items)

    # PATCH — change name + deactivate
    r = await client.patch(f"/v1/admin/resource-types/{rt_id}", headers=headers, json={
        "name": "Campo Society",
        "is_active": False,
    })
    assert r.status_code == 200, r.text
    assert r.json()["name"] == "Campo Society"
    assert r.json()["is_active"] is False

    # Public listing — should NOT see the now-inactive row
    r = await client.get("/v1/catalog/resource-types")
    assert r.status_code == 200, r.text
    public_items = r.json()["items"]
    assert all(i["id"] != rt_id for i in public_items)

    # Re-activate, public sees it
    r = await client.patch(f"/v1/admin/resource-types/{rt_id}", headers=headers,
                           json={"is_active": True})
    assert r.status_code == 200
    r = await client.get("/v1/catalog/resource-types")
    assert any(i["id"] == rt_id for i in r.json()["items"])

    # DELETE
    r = await client.delete(f"/v1/admin/resource-types/{rt_id}", headers=headers)
    assert r.status_code == 204

    # Confirmed gone — admin list no longer includes it
    r = await client.get("/v1/admin/resource-types", headers=headers)
    assert r.status_code == 200
    assert all(i["id"] != rt_id for i in r.json()["items"])


@pytest.mark.asyncio
async def test_admin_endpoints_require_admin_role(client):
    # Register a customer; their token must NOT work on admin endpoints
    await client.post("/v1/auth/register", json={
        "email": "cust@example.com", "password": "hunter2-strong",
        "role": "customer", "full_name": "Cust", "phone": None,
    })
    r = await client.post("/v1/auth/login", json={
        "email": "cust@example.com", "password": "hunter2-strong",
    })
    customer_token = r.json()["access_token"]

    r = await client.post(
        "/v1/admin/resource-types",
        headers={"Authorization": f"Bearer {customer_token}"},
        json={"slug": "x", "name": "X", "description": "", "attribute_schema": []},
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_admin_endpoints_require_token(client):
    # No Authorization header — 401
    r = await client.get("/v1/admin/resource-types")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_create_duplicate_slug_returns_409(client, admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}
    payload = {"slug": "dup", "name": "Dup", "description": "", "attribute_schema": []}
    r1 = await client.post("/v1/admin/resource-types", headers=headers, json=payload)
    assert r1.status_code == 201
    r2 = await client.post("/v1/admin/resource-types", headers=headers, json=payload)
    assert r2.status_code == 409
    assert "slug" in r2.text.lower() or "dup" in r2.text.lower()


@pytest.mark.asyncio
async def test_create_invalid_attribute_schema_422(client, admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}
    # Pydantic-level rejection: data_type must be a literal we declared
    r = await client.post("/v1/admin/resource-types", headers=headers, json={
        "slug": "x", "name": "X", "description": "",
        "attribute_schema": [
            {"key": "k", "label": "L", "data_type": "float",
             "required": True, "enum_values": None},
        ],
    })
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_create_enum_without_values_returns_422(client, admin_token):
    """Pydantic accepts data_type='enum' (it's in the literal); the
    handler-level validation catches the missing enum_values and
    returns 422 (semantic validation failure)."""
    headers = {"Authorization": f"Bearer {admin_token}"}
    r = await client.post("/v1/admin/resource-types", headers=headers, json={
        "slug": "x", "name": "X", "description": "",
        "attribute_schema": [
            {"key": "k", "label": "L", "data_type": "enum",
             "required": False, "enum_values": None},
        ],
    })
    assert r.status_code == 422
    assert "enum" in r.text.lower()


@pytest.mark.asyncio
async def test_delete_missing_resource_type_returns_404(client, admin_token):
    from uuid import uuid4
    headers = {"Authorization": f"Bearer {admin_token}"}
    r = await client.delete(f"/v1/admin/resource-types/{uuid4()}", headers=headers)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_update_no_fields_returns_400(client, admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}
    # First create something to PATCH
    r = await client.post("/v1/admin/resource-types", headers=headers, json={
        "slug": "patchable", "name": "X", "description": "", "attribute_schema": [],
    })
    rt_id = r.json()["id"]
    r = await client.patch(f"/v1/admin/resource-types/{rt_id}", headers=headers, json={})
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_update_missing_resource_type_returns_404(client, admin_token):
    from uuid import uuid4
    headers = {"Authorization": f"Bearer {admin_token}"}
    r = await client.patch(
        f"/v1/admin/resource-types/{uuid4()}",
        headers=headers, json={"name": "X"},
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_public_list_excludes_inactive(client, admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}
    # Two types, one deactivated
    await client.post("/v1/admin/resource-types", headers=headers, json={
        "slug": "active-one", "name": "A", "description": "", "attribute_schema": [],
    })
    r = await client.post("/v1/admin/resource-types", headers=headers, json={
        "slug": "inactive-one", "name": "I", "description": "", "attribute_schema": [],
    })
    inactive_id = r.json()["id"]
    await client.patch(f"/v1/admin/resource-types/{inactive_id}",
                       headers=headers, json={"is_active": False})

    r = await client.get("/v1/catalog/resource-types")
    slugs = [i["slug"] for i in r.json()["items"]]
    assert "active-one" in slugs
    assert "inactive-one" not in slugs


@pytest.mark.asyncio
async def test_public_list_response_shape(client, admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}
    await client.post("/v1/admin/resource-types", headers=headers, json={
        "slug": "shape-test", "name": "Shape", "description": "",
        "attribute_schema": [],
    })
    r = await client.get("/v1/catalog/resource-types")
    assert r.status_code == 200
    item = next(i for i in r.json()["items"] if i["slug"] == "shape-test")
    # Public response must NOT leak the admin-only fields
    assert "is_active" not in item
    assert "created_at" not in item
    assert "updated_at" not in item
    # But carries the slim admin/public-shared shape
    assert set(item.keys()) == {"id", "slug", "name", "description", "attribute_schema"}
```

- [ ] **Step 3: Run the e2e suite — expect green**

```bash
.venv/bin/pytest tests/e2e/catalog/ -q
```

If a test fails because of a fixture mismatch (e.g., the existing `client` fixture autocreates DB tables but the seed insertion happens after), debug by adding `print(repr(...))` calls inside the fixture, then remove them once the issue is found. Common fixture bugs to look for:
- Test session DB not created — should be auto-created by `tests/e2e/conftest.py`'s `client` fixture; if it isn't, the accounts e2e wouldn't have worked either
- Admin user inserted but token decoded against a different secret — make sure both insertion and token issuance use `get_settings()` from the same process

- [ ] **Step 4: Run the FULL suite + ruff**

```bash
.venv/bin/pytest -q
.venv/bin/python -m ruff check app tests
```

Both must be green/clean before committing.

- [ ] **Step 5: Commit**

```bash
git add tests/e2e/catalog/
git commit -m "$(cat <<'EOF'
test(e2e): add catalog admin + public flow tests

Covers the full admin CRUD lifecycle (create → list → patch →
deactivate → delete), the role guard (customer hits 403 on admin
endpoints, no token hits 401), the duplicate-slug conflict, the
two layers of attribute validation (Pydantic for unknown data_type,
handler for ENUM-without-values), the public list filter on
is_active, and the public response shape boundary.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

### Unit D — verification before handoff

- [ ] Run all e2e tests:

```bash
.venv/bin/pytest tests/e2e/ -q
```

Expect: green (existing accounts tests still pass + new catalog tests pass).

- [ ] Run the full suite + lint:

```bash
.venv/bin/pytest -q
.venv/bin/python -m ruff check app tests
```

- [ ] Smoke test the booted app once more:

```bash
BACKEND_DATABASE_URL="sqlite+aiosqlite:///:memory:" \
  .venv/bin/python -c "from app.main import app; print('ok'); print('title:', app.title)"
```

Expect: `ok`, `title: venue-backend`.

- [ ] Verify `git log --oneline | head -20` shows ~15 commits forming a clean Plan 03 sequence.

---

## Final whole-implementation review

After Unit D verification passes, dispatch a final code reviewer (`superpowers:code-reviewer`) over the entire `feat/plan-03-catalog` branch against this plan + spec sections §3 (architecture), §4.2 (cross-feature rules), §5.2 (catalog domain model), and §7.1 + §7.5 (API surface).

The reviewer should specifically check:
- Layering: domain has no infra/use_cases imports; use_cases has no infra imports; api wires both
- The `# TODO(plan-04)` in `delete_resource_type.py` is a known and tracked gap, not an unflagged hole
- AttributeDefinition ↔ dict serialization round-trips through the JSON column without lossy conversions (especially `enum_values` tuple ↔ list)
- Error mapping at the API boundary: 422 for Pydantic, 4xx for `Result.failure` via `error_handler.unwrap`
- The public response shape strictly excludes admin-only fields (regression risk on future schema changes)

If the review surfaces Critical or Important issues, auto-correct them before merge per project pre-authorization. Minor stylistic items can be deferred.

## Integration

After final review passes:
- `git checkout main && git merge --ff-only feat/plan-03-catalog && git push origin main`
- `git branch -d feat/plan-03-catalog`
- Leave the remote branch for manual deletion.

## Pause point

Plan 03 ships catalog. The next plan in the sequence (Plan 04 — `resources` feature) depends on `accounts` and `catalog`, both shipped. Pause for user approval before starting Plan 04.
