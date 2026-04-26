# Validation Error Envelope Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace `"; "`-joined error strings in domain and use-case aggregators with a structured `FieldError` list on `Result.details`, and emit a `ValidationFailed` envelope at the HTTP boundary. Closes the multi-error envelope follow-up before Plan 06.

**Architecture:** `Result[T]` gains a parallel `details: tuple[FieldError, ...] | None` field — exactly one of `error` or `details` is set on failure. Aggregators (`User.create`, `ResourceType.{create, update_metadata, replace_attribute_schema, validate_attributes}`, `CreateResourceTypeHandler.handle`, `UpdateResourceTypeHandler.handle`) emit via `Result.failure_many(...)`. Single-error VOs and handler-level failures are unchanged. `unwrap()` dispatches body shape based on which field is set: flat `{code, message}` for `error`, envelope `{code: "ValidationFailed", message, details: [...]}` for `details`. Default status code for envelope is 400.

**Tech Stack:** Python 3.12, pytest, FastAPI. No new dependencies.

**Reference spec:** `docs/superpowers/specs/2026-04-26-validation-error-envelope-design.md`.

**Conventions reminders:**
- Always invoke Python via the venv: `.venv/bin/python` or `.venv/bin/pytest`.
- Domain code never imports from `infrastructure` or `use_cases`.
- After each task, commit with a focused message. Use `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>`.

---

## Task 1: Add `FieldError` VO

**Files:**
- Create: `app/domain/shared/field_error.py`
- Test: `tests/unit/domain/shared/test_field_error.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/domain/shared/test_field_error.py`:

```python
from dataclasses import FrozenInstanceError

import pytest

from app.domain.shared.field_error import FieldError


def test_field_error_carries_code_and_field():
    err = FieldError(code="EmailInvalidFormat", field="email")
    assert err.code == "EmailInvalidFormat"
    assert err.field == "email"


def test_field_error_field_defaults_to_none():
    err = FieldError(code="DuplicateAttributeKey")
    assert err.field is None


def test_field_error_is_frozen():
    err = FieldError(code="X")
    with pytest.raises(FrozenInstanceError):
        err.code = "Y"  # type: ignore[misc]


def test_field_error_equality_by_value():
    a = FieldError(code="X", field="email")
    b = FieldError(code="X", field="email")
    c = FieldError(code="X", field="phone")
    assert a == b
    assert a != c


def test_field_error_is_hashable():
    s = {FieldError(code="X", field="email"), FieldError(code="X", field="email")}
    assert len(s) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/unit/domain/shared/test_field_error.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.domain.shared.field_error'`.

- [ ] **Step 3: Write minimal implementation**

Create `app/domain/shared/field_error.py`:

```python
from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class FieldError:
    """Structured per-field error emitted by aggregators.

    Carried inside `Result.details` when an aggregate root or use-case handler
    aggregates multiple validation failures. Translated to pt-BR at the HTTP
    boundary via `app.api.error_codes.translate(code)`.
    """

    code: str
    field: str | None = None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/unit/domain/shared/test_field_error.py -v`
Expected: 5 PASS.

- [ ] **Step 5: Commit**

```bash
git add app/domain/shared/field_error.py tests/unit/domain/shared/test_field_error.py
git commit -m "$(cat <<'EOF'
feat(domain): add FieldError VO for structured aggregator errors

Carrier for per-field validation failures inside Result.details. Domain
stays language-free; pt-BR translation lives at the HTTP boundary.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Extend `Result[T]` with `details`, `failure_many`, `from_failure`

**Files:**
- Modify: `app/domain/shared/result.py`
- Modify: `tests/unit/domain/shared/test_result.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/unit/domain/shared/test_result.py`:

```python
from app.domain.shared.field_error import FieldError


# --- failure_many ---

def test_failure_many_sets_details_and_clears_error():
    errs = [FieldError(code="A", field="x"), FieldError(code="B", field="y")]
    r = Result.failure_many(errs)
    assert r.is_failure
    assert r.error is None
    assert r.details == tuple(errs)


def test_failure_many_propagates_status_code():
    r = Result.failure_many([FieldError(code="A")], status_code=400)
    assert r.status_code == 400


def test_failure_many_rejects_empty_list():
    with pytest.raises(ValueError, match="failure_many requires at least one"):
        Result.failure_many([])


def test_failure_many_accepts_iterable_not_just_list():
    r = Result.failure_many(iter([FieldError(code="A")]))
    assert r.details == (FieldError(code="A"),)


# --- exactly-one invariant ---

def test_failure_rejects_both_error_and_details():
    with pytest.raises(ValueError, match="exactly one of error or details"):
        Result(
            is_success=False,
            error="boom",
            details=(FieldError(code="A"),),
        )


def test_failure_rejects_neither_error_nor_details():
    with pytest.raises(ValueError, match="exactly one of error or details"):
        Result(is_success=False)


def test_success_rejects_details():
    with pytest.raises(ValueError, match="cannot carry error/details"):
        Result(is_success=True, value=1, details=(FieldError(code="A"),))


# --- from_failure ---

def test_from_failure_preserves_details():
    src = Result.failure_many([FieldError(code="A", field="x")], status_code=400)
    re = Result.from_failure(src)
    assert re.is_failure
    assert re.details == src.details
    assert re.status_code == 400


def test_from_failure_preserves_error_string():
    src = Result.failure("Boom", status_code=409)
    re = Result.from_failure(src)
    assert re.is_failure
    assert re.error == "Boom"
    assert re.status_code == 409


def test_from_failure_status_code_override():
    src = Result.failure_many([FieldError(code="A")], status_code=400)
    re = Result.from_failure(src, status_code=422)
    assert re.status_code == 422


def test_from_failure_status_code_override_keeps_details():
    src = Result.failure_many([FieldError(code="A", field="x")])
    re = Result.from_failure(src, status_code=422)
    assert re.details == src.details
    assert re.status_code == 422


def test_from_failure_raises_on_success():
    with pytest.raises(ValueError, match="from_failure called on a successful"):
        Result.from_failure(Result.success(1))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/unit/domain/shared/test_result.py -v`
Expected: the new tests FAIL (mostly `AttributeError: type object 'Result' has no attribute 'failure_many'` etc.); the old tests still PASS.

- [ ] **Step 3: Modify `Result[T]`**

Replace `app/domain/shared/result.py` with:

```python
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Callable, Generic, Iterable, Optional, TypeVar

from app.domain.shared.field_error import FieldError

T = TypeVar("T")
U = TypeVar("U")


@dataclass(frozen=True, slots=True)
class Result(Generic[T]):
    """Wrapper sucesso/falha para evitar controle de fluxo por exceção."""
    is_success: bool
    value: Optional[T] = None
    error: Optional[str] = None
    details: Optional[tuple[FieldError, ...]] = None
    status_code: Optional[int] = None

    def __post_init__(self) -> None:
        if self.is_success:
            if self.error is not None or self.details is not None:
                raise ValueError("Successful result cannot carry error/details.")
        else:
            if self.value is not None:
                raise ValueError("Value cannot be set for a failure result.")
            if (self.error is None) == (self.details is None):
                raise ValueError(
                    "Failed result must have exactly one of error or details."
                )

    @property
    def is_failure(self) -> bool:
        return not self.is_success

    @staticmethod
    def success(value: Optional[T] = None, *, status_code: Optional[int] = None) -> "Result[T]":
        return Result(is_success=True, value=value, error=None, status_code=status_code)

    @staticmethod
    def failure(error: str, *, status_code: Optional[int] = None) -> "Result[T]":
        return Result(is_success=False, value=None, error=error, status_code=status_code)

    @staticmethod
    def failure_many(
        errors: Iterable[FieldError],
        *,
        status_code: Optional[int] = None,
    ) -> "Result[T]":
        details = tuple(errors)
        if not details:
            raise ValueError("failure_many requires at least one FieldError.")
        return Result(is_success=False, details=details, status_code=status_code)

    @staticmethod
    def from_failure(
        other: "Result[Any]",
        *,
        status_code: Optional[int] = None,
    ) -> "Result[T]":
        """Re-wrap a failed Result preserving error vs. details path; useful in
        handlers that need to convert Result[User] → Result[UserDto] on failure."""
        if other.is_success:
            raise ValueError("from_failure called on a successful Result.")
        sc = status_code if status_code is not None else other.status_code
        if other.details is not None:
            return Result.failure_many(other.details, status_code=sc)
        return Result.failure(other.error or "InternalError", status_code=sc)

    @staticmethod
    def from_exception(exc: Exception, *, prefix: str | None = None) -> "Result[T]":
        msg = f"{exc.__class__.__name__}: {exc}"
        return Result.failure(f"{prefix}: {msg}" if prefix else msg)

    def map(self, fn: Callable[[T], U]) -> "Result[U]":
        if self.is_failure:
            if self.details is not None:
                return Result.failure_many(self.details, status_code=self.status_code)
            return Result.failure(self.error or "Unknown error", status_code=self.status_code)
        try:
            return Result.success(fn(self.value))  # type: ignore[arg-type]
        except Exception as exc:
            return Result.from_exception(exc, prefix="Result.map failed")

    def unwrap_or(self, default: T) -> T:
        return self.value if self.is_success and self.value is not None else default
```

Note: `map` was updated to forward `details` and `status_code` (it previously dropped both). Existing callers that only used `map` over success-paths are unaffected.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/unit/domain/shared/test_result.py -v`
Expected: all old tests still PASS, all new tests PASS.

- [ ] **Step 5: Commit**

```bash
git add app/domain/shared/result.py tests/unit/domain/shared/test_result.py
git commit -m "$(cat <<'EOF'
feat(domain): Result.details + failure_many + from_failure

Result[T] now supports a parallel structured-error path (details: tuple
of FieldError) used by aggregators. Exactly one of error or details is
set on failure. from_failure re-wraps across Result type parameters
preserving the path. map() now forwards details and status_code.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Update HTTP boundary (`unwrap` + `error_codes` + arch test)

**Files:**
- Modify: `app/api/error_handler.py`
- Modify: `app/api/error_codes.py:107-119` (handler-level codes section)
- Modify: `tests/unit/architecture/test_error_code_coverage.py:89-99` (handler_level_allowlist)

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/api/test_error_handler.py` (and ensure `tests/unit/api/__init__.py` exists):

```python
import pytest
from fastapi import HTTPException

from app.api.error_handler import unwrap
from app.domain.shared.field_error import FieldError
from app.domain.shared.result import Result


def test_unwrap_success_returns_value():
    assert unwrap(Result.success(42)) == 42


def test_unwrap_single_error_emits_flat_body():
    r = Result.failure("ResourceTypeNotFound", status_code=404)
    with pytest.raises(HTTPException) as exc_info:
        unwrap(r)
    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == {
        "code": "ResourceTypeNotFound",
        "message": "Tipo de recurso não encontrado.",
    }


def test_unwrap_details_emits_envelope():
    r = Result.failure_many(
        [
            FieldError(code="EmailInvalidFormat", field="email"),
            FieldError(code="NameCannotBeEmpty", field="full_name"),
        ],
        status_code=400,
    )
    with pytest.raises(HTTPException) as exc_info:
        unwrap(r)
    assert exc_info.value.status_code == 400
    detail = exc_info.value.detail
    assert detail["code"] == "ValidationFailed"
    assert detail["message"] == "Falha de validação."
    assert detail["details"] == [
        {"field": "email", "code": "EmailInvalidFormat", "message": "E-mail em formato inválido."},
        {"field": "full_name", "code": "NameCannotBeEmpty", "message": "Nome é obrigatório."},
    ]


def test_unwrap_details_defaults_status_code_to_400():
    r = Result.failure_many([FieldError(code="EmailInvalidFormat", field="email")])
    with pytest.raises(HTTPException) as exc_info:
        unwrap(r)
    assert exc_info.value.status_code == 400


def test_unwrap_unknown_code_in_details_uses_code_as_message():
    r = Result.failure_many([FieldError(code="NotMappedCode", field="x")])
    with pytest.raises(HTTPException) as exc_info:
        unwrap(r)
    detail_entries = exc_info.value.detail["details"]
    assert detail_entries[0] == {"field": "x", "code": "NotMappedCode", "message": "NotMappedCode"}
```

Make sure the package init file exists:

```bash
test -f tests/unit/api/__init__.py || touch tests/unit/api/__init__.py
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/unit/api/test_error_handler.py -v`
Expected: most tests FAIL — the envelope branch doesn't exist; `"ValidationFailed"` isn't in the translation map.

- [ ] **Step 3: Modify `unwrap()`**

Replace the body of `unwrap()` in `app/api/error_handler.py` (the function defined at line 13) with:

```python
def unwrap(result: Result[T]) -> T:
    if result.is_success:
        return result.value  # type: ignore[return-value]

    if result.details is not None:
        raise HTTPException(
            status_code=result.status_code or 400,
            detail={
                "code": "ValidationFailed",
                "message": translate("ValidationFailed"),
                "details": [
                    {"field": e.field, "code": e.code, "message": translate(e.code)}
                    for e in result.details
                ],
            },
        )

    code = result.error or "InternalError"
    raise HTTPException(
        status_code=result.status_code or 500,
        detail={"code": code, "message": translate(code)},
    )
```

- [ ] **Step 4: Add `ValidationFailed` to `error_codes.py`**

In `app/api/error_codes.py`, in the "Handler-level (not VO-bound) codes" section (around line 107-119), add:

```python
    # Envelope code emitted by unwrap() when result.details is populated
    "ValidationFailed": "Falha de validação.",
```

- [ ] **Step 5: Update arch test allowlist**

In `tests/unit/architecture/test_error_code_coverage.py`, in `handler_level_allowlist` (around line 89), add `"ValidationFailed"`:

```python
    handler_level_allowlist: set[str] = {
        "PasswordHashCannotBeEmpty",
        "DuplicateAttributeKey",
        "RequiredAttributeMissing",
        "UnknownAttributeKey",
        "AttributeTypeMismatch",
        "AttributeEnumValueNotAllowed",
        "SlugAlreadyTaken",
        "ResourceTypeNotFound",
        "InvalidDataType",
        "ValidationFailed",
    }
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/unit/api/test_error_handler.py tests/unit/architecture/test_error_code_coverage.py -v`
Expected: all tests PASS.

- [ ] **Step 7: Commit**

```bash
git add app/api/error_handler.py app/api/error_codes.py tests/unit/api/__init__.py tests/unit/api/test_error_handler.py tests/unit/architecture/test_error_code_coverage.py
git commit -m "$(cat <<'EOF'
feat(api): emit ValidationFailed envelope when Result.details is set

unwrap() now dispatches body shape based on which Result field is
populated: flat {code, message} for single-error path, envelope with
ValidationFailed code + per-field details array when details is set.
Default status code for envelope is 400, matching the existing catalog
e2e convention.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Migrate `User.create`

**Files:**
- Modify: `app/domain/accounts/user.py:36-62` (the `create` classmethod)
- Modify: `tests/unit/domain/accounts/test_user.py`

- [ ] **Step 1: Update existing tests + add multi-field test**

In `tests/unit/domain/accounts/test_user.py`, replace every assertion of the form `assert "<code>" in r.error` (or `assert "email" in r.error.lower()`) with the new pattern. Concretely:

For each failure-path test that today asserts `assert <code> in r.error` (lines 46, 71, 83, 95, etc.), change the assertion block to:

```python
    assert r.error is None
    assert r.details is not None
    codes = {(e.field, e.code) for e in r.details}
```

then assert membership against `codes`. Examples:

- `assert "email" in r.error.lower()` → `assert any(e.field == "email" for e in r.details)`
- `assert Name.NAME_CANNOT_BE_EMPTY in r.error` → `assert ("full_name", Name.NAME_CANNOT_BE_EMPTY) in codes`
- `assert Name.NAME_CANNOT_BE_GREATER_THAN_MAX_LENGTH in r.error` → `assert ("full_name", Name.NAME_CANNOT_BE_GREATER_THAN_MAX_LENGTH) in codes`

(Keep the `r.is_failure` assertion; only the string-content check changes.)

Add a new test at the end of the file demonstrating multi-field aggregation:

```python
def test_user_create_aggregates_multiple_field_failures():
    """Spec §5.1: User.create emits one FieldError per failing field."""
    from app.domain.accounts.role import Role
    from app.domain.shared.value_objects.brazilian_phone import BrazilianPhone
    from app.domain.shared.value_objects.email import Email
    from app.domain.shared.value_objects.name import Name

    r = User.create(
        email="not-an-email",
        password_hash="",
        role=Role.CUSTOMER,
        full_name="",
        phone="abc",
    )
    assert r.is_failure
    assert r.error is None
    assert r.details is not None
    codes = {(e.field, e.code) for e in r.details}
    assert ("email", Email.EMAIL_INVALID_FORMAT) in codes
    assert ("full_name", Name.NAME_CANNOT_BE_EMPTY) in codes
    assert ("password_hash", "PasswordHashCannotBeEmpty") in codes
    assert ("phone", BrazilianPhone.PHONE_CONTAINS_INVALID_CHARACTERS) in codes
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/unit/domain/accounts/test_user.py -v`
Expected: the migrated tests FAIL (User.create still emits joined `error` string, so `r.details is None` fails); the new multi-field test FAILS for the same reason.

- [ ] **Step 3: Migrate `User.create`**

Replace the body of `User.create` in `app/domain/accounts/user.py` (lines 36-62) with:

```python
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

        if errors:
            return Result.failure_many(errors)

        return Result.success(cls(
            email=email_r.value,
            password_hash=password_hash,
            role=role,
            full_name=name_r.value,
            phone=phone_r.value,
        ))
```

Add the `FieldError` import at the top of the file:

```python
from app.domain.shared.field_error import FieldError
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/unit/domain/accounts/test_user.py -v`
Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add app/domain/accounts/user.py tests/unit/domain/accounts/test_user.py
git commit -m "$(cat <<'EOF'
refactor(accounts): User.create emits FieldError list via failure_many

Drops the "; "-join in favor of structured per-field errors. Tests
assert on (field, code) tuples in r.details instead of substring on
r.error. Adds a coverage test for multi-field aggregation.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Migrate `ResourceType.create`

**Files:**
- Modify: `app/domain/catalog/resource_type.py:31-68` (the `create` classmethod)
- Modify: `tests/unit/domain/catalog/test_resource_type.py` (the `create` tests, roughly lines 40-80)

- [ ] **Step 1: Update tests**

In `tests/unit/domain/catalog/test_resource_type.py`, find the tests that exercise `ResourceType.create` failure paths and currently assert `<CODE> in r.error`. For each one, switch to:

```python
    assert r.is_failure
    assert r.error is None
    assert r.details is not None
    codes = {(e.field, e.code) for e in r.details}
```

then assert membership. Field map:

- Slug failures → `field="slug"`
- Name failures → `field="name"`
- ShortDescription failures → `field="description"`
- DUPLICATE_ATTRIBUTE_KEY → `field="attribute_schema"`

Examples:

- `assert Slug.SLUG_INVALID_FORMAT in r.error` → `assert ("slug", Slug.SLUG_INVALID_FORMAT) in codes`
- `assert Name.NAME_CANNOT_BE_EMPTY in r.error` → `assert ("name", Name.NAME_CANNOT_BE_EMPTY) in codes`
- `assert ResourceType.DUPLICATE_ATTRIBUTE_KEY in r.error` (in `create` context) → `assert ("attribute_schema", ResourceType.DUPLICATE_ATTRIBUTE_KEY) in codes`

Add a multi-field aggregation test:

```python
def test_resource_type_create_aggregates_multiple_field_failures():
    r = ResourceType.create(
        slug="BAD slug",
        name="",
        description="",
        attribute_schema=[],
    )
    assert r.is_failure
    assert r.error is None
    assert r.details is not None
    codes = {(e.field, e.code) for e in r.details}
    assert ("slug", Slug.SLUG_INVALID_FORMAT) in codes
    assert ("name", Name.NAME_CANNOT_BE_EMPTY) in codes
```

(ShortDescription with empty string is allowed, so don't assert a description failure here.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/unit/domain/catalog/test_resource_type.py -v -k create`
Expected: migrated `create` tests FAIL; other (`update_metadata`, `validate_attributes`, etc.) tests still PASS.

- [ ] **Step 3: Migrate `ResourceType.create`**

In `app/domain/catalog/resource_type.py`, replace the body of `create` (lines 31-68) with:

```python
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

        schema_list = list(attribute_schema)
        if cls._has_duplicate_keys(schema_list):
            errors.append(FieldError(code=cls.DUPLICATE_ATTRIBUTE_KEY, field="attribute_schema"))

        if errors:
            return Result.failure_many(errors)

        return Result.success(cls(
            slug=slug_r.value,
            name=name_r.value,
            description=desc_r.value,
            is_active=is_active,
            _attribute_schema=schema_list,
        ))
```

Add `FieldError` import to the top of the file:

```python
from app.domain.shared.field_error import FieldError
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/unit/domain/catalog/test_resource_type.py -v -k create`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/domain/catalog/resource_type.py tests/unit/domain/catalog/test_resource_type.py
git commit -m "$(cat <<'EOF'
refactor(catalog): ResourceType.create emits FieldError list

Drops the "; "-join. DUPLICATE_ATTRIBUTE_KEY uses field="attribute_schema"
so clients can highlight the array. Tests switch to (field, code)
tuple assertions and gain a multi-field aggregation case.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Migrate `ResourceType.update_metadata`

**Files:**
- Modify: `app/domain/catalog/resource_type.py:74-110` (the `update_metadata` method)
- Modify: `tests/unit/domain/catalog/test_resource_type.py` (the `update_metadata` tests)

- [ ] **Step 1: Update tests**

Find the tests exercising `update_metadata` failure paths and switch their assertions to the `r.details` pattern. Field map: name → `"name"`, description → `"description"`. Add a multi-field test:

```python
def test_resource_type_update_metadata_aggregates_failures():
    rt = _build_valid_resource_type()  # use the existing fixture/helper if present
    r = rt.update_metadata(name="", description="x" * (ShortDescription.MAX_LENGTH + 1))
    assert r.is_failure
    assert r.error is None
    assert r.details is not None
    codes = {(e.field, e.code) for e in r.details}
    assert ("name", Name.NAME_CANNOT_BE_EMPTY) in codes
    assert ("description", ShortDescription.SHORT_DESCRIPTION_CANNOT_BE_GREATER_THAN_MAX_LENGTH) in codes
```

If there is no `_build_valid_resource_type` helper, inline a minimal valid construction:
```python
rt = ResourceType.create(slug="quadra", name="Quadra", description="ok", attribute_schema=[]).value
```

- [ ] **Step 2: Run the relevant tests to verify they fail**

Run: `.venv/bin/pytest tests/unit/domain/catalog/test_resource_type.py -v -k update_metadata`
Expected: FAIL.

- [ ] **Step 3: Migrate `update_metadata`**

In `app/domain/catalog/resource_type.py`, replace the body of `update_metadata` (lines 74-110) with:

```python
        if name is None and description is None:
            return Result.success(None)

        errors: list[FieldError] = []
        new_name = self.name
        new_desc = self.description

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

        if errors:
            return Result.failure_many(errors)

        self.name = new_name
        self.description = new_desc
        self.updated_at = _utcnow()
        return Result.success(None)
```

Update the docstring's "semicolon-joined" reference to mention the new envelope shape, or simply remove the implementation note and leave only the contract description.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/unit/domain/catalog/test_resource_type.py -v -k update_metadata`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/domain/catalog/resource_type.py tests/unit/domain/catalog/test_resource_type.py
git commit -m "$(cat <<'EOF'
refactor(catalog): ResourceType.update_metadata emits FieldError list

Same migration as ResourceType.create. Returns Result[None] failure with
details on aggregate validation; success unchanged.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: Migrate `ResourceType.replace_attribute_schema`

**Files:**
- Modify: `app/domain/catalog/resource_type.py:112-119` (the `replace_attribute_schema` method)
- Modify: `tests/unit/domain/catalog/test_resource_type.py` (the `replace_attribute_schema` tests)

- [ ] **Step 1: Update tests**

Find the test asserting `r.error == ResourceType.DUPLICATE_ATTRIBUTE_KEY` for `replace_attribute_schema` (around line 141 — the one outside the `create` context). Switch it to:

```python
    assert r.is_failure
    assert r.error is None
    assert r.details is not None
    codes = {(e.field, e.code) for e in r.details}
    assert ("attribute_schema", ResourceType.DUPLICATE_ATTRIBUTE_KEY) in codes
```

- [ ] **Step 2: Run the relevant test to verify it fails**

Run: `.venv/bin/pytest tests/unit/domain/catalog/test_resource_type.py -v -k replace_attribute_schema`
Expected: FAIL.

- [ ] **Step 3: Migrate `replace_attribute_schema`**

In `app/domain/catalog/resource_type.py`, replace the body of `replace_attribute_schema` (lines 112-119) with:

```python
        defs = list(definitions)
        if self._has_duplicate_keys(defs):
            return Result.failure_many([
                FieldError(code=self.DUPLICATE_ATTRIBUTE_KEY, field="attribute_schema"),
            ])
        self._attribute_schema = defs
        self.updated_at = _utcnow()
        return Result.success(None)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/unit/domain/catalog/test_resource_type.py -v -k replace_attribute_schema`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/domain/catalog/resource_type.py tests/unit/domain/catalog/test_resource_type.py
git commit -m "$(cat <<'EOF'
refactor(catalog): replace_attribute_schema uses failure_many for shape consistency

Single-error today, but emitting via failure_many of one keeps the
response envelope shape consistent with ResourceType.create.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: Migrate `ResourceType.validate_attributes` (drops colon-suffix)

**Files:**
- Modify: `app/domain/catalog/resource_type.py:129-166` (the `validate_attributes` method)
- Modify: `tests/unit/domain/catalog/test_resource_type.py` (the `validate_attributes` tests, roughly lines 160-220)

- [ ] **Step 1: Update tests**

For tests asserting on the colon-suffix encoding (e.g., `assert ResourceType.REQUIRED_ATTRIBUTE_MISSING in r.error` plus `assert "players" in r.error`), switch to:

```python
    assert r.is_failure
    assert r.error is None
    assert r.details is not None
    codes = {(e.field, e.code) for e in r.details}
    assert ("players", ResourceType.REQUIRED_ATTRIBUTE_MISSING) in codes
```

Apply the same pattern to `UNKNOWN_ATTRIBUTE_KEY`, `ATTRIBUTE_TYPE_MISMATCH`, `ATTRIBUTE_ENUM_VALUE_NOT_ALLOWED` tests. The dynamic attribute key (e.g., `"players"`, `"surface_type"`) is now the `field` value of the `FieldError`.

- [ ] **Step 2: Run the relevant tests to verify they fail**

Run: `.venv/bin/pytest tests/unit/domain/catalog/test_resource_type.py -v -k validate_attributes`
Expected: FAIL.

- [ ] **Step 3: Migrate `validate_attributes`**

In `app/domain/catalog/resource_type.py`, replace the body of `validate_attributes` (lines 129-166) with:

```python
        errors: list[FieldError] = []
        defs_by_key = {d.key.value: d for d in self._attribute_schema}

        # Required attributes must be present.
        for d in self._attribute_schema:
            if d.required and d.key.value not in values:
                errors.append(FieldError(
                    code=self.REQUIRED_ATTRIBUTE_MISSING,
                    field=d.key.value,
                ))

        for key, value in values.items():
            d = defs_by_key.get(key)
            if d is None:
                errors.append(FieldError(code=self.UNKNOWN_ATTRIBUTE_KEY, field=key))
                continue

            if d.data_type == AttrType.STRING:
                if not isinstance(value, str):
                    errors.append(FieldError(code=self.ATTRIBUTE_TYPE_MISMATCH, field=key))
            elif d.data_type == AttrType.INT:
                # bool is a subclass of int; reject explicitly.
                if isinstance(value, bool) or not isinstance(value, int):
                    errors.append(FieldError(code=self.ATTRIBUTE_TYPE_MISMATCH, field=key))
            elif d.data_type == AttrType.BOOL:
                if not isinstance(value, bool):
                    errors.append(FieldError(code=self.ATTRIBUTE_TYPE_MISMATCH, field=key))
            elif d.data_type == AttrType.ENUM:
                allowed = {v.value for v in (d.enum_values or ())}
                if not isinstance(value, str) or value not in allowed:
                    errors.append(FieldError(
                        code=self.ATTRIBUTE_ENUM_VALUE_NOT_ALLOWED,
                        field=key,
                    ))

        if errors:
            return Result.failure_many(errors)
        return Result.success(None)
```

Update the method docstring: replace the "Returns aggregated errors as semicolon-joined codes." line with "Returns aggregated errors as `Result.failure_many` of `FieldError`, one per failing attribute key.".

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/unit/domain/catalog/test_resource_type.py -v -k validate_attributes`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/domain/catalog/resource_type.py tests/unit/domain/catalog/test_resource_type.py
git commit -m "$(cat <<'EOF'
refactor(catalog): validate_attributes drops colon-suffix encoding

Each attribute failure becomes FieldError(code=..., field=<attr_key>).
The dynamic attribute key (which used to ride along as a "<code>:<key>"
suffix) is now first-class metadata on the structured error.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 9: `RegisterUserHandler` re-wrap via `from_failure`

**Files:**
- Modify: `app/use_cases/accounts/commands/register_user.py:55-56`

- [ ] **Step 1: Run the existing test suite for this handler to check baseline**

Run: `.venv/bin/pytest tests/unit/use_cases/accounts/commands/test_register_user.py -v`
Expected: all PASS (the previous tasks did not touch this handler's interface).

After Task 4, `User.create` returns `Result.failure_many(...)` with `details` populated, so the handler currently re-wraps with `Result.failure(user_r.error, status_code=422)` — but `user_r.error` is `None` when `details` is set. That breaks the handler in production. The unit tests may not catch this if they only assert on `is_failure` / `status_code`. Read through `tests/unit/use_cases/accounts/commands/test_register_user.py` and add a test if the multi-field path isn't covered:

```python
async def test_register_user_propagates_user_create_details():
    handler = RegisterUserHandler(users=_FakeUsersRepo(), hasher=_FakeHasher())
    cmd = RegisterUserCommand(
        email="not-an-email",
        password="strongpass1",
        role=Role.CUSTOMER,
        full_name="",
        phone=None,
    )
    r = await handler.handle(cmd)
    assert r.is_failure
    assert r.status_code == 422
    assert r.error is None
    assert r.details is not None
    codes = {(e.field, e.code) for e in r.details}
    assert ("email", "EmailInvalidFormat") in codes
    assert ("full_name", "NameCannotBeEmpty") in codes
```

(Adjust imports / fixture names to match the existing test file's helpers.)

- [ ] **Step 2: Run the new test to verify it fails**

Run: `.venv/bin/pytest tests/unit/use_cases/accounts/commands/test_register_user.py::test_register_user_propagates_user_create_details -v`
Expected: FAIL because the handler currently re-wraps via `Result.failure(user_r.error, ...)` which raises (or returns a result with `error="None"`).

- [ ] **Step 3: Update the handler**

In `app/use_cases/accounts/commands/register_user.py`, replace lines 55-56:

```python
        if user_r.is_failure:
            return Result.failure(user_r.error, status_code=422)
```

with:

```python
        if user_r.is_failure:
            return Result.from_failure(user_r, status_code=422)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/unit/use_cases/accounts/commands/test_register_user.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/use_cases/accounts/commands/register_user.py tests/unit/use_cases/accounts/commands/test_register_user.py
git commit -m "$(cat <<'EOF'
fix(accounts): RegisterUserHandler preserves details via from_failure

User.create now emits failure_many; the handler must re-wrap via
Result.from_failure to preserve r.details across the Result[User] →
Result[UserDto] type change.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 10: Migrate `CreateResourceTypeHandler.handle`

**Files:**
- Modify: `app/use_cases/catalog/commands/create_resource_type.py`
- Modify: `tests/unit/use_cases/catalog/commands/test_create_resource_type.py`

- [ ] **Step 1: Update tests**

Find the test at line 43 (`assert "SlugInvalidFormat" in r.error`) — that's a pass-through from `ResourceType.create`. Switch to:

```python
    assert r.is_failure
    assert r.error is None
    assert r.details is not None
    codes = {(e.field, e.code) for e in r.details}
    assert ("slug", Slug.SLUG_INVALID_FORMAT) in codes
```

(The `assert r.error == "SlugAlreadyTaken"` test at line 52 is a single-error repository failure path — leave it untouched.)

Add a new test exercising the handler's own aggregation (the `AttributeDefinition.create` loop and `InvalidDataType` branch):

```python
async def test_create_resource_type_aggregates_attribute_schema_failures():
    handler = CreateResourceTypeHandler(repo=_FakeRepo())
    cmd = CreateResourceTypeCommand(
        slug="quadra",
        name="Quadra",
        description="ok",
        attribute_schema=[
            {"data_type": "not-a-type", "key": "x", "label": "X"},
            {"data_type": "string", "key": "BAD KEY", "label": "Y"},
        ],
    )
    r = await handler.handle(cmd)
    assert r.is_failure
    assert r.status_code == 400
    assert r.error is None
    assert r.details is not None
    codes = {(e.field, e.code) for e in r.details}
    assert ("attribute_schema[0].data_type", "InvalidDataType") in codes
    # Second item: AttributeKey will reject "BAD KEY" (uppercase + space) → ATTRIBUTE_KEY_INVALID_FORMAT
    assert any(e.field == "attribute_schema[1]" for e in r.details)
```

(Adjust the second assertion's expected code if `AttributeDefinition.create` emits a different one for that input — check the VO's behavior.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/unit/use_cases/catalog/commands/test_create_resource_type.py -v`
Expected: the migrated tests FAIL.

- [ ] **Step 3: Migrate the handler**

In `app/use_cases/catalog/commands/create_resource_type.py`, replace the `handle` method body with:

```python
    async def handle(self, cmd: CreateResourceTypeCommand) -> Result[ResourceTypeDto]:
        defs: list[AttributeDefinition] = []
        errors: list[FieldError] = []
        for idx, raw in enumerate(cmd.attribute_schema):
            try:
                dt = AttrType(raw["data_type"])
            except ValueError:
                errors.append(FieldError(
                    code="InvalidDataType",
                    field=f"attribute_schema[{idx}].data_type",
                ))
                continue
            r = AttributeDefinition.create(
                key=raw["key"],
                label=raw["label"],
                data_type=dt,
                required=raw.get("required", False),
                enum_values=raw.get("enum_values"),
            )
            if r.is_failure:
                errors.append(FieldError(code=r.error, field=f"attribute_schema[{idx}]"))
            else:
                defs.append(r.value)

        if errors:
            return Result.failure_many(errors, status_code=400)

        rt_r = ResourceType.create(
            slug=cmd.slug,
            name=cmd.name,
            description=cmd.description,
            attribute_schema=defs,
            is_active=cmd.is_active,
        )
        if rt_r.is_failure:
            return Result.from_failure(rt_r, status_code=400)

        add_r = await self._repo.add(rt_r.value)
        if add_r.is_failure:
            return Result.failure(add_r.error, status_code=add_r.status_code or 409)

        return Result.success(ResourceTypeDto.from_entity(rt_r.value))
```

Add the import at the top:

```python
from app.domain.shared.field_error import FieldError
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/unit/use_cases/catalog/commands/test_create_resource_type.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/use_cases/catalog/commands/create_resource_type.py tests/unit/use_cases/catalog/commands/test_create_resource_type.py
git commit -m "$(cat <<'EOF'
refactor(catalog): CreateResourceTypeHandler aggregates via FieldError

Per-element AttributeDefinition.create failures and InvalidDataType
branch use field="attribute_schema[<idx>]..." paths. ResourceType.create
re-wrap goes through Result.from_failure to preserve upstream details.
Repo failures stay flat (infrastructure errors, not validation).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 11: Migrate `UpdateResourceTypeHandler.handle`

**Files:**
- Modify: `app/use_cases/catalog/commands/update_resource_type.py`
- Modify: `tests/unit/use_cases/catalog/commands/test_update_resource_type.py`

- [ ] **Step 1: Update tests**

Apply the same migration pattern as Task 10 to any test that asserts substring on `r.error` for the handler's aggregation paths or for `update_metadata` / `replace_attribute_schema` pass-through. Add a multi-field aggregation test if one isn't already present (the handler aggregates `AttributeDefinition.create` failures over `cmd.attribute_schema`; mirror Task 10's new test).

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/unit/use_cases/catalog/commands/test_update_resource_type.py -v`
Expected: migrated tests FAIL.

- [ ] **Step 3: Migrate the handler**

In `app/use_cases/catalog/commands/update_resource_type.py`, replace the body of `handle` with:

```python
    async def handle(self, cmd: UpdateResourceTypeCommand) -> Result[ResourceTypeDto]:
        rt = await self._repo.get_by_id(cmd.id)
        if rt is None:
            return Result.failure("ResourceTypeNotFound", status_code=404)

        if cmd.name is not None or cmd.description is not None:
            metadata_r = rt.update_metadata(name=cmd.name, description=cmd.description)
            if metadata_r.is_failure:
                return Result.from_failure(metadata_r, status_code=400)

        if cmd.attribute_schema is not None:
            defs: list[AttributeDefinition] = []
            errors: list[FieldError] = []
            for idx, raw in enumerate(cmd.attribute_schema):
                try:
                    dt = AttrType(raw["data_type"])
                except ValueError:
                    errors.append(FieldError(
                        code="InvalidDataType",
                        field=f"attribute_schema[{idx}].data_type",
                    ))
                    continue
                r = AttributeDefinition.create(
                    key=raw["key"],
                    label=raw["label"],
                    data_type=dt,
                    required=raw.get("required", False),
                    enum_values=raw.get("enum_values"),
                )
                if r.is_failure:
                    errors.append(FieldError(code=r.error, field=f"attribute_schema[{idx}]"))
                else:
                    defs.append(r.value)

            if errors:
                return Result.failure_many(errors, status_code=400)

            replace_r = rt.replace_attribute_schema(defs)
            if replace_r.is_failure:
                return Result.from_failure(replace_r, status_code=400)

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

Add the `FieldError` import at the top of the file:

```python
from app.domain.shared.field_error import FieldError
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/unit/use_cases/catalog/commands/test_update_resource_type.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/use_cases/catalog/commands/update_resource_type.py tests/unit/use_cases/catalog/commands/test_update_resource_type.py
git commit -m "$(cat <<'EOF'
refactor(catalog): UpdateResourceTypeHandler aggregates via FieldError

Mirrors CreateResourceTypeHandler. update_metadata and
replace_attribute_schema re-wraps go through Result.from_failure.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 12: E2E test for the envelope contract

**Files:**
- Modify: `tests/e2e/catalog/test_admin_and_public_flow.py`

- [ ] **Step 1: Add a failing test that demonstrates the envelope shape**

Append to `tests/e2e/catalog/test_admin_and_public_flow.py`:

```python
async def test_admin_create_resource_type_emits_validation_envelope_for_multiple_invalid_fields(
    admin_client,
):
    response = await admin_client.post(
        "/v1/admin/resource-types",
        json={
            "slug": "BAD slug",
            "name": "",
            "description": "x" * 1000,  # exceeds ShortDescription.MAX_LENGTH
            "attribute_schema": [],
            "is_active": True,
        },
    )
    assert response.status_code == 400
    body = response.json()["detail"]
    assert body["code"] == "ValidationFailed"
    assert body["message"] == "Falha de validação."
    fields = {d["field"] for d in body["details"]}
    assert {"slug", "name", "description"}.issubset(fields)
    # Each detail entry has the full structured shape.
    for entry in body["details"]:
        assert set(entry.keys()) == {"field", "code", "message"}
        assert entry["code"]
        assert entry["message"]
```

(Adapt `admin_client` and any required setup to match the existing fixtures in this file. If the file uses a different client fixture name or auth setup, mirror that — do not invent a new fixture.)

- [ ] **Step 2: Run the test to verify it passes**

Run: `.venv/bin/pytest tests/e2e/catalog/test_admin_and_public_flow.py -v`
Expected: PASS (Tasks 3, 5, and 10 already wired the behavior end-to-end; this test only asserts it).

If the test fails, that's a real signal — investigate the response body before adjusting the test.

- [ ] **Step 3: Commit**

```bash
git add tests/e2e/catalog/test_admin_and_public_flow.py
git commit -m "$(cat <<'EOF'
test(e2e): assert ValidationFailed envelope shape on admin POST

Three invalid fields → status 400, code "ValidationFailed", details
array with one entry per failing field.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 13: Final verification

**Files:** none modified — verification only.

- [ ] **Step 1: Verify no leftover joined strings in domain or use_cases**

Run: `grep -rn '"; "' app/domain app/use_cases`
Expected: empty output. (Any hit means an aggregator was missed.)

- [ ] **Step 2: Verify no leftover colon-suffix codes**

Run: `grep -rEn 'f"\{[^}]*\}:\{' app/domain app/use_cases`
Expected: empty output. Any hit means a `f"<code>:<dynamic>"` pattern that should be a structured `FieldError` instead.

- [ ] **Step 3: Run the full test suite**

Run: `make test` (or `.venv/bin/pytest`)
Expected: full PASS, no skipped tests except those skipped in the baseline before this plan.

- [ ] **Step 4: Update memory follow-ups**

Edit `/Users/klayver/.claude/projects/-Users-klayver-Repositories-agentic-workbench-venue-backend/memory/project_open_followups.md`: move item 1 (the multi-error envelope note) from "Active items" to "Resolved items", referencing the merge commit / PR.

- [ ] **Step 5: Final commit (if memory was updated)**

The memory file is outside the repo — no commit needed for it. If the verification surfaces any leftover work, that becomes its own task; do not silently fold it into the last commit.

---

## Self-review notes

- All tasks reference `app/domain/shared/field_error.py` from Task 1; `Result.failure_many` / `Result.from_failure` from Task 2; the envelope branch in `unwrap` from Task 3. Order is enforced.
- No "implement later" / "TBD" steps. Each migration task includes the full replacement code block.
- Naming consistency: `failure_many`, `from_failure`, `FieldError(code, field)` are used identically in every task that references them.
- Task 9 explicitly notes that Tasks 4 + 9 together prevent a regression (Task 4 changes `User.create` to populate `details`; Task 9 fixes the handler to propagate it). If Task 4 lands without Task 9, register_user breaks in production. Land them in the same PR.
- Task 13 step 1 acts as a tripwire — if any aggregator was missed, the grep catches it.
