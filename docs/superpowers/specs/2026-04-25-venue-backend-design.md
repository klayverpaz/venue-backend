# Venue Backend — Design Spec

**Date:** 2026-04-25
**Status:** Approved
**Source template:** `agentic-workbench/ai-ready-backend-template/`
**Repository:** `git@github.com:klayverpaz/venue-backend.git`

## 1. Project context

A backend for a rental-by-hourly-slots marketplace. The motivating use case is football-field rentals (owner publishes a field, customers request booking blocks for games), but the domain is built generic so the same code serves padel courts, studios, meeting rooms, etc. Football-field-specific data lives in the seeded `ResourceType` catalog, not in the package or schema.

Built on top of `ai-ready-backend-template` (FastAPI + SQLAlchemy + Postgres + CQRS + vertical slicing per feature). The AI module from the template is removed up front. The `users` sample is replaced with a real `accounts` feature in the same step.

Project name and folder: `venue-backend`. Located at `agentic-workbench/venue-backend/`.

## 2. Roles and personas

| Role | Capabilities |
|---|---|
| **Admin** | Curates `ResourceType` catalog (admin-managed). Manages users (promote/demote roles, deactivate). Manages owner subscription status. |
| **Owner** | Registers and manages their `Resource`s. Defines operating hours, slot duration, pricing rules, custom attributes per resource. Reviews and approves/rejects/cancels bookings on their resources. Read-only view of their subscription status. |
| **Customer** | Browses public resource listings, requests bookings (one or more consecutive slots) with a free-form note, sees their own bookings, cancels until configurable cutoff. |

A user has exactly one role. Roles are immutable except by an explicit admin handler.

## 3. Decisions and rationale (decision log)

| # | Decision | Rationale |
|---|---|---|
| 1 | Three roles: Admin, Owner, Customer. One role per user. | Clean RBAC; matches user's stated split. |
| 2 | Generic "rentable resource" domain, not field-specific. | User wants to repurpose the platform across domains. Genericity lives in `ResourceType`. |
| 3 | Hybrid catalog: admin-curated `ResourceType` with base attribute schema; owners may add custom attributes per resource. | Governance + flexibility. Customers can filter on base attributes; owners can express specifics without schema requests. |
| 4 | One owner → many resources, possibly across types. | Real-world: a sports complex has multiple fields; a studio has multiple rooms. |
| 5 | Fixed slots, owner-defined slot duration + weekly operating hours; bookings span N consecutive slots. | Simpler agenda rendering, trivial conflict detection, matches how this market actually prices ("by the hour"). |
| 6 | Approval flow: multiple customers can request the same slot ("pending"); first owner-approval wins; competing requests auto-rejected in the same transaction. | Realistic: owner picks; clear UX for everyone. |
| 7 | Customer can attach a free-form note on each booking request (e.g., "10 people, birthday game"). | User-requested. |
| 8 | Booking payments are off-platform. `Booking.total_price_cents` is recorded but the system never collects money. | Smallest viable scope; avoids PSP integration. |
| 9 | Platform monetization is a soft owner subscription (status field only, admin-controlled). When `INACTIVE`, owner cannot approve bookings and resources are hidden from public listings. | Exercises the gating logic in the model now; defers PSP work. |
| 10 | Pricing model: day-of-week × time-of-day rules per resource; gaps fall back to a `base_price_cents` on the resource. | Owners with peak/off-peak prices are the norm; fallback prevents validation deadlocks for new owners. |
| 11 | Discovery: each owner and each resource gets a public URL (slug-based). Plus a platform-wide listing filterable by resource type and city/region. No map, no geosearch, no ratings. | Fits the realistic acquisition model (owners drive traffic via social) without skipping browse-ability. |
| 12 | Cancellations: owner can cancel anytime; customer can cancel until `customer_cancellation_cutoff_hours` before slot start. Audit trail on the booking. | Encodes the natural asymmetry; no monetary penalties (money is off-platform). |
| 13 | Notifications: in-app inbox for every event + transactional email via a port (`IEmailSender`). Logging adapter for MVP; real provider later. | In-app alone gets missed; email is essentially free; port keeps WhatsApp/SMS a swap-in. |
| 14 | Idempotency keys accepted on `POST /me/bookings` and approval/reject endpoints. | Cheap to add; avoids the inevitable double-click / network-retry duplicate booking. |
| 15 | Localization: identifiers and code in English; user-facing strings in pt-BR via a translation map. | Matches likely user base; keeps code grep-able. |

## 4. Architecture

The template's rules apply unchanged. Layered + vertical slicing per feature. Six features, each owning one aggregate root.

```
api ──▶ use_cases ──▶ domain ◀── infrastructure
```

`domain/` stays pure Python; `use_cases/` depends only on `domain/<feature>/repository.py` `Protocol`s; `infrastructure/` provides concrete repositories and adapters; `api/v1/<feature>/routes.py` does HTTP-only validation.

### 4.1 Feature split (six aggregates)

| Feature | Aggregate root | Sub-entities / VOs |
|---|---|---|
| `accounts` | `User` | `Email`, `Role` |
| `catalog` | `ResourceType` | `AttributeDefinition` |
| `resources` | `Resource` | `WeeklySchedule`, `PricingRule`, `CustomAttribute` |
| `bookings` | `Booking` | `SlotRange`, `StatusChange` |
| `subscriptions` | `OwnerSubscription` | `SubStatus` |
| `notifications` | `Notification` | `IEmailSender` port |

### 4.2 Cross-feature rules

Per the template's CLAUDE.md §"Regra cross-entity": cross-aggregate rules live in handlers that **inject multiple repositories via DI**, in the feature that owns the operation. No handler-calls-handler. No `domain/<feature_a>/` importing from `domain/<feature_b>/`.

Cross-feature handlers expected:

| Handler | Feature | Repos injected | Responsibility |
|---|---|---|---|
| `RequestBookingHandler` | `bookings/commands` | `IBookingRepository`, `IResourceRepository`, `ISubscriptionRepository`, `INotificationService` | Validate, price, persist `Booking{PENDING}`, notify owner. |
| `ApproveBookingHandler` | `bookings/commands` | `IBookingRepository`, `IResourceRepository`, `INotificationService` | Approve target + auto-reject overlapping pendings in one transaction; notify all parties. |
| `CancelBookingHandler` | `bookings/commands` | `IBookingRepository`, `IResourceRepository`, `INotificationService` | Branch by actor role; enforce customer cutoff; notify counterpart. |
| `PromoteUserRoleHandler` | `accounts/commands` | `IUserRepository` | Admin-only; the only role-mutation entrypoint. |
| `SetOwnerSubscriptionStatusHandler` | `subscriptions/commands` | `ISubscriptionRepository`, `IUserRepository` | Admin-only; verifies target user is `OWNER`. |

## 5. Domain model

### 5.1 `accounts` — `User`

```
User
├── id: UUID
├── email: Email (VO, unique)
├── password_hash: str
├── role: Role (enum: ADMIN | OWNER | CUSTOMER)
├── full_name: str
├── phone: str (optional)
├── is_active: bool
└── created_at, updated_at
```

**Invariants**
- Email globally unique.
- Role is set at creation and only mutable through `PromoteUserRoleHandler` (admin-only).
- Customers self-register as `CUSTOMER`; owners self-register as `OWNER`. Admin accounts are not self-serve.

### 5.2 `catalog` — `ResourceType`

```
ResourceType
├── id: UUID
├── slug: str (unique, e.g. "football-field")
├── name: str
├── description: str
├── attribute_schema: list[AttributeDefinition]
└── is_active: bool

AttributeDefinition (VO)
├── key: str
├── label: str
├── data_type: AttrType (STRING | INT | BOOL | ENUM)
├── required: bool
└── enum_values: list[str] | None  (only when data_type == ENUM)
```

**Invariants**
- `slug` unique.
- Within a `ResourceType`, `AttributeDefinition.key` values are unique.
- Deactivating a `ResourceType` (`is_active = False`) does NOT cascade to existing resources of that type. New resources cannot reference an inactive type.
- Deletion is allowed only if no `Resource` references the type.

### 5.3 `resources` — `Resource`

```
Resource
├── id: UUID
├── owner_id: UUID                          # User with role=OWNER
├── resource_type_id: UUID                  # ResourceType
├── slug: str (unique, public URL)
├── name: str
├── description: str
├── city: str
├── region: str
├── timezone: str                           # IANA tz, e.g. "America/Sao_Paulo"
├── slot_duration_minutes: int              # ∈ {30, 45, 60, 90, 120}
├── operating_hours: WeeklySchedule
├── pricing_rules: list[PricingRule]        # may have gaps
├── base_price_cents: int                   # fallback price when no rule covers a slot
├── base_attributes: dict[str, Any]         # values for ResourceType.attribute_schema
├── custom_attributes: list[CustomAttribute]
├── customer_cancellation_cutoff_hours: int # default 24
├── is_published: bool
└── created_at, updated_at, deleted_at (soft-delete)

WeeklySchedule (VO)
└── 7 entries: { weekday: Weekday, opens_at: time, closes_at: time, closed: bool }

PricingRule (VO)
├── weekdays: set[Weekday]
├── starts_at: time
├── ends_at: time
└── price_cents: int

CustomAttribute (VO)
├── key: str
├── label: str
└── value: str
```

**Invariants**
- `owner_id`'s role must be `OWNER` (verified at handler level).
- `slot_duration_minutes` is in the allowed enum.
- Each non-closed weekday's `(opens_at, closes_at)` window is divisible by `slot_duration_minutes` (slot grid alignment).
- `pricing_rules` may not overlap each other within the same weekday × time window. Gaps are allowed and fall back to `base_price_cents`.
- `base_attributes` satisfies `resource_type.attribute_schema`: every required key present, every value matches `data_type`, every `ENUM` value is in `enum_values`.
- `custom_attribute.key` values unique within a resource and disjoint from `base_attributes` keys.
- Soft-delete (`deleted_at != NULL`) blocked when there is any `APPROVED` booking with `slot_range.start_at >= now`.

### 5.4 `bookings` — `Booking`

```
Booking
├── id: UUID
├── resource_id: UUID
├── customer_id: UUID                       # User with role=CUSTOMER
├── slot_range: SlotRange
├── status: BookingStatus                   # PENDING | APPROVED | REJECTED | CANCELLED | EXPIRED
├── customer_note: str (optional, max 1000 chars)
├── total_price_cents: int                  # frozen at request time
├── status_history: list[StatusChange]
├── cancelled_by: ActorRef | None           # OWNER | CUSTOMER, with user_id
└── created_at, updated_at

SlotRange (VO)
├── start_at: datetime (tz-aware)
├── end_at: datetime (tz-aware)
└── slot_count: int  (derived: (end_at − start_at) / resource.slot_duration_minutes)

StatusChange (VO)
├── from_status: BookingStatus
├── to_status: BookingStatus
├── actor_id: UUID
├── actor_role: Role
├── at: datetime
└── reason: str | None
```

**Invariants**
- `slot_range.start_at` and `end_at` align to the resource's slot grid for that date.
- `slot_range` lies entirely within `operating_hours` for every weekday it spans.
- `slot_count >= 1`.
- State transitions: `PENDING → {APPROVED, REJECTED, CANCELLED, EXPIRED}`; `APPROVED → CANCELLED`; all other states terminal.
- For a given `resource_id`, **at most one** `APPROVED` booking may overlap any moment (enforced by exclusion constraint + advisory lock; see §6).
- Customer cancellation requires `now < slot_range.start_at − resource.customer_cancellation_cutoff_hours`. Owner cancellation has no time bound.
- `total_price_cents` is computed once at request creation; later changes to the resource's pricing do not retroactively alter it.

### 5.5 `subscriptions` — `OwnerSubscription`

```
OwnerSubscription
├── id: UUID
├── owner_id: UUID (unique)
├── status: SubStatus (ACTIVE | TRIALING | PAST_DUE | INACTIVE)
├── status_changed_at: datetime
├── notes: str (admin-freeform)
└── created_at, updated_at
```

**Invariants**
- One row per owner.
- Only `SetOwnerSubscriptionStatusHandler` (admin-only) mutates `status`.
- `is_operational()` returns true when `status ∈ {ACTIVE, TRIALING}`. `RequestBookingHandler` rejects when not operational. Public listings exclude resources whose owner is not operational.

### 5.6 `notifications` — `Notification`

```
Notification
├── id: UUID
├── recipient_id: UUID
├── kind: NotifKind                          # see below
├── payload: dict                            # serialized event context
├── read_at: datetime | None
└── created_at

NotifKind
├── BOOKING_REQUESTED
├── BOOKING_APPROVED
├── BOOKING_REJECTED
├── BOOKING_CANCELLED
└── SUBSCRIPTION_CHANGED

IEmailSender (Protocol, in domain/notifications/)
└── send(to: Email, kind: NotifKind, payload: dict) -> Result[None]
```

**Invariants**
- Every notification persists an in-app row regardless of email delivery outcome.
- Email send failures are logged but do not fail the originating use case.

## 6. Booking lifecycle and concurrency

### 6.1 State machine

```
                        PENDING
              ┌────────────┼─────────────┬───────────┐
              ▼            ▼             ▼           ▼
          APPROVED     REJECTED     CANCELLED    EXPIRED
              │
              ▼
          CANCELLED
```

- `PENDING → APPROVED` — `ApproveBookingHandler` (owner action).
- `PENDING → REJECTED` — owner manual reject OR auto-reject when a competing pending is approved.
- `PENDING → CANCELLED` — customer (within cutoff) or owner.
- `PENDING → EXPIRED` — nightly job for pendings whose `slot_range.start_at < now`.
- `APPROVED → CANCELLED` — owner anytime; customer if cutoff respected.

### 6.2 Approval transaction (auto-rejection of competitors)

`ApproveBookingHandler` runs in a single DB transaction:

1. Acquire Postgres advisory lock keyed on `resource_id`.
2. Load target booking; verify `PENDING` and caller is the resource's owner.
3. Load all OTHER `PENDING` bookings on the same resource whose `slot_range` overlaps the target.
4. Update target → `APPROVED` (append `StatusChange`).
5. Update each overlapping competitor → `REJECTED` (append `StatusChange{reason: "auto_rejected_competing_request"}`).
6. Persist all in the same transaction.
7. Commit, release lock.
8. Outside the transaction: enqueue notifications.

### 6.3 Concurrency primitives

- **Postgres advisory lock** keyed on `resource_id` for `RequestBookingHandler` and `ApproveBookingHandler`. Prevents racing approvals or simultaneous request-and-approve from interleaving.
- **Postgres exclusion constraint** (requires the `btree_gist` extension) on the bookings table, restricted to `WHERE status = 'APPROVED'`:
  ```sql
  EXCLUDE USING gist (
      resource_id WITH =,
      tstzrange(slot_start_at, slot_end_at, '[)') WITH &&
  ) WHERE (status = 'APPROVED')
  ```
  Belt-and-suspenders: if a lock is ever bypassed, this constraint rejects any insert/update that would overlap an existing approved booking — including multi-slot overlaps that a simple unique index would miss.

### 6.4 Nightly job

`ExpirePendingBookings` cron — selects `PENDING` bookings with `slot_range.start_at < now`, transitions them to `EXPIRED`, sends `BOOKING_REJECTED` notifications. Idempotent; safe to retry.

## 7. API surface

All endpoints under `/api/v1/`. JWT auth via the same mechanism as the template's `users` sample. Pagination on every list endpoint: `?page=&page_size=` (max 100). Errors mapped from `Result` per `error_handler.py`.

### 7.1 Public (no auth)

```
GET  /resources                              # filters: type=<slug>&city=&region=&page=&page_size=
GET  /resources/{slug}                       # public resource page
GET  /resources/{slug}/agenda?from=&to=      # slot grid: AVAILABLE | PENDING | APPROVED + price
GET  /owners/{slug}                          # public owner page (their published resources)
GET  /catalog/resource-types                 # for filter UI
```

### 7.2 Auth

```
POST /auth/register                          # role ∈ {CUSTOMER, OWNER}
POST /auth/login
POST /auth/refresh
POST /auth/logout
GET  /me
```

### 7.3 Customer (role = CUSTOMER)

```
POST   /me/bookings                          # body: { resource_id, slot_range, customer_note }; Idempotency-Key supported
GET    /me/bookings?status=
GET    /me/bookings/{id}
POST   /me/bookings/{id}/cancel              # 403 past cutoff
GET    /me/notifications
POST   /me/notifications/{id}/read
```

### 7.4 Owner (role = OWNER)

```
# Resources
POST   /me/resources
GET    /me/resources
PATCH  /me/resources/{id}
PATCH  /me/resources/{id}/operating-hours
PATCH  /me/resources/{id}/pricing-rules
PATCH  /me/resources/{id}/publish            # toggle is_published
DELETE /me/resources/{id}                    # soft-delete; blocked if future approved bookings

# Bookings on my resources
GET    /me/resources/{id}/bookings?status=
GET    /me/resources/{id}/agenda?from=&to=
POST   /me/bookings/{booking_id}/approve     # Idempotency-Key supported
POST   /me/bookings/{booking_id}/reject      # body: { reason? }
POST   /me/bookings/{booking_id}/cancel

# Read-only
GET    /me/subscription
GET    /me/notifications
POST   /me/notifications/{id}/read
```

### 7.5 Admin (role = ADMIN)

```
# Catalog
POST   /admin/resource-types
GET    /admin/resource-types
PATCH  /admin/resource-types/{id}
DELETE /admin/resource-types/{id}            # blocked if referenced

# Users
GET    /admin/users
POST   /admin/users/{id}/role                # the only role-mutation handler
POST   /admin/users/{id}/deactivate

# Subscriptions
GET    /admin/subscriptions
POST   /admin/owners/{owner_id}/subscription
```

## 8. Bootstrap procedure

Performed in the implementation phase (the writing-plans skill expands these into a step-by-step plan).

1. Copy `ai-ready-backend-template/` → `agentic-workbench/venue-backend/`, excluding `.git`. Initialize a fresh git repo.
2. Apply Recipe A (`docs/template-customization.md`) to remove the AI module:
   - delete `app/ai/`, `app/api/v1/ai_chat/`, `tests/unit/ai`, `tests/integration/ai`, `tests/unit/architecture/test_ai_isolation.py`
   - strip the AI conditional from `app/main.py` lifespan (and the unused `settings = get_settings()` line above it)
   - remove `ai_provider`, `ai_model_name`, `ai_api_key`, `ai_temperature` from `app/core/config.py`
   - delete `requirements-ai.txt` and the `install-ai` Make target
   - clean `BACKEND_AI_PROVIDER=none` from `tests/conftest.py` and `tests/e2e/conftest.py`
   - delete `test_settings_ai_provider_default_none`
   - update the docstring at the top of `app/api/v1/router.py`
   - run tests; grep for `ai_provider|app.ai|ai_chat` returns nothing
3. Replace the `users` sample (Recipe C) with the real `accounts` feature in the same step. Read the existing `users/` code first to understand auth + JWT mechanics, port them into `accounts/` with the `Role` enum added.
4. Build the remaining features in this order (each adds a migration, mappings, repos, handlers, routes, tests):
   1. `catalog` (no dependencies)
   2. `subscriptions` (depends on `accounts`)
   3. `resources` (depends on `accounts`, `catalog`)
   4. `notifications` (no dependencies; port + logging adapter)
   5. `bookings` (depends on all of the above)
5. Seed data: one Admin account (env-var-driven on first boot) and a starter `ResourceType("Football Field")` so the platform is immediately usable.
6. Postgres-only. MSSQL files stay as the template provides them but unused; not removed (cheap to keep).

## 9. Testing strategy

Mirrors the template's `tests/` layout.

| Level | Path | What it covers |
|---|---|---|
| Unit (domain) | `tests/unit/domain/` | Pure invariants per aggregate. E.g., `Booking.approve()` from `APPROVED` raises; `Resource.compute_price(slot_range)` matches rules and falls back. |
| Unit (use cases) | `tests/unit/use_cases/` | Handler tests with in-memory fake repos implementing `domain/<feature>/repository.py` `Protocol`s. E.g., `RequestBookingHandler` rejects when subscription `INACTIVE`. |
| Integration | `tests/integration/` | Handler + real DB. Critical: partial unique index prevents two `APPROVED` overlaps; advisory lock serializes concurrent approvals. |
| End-to-end | `tests/e2e/` | One happy-path per role flow via FastAPI test client. |
| Architecture | `tests/unit/architecture/` | Keep existing layer-import tests. Add: no `domain/<feature_a>/` imports from `domain/<feature_b>/`. |

## 10. Out of scope (see `Opportunities.md`)

- Booking payment status field, in-platform payments (Stripe / Mercado Pago / PIX), marketplace split.
- Self-serve flat-rate subscription with PSP webhooks; tiered plans with per-tier limits.
- Per-slot price overrides for holidays / special dates.
- Full marketplace discovery: map, geosearch, ratings, sort.
- WhatsApp / SMS notifications via the existing port.
- Auto-confirm trusted customers (per-resource allowlist that bypasses approval).
- Slot-time-based reminders and no-show flagging.
- Schedule exceptions / holidays at the resource level.
- Reviews and ratings.
- Reports / analytics module from the template (kept removable per Recipe B).

## 11. Open items (none blocking, flagging for awareness)

- Time zones: server stores all timestamps in UTC; resource's `timezone` field (§5.3) is used to interpret `WeeklySchedule` and `PricingRule` window times in the resource's local zone, and to compute the cutoff before customer cancellation.
- Email templates: pt-BR strings via a translation map; concrete templates are an implementation detail, not a design concern.
- Soft-delete semantics for `User` (deactivation) vs `Resource` (soft-delete via `deleted_at`): different fields, intentionally — users are never hard-deleted because of foreign keys on bookings; resources can be soft-deleted because they're owner property.
