# Plan 03 — Value Object Foundation + Accounts Retrofit

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship 12 new shared Value Objects (`Slug`, `Name`, `ShortName`, `ShortDescription`, `AttributeKey`, `Money`, `TimeWindow`, `DateTimeRange`, `IanaTimezone`, `SlotDuration`, `CancellationCutoff`, `RatingScore`), refactor the two existing VOs (`Email`, `BrazilianPhone`) to use stable error code identifiers (per spec §3 decision 15), wire a code → pt-BR mapping into `app/api/error_handler.py`, retrofit `User.full_name: str → Name`, and reset Alembic migrations to a single fresh migration that reflects the VO-aware mapping.

**Architecture:** Every VO follows the spec §4.3 convention: `@dataclass(frozen=True, slots=True)` inheriting `BaseValueObject`, public factory `cls.create(raw) -> Result[Self]`, error messages as class-level stable code constants (e.g., `Name.NAME_CANNOT_BE_EMPTY = "NameCannotBeEmpty"`), bounds (`MAX_LENGTH`, etc.) as class constants, `_validate(...) -> str` private static returning the code or empty string. String VOs strip on entry. Composite VOs (`TimeWindow`, `DateTimeRange`) follow the same pattern with multiple fields; equality is free from `frozen=True`. The HTTP boundary in `app/api/error_handler.py` reads `result.error` (a code) and renders the pt-BR message via a central mapping in `app/api/error_codes.py`. An architecture test enforces 1:1 coverage so a new code without a translation fails CI. Accounts retrofit is mechanical: `User.full_name: str → Name`, `UserModel.full_name: VARCHAR(200) → Text`, regenerate migrations.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2.0 async, Alembic, asyncpg, aiosqlite (tests), pytest, pytest-asyncio, ruff, mypy. New stdlib usage: `zoneinfo` (Python 3.9+) for `IanaTimezone`, `decimal` for `Money.to_decimal()` display helper.

---

## Branch and worktree

Branch: `feat/plan-03-vo-foundation`. Worktree recommended but not required — the plan touches `app/domain/shared/value_objects/`, `app/api/`, `app/domain/accounts/`, `app/infrastructure/db/mappings/user.py`, and `app/migrations/versions/` only. No conflicts with `main` while in flight.

```bash
git checkout -b feat/plan-03-vo-foundation
```

All tasks below assume this branch is checked out.

---

## File structure

### New files

```
app/domain/shared/value_objects/
├── slug.py                          # Slug VO
├── name.py                          # Name VO (max 500)
├── short_name.py                    # ShortName VO (max 40)
├── short_description.py             # ShortDescription VO (max 500)
├── attribute_key.py                 # AttributeKey VO (snake_case, max 50)
├── money.py                         # Money VO (int cents)
├── time_window.py                   # TimeWindow composite VO (time, time)
├── date_time_range.py               # DateTimeRange composite VO (datetime UTC, datetime UTC)
├── iana_timezone.py                 # IanaTimezone VO
├── slot_duration.py                 # SlotDuration VO (∈ {30,45,60,90,120})
├── cancellation_cutoff.py           # CancellationCutoff VO (0..168 hours)
└── rating_score.py                  # RatingScore VO (1..5)

app/api/
└── error_codes.py                   # central code → pt-BR mapping

tests/unit/domain/shared/value_objects/
├── test_slug.py
├── test_name.py
├── test_short_name.py
├── test_short_description.py
├── test_attribute_key.py
├── test_money.py
├── test_time_window.py
├── test_date_time_range.py
├── test_iana_timezone.py
├── test_slot_duration.py
├── test_cancellation_cutoff.py
└── test_rating_score.py

tests/unit/architecture/
└── test_error_code_coverage.py      # asserts every VO error code is in error_codes.ERROR_MESSAGES_PT_BR
```

### Modified files

```
app/domain/shared/value_objects/email.py            # refactor to stable codes
app/domain/shared/value_objects/brazilian_phone.py  # refactor to stable codes
app/domain/accounts/user.py                         # full_name: str → Name
app/infrastructure/db/mappings/user.py              # full_name: VARCHAR(200) → Text
app/api/error_handler.py                            # use error_codes mapping in unwrap()

tests/unit/domain/shared/value_objects/test_email.py            # update assertions to codes
tests/unit/domain/shared/value_objects/test_brazilian_phone.py  # update assertions to codes
tests/unit/domain/accounts/test_user.py                         # update for Name VO
```

### Deleted files

```
app/domain/shared/value_objects/non_negative_float.py
tests/unit/domain/shared/value_objects/test_non_negative_float.py
app/migrations/versions/20260424_1638_initial_users_table.py
app/migrations/versions/20260425_1414_accounts_users_schema.py
```

A single fresh migration is generated at the end of the plan.

---

## Execution Plan — 7 Units

| Unit | Tasks | Approx commits |
|---|---|---|
| **A** | Refactor existing VOs + delete unused | 3 |
| **B** | String VOs (5: Slug, Name, ShortName, ShortDescription, AttributeKey) | 5 |
| **C** | Numeric VOs (4: Money, RatingScore, SlotDuration, CancellationCutoff) | 4 |
| **D** | Special VOs (3: IanaTimezone, TimeWindow, DateTimeRange) | 3 |
| **E** | Error code → pt-BR mapping + architecture test | 3 |
| **F** | Accounts retrofit + migration reset | 3 |
| **G** | Final verification + push | 1 |

Total: **~22 commits**.

---

## UNIT A — Refactor existing VOs + delete unused

### Task A1 — Delete `NonNegativeFloat`

`NonNegativeFloat` has no consumers in `app/` (verified via grep — only its own test file references it). Per spec §4.3 "Removed/renamed", drop it.

**Files:**
- Delete: `app/domain/shared/value_objects/non_negative_float.py`
- Delete: `tests/unit/domain/shared/value_objects/test_non_negative_float.py`

- [ ] **Step 1: Confirm no production consumers**

```bash
grep -rn "NonNegativeFloat\|non_negative_float" app/
```

Expected: zero matches (consumers are only in `tests/unit/domain/shared/value_objects/test_non_negative_float.py`, which is also deleted).

- [ ] **Step 2: Delete the files**

```bash
rm app/domain/shared/value_objects/non_negative_float.py
rm tests/unit/domain/shared/value_objects/test_non_negative_float.py
```

- [ ] **Step 3: Run the test suite**

```bash
.venv/bin/pytest -q
```

Expected: green (we only removed an unused VO and its tests).

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "$(cat <<'EOF'
chore(domain): remove unused NonNegativeFloat VO

Per spec §4.3, monetary values flow exclusively through Money (int
cents); the legacy NonNegativeFloat had no production consumer. Drop
it and its test.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task A2 — Refactor `Email` to stable error codes

Replace interpolated strings (e.g., `f"Email inválido: '{raw}'."`) with stable code constants. Add a `MAX_LENGTH = 254` class constant. Add a `create_if_not_empty(raw) -> Result[Self | None]` companion. Tests assert on the code constants.

**Files:**
- Modify: `app/domain/shared/value_objects/email.py`
- Modify: `tests/unit/domain/shared/value_objects/test_email.py`

- [ ] **Step 1: Rewrite the test file**

`tests/unit/domain/shared/value_objects/test_email.py`:

```python
from __future__ import annotations
from app.domain.shared.value_objects.email import Email


def test_email_create_success_lowercases_and_strips():
    r = Email.create("  USER@Example.COM  ")
    assert r.is_success
    assert r.value.value == "user@example.com"
    assert str(r.value) == "user@example.com"


def test_email_create_rejects_none():
    r = Email.create(None)
    assert r.is_failure
    assert r.error == Email.EMAIL_CANNOT_BE_EMPTY


def test_email_create_rejects_empty():
    r = Email.create("")
    assert r.is_failure
    assert r.error == Email.EMAIL_CANNOT_BE_EMPTY


def test_email_create_rejects_whitespace_only():
    r = Email.create("   ")
    assert r.is_failure
    assert r.error == Email.EMAIL_CANNOT_BE_EMPTY


def test_email_create_rejects_non_string():
    r = Email.create(123)
    assert r.is_failure
    assert r.error == Email.EMAIL_CANNOT_BE_EMPTY


def test_email_create_rejects_invalid_format():
    for bad in ["no-at-sign", "@nodomain.com", "user@", "user@nodot"]:
        r = Email.create(bad)
        assert r.is_failure, f"expected failure for {bad!r}"
        assert r.error == Email.EMAIL_INVALID_FORMAT


def test_email_create_rejects_over_max_length():
    over = "a" * 250 + "@x.io"   # 255 chars
    r = Email.create(over)
    assert r.is_failure
    assert r.error == Email.EMAIL_CANNOT_BE_GREATER_THAN_MAX_LENGTH


def test_email_create_if_not_empty_returns_none_for_blank():
    for blank in [None, "", "   "]:
        r = Email.create_if_not_empty(blank)
        assert r.is_success
        assert r.value is None


def test_email_create_if_not_empty_validates_when_provided():
    r = Email.create_if_not_empty("user@example.com")
    assert r.is_success
    assert r.value is not None
    assert r.value.value == "user@example.com"


def test_email_create_if_not_empty_propagates_failure():
    r = Email.create_if_not_empty("not-an-email")
    assert r.is_failure
    assert r.error == Email.EMAIL_INVALID_FORMAT
```

- [ ] **Step 2: Run the tests — they will fail**

```bash
.venv/bin/pytest tests/unit/domain/shared/value_objects/test_email.py -v
```

Expected: failures (constants `EMAIL_CANNOT_BE_EMPTY`, `EMAIL_INVALID_FORMAT`, `EMAIL_CANNOT_BE_GREATER_THAN_MAX_LENGTH`, `create_if_not_empty` don't exist yet).

- [ ] **Step 3: Rewrite the VO**

`app/domain/shared/value_objects/email.py`:

```python
from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Self
from app.domain.shared.result import Result
from app.domain.shared.value_object import BaseValueObject

_EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")


@dataclass(frozen=True, slots=True)
class Email(BaseValueObject):
    EMAIL_CANNOT_BE_EMPTY = "EmailCannotBeEmpty"
    EMAIL_INVALID_FORMAT = "EmailInvalidFormat"
    EMAIL_CANNOT_BE_GREATER_THAN_MAX_LENGTH = "EmailCannotBeGreaterThanMaxLength"
    MAX_LENGTH = 254

    value: str  # always lowercase, no surrounding whitespace

    @classmethod
    def create(cls, raw) -> Result[Self]:
        err = cls._validate(raw)
        if err:
            return Result.failure(err)
        normalized = raw.strip().lower()
        return Result.success(cls(value=normalized))

    @classmethod
    def create_if_not_empty(cls, raw) -> Result[Self | None]:
        if raw is None or (isinstance(raw, str) and not raw.strip()):
            return Result.success(None)
        return cls.create(raw)

    @staticmethod
    def _validate(raw) -> str:
        if raw is None or not isinstance(raw, str):
            return Email.EMAIL_CANNOT_BE_EMPTY
        normalized = raw.strip().lower()
        if not normalized:
            return Email.EMAIL_CANNOT_BE_EMPTY
        if len(normalized) > Email.MAX_LENGTH:
            return Email.EMAIL_CANNOT_BE_GREATER_THAN_MAX_LENGTH
        if not _EMAIL_RE.match(normalized):
            return Email.EMAIL_INVALID_FORMAT
        return ""

    def __str__(self) -> str:
        return self.value
```

- [ ] **Step 4: Run tests — green**

```bash
.venv/bin/pytest tests/unit/domain/shared/value_objects/test_email.py -v
```

Expected: all tests pass.

- [ ] **Step 5: Run the full suite to ensure no other test depended on the old error string**

```bash
.venv/bin/pytest -q
```

Expected: green. If any test in `tests/unit/domain/accounts/` or `tests/integration/accounts/` substring-matches old messages like `"Email: valor obrigatório"`, fix them to assert on the new code constant instead. Re-run.

- [ ] **Step 6: Commit**

```bash
git add app/domain/shared/value_objects/email.py tests/unit/domain/shared/value_objects/test_email.py
# include any accounts test edits required by step 5
git add tests/
git commit -m "$(cat <<'EOF'
refactor(vo): convert Email to stable error code identifiers

Replace interpolated error strings ("Email: valor obrigatório.") with
class-level stable codes (EmailCannotBeEmpty, EmailInvalidFormat,
EmailCannotBeGreaterThanMaxLength) per spec §3 decision 15. Add
MAX_LENGTH=254 constant and create_if_not_empty() companion. Tests now
assert on the code constants, not substrings.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task A3 — Refactor `BrazilianPhone` to stable error codes

Same treatment as `Email`: replace interpolated strings with stable codes.

**Files:**
- Modify: `app/domain/shared/value_objects/brazilian_phone.py`
- Modify: `tests/unit/domain/shared/value_objects/test_brazilian_phone.py`

- [ ] **Step 1: Rewrite the test file**

`tests/unit/domain/shared/value_objects/test_brazilian_phone.py`:

```python
from __future__ import annotations
from app.domain.shared.value_objects.brazilian_phone import BrazilianPhone


def test_phone_mobile_e164_parsing():
    r = BrazilianPhone.create("+55 21 99694-9389")
    assert r.is_success
    assert r.value.value == "+5521996949389"
    assert r.value.is_mobile is True
    assert r.value.ddd == "21"


def test_phone_landline_parsing():
    r = BrazilianPhone.create("(11) 3333-4444")
    assert r.is_success
    assert r.value.is_mobile is False


def test_phone_rejects_none():
    r = BrazilianPhone.create(None)
    assert r.is_failure
    assert r.error == BrazilianPhone.PHONE_CANNOT_BE_EMPTY


def test_phone_rejects_non_string():
    r = BrazilianPhone.create(12345)
    assert r.is_failure
    assert r.error == BrazilianPhone.PHONE_CANNOT_BE_EMPTY


def test_phone_rejects_alpha_chars():
    r = BrazilianPhone.create("11 99999-9999 ext 100")
    assert r.is_failure
    assert r.error == BrazilianPhone.PHONE_CONTAINS_INVALID_CHARACTERS


def test_phone_rejects_no_digits():
    r = BrazilianPhone.create("()-")
    assert r.is_failure
    assert r.error == BrazilianPhone.PHONE_HAS_NO_DIGITS


def test_phone_rejects_wrong_length():
    r = BrazilianPhone.create("12345")
    assert r.is_failure
    assert r.error == BrazilianPhone.PHONE_INVALID_LENGTH


def test_phone_rejects_invalid_ddd():
    r = BrazilianPhone.create("(10) 99999-9999")
    assert r.is_failure
    assert r.error == BrazilianPhone.PHONE_INVALID_DDD


def test_phone_mobile_must_start_with_9():
    r = BrazilianPhone.create("(11) 8888-9999")  # 10 digits — landline; first digit valid (8 not in 2-7)
    assert r.is_failure
    assert r.error == BrazilianPhone.PHONE_LANDLINE_MUST_START_WITH_2_TO_7


def test_phone_create_if_not_empty_returns_none_for_blank():
    for blank in [None, "", "   "]:
        r = BrazilianPhone.create_if_not_empty(blank)
        assert r.is_success
        assert r.value is None


def test_phone_create_if_not_empty_propagates_failure():
    r = BrazilianPhone.create_if_not_empty("no digits")
    assert r.is_failure
```

- [ ] **Step 2: Run tests — fail**

```bash
.venv/bin/pytest tests/unit/domain/shared/value_objects/test_brazilian_phone.py -v
```

Expected: failures (codes don't exist yet).

- [ ] **Step 3: Rewrite the VO**

`app/domain/shared/value_objects/brazilian_phone.py`:

```python
from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Self
from app.domain.shared.result import Result
from app.domain.shared.value_object import BaseValueObject

_DIGITS_RE = re.compile(r"\D+")
_VALID_DDDS = {
    11, 12, 13, 14, 15, 16, 17, 18, 19,
    21, 22, 24, 27, 28,
    31, 32, 33, 34, 35, 37, 38,
    41, 42, 43, 44, 45, 46, 47, 48, 49,
    51, 53, 54, 55,
    61, 62, 63, 64, 65, 66, 67, 68, 69,
    71, 73, 74, 75, 77, 79,
    81, 82, 83, 84, 85, 86, 87, 88, 89,
    91, 92, 93, 94, 95, 96, 97, 98, 99,
}


@dataclass(frozen=True, slots=True)
class BrazilianPhone(BaseValueObject):
    PHONE_CANNOT_BE_EMPTY = "PhoneCannotBeEmpty"
    PHONE_CONTAINS_INVALID_CHARACTERS = "PhoneContainsInvalidCharacters"
    PHONE_HAS_NO_DIGITS = "PhoneHasNoDigits"
    PHONE_INVALID_LENGTH = "PhoneInvalidLength"
    PHONE_INVALID_DDD = "PhoneInvalidDdd"
    PHONE_MOBILE_MUST_START_WITH_9 = "PhoneMobileMustStartWith9"
    PHONE_LANDLINE_MUST_START_WITH_2_TO_7 = "PhoneLandlineMustStartWith2To7"

    value: str           # E.164: "+5521996949389"
    is_mobile: bool

    @classmethod
    def create(cls, raw) -> Result[Self]:
        if raw is None or not isinstance(raw, str):
            return Result.failure(cls.PHONE_CANNOT_BE_EMPTY)
        if re.search(r"[a-zA-Z]", raw):
            return Result.failure(cls.PHONE_CONTAINS_INVALID_CHARACTERS)
        digits = _DIGITS_RE.sub("", raw)
        if not digits:
            return Result.failure(cls.PHONE_HAS_NO_DIGITS)
        if len(digits) in (12, 13) and digits.startswith("55"):
            digits = digits[2:]
        if len(digits) not in (10, 11):
            return Result.failure(cls.PHONE_INVALID_LENGTH)
        ddd = int(digits[:2])
        if ddd not in _VALID_DDDS:
            return Result.failure(cls.PHONE_INVALID_DDD)
        is_mobile = len(digits) == 11
        if is_mobile and digits[2] != "9":
            return Result.failure(cls.PHONE_MOBILE_MUST_START_WITH_9)
        if not is_mobile and digits[2] not in "234567":
            return Result.failure(cls.PHONE_LANDLINE_MUST_START_WITH_2_TO_7)
        return Result.success(cls(value=f"+55{digits}", is_mobile=is_mobile))

    @classmethod
    def create_if_not_empty(cls, raw) -> Result[Self | None]:
        if raw is None or (isinstance(raw, str) and not raw.strip()):
            return Result.success(None)
        return cls.create(raw)

    @property
    def ddd(self) -> str:
        return self.value[3:5]

    @property
    def national(self) -> str:
        rest = self.value[5:]
        if self.is_mobile:
            return f"({self.ddd}) {rest[:5]}-{rest[5:]}"
        return f"({self.ddd}) {rest[:4]}-{rest[4:]}"

    def __str__(self) -> str:
        return self.value
```

- [ ] **Step 4: Run tests — green**

```bash
.venv/bin/pytest tests/unit/domain/shared/value_objects/test_brazilian_phone.py -v
```

Expected: all pass.

- [ ] **Step 5: Run the full suite**

```bash
.venv/bin/pytest -q
```

Expected: green. Fix any accounts test that substring-matched old strings (analogous to A2 step 5).

- [ ] **Step 6: Commit**

```bash
git add app/domain/shared/value_objects/brazilian_phone.py tests/
git commit -m "$(cat <<'EOF'
refactor(vo): convert BrazilianPhone to stable error code identifiers

Replace interpolated error strings with class-level stable codes
(PhoneCannotBeEmpty, PhoneInvalidDdd, PhoneMobileMustStartWith9, etc.)
per spec §3 decision 15. Add create_if_not_empty() companion. Tests
assert on code constants.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## UNIT B — String VOs

### Task B1 — `Slug`

Slugs are kebab-case identifiers used in public URLs. Pattern: `^[a-z][a-z0-9-]*[a-z0-9]$`, no `--` consecutive, no leading/trailing dash, lowercase-on-create after strip. Length 2..80.

**Files:**
- Create: `app/domain/shared/value_objects/slug.py`
- Create: `tests/unit/domain/shared/value_objects/test_slug.py`

- [ ] **Step 1: Failing test**

`tests/unit/domain/shared/value_objects/test_slug.py`:

```python
from __future__ import annotations
from app.domain.shared.value_objects.slug import Slug


def test_slug_create_success_lowercase_and_strip():
    r = Slug.create("  Football-Field  ")
    assert r.is_success
    assert r.value.value == "football-field"
    assert str(r.value) == "football-field"


def test_slug_rejects_none():
    r = Slug.create(None)
    assert r.is_failure
    assert r.error == Slug.SLUG_CANNOT_BE_EMPTY


def test_slug_rejects_empty():
    r = Slug.create("")
    assert r.is_failure
    assert r.error == Slug.SLUG_CANNOT_BE_EMPTY


def test_slug_rejects_too_short():
    r = Slug.create("a")
    assert r.is_failure
    assert r.error == Slug.SLUG_INVALID_FORMAT


def test_slug_rejects_too_long():
    r = Slug.create("a" + "b" * 80)  # 81 chars
    assert r.is_failure
    assert r.error == Slug.SLUG_CANNOT_BE_GREATER_THAN_MAX_LENGTH


def test_slug_rejects_invalid_chars():
    for bad in ["foo bar", "foo_bar", "foo.bar", "foo!bar", "ção", "Foo--bar".replace("F", "")]:
        r = Slug.create(bad)
        assert r.is_failure, f"expected failure for {bad!r}"


def test_slug_rejects_leading_or_trailing_dash():
    assert Slug.create("-foo").error == Slug.SLUG_INVALID_FORMAT
    assert Slug.create("foo-").error == Slug.SLUG_INVALID_FORMAT


def test_slug_rejects_consecutive_dashes():
    r = Slug.create("foo--bar")
    assert r.is_failure
    assert r.error == Slug.SLUG_INVALID_FORMAT


def test_slug_rejects_leading_digit():
    r = Slug.create("1foo")
    assert r.is_failure
    assert r.error == Slug.SLUG_INVALID_FORMAT


def test_slug_accepts_digits_after_first_char():
    r = Slug.create("field-1")
    assert r.is_success
    assert r.value.value == "field-1"


def test_slug_create_if_not_empty_returns_none_for_blank():
    for blank in [None, "", "   "]:
        r = Slug.create_if_not_empty(blank)
        assert r.is_success
        assert r.value is None


def test_slug_create_if_not_empty_propagates_failure():
    r = Slug.create_if_not_empty("Invalid Slug!")
    assert r.is_failure
```

- [ ] **Step 2: Run — fail**

```bash
.venv/bin/pytest tests/unit/domain/shared/value_objects/test_slug.py -v
```

Expected: ImportError (slug.py doesn't exist).

- [ ] **Step 3: Implementation**

`app/domain/shared/value_objects/slug.py`:

```python
from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Self
from app.domain.shared.result import Result
from app.domain.shared.value_object import BaseValueObject

_SLUG_RE = re.compile(r"^[a-z][a-z0-9-]*[a-z0-9]$")
_DOUBLE_DASH_RE = re.compile(r"--")


@dataclass(frozen=True, slots=True)
class Slug(BaseValueObject):
    SLUG_CANNOT_BE_EMPTY = "SlugCannotBeEmpty"
    SLUG_INVALID_FORMAT = "SlugInvalidFormat"
    SLUG_CANNOT_BE_GREATER_THAN_MAX_LENGTH = "SlugCannotBeGreaterThanMaxLength"
    MIN_LENGTH = 2
    MAX_LENGTH = 80

    value: str

    @classmethod
    def create(cls, raw) -> Result[Self]:
        err = cls._validate(raw)
        if err:
            return Result.failure(err)
        return Result.success(cls(value=raw.strip().lower()))

    @classmethod
    def create_if_not_empty(cls, raw) -> Result[Self | None]:
        if raw is None or (isinstance(raw, str) and not raw.strip()):
            return Result.success(None)
        return cls.create(raw)

    @staticmethod
    def _validate(raw) -> str:
        if raw is None or not isinstance(raw, str):
            return Slug.SLUG_CANNOT_BE_EMPTY
        s = raw.strip().lower()
        if not s:
            return Slug.SLUG_CANNOT_BE_EMPTY
        if len(s) > Slug.MAX_LENGTH:
            return Slug.SLUG_CANNOT_BE_GREATER_THAN_MAX_LENGTH
        if len(s) < Slug.MIN_LENGTH:
            return Slug.SLUG_INVALID_FORMAT
        if _DOUBLE_DASH_RE.search(s):
            return Slug.SLUG_INVALID_FORMAT
        if not _SLUG_RE.match(s):
            return Slug.SLUG_INVALID_FORMAT
        return ""

    def __str__(self) -> str:
        return self.value
```

- [ ] **Step 4: Run — green**

```bash
.venv/bin/pytest tests/unit/domain/shared/value_objects/test_slug.py -v
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add app/domain/shared/value_objects/slug.py tests/unit/domain/shared/value_objects/test_slug.py
git commit -m "$(cat <<'EOF'
feat(vo): add Slug value object

Kebab-case identifier for public URLs. Strict: lowercase letters,
digits, hyphens; no leading/trailing/consecutive hyphens; first char
must be a letter. Length 2..80. Used by future ResourceType.slug and
Resource.slug per spec §4.3.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task B2 — `Name`

Long name VO, max 500 chars. Used for `User.full_name`, `ResourceType.name`, `Resource.name`, `Resource.city`, `Resource.region`. Strip on entry. Reject control characters (`\n`, `\r`, `\t`, `\x00`–`\x1f`).

**Files:**
- Create: `app/domain/shared/value_objects/name.py`
- Create: `tests/unit/domain/shared/value_objects/test_name.py`

- [ ] **Step 1: Failing test**

`tests/unit/domain/shared/value_objects/test_name.py`:

```python
from __future__ import annotations
from app.domain.shared.value_objects.name import Name


def test_name_create_success():
    r = Name.create("  Arena Mané Garrincha — Campo 1  ")
    assert r.is_success
    assert r.value.value == "Arena Mané Garrincha — Campo 1"
    assert str(r.value) == "Arena Mané Garrincha — Campo 1"


def test_name_rejects_none():
    r = Name.create(None)
    assert r.is_failure
    assert r.error == Name.NAME_CANNOT_BE_EMPTY


def test_name_rejects_empty():
    r = Name.create("")
    assert r.is_failure
    assert r.error == Name.NAME_CANNOT_BE_EMPTY


def test_name_rejects_whitespace_only():
    r = Name.create("   ")
    assert r.is_failure
    assert r.error == Name.NAME_CANNOT_BE_EMPTY


def test_name_rejects_too_long():
    r = Name.create("a" * 501)
    assert r.is_failure
    assert r.error == Name.NAME_CANNOT_BE_GREATER_THAN_MAX_LENGTH


def test_name_accepts_max_length():
    r = Name.create("a" * 500)
    assert r.is_success


def test_name_rejects_control_chars():
    for bad in ["foo\nbar", "foo\rbar", "foo\tbar", "foo\x00bar"]:
        r = Name.create(bad)
        assert r.is_failure, f"expected failure for {bad!r}"
        assert r.error == Name.NAME_CONTAINS_INVALID_CHARACTERS


def test_name_create_if_not_empty_returns_none_for_blank():
    for blank in [None, "", "   "]:
        r = Name.create_if_not_empty(blank)
        assert r.is_success
        assert r.value is None
```

- [ ] **Step 2: Run — fail**

```bash
.venv/bin/pytest tests/unit/domain/shared/value_objects/test_name.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implementation**

`app/domain/shared/value_objects/name.py`:

```python
from __future__ import annotations
from dataclasses import dataclass
from typing import Self
from app.domain.shared.result import Result
from app.domain.shared.value_object import BaseValueObject


@dataclass(frozen=True, slots=True)
class Name(BaseValueObject):
    NAME_CANNOT_BE_EMPTY = "NameCannotBeEmpty"
    NAME_CANNOT_BE_GREATER_THAN_MAX_LENGTH = "NameCannotBeGreaterThanMaxLength"
    NAME_CONTAINS_INVALID_CHARACTERS = "NameContainsInvalidCharacters"
    MAX_LENGTH = 500

    value: str

    @classmethod
    def create(cls, raw) -> Result[Self]:
        err = cls._validate(raw)
        if err:
            return Result.failure(err)
        return Result.success(cls(value=raw.strip()))

    @classmethod
    def create_if_not_empty(cls, raw) -> Result[Self | None]:
        if raw is None or (isinstance(raw, str) and not raw.strip()):
            return Result.success(None)
        return cls.create(raw)

    @staticmethod
    def _validate(raw) -> str:
        if raw is None or not isinstance(raw, str):
            return Name.NAME_CANNOT_BE_EMPTY
        s = raw.strip()
        if not s:
            return Name.NAME_CANNOT_BE_EMPTY
        if len(s) > Name.MAX_LENGTH:
            return Name.NAME_CANNOT_BE_GREATER_THAN_MAX_LENGTH
        for ch in s:
            if ord(ch) < 0x20:
                return Name.NAME_CONTAINS_INVALID_CHARACTERS
        return ""

    def __str__(self) -> str:
        return self.value
```

- [ ] **Step 4: Run — green**

```bash
.venv/bin/pytest tests/unit/domain/shared/value_objects/test_name.py -v
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add app/domain/shared/value_objects/name.py tests/unit/domain/shared/value_objects/test_name.py
git commit -m "$(cat <<'EOF'
feat(vo): add Name value object (max 500)

Long-form name VO used for User.full_name, ResourceType.name,
Resource.name, Resource.city, Resource.region (per spec §4.3).
Strips on entry, rejects control chars (< 0x20).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task B3 — `ShortName`

Short name VO, max 40 chars. Used for `AttributeDefinition.label`, `CustomAttribute.label`, entries in `AttributeDefinition.enum_values`. Same validation shape as `Name` but with smaller max.

**Files:**
- Create: `app/domain/shared/value_objects/short_name.py`
- Create: `tests/unit/domain/shared/value_objects/test_short_name.py`

- [ ] **Step 1: Failing test**

`tests/unit/domain/shared/value_objects/test_short_name.py`:

```python
from __future__ import annotations
from app.domain.shared.value_objects.short_name import ShortName


def test_short_name_create_success():
    r = ShortName.create("  Tamanho do campo  ")
    assert r.is_success
    assert r.value.value == "Tamanho do campo"


def test_short_name_rejects_none():
    r = ShortName.create(None)
    assert r.is_failure
    assert r.error == ShortName.SHORT_NAME_CANNOT_BE_EMPTY


def test_short_name_rejects_empty():
    r = ShortName.create("")
    assert r.is_failure
    assert r.error == ShortName.SHORT_NAME_CANNOT_BE_EMPTY


def test_short_name_rejects_too_long():
    r = ShortName.create("a" * 41)
    assert r.is_failure
    assert r.error == ShortName.SHORT_NAME_CANNOT_BE_GREATER_THAN_MAX_LENGTH


def test_short_name_accepts_max_length():
    r = ShortName.create("a" * 40)
    assert r.is_success


def test_short_name_rejects_control_chars():
    r = ShortName.create("foo\nbar")
    assert r.is_failure
    assert r.error == ShortName.SHORT_NAME_CONTAINS_INVALID_CHARACTERS


def test_short_name_create_if_not_empty_returns_none_for_blank():
    for blank in [None, "", "   "]:
        r = ShortName.create_if_not_empty(blank)
        assert r.is_success
        assert r.value is None
```

- [ ] **Step 2: Run — fail**

```bash
.venv/bin/pytest tests/unit/domain/shared/value_objects/test_short_name.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implementation**

`app/domain/shared/value_objects/short_name.py`:

```python
from __future__ import annotations
from dataclasses import dataclass
from typing import Self
from app.domain.shared.result import Result
from app.domain.shared.value_object import BaseValueObject


@dataclass(frozen=True, slots=True)
class ShortName(BaseValueObject):
    SHORT_NAME_CANNOT_BE_EMPTY = "ShortNameCannotBeEmpty"
    SHORT_NAME_CANNOT_BE_GREATER_THAN_MAX_LENGTH = "ShortNameCannotBeGreaterThanMaxLength"
    SHORT_NAME_CONTAINS_INVALID_CHARACTERS = "ShortNameContainsInvalidCharacters"
    MAX_LENGTH = 40

    value: str

    @classmethod
    def create(cls, raw) -> Result[Self]:
        err = cls._validate(raw)
        if err:
            return Result.failure(err)
        return Result.success(cls(value=raw.strip()))

    @classmethod
    def create_if_not_empty(cls, raw) -> Result[Self | None]:
        if raw is None or (isinstance(raw, str) and not raw.strip()):
            return Result.success(None)
        return cls.create(raw)

    @staticmethod
    def _validate(raw) -> str:
        if raw is None or not isinstance(raw, str):
            return ShortName.SHORT_NAME_CANNOT_BE_EMPTY
        s = raw.strip()
        if not s:
            return ShortName.SHORT_NAME_CANNOT_BE_EMPTY
        if len(s) > ShortName.MAX_LENGTH:
            return ShortName.SHORT_NAME_CANNOT_BE_GREATER_THAN_MAX_LENGTH
        for ch in s:
            if ord(ch) < 0x20:
                return ShortName.SHORT_NAME_CONTAINS_INVALID_CHARACTERS
        return ""

    def __str__(self) -> str:
        return self.value
```

- [ ] **Step 4: Run — green**

```bash
.venv/bin/pytest tests/unit/domain/shared/value_objects/test_short_name.py -v
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add app/domain/shared/value_objects/short_name.py tests/unit/domain/shared/value_objects/test_short_name.py
git commit -m "$(cat <<'EOF'
feat(vo): add ShortName value object (max 40)

Short label VO used for AttributeDefinition.label, CustomAttribute.label,
and entries in AttributeDefinition.enum_values per spec §4.3.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task B4 — `ShortDescription`

Description VO, max 500 chars. Used for `ResourceType.description`, `Resource.description`, `Booking.customer_note`, `OwnerSubscription.notes`, `Rating.comment`. **Empty is allowed** — use `create()` always; `create_if_not_empty()` is provided but functionally equivalent to `create()` since empty is valid.

**Files:**
- Create: `app/domain/shared/value_objects/short_description.py`
- Create: `tests/unit/domain/shared/value_objects/test_short_description.py`

- [ ] **Step 1: Failing test**

`tests/unit/domain/shared/value_objects/test_short_description.py`:

```python
from __future__ import annotations
from app.domain.shared.value_objects.short_description import ShortDescription


def test_short_description_accepts_empty_string():
    r = ShortDescription.create("")
    assert r.is_success
    assert r.value.value == ""


def test_short_description_accepts_whitespace_only():
    r = ShortDescription.create("   ")
    assert r.is_success
    assert r.value.value == ""  # stripped


def test_short_description_accepts_text():
    r = ShortDescription.create("  Campo gramado, com vestiário e estacionamento.  ")
    assert r.is_success
    assert r.value.value == "Campo gramado, com vestiário e estacionamento."


def test_short_description_rejects_none():
    r = ShortDescription.create(None)
    assert r.is_failure
    assert r.error == ShortDescription.SHORT_DESCRIPTION_INVALID_TYPE


def test_short_description_rejects_too_long():
    r = ShortDescription.create("a" * 501)
    assert r.is_failure
    assert r.error == ShortDescription.SHORT_DESCRIPTION_CANNOT_BE_GREATER_THAN_MAX_LENGTH


def test_short_description_accepts_max_length():
    r = ShortDescription.create("a" * 500)
    assert r.is_success


def test_short_description_accepts_newlines_and_tabs():
    # Descriptions allow line breaks for readability.
    r = ShortDescription.create("Linha 1\nLinha 2\n\tIndentado")
    assert r.is_success
```

- [ ] **Step 2: Run — fail**

```bash
.venv/bin/pytest tests/unit/domain/shared/value_objects/test_short_description.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implementation**

`app/domain/shared/value_objects/short_description.py`:

```python
from __future__ import annotations
from dataclasses import dataclass
from typing import Self
from app.domain.shared.result import Result
from app.domain.shared.value_object import BaseValueObject


@dataclass(frozen=True, slots=True)
class ShortDescription(BaseValueObject):
    SHORT_DESCRIPTION_INVALID_TYPE = "ShortDescriptionInvalidType"
    SHORT_DESCRIPTION_CANNOT_BE_GREATER_THAN_MAX_LENGTH = "ShortDescriptionCannotBeGreaterThanMaxLength"
    MAX_LENGTH = 500

    value: str

    @classmethod
    def create(cls, raw) -> Result[Self]:
        err = cls._validate(raw)
        if err:
            return Result.failure(err)
        return Result.success(cls(value=raw.strip()))

    @classmethod
    def create_if_not_empty(cls, raw) -> Result[Self | None]:
        if raw is None or (isinstance(raw, str) and not raw.strip()):
            return Result.success(None)
        return cls.create(raw)

    @staticmethod
    def _validate(raw) -> str:
        if raw is None or not isinstance(raw, str):
            return ShortDescription.SHORT_DESCRIPTION_INVALID_TYPE
        s = raw.strip()
        if len(s) > ShortDescription.MAX_LENGTH:
            return ShortDescription.SHORT_DESCRIPTION_CANNOT_BE_GREATER_THAN_MAX_LENGTH
        return ""

    def __str__(self) -> str:
        return self.value
```

- [ ] **Step 4: Run — green**

```bash
.venv/bin/pytest tests/unit/domain/shared/value_objects/test_short_description.py -v
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add app/domain/shared/value_objects/short_description.py tests/unit/domain/shared/value_objects/test_short_description.py
git commit -m "$(cat <<'EOF'
feat(vo): add ShortDescription value object (max 500)

Body-text VO used for ResourceType.description, Resource.description,
Booking.customer_note, OwnerSubscription.notes, Rating.comment per
spec §4.3. Empty string is allowed; newlines and tabs are permitted
(unlike Name/ShortName).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task B5 — `AttributeKey`

Snake-case key for resource attribute definitions and values. Pattern: `^[a-z][a-z0-9_]*$`. Length 1..50. Distinct from `Slug` (kebab-case) — see spec §4.3.

**Files:**
- Create: `app/domain/shared/value_objects/attribute_key.py`
- Create: `tests/unit/domain/shared/value_objects/test_attribute_key.py`

- [ ] **Step 1: Failing test**

`tests/unit/domain/shared/value_objects/test_attribute_key.py`:

```python
from __future__ import annotations
from app.domain.shared.value_objects.attribute_key import AttributeKey


def test_attribute_key_create_success():
    r = AttributeKey.create("  field_size  ")
    assert r.is_success
    assert r.value.value == "field_size"


def test_attribute_key_rejects_none():
    r = AttributeKey.create(None)
    assert r.is_failure
    assert r.error == AttributeKey.ATTRIBUTE_KEY_CANNOT_BE_EMPTY


def test_attribute_key_rejects_empty():
    r = AttributeKey.create("")
    assert r.is_failure
    assert r.error == AttributeKey.ATTRIBUTE_KEY_CANNOT_BE_EMPTY


def test_attribute_key_rejects_too_long():
    r = AttributeKey.create("a" * 51)
    assert r.is_failure
    assert r.error == AttributeKey.ATTRIBUTE_KEY_CANNOT_BE_GREATER_THAN_MAX_LENGTH


def test_attribute_key_accepts_max_length():
    r = AttributeKey.create("a" * 50)
    assert r.is_success


def test_attribute_key_rejects_uppercase_or_kebab():
    for bad in ["FieldSize", "field-size", "field size", "1field", "_field", "field!", "ção"]:
        r = AttributeKey.create(bad)
        assert r.is_failure, f"expected failure for {bad!r}"
        assert r.error == AttributeKey.ATTRIBUTE_KEY_INVALID_FORMAT


def test_attribute_key_accepts_digits_after_first():
    r = AttributeKey.create("field_1")
    assert r.is_success
```

- [ ] **Step 2: Run — fail**

```bash
.venv/bin/pytest tests/unit/domain/shared/value_objects/test_attribute_key.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implementation**

`app/domain/shared/value_objects/attribute_key.py`:

```python
from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Self
from app.domain.shared.result import Result
from app.domain.shared.value_object import BaseValueObject

_KEY_RE = re.compile(r"^[a-z][a-z0-9_]*$")


@dataclass(frozen=True, slots=True)
class AttributeKey(BaseValueObject):
    ATTRIBUTE_KEY_CANNOT_BE_EMPTY = "AttributeKeyCannotBeEmpty"
    ATTRIBUTE_KEY_INVALID_FORMAT = "AttributeKeyInvalidFormat"
    ATTRIBUTE_KEY_CANNOT_BE_GREATER_THAN_MAX_LENGTH = "AttributeKeyCannotBeGreaterThanMaxLength"
    MAX_LENGTH = 50

    value: str

    @classmethod
    def create(cls, raw) -> Result[Self]:
        err = cls._validate(raw)
        if err:
            return Result.failure(err)
        return Result.success(cls(value=raw.strip()))

    @classmethod
    def create_if_not_empty(cls, raw) -> Result[Self | None]:
        if raw is None or (isinstance(raw, str) and not raw.strip()):
            return Result.success(None)
        return cls.create(raw)

    @staticmethod
    def _validate(raw) -> str:
        if raw is None or not isinstance(raw, str):
            return AttributeKey.ATTRIBUTE_KEY_CANNOT_BE_EMPTY
        s = raw.strip()
        if not s:
            return AttributeKey.ATTRIBUTE_KEY_CANNOT_BE_EMPTY
        if len(s) > AttributeKey.MAX_LENGTH:
            return AttributeKey.ATTRIBUTE_KEY_CANNOT_BE_GREATER_THAN_MAX_LENGTH
        if not _KEY_RE.match(s):
            return AttributeKey.ATTRIBUTE_KEY_INVALID_FORMAT
        return ""

    def __str__(self) -> str:
        return self.value
```

- [ ] **Step 4: Run — green**

```bash
.venv/bin/pytest tests/unit/domain/shared/value_objects/test_attribute_key.py -v
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add app/domain/shared/value_objects/attribute_key.py tests/unit/domain/shared/value_objects/test_attribute_key.py
git commit -m "$(cat <<'EOF'
feat(vo): add AttributeKey value object (snake_case, max 50)

Snake-case key for AttributeDefinition.key and CustomAttribute.key
per spec §4.3. Distinct from Slug (kebab-case): catalog attribute
keys are programmatic identifiers consumed in dict lookups, not
public URLs.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## UNIT C — Numeric VOs

### Task C1 — `Money`

Integer cents (smallest currency unit). Non-negative; max R$ 100M (10^10 cents). Helpers: `from_reais(reais, centavos=0)` factory and `to_decimal()` for display only (never used for arithmetic).

**Files:**
- Create: `app/domain/shared/value_objects/money.py`
- Create: `tests/unit/domain/shared/value_objects/test_money.py`

- [ ] **Step 1: Failing test**

`tests/unit/domain/shared/value_objects/test_money.py`:

```python
from __future__ import annotations
from decimal import Decimal
from app.domain.shared.value_objects.money import Money


def test_money_create_success_zero():
    r = Money.create(0)
    assert r.is_success
    assert r.value.cents == 0


def test_money_create_success_positive():
    r = Money.create(4990)
    assert r.is_success
    assert r.value.cents == 4990


def test_money_rejects_negative():
    r = Money.create(-1)
    assert r.is_failure
    assert r.error == Money.MONEY_CANNOT_BE_NEGATIVE


def test_money_rejects_above_max():
    r = Money.create(10**10 + 1)
    assert r.is_failure
    assert r.error == Money.MONEY_EXCEEDS_MAX


def test_money_accepts_max():
    r = Money.create(10**10)
    assert r.is_success


def test_money_rejects_non_int():
    for bad in [1.5, "100", None, True]:  # bool isn't usable as currency
        r = Money.create(bad)
        assert r.is_failure, f"expected failure for {bad!r}"
        assert r.error == Money.MONEY_INVALID_TYPE


def test_money_from_reais_success():
    r = Money.from_reais(49, 90)
    assert r.is_success
    assert r.value.cents == 4990


def test_money_from_reais_zero_centavos():
    r = Money.from_reais(100)
    assert r.is_success
    assert r.value.cents == 10000


def test_money_from_reais_rejects_negative_reais():
    r = Money.from_reais(-1, 0)
    assert r.is_failure
    assert r.error == Money.MONEY_CANNOT_BE_NEGATIVE


def test_money_from_reais_rejects_invalid_centavos():
    for bad_centavos in [-1, 100, 200]:
        r = Money.from_reais(10, bad_centavos)
        assert r.is_failure
        assert r.error == Money.MONEY_INVALID_CENTAVOS


def test_money_to_decimal_for_display():
    m = Money.create(4990).value
    assert m.to_decimal() == Decimal("49.90")


def test_money_str_brl_format():
    m = Money.create(4990).value
    assert str(m) == "R$ 49,90"


def test_money_equality_by_value():
    a = Money.create(4990).value
    b = Money.create(4990).value
    assert a == b
    assert hash(a) == hash(b)
```

- [ ] **Step 2: Run — fail**

```bash
.venv/bin/pytest tests/unit/domain/shared/value_objects/test_money.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implementation**

`app/domain/shared/value_objects/money.py`:

```python
from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal
from typing import Self
from app.domain.shared.result import Result
from app.domain.shared.value_object import BaseValueObject


@dataclass(frozen=True, slots=True)
class Money(BaseValueObject):
    MONEY_INVALID_TYPE = "MoneyInvalidType"
    MONEY_CANNOT_BE_NEGATIVE = "MoneyCannotBeNegative"
    MONEY_EXCEEDS_MAX = "MoneyExceedsMax"
    MONEY_INVALID_CENTAVOS = "MoneyInvalidCentavos"
    MAX_CENTS = 10_000_000_000  # R$ 100,000,000.00

    cents: int

    @classmethod
    def create(cls, cents) -> Result[Self]:
        # Reject bool (which is an int subclass) explicitly — money is never a flag.
        if isinstance(cents, bool) or not isinstance(cents, int):
            return Result.failure(cls.MONEY_INVALID_TYPE)
        if cents < 0:
            return Result.failure(cls.MONEY_CANNOT_BE_NEGATIVE)
        if cents > cls.MAX_CENTS:
            return Result.failure(cls.MONEY_EXCEEDS_MAX)
        return Result.success(cls(cents=cents))

    @classmethod
    def from_reais(cls, reais: int, centavos: int = 0) -> Result[Self]:
        if not isinstance(reais, int) or isinstance(reais, bool):
            return Result.failure(cls.MONEY_INVALID_TYPE)
        if not isinstance(centavos, int) or isinstance(centavos, bool):
            return Result.failure(cls.MONEY_INVALID_CENTAVOS)
        if reais < 0:
            return Result.failure(cls.MONEY_CANNOT_BE_NEGATIVE)
        if not 0 <= centavos < 100:
            return Result.failure(cls.MONEY_INVALID_CENTAVOS)
        return cls.create(reais * 100 + centavos)

    def to_decimal(self) -> Decimal:
        """For display only. Never use the result for arithmetic."""
        return Decimal(self.cents) / Decimal(100)

    def __str__(self) -> str:
        reais, cents = divmod(self.cents, 100)
        return f"R$ {reais},{cents:02d}"
```

- [ ] **Step 4: Run — green**

```bash
.venv/bin/pytest tests/unit/domain/shared/value_objects/test_money.py -v
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add app/domain/shared/value_objects/money.py tests/unit/domain/shared/value_objects/test_money.py
git commit -m "$(cat <<'EOF'
feat(vo): add Money value object (int cents, max R$ 100M)

Per spec §3 decision 16, monetary values are integer cents (smallest
currency unit). Float is forbidden — IEEE 754 cannot represent
0.10 exactly. Used by Resource.base_price_cents, PricingRule.price,
Booking.total_price_cents (spec §4.3). from_reais() factory accepts
human input ("R$ 49,90" → from_reais(49, 90)); to_decimal() is for
display only.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task C2 — `RatingScore`

Integer 1..5. Used by `Rating.score` (spec §5.7).

**Files:**
- Create: `app/domain/shared/value_objects/rating_score.py`
- Create: `tests/unit/domain/shared/value_objects/test_rating_score.py`

- [ ] **Step 1: Failing test**

`tests/unit/domain/shared/value_objects/test_rating_score.py`:

```python
from __future__ import annotations
from app.domain.shared.value_objects.rating_score import RatingScore


def test_rating_score_accepts_1_to_5():
    for n in [1, 2, 3, 4, 5]:
        r = RatingScore.create(n)
        assert r.is_success, f"failed for {n}"
        assert r.value.value == n


def test_rating_score_rejects_zero():
    r = RatingScore.create(0)
    assert r.is_failure
    assert r.error == RatingScore.RATING_SCORE_OUT_OF_RANGE


def test_rating_score_rejects_six():
    r = RatingScore.create(6)
    assert r.is_failure
    assert r.error == RatingScore.RATING_SCORE_OUT_OF_RANGE


def test_rating_score_rejects_negative():
    r = RatingScore.create(-1)
    assert r.is_failure
    assert r.error == RatingScore.RATING_SCORE_OUT_OF_RANGE


def test_rating_score_rejects_non_int():
    for bad in [None, 1.5, "5", True]:
        r = RatingScore.create(bad)
        assert r.is_failure, f"expected failure for {bad!r}"
        assert r.error == RatingScore.RATING_SCORE_INVALID_TYPE
```

- [ ] **Step 2: Run — fail**

```bash
.venv/bin/pytest tests/unit/domain/shared/value_objects/test_rating_score.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implementation**

`app/domain/shared/value_objects/rating_score.py`:

```python
from __future__ import annotations
from dataclasses import dataclass
from typing import Self
from app.domain.shared.result import Result
from app.domain.shared.value_object import BaseValueObject


@dataclass(frozen=True, slots=True)
class RatingScore(BaseValueObject):
    RATING_SCORE_INVALID_TYPE = "RatingScoreInvalidType"
    RATING_SCORE_OUT_OF_RANGE = "RatingScoreOutOfRange"
    MIN_VALUE = 1
    MAX_VALUE = 5

    value: int

    @classmethod
    def create(cls, raw) -> Result[Self]:
        if isinstance(raw, bool) or not isinstance(raw, int):
            return Result.failure(cls.RATING_SCORE_INVALID_TYPE)
        if not (cls.MIN_VALUE <= raw <= cls.MAX_VALUE):
            return Result.failure(cls.RATING_SCORE_OUT_OF_RANGE)
        return Result.success(cls(value=raw))
```

- [ ] **Step 4: Run — green**

```bash
.venv/bin/pytest tests/unit/domain/shared/value_objects/test_rating_score.py -v
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add app/domain/shared/value_objects/rating_score.py tests/unit/domain/shared/value_objects/test_rating_score.py
git commit -m "$(cat <<'EOF'
feat(vo): add RatingScore value object (int 1..5)

Per spec §5.7, ratings are whole stars 1 through 5. 0 means "not
rated" (absence of rating, not a value). Used by Rating.score in
the future ratings feature (Plan 09).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task C3 — `SlotDuration`

Integer minutes ∈ {30, 45, 60, 90, 120}. Used by `Resource.slot_duration_minutes` (spec §5.3).

**Files:**
- Create: `app/domain/shared/value_objects/slot_duration.py`
- Create: `tests/unit/domain/shared/value_objects/test_slot_duration.py`

- [ ] **Step 1: Failing test**

`tests/unit/domain/shared/value_objects/test_slot_duration.py`:

```python
from __future__ import annotations
from app.domain.shared.value_objects.slot_duration import SlotDuration


def test_slot_duration_accepts_allowed_values():
    for n in [30, 45, 60, 90, 120]:
        r = SlotDuration.create(n)
        assert r.is_success
        assert r.value.minutes == n


def test_slot_duration_rejects_unsupported():
    for bad in [10, 15, 25, 50, 75, 100, 150, 0, -30]:
        r = SlotDuration.create(bad)
        assert r.is_failure, f"expected failure for {bad}"
        assert r.error == SlotDuration.SLOT_DURATION_NOT_ALLOWED


def test_slot_duration_rejects_non_int():
    for bad in [None, 30.0, "60", True]:
        r = SlotDuration.create(bad)
        assert r.is_failure, f"expected failure for {bad!r}"
        assert r.error == SlotDuration.SLOT_DURATION_INVALID_TYPE


def test_slot_duration_allowed_set_exposed():
    assert SlotDuration.ALLOWED == frozenset({30, 45, 60, 90, 120})
```

- [ ] **Step 2: Run — fail**

```bash
.venv/bin/pytest tests/unit/domain/shared/value_objects/test_slot_duration.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implementation**

`app/domain/shared/value_objects/slot_duration.py`:

```python
from __future__ import annotations
from dataclasses import dataclass
from typing import Self
from app.domain.shared.result import Result
from app.domain.shared.value_object import BaseValueObject


@dataclass(frozen=True, slots=True)
class SlotDuration(BaseValueObject):
    SLOT_DURATION_INVALID_TYPE = "SlotDurationInvalidType"
    SLOT_DURATION_NOT_ALLOWED = "SlotDurationNotAllowed"
    ALLOWED: frozenset[int] = frozenset({30, 45, 60, 90, 120})

    minutes: int

    @classmethod
    def create(cls, raw) -> Result[Self]:
        if isinstance(raw, bool) or not isinstance(raw, int):
            return Result.failure(cls.SLOT_DURATION_INVALID_TYPE)
        if raw not in cls.ALLOWED:
            return Result.failure(cls.SLOT_DURATION_NOT_ALLOWED)
        return Result.success(cls(minutes=raw))
```

- [ ] **Step 4: Run — green**

```bash
.venv/bin/pytest tests/unit/domain/shared/value_objects/test_slot_duration.py -v
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add app/domain/shared/value_objects/slot_duration.py tests/unit/domain/shared/value_objects/test_slot_duration.py
git commit -m "$(cat <<'EOF'
feat(vo): add SlotDuration value object (∈ {30,45,60,90,120})

Per spec §5.3, owners pick from a fixed set of slot durations. The
constraint matches how this market actually prices ("by the hour" or
half-hour). Used by Resource.slot_duration_minutes (Plan 06).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task C4 — `CancellationCutoff`

Integer hours, range 0..168 (one week). Used by `Resource.customer_cancellation_cutoff_hours` (spec §5.3).

**Files:**
- Create: `app/domain/shared/value_objects/cancellation_cutoff.py`
- Create: `tests/unit/domain/shared/value_objects/test_cancellation_cutoff.py`

- [ ] **Step 1: Failing test**

`tests/unit/domain/shared/value_objects/test_cancellation_cutoff.py`:

```python
from __future__ import annotations
from app.domain.shared.value_objects.cancellation_cutoff import CancellationCutoff


def test_cutoff_accepts_zero():
    r = CancellationCutoff.create(0)
    assert r.is_success
    assert r.value.hours == 0


def test_cutoff_accepts_typical_24():
    r = CancellationCutoff.create(24)
    assert r.is_success
    assert r.value.hours == 24


def test_cutoff_accepts_max_168():
    r = CancellationCutoff.create(168)
    assert r.is_success


def test_cutoff_rejects_negative():
    r = CancellationCutoff.create(-1)
    assert r.is_failure
    assert r.error == CancellationCutoff.CANCELLATION_CUTOFF_OUT_OF_RANGE


def test_cutoff_rejects_above_max():
    r = CancellationCutoff.create(169)
    assert r.is_failure
    assert r.error == CancellationCutoff.CANCELLATION_CUTOFF_OUT_OF_RANGE


def test_cutoff_rejects_non_int():
    for bad in [None, 24.0, "24", True]:
        r = CancellationCutoff.create(bad)
        assert r.is_failure, f"expected failure for {bad!r}"
        assert r.error == CancellationCutoff.CANCELLATION_CUTOFF_INVALID_TYPE
```

- [ ] **Step 2: Run — fail**

```bash
.venv/bin/pytest tests/unit/domain/shared/value_objects/test_cancellation_cutoff.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implementation**

`app/domain/shared/value_objects/cancellation_cutoff.py`:

```python
from __future__ import annotations
from dataclasses import dataclass
from typing import Self
from app.domain.shared.result import Result
from app.domain.shared.value_object import BaseValueObject


@dataclass(frozen=True, slots=True)
class CancellationCutoff(BaseValueObject):
    CANCELLATION_CUTOFF_INVALID_TYPE = "CancellationCutoffInvalidType"
    CANCELLATION_CUTOFF_OUT_OF_RANGE = "CancellationCutoffOutOfRange"
    MIN_HOURS = 0
    MAX_HOURS = 168  # 1 week

    hours: int

    @classmethod
    def create(cls, raw) -> Result[Self]:
        if isinstance(raw, bool) or not isinstance(raw, int):
            return Result.failure(cls.CANCELLATION_CUTOFF_INVALID_TYPE)
        if not (cls.MIN_HOURS <= raw <= cls.MAX_HOURS):
            return Result.failure(cls.CANCELLATION_CUTOFF_OUT_OF_RANGE)
        return Result.success(cls(hours=raw))
```

- [ ] **Step 4: Run — green**

```bash
.venv/bin/pytest tests/unit/domain/shared/value_objects/test_cancellation_cutoff.py -v
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add app/domain/shared/value_objects/cancellation_cutoff.py tests/unit/domain/shared/value_objects/test_cancellation_cutoff.py
git commit -m "$(cat <<'EOF'
feat(vo): add CancellationCutoff value object (0..168 hours)

Per spec §5.3, an owner picks how many hours before slot start the
customer can no longer cancel. Range covers from "no cutoff" (0) to
one week (168). Used by Resource.customer_cancellation_cutoff_hours
(Plan 06).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## UNIT D — Special VOs

### Task D1 — `IanaTimezone`

String validated against `zoneinfo.available_timezones()`. Used by `Resource.timezone`.

**Files:**
- Create: `app/domain/shared/value_objects/iana_timezone.py`
- Create: `tests/unit/domain/shared/value_objects/test_iana_timezone.py`

- [ ] **Step 1: Failing test**

`tests/unit/domain/shared/value_objects/test_iana_timezone.py`:

```python
from __future__ import annotations
from app.domain.shared.value_objects.iana_timezone import IanaTimezone


def test_iana_tz_accepts_sao_paulo():
    r = IanaTimezone.create("America/Sao_Paulo")
    assert r.is_success
    assert r.value.value == "America/Sao_Paulo"
    assert str(r.value) == "America/Sao_Paulo"


def test_iana_tz_accepts_utc():
    r = IanaTimezone.create("UTC")
    assert r.is_success


def test_iana_tz_strips_whitespace():
    r = IanaTimezone.create("  America/Sao_Paulo  ")
    assert r.is_success
    assert r.value.value == "America/Sao_Paulo"


def test_iana_tz_rejects_unknown():
    r = IanaTimezone.create("Mars/Olympus")
    assert r.is_failure
    assert r.error == IanaTimezone.IANA_TIMEZONE_UNKNOWN


def test_iana_tz_rejects_empty():
    r = IanaTimezone.create("")
    assert r.is_failure
    assert r.error == IanaTimezone.IANA_TIMEZONE_CANNOT_BE_EMPTY


def test_iana_tz_rejects_none():
    r = IanaTimezone.create(None)
    assert r.is_failure
    assert r.error == IanaTimezone.IANA_TIMEZONE_CANNOT_BE_EMPTY


def test_iana_tz_rejects_non_string():
    r = IanaTimezone.create(123)
    assert r.is_failure
    assert r.error == IanaTimezone.IANA_TIMEZONE_CANNOT_BE_EMPTY


def test_iana_tz_to_zoneinfo_returns_valid_object():
    from zoneinfo import ZoneInfo
    tz = IanaTimezone.create("America/Sao_Paulo").value
    assert isinstance(tz.to_zoneinfo(), ZoneInfo)
```

- [ ] **Step 2: Run — fail**

```bash
.venv/bin/pytest tests/unit/domain/shared/value_objects/test_iana_timezone.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implementation**

`app/domain/shared/value_objects/iana_timezone.py`:

```python
from __future__ import annotations
from dataclasses import dataclass
from typing import Self
from zoneinfo import ZoneInfo, available_timezones
from app.domain.shared.result import Result
from app.domain.shared.value_object import BaseValueObject

# Cache the set once at import time. Stable per Python install.
_AVAILABLE = frozenset(available_timezones())


@dataclass(frozen=True, slots=True)
class IanaTimezone(BaseValueObject):
    IANA_TIMEZONE_CANNOT_BE_EMPTY = "IanaTimezoneCannotBeEmpty"
    IANA_TIMEZONE_UNKNOWN = "IanaTimezoneUnknown"

    value: str

    @classmethod
    def create(cls, raw) -> Result[Self]:
        if raw is None or not isinstance(raw, str):
            return Result.failure(cls.IANA_TIMEZONE_CANNOT_BE_EMPTY)
        s = raw.strip()
        if not s:
            return Result.failure(cls.IANA_TIMEZONE_CANNOT_BE_EMPTY)
        if s not in _AVAILABLE:
            return Result.failure(cls.IANA_TIMEZONE_UNKNOWN)
        return Result.success(cls(value=s))

    def to_zoneinfo(self) -> ZoneInfo:
        return ZoneInfo(self.value)

    def __str__(self) -> str:
        return self.value
```

- [ ] **Step 4: Run — green**

```bash
.venv/bin/pytest tests/unit/domain/shared/value_objects/test_iana_timezone.py -v
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add app/domain/shared/value_objects/iana_timezone.py tests/unit/domain/shared/value_objects/test_iana_timezone.py
git commit -m "$(cat <<'EOF'
feat(vo): add IanaTimezone value object

Validated against zoneinfo.available_timezones(). Used by
Resource.timezone (spec §5.3). Adds to_zoneinfo() helper for handlers
that need the actual ZoneInfo object (e.g., to convert local schedule
times to UTC for booking conflict checks).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task D2 — `TimeWindow`

Composite VO: `(start: time, end: time)` with `start < end` (strict, no overnight wrap). Used by `WeeklySchedule` per-day entries and `PricingRule.starts_at`/`ends_at`.

**Files:**
- Create: `app/domain/shared/value_objects/time_window.py`
- Create: `tests/unit/domain/shared/value_objects/test_time_window.py`

- [ ] **Step 1: Failing test**

`tests/unit/domain/shared/value_objects/test_time_window.py`:

```python
from __future__ import annotations
from datetime import time
from app.domain.shared.value_objects.time_window import TimeWindow


def test_time_window_create_success():
    r = TimeWindow.create(time(8, 0), time(18, 0))
    assert r.is_success
    assert r.value.start == time(8, 0)
    assert r.value.end == time(18, 0)


def test_time_window_rejects_start_equals_end():
    r = TimeWindow.create(time(8, 0), time(8, 0))
    assert r.is_failure
    assert r.error == TimeWindow.TIME_WINDOW_START_MUST_BE_BEFORE_END


def test_time_window_rejects_start_after_end():
    r = TimeWindow.create(time(18, 0), time(8, 0))
    assert r.is_failure
    assert r.error == TimeWindow.TIME_WINDOW_START_MUST_BE_BEFORE_END


def test_time_window_rejects_invalid_type():
    r = TimeWindow.create("08:00", "18:00")
    assert r.is_failure
    assert r.error == TimeWindow.TIME_WINDOW_INVALID_TYPE


def test_time_window_rejects_none():
    r = TimeWindow.create(None, None)
    assert r.is_failure
    assert r.error == TimeWindow.TIME_WINDOW_INVALID_TYPE


def test_time_window_duration_minutes():
    w = TimeWindow.create(time(8, 0), time(10, 30)).value
    assert w.duration_minutes() == 150


def test_time_window_duration_minutes_seconds_dropped():
    # Sub-minute precision is irrelevant for slot scheduling.
    w = TimeWindow.create(time(8, 0, 0), time(8, 30, 0)).value
    assert w.duration_minutes() == 30


def test_time_window_equality_by_value():
    a = TimeWindow.create(time(8, 0), time(18, 0)).value
    b = TimeWindow.create(time(8, 0), time(18, 0)).value
    assert a == b
    assert hash(a) == hash(b)


def test_time_window_overnight_explicitly_rejected():
    # Spec §10: overnight TimeWindow is out of scope for MVP.
    r = TimeWindow.create(time(22, 0), time(2, 0))
    assert r.is_failure
    assert r.error == TimeWindow.TIME_WINDOW_START_MUST_BE_BEFORE_END
```

- [ ] **Step 2: Run — fail**

```bash
.venv/bin/pytest tests/unit/domain/shared/value_objects/test_time_window.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implementation**

`app/domain/shared/value_objects/time_window.py`:

```python
from __future__ import annotations
from dataclasses import dataclass
from datetime import time
from typing import Self
from app.domain.shared.result import Result
from app.domain.shared.value_object import BaseValueObject


@dataclass(frozen=True, slots=True)
class TimeWindow(BaseValueObject):
    TIME_WINDOW_INVALID_TYPE = "TimeWindowInvalidType"
    TIME_WINDOW_START_MUST_BE_BEFORE_END = "TimeWindowStartMustBeBeforeEnd"

    start: time
    end: time

    @classmethod
    def create(cls, start, end) -> Result[Self]:
        if not isinstance(start, time) or not isinstance(end, time):
            return Result.failure(cls.TIME_WINDOW_INVALID_TYPE)
        if start >= end:
            return Result.failure(cls.TIME_WINDOW_START_MUST_BE_BEFORE_END)
        return Result.success(cls(start=start, end=end))

    def duration_minutes(self) -> int:
        return (self.end.hour - self.start.hour) * 60 + (self.end.minute - self.start.minute)
```

- [ ] **Step 4: Run — green**

```bash
.venv/bin/pytest tests/unit/domain/shared/value_objects/test_time_window.py -v
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add app/domain/shared/value_objects/time_window.py tests/unit/domain/shared/value_objects/test_time_window.py
git commit -m "$(cat <<'EOF'
feat(vo): add TimeWindow composite value object

(start: time, end: time) with strict start < end (no overnight wrap;
overnight windows deferred per spec §10). Used by per-day
WeeklySchedule entries and PricingRule windows in the future
resources feature (Plan 06).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task D3 — `DateTimeRange`

Composite VO: `(start_at: datetime, end_at: datetime)` with both tz-aware UTC and `start_at < end_at`. Used by `Booking.SlotRange` (spec §5.4).

**Files:**
- Create: `app/domain/shared/value_objects/date_time_range.py`
- Create: `tests/unit/domain/shared/value_objects/test_date_time_range.py`

- [ ] **Step 1: Failing test**

`tests/unit/domain/shared/value_objects/test_date_time_range.py`:

```python
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from app.domain.shared.value_objects.date_time_range import DateTimeRange


def test_date_time_range_create_success_utc():
    start = datetime(2026, 5, 1, 14, 0, tzinfo=timezone.utc)
    end = datetime(2026, 5, 1, 16, 0, tzinfo=timezone.utc)
    r = DateTimeRange.create(start, end)
    assert r.is_success
    assert r.value.start_at == start
    assert r.value.end_at == end


def test_date_time_range_accepts_zoneinfo_utc():
    # ZoneInfo("UTC") yields utcoffset 0 and is acceptable.
    start = datetime(2026, 5, 1, 14, 0, tzinfo=ZoneInfo("UTC"))
    end = datetime(2026, 5, 1, 16, 0, tzinfo=ZoneInfo("UTC"))
    r = DateTimeRange.create(start, end)
    assert r.is_success


def test_date_time_range_rejects_naive_datetime():
    start = datetime(2026, 5, 1, 14, 0)
    end = datetime(2026, 5, 1, 16, 0)
    r = DateTimeRange.create(start, end)
    assert r.is_failure
    assert r.error == DateTimeRange.DATE_TIME_RANGE_NOT_TZ_AWARE


def test_date_time_range_rejects_non_utc_offset():
    start = datetime(2026, 5, 1, 14, 0, tzinfo=ZoneInfo("America/Sao_Paulo"))
    end = datetime(2026, 5, 1, 16, 0, tzinfo=ZoneInfo("America/Sao_Paulo"))
    r = DateTimeRange.create(start, end)
    assert r.is_failure
    assert r.error == DateTimeRange.DATE_TIME_RANGE_NOT_UTC


def test_date_time_range_rejects_start_equals_end():
    start = datetime(2026, 5, 1, 14, 0, tzinfo=timezone.utc)
    r = DateTimeRange.create(start, start)
    assert r.is_failure
    assert r.error == DateTimeRange.DATE_TIME_RANGE_START_MUST_BE_BEFORE_END


def test_date_time_range_rejects_start_after_end():
    start = datetime(2026, 5, 1, 16, 0, tzinfo=timezone.utc)
    end = datetime(2026, 5, 1, 14, 0, tzinfo=timezone.utc)
    r = DateTimeRange.create(start, end)
    assert r.is_failure
    assert r.error == DateTimeRange.DATE_TIME_RANGE_START_MUST_BE_BEFORE_END


def test_date_time_range_rejects_invalid_type():
    r = DateTimeRange.create("2026-05-01T14:00:00Z", "2026-05-01T16:00:00Z")
    assert r.is_failure
    assert r.error == DateTimeRange.DATE_TIME_RANGE_INVALID_TYPE


def test_date_time_range_duration_minutes():
    start = datetime(2026, 5, 1, 14, 0, tzinfo=timezone.utc)
    end = datetime(2026, 5, 1, 16, 30, tzinfo=timezone.utc)
    r = DateTimeRange.create(start, end).value
    assert r.duration_minutes() == 150


def test_date_time_range_overlaps():
    a = DateTimeRange.create(
        datetime(2026, 5, 1, 14, 0, tzinfo=timezone.utc),
        datetime(2026, 5, 1, 16, 0, tzinfo=timezone.utc),
    ).value
    b_overlap = DateTimeRange.create(
        datetime(2026, 5, 1, 15, 0, tzinfo=timezone.utc),
        datetime(2026, 5, 1, 17, 0, tzinfo=timezone.utc),
    ).value
    b_disjoint = DateTimeRange.create(
        datetime(2026, 5, 1, 16, 0, tzinfo=timezone.utc),  # touching == disjoint (half-open)
        datetime(2026, 5, 1, 17, 0, tzinfo=timezone.utc),
    ).value
    assert a.overlaps(b_overlap) is True
    assert a.overlaps(b_disjoint) is False  # [start, end) — touching does not overlap
    assert b_disjoint.overlaps(a) is False
```

- [ ] **Step 2: Run — fail**

```bash
.venv/bin/pytest tests/unit/domain/shared/value_objects/test_date_time_range.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implementation**

`app/domain/shared/value_objects/date_time_range.py`:

```python
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Self
from app.domain.shared.result import Result
from app.domain.shared.value_object import BaseValueObject


@dataclass(frozen=True, slots=True)
class DateTimeRange(BaseValueObject):
    DATE_TIME_RANGE_INVALID_TYPE = "DateTimeRangeInvalidType"
    DATE_TIME_RANGE_NOT_TZ_AWARE = "DateTimeRangeNotTzAware"
    DATE_TIME_RANGE_NOT_UTC = "DateTimeRangeNotUtc"
    DATE_TIME_RANGE_START_MUST_BE_BEFORE_END = "DateTimeRangeStartMustBeBeforeEnd"

    start_at: datetime
    end_at: datetime

    @classmethod
    def create(cls, start_at, end_at) -> Result[Self]:
        if not isinstance(start_at, datetime) or not isinstance(end_at, datetime):
            return Result.failure(cls.DATE_TIME_RANGE_INVALID_TYPE)
        if start_at.tzinfo is None or end_at.tzinfo is None:
            return Result.failure(cls.DATE_TIME_RANGE_NOT_TZ_AWARE)
        if start_at.utcoffset() != timedelta(0) or end_at.utcoffset() != timedelta(0):
            return Result.failure(cls.DATE_TIME_RANGE_NOT_UTC)
        if start_at >= end_at:
            return Result.failure(cls.DATE_TIME_RANGE_START_MUST_BE_BEFORE_END)
        return Result.success(cls(start_at=start_at, end_at=end_at))

    def duration_minutes(self) -> int:
        delta = self.end_at - self.start_at
        return int(delta.total_seconds() // 60)

    def overlaps(self, other: "DateTimeRange") -> bool:
        # Half-open interval [start_at, end_at): touching does NOT overlap.
        return self.start_at < other.end_at and other.start_at < self.end_at
```

- [ ] **Step 4: Run — green**

```bash
.venv/bin/pytest tests/unit/domain/shared/value_objects/test_date_time_range.py -v
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add app/domain/shared/value_objects/date_time_range.py tests/unit/domain/shared/value_objects/test_date_time_range.py
git commit -m "$(cat <<'EOF'
feat(vo): add DateTimeRange composite value object

(start_at, end_at) with strict tz-aware UTC and start_at < end_at.
Half-open semantics — overlaps() treats [start, end) so touching
ranges are disjoint, matching the Postgres tstzrange exclusion
constraint planned for Booking (spec §6.3). Used by Booking.SlotRange
(Plan 08).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## UNIT E — Error code → pt-BR mapping

### Task E1 — Create the central mapping table

Single dict from code identifier → pt-BR string. Lives in `app/api/error_codes.py`.

**Files:**
- Create: `app/api/error_codes.py`

- [ ] **Step 1: Create the file**

`app/api/error_codes.py`:

```python
"""Mapping from VO/handler stable error codes to pt-BR display strings.

This is the only place pt-BR error text lives. Domain code emits codes
(e.g., "NameCannotBeEmpty"); the HTTP boundary translates them via this
table when building the response body.

Adding a new VO error code:
  1. Define it as a class constant on the VO (e.g., Foo.FOO_INVALID = "FooInvalid").
  2. Add the corresponding pt-BR entry below.
  3. The architecture test in tests/unit/architecture/test_error_code_coverage.py
     enforces 1:1 coverage and will fail CI if either side is missing.
"""
from __future__ import annotations

from app.domain.shared.value_objects.attribute_key import AttributeKey
from app.domain.shared.value_objects.brazilian_phone import BrazilianPhone
from app.domain.shared.value_objects.cancellation_cutoff import CancellationCutoff
from app.domain.shared.value_objects.date_time_range import DateTimeRange
from app.domain.shared.value_objects.email import Email
from app.domain.shared.value_objects.iana_timezone import IanaTimezone
from app.domain.shared.value_objects.money import Money
from app.domain.shared.value_objects.name import Name
from app.domain.shared.value_objects.rating_score import RatingScore
from app.domain.shared.value_objects.short_description import ShortDescription
from app.domain.shared.value_objects.short_name import ShortName
from app.domain.shared.value_objects.slot_duration import SlotDuration
from app.domain.shared.value_objects.slug import Slug
from app.domain.shared.value_objects.time_window import TimeWindow


ERROR_MESSAGES_PT_BR: dict[str, str] = {
    # Email
    Email.EMAIL_CANNOT_BE_EMPTY: "E-mail é obrigatório.",
    Email.EMAIL_INVALID_FORMAT: "E-mail em formato inválido.",
    Email.EMAIL_CANNOT_BE_GREATER_THAN_MAX_LENGTH: f"E-mail não pode exceder {Email.MAX_LENGTH} caracteres.",

    # BrazilianPhone
    BrazilianPhone.PHONE_CANNOT_BE_EMPTY: "Telefone é obrigatório.",
    BrazilianPhone.PHONE_CONTAINS_INVALID_CHARACTERS: "Telefone contém caracteres inválidos.",
    BrazilianPhone.PHONE_HAS_NO_DIGITS: "Telefone não contém dígitos.",
    BrazilianPhone.PHONE_INVALID_LENGTH: "Telefone deve ter 10 dígitos (fixo) ou 11 (celular).",
    BrazilianPhone.PHONE_INVALID_DDD: "DDD inválido.",
    BrazilianPhone.PHONE_MOBILE_MUST_START_WITH_9: "Celular deve começar com 9 após o DDD.",
    BrazilianPhone.PHONE_LANDLINE_MUST_START_WITH_2_TO_7: "Telefone fixo deve começar com dígito entre 2 e 7.",

    # Slug
    Slug.SLUG_CANNOT_BE_EMPTY: "Slug é obrigatório.",
    Slug.SLUG_INVALID_FORMAT: "Slug inválido — use apenas letras minúsculas, dígitos e hífens; sem hífens repetidos ou nas pontas.",
    Slug.SLUG_CANNOT_BE_GREATER_THAN_MAX_LENGTH: f"Slug não pode exceder {Slug.MAX_LENGTH} caracteres.",

    # Name
    Name.NAME_CANNOT_BE_EMPTY: "Nome é obrigatório.",
    Name.NAME_CANNOT_BE_GREATER_THAN_MAX_LENGTH: f"Nome não pode exceder {Name.MAX_LENGTH} caracteres.",
    Name.NAME_CONTAINS_INVALID_CHARACTERS: "Nome contém caracteres inválidos (controle/sem-imprimíveis).",

    # ShortName
    ShortName.SHORT_NAME_CANNOT_BE_EMPTY: "Rótulo é obrigatório.",
    ShortName.SHORT_NAME_CANNOT_BE_GREATER_THAN_MAX_LENGTH: f"Rótulo não pode exceder {ShortName.MAX_LENGTH} caracteres.",
    ShortName.SHORT_NAME_CONTAINS_INVALID_CHARACTERS: "Rótulo contém caracteres inválidos.",

    # ShortDescription
    ShortDescription.SHORT_DESCRIPTION_INVALID_TYPE: "Descrição em formato inválido.",
    ShortDescription.SHORT_DESCRIPTION_CANNOT_BE_GREATER_THAN_MAX_LENGTH: f"Descrição não pode exceder {ShortDescription.MAX_LENGTH} caracteres.",

    # AttributeKey
    AttributeKey.ATTRIBUTE_KEY_CANNOT_BE_EMPTY: "Chave de atributo é obrigatória.",
    AttributeKey.ATTRIBUTE_KEY_INVALID_FORMAT: "Chave de atributo inválida — use letras minúsculas, dígitos e underscores (snake_case).",
    AttributeKey.ATTRIBUTE_KEY_CANNOT_BE_GREATER_THAN_MAX_LENGTH: f"Chave de atributo não pode exceder {AttributeKey.MAX_LENGTH} caracteres.",

    # Money
    Money.MONEY_INVALID_TYPE: "Valor monetário deve ser inteiro (em centavos).",
    Money.MONEY_CANNOT_BE_NEGATIVE: "Valor monetário não pode ser negativo.",
    Money.MONEY_EXCEEDS_MAX: "Valor monetário excede o limite permitido.",
    Money.MONEY_INVALID_CENTAVOS: "Centavos devem ser inteiro entre 0 e 99.",

    # RatingScore
    RatingScore.RATING_SCORE_INVALID_TYPE: "Avaliação deve ser número inteiro.",
    RatingScore.RATING_SCORE_OUT_OF_RANGE: f"Avaliação deve estar entre {RatingScore.MIN_VALUE} e {RatingScore.MAX_VALUE} estrelas.",

    # SlotDuration
    SlotDuration.SLOT_DURATION_INVALID_TYPE: "Duração de slot deve ser inteiro (minutos).",
    SlotDuration.SLOT_DURATION_NOT_ALLOWED: "Duração de slot não permitida — escolha 30, 45, 60, 90 ou 120 minutos.",

    # CancellationCutoff
    CancellationCutoff.CANCELLATION_CUTOFF_INVALID_TYPE: "Antecedência de cancelamento deve ser inteiro (horas).",
    CancellationCutoff.CANCELLATION_CUTOFF_OUT_OF_RANGE: f"Antecedência de cancelamento deve estar entre {CancellationCutoff.MIN_HOURS} e {CancellationCutoff.MAX_HOURS} horas.",

    # IanaTimezone
    IanaTimezone.IANA_TIMEZONE_CANNOT_BE_EMPTY: "Fuso horário é obrigatório.",
    IanaTimezone.IANA_TIMEZONE_UNKNOWN: "Fuso horário desconhecido.",

    # TimeWindow
    TimeWindow.TIME_WINDOW_INVALID_TYPE: "Janela de horário em formato inválido.",
    TimeWindow.TIME_WINDOW_START_MUST_BE_BEFORE_END: "Horário inicial deve ser anterior ao final (sem virada de meia-noite).",

    # DateTimeRange
    DateTimeRange.DATE_TIME_RANGE_INVALID_TYPE: "Intervalo de datas em formato inválido.",
    DateTimeRange.DATE_TIME_RANGE_NOT_TZ_AWARE: "Datas precisam de fuso horário (tz-aware).",
    DateTimeRange.DATE_TIME_RANGE_NOT_UTC: "Datas precisam estar em UTC.",
    DateTimeRange.DATE_TIME_RANGE_START_MUST_BE_BEFORE_END: "Data inicial deve ser anterior à final.",
}


def translate(code: str) -> str:
    """Return pt-BR display message for an error code, or the code itself if unmapped."""
    return ERROR_MESSAGES_PT_BR.get(code, code)
```

- [ ] **Step 2: Smoke import**

```bash
BACKEND_DATABASE_URL="sqlite+aiosqlite:///:memory:" \
  .venv/bin/python -c "from app.api.error_codes import ERROR_MESSAGES_PT_BR, translate; \
print(len(ERROR_MESSAGES_PT_BR), 'codes mapped'); \
print(translate('EmailCannotBeEmpty'))"
```

Expected: prints number of codes (around 40+) and the pt-BR message for `EmailCannotBeEmpty`.

- [ ] **Step 3: Commit**

```bash
git add app/api/error_codes.py
git commit -m "$(cat <<'EOF'
feat(api): central error code -> pt-BR mapping

Map every VO stable error code to a pt-BR display message in one
file. Domain emits codes; this is the only place pt-BR text exists
on the server (per spec §3 decision 15). Adding a new code requires
adding the entry here, enforced by the architecture test in
tests/unit/architecture/test_error_code_coverage.py (next task).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task E2 — Wire `unwrap()` to translate codes

`unwrap()` in `app/api/error_handler.py` currently passes `result.error` directly into `HTTPException.detail`. After this change, it passes `translate(result.error)` so the pt-BR string reaches the client.

**Files:**
- Modify: `app/api/error_handler.py`

- [ ] **Step 1: Edit `app/api/error_handler.py`**

Final state:

```python
from __future__ import annotations
import logging
from typing import TypeVar
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from app.api.error_codes import translate
from app.domain.shared.result import Result

T = TypeVar("T")
logger = logging.getLogger(__name__)


def unwrap(result: Result[T]) -> T:
    if result.is_success:
        return result.value  # type: ignore[return-value]
    code = result.error or "InternalError"
    raise HTTPException(
        status_code=result.status_code or 500,
        detail={"code": code, "message": translate(code)},
    )


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(Exception)
    async def on_unhandled(request: Request, exc: Exception):
        logger.exception(
            "Unhandled error on %s %s", request.method, request.url.path
        )
        return JSONResponse(
            status_code=500,
            content={"detail": {"code": "InternalError", "message": f"{exc.__class__.__name__}: erro interno."}},
        )
```

- [ ] **Step 2: Run the test suite**

```bash
.venv/bin/pytest -q
```

Expected: green for unit tests. Some e2e tests in `tests/e2e/accounts/` may fail because they assert on `detail` being a string, not an object. Update those tests to read `response.json()["detail"]["code"]` and assert on code constants. Re-run.

For each updated e2e test, the pattern is:

```python
# before:
assert response.json()["detail"] == "Email: valor obrigatório."

# after:
detail = response.json()["detail"]
assert detail["code"] == "EmailCannotBeEmpty"
# optionally also assert message presence
assert "obrigatório" in detail["message"].lower()
```

- [ ] **Step 3: Commit**

```bash
git add app/api/error_handler.py tests/
git commit -m "$(cat <<'EOF'
feat(api): unwrap() emits {code, message} objects, not bare strings

Errors now reach the client as {"code": "EmailCannotBeEmpty",
"message": "E-mail é obrigatório."}. Frontends can stay
language-agnostic by consuming the code; users see the pt-BR text.
Existing e2e tests updated to assert on code identifiers instead of
substring-matching pt-BR strings.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task E3 — Architecture test: 1:1 code coverage

A test that walks every VO module, collects every class constant whose name ends in a known suffix (`_CANNOT_BE_EMPTY`, `_INVALID_FORMAT`, etc.), and asserts each is in `ERROR_MESSAGES_PT_BR`. New codes added to a VO without a translation will fail CI.

**Files:**
- Create: `tests/unit/architecture/test_error_code_coverage.py`

- [ ] **Step 1: Failing test (it will pass on first run if E1 is complete; but we still write it before "verifying")**

`tests/unit/architecture/test_error_code_coverage.py`:

```python
"""Architecture test: every VO error code must have a pt-BR translation.

Catches the failure mode where someone adds a new constant on a VO but
forgets to add the corresponding entry in app/api/error_codes.py. CI
fails before the gap reaches main.
"""
from __future__ import annotations
import importlib
import inspect
import pkgutil
from app.domain.shared import value_objects as value_objects_pkg
from app.domain.shared.value_object import BaseValueObject
from app.api.error_codes import ERROR_MESSAGES_PT_BR


def _collect_vo_classes():
    classes = []
    for mod_info in pkgutil.iter_modules(value_objects_pkg.__path__):
        module = importlib.import_module(f"{value_objects_pkg.__name__}.{mod_info.name}")
        for _name, obj in inspect.getmembers(module, inspect.isclass):
            if (
                obj is not BaseValueObject
                and issubclass(obj, BaseValueObject)
                and obj.__module__ == module.__name__
            ):
                classes.append(obj)
    return classes


def _collect_error_codes(vo_class) -> list[tuple[str, str]]:
    """Return (constant_name, code_value) pairs declared on the VO class."""
    codes = []
    for attr_name in dir(vo_class):
        if attr_name.startswith("_"):
            continue
        if attr_name.isupper():  # class-level constants are UPPER_SNAKE
            value = getattr(vo_class, attr_name)
            # We're looking for stable code identifiers — strings shaped like
            # "PascalCase" without spaces. Filter MAX_LENGTH-style numeric or
            # ALLOWED-style frozenset constants out by checking the value type.
            if isinstance(value, str) and value and value[0].isupper() and " " not in value:
                codes.append((attr_name, value))
    return codes


def test_every_vo_error_code_has_pt_br_translation():
    missing: list[str] = []
    for vo_class in _collect_vo_classes():
        for const_name, code in _collect_error_codes(vo_class):
            if code not in ERROR_MESSAGES_PT_BR:
                missing.append(f"{vo_class.__name__}.{const_name} = {code!r}")

    assert not missing, (
        "These VO error codes have no pt-BR translation in "
        "app/api/error_codes.py:\n  " + "\n  ".join(missing)
    )


def test_no_orphan_translations_in_mapping():
    """Every key in ERROR_MESSAGES_PT_BR must originate from a VO constant.

    Prevents stale entries lingering after a VO code is renamed or removed.
    """
    declared_codes: set[str] = set()
    for vo_class in _collect_vo_classes():
        for _const_name, code in _collect_error_codes(vo_class):
            declared_codes.add(code)

    orphans = sorted(set(ERROR_MESSAGES_PT_BR) - declared_codes)
    # Allow handler-level codes by listing them here as the pattern emerges in
    # later plans. For now (Plan 03), only VO-level codes exist.
    handler_level_allowlist: set[str] = set()
    real_orphans = [c for c in orphans if c not in handler_level_allowlist]

    assert not real_orphans, (
        "These pt-BR mapping keys do not match any VO error code:\n  "
        + "\n  ".join(real_orphans)
    )
```

- [ ] **Step 2: Run — should pass on first try**

```bash
.venv/bin/pytest tests/unit/architecture/test_error_code_coverage.py -v
```

Expected: both tests pass (E1 wired up every code).

If a test fails, it's because either (a) a VO defined in B/C/D missed an entry in E1's mapping, or (b) E1 has a typo. Fix the gap and re-run.

- [ ] **Step 3: Commit**

```bash
git add tests/unit/architecture/test_error_code_coverage.py
git commit -m "$(cat <<'EOF'
test(architecture): enforce 1:1 VO error code <-> pt-BR coverage

Walks every VO module and every UPPER_SNAKE PascalCase string
constant; fails CI if any code lacks a pt-BR translation in
app/api/error_codes.py, or if the mapping has an orphan entry that
no VO defines. Per spec §11 open item.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## UNIT F — Accounts retrofit + migration reset

### Task F1 — `User.full_name: str → Name`

Update `User` entity to type `full_name` as `Name`. The `create()` factory now calls `Name.create(full_name)` and aggregates the failure with the email-validation failure.

**Files:**
- Modify: `app/domain/accounts/user.py`
- Modify: `tests/unit/domain/accounts/test_user.py`

- [ ] **Step 1: Update existing user tests for the Name VO assertion style**

Read the current test file to see what's there:

```bash
.venv/bin/pytest tests/unit/domain/accounts/test_user.py --collect-only
```

For each test that constructs a `User` with `full_name="Foo"`, the call site stays the same (`User.create(...)` accepts `str`). What changes is:

1. Reading the entity field: `user.full_name.value` (instead of `user.full_name`).
2. Failure assertions: `assert "full_name" in r.error.lower()` becomes `assert Name.NAME_CANNOT_BE_EMPTY in r.error`.

Add or update tests in `tests/unit/domain/accounts/test_user.py`:

```python
from app.domain.shared.value_objects.name import Name


def test_user_full_name_is_name_vo():
    from app.domain.accounts.user import User
    from app.domain.accounts.role import Role
    r = User.create(
        email="user@example.com",
        password_hash="$2b$12$abcdefghijklmnopqrstuv",
        role=Role.CUSTOMER,
        full_name="Maria da Silva",
        phone=None,
    )
    assert r.is_success
    assert isinstance(r.value.full_name, Name)
    assert r.value.full_name.value == "Maria da Silva"


def test_user_create_propagates_name_validation_error():
    from app.domain.accounts.user import User
    from app.domain.accounts.role import Role
    r = User.create(
        email="user@example.com",
        password_hash="$2b$12$abcdefghijklmnopqrstuv",
        role=Role.CUSTOMER,
        full_name="",
        phone=None,
    )
    assert r.is_failure
    assert Name.NAME_CANNOT_BE_EMPTY in r.error


def test_user_create_propagates_name_max_length_error():
    from app.domain.accounts.user import User
    from app.domain.accounts.role import Role
    r = User.create(
        email="user@example.com",
        password_hash="$2b$12$abcdefghijklmnopqrstuv",
        role=Role.CUSTOMER,
        full_name="a" * 501,
        phone=None,
    )
    assert r.is_failure
    assert Name.NAME_CANNOT_BE_GREATER_THAN_MAX_LENGTH in r.error
```

Also update any pre-existing test that reads `user.full_name` directly (without `.value`). After the type change, that comparison would compare a `Name` VO to a `str` — failing. Find them with:

```bash
grep -n "full_name" tests/unit/domain/accounts/test_user.py
```

Update each occurrence: `user.full_name == "x"` → `user.full_name.value == "x"`.

- [ ] **Step 2: Update the `User` entity**

`app/domain/accounts/user.py`:

```python
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Self
from app.domain.accounts.role import Role
from app.domain.shared.entity import BaseEntity
from app.domain.shared.result import Result
from app.domain.shared.value_objects.brazilian_phone import BrazilianPhone
from app.domain.shared.value_objects.email import Email
from app.domain.shared.value_objects.name import Name


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(slots=True, kw_only=True)
class User(BaseEntity):
    email: Email
    password_hash: str
    role: Role
    full_name: Name
    phone: BrazilianPhone | None = None
    is_active: bool = True

    @classmethod
    def create(
        cls,
        *,
        email: str,
        password_hash: str,
        role: Role,
        full_name: str,
        phone: str | None,
    ) -> Result[Self]:
        errors: list[str] = []

        email_r = Email.create(email)
        if email_r.is_failure:
            errors.append(email_r.error)

        name_r = Name.create(full_name)
        if name_r.is_failure:
            errors.append(name_r.error)

        if not password_hash:
            errors.append("PasswordHashCannotBeEmpty")

        phone_r = BrazilianPhone.create_if_not_empty(phone)
        if phone_r.is_failure:
            errors.append(phone_r.error)

        if errors:
            return Result.failure("; ".join(errors))

        return Result.success(cls(
            email=email_r.value,
            password_hash=password_hash,
            role=role,
            full_name=name_r.value,
            phone=phone_r.value,
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

A new constant `"PasswordHashCannotBeEmpty"` is emitted but not yet in `ERROR_MESSAGES_PT_BR` (it's a handler-level concern, not a VO). Add it to the handler-level allowlist in `tests/unit/architecture/test_error_code_coverage.py` (the `handler_level_allowlist` set in `test_no_orphan_translations_in_mapping`):

```python
handler_level_allowlist: set[str] = {"PasswordHashCannotBeEmpty"}
```

…and add a translation to `app/api/error_codes.py`:

```python
# Handler-level (not VO-bound) codes
"PasswordHashCannotBeEmpty": "Hash de senha é obrigatório.",
```

- [ ] **Step 3: Run accounts unit tests**

```bash
.venv/bin/pytest tests/unit/domain/accounts/ -v
```

Expected: all green. Fix any leftover `user.full_name == "x"` comparisons.

- [ ] **Step 4: Run integration + e2e**

```bash
.venv/bin/pytest tests/integration/accounts tests/e2e/accounts -v
```

Some integration tests serialize `user.full_name` (e.g., to JSON). If a serializer expects `str` but now gets `Name`, fix it:
- Repository ORM mapping: `model.full_name = entity.full_name.value` (Name → str on persistence).
- Reconstitution: `entity.full_name = Name.create(model.full_name).value` (str → Name on load) — but wait, that goes through validation. Trusted reconstitution should bypass `create()` and use `Name(value=...)` directly. Note the `BaseValueObject` docstring says: *"Construtor direto (`cls(value=...)`) é usado só para reconstituição de dados confiáveis (vindos do DB)."* — this is the convention. Use it in repositories.

Find affected files:

```bash
grep -rn "full_name" app/infrastructure/ app/api/v1/accounts/ app/api/v1/admin_users/ app/use_cases/accounts/
```

Adjust each:
- ORM persistence (`UserRepository._to_model`): use `entity.full_name.value`
- ORM reconstitution (`UserRepository._to_entity`): use `Name(value=model.full_name)` (raw construction, trusted source).
- API schema: response model `full_name: str` stays — Pydantic serializers serialize `Name` via `__str__` if you tell it to, OR the route maps explicitly: `full_name=user.full_name.value`. Pick the explicit map; less magic.

Re-run integration + e2e:

```bash
.venv/bin/pytest tests/integration/accounts tests/e2e/accounts -v
```

Expected: green.

- [ ] **Step 5: Run full suite**

```bash
.venv/bin/pytest -q
```

Expected: green.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "$(cat <<'EOF'
refactor(accounts): User.full_name uses Name VO

Replace User.full_name: str with Name (max 500), per spec §5.1.
User.create() now aggregates Name validation alongside Email and
phone. Repositories adapt at the boundary: persistence stores the
underlying string, reconstitution uses the trusted Name(value=...)
constructor (per BaseValueObject convention).

Add PasswordHashCannotBeEmpty as the first handler-level error code
(not VO-bound); allowlisted in the architecture coverage test.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task F2 — Update `UserModel` mapping: `Text` for VO-backed columns

Per spec §3 decision 17, DB columns for VO-backed strings drop `VARCHAR(N)` and use `Text` — the VO governs length on the way in.

**Files:**
- Modify: `app/infrastructure/db/mappings/user.py`

- [ ] **Step 1: Edit the mapping**

`app/infrastructure/db/mappings/user.py`:

```python
from __future__ import annotations
from uuid import UUID
from sqlalchemy import Boolean, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import CHAR
from app.infrastructure.db.base import Base, TimestampMixin


class UserModel(Base, TimestampMixin):
    __tablename__ = "users"

    # CHAR(36) works on Postgres, SQL Server, and SQLite (tests).
    id: Mapped[UUID] = mapped_column(CHAR(36), primary_key=True)
    email: Mapped[str] = mapped_column(Text, nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    # role is a Role enum (ADMIN/OWNER/CUSTOMER) — short and indexable; keep small varchar.
    role: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(Text, nullable=False)
    phone_number: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
```

- [ ] **Step 2: Run unit tests** (mapping change doesn't affect them, but sanity check)

```bash
.venv/bin/pytest -q
```

Expected: green. (Tests use SQLite in-memory; `Text` works there.)

- [ ] **Step 3: Commit**

```bash
git add app/infrastructure/db/mappings/user.py
git commit -m "$(cat <<'EOF'
refactor(db): UserModel string columns use Text (no VARCHAR length)

Per spec §3 decision 17, the VO is the single source of truth for
length validation. DB columns drop VARCHAR(N) bounds and use Text;
adding a new VO bound (or relaxing one) no longer needs a column-
length migration.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task F3 — Reset migrations and regenerate fresh initial migration

Drop the two existing migration files and let Alembic autogenerate a single migration covering the current state of `UserModel`. **Local DB state is destroyed** — engineer must drop their local DB or `alembic_version` row first.

**Files:**
- Delete: `app/migrations/versions/20260424_1638_initial_users_table.py`
- Delete: `app/migrations/versions/20260425_1414_accounts_users_schema.py`
- Create: `app/migrations/versions/<timestamp>_initial_accounts.py` (autogenerated)

- [ ] **Step 1: Drop the existing migration files**

```bash
rm app/migrations/versions/20260424_1638_initial_users_table.py
rm app/migrations/versions/20260425_1414_accounts_users_schema.py
```

- [ ] **Step 2: Reset local DB state**

If the engineer has a local Postgres dev DB, drop and recreate it:

```bash
# Adjust connection params per your .env
psql -h localhost -U venue -d postgres -c "DROP DATABASE IF EXISTS venue_dev"
psql -h localhost -U venue -d postgres -c "CREATE DATABASE venue_dev"
```

If no local DB exists yet, skip — the autogen step below uses the `BACKEND_DATABASE_URL` from `.env`. For test isolation we use SQLite in-memory; for autogen we need a real connection that Alembic can introspect (or `--sql` offline mode). Easiest path:

```bash
# Use a temporary SQLite file just to autogenerate
BACKEND_DATABASE_URL="sqlite:///./_alembic_tmp.db" \
  .venv/bin/alembic upgrade head 2>/dev/null || true   # likely a no-op
BACKEND_DATABASE_URL="sqlite:///./_alembic_tmp.db" \
  .venv/bin/alembic revision --autogenerate -m "initial accounts"
rm -f ./_alembic_tmp.db
```

- [ ] **Step 3: Inspect the generated file**

The new migration in `app/migrations/versions/<timestamp>_initial_accounts.py` should look roughly like:

```python
def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.CHAR(length=36), primary_key=True),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("full_name", sa.Text(), nullable=False),
        sa.Column("phone_number", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_role", "users", ["role"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_users_role", "users")
    op.drop_index("ix_users_email", "users")
    op.drop_table("users")
```

If the generated file diverges (e.g., still has `String(254)` because env caching), edit it manually to match the structure above. The bound checking lives in the VO; the column type is `Text`.

- [ ] **Step 4: Apply the migration to confirm it runs**

```bash
# On a real Postgres
make migrate-up
```

Expected: migration runs cleanly. If you don't have local Postgres yet, skip — CI will catch failures when integration tests run against a real DB.

- [ ] **Step 5: Run the full test suite**

```bash
.venv/bin/pytest -q
```

Expected: green.

- [ ] **Step 6: Commit**

```bash
git add app/migrations/versions/
git commit -m "$(cat <<'EOF'
feat(migrations): reset to single fresh accounts migration

Drop the two pre-VO migrations (initial_users_table + accounts_users_
schema) and autogenerate a single migration matching the VO-aware
UserModel: Text columns (no VARCHAR bound), email unique index, role
index. Pre-launch reset is intentional — the team explicitly chose
this over multi-step alters.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## UNIT G — Final verification + push

### Task G1 — Full verification + lint

- [ ] **Step 1: Full test suite**

```bash
.venv/bin/pytest -q
```

Expected: ALL tests green. No skips.

- [ ] **Step 2: Lint**

```bash
make lint
# = .venv/bin/python -m ruff check app tests
#   .venv/bin/python -m mypy app
```

Expected: ruff clean. mypy may surface unrelated pre-existing issues in template code — fix any new issues you introduced (e.g., a missing import); ignore pre-existing template issues that are not VO-related.

- [ ] **Step 3: Smoke import**

```bash
BACKEND_DATABASE_URL="sqlite+aiosqlite:///:memory:" \
  .venv/bin/python -c "from app.main import app; \
from app.api.error_codes import ERROR_MESSAGES_PT_BR; \
from app.domain.shared.value_objects.money import Money; \
print('app loaded;', len(ERROR_MESSAGES_PT_BR), 'codes;', Money.create(4990).value)"
```

Expected: prints something like `app loaded; 41 codes; Money(cents=4990)` (no errors).

- [ ] **Step 4: Grep for stragglers**

```bash
# No more interpolated VO error strings in tests
grep -rn '"Email:\|"BrazilianPhone:\|"Slug:\|valor obrigatório' tests/
```

Expected: zero matches inside `tests/` (we converted everything to code-constant assertions).

- [ ] **Step 5: Push to GitHub**

```bash
git push -u origin feat/plan-03-vo-foundation
```

Expected: push succeeds, branch tracked on origin. Open a PR via GitHub UI when ready, or:

```bash
gh pr create --title "feat: VO foundation + accounts retrofit (Plan 03)" --body "$(cat <<'EOF'
## Summary
- 12 new shared Value Objects (Slug, Name, ShortName, ShortDescription, AttributeKey, Money, TimeWindow, DateTimeRange, IanaTimezone, SlotDuration, CancellationCutoff, RatingScore)
- Email and BrazilianPhone refactored to stable error code identifiers
- Central code → pt-BR mapping in app/api/error_codes.py
- Architecture test enforces 1:1 code coverage
- User.full_name retrofit to Name VO
- UserModel string columns: VARCHAR(N) → Text
- Migrations reset to a single fresh initial_accounts migration

## Test plan
- [ ] make test (full suite green)
- [ ] make lint
- [ ] manual: register a customer with a 501-char name and verify the response carries `{"code": "NameCannotBeGreaterThanMaxLength", "message": "..."}`
- [ ] manual: verify Money rejects 0.10 (float) but accepts 4990 (int cents)

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 6: No commit (verification only)**

---

## Self-review

**Spec coverage.** This plan covers spec §8 step 3 in full:
- ✅ 12 new VOs (Tasks B1–B5, C1–C4, D1–D3) — count matches §8.
- ✅ Refactor Email/BrazilianPhone to stable codes (Tasks A2, A3).
- ✅ `app/api/error_handler.py` maps codes → pt-BR (Task E2 + E1 mapping).
- ✅ Retrofit `User.full_name: str → Name` (Task F1).
- ✅ Reset and regenerate Alembic migrations (Task F3).
- ✅ Architecture test for code coverage (Task E3) — addresses spec §11 open item.
- ✅ Spec §3 decision 17 — `Text` columns, no VARCHAR bounds — handled in F2.

Plan 04 (catalog) consumes Slug, Name, ShortDescription, AttributeKey, ShortName — all delivered here.
Plan 06 (resources) consumes Slug, Name, ShortDescription, Money, TimeWindow, IanaTimezone, SlotDuration, CancellationCutoff — all delivered here.
Plan 08 (bookings) consumes DateTimeRange, Money, ShortDescription — all delivered here.
Plan 09 (ratings) consumes RatingScore, ShortDescription — all delivered here.

**Placeholder scan.** No "TBD", "TODO", or "implement later" inside steps. Every code block is concrete and self-contained.

**Type consistency.**
- VO factory return type is `Result[Self]` everywhere.
- VO `create_if_not_empty()` return type is `Result[Self | None]` everywhere it appears.
- Class-constant naming is `UPPER_SNAKE = "PascalCase"` everywhere.
- `BaseValueObject` is the parent everywhere.
- `Result` API used consistently (`Result.success(value)`, `Result.failure(code)`, `r.is_success`, `r.is_failure`, `r.value`, `r.error`).
- `Name`, `ShortName`, `ShortDescription` all expose `.value`; `Money` exposes `.cents`; `TimeWindow` exposes `.start`/`.end`; `DateTimeRange` exposes `.start_at`/`.end_at`. Test assertions match these names.

**Risks the engineer should watch for during execution.**

1. Tests in `tests/e2e/accounts/` may currently substring-match old VO error strings. Task A2 step 5 + A3 step 5 + E2 step 2 handle this iteratively; if more turn up, the same pattern applies (assert on code constants).
2. Task F3 destroys local DB state. Make sure no in-progress migrations or hand-rolled tables are lost. Pre-launch, this is intentional.
3. mypy may complain that `BaseValueObject.create(raw)` returns `Result[Self]` while a subclass returns `Result[Email]`. The PEP 673 `Self` type covers this — Python 3.12 + recent mypy support it. If mypy is older, add `from typing import Self`.
4. The architecture test in E3 walks `app.domain.shared.value_objects` via `pkgutil.iter_modules`. If a new VO gets added in a sub-package later, the walker will need updating. Out of scope for this plan.

---

## Execution handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-25-plan-03-vo-foundation.md`. Two execution options:

1. **Subagent-Driven (recommended)** — dispatch a fresh subagent per task, review between tasks, fast iteration.
2. **Inline Execution** — execute tasks in this session using executing-plans, batch execution with checkpoints.

Reply with **"subagent"** or **"inline"** to proceed.
