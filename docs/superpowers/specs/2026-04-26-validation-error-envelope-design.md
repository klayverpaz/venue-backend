# Validation Error Envelope — Design Doc

**Status:** Approved 2026-04-26.
**Author:** klayver + Claude (brainstorm session).
**Scope:** Slim cleanup before Plan 06. Structural — no business-rule changes.

## 1. Motivation

The `Result[T]` type emits failure as a single `error: str | None`. Aggregate roots that validate multiple fields (`User.create`, `ResourceType.create`, `ResourceType.update_metadata`, `ResourceType.validate_attributes`) currently concatenate per-field codes with `"; "` and stuff the joined string back into `Result.failure(...)`.

The HTTP boundary in `app/api/error_handler.py:unwrap()` reads `result.error` and uses it both as the response `code` and as the input to `translate(code)`. When the error is a joined string like `"NameCannotBeEmpty; PhoneInvalidLength"`, neither field works:

```json
{"detail": {"code": "NameCannotBeEmpty; PhoneInvalidLength",
            "message": "NameCannotBeEmpty; PhoneInvalidLength"}}
```

That's neither a usable code (impossible to switch on) nor a localized message. Spec decision 15 envisioned **one stable code per response**; aggregator joining was never reconciled with the HTTP contract.

This bites hardest in Plan 06 (`Resource.create`), which aggregates `Slug + Name + ShortDescription + WeeklySchedule + PricingRule + base_attributes + custom_attributes`. Plan 06 must not start without this fixed.

## 2. Scope

### In scope

- New VO `FieldError(code, field)` in `app/domain/shared/`.
- `Result[T]` gains a parallel field `details: tuple[FieldError, ...] | None`.
- New factories: `Result.failure_many(errors, status_code=None)` and `Result.from_failure(other, status_code=None)`.
- `unwrap()` emits a `ValidationFailed` envelope when `result.details` is populated.
- Migrate the aggregators that currently use `"; "`-join, plus one for shape consistency:
  - `User.create`
  - `ResourceType.create`
  - `ResourceType.update_metadata`
  - `ResourceType.validate_attributes` (also drops the `code:field` colon-suffix encoding)
  - `ResourceType.replace_attribute_schema` (single-error today; switch to `failure_many` of one for shape consistency)
- `RegisterUserHandler` re-wrap of `User.create` failure switches to `Result.from_failure(...)` to preserve `details`.
- `ERROR_MESSAGES_PT_BR` gains `"ValidationFailed"`.
- Architecture test (`test_error_code_coverage.py`) gets `"ValidationFailed"` added to `handler_level_allowlist`.
- Test migration: ~15 unit-test asserts switch from `"<code>" in r.error` to inspecting `r.details`. One new e2e test demonstrates the envelope with multiple `details`.

### Out of scope (deliberate)

- Raw-pt-BR strings emitted by `RegisterUserHandler` for 403 / 422 / 409 (e.g., `"Não é permitido registrar contas admin..."`). Those are a separate "handler-level codes are also unstable" problem; they roll into Plan 05 polish, where new handler-level codes (`SubscriptionAlreadyActive`, etc.) are introduced anyway.
- Nested aggregator composition (e.g., `Resource.create` calling `WeeklySchedule.create` which is itself an aggregator). Plan 06 decides the prefix/flatten policy when it lands.
- The optional architecture-test heuristic tightening (follow-up #2 in `project_open_followups.md`).
- Adding `message` to `FieldError`. Domain stays language-free; pt-BR lives only in `error_codes.py`.

## 3. Domain shape

### 3.1 `FieldError` VO

`app/domain/shared/field_error.py` (new file):

```python
from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class FieldError:
    code: str
    field: str | None = None
```

- `code` — stable identifier emitted by VOs and aggregates (e.g., `"EmailInvalidFormat"`, `"DuplicateAttributeKey"`).
- `field` — the aggregate's field that failed validation (`"email"`, `"phone"`, `"attribute_schema"`, or a dynamic key like `"bedrooms"` for `validate_attributes`). `None` when the rule is aggregate-wide and no single field is responsible.
- No `message`. pt-BR translation happens at the HTTP boundary via `translate(code)`.

### 3.2 `Result[T]` extension

`app/domain/shared/result.py`:

```python
@dataclass(frozen=True, slots=True)
class Result(Generic[T]):
    is_success: bool
    value: Optional[T] = None
    error: Optional[str] = None
    details: Optional[tuple[FieldError, ...]] = None   # NEW
    status_code: Optional[int] = None

    def __post_init__(self) -> None:
        if self.is_success:
            if self.error is not None or self.details is not None:
                raise ValueError("Successful result cannot carry error/details.")
        else:
            if self.value is not None:
                raise ValueError("Failed result cannot carry value.")
            if (self.error is None) == (self.details is None):
                raise ValueError(
                    "Failed result must have exactly one of error or details."
                )

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
```

**Invariant:** a failure has **exactly one** of `error` or `details` set. `failure_many` rejects empty input. The existing `Result.failure(...)` path is unchanged for VOs and single-error handler emissions.

## 4. HTTP boundary

### 4.1 `unwrap()` — envelope dispatch

`app/api/error_handler.py:unwrap()`:

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

**Default status code** when `details` is set and `status_code` is `None` is **400** (Bad Request), aligning with the existing convention in the e2e catalog test (`test_admin_and_public_flow.py` asserts 400 on `SlugInvalidFormat`). Aggregators that need a different code pass it explicitly.

### 4.2 Response contract

| Path | Response body |
|---|---|
| Aggregate failure (`details` populated) | `{"detail": {"code": "ValidationFailed", "message": "Falha de validação.", "details": [{"field": ..., "code": ..., "message": ...}, ...]}}` |
| Single-code failure (`error` populated) | `{"detail": {"code": "<code>", "message": "<pt-BR>"}}` (unchanged) |

Client rule: when `detail.code == "ValidationFailed"`, read `detail.details`. Otherwise read `detail.code` + `detail.message` directly.

### 4.3 `error_codes.py`

Add to `ERROR_MESSAGES_PT_BR`:

```python
"ValidationFailed": "Falha de validação.",
```

## 5. Aggregator migration

### 5.1 `User.create` — `app/domain/accounts/user.py`

Replace the `errors: list[str]` accumulator with `list[FieldError]`. Field map: `email` → `"email"`, `full_name` → `"full_name"`, `password_hash` → `"password_hash"`, `phone` → `"phone"`. The handler-emitted code `"PasswordHashCannotBeEmpty"` keeps its current spelling. Final emission: `Result.failure_many(errors)` (no status_code — handler will set it via `from_failure`).

### 5.2 `ResourceType.create` — `app/domain/catalog/resource_type.py`

Field map: `slug` → `"slug"`, `name` → `"name"`, `description` → `"description"`. `DUPLICATE_ATTRIBUTE_KEY` uses `field="attribute_schema"` (more useful for clients than `None` — they can highlight the array).

### 5.3 `ResourceType.update_metadata`

Field map: `name`, `description`. Returns `Result[None]` on failure via `failure_many`.

### 5.4 `ResourceType.replace_attribute_schema`

Single-error today. Switches to `Result.failure_many([FieldError(code=DUPLICATE_ATTRIBUTE_KEY, field="attribute_schema")])` for shape consistency with `ResourceType.create`.

### 5.5 `ResourceType.validate_attributes`

Drop the `f"{CODE}:{key}"` colon-suffix encoding entirely. Each error becomes a `FieldError(code=CODE, field=key)` where `key` is the dynamic attribute name (`"bedrooms"`, `"surface_type"`, etc.).

### 5.6 `RegisterUserHandler`

`register_user.py:55-56` switches from:

```python
if user_r.is_failure:
    return Result.failure(user_r.error, status_code=422)
```

to:

```python
if user_r.is_failure:
    return Result.from_failure(user_r, status_code=422)
```

The other three `Result.failure(...)` calls in this handler stay as-is (raw-pt-BR strings — out of scope, see §2).

### 5.7 Cross-aggregate handlers (`CreateResourceTypeHandler`, `UpdateResourceTypeHandler`)

Inspect during implementation. If they re-wrap `ResourceType.create` / `update_metadata` / `replace_attribute_schema` failures with a different `Result[T]` type or different `status_code`, switch to `Result.from_failure(...)`. Otherwise no change.

## 6. Test migration

### 6.1 Pattern

Before:
```python
assert "EmailInvalidFormat" in r.error
```

After:
```python
assert r.error is None
assert r.details is not None
codes_by_field = {(e.field, e.code) for e in r.details}
assert ("email", "EmailInvalidFormat") in codes_by_field
```

For tests that only verify a code appeared without caring about the field:
```python
assert any(e.code == Slug.SLUG_INVALID_FORMAT for e in r.details)
```

### 6.2 Affected files

- `tests/unit/domain/accounts/test_user.py` — ~5 asserts.
- `tests/unit/domain/catalog/test_resource_type.py` — ~10 asserts. Note: the existing assertion `"players" in r.error` was a workaround for the colon-suffix encoding; it becomes `assert any(e.field == "players" for e in r.details)`.
- `tests/unit/use_cases/catalog/commands/test_create_resource_type.py` — 1 assert.
- `tests/unit/use_cases/accounts/commands/test_register_user.py` — verify; likely no change since the handler currently asserts only on status code.

### 6.3 New tests

- **Unit:** at least one test per migrated aggregator demonstrating multi-field aggregation (e.g., `test_user_create_aggregates_email_and_phone_failures`).
- **E2E:** add to `tests/e2e/catalog/test_admin_and_public_flow.py` (or sibling) one POST with three invalid fields, asserting:
  ```python
  assert response.status_code == 400
  body = response.json()["detail"]
  assert body["code"] == "ValidationFailed"
  fields = {d["field"] for d in body["details"]}
  assert fields == {"slug", "name", "description"}
  ```

## 7. Architecture test impact

`tests/unit/architecture/test_error_code_coverage.py`:
- Add `"ValidationFailed"` to `handler_level_allowlist` in `test_no_orphan_translations_in_mapping` (it's not a VO constant).
- The existing aggregate-level codes (`DUPLICATE_ATTRIBUTE_KEY`, `REQUIRED_ATTRIBUTE_MISSING`, etc.) remain class constants on `ResourceType` and stay in the allowlist — only their *use site* changes (no more colon-suffix concatenation).

The optional heuristic tightening (open-followup #2) stays out of scope.

## 8. Migration strategy

Single PR, slim. Order of operations within the plan:

1. Add `FieldError` VO + tests.
2. Extend `Result` (`details`, `failure_many`, `from_failure`) + tests.
3. Update `unwrap()` + `error_codes.py` + arch test allowlist.
4. Migrate `User.create` + tests.
5. Migrate `ResourceType.{create, update_metadata, replace_attribute_schema, validate_attributes}` + tests.
6. Update `RegisterUserHandler` re-wrap.
7. Inspect catalog handlers; update if needed.
8. Add e2e test demonstrating envelope with multiple details.
9. Run full test suite. Verify no `; ` joined strings remain in domain code (`grep -r '"; "' app/domain` should be empty).

The plan is expected to be small — single session, single PR, single review pass.

## 9. Follow-ups (post-merge)

- Once merged, mark open-followup item #1 as resolved in `project_open_followups.md`.
- Plan 05 (subscriptions) inherits the new convention: aggregators use `failure_many`, single-error stays `failure`, handler-level raw-pt-BR strings get cleaned up alongside Plan 05's new codes.
