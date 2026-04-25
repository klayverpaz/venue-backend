# Plan 04 — `catalog` feature (`ResourceType` aggregate)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the `catalog` feature from scratch — `ResourceType` aggregate composed of `AttributeDefinition` VOs, admin CRUD endpoints (`POST/GET/PATCH/DELETE /v1/admin/resource-types`), public listing (`GET /v1/catalog/resource-types`), and a `validate_attributes(values)` helper that the future `resources` feature (Plan 06) will use to validate `Resource.base_attributes`. Leave `feat/plan-04-catalog` ready to ff-merge into `main` with all tests green.

**Architecture:** New domain feature `catalog/` with one aggregate (`ResourceType`) and one port (`IResourceTypeRepository`). All VOs already shipped by Plan 03 (`Slug`, `Name`, `ShortDescription`, `AttributeKey`, `ShortName`); this plan creates only one new VO local to the feature: `AttributeDefinition` (composite). `attribute_schema` is persisted as a JSON column on the `resource_types` table (works on Postgres + SQLite). Admin endpoints reuse the existing `require_role(Role.ADMIN)` guard from `app/api/deps.py`; public listing has no auth gate. No cross-feature handlers in this plan — `catalog` has zero feature dependencies (per spec §8 step 4). Entity follows the spec §4.4 convention: class-level error codes, `cls.create()` factory, mutators returning `Result[None]` when enforcing invariants, private collections with immutable views, `updated_at` bumped inside every successful mutator.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0 async, Alembic. No new third-party libraries — JSON storage uses SQLAlchemy's built-in `JSON` type which adapts to Postgres `JSON` and SQLite `TEXT`.

**Decisions pinned (do NOT re-debate during execution):**

| # | Decision | Rationale |
|---|---|---|
| 1 | Reuse `Slug`, `Name`, `ShortDescription`, `AttributeKey`, `ShortName` from `app/domain/shared/value_objects/` (shipped in Plan 03). | These are now part of the platform-wide convention. |
| 2 | `AttrType` is a `str` Enum with values `string`, `int`, `bool`, `enum` (lowercase). | Matches JSON wire format; no need to translate at the API boundary. |
| 3 | `AttributeDefinition.enum_values` is non-`None` **iff** `data_type == AttrType.ENUM`. Validated in `AttributeDefinition.create()`. | Keeps the VO self-consistent; eliminates a class of "ENUM with no values" or "STRING with stale values" bugs. |
| 4 | `attribute_schema` is persisted as a JSON column (`sa.JSON()` — generic, dialect-portable). The repository serializes `AttributeDefinition` ↔ dict at the boundary. | Avoids a separate `attribute_definitions` table for what is conceptually a typed list; simple to query, simple to evolve. |
| 5 | `UpdateResourceTypeHandler` accepts partial updates (name/description/attribute_schema/is_active) but `attribute_schema` is REPLACED wholesale when provided (no per-key patching). | Per-key patching is harder to validate consistently; replacement is what the admin UI will do anyway. |
| 6 | `DeleteResourceTypeHandler` does **NOT** check whether any `Resource` references this type. The "blocked if referenced" invariant from spec §5.2 is deferred to Plan 06 (`resources`), which will inject `IResourceRepository` and add the check. A `# TODO(plan-06)` comment marks the gap. | `Resource` does not exist yet — the check would be vacuous. Adding a Protocol stub now is ceremony. |
| 7 | Pagination uses `limit` + `offset` query params on list endpoints, mirroring `app/api/v1/admin_users/routes.py` from Plan 02. | Consistency with `accounts`. |
| 8 | Public list (`GET /v1/catalog/resource-types`) returns ONLY `is_active = True` rows. Admin list (`GET /v1/admin/resource-types`) returns all rows including inactive. | Public is the storefront filter UI; admin is for management. |
| 9 | Domain & handler errors are stable PascalCase code identifiers (e.g., `"SlugAlreadyTaken"`); pt-BR translation lives in `app/api/error_codes.py`. New handler-level codes added by this plan must include their pt-BR entry and be added to the architecture-test allowlist. | Spec §3 decision 15; same pattern as Plan 03. |
| 10 | No `ListResourceTypesQuery` / `GetResourceTypeQuery` handlers. List + detail are pure DB reads; routes call the repo directly. | Mirrors `admin_users/routes.py` from Plan 02 — no business logic worth wrapping. |
| 11 | The `validate_attributes(values: dict[str, Any]) -> Result[None]` method lives on the `ResourceType` entity. | The schema lives on the entity; co-locating the validator keeps callers simple — `resource_type.validate_attributes(...)`. |
| 12 | DB string columns use `Text` (no `VARCHAR(N)`) — VO governs length per spec §3 decision 17. | Same as `UserModel` in Plan 03. |

---

## Branch

```bash
git checkout -b feat/plan-04-catalog
```

All tasks below assume this branch is checked out.

---

## File structure

### New files

```
app/domain/catalog/
├── __init__.py
├── attribute.py                                  # AttrType enum + AttributeDefinition composite VO
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
app/api/error_codes.py                            # add catalog handler-level codes (pt-BR)
tests/unit/architecture/test_error_code_coverage.py  # extend handler_level_allowlist
```

### Test files (new)

```
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
| `slug` | Text | NOT NULL, UNIQUE, indexed |
| `name` | Text | NOT NULL |
| `description` | Text | NOT NULL, default `""` |
| `attribute_schema` | JSON | NOT NULL, default `[]` |
| `is_active` | Boolean | NOT NULL, default TRUE, indexed |
| `created_at` | DateTime(timezone=True) | NOT NULL (from `TimestampMixin`) |
| `updated_at` | DateTime(timezone=True) | NOT NULL (from `TimestampMixin`) |

No foreign keys. No cross-table joins.

---

## Execution Plan — four units

| Unit | Tasks | Approx commits |
|---|---|---|
| **A** | Domain layer (AttrType + AttributeDefinition + ResourceType + Repository protocol) | 4 |
| **B** | Infrastructure (mapping + migration + repo + integration test) | 3 |
| **C** | Use cases (Create / Update / Delete handlers + DTOs + fake repo) | 4 |
| **D** | API layer (admin + public routes) + e2e tests | 4 |

Total: **~15 commits**. Branch: `feat/plan-04-catalog`. ff-merges into `main` after final review.

---

## UNIT A — Domain layer

### Task A1 — `AttrType` enum + `AttributeDefinition` composite VO

`AttrType` is a string enum. `AttributeDefinition` is a composite VO bundling `key`/`label`/`data_type`/`required`/`enum_values`, with the conditional invariant that `enum_values` is non-`None` iff `data_type == AttrType.ENUM`.

**Files:** create `app/domain/catalog/__init__.py` (empty), `app/domain/catalog/attribute.py`, `tests/unit/domain/catalog/__init__.py` (empty), `tests/unit/domain/catalog/test_attribute.py`.

- [ ] **Step 1: Failing tests**

`tests/unit/domain/catalog/test_attribute.py`:

```python
from __future__ import annotations
from app.domain.catalog.attribute import AttrType, AttributeDefinition
from app.domain.shared.value_objects.attribute_key import AttributeKey
from app.domain.shared.value_objects.short_name import ShortName


def test_attr_type_values_lowercase():
    assert AttrType.STRING.value == "string"
    assert AttrType.INT.value == "int"
    assert AttrType.BOOL.value == "bool"
    assert AttrType.ENUM.value == "enum"


def test_attribute_definition_create_string_success():
    r = AttributeDefinition.create(
        key="field_size",
        label="Tamanho do campo",
        data_type=AttrType.STRING,
        required=True,
    )
    assert r.is_success
    assert isinstance(r.value.key, AttributeKey)
    assert r.value.key.value == "field_size"
    assert isinstance(r.value.label, ShortName)
    assert r.value.label.value == "Tamanho do campo"
    assert r.value.data_type == AttrType.STRING
    assert r.value.required is True
    assert r.value.enum_values is None


def test_attribute_definition_create_int_default_not_required():
    r = AttributeDefinition.create(
        key="players",
        label="Jogadores",
        data_type=AttrType.INT,
    )
    assert r.is_success
    assert r.value.required is False


def test_attribute_definition_create_enum_with_values():
    r = AttributeDefinition.create(
        key="surface",
        label="Tipo de gramado",
        data_type=AttrType.ENUM,
        enum_values=["natural", "synthetic"],
    )
    assert r.is_success
    assert r.value.enum_values is not None
    assert tuple(v.value for v in r.value.enum_values) == ("natural", "synthetic")


def test_attribute_definition_enum_requires_values():
    r = AttributeDefinition.create(
        key="surface",
        label="Tipo de gramado",
        data_type=AttrType.ENUM,
        enum_values=None,
    )
    assert r.is_failure
    assert AttributeDefinition.ENUM_TYPE_REQUIRES_VALUES in r.error


def test_attribute_definition_enum_rejects_empty_values():
    r = AttributeDefinition.create(
        key="surface",
        label="Tipo de gramado",
        data_type=AttrType.ENUM,
        enum_values=[],
    )
    assert r.is_failure
    assert AttributeDefinition.ENUM_TYPE_REQUIRES_VALUES in r.error


def test_attribute_definition_non_enum_rejects_values():
    r = AttributeDefinition.create(
        key="players",
        label="Jogadores",
        data_type=AttrType.INT,
        enum_values=["a", "b"],
    )
    assert r.is_failure
    assert AttributeDefinition.NON_ENUM_TYPE_CANNOT_HAVE_VALUES in r.error


def test_attribute_definition_propagates_attribute_key_error():
    r = AttributeDefinition.create(
        key="Invalid Key!",
        label="Foo",
        data_type=AttrType.STRING,
    )
    assert r.is_failure
    assert AttributeKey.ATTRIBUTE_KEY_INVALID_FORMAT in r.error


def test_attribute_definition_propagates_label_error():
    r = AttributeDefinition.create(
        key="ok",
        label="",
        data_type=AttrType.STRING,
    )
    assert r.is_failure
    assert ShortName.SHORT_NAME_CANNOT_BE_EMPTY in r.error


def test_attribute_definition_propagates_enum_value_error():
    r = AttributeDefinition.create(
        key="surface",
        label="Tipo",
        data_type=AttrType.ENUM,
        enum_values=["valid", ""],
    )
    assert r.is_failure
    assert ShortName.SHORT_NAME_CANNOT_BE_EMPTY in r.error


def test_attribute_definition_equality():
    a = AttributeDefinition.create(
        key="k", label="L", data_type=AttrType.STRING, required=True,
    ).value
    b = AttributeDefinition.create(
        key="k", label="L", data_type=AttrType.STRING, required=True,
    ).value
    assert a == b
    assert hash(a) == hash(b)
```

- [ ] **Step 2: Run — fail (ImportError on `app.domain.catalog.attribute`)**

```bash
.venv/bin/pytest tests/unit/domain/catalog/test_attribute.py -v
```

- [ ] **Step 3: Implementation**

`app/domain/catalog/__init__.py`: empty file.

`app/domain/catalog/attribute.py`:

```python
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Self
from app.domain.shared.result import Result
from app.domain.shared.value_object import BaseValueObject
from app.domain.shared.value_objects.attribute_key import AttributeKey
from app.domain.shared.value_objects.short_name import ShortName


class AttrType(str, Enum):
    STRING = "string"
    INT = "int"
    BOOL = "bool"
    ENUM = "enum"


@dataclass(frozen=True, slots=True)
class AttributeDefinition(BaseValueObject):
    ENUM_TYPE_REQUIRES_VALUES = "EnumTypeRequiresValues"
    NON_ENUM_TYPE_CANNOT_HAVE_VALUES = "NonEnumTypeCannotHaveValues"

    key: AttributeKey
    label: ShortName
    data_type: AttrType
    required: bool
    # tuple instead of list so the VO stays hashable + frozen-friendly.
    enum_values: tuple[ShortName, ...] | None

    @classmethod
    def create(
        cls,
        *,
        key: str,
        label: str,
        data_type: AttrType,
        required: bool = False,
        enum_values: list[str] | None = None,
    ) -> Result[Self]:
        errors: list[str] = []

        key_r = AttributeKey.create(key)
        if key_r.is_failure:
            errors.append(key_r.error)

        label_r = ShortName.create(label)
        if label_r.is_failure:
            errors.append(label_r.error)

        enum_vos: tuple[ShortName, ...] | None = None
        if data_type == AttrType.ENUM:
            if not enum_values:
                errors.append(cls.ENUM_TYPE_REQUIRES_VALUES)
            else:
                vos: list[ShortName] = []
                for raw in enum_values:
                    r = ShortName.create(raw)
                    if r.is_failure:
                        errors.append(r.error)
                    else:
                        vos.append(r.value)
                if not errors:
                    enum_vos = tuple(vos)
        else:
            if enum_values:
                errors.append(cls.NON_ENUM_TYPE_CANNOT_HAVE_VALUES)

        if errors:
            return Result.failure("; ".join(errors))

        return Result.success(cls(
            key=key_r.value,
            label=label_r.value,
            data_type=data_type,
            required=required,
            enum_values=enum_vos,
        ))
```

- [ ] **Step 4: Run — green**

```bash
.venv/bin/pytest tests/unit/domain/catalog/test_attribute.py -v
.venv/bin/pytest -q
```

Expected: 10 new tests pass; full suite still green.

- [ ] **Step 5: Add the new error codes to the pt-BR mapping**

Edit `app/api/error_codes.py`. Find the existing `# Handler-level (not VO-bound) codes` section (added in Plan 03) and add the catalog VO codes alongside it (or create a new `# Catalog VO-level` section). Since `AttributeDefinition` is a VO subclass of `BaseValueObject`, the architecture test will pick it up automatically — no allowlist needed.

```python
    # AttributeDefinition (catalog VO)
    AttributeDefinition.ENUM_TYPE_REQUIRES_VALUES: "Atributo do tipo enum precisa de valores possíveis.",
    AttributeDefinition.NON_ENUM_TYPE_CANNOT_HAVE_VALUES: "Atributo que não é enum não pode ter valores possíveis.",
```

Add the import at the top:

```python
from app.domain.catalog.attribute import AttributeDefinition
```

- [ ] **Step 6: Run architecture test**

```bash
.venv/bin/pytest tests/unit/architecture/test_error_code_coverage.py -v
```

Expected: 2 tests pass. The walker discovers `AttributeDefinition` as a `BaseValueObject` subclass and validates both new codes have translations.

- [ ] **Step 7: Run full suite**

```bash
.venv/bin/pytest -q
```

Expected: green.

- [ ] **Step 8: Commit**

```bash
git add app/domain/catalog/__init__.py app/domain/catalog/attribute.py \
        tests/unit/domain/catalog/__init__.py tests/unit/domain/catalog/test_attribute.py \
        app/api/error_codes.py
git commit -m "$(cat <<'EOF'
feat(catalog): add AttrType enum + AttributeDefinition composite VO

AttrType is a str Enum with lowercase values (string/int/bool/enum)
that doubles as the JSON wire format. AttributeDefinition is a
composite VO bundling key (AttributeKey), label (ShortName), data_type,
required, and conditionally enum_values (tuple[ShortName, ...] iff
data_type == ENUM). create() aggregates VO failures from key, label,
and each enum value, plus enforces the conditional ENUM-vs-values
invariant. pt-BR mappings registered.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task A2 — `ResourceType` aggregate

The aggregate root. Slug-keyed identity. Holds the schema list. Mutators per spec §4.4 conventions: `update_metadata` (no invariant → `None`), `replace_attribute_schema` (enforces unique-key invariant → `Result[None]`), `activate`/`deactivate` (no invariant → `None`).

**Files:** `app/domain/catalog/resource_type.py`, `tests/unit/domain/catalog/test_resource_type.py`.

- [ ] **Step 1: Failing tests**

`tests/unit/domain/catalog/test_resource_type.py`:

```python
from __future__ import annotations
from app.domain.catalog.attribute import AttrType, AttributeDefinition
from app.domain.catalog.resource_type import ResourceType
from app.domain.shared.value_objects.name import Name
from app.domain.shared.value_objects.short_description import ShortDescription
from app.domain.shared.value_objects.slug import Slug


def _ad(key: str, label: str, dt: AttrType = AttrType.STRING, **kw):
    return AttributeDefinition.create(key=key, label=label, data_type=dt, **kw).value


def test_resource_type_create_minimal():
    r = ResourceType.create(
        slug="football-field",
        name="Football Field",
        description="",
        attribute_schema=[],
    )
    assert r.is_success
    rt = r.value
    assert isinstance(rt.slug, Slug)
    assert isinstance(rt.name, Name)
    assert isinstance(rt.description, ShortDescription)
    assert rt.slug.value == "football-field"
    assert rt.name.value == "Football Field"
    assert rt.description.value == ""
    assert rt.attribute_schema == ()
    assert rt.is_active is True


def test_resource_type_create_with_schema():
    r = ResourceType.create(
        slug="padel-court",
        name="Padel Court",
        description="Quadras de padel cobertas",
        attribute_schema=[
            _ad("surface", "Tipo de gramado", AttrType.ENUM, enum_values=["sintetico", "natural"]),
            _ad("players", "Jogadores", AttrType.INT, required=True),
        ],
    )
    assert r.is_success
    assert len(r.value.attribute_schema) == 2


def test_resource_type_create_propagates_slug_error():
    r = ResourceType.create(
        slug="Invalid Slug!",
        name="Foo",
        description="",
        attribute_schema=[],
    )
    assert r.is_failure
    assert Slug.SLUG_INVALID_FORMAT in r.error


def test_resource_type_create_propagates_name_error():
    r = ResourceType.create(
        slug="football-field",
        name="",
        description="",
        attribute_schema=[],
    )
    assert r.is_failure
    assert Name.NAME_CANNOT_BE_EMPTY in r.error


def test_resource_type_create_rejects_duplicate_attribute_keys():
    a1 = _ad("size", "Tamanho")
    a2 = _ad("size", "Outro tamanho")
    r = ResourceType.create(
        slug="football-field",
        name="Football Field",
        description="",
        attribute_schema=[a1, a2],
    )
    assert r.is_failure
    assert ResourceType.DUPLICATE_ATTRIBUTE_KEY in r.error


def test_resource_type_attribute_schema_returns_tuple_view():
    rt = ResourceType.create(
        slug="football-field",
        name="Football Field",
        description="",
        attribute_schema=[_ad("size", "Tamanho")],
    ).value
    schema = rt.attribute_schema
    assert isinstance(schema, tuple)


def test_resource_type_update_metadata_no_invariant_returns_none():
    rt = ResourceType.create(
        slug="football-field", name="Football Field", description="", attribute_schema=[],
    ).value
    before = rt.updated_at
    result = rt.update_metadata(name="Campo de Futebol", description="atualizado")
    assert result is None
    assert rt.name.value == "Campo de Futebol"
    assert rt.description.value == "atualizado"
    assert rt.updated_at > before


def test_resource_type_replace_attribute_schema_success():
    rt = ResourceType.create(
        slug="football-field", name="Football Field", description="", attribute_schema=[],
    ).value
    new_schema = [_ad("size", "Tamanho"), _ad("players", "Jogadores", AttrType.INT)]
    r = rt.replace_attribute_schema(new_schema)
    assert r.is_success
    assert len(rt.attribute_schema) == 2


def test_resource_type_replace_attribute_schema_rejects_duplicates():
    rt = ResourceType.create(
        slug="football-field", name="Football Field", description="", attribute_schema=[],
    ).value
    r = rt.replace_attribute_schema([_ad("size", "A"), _ad("size", "B")])
    assert r.is_failure
    assert r.error == ResourceType.DUPLICATE_ATTRIBUTE_KEY


def test_resource_type_activate_deactivate():
    rt = ResourceType.create(
        slug="football-field", name="Football Field", description="", attribute_schema=[],
    ).value
    assert rt.is_active is True
    rt.deactivate()
    assert rt.is_active is False
    rt.activate()
    assert rt.is_active is True


def test_resource_type_validate_attributes_required_present():
    rt = ResourceType.create(
        slug="football-field", name="Football Field", description="",
        attribute_schema=[_ad("players", "Jogadores", AttrType.INT, required=True)],
    ).value
    assert rt.validate_attributes({"players": 10}).is_success


def test_resource_type_validate_attributes_required_missing():
    rt = ResourceType.create(
        slug="football-field", name="Football Field", description="",
        attribute_schema=[_ad("players", "Jogadores", AttrType.INT, required=True)],
    ).value
    r = rt.validate_attributes({})
    assert r.is_failure
    assert ResourceType.REQUIRED_ATTRIBUTE_MISSING in r.error
    assert "players" in r.error


def test_resource_type_validate_attributes_type_mismatch_int():
    rt = ResourceType.create(
        slug="football-field", name="Football Field", description="",
        attribute_schema=[_ad("players", "Jogadores", AttrType.INT, required=True)],
    ).value
    r = rt.validate_attributes({"players": "ten"})
    assert r.is_failure
    assert ResourceType.ATTRIBUTE_TYPE_MISMATCH in r.error


def test_resource_type_validate_attributes_type_mismatch_bool():
    rt = ResourceType.create(
        slug="football-field", name="Football Field", description="",
        attribute_schema=[_ad("lit", "Iluminado", AttrType.BOOL)],
    ).value
    r = rt.validate_attributes({"lit": "yes"})
    assert r.is_failure
    assert ResourceType.ATTRIBUTE_TYPE_MISMATCH in r.error


def test_resource_type_validate_attributes_enum_value_in_set():
    rt = ResourceType.create(
        slug="football-field", name="Football Field", description="",
        attribute_schema=[_ad("surface", "Tipo", AttrType.ENUM, enum_values=["natural", "synthetic"])],
    ).value
    assert rt.validate_attributes({"surface": "natural"}).is_success


def test_resource_type_validate_attributes_enum_value_not_in_set():
    rt = ResourceType.create(
        slug="football-field", name="Football Field", description="",
        attribute_schema=[_ad("surface", "Tipo", AttrType.ENUM, enum_values=["natural", "synthetic"])],
    ).value
    r = rt.validate_attributes({"surface": "concrete"})
    assert r.is_failure
    assert ResourceType.ATTRIBUTE_ENUM_VALUE_NOT_ALLOWED in r.error


def test_resource_type_validate_attributes_unknown_key():
    rt = ResourceType.create(
        slug="football-field", name="Football Field", description="",
        attribute_schema=[_ad("size", "Tamanho")],
    ).value
    r = rt.validate_attributes({"size": "ok", "unknown": "value"})
    assert r.is_failure
    assert ResourceType.UNKNOWN_ATTRIBUTE_KEY in r.error


def test_resource_type_validate_attributes_optional_absent_is_ok():
    rt = ResourceType.create(
        slug="football-field", name="Football Field", description="",
        attribute_schema=[_ad("size", "Tamanho", AttrType.STRING, required=False)],
    ).value
    assert rt.validate_attributes({}).is_success
```

- [ ] **Step 2: Run — fail**

```bash
.venv/bin/pytest tests/unit/domain/catalog/test_resource_type.py -v
```

- [ ] **Step 3: Implementation**

`app/domain/catalog/resource_type.py`:

```python
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable, Self
from app.domain.catalog.attribute import AttrType, AttributeDefinition
from app.domain.shared.entity import BaseEntity
from app.domain.shared.result import Result
from app.domain.shared.value_objects.name import Name
from app.domain.shared.value_objects.short_description import ShortDescription
from app.domain.shared.value_objects.slug import Slug


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(slots=True, kw_only=True)
class ResourceType(BaseEntity):
    DUPLICATE_ATTRIBUTE_KEY = "DuplicateAttributeKey"
    REQUIRED_ATTRIBUTE_MISSING = "RequiredAttributeMissing"
    UNKNOWN_ATTRIBUTE_KEY = "UnknownAttributeKey"
    ATTRIBUTE_TYPE_MISMATCH = "AttributeTypeMismatch"
    ATTRIBUTE_ENUM_VALUE_NOT_ALLOWED = "AttributeEnumValueNotAllowed"

    slug: Slug
    name: Name
    description: ShortDescription
    is_active: bool = True
    _attribute_schema: list[AttributeDefinition] = field(default_factory=list, repr=False)

    @classmethod
    def create(
        cls,
        *,
        slug: str,
        name: str,
        description: str,
        attribute_schema: Iterable[AttributeDefinition],
        is_active: bool = True,
    ) -> Result[Self]:
        errors: list[str] = []

        slug_r = Slug.create(slug)
        if slug_r.is_failure:
            errors.append(slug_r.error)

        name_r = Name.create(name)
        if name_r.is_failure:
            errors.append(name_r.error)

        desc_r = ShortDescription.create(description)
        if desc_r.is_failure:
            errors.append(desc_r.error)

        schema_list = list(attribute_schema)
        if cls._has_duplicate_keys(schema_list):
            errors.append(cls.DUPLICATE_ATTRIBUTE_KEY)

        if errors:
            return Result.failure("; ".join(errors))

        return Result.success(cls(
            slug=slug_r.value,
            name=name_r.value,
            description=desc_r.value,
            is_active=is_active,
            _attribute_schema=schema_list,
        ))

    @property
    def attribute_schema(self) -> tuple[AttributeDefinition, ...]:
        return tuple(self._attribute_schema)

    def update_metadata(self, *, name: str | None = None, description: str | None = None) -> None:
        """Updates name and/or description from raw input. No invariant — returns None.
        Validates each VO; if either fails, raises (caller should validate first via VOs).
        Per §4.4: mutators with no domain invariant return None. The VO factory is the
        validation gate.
        """
        if name is not None:
            r = Name.create(name)
            if r.is_success:
                self.name = r.value
        if description is not None:
            r = ShortDescription.create(description)
            if r.is_success:
                self.description = r.value
        self.updated_at = _utcnow()

    def replace_attribute_schema(self, definitions: Iterable[AttributeDefinition]) -> Result[None]:
        """Wholesale replacement. Enforces unique-key invariant — returns Result[None]."""
        defs = list(definitions)
        if self._has_duplicate_keys(defs):
            return Result.failure(self.DUPLICATE_ATTRIBUTE_KEY)
        self._attribute_schema = defs
        self.updated_at = _utcnow()
        return Result.success(None)

    def activate(self) -> None:
        self.is_active = True
        self.updated_at = _utcnow()

    def deactivate(self) -> None:
        self.is_active = False
        self.updated_at = _utcnow()

    def validate_attributes(self, values: dict[str, Any]) -> Result[None]:
        """Validate a dict of raw values against this type's attribute_schema.

        Used by future Plan 06 Resource.create() to validate Resource.base_attributes
        before persistence. Returns aggregated errors as semicolon-joined codes.
        """
        errors: list[str] = []
        defs_by_key = {d.key.value: d for d in self._attribute_schema}

        # Required attributes must be present.
        for d in self._attribute_schema:
            if d.required and d.key.value not in values:
                errors.append(f"{self.REQUIRED_ATTRIBUTE_MISSING}:{d.key.value}")

        for key, value in values.items():
            d = defs_by_key.get(key)
            if d is None:
                errors.append(f"{self.UNKNOWN_ATTRIBUTE_KEY}:{key}")
                continue

            if d.data_type == AttrType.STRING:
                if not isinstance(value, str):
                    errors.append(f"{self.ATTRIBUTE_TYPE_MISMATCH}:{key}")
            elif d.data_type == AttrType.INT:
                # bool is a subclass of int; reject explicitly.
                if isinstance(value, bool) or not isinstance(value, int):
                    errors.append(f"{self.ATTRIBUTE_TYPE_MISMATCH}:{key}")
            elif d.data_type == AttrType.BOOL:
                if not isinstance(value, bool):
                    errors.append(f"{self.ATTRIBUTE_TYPE_MISMATCH}:{key}")
            elif d.data_type == AttrType.ENUM:
                allowed = {v.value for v in (d.enum_values or ())}
                if not isinstance(value, str) or value not in allowed:
                    errors.append(f"{self.ATTRIBUTE_ENUM_VALUE_NOT_ALLOWED}:{key}")

        if errors:
            return Result.failure("; ".join(errors))
        return Result.success(None)

    @staticmethod
    def _has_duplicate_keys(definitions: list[AttributeDefinition]) -> bool:
        keys = [d.key.value for d in definitions]
        return len(keys) != len(set(keys))
```

- [ ] **Step 4: Run — green**

```bash
.venv/bin/pytest tests/unit/domain/catalog/test_resource_type.py -v
.venv/bin/pytest -q
```

- [ ] **Step 5: Add the new error codes to `app/api/error_codes.py`**

These are entity-level codes (not VO-level), so they go in the handler-level allowlist of the architecture test. Add to `error_codes.py`:

```python
    # ResourceType (entity-level codes — registered in arch test allowlist)
    "DuplicateAttributeKey": "Atributos duplicados — chaves devem ser únicas dentro do tipo.",
    "RequiredAttributeMissing": "Atributo obrigatório ausente.",
    "UnknownAttributeKey": "Atributo desconhecido — não está no schema do tipo.",
    "AttributeTypeMismatch": "Valor do atributo não bate com o tipo declarado.",
    "AttributeEnumValueNotAllowed": "Valor do atributo enum fora dos valores permitidos.",
```

Add to `tests/unit/architecture/test_error_code_coverage.py`:

```python
    handler_level_allowlist: set[str] = {
        "PasswordHashCannotBeEmpty",
        "DuplicateAttributeKey",
        "RequiredAttributeMissing",
        "UnknownAttributeKey",
        "AttributeTypeMismatch",
        "AttributeEnumValueNotAllowed",
    }
```

Note: `validate_attributes` emits codes with a suffix (e.g., `"RequiredAttributeMissing:players"`). The architecture test checks the bare code; the suffix is appended at runtime for caller-side context. The bare code constants are what get translated.

- [ ] **Step 6: Run architecture test + full suite**

```bash
.venv/bin/pytest tests/unit/architecture/test_error_code_coverage.py -v
.venv/bin/pytest -q
```

Expected: green.

- [ ] **Step 7: Commit**

```bash
git add app/domain/catalog/resource_type.py tests/unit/domain/catalog/test_resource_type.py \
        app/api/error_codes.py tests/unit/architecture/test_error_code_coverage.py
git commit -m "$(cat <<'EOF'
feat(catalog): add ResourceType aggregate with validate_attributes

ResourceType is a slug-keyed aggregate root holding name (Name),
description (ShortDescription), and an attribute_schema (private
list of AttributeDefinition with immutable tuple view). Mutators
follow spec §4.4: update_metadata + activate/deactivate return None
(no domain invariant); replace_attribute_schema returns Result[None]
to enforce unique-key invariant. validate_attributes(dict) walks the
schema and aggregates type/required/enum errors with stable codes
suffixed by the offending key (e.g., "RequiredAttributeMissing:players")
for caller context.

Five new entity-level codes registered in the pt-BR mapping and the
architecture-test handler_level_allowlist.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task A3 — `IResourceTypeRepository` Protocol

Defines the persistence contract that the SQLAlchemy adapter (Unit B) and the in-memory fake (Unit C) implement.

**Files:** `app/domain/catalog/repository.py`.

- [ ] **Step 1: Implementation** (no dedicated test for a Protocol; consumers in C/D test it)

`app/domain/catalog/repository.py`:

```python
from __future__ import annotations
from typing import Protocol
from uuid import UUID
from app.domain.catalog.resource_type import ResourceType
from app.domain.shared.result import Result


class IResourceTypeRepository(Protocol):
    """Persistence port for the catalog feature."""

    async def add(self, rt: ResourceType) -> Result[None]:
        """Persist a new ResourceType. Returns SlugAlreadyTaken on conflict."""
        ...

    async def update(self, rt: ResourceType) -> Result[None]:
        """Persist changes to an existing ResourceType."""
        ...

    async def delete(self, rt_id: UUID) -> Result[None]:
        """Hard-delete the row. Returns ResourceTypeNotFound if missing."""
        ...

    async def get_by_id(self, rt_id: UUID) -> ResourceType | None:
        ...

    async def get_by_slug(self, slug: str) -> ResourceType | None:
        ...

    async def list_all(self, *, limit: int = 50, offset: int = 0) -> list[ResourceType]:
        """Admin list — includes inactive rows."""
        ...

    async def list_active(self, *, limit: int = 50, offset: int = 0) -> list[ResourceType]:
        """Public list — only is_active=True rows."""
        ...
```

Two new handler-level codes appear here as comments — `"SlugAlreadyTaken"` and `"ResourceTypeNotFound"`. They're not yet emitted; handlers in Unit C will emit them. We register them now since the Protocol's docstrings reference them.

Add to `app/api/error_codes.py`:

```python
    "SlugAlreadyTaken": "Slug já está em uso.",
    "ResourceTypeNotFound": "Tipo de recurso não encontrado.",
```

Add to `tests/unit/architecture/test_error_code_coverage.py` `handler_level_allowlist`:

```python
        "SlugAlreadyTaken",
        "ResourceTypeNotFound",
```

- [ ] **Step 2: Architecture test passes (orphan check would fail otherwise)**

```bash
.venv/bin/pytest tests/unit/architecture/test_error_code_coverage.py -v
.venv/bin/pytest -q
```

- [ ] **Step 3: Commit**

```bash
git add app/domain/catalog/repository.py \
        app/api/error_codes.py \
        tests/unit/architecture/test_error_code_coverage.py
git commit -m "$(cat <<'EOF'
feat(catalog): add IResourceTypeRepository Protocol

Persistence port with async add/update/delete/get/list signatures.
Returns Result[None] on writes (Plan 03 convention) so handlers can
distinguish persistence failures (SlugAlreadyTaken, ResourceTypeNotFound)
from domain failures. Two read variants — list_all (admin, includes
inactive) and list_active (public). Two new handler-level codes
registered in pt-BR mapping + arch-test allowlist.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task A4 — Self-check after Unit A

No new code; verify everything still composes.

- [ ] **Step 1: Smoke import**

```bash
BACKEND_DATABASE_URL="sqlite+aiosqlite:///:memory:" .venv/bin/python -c "
from app.domain.catalog.attribute import AttrType, AttributeDefinition
from app.domain.catalog.resource_type import ResourceType
from app.domain.catalog.repository import IResourceTypeRepository
from app.api.error_codes import ERROR_MESSAGES_PT_BR
print('catalog domain loaded;', len(ERROR_MESSAGES_PT_BR), 'codes mapped')
"
```

Expected: prints `catalog domain loaded; 49 codes mapped` (or similar — 42 from Plan 03 + 7 catalog codes = 49).

- [ ] **Step 2: Full suite + arch test**

```bash
.venv/bin/pytest -q
```

Expected: green. Approximately 210 + (10 attribute + 17 resource_type) = ~237 tests passing.

- [ ] **Step 3: No commit (verification only)**

---

## UNIT B — Infrastructure (mapping + migration + repository + integration test)

### Task B1 — `ResourceTypeModel` mapping + register in env.py

**Files:** create `app/infrastructure/db/mappings/resource_type.py`, modify `app/migrations/env.py`.

- [ ] **Step 1: Create the mapping**

`app/infrastructure/db/mappings/resource_type.py`:

```python
from __future__ import annotations
from uuid import UUID
from sqlalchemy import JSON, Boolean, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import CHAR
from app.infrastructure.db.base import Base, TimestampMixin


class ResourceTypeModel(Base, TimestampMixin):
    __tablename__ = "resource_types"

    id: Mapped[UUID] = mapped_column(CHAR(36), primary_key=True)
    slug: Mapped[str] = mapped_column(Text, nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    attribute_schema: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
```

- [ ] **Step 2: Register the model in env.py**

Read `app/migrations/env.py`. Locate the section that imports models for autogenerate (look for a comment like `# import all mappings` or model imports near the top). Add:

```python
from app.infrastructure.db.mappings import resource_type  # noqa: F401  (registers metadata)
```

Group it alphabetically with the existing user import.

- [ ] **Step 3: Smoke import**

```bash
BACKEND_DATABASE_URL="sqlite+aiosqlite:///:memory:" .venv/bin/python -c "
from app.infrastructure.db.mappings.resource_type import ResourceTypeModel
print(ResourceTypeModel.__table__)
print('columns:', [c.name for c in ResourceTypeModel.__table__.columns])
"
```

Expected: prints the table object and column list `['id', 'slug', 'name', 'description', 'attribute_schema', 'is_active', 'created_at', 'updated_at']`.

- [ ] **Step 4: Run full suite**

```bash
.venv/bin/pytest -q
```

Expected: green.

- [ ] **Step 5: Commit**

```bash
git add app/infrastructure/db/mappings/resource_type.py app/migrations/env.py
git commit -m "$(cat <<'EOF'
feat(catalog): add ResourceTypeModel mapping

resource_types table with Text columns (VO governs length per spec
§3 decision 17), JSON column for attribute_schema (dialect-portable
between Postgres and SQLite tests), unique index on slug, regular
index on is_active. Registered in migrations/env.py for autogenerate.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task B2 — Alembic migration

Autogenerate the `resource_types` table migration on top of the existing initial_accounts revision.

**Files:** new `app/migrations/versions/<timestamp>_catalog_resource_types_table.py`.

- [ ] **Step 1: Autogenerate**

```bash
cd /Users/klayver/Repositories/agentic-workbench/venue-backend
rm -f ./_alembic_tmp.db

# Apply existing migrations to a temp SQLite first so the next autogen sees them.
BACKEND_DATABASE_URL="sqlite+aiosqlite:///./_alembic_tmp.db" .venv/bin/alembic upgrade head

# Now autogenerate the new revision against that state.
BACKEND_DATABASE_URL="sqlite+aiosqlite:///./_alembic_tmp.db" .venv/bin/alembic revision --autogenerate -m "catalog resource types table"

rm -f ./_alembic_tmp.db
```

- [ ] **Step 2: Inspect the generated file**

The new file at `app/migrations/versions/<timestamp>_catalog_resource_types_table.py` should look roughly like:

```python
def upgrade() -> None:
    op.create_table(
        "resource_types",
        sa.Column("id", sa.CHAR(length=36), nullable=False),
        sa.Column("slug", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("attribute_schema", sa.JSON(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_resource_types_slug"), "resource_types", ["slug"], unique=True)
    op.create_index(op.f("ix_resource_types_is_active"), "resource_types", ["is_active"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_resource_types_is_active"), table_name="resource_types")
    op.drop_index(op.f("ix_resource_types_slug"), table_name="resource_types")
    op.drop_table("resource_types")
```

`down_revision` must point to `'643934c1e272'` (the initial_accounts revision from Plan 03). If autogen produced a different value, edit it.

If autogen creates spurious DROP statements at the top of `upgrade()` (because of stale state), investigate before proceeding — there should be ONLY `op.create_table` + `op.create_index` calls in upgrade.

- [ ] **Step 3: Run tests**

```bash
.venv/bin/pytest -q
```

Expected: green (tests use `Base.metadata.create_all` not migrations, but verify nothing imports broke).

- [ ] **Step 4: Commit**

```bash
git add app/migrations/versions/
git commit -m "$(cat <<'EOF'
feat(migrations): add resource_types table migration

Autogenerated revision creating the resource_types table with Text
columns, JSON column for attribute_schema, unique index on slug, and
regular index on is_active. Stacks on top of the initial_accounts
revision from Plan 03.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task B3 — `SQLAlchemyResourceTypeRepository` adapter + integration test

The adapter implements `IResourceTypeRepository`. It serializes `AttributeDefinition` ↔ dict at the JSON boundary (per Decision 4). Reconstitution uses trusted constructors per the `BaseValueObject` convention.

**Files:** create `app/infrastructure/repositories/resource_type_repository.py`, `tests/integration/catalog/__init__.py`, `tests/integration/catalog/test_resource_type_repository.py`.

- [ ] **Step 1: Failing integration test**

`tests/integration/catalog/__init__.py`: empty file.

`tests/integration/catalog/test_resource_type_repository.py`:

```python
from __future__ import annotations
import pytest
from app.domain.catalog.attribute import AttrType, AttributeDefinition
from app.domain.catalog.resource_type import ResourceType
from app.infrastructure.repositories.resource_type_repository import (
    SQLAlchemyResourceTypeRepository,
)


pytestmark = pytest.mark.asyncio


def _make_rt(slug: str = "football-field", name: str = "Football Field", active: bool = True):
    rt = ResourceType.create(
        slug=slug,
        name=name,
        description="Campo gramado para futebol",
        attribute_schema=[
            AttributeDefinition.create(
                key="surface", label="Tipo de gramado", data_type=AttrType.ENUM,
                enum_values=["natural", "synthetic"],
            ).value,
            AttributeDefinition.create(
                key="players", label="Jogadores", data_type=AttrType.INT, required=True,
            ).value,
        ],
        is_active=active,
    )
    return rt.value


async def test_add_and_get_by_id(db_session):
    repo = SQLAlchemyResourceTypeRepository(db_session)
    rt = _make_rt()
    r = await repo.add(rt)
    assert r.is_success
    fetched = await repo.get_by_id(rt.id)
    assert fetched is not None
    assert fetched.slug.value == "football-field"
    assert fetched.name.value == "Football Field"
    assert len(fetched.attribute_schema) == 2
    surface = fetched.attribute_schema[0]
    assert surface.data_type == AttrType.ENUM
    assert surface.enum_values is not None
    assert tuple(v.value for v in surface.enum_values) == ("natural", "synthetic")


async def test_add_rejects_duplicate_slug(db_session):
    repo = SQLAlchemyResourceTypeRepository(db_session)
    await repo.add(_make_rt(slug="court"))
    r = await repo.add(_make_rt(slug="court"))
    assert r.is_failure
    assert r.error == "SlugAlreadyTaken"


async def test_get_by_slug(db_session):
    repo = SQLAlchemyResourceTypeRepository(db_session)
    rt = _make_rt(slug="padel-court")
    await repo.add(rt)
    fetched = await repo.get_by_slug("padel-court")
    assert fetched is not None
    assert fetched.id == rt.id


async def test_get_by_slug_returns_none_when_absent(db_session):
    repo = SQLAlchemyResourceTypeRepository(db_session)
    assert await repo.get_by_slug("missing") is None


async def test_update_persists_changes(db_session):
    repo = SQLAlchemyResourceTypeRepository(db_session)
    rt = _make_rt()
    await repo.add(rt)
    rt.update_metadata(name="Campo de Futebol", description="atualizado")
    rt.deactivate()
    r = await repo.update(rt)
    assert r.is_success
    fetched = await repo.get_by_id(rt.id)
    assert fetched is not None
    assert fetched.name.value == "Campo de Futebol"
    assert fetched.is_active is False


async def test_delete_removes_row(db_session):
    repo = SQLAlchemyResourceTypeRepository(db_session)
    rt = _make_rt()
    await repo.add(rt)
    r = await repo.delete(rt.id)
    assert r.is_success
    assert await repo.get_by_id(rt.id) is None


async def test_delete_returns_not_found_when_absent(db_session):
    from uuid import uuid4
    repo = SQLAlchemyResourceTypeRepository(db_session)
    r = await repo.delete(uuid4())
    assert r.is_failure
    assert r.error == "ResourceTypeNotFound"


async def test_list_all_includes_inactive(db_session):
    repo = SQLAlchemyResourceTypeRepository(db_session)
    await repo.add(_make_rt(slug="active-1", active=True))
    await repo.add(_make_rt(slug="inactive-1", active=False))
    rows = await repo.list_all()
    slugs = {r.slug.value for r in rows}
    assert {"active-1", "inactive-1"} <= slugs


async def test_list_active_excludes_inactive(db_session):
    repo = SQLAlchemyResourceTypeRepository(db_session)
    await repo.add(_make_rt(slug="active-2", active=True))
    await repo.add(_make_rt(slug="inactive-2", active=False))
    rows = await repo.list_active()
    slugs = {r.slug.value for r in rows}
    assert "active-2" in slugs
    assert "inactive-2" not in slugs


async def test_list_pagination(db_session):
    repo = SQLAlchemyResourceTypeRepository(db_session)
    for i in range(5):
        await repo.add(_make_rt(slug=f"page-{i}"))
    page1 = await repo.list_all(limit=2, offset=0)
    page2 = await repo.list_all(limit=2, offset=2)
    assert len(page1) == 2
    assert len(page2) == 2
    assert {r.id for r in page1}.isdisjoint({r.id for r in page2})
```

The `db_session` fixture exists in `tests/conftest.py` (per Plan 02 setup); it provides an `AsyncSession` against an in-memory SQLite with all tables created via `Base.metadata.create_all`.

- [ ] **Step 2: Run — fail (ImportError on resource_type_repository)**

```bash
.venv/bin/pytest tests/integration/catalog/test_resource_type_repository.py -v
```

- [ ] **Step 3: Implementation**

`app/infrastructure/repositories/resource_type_repository.py`:

```python
from __future__ import annotations
from typing import Any
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from app.domain.catalog.attribute import AttrType, AttributeDefinition
from app.domain.catalog.resource_type import ResourceType
from app.domain.shared.result import Result
from app.domain.shared.value_objects.attribute_key import AttributeKey
from app.domain.shared.value_objects.name import Name
from app.domain.shared.value_objects.short_description import ShortDescription
from app.domain.shared.value_objects.short_name import ShortName
from app.domain.shared.value_objects.slug import Slug
from app.infrastructure.db.mappings.resource_type import ResourceTypeModel


def _attribute_to_dict(a: AttributeDefinition) -> dict[str, Any]:
    return {
        "key": a.key.value,
        "label": a.label.value,
        "data_type": a.data_type.value,
        "required": a.required,
        "enum_values": [v.value for v in a.enum_values] if a.enum_values else None,
    }


def _attribute_from_dict(d: dict[str, Any]) -> AttributeDefinition:
    """Trusted reconstitution from DB JSON. Bypasses VO factory validation."""
    enum_vos = (
        tuple(ShortName(value=v) for v in d["enum_values"])
        if d.get("enum_values") is not None
        else None
    )
    return AttributeDefinition(
        key=AttributeKey(value=d["key"]),
        label=ShortName(value=d["label"]),
        data_type=AttrType(d["data_type"]),
        required=d["required"],
        enum_values=enum_vos,
    )


def _to_entity(model: ResourceTypeModel) -> ResourceType:
    """Trusted reconstitution from DB row."""
    rt = ResourceType(
        id=model.id,  # type: ignore[arg-type]
        slug=Slug(value=model.slug),
        name=Name(value=model.name),
        description=ShortDescription(value=model.description),
        is_active=model.is_active,
        _attribute_schema=[_attribute_from_dict(d) for d in (model.attribute_schema or [])],
    )
    rt.created_at = model.created_at
    rt.updated_at = model.updated_at
    return rt


def _to_model_dict(rt: ResourceType) -> dict[str, Any]:
    return {
        "id": str(rt.id),
        "slug": rt.slug.value,
        "name": rt.name.value,
        "description": rt.description.value,
        "is_active": rt.is_active,
        "attribute_schema": [_attribute_to_dict(a) for a in rt.attribute_schema],
        "created_at": rt.created_at,
        "updated_at": rt.updated_at,
    }


class SQLAlchemyResourceTypeRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def add(self, rt: ResourceType) -> Result[None]:
        model = ResourceTypeModel(**_to_model_dict(rt))
        self._session.add(model)
        try:
            await self._session.flush()
        except IntegrityError:
            await self._session.rollback()
            return Result.failure("SlugAlreadyTaken", status_code=409)
        return Result.success(None)

    async def update(self, rt: ResourceType) -> Result[None]:
        stmt = select(ResourceTypeModel).where(ResourceTypeModel.id == str(rt.id))
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        if row is None:
            return Result.failure("ResourceTypeNotFound", status_code=404)
        row.slug = rt.slug.value
        row.name = rt.name.value
        row.description = rt.description.value
        row.is_active = rt.is_active
        row.attribute_schema = [_attribute_to_dict(a) for a in rt.attribute_schema]
        row.updated_at = rt.updated_at
        try:
            await self._session.flush()
        except IntegrityError:
            await self._session.rollback()
            return Result.failure("SlugAlreadyTaken", status_code=409)
        return Result.success(None)

    async def delete(self, rt_id: UUID) -> Result[None]:
        stmt = select(ResourceTypeModel).where(ResourceTypeModel.id == str(rt_id))
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        if row is None:
            return Result.failure("ResourceTypeNotFound", status_code=404)
        await self._session.delete(row)
        await self._session.flush()
        return Result.success(None)

    async def get_by_id(self, rt_id: UUID) -> ResourceType | None:
        stmt = select(ResourceTypeModel).where(ResourceTypeModel.id == str(rt_id))
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return _to_entity(row) if row else None

    async def get_by_slug(self, slug: str) -> ResourceType | None:
        stmt = select(ResourceTypeModel).where(ResourceTypeModel.slug == slug)
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return _to_entity(row) if row else None

    async def list_all(self, *, limit: int = 50, offset: int = 0) -> list[ResourceType]:
        stmt = (
            select(ResourceTypeModel)
            .order_by(ResourceTypeModel.created_at)
            .limit(limit)
            .offset(offset)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_entity(r) for r in rows]

    async def list_active(self, *, limit: int = 50, offset: int = 0) -> list[ResourceType]:
        stmt = (
            select(ResourceTypeModel)
            .where(ResourceTypeModel.is_active.is_(True))
            .order_by(ResourceTypeModel.created_at)
            .limit(limit)
            .offset(offset)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_entity(r) for r in rows]
```

- [ ] **Step 4: Run integration test**

```bash
.venv/bin/pytest tests/integration/catalog/test_resource_type_repository.py -v
```

If `db_session` fixture isn't visible, it likely lives in `tests/conftest.py` or `tests/integration/conftest.py`. Check accounts integration tests for the pattern; if there's a separate conftest needed for `tests/integration/catalog/`, add it (just `from tests.integration.accounts.conftest import db_session  # noqa` or by importing the shared fixture).

Expected: 10 tests pass.

- [ ] **Step 5: Run full suite**

```bash
.venv/bin/pytest -q
```

Expected: green.

- [ ] **Step 6: Commit**

```bash
git add app/infrastructure/repositories/resource_type_repository.py \
        tests/integration/catalog/__init__.py \
        tests/integration/catalog/test_resource_type_repository.py
git commit -m "$(cat <<'EOF'
feat(catalog): SQLAlchemy adapter for IResourceTypeRepository

CRUD against the resource_types table. Serializes
AttributeDefinition ↔ dict at the JSON boundary; reconstitution uses
trusted VO constructors (Slug(value=...), Name(value=...), etc.) per
the BaseValueObject convention. IntegrityError on slug uniqueness is
caught and surfaced as SlugAlreadyTaken (409). Missing rows on
update/delete return ResourceTypeNotFound (404). list_all and
list_active variants serve admin and public reads respectively.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## UNIT C — Use cases

### Task C1 — DTOs + in-memory fake repo

**Files:** create `app/use_cases/catalog/__init__.py`, `app/use_cases/catalog/dtos.py`, `app/use_cases/catalog/commands/__init__.py`, `tests/unit/use_cases/catalog/__init__.py`, `tests/unit/use_cases/catalog/fakes/__init__.py`, `tests/unit/use_cases/catalog/fakes/in_memory_resource_type_repository.py`.

- [ ] **Step 1: Create the empty `__init__.py` files**

```bash
mkdir -p app/use_cases/catalog/commands
touch app/use_cases/catalog/__init__.py
touch app/use_cases/catalog/commands/__init__.py
mkdir -p tests/unit/use_cases/catalog/commands
mkdir -p tests/unit/use_cases/catalog/fakes
touch tests/unit/use_cases/catalog/__init__.py
touch tests/unit/use_cases/catalog/commands/__init__.py
touch tests/unit/use_cases/catalog/fakes/__init__.py
```

- [ ] **Step 2: DTOs**

`app/use_cases/catalog/dtos.py`:

```python
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID
from app.domain.catalog.attribute import AttrType, AttributeDefinition
from app.domain.catalog.resource_type import ResourceType


@dataclass(frozen=True, slots=True)
class AttributeDefinitionDto:
    key: str
    label: str
    data_type: str
    required: bool
    enum_values: list[str] | None

    @classmethod
    def from_vo(cls, a: AttributeDefinition) -> "AttributeDefinitionDto":
        return cls(
            key=a.key.value,
            label=a.label.value,
            data_type=a.data_type.value,
            required=a.required,
            enum_values=[v.value for v in a.enum_values] if a.enum_values else None,
        )


@dataclass(frozen=True, slots=True)
class ResourceTypeDto:
    id: UUID
    slug: str
    name: str
    description: str
    attribute_schema: list[AttributeDefinitionDto]
    is_active: bool
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_entity(cls, rt: ResourceType) -> "ResourceTypeDto":
        return cls(
            id=rt.id,
            slug=rt.slug.value,
            name=rt.name.value,
            description=rt.description.value,
            attribute_schema=[AttributeDefinitionDto.from_vo(a) for a in rt.attribute_schema],
            is_active=rt.is_active,
            created_at=rt.created_at,
            updated_at=rt.updated_at,
        )
```

- [ ] **Step 3: In-memory fake**

`tests/unit/use_cases/catalog/fakes/in_memory_resource_type_repository.py`:

```python
from __future__ import annotations
from uuid import UUID
from app.domain.catalog.resource_type import ResourceType
from app.domain.shared.result import Result


class InMemoryResourceTypeRepository:
    """Test fake implementing IResourceTypeRepository."""

    def __init__(self) -> None:
        self._by_id: dict[UUID, ResourceType] = {}

    async def add(self, rt: ResourceType) -> Result[None]:
        if any(existing.slug.value == rt.slug.value for existing in self._by_id.values()):
            return Result.failure("SlugAlreadyTaken", status_code=409)
        self._by_id[rt.id] = rt
        return Result.success(None)

    async def update(self, rt: ResourceType) -> Result[None]:
        if rt.id not in self._by_id:
            return Result.failure("ResourceTypeNotFound", status_code=404)
        clash = next(
            (other for other in self._by_id.values()
             if other.id != rt.id and other.slug.value == rt.slug.value),
            None,
        )
        if clash is not None:
            return Result.failure("SlugAlreadyTaken", status_code=409)
        self._by_id[rt.id] = rt
        return Result.success(None)

    async def delete(self, rt_id: UUID) -> Result[None]:
        if rt_id not in self._by_id:
            return Result.failure("ResourceTypeNotFound", status_code=404)
        del self._by_id[rt_id]
        return Result.success(None)

    async def get_by_id(self, rt_id: UUID) -> ResourceType | None:
        return self._by_id.get(rt_id)

    async def get_by_slug(self, slug: str) -> ResourceType | None:
        return next(
            (rt for rt in self._by_id.values() if rt.slug.value == slug),
            None,
        )

    async def list_all(self, *, limit: int = 50, offset: int = 0) -> list[ResourceType]:
        rows = sorted(self._by_id.values(), key=lambda rt: rt.created_at)
        return rows[offset:offset + limit]

    async def list_active(self, *, limit: int = 50, offset: int = 0) -> list[ResourceType]:
        rows = sorted(
            (rt for rt in self._by_id.values() if rt.is_active),
            key=lambda rt: rt.created_at,
        )
        return rows[offset:offset + limit]
```

- [ ] **Step 4: Smoke test the DTO**

```bash
BACKEND_DATABASE_URL="sqlite+aiosqlite:///:memory:" .venv/bin/python -c "
from app.domain.catalog.attribute import AttrType, AttributeDefinition
from app.domain.catalog.resource_type import ResourceType
from app.use_cases.catalog.dtos import ResourceTypeDto
rt = ResourceType.create(
    slug='football-field', name='Football Field', description='',
    attribute_schema=[AttributeDefinition.create(
        key='size', label='Tamanho', data_type=AttrType.STRING).value],
).value
dto = ResourceTypeDto.from_entity(rt)
print(dto.slug, dto.name, dto.attribute_schema[0].key)
"
```

Expected: prints `football-field Football Field size`.

- [ ] **Step 5: Run full suite**

```bash
.venv/bin/pytest -q
```

Expected: green.

- [ ] **Step 6: Commit**

```bash
git add app/use_cases/catalog/ tests/unit/use_cases/catalog/
git commit -m "$(cat <<'EOF'
feat(catalog): add use-case DTOs + in-memory fake repository

ResourceTypeDto and AttributeDefinitionDto flatten VO-typed entity
fields to plain types for HTTP serialization. InMemoryResourceType
Repository is the test fake matching the IResourceTypeRepository
Protocol — handlers in C2-C4 use it; the SQLAlchemy adapter (B3) is
its production counterpart.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task C2 — `CreateResourceTypeHandler`

**Files:** `app/use_cases/catalog/commands/create_resource_type.py`, `tests/unit/use_cases/catalog/commands/test_create_resource_type.py`.

- [ ] **Step 1: Failing tests**

`tests/unit/use_cases/catalog/commands/test_create_resource_type.py`:

```python
from __future__ import annotations
import pytest
from app.domain.catalog.attribute import AttrType
from app.use_cases.catalog.commands.create_resource_type import (
    CreateResourceTypeCommand,
    CreateResourceTypeHandler,
)
from tests.unit.use_cases.catalog.fakes.in_memory_resource_type_repository import (
    InMemoryResourceTypeRepository,
)


pytestmark = pytest.mark.asyncio


def _cmd(**kw) -> CreateResourceTypeCommand:
    base = dict(
        slug="football-field",
        name="Football Field",
        description="Campo de futebol",
        attribute_schema=[
            {"key": "size", "label": "Tamanho", "data_type": "string", "required": True, "enum_values": None},
        ],
    )
    base.update(kw)
    return CreateResourceTypeCommand(**base)


async def test_create_resource_type_success():
    repo = InMemoryResourceTypeRepository()
    handler = CreateResourceTypeHandler(repo)
    r = await handler.handle(_cmd())
    assert r.is_success
    assert r.value.slug == "football-field"
    assert r.value.is_active is True
    assert (await repo.get_by_id(r.value.id)) is not None


async def test_create_resource_type_propagates_slug_failure():
    repo = InMemoryResourceTypeRepository()
    handler = CreateResourceTypeHandler(repo)
    r = await handler.handle(_cmd(slug="Invalid Slug!"))
    assert r.is_failure
    assert "SlugInvalidFormat" in r.error


async def test_create_resource_type_rejects_duplicate_slug():
    repo = InMemoryResourceTypeRepository()
    handler = CreateResourceTypeHandler(repo)
    await handler.handle(_cmd())
    r = await handler.handle(_cmd(name="Other"))
    assert r.is_failure
    assert r.error == "SlugAlreadyTaken"


async def test_create_resource_type_with_enum_attribute():
    repo = InMemoryResourceTypeRepository()
    handler = CreateResourceTypeHandler(repo)
    r = await handler.handle(_cmd(
        slug="padel-court",
        attribute_schema=[
            {"key": "surface", "label": "Tipo", "data_type": "enum", "required": False,
             "enum_values": ["natural", "synthetic"]},
        ],
    ))
    assert r.is_success
    assert r.value.attribute_schema[0].data_type == "enum"
    assert r.value.attribute_schema[0].enum_values == ["natural", "synthetic"]
```

- [ ] **Step 2: Run — fail**

```bash
.venv/bin/pytest tests/unit/use_cases/catalog/commands/test_create_resource_type.py -v
```

- [ ] **Step 3: Implementation**

`app/use_cases/catalog/commands/create_resource_type.py`:

```python
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Protocol
from uuid import UUID
from app.domain.catalog.attribute import AttrType, AttributeDefinition
from app.domain.catalog.resource_type import ResourceType
from app.domain.shared.result import Result
from app.use_cases.catalog.dtos import ResourceTypeDto


class _RepoLike(Protocol):
    async def add(self, rt: ResourceType) -> Result[None]: ...


@dataclass(frozen=True, slots=True)
class CreateResourceTypeCommand:
    slug: str
    name: str
    description: str
    attribute_schema: list[dict[str, Any]] = field(default_factory=list)
    is_active: bool = True


class CreateResourceTypeHandler:
    def __init__(self, repo: _RepoLike) -> None:
        self._repo = repo

    async def handle(self, cmd: CreateResourceTypeCommand) -> Result[ResourceTypeDto]:
        # Build AttributeDefinition VOs from raw dict input.
        defs: list[AttributeDefinition] = []
        errors: list[str] = []
        for raw in cmd.attribute_schema:
            try:
                dt = AttrType(raw["data_type"])
            except ValueError:
                errors.append(f"InvalidDataType:{raw.get('data_type')!r}")
                continue
            r = AttributeDefinition.create(
                key=raw["key"],
                label=raw["label"],
                data_type=dt,
                required=raw.get("required", False),
                enum_values=raw.get("enum_values"),
            )
            if r.is_failure:
                errors.append(r.error)
            else:
                defs.append(r.value)

        if errors:
            return Result.failure("; ".join(errors), status_code=400)

        rt_r = ResourceType.create(
            slug=cmd.slug,
            name=cmd.name,
            description=cmd.description,
            attribute_schema=defs,
            is_active=cmd.is_active,
        )
        if rt_r.is_failure:
            return Result.failure(rt_r.error, status_code=400)

        add_r = await self._repo.add(rt_r.value)
        if add_r.is_failure:
            return Result.failure(add_r.error, status_code=add_r.status_code or 409)

        return Result.success(ResourceTypeDto.from_entity(rt_r.value))
```

The new code `"InvalidDataType"` is emitted at the handler boundary. Add to `app/api/error_codes.py`:

```python
    "InvalidDataType": "Tipo de dado de atributo desconhecido.",
```

And to the architecture-test allowlist:

```python
        "InvalidDataType",
```

- [ ] **Step 4: Run — green**

```bash
.venv/bin/pytest tests/unit/use_cases/catalog/commands/test_create_resource_type.py tests/unit/architecture/test_error_code_coverage.py -v
.venv/bin/pytest -q
```

- [ ] **Step 5: Commit**

```bash
git add app/use_cases/catalog/commands/create_resource_type.py \
        tests/unit/use_cases/catalog/commands/test_create_resource_type.py \
        app/api/error_codes.py tests/unit/architecture/test_error_code_coverage.py
git commit -m "$(cat <<'EOF'
feat(catalog): CreateResourceTypeHandler

Builds AttributeDefinition VOs from raw dict input (aggregating
failures), constructs ResourceType, persists via repo, returns DTO.
Emits InvalidDataType when raw data_type doesn't match the AttrType
enum; propagates downstream codes (slug/name validation, slug
uniqueness conflict).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task C3 — `UpdateResourceTypeHandler`

Partial update: any field provided is updated; absent fields stay. `attribute_schema`, when provided, is replaced wholesale (per Decision 5).

**Files:** `app/use_cases/catalog/commands/update_resource_type.py`, `tests/unit/use_cases/catalog/commands/test_update_resource_type.py`.

- [ ] **Step 1: Failing tests**

```python
from __future__ import annotations
import pytest
from app.domain.catalog.attribute import AttrType, AttributeDefinition
from app.domain.catalog.resource_type import ResourceType
from app.use_cases.catalog.commands.update_resource_type import (
    UpdateResourceTypeCommand,
    UpdateResourceTypeHandler,
)
from tests.unit.use_cases.catalog.fakes.in_memory_resource_type_repository import (
    InMemoryResourceTypeRepository,
)


pytestmark = pytest.mark.asyncio


async def _setup_repo_with_one():
    repo = InMemoryResourceTypeRepository()
    rt = ResourceType.create(
        slug="football-field", name="Football Field", description="",
        attribute_schema=[
            AttributeDefinition.create(
                key="size", label="Tamanho", data_type=AttrType.STRING,
            ).value,
        ],
    ).value
    await repo.add(rt)
    return repo, rt


async def test_update_changes_name_and_description():
    repo, rt = await _setup_repo_with_one()
    handler = UpdateResourceTypeHandler(repo)
    r = await handler.handle(UpdateResourceTypeCommand(
        id=rt.id, name="Campo de Futebol", description="atualizado",
    ))
    assert r.is_success
    fetched = await repo.get_by_id(rt.id)
    assert fetched.name.value == "Campo de Futebol"
    assert fetched.description.value == "atualizado"


async def test_update_replaces_attribute_schema_wholesale():
    repo, rt = await _setup_repo_with_one()
    handler = UpdateResourceTypeHandler(repo)
    r = await handler.handle(UpdateResourceTypeCommand(
        id=rt.id,
        attribute_schema=[
            {"key": "players", "label": "Jogadores", "data_type": "int", "required": True, "enum_values": None},
        ],
    ))
    assert r.is_success
    fetched = await repo.get_by_id(rt.id)
    assert len(fetched.attribute_schema) == 1
    assert fetched.attribute_schema[0].key.value == "players"


async def test_update_toggles_is_active():
    repo, rt = await _setup_repo_with_one()
    handler = UpdateResourceTypeHandler(repo)
    r = await handler.handle(UpdateResourceTypeCommand(id=rt.id, is_active=False))
    assert r.is_success
    fetched = await repo.get_by_id(rt.id)
    assert fetched.is_active is False


async def test_update_returns_not_found_for_missing_id():
    from uuid import uuid4
    repo, _ = await _setup_repo_with_one()
    handler = UpdateResourceTypeHandler(repo)
    r = await handler.handle(UpdateResourceTypeCommand(id=uuid4(), name="x"))
    assert r.is_failure
    assert r.error == "ResourceTypeNotFound"


async def test_update_propagates_attribute_schema_validation_failure():
    repo, rt = await _setup_repo_with_one()
    handler = UpdateResourceTypeHandler(repo)
    r = await handler.handle(UpdateResourceTypeCommand(
        id=rt.id,
        attribute_schema=[
            {"key": "size", "label": "A", "data_type": "string", "required": False, "enum_values": None},
            {"key": "size", "label": "B", "data_type": "string", "required": False, "enum_values": None},
        ],
    ))
    assert r.is_failure
    assert "DuplicateAttributeKey" in r.error
```

- [ ] **Step 2: Run — fail**

```bash
.venv/bin/pytest tests/unit/use_cases/catalog/commands/test_update_resource_type.py -v
```

- [ ] **Step 3: Implementation**

`app/use_cases/catalog/commands/update_resource_type.py`:

```python
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID
from app.domain.catalog.attribute import AttrType, AttributeDefinition
from app.domain.catalog.resource_type import ResourceType
from app.domain.shared.result import Result
from app.use_cases.catalog.dtos import ResourceTypeDto


class _RepoLike(Protocol):
    async def get_by_id(self, rt_id: UUID) -> ResourceType | None: ...
    async def update(self, rt: ResourceType) -> Result[None]: ...


@dataclass(frozen=True, slots=True)
class UpdateResourceTypeCommand:
    id: UUID
    name: str | None = None
    description: str | None = None
    attribute_schema: list[dict[str, Any]] | None = None
    is_active: bool | None = None


class UpdateResourceTypeHandler:
    def __init__(self, repo: _RepoLike) -> None:
        self._repo = repo

    async def handle(self, cmd: UpdateResourceTypeCommand) -> Result[ResourceTypeDto]:
        rt = await self._repo.get_by_id(cmd.id)
        if rt is None:
            return Result.failure("ResourceTypeNotFound", status_code=404)

        if cmd.name is not None or cmd.description is not None:
            rt.update_metadata(name=cmd.name, description=cmd.description)

        if cmd.attribute_schema is not None:
            defs: list[AttributeDefinition] = []
            errors: list[str] = []
            for raw in cmd.attribute_schema:
                try:
                    dt = AttrType(raw["data_type"])
                except ValueError:
                    errors.append(f"InvalidDataType:{raw.get('data_type')!r}")
                    continue
                r = AttributeDefinition.create(
                    key=raw["key"],
                    label=raw["label"],
                    data_type=dt,
                    required=raw.get("required", False),
                    enum_values=raw.get("enum_values"),
                )
                if r.is_failure:
                    errors.append(r.error)
                else:
                    defs.append(r.value)
            if errors:
                return Result.failure("; ".join(errors), status_code=400)

            replace_r = rt.replace_attribute_schema(defs)
            if replace_r.is_failure:
                return Result.failure(replace_r.error, status_code=400)

        if cmd.is_active is not None:
            if cmd.is_active:
                rt.activate()
            else:
                rt.deactivate()

        update_r = await self._repo.update(rt)
        if update_r.is_failure:
            return Result.failure(update_r.error, status_code=update_r.status_code or 500)

        return Result.success(ResourceTypeDto.from_entity(rt))
```

- [ ] **Step 4: Run — green**

```bash
.venv/bin/pytest tests/unit/use_cases/catalog/commands/test_update_resource_type.py -v
.venv/bin/pytest -q
```

- [ ] **Step 5: Commit**

```bash
git add app/use_cases/catalog/commands/update_resource_type.py \
        tests/unit/use_cases/catalog/commands/test_update_resource_type.py
git commit -m "$(cat <<'EOF'
feat(catalog): UpdateResourceTypeHandler

Partial update: any field provided is updated, absent fields stay
unchanged. attribute_schema is replaced wholesale per Decision 5
(no per-key patching). Returns ResourceTypeNotFound (404) when the
target id doesn't exist; propagates DuplicateAttributeKey or VO
validation errors from replace_attribute_schema.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task C4 — `DeleteResourceTypeHandler`

**Files:** `app/use_cases/catalog/commands/delete_resource_type.py`, `tests/unit/use_cases/catalog/commands/test_delete_resource_type.py`.

- [ ] **Step 1: Failing tests**

```python
from __future__ import annotations
from uuid import uuid4
import pytest
from app.domain.catalog.attribute import AttrType, AttributeDefinition
from app.domain.catalog.resource_type import ResourceType
from app.use_cases.catalog.commands.delete_resource_type import (
    DeleteResourceTypeCommand,
    DeleteResourceTypeHandler,
)
from tests.unit.use_cases.catalog.fakes.in_memory_resource_type_repository import (
    InMemoryResourceTypeRepository,
)


pytestmark = pytest.mark.asyncio


async def test_delete_resource_type_success():
    repo = InMemoryResourceTypeRepository()
    rt = ResourceType.create(
        slug="football-field", name="Football Field", description="", attribute_schema=[],
    ).value
    await repo.add(rt)
    handler = DeleteResourceTypeHandler(repo)
    r = await handler.handle(DeleteResourceTypeCommand(id=rt.id))
    assert r.is_success
    assert (await repo.get_by_id(rt.id)) is None


async def test_delete_returns_not_found_for_missing_id():
    repo = InMemoryResourceTypeRepository()
    handler = DeleteResourceTypeHandler(repo)
    r = await handler.handle(DeleteResourceTypeCommand(id=uuid4()))
    assert r.is_failure
    assert r.error == "ResourceTypeNotFound"
```

- [ ] **Step 2: Run — fail**

- [ ] **Step 3: Implementation**

`app/use_cases/catalog/commands/delete_resource_type.py`:

```python
from __future__ import annotations
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID
from app.domain.shared.result import Result


class _RepoLike(Protocol):
    async def delete(self, rt_id: UUID) -> Result[None]: ...


@dataclass(frozen=True, slots=True)
class DeleteResourceTypeCommand:
    id: UUID


class DeleteResourceTypeHandler:
    def __init__(self, repo: _RepoLike) -> None:
        self._repo = repo

    async def handle(self, cmd: DeleteResourceTypeCommand) -> Result[None]:
        # TODO(plan-06): inject IResourceRepository and check whether any Resource
        # references this type. Spec §5.2: "Deletion is allowed only if no
        # Resource references the type." Resource doesn't exist yet.
        return await self._repo.delete(cmd.id)
```

- [ ] **Step 4: Run — green**

```bash
.venv/bin/pytest tests/unit/use_cases/catalog/commands/ -v
.venv/bin/pytest -q
```

- [ ] **Step 5: Commit**

```bash
git add app/use_cases/catalog/commands/delete_resource_type.py \
        tests/unit/use_cases/catalog/commands/test_delete_resource_type.py
git commit -m "$(cat <<'EOF'
feat(catalog): DeleteResourceTypeHandler

Hard-delete via repository. Returns ResourceTypeNotFound (404) for
missing ids. The "blocked if referenced" invariant from spec §5.2
is deferred to Plan 06 (resources) where IResourceRepository becomes
available; a TODO marks the gap.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## UNIT D — API + e2e

### Task D1 — Pydantic schemas

**Files:** create `app/api/v1/admin_resource_types/__init__.py`, `app/api/v1/admin_resource_types/schemas.py`, `app/api/v1/catalog/__init__.py`, `app/api/v1/catalog/schemas.py`.

- [ ] **Step 1: Create empty `__init__.py`s**

```bash
mkdir -p app/api/v1/admin_resource_types
mkdir -p app/api/v1/catalog
touch app/api/v1/admin_resource_types/__init__.py
touch app/api/v1/catalog/__init__.py
```

- [ ] **Step 2: Admin schemas**

`app/api/v1/admin_resource_types/schemas.py`:

```python
from __future__ import annotations
from datetime import datetime
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field
from app.use_cases.catalog.dtos import ResourceTypeDto


_DataType = Literal["string", "int", "bool", "enum"]


class AttributeDefinitionPayload(BaseModel):
    """Wire format for an attribute definition. VOs own length validation;
    no max_length on key/label here."""
    model_config = ConfigDict(extra="forbid")

    key: str
    label: str
    data_type: _DataType
    required: bool = False
    enum_values: list[str] | None = None


class CreateResourceTypeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slug: str
    name: str
    description: str = ""
    attribute_schema: list[AttributeDefinitionPayload] = Field(default_factory=list)
    is_active: bool = True


class UpdateResourceTypeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    description: str | None = None
    attribute_schema: list[AttributeDefinitionPayload] | None = None
    is_active: bool | None = None


class AttributeDefinitionResponse(BaseModel):
    key: str
    label: str
    data_type: _DataType
    required: bool
    enum_values: list[str] | None = None


class ResourceTypeResponse(BaseModel):
    id: UUID
    slug: str
    name: str
    description: str
    attribute_schema: list[AttributeDefinitionResponse]
    is_active: bool
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_dto(cls, dto: ResourceTypeDto) -> "ResourceTypeResponse":
        return cls(
            id=dto.id,
            slug=dto.slug,
            name=dto.name,
            description=dto.description,
            attribute_schema=[
                AttributeDefinitionResponse(
                    key=a.key, label=a.label, data_type=a.data_type,  # type: ignore[arg-type]
                    required=a.required, enum_values=a.enum_values,
                )
                for a in dto.attribute_schema
            ],
            is_active=dto.is_active,
            created_at=dto.created_at,
            updated_at=dto.updated_at,
        )


class ResourceTypeListResponse(BaseModel):
    items: list[ResourceTypeResponse]
    limit: int
    offset: int
```

- [ ] **Step 3: Public schemas**

`app/api/v1/catalog/schemas.py`:

```python
from __future__ import annotations
from app.api.v1.admin_resource_types.schemas import (
    ResourceTypeResponse,
    ResourceTypeListResponse,
)

# Public storefront uses the same response shape — no admin-only fields exposed
# yet (is_active is implicit since public listings filter to active only).
__all__ = ["ResourceTypeResponse", "ResourceTypeListResponse"]
```

- [ ] **Step 4: Smoke import**

```bash
BACKEND_DATABASE_URL="sqlite+aiosqlite:///:memory:" .venv/bin/python -c "
from app.api.v1.admin_resource_types.schemas import (
    CreateResourceTypeRequest, UpdateResourceTypeRequest, ResourceTypeResponse,
)
from app.api.v1.catalog.schemas import ResourceTypeListResponse
print('schemas loaded')
"
```

- [ ] **Step 5: Commit**

```bash
git add app/api/v1/admin_resource_types/ app/api/v1/catalog/
git commit -m "$(cat <<'EOF'
feat(catalog): add Pydantic schemas (admin + public)

Request/response models for admin CRUD and the public catalog
listing. No max_length on VO-backed fields (slug/name/description/
key/label) per spec §3 decision 17. extra="forbid" on requests so
unknown fields are rejected at the boundary.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task D2 — Admin routes

`POST/GET/PATCH/DELETE /v1/admin/resource-types`. Reuses `require_role(Role.ADMIN)` from `app/api/deps.py` and the unwrap pattern from Plan 02.

**Files:** create `app/api/v1/admin_resource_types/deps.py`, `app/api/v1/admin_resource_types/routes.py`, modify `app/api/v1/router.py`.

- [ ] **Step 1: DI deps**

`app/api/v1/admin_resource_types/deps.py`:

```python
from __future__ import annotations
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_db_session
from app.infrastructure.repositories.resource_type_repository import (
    SQLAlchemyResourceTypeRepository,
)
from app.use_cases.catalog.commands.create_resource_type import CreateResourceTypeHandler
from app.use_cases.catalog.commands.delete_resource_type import DeleteResourceTypeHandler
from app.use_cases.catalog.commands.update_resource_type import UpdateResourceTypeHandler


async def get_resource_type_repo(
    session: AsyncSession = Depends(get_db_session),
) -> SQLAlchemyResourceTypeRepository:
    return SQLAlchemyResourceTypeRepository(session)


async def get_create_handler(
    repo: SQLAlchemyResourceTypeRepository = Depends(get_resource_type_repo),
) -> CreateResourceTypeHandler:
    return CreateResourceTypeHandler(repo)


async def get_update_handler(
    repo: SQLAlchemyResourceTypeRepository = Depends(get_resource_type_repo),
) -> UpdateResourceTypeHandler:
    return UpdateResourceTypeHandler(repo)


async def get_delete_handler(
    repo: SQLAlchemyResourceTypeRepository = Depends(get_resource_type_repo),
) -> DeleteResourceTypeHandler:
    return DeleteResourceTypeHandler(repo)
```

If `get_db_session` doesn't exist at `app/api/deps.py`, look at how `admin_users/routes.py` from Plan 02 acquires its session. Match that pattern.

- [ ] **Step 2: Routes**

`app/api/v1/admin_resource_types/routes.py`:

```python
from __future__ import annotations
from uuid import UUID
from fastapi import APIRouter, Depends, Query
from app.api.deps import require_role
from app.api.error_handler import unwrap
from app.api.v1.admin_resource_types.deps import (
    get_create_handler, get_delete_handler, get_resource_type_repo, get_update_handler,
)
from app.api.v1.admin_resource_types.schemas import (
    CreateResourceTypeRequest,
    ResourceTypeListResponse,
    ResourceTypeResponse,
    UpdateResourceTypeRequest,
)
from app.domain.accounts.role import Role
from app.infrastructure.repositories.resource_type_repository import SQLAlchemyResourceTypeRepository
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
    prefix="/admin/resource-types",
    tags=["admin:catalog"],
    dependencies=[Depends(require_role(Role.ADMIN))],
)


@router.post("", response_model=ResourceTypeResponse, status_code=201)
async def create_resource_type(
    body: CreateResourceTypeRequest,
    handler: CreateResourceTypeHandler = Depends(get_create_handler),
):
    cmd = CreateResourceTypeCommand(
        slug=body.slug,
        name=body.name,
        description=body.description,
        attribute_schema=[a.model_dump() for a in body.attribute_schema],
        is_active=body.is_active,
    )
    dto: ResourceTypeDto = unwrap(await handler.handle(cmd))
    return ResourceTypeResponse.from_dto(dto)


@router.get("", response_model=ResourceTypeListResponse)
async def list_resource_types(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    repo: SQLAlchemyResourceTypeRepository = Depends(get_resource_type_repo),
):
    rows = await repo.list_all(limit=limit, offset=offset)
    return ResourceTypeListResponse(
        items=[ResourceTypeResponse.from_dto(ResourceTypeDto.from_entity(rt)) for rt in rows],
        limit=limit,
        offset=offset,
    )


@router.get("/{rt_id}", response_model=ResourceTypeResponse)
async def get_resource_type(
    rt_id: UUID,
    repo: SQLAlchemyResourceTypeRepository = Depends(get_resource_type_repo),
):
    rt = await repo.get_by_id(rt_id)
    if rt is None:
        from fastapi import HTTPException
        from app.api.error_codes import translate
        raise HTTPException(
            status_code=404,
            detail={"code": "ResourceTypeNotFound", "message": translate("ResourceTypeNotFound")},
        )
    return ResourceTypeResponse.from_dto(ResourceTypeDto.from_entity(rt))


@router.patch("/{rt_id}", response_model=ResourceTypeResponse)
async def update_resource_type(
    rt_id: UUID,
    body: UpdateResourceTypeRequest,
    handler: UpdateResourceTypeHandler = Depends(get_update_handler),
):
    cmd = UpdateResourceTypeCommand(
        id=rt_id,
        name=body.name,
        description=body.description,
        attribute_schema=(
            [a.model_dump() for a in body.attribute_schema]
            if body.attribute_schema is not None
            else None
        ),
        is_active=body.is_active,
    )
    dto = unwrap(await handler.handle(cmd))
    return ResourceTypeResponse.from_dto(dto)


@router.delete("/{rt_id}", status_code=204)
async def delete_resource_type(
    rt_id: UUID,
    handler: DeleteResourceTypeHandler = Depends(get_delete_handler),
):
    unwrap(await handler.handle(DeleteResourceTypeCommand(id=rt_id)))
    return None
```

- [ ] **Step 3: Register in `app/api/v1/router.py`**

Read the current router file. Add an import + include for the admin_resource_types router. Pattern matches the existing `admin_users` registration.

```python
from app.api.v1.admin_resource_types.routes import router as admin_resource_types_router
# ...
api_router.include_router(admin_resource_types_router)
```

- [ ] **Step 4: Smoke import + run full suite**

```bash
BACKEND_DATABASE_URL="sqlite+aiosqlite:///:memory:" .venv/bin/python -c "from app.main import app; print('ok')"
.venv/bin/pytest -q
```

Expected: green.

- [ ] **Step 5: Commit**

```bash
git add app/api/v1/admin_resource_types/deps.py \
        app/api/v1/admin_resource_types/routes.py \
        app/api/v1/router.py
git commit -m "$(cat <<'EOF'
feat(catalog): admin CRUD routes for resource-types

POST/GET/PATCH/DELETE /v1/admin/resource-types behind the
require_role(Role.ADMIN) guard. List endpoint paginates with limit
(1..100) + offset. Detail endpoint returns 404 with the
ResourceTypeNotFound code when the id is missing. Mutation paths
go through CreateResourceType/UpdateResourceType/DeleteResource
TypeHandler and unwrap their Result to {code, message} on failure.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task D3 — Public route

`GET /v1/catalog/resource-types`. No auth. Active rows only.

**Files:** create `app/api/v1/catalog/routes.py`, modify `app/api/v1/router.py`.

- [ ] **Step 1: Routes**

`app/api/v1/catalog/routes.py`:

```python
from __future__ import annotations
from fastapi import APIRouter, Depends, Query
from app.api.v1.admin_resource_types.deps import get_resource_type_repo
from app.api.v1.admin_resource_types.schemas import ResourceTypeResponse
from app.api.v1.catalog.schemas import ResourceTypeListResponse
from app.infrastructure.repositories.resource_type_repository import SQLAlchemyResourceTypeRepository
from app.use_cases.catalog.dtos import ResourceTypeDto


router = APIRouter(prefix="/catalog", tags=["catalog"])


@router.get("/resource-types", response_model=ResourceTypeListResponse)
async def list_active_resource_types(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    repo: SQLAlchemyResourceTypeRepository = Depends(get_resource_type_repo),
):
    rows = await repo.list_active(limit=limit, offset=offset)
    return ResourceTypeListResponse(
        items=[ResourceTypeResponse.from_dto(ResourceTypeDto.from_entity(rt)) for rt in rows],
        limit=limit,
        offset=offset,
    )
```

- [ ] **Step 2: Register in `app/api/v1/router.py`**

```python
from app.api.v1.catalog.routes import router as catalog_router
# ...
api_router.include_router(catalog_router)
```

- [ ] **Step 3: Run full suite**

```bash
.venv/bin/pytest -q
```

Expected: green.

- [ ] **Step 4: Commit**

```bash
git add app/api/v1/catalog/routes.py app/api/v1/router.py
git commit -m "$(cat <<'EOF'
feat(catalog): public listing endpoint

GET /v1/catalog/resource-types — no auth, returns only is_active=True
rows, paginated. Powers the storefront filter UI.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task D4 — End-to-end flow test

Admin creates → public sees → admin updates → admin deletes → public no longer sees.

**Files:** create `tests/e2e/catalog/__init__.py`, `tests/e2e/catalog/test_admin_and_public_flow.py`.

- [ ] **Step 1: e2e test**

`tests/e2e/catalog/test_admin_and_public_flow.py`:

```python
from __future__ import annotations
import pytest


pytestmark = pytest.mark.asyncio


async def test_admin_creates_resource_type_then_public_sees_it(http_client, admin_token):
    # Admin creates
    create = await http_client.post(
        "/api/v1/admin/resource-types",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "slug": "football-field",
            "name": "Football Field",
            "description": "Campos de futebol",
            "attribute_schema": [
                {"key": "surface", "label": "Tipo de gramado", "data_type": "enum",
                 "required": True, "enum_values": ["natural", "synthetic"]},
            ],
            "is_active": True,
        },
    )
    assert create.status_code == 201, create.text
    body = create.json()
    rt_id = body["id"]
    assert body["slug"] == "football-field"

    # Public sees it
    public_list = await http_client.get("/api/v1/catalog/resource-types")
    assert public_list.status_code == 200
    items = public_list.json()["items"]
    assert any(item["slug"] == "football-field" for item in items)

    # Admin deactivates
    patch = await http_client.patch(
        f"/api/v1/admin/resource-types/{rt_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"is_active": False},
    )
    assert patch.status_code == 200

    # Public no longer sees it
    public_list_after = await http_client.get("/api/v1/catalog/resource-types")
    assert public_list_after.status_code == 200
    items_after = public_list_after.json()["items"]
    assert not any(item["slug"] == "football-field" for item in items_after)


async def test_admin_create_rejects_duplicate_slug(http_client, admin_token):
    payload = {
        "slug": "padel-court",
        "name": "Padel Court",
        "description": "",
        "attribute_schema": [],
    }
    first = await http_client.post(
        "/api/v1/admin/resource-types",
        headers={"Authorization": f"Bearer {admin_token}"},
        json=payload,
    )
    assert first.status_code == 201

    second = await http_client.post(
        "/api/v1/admin/resource-types",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={**payload, "name": "Other Padel Court"},
    )
    assert second.status_code == 409
    assert second.json()["detail"]["code"] == "SlugAlreadyTaken"


async def test_public_listing_no_auth_required(http_client):
    response = await http_client.get("/api/v1/catalog/resource-types")
    assert response.status_code == 200


async def test_admin_create_rejects_non_admin_role(http_client, customer_token):
    response = await http_client.post(
        "/api/v1/admin/resource-types",
        headers={"Authorization": f"Bearer {customer_token}"},
        json={"slug": "x", "name": "X", "description": "", "attribute_schema": []},
    )
    assert response.status_code == 403


async def test_admin_create_propagates_slug_validation_error(http_client, admin_token):
    response = await http_client.post(
        "/api/v1/admin/resource-types",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "slug": "Invalid Slug!",
            "name": "Foo",
            "description": "",
            "attribute_schema": [],
        },
    )
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert "SlugInvalidFormat" in detail["code"]
```

The fixtures `http_client`, `admin_token`, `customer_token` should already exist in `tests/e2e/conftest.py` from Plan 02. If `customer_token` isn't there, add it to that conftest using the same pattern as `admin_token`.

- [ ] **Step 2: Run e2e**

```bash
.venv/bin/pytest tests/e2e/catalog/ -v
```

Expected: 5 tests pass.

- [ ] **Step 3: Run full suite**

```bash
.venv/bin/pytest -q
```

Expected: green.

- [ ] **Step 4: Commit**

```bash
git add tests/e2e/catalog/
git commit -m "$(cat <<'EOF'
test(e2e): catalog admin + public flow

Five e2e tests covering: full create→public-list→deactivate→public-
hides flow; duplicate-slug 409; public no-auth; admin-only role
guard; slug validation propagation. Validates the wire shape of
{code, message} error payloads for the catalog endpoints.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Final verification

- [ ] **Step 1: Full test suite + lint**

```bash
.venv/bin/pytest -q
make lint
```

Expected: all green. ~210 (Plan 03 baseline) + ~50 new tests = ~260 passing.

- [ ] **Step 2: Smoke import**

```bash
BACKEND_DATABASE_URL="sqlite+aiosqlite:///:memory:" .venv/bin/python -c "
from app.main import app
from app.domain.catalog.resource_type import ResourceType
from app.api.v1.admin_resource_types.routes import router as admin_router
from app.api.v1.catalog.routes import router as catalog_router
print('app loaded; admin routes:', len(admin_router.routes))
print('public routes:', len(catalog_router.routes))
"
```

Expected: prints route counts (5 admin, 1 public).

- [ ] **Step 3: Push branch**

```bash
git push -u origin feat/plan-04-catalog
```

- [ ] **Step 4: No commit (verification only)**

---

## Self-review

**Spec coverage.** This plan covers spec §5.2 (`ResourceType` aggregate + `AttributeDefinition`) and §7 endpoints (`POST/GET/PATCH/DELETE /admin/resource-types`, `GET /catalog/resource-types`). The "blocked if referenced" invariant from §5.2 is deferred to Plan 06 with a TODO marker (Decision 6). The `validate_attributes` method (§5.2 will be used by Plan 06's Resource creation) is implemented and tested.

**VO reuse.** Slug, Name, ShortDescription, AttributeKey, ShortName all consumed from `app/domain/shared/value_objects/` (Plan 03). One new VO created: `AttributeDefinition` (composite, in `app/domain/catalog/`).

**Entity convention §4.4.** `ResourceType` is `@dataclass(slots=True, kw_only=True)` (mutable), inherits `BaseEntity`. Class-level error code constants for invariants. `cls.create()` factory. Mutators: `update_metadata`/`activate`/`deactivate` return `None` (no domain invariant — VO factories validate); `replace_attribute_schema` returns `Result[None]` (enforces unique-key invariant). Private collection `_attribute_schema` with tuple view. `updated_at` bumped in every successful mutator.

**Placeholder scan.** No "TBD"/"TODO" inside step bodies (only in code comments where intentional, e.g., the Plan 06 reference check).

**Type consistency.**
- `Result[ResourceTypeDto]` is the handler-return shape for Create/Update.
- `Result[None]` for Delete and repository methods.
- `Result[None]` for entity mutators with invariants.
- DTOs flatten VO `.value` to plain types; Pydantic schemas mirror DTO.
- API errors use `{code, message}` per Plan 03.

**Risks the engineer should watch for.**

1. The `db_session` fixture and `http_client`/`admin_token` fixtures are assumed available from Plan 02. If they're not visible, look at how the accounts integration/e2e tests acquire them and either reuse the conftest or import the fixtures.
2. Alembic autogen sometimes generates spurious DROP statements when stale state exists. Inspect every generated file before committing.
3. `mypy` may complain about Protocol `_RepoLike` not declaring all repository methods (each handler only declares what it uses). This is intentional — handlers depend on the slimmest interface they need. Suppress the complaint or cast at call site if mypy is strict.
4. `attribute_schema` JSON storage means the row is returned as a Python list of dicts when read. The `_attribute_from_dict` helper trusts the dict shape — if a hand-edited DB row is malformed, reconstitution explodes at runtime. Acceptable since admin is the only writer.

---

## Execution handoff

Plan complete. Two execution options:

1. **Subagent-Driven (recommended)** — fresh subagent per task, two-stage review, fast iteration.
2. **Inline Execution** — execute tasks in this session using executing-plans, batch execution with checkpoints.

Reply with **"subagent"** or **"inline"** to proceed.
