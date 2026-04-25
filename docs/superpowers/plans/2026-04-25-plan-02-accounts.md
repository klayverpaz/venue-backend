# Plan 02 — `accounts` feature with auth (replaces `users` sample)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the `accounts` feature from scratch — `User` aggregate with `Role`, password hashing (Argon2), JWT-based auth (access + refresh tokens), `get_current_user` and `require_role(...)` API dependencies, register/login/refresh/me endpoints, admin user management. Replace the template's `users` sample (Recipe C in `docs/template-customization.md`) and leave `feat/plan-02-accounts` ready to merge into `main` with all tests green.

**Architecture:** New domain feature `accounts/` with one aggregate (`User`) and three ports (`IUserRepository`, `IPasswordHasher`, `IJwtService`). Stateless JWT — no server-side session store; revocation is out of scope (see `Opportunities.md`). API surface split into `app/api/v1/auth/` (public + `/me`) and `app/api/v1/admin_users/` (admin-only management). Old `users` sample deleted in the final unit.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0 async, Alembic. New libraries: `argon2-cffi` (password hashing) and `python-jose[cryptography]` (JWT).

**Decisions pinned (do NOT re-debate during execution):**

| # | Decision | Rationale |
|---|---|---|
| 1 | One role per user (ADMIN / OWNER / CUSTOMER). Role mutation only via the explicit `PromoteUserRoleHandler`. | Spec §2 + §5.1. |
| 2 | Stateless JWT (HS256). Access token: 30 min. Refresh token: 7 days. No revocation list. | Simplicity; revocation deferred to Opportunities.md. |
| 3 | Argon2 password hashing via `argon2-cffi` (OWASP recommended). Hash parameters parameterized via `Settings` so tests can use cheap hashes. | Modern default; bcrypt has 72-byte truncation surprise. |
| 4 | `get_current_user` decodes the JWT only (no DB load). Role taken from JWT payload. Deactivated users keep working until token expires (max 30 min). | Keeps the dep cheap; fine for MVP. |
| 5 | Self-register: only `CUSTOMER` and `OWNER` roles. Admin accounts are seeded out-of-band (env var on first boot — done in Plan 07). | Spec §2. |
| 6 | API folder split: `app/api/v1/auth/` (register/login/refresh/logout/me) + `app/api/v1/admin_users/` (admin management). Both call into the same use cases. | URL prefixes are different; folder names mirror URL. |
| 7 | DELETE the `users` sample at the END of this plan, after `accounts` is fully working. The deletion goes in its own commit. | Lets the review at each unit boundary use the old sample as a structural reference. |
| 8 | `Email` VO reused from `app/domain/shared/value_objects/email.py`. `BrazilianPhone` VO reused for the optional `phone` field. | Already in shared kernel; no need to duplicate. |
| 9 | Use the `app/api/v1/users/` patterns (deps + routes shape) as the structural template for the new routers. | Consistency with the rest of the codebase. |

---

## File Structure

### New files

```
app/domain/accounts/
├── __init__.py
├── role.py                       # Role enum
├── user.py                       # User aggregate
├── repository.py                 # IUserRepository Protocol
├── password_hasher.py            # IPasswordHasher Protocol
└── jwt_service.py                # IJwtService Protocol + token DTOs

app/use_cases/accounts/
├── __init__.py
├── dtos.py                       # UserDto, TokenPairDto
├── commands/
│   ├── __init__.py
│   ├── register_user.py          # Public: register CUSTOMER or OWNER
│   ├── login.py                  # Public: email+password → token pair
│   ├── refresh_token.py          # Refresh token → new token pair
│   ├── promote_user_role.py      # Admin: change role
│   └── deactivate_user.py        # Admin: deactivate
└── queries/
    ├── __init__.py
    └── get_user_by_id.py         # Used by /me

app/infrastructure/auth/
├── __init__.py
├── argon2_password_hasher.py     # argon2-cffi adapter
└── jose_jwt_service.py           # python-jose adapter

app/api/v1/auth/
├── __init__.py                   # re-export router
├── routes.py                     # POST /v1/auth/register, /login, /refresh, /logout; GET /v1/me
├── schemas.py
└── deps.py                       # handler DI

app/api/v1/admin_users/
├── __init__.py
├── routes.py                     # GET /v1/admin/users, POST /v1/admin/users/{id}/role, .../deactivate
├── schemas.py
└── deps.py
```

### Modified files

```
app/api/deps.py                                  # add get_current_user, require_role
app/api/v1/router.py                             # include auth_router + admin_users_router; remove users_router
app/core/config.py                               # add JWT + Argon2 settings
.env.example                                     # add the new BACKEND_JWT_* and BACKEND_ARGON2_* keys
requirements.txt                                 # add argon2-cffi + python-jose[cryptography]
app/infrastructure/db/mappings/__init__.py       # nothing to change (mappings/__init__.py is empty)
app/infrastructure/db/mappings/user.py           # rewritten for the new schema (or replaced; see Task B5)
app/infrastructure/repositories/user_repository.py   # rewritten (mapping changed)
app/migrations/env.py                            # update import (point at new mapping module if renamed)
tests/e2e/conftest.py                            # update mapping import; set test JWT secret
tests/conftest.py                                # set test JWT secret + cheap Argon2 params
```

### Deleted files (final unit, Recipe C step)

```
app/domain/user/                                 # entire dir
app/use_cases/users/                             # entire dir
app/api/v1/users/                                # entire dir
tests/unit/domain/user/
tests/unit/use_cases/users/
tests/integration/users/
tests/e2e/users/
```

(`app/infrastructure/db/mappings/user.py` and `app/infrastructure/repositories/user_repository.py` are NOT deleted — they're rewritten in place to back the new `accounts` feature, so the table name `users` stays the same and the migration path is clean.)

### Database migration

A single auto-generated Alembic revision that ALTERs the `users` table:
- DROP `name`, `phone`, `credit_score`, `balance`.
- ADD `password_hash` (String 255, NOT NULL), `role` (String 16, NOT NULL), `full_name` (String 200, NOT NULL), `phone_number` (String 14, NULL).
- KEEP `id`, `email`, `is_active`, `created_at`, `updated_at`.

(We could write a fresh `0001_initial.py` migration since the project is brand-new and the previous initial migration has never been applied to a real DB, but the cleaner path is to ALTER — it lets the existing migration history stay intact and works whether or not someone has applied the original. Task B7 generates and inspects the autogenerate output.)

---

## Execution Plan — five units

Each unit is one implementer dispatch. Reviewers (spec compliance + code quality) run between units.

| Unit | Tasks | Approx commits |
|---|---|---|
| **A** | Domain layer | 4 |
| **B** | Infrastructure (libs + adapters + mapping + repo + migration) | 6 |
| **C** | Use cases | 6 |
| **D** | API layer + DI | 4 |
| **E** | Cleanup + verification | 2 |

Total: ~22 commits.

---

## UNIT A — Domain layer

Pure Python. No infrastructure imports. All four files are small.

### Task A1 — `Role` enum

**File:** `app/domain/accounts/__init__.py` (empty), `app/domain/accounts/role.py`.

- [ ] **Step 1: Failing test**

`tests/unit/domain/accounts/__init__.py` (empty), `tests/unit/domain/accounts/test_role.py`:

```python
from app.domain.accounts.role import Role


def test_role_values():
    assert Role.ADMIN.value == "admin"
    assert Role.OWNER.value == "owner"
    assert Role.CUSTOMER.value == "customer"


def test_role_from_string():
    assert Role("admin") is Role.ADMIN
    assert Role("owner") is Role.OWNER
    assert Role("customer") is Role.CUSTOMER


def test_role_self_registerable():
    assert Role.OWNER.is_self_registerable() is True
    assert Role.CUSTOMER.is_self_registerable() is True
    assert Role.ADMIN.is_self_registerable() is False
```

- [ ] **Step 2: Run — expect FAIL (`ModuleNotFoundError: No module named 'app.domain.accounts'`).**

`.venv/bin/pytest tests/unit/domain/accounts/test_role.py -q`

- [ ] **Step 3: Implement**

`app/domain/accounts/role.py`:

```python
from __future__ import annotations
from enum import Enum


class Role(str, Enum):
    ADMIN = "admin"
    OWNER = "owner"
    CUSTOMER = "customer"

    def is_self_registerable(self) -> bool:
        return self is Role.OWNER or self is Role.CUSTOMER
```

- [ ] **Step 4: Run — expect PASS.**

`.venv/bin/pytest tests/unit/domain/accounts/test_role.py -q`

- [ ] **Step 5: Commit**

```bash
git add app/domain/accounts/ tests/unit/domain/accounts/
git commit -m "$(cat <<'EOF'
feat(accounts): add Role enum (ADMIN, OWNER, CUSTOMER)

Role.is_self_registerable() encodes the rule that ADMIN accounts are
seeded out-of-band; only OWNER and CUSTOMER may self-register.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

### Task A2 — `User` aggregate

**Files:** `app/domain/accounts/user.py`, `tests/unit/domain/accounts/test_user.py`.

- [ ] **Step 1: Failing test**

```python
from __future__ import annotations
from datetime import datetime, timezone
from uuid import uuid4
from app.domain.accounts.role import Role
from app.domain.accounts.user import User


def test_create_user_success():
    r = User.create(
        email="alice@example.com",
        password_hash="$argon2id$...",
        role=Role.CUSTOMER,
        full_name="Alice Almeida",
        phone="+5511999999999",
    )
    assert r.is_success
    u = r.value
    assert str(u.email) == "alice@example.com"
    assert u.password_hash == "$argon2id$..."
    assert u.role is Role.CUSTOMER
    assert u.full_name == "Alice Almeida"
    assert str(u.phone) == "+5511999999999"
    assert u.is_active is True


def test_create_user_no_phone():
    r = User.create(
        email="bob@example.com",
        password_hash="hash",
        role=Role.OWNER,
        full_name="Bob",
        phone=None,
    )
    assert r.is_success
    assert r.value.phone is None


def test_create_user_invalid_email():
    r = User.create(
        email="not-an-email",
        password_hash="hash",
        role=Role.CUSTOMER,
        full_name="x",
        phone=None,
    )
    assert r.is_failure
    assert "email" in r.error.lower()


def test_create_user_blank_full_name():
    r = User.create(
        email="alice@example.com",
        password_hash="hash",
        role=Role.CUSTOMER,
        full_name="   ",
        phone=None,
    )
    assert r.is_failure
    assert "full_name" in r.error or "nome" in r.error.lower()


def test_change_password_hash_updates_timestamp():
    r = User.create(
        email="alice@example.com",
        password_hash="old",
        role=Role.CUSTOMER,
        full_name="Alice",
        phone=None,
    )
    u = r.value
    before = u.updated_at
    u.change_password_hash("new")
    assert u.password_hash == "new"
    assert u.updated_at > before


def test_promote_role_admin_only_called_via_handler():
    """Domain just supports the mutation; the admin-only invariant is enforced at the handler level."""
    r = User.create(
        email="alice@example.com",
        password_hash="h",
        role=Role.CUSTOMER,
        full_name="Alice",
        phone=None,
    )
    u = r.value
    before = u.updated_at
    u.set_role(Role.OWNER)
    assert u.role is Role.OWNER
    assert u.updated_at > before


def test_deactivate_and_reactivate():
    r = User.create(
        email="alice@example.com",
        password_hash="h",
        role=Role.CUSTOMER,
        full_name="Alice",
        phone=None,
    )
    u = r.value
    u.deactivate()
    assert u.is_active is False
    u.activate()
    assert u.is_active is True
```

- [ ] **Step 2: Run — expect FAIL.**

`.venv/bin/pytest tests/unit/domain/accounts/test_user.py -q`

- [ ] **Step 3: Implement**

`app/domain/accounts/user.py`:

```python
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Self
from app.domain.accounts.role import Role
from app.domain.shared.entity import BaseEntity
from app.domain.shared.result import Result
from app.domain.shared.value_objects.brazilian_phone import BrazilianPhone
from app.domain.shared.value_objects.email import Email


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(slots=True, kw_only=True)
class User(BaseEntity):
    email: Email
    password_hash: str
    role: Role
    full_name: str
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

        full_name_clean = (full_name or "").strip()
        if not full_name_clean:
            errors.append("full_name: obrigatório.")

        if not password_hash:
            errors.append("password_hash: obrigatório.")

        phone_vo: BrazilianPhone | None = None
        if phone is not None and phone.strip():
            phone_r = BrazilianPhone.create(phone)
            if phone_r.is_failure:
                errors.append(phone_r.error)
            else:
                phone_vo = phone_r.value

        if errors:
            return Result.failure("; ".join(errors))

        return Result.success(cls(
            email=email_r.value,
            password_hash=password_hash,
            role=role,
            full_name=full_name_clean,
            phone=phone_vo,
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

- [ ] **Step 4: Run — expect PASS (7 tests).**

- [ ] **Step 5: Commit**

```bash
git add app/domain/accounts/user.py tests/unit/domain/accounts/test_user.py
git commit -m "$(cat <<'EOF'
feat(accounts): add User aggregate with Role + password_hash

User holds email (VO), password_hash (string from infrastructure
hasher), role (enum), full_name, optional BrazilianPhone, is_active.
Mutations (change_password_hash, set_role, deactivate, activate) bump
updated_at. Admin-only invariants are enforced at handler level, not
in the entity, so the domain stays pure.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

### Task A3 — `IUserRepository` Protocol

**File:** `app/domain/accounts/repository.py`.

- [ ] **Step 1: Implement directly (Protocol — no separate test, behavior verified by handler tests in Unit C and integration tests in Unit B)**

```python
from __future__ import annotations
from typing import Protocol, Sequence
from uuid import UUID
from app.domain.accounts.user import User


class IUserRepository(Protocol):
    async def get_by_id(self, user_id: UUID) -> User | None: ...
    async def get_by_email(self, email: str) -> User | None: ...
    async def list_active(
        self, *, limit: int = 50, offset: int = 0
    ) -> Sequence[User]: ...
    async def add(self, user: User) -> None: ...
    async def update(self, user: User) -> None: ...
```

(No `remove` — accounts are deactivated, not deleted, per the design spec §11.)

- [ ] **Step 2: Run full unit suite to ensure nothing broke**

`.venv/bin/pytest tests/unit/domain/accounts/ -q` — expect green.

- [ ] **Step 3: Commit**

```bash
git add app/domain/accounts/repository.py
git commit -m "$(cat <<'EOF'
feat(accounts): add IUserRepository Protocol

CRUD-style interface used by use cases. No remove() — accounts are
deactivated, never hard-deleted (FK constraints from bookings later).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

### Task A4 — `IPasswordHasher` and `IJwtService` ports + token DTOs

**Files:** `app/domain/accounts/password_hasher.py`, `app/domain/accounts/jwt_service.py`.

- [ ] **Step 1: Implement password hasher port**

`app/domain/accounts/password_hasher.py`:

```python
from __future__ import annotations
from typing import Protocol


class IPasswordHasher(Protocol):
    def hash(self, plaintext: str) -> str:
        """Return an opaque hash string. Algorithm + parameters are encoded inside the hash."""

    def verify(self, plaintext: str, hashed: str) -> bool:
        """Return True iff plaintext matches hashed. MUST be timing-safe."""

    def needs_rehash(self, hashed: str) -> bool:
        """Return True if the hash was produced with weaker parameters than current settings."""
```

- [ ] **Step 2: Implement JWT service port + token DTOs**

`app/domain/accounts/jwt_service.py`:

```python
from __future__ import annotations
from dataclasses import dataclass
from typing import Literal, Protocol
from uuid import UUID
from app.domain.accounts.role import Role
from app.domain.shared.result import Result


TokenType = Literal["access", "refresh"]


@dataclass(frozen=True, slots=True)
class TokenPair:
    """Issued by login or refresh — returned to the client."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    access_expires_in_seconds: int = 0  # filled by issuer


@dataclass(frozen=True, slots=True)
class TokenClaims:
    """Decoded payload — what get_current_user receives."""
    user_id: UUID
    role: Role
    type: TokenType


class IJwtService(Protocol):
    def issue_pair(self, *, user_id: UUID, role: Role) -> TokenPair: ...
    def decode(self, token: str) -> Result[TokenClaims]:
        """Parse + verify signature + check expiry. Returns Result.failure on any of those."""
```

- [ ] **Step 3: Smoke test that the modules import cleanly**

`.venv/bin/python -c "from app.domain.accounts.password_hasher import IPasswordHasher; from app.domain.accounts.jwt_service import IJwtService, TokenPair, TokenClaims; print('ok')"` — should print `ok`.

Run the unit suite for accounts: `.venv/bin/pytest tests/unit/domain/accounts/ -q` — green.

- [ ] **Step 4: Commit**

```bash
git add app/domain/accounts/password_hasher.py app/domain/accounts/jwt_service.py
git commit -m "$(cat <<'EOF'
feat(accounts): add IPasswordHasher + IJwtService ports

Two pure Protocols + the TokenPair / TokenClaims dataclasses they
exchange. Concrete adapters (Argon2, jose) live in infrastructure/
and are wired in unit B.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## UNIT B — Infrastructure

Library installs, settings, two concrete adapters, DB mapping rewrite, repository rewrite, migration. Six tasks, six commits.

### Task B1 — Add `argon2-cffi` and `python-jose[cryptography]` to `requirements.txt`

**File:** `requirements.txt`.

- [ ] **Step 1: Append the two lines**

Open `requirements.txt`, add at the bottom (in alphabetical order to match existing style if applicable):

```
argon2-cffi==23.1.0
python-jose[cryptography]==3.3.0
```

- [ ] **Step 2: Install into the venv**

```bash
.venv/bin/pip install -r requirements.txt
```

- [ ] **Step 3: Smoke import**

```bash
.venv/bin/python -c "import argon2; from jose import jwt; print('ok')"
```

Expect: `ok`.

- [ ] **Step 4: Commit**

```bash
git add requirements.txt
git commit -m "$(cat <<'EOF'
chore: add argon2-cffi and python-jose for accounts auth

argon2-cffi backs IPasswordHasher; python-jose[cryptography] backs
IJwtService. Pinned to current stable releases.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

### Task B2 — Add JWT and Argon2 settings to `Settings` and `.env.example`

**Files:** `app/core/config.py`, `.env.example`.

- [ ] **Step 1: Edit `app/core/config.py`**

Add these fields to the `Settings` class body, after `redis_password`:

```python
    # JWT
    jwt_secret_key: SecretStr = SecretStr("dev-only-jwt-secret-DO-NOT-USE-IN-PROD")
    jwt_algorithm: str = "HS256"
    jwt_access_token_expires_minutes: int = 30
    jwt_refresh_token_expires_days: int = 7

    # Argon2 (defaults follow OWASP 2024; tests override to cheap params)
    argon2_time_cost: int = 3
    argon2_memory_cost_kib: int = 12_288
    argon2_parallelism: int = 1
```

`SecretStr` is already imported.

- [ ] **Step 2: Edit `.env.example`**

Append, after the Redis block:

```
# JWT
BACKEND_JWT_SECRET_KEY=dev-only-jwt-secret-DO-NOT-USE-IN-PROD
BACKEND_JWT_ALGORITHM=HS256
BACKEND_JWT_ACCESS_TOKEN_EXPIRES_MINUTES=30
BACKEND_JWT_REFRESH_TOKEN_EXPIRES_DAYS=7

# Argon2 (OWASP 2024 defaults)
BACKEND_ARGON2_TIME_COST=3
BACKEND_ARGON2_MEMORY_COST_KIB=12288
BACKEND_ARGON2_PARALLELISM=1
```

- [ ] **Step 3: Update test conftests so tests can use cheap Argon2 + a known JWT secret**

Edit `tests/conftest.py`. Inside `_env_defaults`, add:

```python
    monkeypatch.setenv("BACKEND_JWT_SECRET_KEY", "test-jwt-secret-fixed-for-determinism")
    monkeypatch.setenv("BACKEND_JWT_ACCESS_TOKEN_EXPIRES_MINUTES", "30")
    monkeypatch.setenv("BACKEND_JWT_REFRESH_TOKEN_EXPIRES_DAYS", "7")
    monkeypatch.setenv("BACKEND_ARGON2_TIME_COST", "1")
    monkeypatch.setenv("BACKEND_ARGON2_MEMORY_COST_KIB", "8")
    monkeypatch.setenv("BACKEND_ARGON2_PARALLELISM", "1")
```

Edit `tests/e2e/conftest.py`. Inside the `os.environ.setdefault(...)` block at the top, add:

```python
os.environ.setdefault("BACKEND_JWT_SECRET_KEY", "test-jwt-secret-fixed-for-determinism")
os.environ.setdefault("BACKEND_ARGON2_TIME_COST", "1")
os.environ.setdefault("BACKEND_ARGON2_MEMORY_COST_KIB", "8")
os.environ.setdefault("BACKEND_ARGON2_PARALLELISM", "1")
```

- [ ] **Step 4: Update `tests/unit/core/test_config.py`**

Add a test asserting the new fields are picked up correctly:

```python
def test_settings_jwt_defaults(monkeypatch):
    monkeypatch.setenv("BACKEND_DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    monkeypatch.setenv("BACKEND_JWT_SECRET_KEY", "abc")
    get_settings.cache_clear()
    s = get_settings()
    assert s.jwt_secret_key.get_secret_value() == "abc"
    assert s.jwt_algorithm == "HS256"
    assert s.jwt_access_token_expires_minutes == 30
    assert s.jwt_refresh_token_expires_days == 7
```

- [ ] **Step 5: Run tests**

`.venv/bin/pytest -q` — green.

- [ ] **Step 6: Commit**

```bash
git add app/core/config.py .env.example tests/conftest.py tests/e2e/conftest.py tests/unit/core/test_config.py
git commit -m "$(cat <<'EOF'
feat(config): add JWT and Argon2 settings + test overrides

New Settings fields: jwt_secret_key, jwt_algorithm,
jwt_access_token_expires_minutes (30 default), jwt_refresh_token_expires_days
(7 default), argon2_{time_cost,memory_cost_kib,parallelism} (OWASP 2024
defaults). .env.example documents them. Test conftests pin a known
JWT secret and cheap Argon2 params so password hashing in tests stays
fast (sub-millisecond rather than ~500ms each).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

### Task B3 — Implement `Argon2PasswordHasher`

**Files:** `app/infrastructure/auth/__init__.py` (empty), `app/infrastructure/auth/argon2_password_hasher.py`, `tests/integration/auth/__init__.py` (empty), `tests/integration/auth/test_argon2_password_hasher.py`.

- [ ] **Step 1: Failing test (integration test — uses the real Argon2 lib with cheap params)**

```python
from __future__ import annotations
from app.infrastructure.auth.argon2_password_hasher import Argon2PasswordHasher


def test_hash_and_verify_round_trip():
    hasher = Argon2PasswordHasher(time_cost=1, memory_cost_kib=8, parallelism=1)
    h = hasher.hash("hunter2")
    assert h.startswith("$argon2")
    assert hasher.verify("hunter2", h) is True
    assert hasher.verify("wrong", h) is False


def test_two_hashes_of_same_plaintext_differ():
    hasher = Argon2PasswordHasher(time_cost=1, memory_cost_kib=8, parallelism=1)
    a = hasher.hash("hunter2")
    b = hasher.hash("hunter2")
    assert a != b  # salt is random


def test_needs_rehash_detects_weaker_params():
    weak = Argon2PasswordHasher(time_cost=1, memory_cost_kib=8, parallelism=1)
    strong = Argon2PasswordHasher(time_cost=3, memory_cost_kib=64, parallelism=1)
    h = weak.hash("hunter2")
    assert strong.needs_rehash(h) is True
    assert weak.needs_rehash(h) is False
```

- [ ] **Step 2: Run — expect FAIL.**

`.venv/bin/pytest tests/integration/auth/ -q`

- [ ] **Step 3: Implement**

`app/infrastructure/auth/argon2_password_hasher.py`:

```python
from __future__ import annotations
from argon2 import PasswordHasher as _ArgonHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError

from app.domain.accounts.password_hasher import IPasswordHasher


class Argon2PasswordHasher(IPasswordHasher):
    def __init__(
        self,
        *,
        time_cost: int,
        memory_cost_kib: int,
        parallelism: int,
    ) -> None:
        self._impl = _ArgonHasher(
            time_cost=time_cost,
            memory_cost=memory_cost_kib,
            parallelism=parallelism,
        )

    def hash(self, plaintext: str) -> str:
        return self._impl.hash(plaintext)

    def verify(self, plaintext: str, hashed: str) -> bool:
        try:
            return self._impl.verify(hashed, plaintext)
        except (VerifyMismatchError, VerificationError, InvalidHashError):
            return False

    def needs_rehash(self, hashed: str) -> bool:
        try:
            return self._impl.check_needs_rehash(hashed)
        except InvalidHashError:
            return True
```

- [ ] **Step 4: Run — expect PASS.**

- [ ] **Step 5: Commit**

```bash
git add app/infrastructure/auth/__init__.py app/infrastructure/auth/argon2_password_hasher.py tests/integration/auth/
git commit -m "$(cat <<'EOF'
feat(auth): add Argon2PasswordHasher implementing IPasswordHasher

Wraps argon2-cffi's PasswordHasher. verify() returns False on any
mismatch / corruption (no exceptions leak to the use-case layer).
needs_rehash() returns True when the stored hash uses weaker params
than the current Settings — handlers can opportunistically re-hash
on successful login.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

### Task B4 — Implement `JoseJwtService`

**Files:** `app/infrastructure/auth/jose_jwt_service.py`, `tests/integration/auth/test_jose_jwt_service.py`.

- [ ] **Step 1: Failing test**

```python
from __future__ import annotations
import time
from uuid import uuid4
from app.domain.accounts.role import Role
from app.infrastructure.auth.jose_jwt_service import JoseJwtService


def make_service(*, access_seconds: int = 60, refresh_seconds: int = 600):
    return JoseJwtService(
        secret_key="test-secret",
        algorithm="HS256",
        access_token_expires_seconds=access_seconds,
        refresh_token_expires_seconds=refresh_seconds,
    )


def test_issue_and_decode_access_token():
    svc = make_service()
    user_id = uuid4()
    pair = svc.issue_pair(user_id=user_id, role=Role.OWNER)
    assert pair.token_type == "bearer"
    assert pair.access_expires_in_seconds == 60
    r = svc.decode(pair.access_token)
    assert r.is_success
    claims = r.value
    assert claims.user_id == user_id
    assert claims.role is Role.OWNER
    assert claims.type == "access"


def test_decode_refresh_token():
    svc = make_service()
    user_id = uuid4()
    pair = svc.issue_pair(user_id=user_id, role=Role.CUSTOMER)
    r = svc.decode(pair.refresh_token)
    assert r.is_success
    assert r.value.type == "refresh"


def test_decode_invalid_signature_fails():
    a = JoseJwtService(secret_key="A", algorithm="HS256",
                      access_token_expires_seconds=60, refresh_token_expires_seconds=600)
    b = JoseJwtService(secret_key="B", algorithm="HS256",
                      access_token_expires_seconds=60, refresh_token_expires_seconds=600)
    pair = a.issue_pair(user_id=uuid4(), role=Role.CUSTOMER)
    r = b.decode(pair.access_token)
    assert r.is_failure
    assert "signature" in r.error.lower() or "invalid" in r.error.lower()


def test_decode_expired_fails():
    svc = make_service(access_seconds=1, refresh_seconds=1)
    pair = svc.issue_pair(user_id=uuid4(), role=Role.CUSTOMER)
    time.sleep(2)
    r = svc.decode(pair.access_token)
    assert r.is_failure
    assert "expir" in r.error.lower()


def test_decode_garbage_fails():
    svc = make_service()
    r = svc.decode("not-a-jwt")
    assert r.is_failure


def test_two_pairs_for_same_user_have_different_tokens():
    svc = make_service()
    uid = uuid4()
    a = svc.issue_pair(user_id=uid, role=Role.OWNER)
    time.sleep(1.1)  # iat resolution is 1s
    b = svc.issue_pair(user_id=uid, role=Role.OWNER)
    assert a.access_token != b.access_token
```

- [ ] **Step 2: Run — expect FAIL.**

- [ ] **Step 3: Implement**

`app/infrastructure/auth/jose_jwt_service.py`:

```python
from __future__ import annotations
from datetime import datetime, timezone, timedelta
from uuid import UUID
from jose import jwt, JWTError, ExpiredSignatureError

from app.domain.accounts.jwt_service import (
    IJwtService, TokenPair, TokenClaims, TokenType,
)
from app.domain.accounts.role import Role
from app.domain.shared.result import Result


class JoseJwtService(IJwtService):
    def __init__(
        self,
        *,
        secret_key: str,
        algorithm: str,
        access_token_expires_seconds: int,
        refresh_token_expires_seconds: int,
    ) -> None:
        self._secret = secret_key
        self._alg = algorithm
        self._access_seconds = access_token_expires_seconds
        self._refresh_seconds = refresh_token_expires_seconds

    def issue_pair(self, *, user_id: UUID, role: Role) -> TokenPair:
        now = datetime.now(timezone.utc)
        access = self._encode(user_id=user_id, role=role, type_="access",
                              now=now, ttl_seconds=self._access_seconds)
        refresh = self._encode(user_id=user_id, role=role, type_="refresh",
                               now=now, ttl_seconds=self._refresh_seconds)
        return TokenPair(
            access_token=access,
            refresh_token=refresh,
            access_expires_in_seconds=self._access_seconds,
        )

    def decode(self, token: str) -> Result[TokenClaims]:
        try:
            payload = jwt.decode(token, self._secret, algorithms=[self._alg])
        except ExpiredSignatureError:
            return Result.failure("Token expirado.", status_code=401)
        except JWTError as exc:
            return Result.failure(f"Token inválido: {exc}", status_code=401)

        try:
            return Result.success(TokenClaims(
                user_id=UUID(payload["sub"]),
                role=Role(payload["role"]),
                type=payload["type"],
            ))
        except (KeyError, ValueError, TypeError) as exc:
            return Result.failure(f"Token malformado: {exc}", status_code=401)

    def _encode(
        self,
        *,
        user_id: UUID,
        role: Role,
        type_: TokenType,
        now: datetime,
        ttl_seconds: int,
    ) -> str:
        payload = {
            "sub": str(user_id),
            "role": role.value,
            "type": type_,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(seconds=ttl_seconds)).timestamp()),
        }
        return jwt.encode(payload, self._secret, algorithm=self._alg)
```

- [ ] **Step 4: Run — expect PASS (6 tests, ~3s due to the `time.sleep` calls).**

- [ ] **Step 5: Commit**

```bash
git add app/infrastructure/auth/jose_jwt_service.py tests/integration/auth/test_jose_jwt_service.py
git commit -m "$(cat <<'EOF'
feat(auth): add JoseJwtService implementing IJwtService

HS256-signed JWTs. Payload: sub (user_id), role, type (access|refresh),
iat, exp. decode() returns Result.failure with status_code=401 on
expired/invalid/malformed tokens — get_current_user maps that straight
to a 401 response without raising.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

### Task B5 — Rewrite `app/infrastructure/db/mappings/user.py` for the new schema

**File:** `app/infrastructure/db/mappings/user.py`.

- [ ] **Step 1: Replace the file content**

```python
from __future__ import annotations
from uuid import UUID
from sqlalchemy import String, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import CHAR
from app.infrastructure.db.base import Base, TimestampMixin


class UserModel(Base, TimestampMixin):
    __tablename__ = "users"

    # CHAR(36) works on Postgres, SQL Server, and SQLite (tests).
    id: Mapped[UUID] = mapped_column(CHAR(36), primary_key=True)
    email: Mapped[str] = mapped_column(String(254), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    phone_number: Mapped[str | None] = mapped_column(String(14), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
```

- [ ] **Step 2: Smoke import**

```bash
.venv/bin/python -c "from app.infrastructure.db.mappings.user import UserModel; print(UserModel.__tablename__, sorted(c.name for c in UserModel.__table__.columns))"
```

Expect: `users ['created_at', 'email', 'full_name', 'id', 'is_active', 'password_hash', 'phone_number', 'role', 'updated_at']`.

- [ ] **Step 3: Run pytest — should fail**

`.venv/bin/pytest -q` — the existing `users` repository and tests still reference the old fields (`name`, `phone`, `credit_score`, `balance`). They WILL fail. This is expected — Tasks B6 (rewrite repo) and Unit E (delete old sample) finish the job.

For now, before commit, narrow the test run to just what's verified at this point:

```bash
.venv/bin/pytest tests/unit/domain/accounts/ tests/integration/auth/ tests/unit/core/ -q
```

Should be green.

- [ ] **Step 4: Commit**

```bash
git add app/infrastructure/db/mappings/user.py
git commit -m "$(cat <<'EOF'
feat(db): rewrite users table mapping for accounts feature

New schema: id, email (unique), password_hash, role (indexed),
full_name, phone_number (NULLable), is_active, created_at, updated_at.
Drops the previous sample fields (name, phone, credit_score, balance).
The OLD UserRepository and old users sample tests are now broken — they
will be rewritten or deleted in subsequent tasks.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

### Task B6 — Rewrite `app/infrastructure/repositories/user_repository.py` for the `accounts.User`

**File:** `app/infrastructure/repositories/user_repository.py`.

- [ ] **Step 1: Failing integration test**

`tests/integration/accounts/__init__.py` (empty), `tests/integration/accounts/test_user_repository.py`:

```python
from __future__ import annotations
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.domain.accounts.role import Role
from app.domain.accounts.user import User
from app.infrastructure.db.base import Base
from app.infrastructure.db.mappings import user  # noqa: F401  (registers mapping)
from app.infrastructure.repositories.user_repository import UserRepository


@pytest_asyncio.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sm = async_sessionmaker(engine, expire_on_commit=False)
    async with sm() as s:
        yield s
    await engine.dispose()


def make_user(email: str = "alice@example.com", role: Role = Role.CUSTOMER) -> User:
    r = User.create(
        email=email,
        password_hash="$argon2id$fake",
        role=role,
        full_name="Alice",
        phone="+5511999999999",
    )
    assert r.is_success
    return r.value


@pytest.mark.asyncio
async def test_add_and_get_by_id(session):
    repo = UserRepository(session)
    u = make_user()
    await repo.add(u)
    await session.commit()

    fetched = await repo.get_by_id(u.id)
    assert fetched is not None
    assert str(fetched.email) == "alice@example.com"
    assert fetched.role is Role.CUSTOMER
    assert fetched.full_name == "Alice"


@pytest.mark.asyncio
async def test_get_by_email_case_insensitive(session):
    repo = UserRepository(session)
    await repo.add(make_user("Alice@Example.com"))
    await session.commit()
    found = await repo.get_by_email("alice@example.com")
    assert found is not None
    assert str(found.email) == "alice@example.com"


@pytest.mark.asyncio
async def test_get_by_email_missing_returns_none(session):
    repo = UserRepository(session)
    assert await repo.get_by_email("nobody@example.com") is None


@pytest.mark.asyncio
async def test_update_role(session):
    repo = UserRepository(session)
    u = make_user(role=Role.CUSTOMER)
    await repo.add(u)
    await session.commit()

    u.set_role(Role.OWNER)
    await repo.update(u)
    await session.commit()

    fetched = await repo.get_by_id(u.id)
    assert fetched.role is Role.OWNER


@pytest.mark.asyncio
async def test_list_active_excludes_deactivated(session):
    repo = UserRepository(session)
    a = make_user("a@example.com")
    b = make_user("b@example.com")
    b.deactivate()
    await repo.add(a)
    await repo.add(b)
    await session.commit()

    rows = await repo.list_active()
    assert len(rows) == 1
    assert str(rows[0].email) == "a@example.com"
```

- [ ] **Step 2: Run — expect FAIL.**

- [ ] **Step 3: Implement (full rewrite)**

`app/infrastructure/repositories/user_repository.py`:

```python
from __future__ import annotations
from typing import Sequence
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.accounts.role import Role
from app.domain.accounts.user import User
from app.domain.accounts.repository import IUserRepository
from app.domain.shared.value_objects.brazilian_phone import BrazilianPhone
from app.domain.shared.value_objects.email import Email
from app.infrastructure.db.mappings.user import UserModel
from app.infrastructure.repositories.base_repository import BaseRepository


class UserRepository(BaseRepository[UserModel], IUserRepository):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, UserModel)

    async def get_by_id(self, user_id: UUID) -> User | None:
        row = await super().get_by_id(user_id)
        return self._to_entity(row) if row else None

    async def get_by_email(self, email: str) -> User | None:
        normalized = email.strip().lower()
        stmt = select(UserModel).where(UserModel.email == normalized)
        row = await self._first_or_default(stmt)
        return self._to_entity(row) if row else None

    async def list_active(self, *, limit: int = 50, offset: int = 0) -> Sequence[User]:
        stmt = (
            select(UserModel)
            .where(UserModel.is_active.is_(True))
            .order_by(UserModel.created_at.desc())
            .limit(limit).offset(offset)
        )
        rows = await self._to_list(stmt)
        return [self._to_entity(r) for r in rows]

    async def add(self, user: User) -> None:
        self._session.add(self._to_model(user))

    async def update(self, user: User) -> None:
        row = await self._session.get(UserModel, str(user.id))
        if row is None:
            raise LookupError(f"User {user.id} not found.")
        row.email = user.email.value
        row.password_hash = user.password_hash
        row.role = user.role.value
        row.full_name = user.full_name
        row.phone_number = user.phone.value if user.phone else None
        row.is_active = user.is_active
        row.updated_at = user.updated_at

    @staticmethod
    def _to_model(u: User) -> UserModel:
        return UserModel(
            id=str(u.id),
            email=u.email.value,
            password_hash=u.password_hash,
            role=u.role.value,
            full_name=u.full_name,
            phone_number=u.phone.value if u.phone else None,
            is_active=u.is_active,
            created_at=u.created_at,
            updated_at=u.updated_at,
        )

    @staticmethod
    def _to_entity(row: UserModel) -> User:
        phone_vo: BrazilianPhone | None = None
        if row.phone_number:
            phone_vo = BrazilianPhone(
                value=row.phone_number,
                is_mobile=len(row.phone_number) == 14,
            )
        return User(
            id=UUID(str(row.id)),
            email=Email(value=row.email),
            password_hash=row.password_hash,
            role=Role(row.role),
            full_name=row.full_name,
            phone=phone_vo,
            is_active=row.is_active,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
```

- [ ] **Step 4: Run integration tests — expect 5 PASS.**

`.venv/bin/pytest tests/integration/accounts/ -q`

The OLD `tests/integration/users/` will still fail because the old `users` sample's domain object no longer matches; that's fine — Unit E deletes them.

- [ ] **Step 5: Commit**

```bash
git add app/infrastructure/repositories/user_repository.py tests/integration/accounts/
git commit -m "$(cat <<'EOF'
feat(accounts): rewrite UserRepository for the new User aggregate

Implements IUserRepository against the rewritten users table. update()
no longer touches credit_score/balance; instead it persists role,
password_hash, full_name, phone_number, is_active. _to_entity() rebuilds
the BrazilianPhone VO from the nullable phone_number column.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

### Task B7 — Generate the Alembic migration for the schema change

**Files:** new revision under `app/migrations/versions/`.

- [ ] **Step 1: Generate**

```bash
.venv/bin/alembic revision --autogenerate -m "accounts_users_schema"
```

This produces a new file in `app/migrations/versions/`. Note the filename and revision id.

- [ ] **Step 2: Inspect the generated revision**

Open the new file. Confirm `upgrade()` does some combination of: drop columns `name`, `phone`, `credit_score`, `balance`; add columns `password_hash`, `role`, `full_name`, `phone_number`. The autogenerator may also create an index on `role`.

If the autogenerator generated something nonsensical (e.g., dropping the whole table), STOP and report. Otherwise proceed.

- [ ] **Step 3: For SQLite, ALTER COLUMN may need batch_alter_table**

If the generated revision uses bare `op.alter_column(...)` calls and the test env runs on SQLite, wrap them in `with op.batch_alter_table('users') as batch:`. Most ALTER ops on SQLite require batch mode.

If you're unsure, the safest path: replace the whole `upgrade()` body with:

```python
def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.drop_column("credit_score")
        batch.drop_column("balance")
        batch.drop_column("phone")
        batch.alter_column("name", new_column_name="full_name")  # rename name -> full_name
        batch.add_column(sa.Column("password_hash", sa.String(length=255), nullable=False, server_default=""))
        batch.add_column(sa.Column("role", sa.String(length=16), nullable=False, server_default="customer"))
        batch.add_column(sa.Column("phone_number", sa.String(length=14), nullable=True))
        batch.create_index(op.f("ix_users_role"), ["role"])
    # Drop server defaults — they were only needed to fill existing rows
    op.execute("UPDATE users SET password_hash = '' WHERE password_hash IS NULL")
```

(Adjust to match what autogenerate produced; this is the reference shape.)

The matching `downgrade()` reverses it.

- [ ] **Step 4: Run pytest**

The e2e conftest creates a fresh in-memory DB with `Base.metadata.create_all` (it does NOT run migrations), so e2e tests are unaffected by the migration content. Integration tests for `accounts` we already verified in Task B6.

```bash
.venv/bin/pytest tests/unit/domain/accounts/ tests/integration/accounts/ tests/integration/auth/ tests/unit/core/ -q
```

Expect green.

- [ ] **Step 5: Commit**

```bash
git add app/migrations/versions/
git commit -m "$(cat <<'EOF'
feat(db): alembic revision for accounts users schema

ALTERs the users table: drops credit_score/balance/phone, renames name
to full_name, adds password_hash/role/phone_number, indexes role.
Uses batch_alter_table for SQLite compatibility.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## UNIT C — Use cases

Six handlers. Each gets a unit test against an in-memory fake.

### Task C1 — In-memory fake repository + DTOs

**Files:** `tests/unit/use_cases/accounts/__init__.py`, `tests/unit/use_cases/accounts/fakes/__init__.py`, `tests/unit/use_cases/accounts/fakes/in_memory_user_repository.py`, `tests/unit/use_cases/accounts/fakes/fake_password_hasher.py`, `app/use_cases/accounts/__init__.py`, `app/use_cases/accounts/dtos.py`.

- [ ] **Step 1: Implement the fakes**

`tests/unit/use_cases/accounts/fakes/in_memory_user_repository.py`:

```python
from __future__ import annotations
from typing import Sequence
from uuid import UUID
from app.domain.accounts.user import User
from app.domain.accounts.repository import IUserRepository


class InMemoryUserRepository(IUserRepository):
    def __init__(self, *, seed: Sequence[User] = ()) -> None:
        self._by_id: dict[UUID, User] = {u.id: u for u in seed}

    async def get_by_id(self, user_id: UUID) -> User | None:
        return self._by_id.get(user_id)

    async def get_by_email(self, email: str) -> User | None:
        target = email.strip().lower()
        for u in self._by_id.values():
            if str(u.email) == target:
                return u
        return None

    async def list_active(self, *, limit: int = 50, offset: int = 0) -> Sequence[User]:
        active = [u for u in self._by_id.values() if u.is_active]
        active.sort(key=lambda u: u.created_at, reverse=True)
        return active[offset:offset + limit]

    async def add(self, user: User) -> None:
        self._by_id[user.id] = user

    async def update(self, user: User) -> None:
        if user.id not in self._by_id:
            raise LookupError(f"User {user.id} not found.")
        self._by_id[user.id] = user
```

`tests/unit/use_cases/accounts/fakes/fake_password_hasher.py`:

```python
from __future__ import annotations
from app.domain.accounts.password_hasher import IPasswordHasher


class FakePasswordHasher(IPasswordHasher):
    """Reversible fake: hash(x) == 'fake:' + x. Use in handler tests."""

    def hash(self, plaintext: str) -> str:
        return f"fake:{plaintext}"

    def verify(self, plaintext: str, hashed: str) -> bool:
        return hashed == f"fake:{plaintext}"

    def needs_rehash(self, hashed: str) -> bool:
        return not hashed.startswith("fake:")
```

- [ ] **Step 2: Implement DTOs**

`app/use_cases/accounts/dtos.py`:

```python
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID
from app.domain.accounts.role import Role
from app.domain.accounts.user import User


@dataclass(frozen=True, slots=True)
class UserDto:
    id: UUID
    email: str
    role: Role
    full_name: str
    phone: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_entity(cls, u: User) -> "UserDto":
        return cls(
            id=u.id,
            email=str(u.email),
            role=u.role,
            full_name=u.full_name,
            phone=str(u.phone) if u.phone else None,
            is_active=u.is_active,
            created_at=u.created_at,
            updated_at=u.updated_at,
        )


@dataclass(frozen=True, slots=True)
class TokenPairDto:
    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int
    user: UserDto
```

- [ ] **Step 3: Smoke import**

```bash
.venv/bin/python -c "from app.use_cases.accounts.dtos import UserDto, TokenPairDto; from tests.unit.use_cases.accounts.fakes.in_memory_user_repository import InMemoryUserRepository; from tests.unit.use_cases.accounts.fakes.fake_password_hasher import FakePasswordHasher; print('ok')"
```

- [ ] **Step 4: Commit**

```bash
git add app/use_cases/accounts/__init__.py app/use_cases/accounts/dtos.py tests/unit/use_cases/accounts/
git commit -m "$(cat <<'EOF'
feat(accounts): add UserDto + TokenPairDto + handler test fakes

UserDto exposes role + is_active. TokenPairDto wraps a JWT pair plus
the user payload (so /auth/login can return everything in one go).
InMemoryUserRepository and FakePasswordHasher back the handler tests
in subsequent tasks.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

### Task C2 — `RegisterUserHandler`

**Files:** `app/use_cases/accounts/commands/__init__.py`, `app/use_cases/accounts/commands/register_user.py`, `tests/unit/use_cases/accounts/commands/__init__.py`, `tests/unit/use_cases/accounts/commands/test_register_user.py`.

- [ ] **Step 1: Failing test**

```python
from __future__ import annotations
import pytest
from app.domain.accounts.role import Role
from app.use_cases.accounts.commands.register_user import (
    RegisterUserCommand, RegisterUserHandler,
)
from tests.unit.use_cases.accounts.fakes.in_memory_user_repository import InMemoryUserRepository
from tests.unit.use_cases.accounts.fakes.fake_password_hasher import FakePasswordHasher


def make_handler():
    repo = InMemoryUserRepository()
    hasher = FakePasswordHasher()
    return RegisterUserHandler(repo, hasher), repo, hasher


@pytest.mark.asyncio
async def test_register_customer_success():
    handler, repo, _ = make_handler()
    r = await handler.handle(RegisterUserCommand(
        email="alice@example.com",
        password="hunter2-strong",
        role=Role.CUSTOMER,
        full_name="Alice",
        phone=None,
    ))
    assert r.is_success
    dto = r.value
    assert dto.email == "alice@example.com"
    assert dto.role is Role.CUSTOMER
    # Password is hashed, not stored
    persisted = await repo.get_by_email("alice@example.com")
    assert persisted.password_hash == "fake:hunter2-strong"


@pytest.mark.asyncio
async def test_register_owner_success():
    handler, _, _ = make_handler()
    r = await handler.handle(RegisterUserCommand(
        email="bob@example.com",
        password="hunter2-strong",
        role=Role.OWNER,
        full_name="Bob",
        phone="+5511999999999",
    ))
    assert r.is_success
    assert r.value.role is Role.OWNER


@pytest.mark.asyncio
async def test_register_admin_rejected():
    handler, _, _ = make_handler()
    r = await handler.handle(RegisterUserCommand(
        email="admin@example.com",
        password="hunter2-strong",
        role=Role.ADMIN,
        full_name="Adm",
        phone=None,
    ))
    assert r.is_failure
    assert r.status_code == 403
    assert "admin" in r.error.lower()


@pytest.mark.asyncio
async def test_register_email_collision():
    handler, repo, _ = make_handler()
    await handler.handle(RegisterUserCommand(
        email="alice@example.com", password="hunter2-strong",
        role=Role.CUSTOMER, full_name="Alice", phone=None,
    ))
    r = await handler.handle(RegisterUserCommand(
        email="alice@example.com", password="other-pw",
        role=Role.CUSTOMER, full_name="Alice2", phone=None,
    ))
    assert r.is_failure
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_register_short_password():
    handler, _, _ = make_handler()
    r = await handler.handle(RegisterUserCommand(
        email="alice@example.com", password="abc",
        role=Role.CUSTOMER, full_name="Alice", phone=None,
    ))
    assert r.is_failure
    assert r.status_code == 422
    assert "senha" in r.error.lower() or "password" in r.error.lower()


@pytest.mark.asyncio
async def test_register_invalid_email():
    handler, _, _ = make_handler()
    r = await handler.handle(RegisterUserCommand(
        email="not-an-email", password="hunter2-strong",
        role=Role.CUSTOMER, full_name="Alice", phone=None,
    ))
    assert r.is_failure
    assert r.status_code == 422
```

- [ ] **Step 2: Run — expect FAIL.**

- [ ] **Step 3: Implement**

`app/use_cases/accounts/commands/register_user.py`:

```python
from __future__ import annotations
from dataclasses import dataclass
from app.domain.accounts.repository import IUserRepository
from app.domain.accounts.password_hasher import IPasswordHasher
from app.domain.accounts.role import Role
from app.domain.accounts.user import User
from app.domain.shared.result import Result
from app.use_cases.accounts.dtos import UserDto


MIN_PASSWORD_LENGTH = 8


@dataclass(frozen=True, slots=True)
class RegisterUserCommand:
    email: str
    password: str
    role: Role
    full_name: str
    phone: str | None


class RegisterUserHandler:
    def __init__(self, users: IUserRepository, hasher: IPasswordHasher) -> None:
        self._users = users
        self._hasher = hasher

    async def handle(self, cmd: RegisterUserCommand) -> Result[UserDto]:
        if not cmd.role.is_self_registerable():
            return Result.failure(
                "Não é permitido registrar contas admin via cadastro público.",
                status_code=403,
            )

        if len(cmd.password) < MIN_PASSWORD_LENGTH:
            return Result.failure(
                f"Senha precisa ter ao menos {MIN_PASSWORD_LENGTH} caracteres.",
                status_code=422,
            )

        existing = await self._users.get_by_email(cmd.email)
        if existing is not None:
            return Result.failure(
                f"Email já cadastrado: {cmd.email}",
                status_code=409,
            )

        user_r = User.create(
            email=cmd.email,
            password_hash=self._hasher.hash(cmd.password),
            role=cmd.role,
            full_name=cmd.full_name,
            phone=cmd.phone,
        )
        if user_r.is_failure:
            return Result.failure(user_r.error, status_code=422)

        user = user_r.value
        await self._users.add(user)
        return Result.success(UserDto.from_entity(user), status_code=201)
```

- [ ] **Step 4: Run — expect PASS (6).**

- [ ] **Step 5: Commit**

```bash
git add app/use_cases/accounts/commands/__init__.py app/use_cases/accounts/commands/register_user.py tests/unit/use_cases/accounts/commands/
git commit -m "$(cat <<'EOF'
feat(accounts): add RegisterUserHandler

Public registration for CUSTOMER and OWNER roles. Rejects ADMIN with
403 (admin accounts are seeded out-of-band, see Plan 07). Enforces
minimum password length (8). Email collision → 409. Failed User.create
(invalid email, blank full_name, etc.) → 422. Success → 201 with the
UserDto (no token; client logs in next).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

### Task C3 — `LoginHandler`

**Files:** `app/use_cases/accounts/commands/login.py`, `tests/unit/use_cases/accounts/commands/test_login.py`.

- [ ] **Step 1: Failing test**

```python
from __future__ import annotations
import pytest
from uuid import uuid4
from app.domain.accounts.role import Role
from app.domain.accounts.user import User
from app.use_cases.accounts.commands.login import LoginCommand, LoginHandler
from tests.unit.use_cases.accounts.fakes.in_memory_user_repository import InMemoryUserRepository
from tests.unit.use_cases.accounts.fakes.fake_password_hasher import FakePasswordHasher


class FakeJwtService:
    def __init__(self):
        self.last_user_id = None
        self.last_role = None

    def issue_pair(self, *, user_id, role):
        from app.domain.accounts.jwt_service import TokenPair
        self.last_user_id = user_id
        self.last_role = role
        return TokenPair(
            access_token=f"acc-{user_id}",
            refresh_token=f"ref-{user_id}",
            access_expires_in_seconds=1800,
        )

    def decode(self, token):
        raise NotImplementedError


def seed_user(*, email="alice@example.com", password="hunter2-strong",
              role=Role.CUSTOMER, is_active=True):
    h = FakePasswordHasher()
    r = User.create(
        email=email, password_hash=h.hash(password), role=role,
        full_name="Alice", phone=None,
    )
    u = r.value
    if not is_active:
        u.deactivate()
    return u


def make_handler(seed_users=()):
    repo = InMemoryUserRepository(seed=seed_users)
    hasher = FakePasswordHasher()
    jwt_svc = FakeJwtService()
    return LoginHandler(repo, hasher, jwt_svc), repo, hasher, jwt_svc


@pytest.mark.asyncio
async def test_login_success():
    user = seed_user()
    handler, _, _, jwt_svc = make_handler([user])
    r = await handler.handle(LoginCommand(email="alice@example.com", password="hunter2-strong"))
    assert r.is_success
    pair = r.value
    assert pair.access_token == f"acc-{user.id}"
    assert pair.user.email == "alice@example.com"
    assert jwt_svc.last_role is Role.CUSTOMER


@pytest.mark.asyncio
async def test_login_wrong_password():
    user = seed_user()
    handler, _, _, _ = make_handler([user])
    r = await handler.handle(LoginCommand(email="alice@example.com", password="wrong"))
    assert r.is_failure
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_login_unknown_email():
    handler, _, _, _ = make_handler([])
    r = await handler.handle(LoginCommand(email="nobody@example.com", password="x"))
    assert r.is_failure
    assert r.status_code == 401  # same code as wrong password — don't leak existence


@pytest.mark.asyncio
async def test_login_deactivated_account():
    user = seed_user(is_active=False)
    handler, _, _, _ = make_handler([user])
    r = await handler.handle(LoginCommand(email="alice@example.com", password="hunter2-strong"))
    assert r.is_failure
    assert r.status_code == 403
```

- [ ] **Step 2: Run — expect FAIL.**

- [ ] **Step 3: Implement**

`app/use_cases/accounts/commands/login.py`:

```python
from __future__ import annotations
from dataclasses import dataclass
from app.domain.accounts.repository import IUserRepository
from app.domain.accounts.password_hasher import IPasswordHasher
from app.domain.accounts.jwt_service import IJwtService
from app.domain.shared.result import Result
from app.use_cases.accounts.dtos import TokenPairDto, UserDto


@dataclass(frozen=True, slots=True)
class LoginCommand:
    email: str
    password: str


class LoginHandler:
    def __init__(
        self,
        users: IUserRepository,
        hasher: IPasswordHasher,
        jwt_service: IJwtService,
    ) -> None:
        self._users = users
        self._hasher = hasher
        self._jwt = jwt_service

    async def handle(self, cmd: LoginCommand) -> Result[TokenPairDto]:
        # Same 401 message whether the email is unknown or the password is wrong,
        # so callers can't enumerate accounts.
        invalid = Result.failure("Email ou senha inválidos.", status_code=401)

        user = await self._users.get_by_email(cmd.email)
        if user is None:
            return invalid

        if not self._hasher.verify(cmd.password, user.password_hash):
            return invalid

        if not user.is_active:
            return Result.failure(
                "Conta desativada. Contate um administrador.", status_code=403,
            )

        # Opportunistic rehash if Argon2 params have been bumped server-side.
        if self._hasher.needs_rehash(user.password_hash):
            user.change_password_hash(self._hasher.hash(cmd.password))
            await self._users.update(user)

        pair = self._jwt.issue_pair(user_id=user.id, role=user.role)
        return Result.success(TokenPairDto(
            access_token=pair.access_token,
            refresh_token=pair.refresh_token,
            token_type=pair.token_type,
            expires_in=pair.access_expires_in_seconds,
            user=UserDto.from_entity(user),
        ))
```

- [ ] **Step 4: Run — expect PASS (4).**

- [ ] **Step 5: Commit**

```bash
git add app/use_cases/accounts/commands/login.py tests/unit/use_cases/accounts/commands/test_login.py
git commit -m "$(cat <<'EOF'
feat(accounts): add LoginHandler

email + password → TokenPairDto with the freshly-issued access/refresh
JWTs and the UserDto. Wrong password and unknown email both return the
same 401 message ("Email ou senha inválidos.") so callers can't
enumerate accounts. Deactivated accounts get 403 with a distinct
message. Opportunistic rehash on successful login when Argon2 params
have been bumped server-side.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

### Task C4 — `RefreshTokenHandler`

**Files:** `app/use_cases/accounts/commands/refresh_token.py`, `tests/unit/use_cases/accounts/commands/test_refresh_token.py`.

- [ ] **Step 1: Failing test**

```python
from __future__ import annotations
import pytest
from uuid import uuid4
from app.domain.accounts.jwt_service import TokenClaims, TokenPair
from app.domain.accounts.role import Role
from app.domain.accounts.user import User
from app.domain.shared.result import Result
from app.use_cases.accounts.commands.refresh_token import (
    RefreshTokenCommand, RefreshTokenHandler,
)
from tests.unit.use_cases.accounts.fakes.in_memory_user_repository import InMemoryUserRepository
from tests.unit.use_cases.accounts.fakes.fake_password_hasher import FakePasswordHasher


class StubJwtService:
    def __init__(self, *, decode_result: Result[TokenClaims]):
        self._decode_result = decode_result

    def issue_pair(self, *, user_id, role):
        return TokenPair(
            access_token=f"new-acc-{user_id}",
            refresh_token=f"new-ref-{user_id}",
            access_expires_in_seconds=1800,
        )

    def decode(self, token):
        return self._decode_result


def seed_active_user(role=Role.CUSTOMER):
    h = FakePasswordHasher()
    r = User.create(
        email="alice@example.com", password_hash=h.hash("hunter2-strong"),
        role=role, full_name="Alice", phone=None,
    )
    return r.value


@pytest.mark.asyncio
async def test_refresh_success():
    user = seed_active_user()
    repo = InMemoryUserRepository(seed=[user])
    jwt_svc = StubJwtService(decode_result=Result.success(
        TokenClaims(user_id=user.id, role=user.role, type="refresh")
    ))
    handler = RefreshTokenHandler(repo, jwt_svc)
    r = await handler.handle(RefreshTokenCommand(refresh_token="ignored"))
    assert r.is_success
    assert r.value.access_token == f"new-acc-{user.id}"
    assert r.value.user.email == "alice@example.com"


@pytest.mark.asyncio
async def test_refresh_with_access_token_rejected():
    user = seed_active_user()
    repo = InMemoryUserRepository(seed=[user])
    jwt_svc = StubJwtService(decode_result=Result.success(
        TokenClaims(user_id=user.id, role=user.role, type="access"),
    ))
    handler = RefreshTokenHandler(repo, jwt_svc)
    r = await handler.handle(RefreshTokenCommand(refresh_token="ignored"))
    assert r.is_failure
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_refresh_invalid_token():
    repo = InMemoryUserRepository()
    jwt_svc = StubJwtService(decode_result=Result.failure("expired", status_code=401))
    handler = RefreshTokenHandler(repo, jwt_svc)
    r = await handler.handle(RefreshTokenCommand(refresh_token="ignored"))
    assert r.is_failure
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_refresh_user_deactivated_after_token_issued():
    user = seed_active_user()
    user.deactivate()
    repo = InMemoryUserRepository(seed=[user])
    jwt_svc = StubJwtService(decode_result=Result.success(
        TokenClaims(user_id=user.id, role=user.role, type="refresh")
    ))
    handler = RefreshTokenHandler(repo, jwt_svc)
    r = await handler.handle(RefreshTokenCommand(refresh_token="ignored"))
    assert r.is_failure
    assert r.status_code == 403
```

- [ ] **Step 2: Run — expect FAIL.**

- [ ] **Step 3: Implement**

`app/use_cases/accounts/commands/refresh_token.py`:

```python
from __future__ import annotations
from dataclasses import dataclass
from app.domain.accounts.repository import IUserRepository
from app.domain.accounts.jwt_service import IJwtService
from app.domain.shared.result import Result
from app.use_cases.accounts.dtos import TokenPairDto, UserDto


@dataclass(frozen=True, slots=True)
class RefreshTokenCommand:
    refresh_token: str


class RefreshTokenHandler:
    def __init__(self, users: IUserRepository, jwt_service: IJwtService) -> None:
        self._users = users
        self._jwt = jwt_service

    async def handle(self, cmd: RefreshTokenCommand) -> Result[TokenPairDto]:
        decoded = self._jwt.decode(cmd.refresh_token)
        if decoded.is_failure:
            return Result.failure(decoded.error, status_code=401)

        claims = decoded.value
        if claims.type != "refresh":
            return Result.failure(
                "Token de acesso não pode ser usado para refresh.",
                status_code=401,
            )

        user = await self._users.get_by_id(claims.user_id)
        if user is None:
            return Result.failure("Usuário não encontrado.", status_code=401)

        if not user.is_active:
            return Result.failure(
                "Conta desativada. Faça login novamente.",
                status_code=403,
            )

        pair = self._jwt.issue_pair(user_id=user.id, role=user.role)
        return Result.success(TokenPairDto(
            access_token=pair.access_token,
            refresh_token=pair.refresh_token,
            token_type=pair.token_type,
            expires_in=pair.access_expires_in_seconds,
            user=UserDto.from_entity(user),
        ))
```

- [ ] **Step 4: Run — expect PASS (4).**

- [ ] **Step 5: Commit**

```bash
git add app/use_cases/accounts/commands/refresh_token.py tests/unit/use_cases/accounts/commands/test_refresh_token.py
git commit -m "$(cat <<'EOF'
feat(accounts): add RefreshTokenHandler

Verifies the supplied token decodes, has type=refresh, the user still
exists, and the user is still active. Issues a fresh access+refresh
pair and returns it with the UserDto. Access tokens used as refresh
tokens are rejected (401).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

### Task C5 — `GetUserByIdHandler` (used by /me)

**Files:** `app/use_cases/accounts/queries/__init__.py`, `app/use_cases/accounts/queries/get_user_by_id.py`, `tests/unit/use_cases/accounts/queries/__init__.py`, `tests/unit/use_cases/accounts/queries/test_get_user_by_id.py`.

- [ ] **Step 1: Failing test**

```python
from __future__ import annotations
import pytest
from uuid import uuid4
from app.domain.accounts.role import Role
from app.domain.accounts.user import User
from app.use_cases.accounts.queries.get_user_by_id import (
    GetUserByIdQuery, GetUserByIdHandler,
)
from tests.unit.use_cases.accounts.fakes.in_memory_user_repository import InMemoryUserRepository
from tests.unit.use_cases.accounts.fakes.fake_password_hasher import FakePasswordHasher


def seed_user():
    h = FakePasswordHasher()
    r = User.create(
        email="alice@example.com", password_hash=h.hash("pw"),
        role=Role.OWNER, full_name="Alice", phone=None,
    )
    return r.value


@pytest.mark.asyncio
async def test_get_existing():
    user = seed_user()
    repo = InMemoryUserRepository(seed=[user])
    handler = GetUserByIdHandler(repo)
    r = await handler.handle(GetUserByIdQuery(user_id=user.id))
    assert r.is_success
    assert r.value.email == "alice@example.com"


@pytest.mark.asyncio
async def test_get_missing():
    repo = InMemoryUserRepository()
    handler = GetUserByIdHandler(repo)
    r = await handler.handle(GetUserByIdQuery(user_id=uuid4()))
    assert r.is_failure
    assert r.status_code == 404
```

- [ ] **Step 2: Run — expect FAIL.**

- [ ] **Step 3: Implement**

`app/use_cases/accounts/queries/get_user_by_id.py`:

```python
from __future__ import annotations
from dataclasses import dataclass
from uuid import UUID
from app.domain.accounts.repository import IUserRepository
from app.domain.shared.result import Result
from app.use_cases.accounts.dtos import UserDto


@dataclass(frozen=True, slots=True)
class GetUserByIdQuery:
    user_id: UUID


class GetUserByIdHandler:
    def __init__(self, users: IUserRepository) -> None:
        self._users = users

    async def handle(self, q: GetUserByIdQuery) -> Result[UserDto]:
        user = await self._users.get_by_id(q.user_id)
        if user is None:
            return Result.failure("Usuário não encontrado.", status_code=404)
        return Result.success(UserDto.from_entity(user))
```

- [ ] **Step 4: Run — expect PASS (2).**

- [ ] **Step 5: Commit**

```bash
git add app/use_cases/accounts/queries/__init__.py app/use_cases/accounts/queries/get_user_by_id.py tests/unit/use_cases/accounts/queries/
git commit -m "$(cat <<'EOF'
feat(accounts): add GetUserByIdHandler (powers /me)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

### Task C6 — `PromoteUserRoleHandler` and `DeactivateUserHandler`

**Files:** `app/use_cases/accounts/commands/promote_user_role.py`, `app/use_cases/accounts/commands/deactivate_user.py`, paired tests under `tests/unit/use_cases/accounts/commands/`.

- [ ] **Step 1: Failing tests for both handlers**

`test_promote_user_role.py`:

```python
from __future__ import annotations
import pytest
from uuid import uuid4
from app.domain.accounts.role import Role
from app.domain.accounts.user import User
from app.use_cases.accounts.commands.promote_user_role import (
    PromoteUserRoleCommand, PromoteUserRoleHandler,
)
from tests.unit.use_cases.accounts.fakes.in_memory_user_repository import InMemoryUserRepository
from tests.unit.use_cases.accounts.fakes.fake_password_hasher import FakePasswordHasher


def seed_user(role=Role.CUSTOMER):
    h = FakePasswordHasher()
    r = User.create(
        email="alice@example.com", password_hash=h.hash("pw"),
        role=role, full_name="Alice", phone=None,
    )
    return r.value


@pytest.mark.asyncio
async def test_promote_customer_to_owner():
    user = seed_user(Role.CUSTOMER)
    repo = InMemoryUserRepository(seed=[user])
    handler = PromoteUserRoleHandler(repo)
    r = await handler.handle(PromoteUserRoleCommand(
        user_id=user.id, new_role=Role.OWNER,
    ))
    assert r.is_success
    refreshed = await repo.get_by_id(user.id)
    assert refreshed.role is Role.OWNER


@pytest.mark.asyncio
async def test_promote_missing_user():
    repo = InMemoryUserRepository()
    handler = PromoteUserRoleHandler(repo)
    r = await handler.handle(PromoteUserRoleCommand(user_id=uuid4(), new_role=Role.OWNER))
    assert r.is_failure
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_promote_to_admin_allowed():
    """The handler accepts ADMIN — only the route-level guard restricts who can call this handler."""
    user = seed_user(Role.OWNER)
    repo = InMemoryUserRepository(seed=[user])
    handler = PromoteUserRoleHandler(repo)
    r = await handler.handle(PromoteUserRoleCommand(user_id=user.id, new_role=Role.ADMIN))
    assert r.is_success
    refreshed = await repo.get_by_id(user.id)
    assert refreshed.role is Role.ADMIN


@pytest.mark.asyncio
async def test_promote_same_role_is_noop_but_succeeds():
    user = seed_user(Role.OWNER)
    repo = InMemoryUserRepository(seed=[user])
    handler = PromoteUserRoleHandler(repo)
    r = await handler.handle(PromoteUserRoleCommand(user_id=user.id, new_role=Role.OWNER))
    assert r.is_success
```

`test_deactivate_user.py`:

```python
from __future__ import annotations
import pytest
from uuid import uuid4
from app.domain.accounts.role import Role
from app.domain.accounts.user import User
from app.use_cases.accounts.commands.deactivate_user import (
    DeactivateUserCommand, DeactivateUserHandler,
)
from tests.unit.use_cases.accounts.fakes.in_memory_user_repository import InMemoryUserRepository
from tests.unit.use_cases.accounts.fakes.fake_password_hasher import FakePasswordHasher


def seed_user():
    h = FakePasswordHasher()
    r = User.create(
        email="alice@example.com", password_hash=h.hash("pw"),
        role=Role.OWNER, full_name="Alice", phone=None,
    )
    return r.value


@pytest.mark.asyncio
async def test_deactivate_user():
    user = seed_user()
    repo = InMemoryUserRepository(seed=[user])
    handler = DeactivateUserHandler(repo)
    r = await handler.handle(DeactivateUserCommand(user_id=user.id))
    assert r.is_success
    refreshed = await repo.get_by_id(user.id)
    assert refreshed.is_active is False


@pytest.mark.asyncio
async def test_deactivate_missing_user():
    repo = InMemoryUserRepository()
    handler = DeactivateUserHandler(repo)
    r = await handler.handle(DeactivateUserCommand(user_id=uuid4()))
    assert r.is_failure
    assert r.status_code == 404
```

- [ ] **Step 2: Run — expect FAIL.**

- [ ] **Step 3: Implement both handlers**

`app/use_cases/accounts/commands/promote_user_role.py`:

```python
from __future__ import annotations
from dataclasses import dataclass
from uuid import UUID
from app.domain.accounts.repository import IUserRepository
from app.domain.accounts.role import Role
from app.domain.shared.result import Result
from app.use_cases.accounts.dtos import UserDto


@dataclass(frozen=True, slots=True)
class PromoteUserRoleCommand:
    user_id: UUID
    new_role: Role


class PromoteUserRoleHandler:
    """Admin-only entrypoint for changing a user's role.

    The admin-only restriction is enforced at the API layer via require_role(ADMIN).
    The handler itself accepts any new_role — including ADMIN — so admins can
    promote any user (e.g., to back-fill an admin account).
    """

    def __init__(self, users: IUserRepository) -> None:
        self._users = users

    async def handle(self, cmd: PromoteUserRoleCommand) -> Result[UserDto]:
        user = await self._users.get_by_id(cmd.user_id)
        if user is None:
            return Result.failure("Usuário não encontrado.", status_code=404)

        user.set_role(cmd.new_role)
        await self._users.update(user)
        return Result.success(UserDto.from_entity(user))
```

`app/use_cases/accounts/commands/deactivate_user.py`:

```python
from __future__ import annotations
from dataclasses import dataclass
from uuid import UUID
from app.domain.accounts.repository import IUserRepository
from app.domain.shared.result import Result
from app.use_cases.accounts.dtos import UserDto


@dataclass(frozen=True, slots=True)
class DeactivateUserCommand:
    user_id: UUID


class DeactivateUserHandler:
    def __init__(self, users: IUserRepository) -> None:
        self._users = users

    async def handle(self, cmd: DeactivateUserCommand) -> Result[UserDto]:
        user = await self._users.get_by_id(cmd.user_id)
        if user is None:
            return Result.failure("Usuário não encontrado.", status_code=404)

        user.deactivate()
        await self._users.update(user)
        return Result.success(UserDto.from_entity(user))
```

- [ ] **Step 4: Run all accounts tests**

`.venv/bin/pytest tests/unit/use_cases/accounts/ tests/unit/domain/accounts/ tests/integration/accounts/ tests/integration/auth/ -q` — expect green.

- [ ] **Step 5: Commit**

```bash
git add app/use_cases/accounts/commands/promote_user_role.py app/use_cases/accounts/commands/deactivate_user.py tests/unit/use_cases/accounts/commands/test_promote_user_role.py tests/unit/use_cases/accounts/commands/test_deactivate_user.py
git commit -m "$(cat <<'EOF'
feat(accounts): add PromoteUserRoleHandler and DeactivateUserHandler

Both are admin-only at the API layer (Plan 02 Unit D wires require_role).
The handlers themselves are uniform user-mutation handlers — they look
up the user, mutate, persist, return UserDto. PromoteUserRoleHandler
accepts ADMIN so the admin can backfill another admin account.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## UNIT D — API layer + DI

Four tasks.

### Task D1 — `app/api/deps.py`: `get_current_user` and `require_role`

**File:** `app/api/deps.py`.

- [ ] **Step 1: Replace the file content**

```python
"""Cross-cutting API dependencies.

DI específica de feature mora em `app/api/v1/<feature>/deps.py`.
Este módulo abriga as dependências compartilhadas entre features:
identidade do usuário corrente e guards baseados em Role.
"""
from __future__ import annotations
from typing import Annotated, Callable
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import get_settings
from app.domain.accounts.jwt_service import IJwtService, TokenClaims
from app.domain.accounts.role import Role
from app.infrastructure.auth.jose_jwt_service import JoseJwtService

_bearer = HTTPBearer(auto_error=True)


def get_jwt_service() -> IJwtService:
    s = get_settings()
    return JoseJwtService(
        secret_key=s.jwt_secret_key.get_secret_value(),
        algorithm=s.jwt_algorithm,
        access_token_expires_seconds=s.jwt_access_token_expires_minutes * 60,
        refresh_token_expires_seconds=s.jwt_refresh_token_expires_days * 24 * 3600,
    )


def get_current_user(
    creds: Annotated[HTTPAuthorizationCredentials, Depends(_bearer)],
    jwt_service: Annotated[IJwtService, Depends(get_jwt_service)],
) -> TokenClaims:
    decoded = jwt_service.decode(creds.credentials)
    if decoded.is_failure:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=decoded.error or "Unauthorized",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if decoded.value.type != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh tokens não podem ser usados como credenciais.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return decoded.value


CurrentUser = Annotated[TokenClaims, Depends(get_current_user)]


def require_role(*allowed: Role) -> Callable[[TokenClaims], TokenClaims]:
    """Returns a dependency that 403s if the current user's role isn't in `allowed`."""
    allowed_set = frozenset(allowed)

    def _dep(user: CurrentUser) -> TokenClaims:
        if user.role not in allowed_set:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permissão negada para este recurso.",
            )
        return user

    return _dep
```

- [ ] **Step 2: Smoke import**

```bash
.venv/bin/python -c "from app.api.deps import get_current_user, require_role, CurrentUser; print('ok')"
```

- [ ] **Step 3: Commit**

```bash
git add app/api/deps.py
git commit -m "$(cat <<'EOF'
feat(api): add get_current_user + require_role(*roles) deps

get_current_user verifies the bearer token via IJwtService, rejecting
non-access-type tokens with 401. require_role(...) returns a
sub-dependency that 403s when the role doesn't match. Both wire JWT
settings from Settings via get_jwt_service.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

### Task D2 — `app/api/v1/auth/` router (register, login, refresh, logout, /me)

**Files:** `app/api/v1/auth/__init__.py`, `app/api/v1/auth/schemas.py`, `app/api/v1/auth/deps.py`, `app/api/v1/auth/routes.py`.

- [ ] **Step 1: Implement schemas**

`app/api/v1/auth/schemas.py`:

```python
from __future__ import annotations
from typing import Literal
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field
from app.domain.accounts.role import Role
from app.use_cases.accounts.dtos import TokenPairDto, UserDto


SelfRegisterableRole = Literal["customer", "owner"]


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=200)
    role: SelfRegisterableRole
    full_name: str = Field(min_length=1, max_length=200)
    phone: str | None = Field(default=None, max_length=14)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class UserResponse(BaseModel):
    id: UUID
    email: str
    role: Role
    full_name: str
    phone: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_dto(cls, dto: UserDto) -> "UserResponse":
        return cls(
            id=dto.id,
            email=dto.email,
            role=dto.role,
            full_name=dto.full_name,
            phone=dto.phone,
            is_active=dto.is_active,
            created_at=dto.created_at,
            updated_at=dto.updated_at,
        )


class TokenPairResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int
    user: UserResponse

    @classmethod
    def from_dto(cls, dto: TokenPairDto) -> "TokenPairResponse":
        return cls(
            access_token=dto.access_token,
            refresh_token=dto.refresh_token,
            token_type=dto.token_type,
            expires_in=dto.expires_in,
            user=UserResponse.from_dto(dto.user),
        )
```

- [ ] **Step 2: Implement deps**

`app/api/v1/auth/deps.py`:

```python
from __future__ import annotations
from typing import Annotated
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_jwt_service
from app.core.config import get_settings
from app.domain.accounts.password_hasher import IPasswordHasher
from app.domain.accounts.repository import IUserRepository
from app.domain.accounts.jwt_service import IJwtService
from app.infrastructure.auth.argon2_password_hasher import Argon2PasswordHasher
from app.infrastructure.db.session import get_session
from app.infrastructure.repositories.user_repository import UserRepository
from app.use_cases.accounts.commands.login import LoginHandler
from app.use_cases.accounts.commands.refresh_token import RefreshTokenHandler
from app.use_cases.accounts.commands.register_user import RegisterUserHandler
from app.use_cases.accounts.queries.get_user_by_id import GetUserByIdHandler


def get_user_repository(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> IUserRepository:
    return UserRepository(session)


def get_password_hasher() -> IPasswordHasher:
    s = get_settings()
    return Argon2PasswordHasher(
        time_cost=s.argon2_time_cost,
        memory_cost_kib=s.argon2_memory_cost_kib,
        parallelism=s.argon2_parallelism,
    )


UserRepo = Annotated[IUserRepository, Depends(get_user_repository)]
Hasher = Annotated[IPasswordHasher, Depends(get_password_hasher)]
Jwt = Annotated[IJwtService, Depends(get_jwt_service)]


def get_register_user_handler(repo: UserRepo, hasher: Hasher) -> RegisterUserHandler:
    return RegisterUserHandler(repo, hasher)


def get_login_handler(repo: UserRepo, hasher: Hasher, jwt: Jwt) -> LoginHandler:
    return LoginHandler(repo, hasher, jwt)


def get_refresh_token_handler(repo: UserRepo, jwt: Jwt) -> RefreshTokenHandler:
    return RefreshTokenHandler(repo, jwt)


def get_get_user_by_id_handler(repo: UserRepo) -> GetUserByIdHandler:
    return GetUserByIdHandler(repo)
```

- [ ] **Step 3: Implement routes**

`app/api/v1/auth/routes.py`:

```python
from __future__ import annotations
from typing import Annotated
from fastapi import APIRouter, Depends

from app.api.deps import CurrentUser
from app.api.error_handler import unwrap
from app.api.v1.auth.deps import (
    get_get_user_by_id_handler, get_login_handler,
    get_refresh_token_handler, get_register_user_handler,
)
from app.api.v1.auth.schemas import (
    LoginRequest, RefreshRequest, RegisterRequest,
    TokenPairResponse, UserResponse,
)
from app.domain.accounts.role import Role
from app.use_cases.accounts.commands.login import LoginCommand, LoginHandler
from app.use_cases.accounts.commands.refresh_token import (
    RefreshTokenCommand, RefreshTokenHandler,
)
from app.use_cases.accounts.commands.register_user import (
    RegisterUserCommand, RegisterUserHandler,
)
from app.use_cases.accounts.queries.get_user_by_id import (
    GetUserByIdHandler, GetUserByIdQuery,
)


router = APIRouter(prefix="/v1", tags=["auth"])


@router.post("/auth/register", response_model=UserResponse, status_code=201)
async def register(
    req: RegisterRequest,
    handler: Annotated[RegisterUserHandler, Depends(get_register_user_handler)],
) -> UserResponse:
    dto = unwrap(await handler.handle(RegisterUserCommand(
        email=req.email, password=req.password,
        role=Role(req.role),
        full_name=req.full_name, phone=req.phone,
    )))
    return UserResponse.from_dto(dto)


@router.post("/auth/login", response_model=TokenPairResponse)
async def login(
    req: LoginRequest,
    handler: Annotated[LoginHandler, Depends(get_login_handler)],
) -> TokenPairResponse:
    dto = unwrap(await handler.handle(LoginCommand(
        email=req.email, password=req.password,
    )))
    return TokenPairResponse.from_dto(dto)


@router.post("/auth/refresh", response_model=TokenPairResponse)
async def refresh(
    req: RefreshRequest,
    handler: Annotated[RefreshTokenHandler, Depends(get_refresh_token_handler)],
) -> TokenPairResponse:
    dto = unwrap(await handler.handle(RefreshTokenCommand(refresh_token=req.refresh_token)))
    return TokenPairResponse.from_dto(dto)


@router.post("/auth/logout", status_code=204)
async def logout(_user: CurrentUser) -> None:
    """Stateless JWT — there's nothing to revoke server-side. Client drops the token.

    Returning 204 keeps the contract for the eventual blocklist-backed
    implementation (see Opportunities.md). The dep ensures the caller has a
    valid access token, so 401 leaks aren't possible from a missing-token call.
    """
    return None


@router.get("/me", response_model=UserResponse)
async def me(
    user: CurrentUser,
    handler: Annotated[GetUserByIdHandler, Depends(get_get_user_by_id_handler)],
) -> UserResponse:
    dto = unwrap(await handler.handle(GetUserByIdQuery(user_id=user.user_id)))
    return UserResponse.from_dto(dto)
```

- [ ] **Step 4: `app/api/v1/auth/__init__.py`**

```python
from app.api.v1.auth.routes import router

__all__ = ["router"]
```

- [ ] **Step 5: Smoke import**

```bash
.venv/bin/python -c "from app.api.v1.auth import router; print('routes:', [r.path for r in router.routes])"
```

Expect to see `/v1/auth/register`, `/v1/auth/login`, `/v1/auth/refresh`, `/v1/auth/logout`, `/v1/me`.

- [ ] **Step 6: Commit**

```bash
git add app/api/v1/auth/
git commit -m "$(cat <<'EOF'
feat(api): add /v1/auth/{register,login,refresh,logout} + /v1/me

All five endpoints wired to accounts use cases via deps.py. logout is
a 204 no-op for now (client just drops the token); blocklist-backed
revocation is in Opportunities.md.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

### Task D3 — `app/api/v1/admin_users/` router (admin-only management)

**Files:** `app/api/v1/admin_users/__init__.py`, `app/api/v1/admin_users/schemas.py`, `app/api/v1/admin_users/deps.py`, `app/api/v1/admin_users/routes.py`.

- [ ] **Step 1: Schemas**

`app/api/v1/admin_users/schemas.py`:

```python
from __future__ import annotations
from typing import Literal
from pydantic import BaseModel
from app.api.v1.auth.schemas import UserResponse  # reuse


AnyRole = Literal["admin", "owner", "customer"]


class ChangeRoleRequest(BaseModel):
    new_role: AnyRole


class ListUsersResponse(BaseModel):
    items: list[UserResponse]
```

- [ ] **Step 2: Deps**

`app/api/v1/admin_users/deps.py`:

```python
from __future__ import annotations
from app.api.v1.auth.deps import UserRepo
from app.use_cases.accounts.commands.deactivate_user import DeactivateUserHandler
from app.use_cases.accounts.commands.promote_user_role import PromoteUserRoleHandler


def get_promote_user_role_handler(repo: UserRepo) -> PromoteUserRoleHandler:
    return PromoteUserRoleHandler(repo)


def get_deactivate_user_handler(repo: UserRepo) -> DeactivateUserHandler:
    return DeactivateUserHandler(repo)
```

- [ ] **Step 3: Routes**

`app/api/v1/admin_users/routes.py`:

```python
from __future__ import annotations
from typing import Annotated
from uuid import UUID
from fastapi import APIRouter, Depends, Query

from app.api.deps import require_role
from app.api.error_handler import unwrap
from app.api.v1.admin_users.deps import (
    get_deactivate_user_handler, get_promote_user_role_handler,
)
from app.api.v1.admin_users.schemas import ChangeRoleRequest, ListUsersResponse
from app.api.v1.auth.deps import UserRepo
from app.api.v1.auth.schemas import UserResponse
from app.domain.accounts.role import Role
from app.use_cases.accounts.commands.deactivate_user import (
    DeactivateUserCommand, DeactivateUserHandler,
)
from app.use_cases.accounts.commands.promote_user_role import (
    PromoteUserRoleCommand, PromoteUserRoleHandler,
)
from app.use_cases.accounts.dtos import UserDto


router = APIRouter(
    prefix="/v1/admin/users",
    tags=["admin", "users"],
    dependencies=[Depends(require_role(Role.ADMIN))],
)


@router.get("", response_model=ListUsersResponse)
async def list_users(
    repo: UserRepo,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> ListUsersResponse:
    users = await repo.list_active(limit=limit, offset=offset)
    items = [UserResponse.from_dto(UserDto.from_entity(u)) for u in users]
    return ListUsersResponse(items=items)


@router.post("/{user_id}/role", response_model=UserResponse)
async def change_role(
    user_id: UUID,
    req: ChangeRoleRequest,
    handler: Annotated[PromoteUserRoleHandler, Depends(get_promote_user_role_handler)],
) -> UserResponse:
    dto = unwrap(await handler.handle(PromoteUserRoleCommand(
        user_id=user_id, new_role=Role(req.new_role),
    )))
    return UserResponse.from_dto(dto)


@router.post("/{user_id}/deactivate", response_model=UserResponse)
async def deactivate(
    user_id: UUID,
    handler: Annotated[DeactivateUserHandler, Depends(get_deactivate_user_handler)],
) -> UserResponse:
    dto = unwrap(await handler.handle(DeactivateUserCommand(user_id=user_id)))
    return UserResponse.from_dto(dto)
```

- [ ] **Step 4: `__init__.py`**

```python
from app.api.v1.admin_users.routes import router

__all__ = ["router"]
```

- [ ] **Step 5: Smoke import**

```bash
.venv/bin/python -c "from app.api.v1.admin_users import router; print('routes:', [r.path for r in router.routes])"
```

- [ ] **Step 6: Commit**

```bash
git add app/api/v1/admin_users/
git commit -m "$(cat <<'EOF'
feat(api): add /v1/admin/users — admin-only user management

Three endpoints (list, change role, deactivate), all guarded by
require_role(ADMIN) at the router level. Reuses UserResponse and
UserRepo from the auth feature so we don't duplicate the schemas.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

### Task D4 — Wire both routers into `app/api/v1/router.py`; remove the old `users` router

**File:** `app/api/v1/router.py`.

- [ ] **Step 1: Edit**

Replace the file content:

```python
"""API router agregador: include cada feature router aqui.

Uso em main.py:
    from app.api.v1.router import api_router
    app.include_router(api_router)
"""
from fastapi import APIRouter

from app.api.v1.admin_users import router as admin_users_router
from app.api.v1.auth import router as auth_router
from app.api.v1.reports import router as reports_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(admin_users_router)
api_router.include_router(reports_router)
```

- [ ] **Step 2: Smoke import the full app**

```bash
BACKEND_DATABASE_URL="sqlite+aiosqlite:///:memory:" \
  .venv/bin/python -c "from app.main import app; print(sorted(set(r.path for r in app.routes)))"
```

Expect to see `/v1/auth/register`, `/v1/auth/login`, `/v1/auth/refresh`, `/v1/auth/logout`, `/v1/me`, `/v1/admin/users`, `/v1/admin/users/{user_id}/role`, `/v1/admin/users/{user_id}/deactivate`, plus the existing `/v1/reports/...` routes — and NO `/v1/users` (that's still wired but the old `users_router` is about to be deleted in Unit E).

Wait — at this point the OLD `app/api/v1/users/` is still present but no longer included in the api_router (we just removed its import). The old user feature's tests (`tests/e2e/users/`) will start failing because their endpoints don't exist.

- [ ] **Step 3: Run tests, accepting some failures**

`.venv/bin/pytest -q tests/unit/use_cases/accounts/ tests/unit/domain/accounts/ tests/integration/accounts/ tests/integration/auth/ tests/unit/core/ -q` — expect green.

The OLD users tests fail; that's fine — Unit E deletes them.

- [ ] **Step 4: Commit**

```bash
git add app/api/v1/router.py
git commit -m "$(cat <<'EOF'
feat(api): swap users sample router for auth + admin_users routers

Removes the include for the old users sample; adds includes for the
auth and admin_users routers. Old /v1/users/* endpoints are gone.
The old users sample files are deleted in Unit E (final).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## UNIT E — Cleanup + final verification

### Task E1 — Delete the old `users` sample (Recipe C)

**Paths to delete (per `docs/template-customization.md` Recipe C, adapted):**

```bash
rm -rf app/domain/user
rm -rf app/use_cases/users
rm -rf app/api/v1/users
rm -rf tests/unit/domain/user
rm -rf tests/unit/use_cases/users
rm -rf tests/integration/users
rm -rf tests/e2e/users
```

(Notice: we do NOT delete `app/infrastructure/db/mappings/user.py` or `app/infrastructure/repositories/user_repository.py` — those were rewritten in place to back the new `accounts` feature.)

- [ ] **Step 1: Delete**

Run the seven `rm -rf` commands above.

- [ ] **Step 2: Verify nothing imports from the deleted paths**

```bash
grep -rnE "app\.domain\.user|app\.use_cases\.users|app\.api\.v1\.users|tests\.unit\.use_cases\.users|tests\.unit\.domain\.user" app/ tests/ 2>/dev/null
```

Expect: zero matches.

- [ ] **Step 3: Run the FULL test suite**

```bash
.venv/bin/pytest -q
```

Expect: ALL tests green. The expected count: 106 (Plan 01 baseline) MINUS the deleted users sample tests (~20 of them) PLUS the new accounts tests (~30+) = roughly 115-120 tests, all passing.

If anything fails, STOP and diagnose. Likely culprits:
- Lingering import in `app/migrations/env.py` — already imports `app.infrastructure.db.mappings.user` which still exists (UserModel is rewritten there), so should be fine.
- Lingering import in `tests/e2e/conftest.py` — same: it imports `app.infrastructure.db.mappings.user`, which still exists.

- [ ] **Step 4: Run linter**

```bash
.venv/bin/python -m ruff check app tests
```

Expect: clean.

- [ ] **Step 5: Smoke import**

```bash
BACKEND_DATABASE_URL="sqlite+aiosqlite:///:memory:" \
  .venv/bin/python -c "from app.main import app; print('ok'); print('title:', app.title)"
```

Expect: `ok`, `title: venue-backend`.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "$(cat <<'EOF'
chore: remove users sample (Recipe C)

Deletes the old users sample now that accounts is fully in place:
  - app/domain/user/
  - app/use_cases/users/
  - app/api/v1/users/
  - tests/{unit,integration,e2e}/users/
  - tests/unit/domain/user/

The infrastructure layer (mapping + repository) was rewritten in
place, so users table + UserRepository/UserModel still exist — they
just back accounts.User now.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

### Task E2 — End-to-end auth flow test

**File:** `tests/e2e/accounts/__init__.py` (empty), `tests/e2e/accounts/test_auth_flow.py`.

- [ ] **Step 1: Implement the e2e test**

```python
from __future__ import annotations
import pytest


@pytest.mark.asyncio
async def test_full_register_login_me_refresh_flow(client):
    # Register a customer
    r = await client.post("/v1/auth/register", json={
        "email": "alice@example.com",
        "password": "hunter2-strong",
        "role": "customer",
        "full_name": "Alice",
        "phone": "+5511999999999",
    })
    assert r.status_code == 201, r.text
    user = r.json()
    assert user["email"] == "alice@example.com"
    assert user["role"] == "customer"

    # Login
    r = await client.post("/v1/auth/login", json={
        "email": "alice@example.com",
        "password": "hunter2-strong",
    })
    assert r.status_code == 200, r.text
    tokens = r.json()
    access = tokens["access_token"]
    refresh = tokens["refresh_token"]
    assert tokens["user"]["email"] == "alice@example.com"

    # /me with the access token
    r = await client.get("/v1/me", headers={"Authorization": f"Bearer {access}"})
    assert r.status_code == 200, r.text
    me = r.json()
    assert me["email"] == "alice@example.com"

    # /me without a token → 403 (FastAPI HTTPBearer returns 403 by default for missing creds)
    r = await client.get("/v1/me")
    assert r.status_code == 403

    # /me with garbage token → 401
    r = await client.get("/v1/me", headers={"Authorization": "Bearer not-a-jwt"})
    assert r.status_code == 401

    # Refresh
    r = await client.post("/v1/auth/refresh", json={"refresh_token": refresh})
    assert r.status_code == 200, r.text
    new_tokens = r.json()
    assert new_tokens["access_token"] != access  # new pair issued

    # Logout (no-op, just verifies the dep works)
    r = await client.post("/v1/auth/logout", headers={
        "Authorization": f"Bearer {new_tokens['access_token']}",
    })
    assert r.status_code == 204


@pytest.mark.asyncio
async def test_register_admin_role_rejected(client):
    r = await client.post("/v1/auth/register", json={
        "email": "admin@example.com", "password": "hunter2-strong",
        "role": "admin",  # not in the SelfRegisterableRole literal
        "full_name": "Adm", "phone": None,
    })
    # Pydantic validation rejects the literal — 422, not 403
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_login_unknown_email_returns_401(client):
    r = await client.post("/v1/auth/login", json={
        "email": "nobody@example.com", "password": "anything",
    })
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_admin_endpoint_blocks_non_admin(client):
    # Register and log in as a customer
    await client.post("/v1/auth/register", json={
        "email": "cust@example.com", "password": "hunter2-strong",
        "role": "customer", "full_name": "Cust", "phone": None,
    })
    r = await client.post("/v1/auth/login", json={
        "email": "cust@example.com", "password": "hunter2-strong",
    })
    access = r.json()["access_token"]

    # Try to call an admin endpoint
    r = await client.get(
        "/v1/admin/users",
        headers={"Authorization": f"Bearer {access}"},
    )
    assert r.status_code == 403
```

- [ ] **Step 2: Run**

`.venv/bin/pytest tests/e2e/accounts/ -q` — expect green (4 tests).

- [ ] **Step 3: Final full test run + lint**

```bash
.venv/bin/pytest -q
.venv/bin/python -m ruff check app tests
```

Both green.

- [ ] **Step 4: Commit**

```bash
git add tests/e2e/accounts/
git commit -m "$(cat <<'EOF'
test(accounts): e2e auth flow + admin guard

Covers register → login → /me → refresh → logout end-to-end via the
FastAPI test client. Verifies 401 on garbage token, 403 on
missing-credential, 422 on register-as-admin (Pydantic literal),
and 403 when a customer hits /v1/admin/users.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Self-Review Checklist (controller runs this BEFORE final code review)

After all five units land, before the final whole-implementation review:

1. `grep -rn "app\.domain\.user\b\|app\.use_cases\.users\b\|app\.api\.v1\.users\b" app/ tests/` returns zero — old sample fully gone.
2. `.venv/bin/pytest -q` reports green; count is in the 110-130 range.
3. `.venv/bin/python -m ruff check app tests` is clean.
4. Smoke import: `BACKEND_DATABASE_URL=sqlite+aiosqlite:///:memory: .venv/bin/python -c "from app.main import app; print(sorted({r.path for r in app.routes}))"` lists all auth + admin/users routes.
5. The Alembic migration applies cleanly to a fresh Postgres (manual local check; not gated since CI doesn't have Postgres).
6. No handler-calls-handler. No `domain/<feature_a>/` importing from `domain/<feature_b>/`. (`accounts` doesn't import from anywhere domain-level except `domain/shared/`.)
7. `app/api/deps.py` is the only place that constructs `JoseJwtService` for auth — the auth router and admin_users router both inject the port via `get_jwt_service()`.

---

## Execution Notes for the Implementer

- **TDD:** every code-producing task above writes a failing test first, runs it to confirm failure, implements, runs again to confirm pass, then commits. Do NOT skip the failing-test run.
- **Commit per task:** each numbered task in this plan corresponds to ONE commit. Don't squash.
- **Order:** Units A → B → C → D → E. Within a unit, tasks are sequential. Inside Unit B, B5 (mapping) MUST come before B6 (repo) and B7 (migration).
- **If the autogenerated migration in B7 looks wrong:** STOP and report. The plan's reference shape covers the most likely case; deviating is fine if you understand the autogenerator's diff.
- **If tests fail unexpectedly:** STOP and report; don't improvise. The most likely cause is a missing import or a wrong path to `tests/unit/use_cases/accounts/fakes/` — those are real test modules and need `__init__.py` files (the plan creates them in C1).

---

## Execution Handoff

Plan complete. Ready for subagent-driven-development.
