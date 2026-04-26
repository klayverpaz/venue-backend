# Venue Backend — Design Spec

**Date:** 2026-04-25
**Status:** Approved (revised 2026-04-25 — VO foundation + ratings feature)
**Source template:** `agentic-workbench/ai-ready-backend-template/`
**Repository:** `git@github.com:klayverpaz/venue-backend.git`

## 1. Project context

A backend for a rental-by-hourly-slots marketplace. The motivating use case is football-field rentals (owner publishes a field, customers request booking blocks for games), but the domain is built generic so the same code serves padel courts, studios, meeting rooms, etc. Football-field-specific data lives in the seeded `ResourceType` catalog, not in the package or schema.

Built on top of `ai-ready-backend-template` (FastAPI + SQLAlchemy + Postgres + CQRS + vertical slicing per feature). The AI module from the template is removed up front. The `users` sample is replaced with a real `accounts` feature in the same step.

Project name and folder: `venue-backend`. Located at `agentic-workbench/venue-backend/`.

## 2. Roles and personas

| Role | Capabilities |
|---|---|
| **Admin** | Curates `ResourceType` catalog (admin-managed). Manages users (promote/demote roles, deactivate). Manages owner subscription status. Moderates ratings (hide/unhide). |
| **Owner** | Registers and manages their `Resource`s. Defines operating hours, slot duration, pricing rules, custom attributes per resource. Reviews and approves/rejects/cancels bookings on their resources. Read-only view of their subscription status and ratings on their resources. |
| **Customer** | Browses public resource listings, requests bookings (one or more consecutive slots) with a free-form note, sees their own bookings, cancels until configurable cutoff, rates resources after the booking ends. |

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
| 11 | Discovery: each owner and each resource gets a public URL (slug-based). Plus a platform-wide listing filterable by resource type and city/region. No map, no geosearch. Ratings are aggregated from completed bookings. | Fits the realistic acquisition model (owners drive traffic via social) without skipping browse-ability. |
| 12 | Cancellations: owner can cancel anytime; customer can cancel until `customer_cancellation_cutoff_hours` before slot start. Audit trail on the booking. | Encodes the natural asymmetry; no monetary penalties (money is off-platform). |
| 13 | Notifications: in-app inbox for every event + transactional email via a port (`IEmailSender`). Logging adapter for MVP; real provider later. | In-app alone gets missed; email is essentially free; port keeps WhatsApp/SMS a swap-in. |
| 14 | Idempotency keys accepted on `POST /me/bookings` and approval/reject endpoints. | Cheap to add; avoids the inevitable double-click / network-retry duplicate booking. |
| 15 | Localization: identifiers and code in English; user-facing strings in pt-BR. **VO and handler errors are stable code identifiers** (e.g., `"NameCannotBeEmpty"`); the HTTP boundary in `app/api/error_handler.py` maps codes → pt-BR. | Stable contract for tests + i18n, decoupled from display language. |
| 16 | **Money is represented as `int` cents (smallest currency unit), wrapped in a `Money` VO.** Float is forbidden for monetary values. | Floats can't represent decimals exactly (`0.1 + 0.2 ≠ 0.3`); industry standard for marketplaces (Stripe, Mercado Pago, Adyen) is integer minor units. |
| 17 | **Domain entities NEVER hold raw primitives where a VO exists.** `User.full_name: Name`, not `str`; `Booking.slot_range: DateTimeRange`, not two datetimes; etc. DB columns for VO-backed strings are `TEXT` (no `VARCHAR(N)`) — the VO is the single source of truth for length. | Centralizes validation and prevents "this `name` got past validation because it took a different path" bugs. |
| 18 | **Ratings are per-booking** (1 rating per completed `APPROVED` booking), not per (customer × resource). Resource exposes `rating_avg` and `rating_count` derived on-the-fly via SQL aggregation; **no denormalized cache** in MVP. | Reflects discrete experiences (rainy Saturday vs sunny Saturday); eligibility check is trivial (`booking.status = APPROVED AND end_at < now`); on-the-fly aggregation with index on `resource_id` is microseconds at MVP scale. |
| 19 | Rating creation window: 90 days after `slot_range.end_at`. Rating edit window: 7 days after `created_at`. | Anti-retaliation / anti-spam on ancient bookings; short edit window matches Booking.com pattern. |
| 20 | Admin can soft-hide a rating (`is_hidden = True`); never deletes. Hidden ratings excluded from average/count/public listings. | Audit trail preserved; no information loss. |

## 4. Architecture

The template's rules apply unchanged. Layered + vertical slicing per feature. Seven features, each owning one aggregate root.

```
api ──▶ use_cases ──▶ domain ◀── infrastructure
```

`domain/` stays pure Python; `use_cases/` depends only on `domain/<feature>/repository.py` `Protocol`s; `infrastructure/` provides concrete repositories and adapters; `api/v1/<feature>/routes.py` does HTTP-only validation.

### 4.1 Feature split (seven aggregates)

| Feature | Aggregate root | Sub-entities / VOs |
|---|---|---|
| `accounts` | `User` | `Role` |
| `catalog` | `ResourceType` | `AttributeDefinition` |
| `resources` | `Resource` | `WeeklySchedule`, `PricingRule`, `CustomAttribute` |
| `bookings` | `Booking` | `SlotRange`, `StatusChange` |
| `subscriptions` | `OwnerSubscription` | `SubStatus` |
| `notifications` | `Notification` | `IEmailSender` port |
| `ratings` | `Rating` | (none — leaf aggregate) |

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
| `CreateRatingHandler` | `ratings/commands` | `IRatingRepository`, `IBookingRepository`, `INotificationService` | Verifies booking is APPROVED + ended + within 90d window + customer matches; persists rating; notifies owner. |
| `UpdateRatingHandler` | `ratings/commands` | `IRatingRepository` | Customer-only; enforces 7d edit window. |
| `HideRatingHandler` | `ratings/commands` | `IRatingRepository` | Admin-only; soft-hide + reason. |

### 4.3 Shared Value Objects

All VOs live under `app/domain/shared/value_objects/<vo>.py`. **Every VO follows the same convention** (Python translation of the team's C# `SimpleValueObject<T>` / `ValueObject<TSelf>` pattern):

- `@dataclass(frozen=True, slots=True)` inheriting `BaseValueObject`.
- Public entrypoint is `cls.create(raw) -> Result[Self]`. Direct `__init__` is the dataclass auto-generated one but is treated as private — call sites use `create()`.
- `cls.create_if_not_empty(raw) -> Result[Self | None]` companion for optional inputs (returns `None` on null/empty).
- `_validate(...) -> str` private static; returns the error code or `""`.
- Error messages are **stable identifier codes** as class constants (e.g., `Name.NAME_CANNOT_BE_EMPTY = "NameCannotBeEmpty"`), NOT human-readable strings. The HTTP boundary maps codes → pt-BR.
- `MAX_LENGTH` (and similar bounds) are exposed as class constants.
- String VOs strip on entry.
- Equality is free from `frozen=True`.

#### Catalog of VOs

| VO | Type | Bound | Where used |
|---|---|---|---|
| `Email` | `str` | max 254 | `User.email` (existing) |
| `BrazilianPhone` | `str` | tel format | `User.phone` (existing) |
| `Slug` | `str` | max 80, kebab-case `^[a-z][a-z0-9-]*[a-z0-9]$`, no leading/trailing/repeated `-` | `ResourceType.slug`, `Resource.slug` |
| `Name` | `str` | max 500, min 1 (after strip), no control chars | `User.full_name`, `ResourceType.name`, `Resource.name`, `Resource.city`, `Resource.region` |
| `ShortName` | `str` | max 40, min 1 | `AttributeDefinition.label`, `CustomAttribute.label`, entries in `AttributeDefinition.enum_values` |
| `ShortDescription` | `str` | max 500, min 0 (empty allowed) | `ResourceType.description`, `Resource.description`, `Booking.customer_note`, `Rating.comment` |
| `AttributeKey` | `str` | max 50, snake_case `^[a-z][a-z0-9_]*$` | `AttributeDefinition.key`, `CustomAttribute.key` |
| `Money` | `int` cents | ≥ 0, ≤ 10¹⁰ (R$ 100M) | `Resource.base_price_cents`, `PricingRule.price_cents`, `Booking.total_price_cents` |
| `TimeWindow` | `(time, time)` | `start < end`, intra-day (no overnight wrap) | per-day operating hours, `PricingRule.starts_at`/`ends_at` |
| `DateTimeRange` | `(datetime, datetime)` | both tz-aware UTC, `start_at < end_at` | `Booking.SlotRange` (alias) |
| `IanaTimezone` | `str` | ∈ `zoneinfo.available_timezones()` | `Resource.timezone` |
| `SlotDuration` | `int` | ∈ {30, 45, 60, 90, 120} | `Resource.slot_duration_minutes` |
| `CancellationCutoff` | `int` hours | 0 ≤ n ≤ 168 | `Resource.customer_cancellation_cutoff_hours` |
| `RatingScore` | `int` | ∈ {1, 2, 3, 4, 5} | `Rating.score` |

#### Removed / renamed

- The template-shipped `NonNegativeFloat` is removed. Money flows exclusively through `Money` (int cents); float is forbidden for any monetary value.
- The template-shipped `Percentage` VO is left as-is (unused by the current model); kept available if a future feature needs it.
- `Email` and `BrazilianPhone` stay; their internal error strings are refactored to the stable-code style above (e.g., `Email.EMAIL_CANNOT_BE_EMPTY = "EmailCannotBeEmpty"`).

### 4.4 Entity conventions

All aggregate roots follow the same convention (Python translation of the team's C# `Entity<TId>` pattern):

- `@dataclass(slots=True, kw_only=True)` inheriting `BaseEntity`. **Not** `frozen=True` — entities are mutable through their methods.
- **Class-level error code constants** for entity-scoped invariants and state-transition errors. Same stable-identifier style as VOs:
  ```python
  class Booking(BaseEntity):
      BOOKING_ALREADY_APPROVED = "BookingAlreadyApproved"
      INVALID_STATUS_TRANSITION = "InvalidStatusTransition"
      CUSTOMER_CUTOFF_PASSED = "CustomerCutoffPassed"
  ```
- **Public construction via `cls.create(...) -> Result[Self]` only.** The dataclass `__init__` is treated as private; call sites always go through `create()`.
- **VO-typed fields throughout** (`name: Name`, `slot_range: DateTimeRange`, `total_price_cents: Money`). No raw primitives where a VO exists.
- **Mutators that enforce an invariant return `Result[None]`.** They mutate `self` as a side effect; the `Result` signals whether the mutation succeeded:
  ```python
  def approve(self, *, owner_id: UUID, at: datetime) -> Result[None]:
      if self.status != BookingStatus.PENDING:
          return Result.failure(self.INVALID_STATUS_TRANSITION)
      self.status = BookingStatus.APPROVED
      self._status_history.append(...)
      self.updated_at = _utcnow()
      return Result.success(None)
  ```
- **Mutators with no invariant return `None`** (e.g., `User.set_role`, `User.deactivate`). The discriminator is "is there a domain rule that can fail here?".
- **State-transition methods (`mark_as_X`, `approve`, `reject`, `cancel`)** enforce the state machine. Invalid transitions return `Result.failure(<entity>.<CODE>)`.
- **Private collections + immutable views** for child collections:
  ```python
  _status_history: list[StatusChange] = field(default_factory=list)

  @property
  def status_history(self) -> tuple[StatusChange, ...]:
      return tuple(self._status_history)
  ```
  External code reads through the tuple; mutation is only through `add_*` / `remove_*` methods on the entity.
- **`Add*` / `Remove*` collection methods** validate uniqueness and ownership before mutating, return `Result[None]`.
- **`updated_at` is bumped inside every successful mutator.** A `_utcnow()` helper at module level keeps imports tight.
- **Pure read methods on state** (`is_in_window(now)`, `is_delayed(now)`) coexist with mutators and return primitives — no `Result` wrapping reads.
- **No business logic in `routes.py` or repositories.** All invariants live in the entity or in the use-case handler that orchestrates multiple entities (per CLAUDE.md §"Regra cross-entity").

## 5. Domain model

> **Notation:** any property typed as a VO name (e.g., `name: Name`) is constructed via the VO's `create()` factory at the entity's `create()` boundary. Raw primitives never enter the entity for those fields.

### 5.1 `accounts` — `User`

```
User
├── id: UUID
├── email: Email
├── password_hash: str                # opaque hash; PasswordHasher controls format
├── role: Role (enum: ADMIN | OWNER | CUSTOMER)
├── full_name: Name
├── phone: BrazilianPhone | None
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
├── slug: Slug                        # unique, e.g. "football-field"
├── name: Name
├── description: ShortDescription
├── attribute_schema: list[AttributeDefinition]
└── is_active: bool

AttributeDefinition (VO, composite)
├── key: AttributeKey
├── label: ShortName
├── data_type: AttrType (STRING | INT | BOOL | ENUM)
├── required: bool
└── enum_values: list[ShortName] | None  (only when data_type == ENUM)
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
├── slug: Slug                              # unique, public URL
├── name: Name
├── description: ShortDescription
├── city: Name
├── region: Name
├── timezone: IanaTimezone
├── slot_duration_minutes: SlotDuration
├── operating_hours: WeeklySchedule
├── pricing_rules: list[PricingRule]        # may have gaps
├── base_price_cents: Money                 # fallback price when no rule covers a slot
├── base_attributes: dict[str, Any]         # values for ResourceType.attribute_schema
├── custom_attributes: list[CustomAttribute]
├── customer_cancellation_cutoff_hours: CancellationCutoff
├── is_published: bool
└── created_at, updated_at, deleted_at (soft-delete)

WeeklySchedule (VO, composite)
└── 7 entries: { weekday: Weekday, hours: TimeWindow | None (None = closed) }

PricingRule (VO, composite)
├── weekdays: set[Weekday]
├── window: TimeWindow
└── price: Money

CustomAttribute (VO, composite)
├── key: AttributeKey
├── label: ShortName
└── value: ShortDescription
```

**Invariants**
- `owner_id`'s role must be `OWNER` (verified at handler level).
- Each non-closed weekday's `TimeWindow` is divisible by `slot_duration_minutes` (slot grid alignment).
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
├── slot_range: DateTimeRange               # tz-aware UTC; start_at < end_at
├── status: BookingStatus                   # PENDING | APPROVED | REJECTED | CANCELLED | EXPIRED
├── customer_note: ShortDescription | None
├── total_price_cents: Money                # frozen at request time
├── status_history: list[StatusChange]
├── cancelled_by: ActorRef | None           # OWNER | CUSTOMER, with user_id
└── created_at, updated_at

# Derived: slot_count = (slot_range.end_at − slot_range.start_at) / resource.slot_duration_minutes

StatusChange (VO, composite)
├── from_status: BookingStatus
├── to_status: BookingStatus
├── actor_id: UUID
├── actor_role: Role
├── at: datetime
└── reason: str | None                      # ≤ 500 chars; not VO-wrapped (audit field)
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
├── status_changed_at: datetime          # tz-aware UTC
├── trial_ends_at: datetime | None       # tz-aware UTC; required iff status=TRIALING
└── created_at, updated_at
```

**Invariants**
- One row per owner.
- Cross-field invariant: `status == TRIALING` ⇔ `trial_ends_at is not None` (enforced in `__post_init__`).
- Auto-created in `TRIALING` status when a `User` registers with `role=OWNER` (atomic with the user insert, shared `AsyncSession`). `trial_ends_at = now + Settings.trial_duration_days` (default 3 days).
- Only `SetOwnerSubscriptionStatusHandler` (admin-only) mutates `status`; idempotent on no-op.
- `ExpireTrialingSubscriptionsHandler` nightly cron flips `TRIALING → INACTIVE` for rows with `trial_ends_at < now`. Stale-state window bounded by cron interval (acceptable per §3 decision 9 — soft subscription, no money at stake).
- `is_operational()` returns true when `status ∈ {ACTIVE, TRIALING}`. Plan 06 `PublicListResources` composes this with `User.is_active` for the operational gate.

### 5.6 `notifications` — `Notification`

```
Notification
├── id: UUID
├── recipient_id: UUID
├── kind: NotifKind
├── payload: dict                           # JSON, kind-specific shape
├── read_at: datetime | None
└── created_at

NotifKind
├── BOOKING_REQUESTED
├── BOOKING_APPROVED
├── BOOKING_REJECTED
├── BOOKING_CANCELLED
├── BOOKING_RATED                           # NEW — rating created on owner's resource
└── SUBSCRIPTION_CHANGED

IEmailSender (Protocol, in domain/notifications/)
└── send(to: Email, kind: NotifKind, payload: dict) -> Result[None]
```

**Invariants**
- Every notification persists an in-app row regardless of email delivery outcome.
- Email send failures are logged but do not fail the originating use case.

### 5.7 `ratings` — `Rating`

```
Rating
├── id: UUID
├── booking_id: UUID                        # FK + UNIQUE — 1 rating per booking
├── resource_id: UUID                       # denormalized for AVG queries
├── customer_id: UUID                       # denormalized for "my ratings"
├── score: RatingScore                      # int 1..5
├── comment: ShortDescription | None        # optional
├── is_hidden: bool                         # admin moderation; default False
├── hidden_reason: str | None               # ≤ 500 chars; admin freeform on hide
└── created_at, updated_at
```

**Invariants**
- `booking_id` UNIQUE (DB index) — a booking yields at most one rating.
- The booking referenced must satisfy: `status == APPROVED`, `slot_range.end_at < now`, `customer_id == rating.customer_id`. Verified in `CreateRatingHandler`.
- **Creation window:** `now ≤ booking.slot_range.end_at + 90 days`. After that, creation is rejected.
- **Edit window:** `now ≤ rating.created_at + 7 days`. After that, only `is_hidden` mutates (admin-only).
- `is_hidden = True` removes the row from public average, count, and listings.

**Read-side derivation (resource aggregation)**

`Resource` does NOT store rating fields. Every endpoint that returns a resource (public or owner-scoped) computes:

```sql
SELECT
  AVG(score)::numeric(3, 1) AS rating_avg,    -- one decimal, NULL if no rows
  COUNT(*)                  AS rating_count
FROM ratings
WHERE resource_id = $1 AND is_hidden = FALSE
```

Owner-scoped resource list adds the same agg. Public owner page (`GET /owners/{slug}`) computes a count-weighted average across all of the owner's published resources.

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

All endpoints under `/api/v1/`. JWT auth via the same mechanism as the template's `users` sample. Pagination on every list endpoint: `?page=&page_size=` (max 100). Errors mapped from `Result` per `error_handler.py`, which translates VO/handler error codes to pt-BR.

### 7.1 Public (no auth)

```
GET  /resources                              # filters: type=<slug>&city=&region=&page=&page_size=
GET  /resources/{slug}                       # public resource page (incl. rating_avg + rating_count)
GET  /resources/{slug}/agenda?from=&to=      # slot grid: AVAILABLE | PENDING | APPROVED + price
GET  /resources/{slug}/ratings               # only ratings with comment, not hidden, paginated
GET  /owners/{slug}                          # public owner page (their published resources + rating agg)
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

POST   /me/bookings/{booking_id}/rating      # body: { score, comment? }
PATCH  /me/bookings/{booking_id}/rating      # body: { score?, comment? }; 403 after 7d
GET    /me/ratings

GET    /me/notifications
POST   /me/notifications/{id}/read
```

### 7.4 Owner (role = OWNER)

```
# Resources
POST   /me/resources
GET    /me/resources                         # incl. rating_avg + rating_count per resource
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

# Ratings on my resources (read-only)
GET    /me/resources/{id}/ratings            # all ratings (hidden + not), paginated

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

# Ratings (moderation)
GET    /admin/ratings?hidden=&resource_id=
POST   /admin/ratings/{id}/hide              # body: { reason? }
POST   /admin/ratings/{id}/unhide
```

## 8. Bootstrap procedure

The plan order below is the contract for `docs/superpowers/plans/`.

1. **Plan 01 — Bootstrap** ✅ done. Copy `ai-ready-backend-template/` → `agentic-workbench/venue-backend/` and apply Recipe A (remove AI module).
2. **Plan 02 — Accounts** ✅ done. JWT auth + `accounts` feature with `Role` enum, replacing the `users` sample.
3. **Plan 03 — VO foundation + accounts retrofit.** Ship the 12 new VOs (`Slug`, `Name`, `ShortName`, `ShortDescription`, `AttributeKey`, `Money`, `TimeWindow`, `DateTimeRange`, `IanaTimezone`, `SlotDuration`, `CancellationCutoff`, `RatingScore`) plus refactor existing `Email` and `BrazilianPhone` to the stable-code style. Update `app/api/error_handler.py` to map VO/handler error codes to pt-BR. Retrofit `accounts`: `User.full_name: str → Name`. Reset and regenerate Alembic migrations on top of the new VO-aware mappings.
4. **Plan 04 — Catalog.** `ResourceType` aggregate using `Slug`/`Name`/`ShortDescription`/`AttributeKey`/`ShortName`. Admin CRUD + public listing.
5. **Plan 05 — Subscriptions.** `OwnerSubscription` aggregate; admin-only mutation; `is_operational()` gating.
6. **Plan 06 — Resources.** `Resource` aggregate using `Slug`/`Name`/`ShortDescription`/`Money`/`TimeWindow`/`IanaTimezone`/`SlotDuration`/`CancellationCutoff`. Owner CRUD + public read.
7. **Plan 07 — Notifications.** `Notification` aggregate + `IEmailSender` port + logging adapter. Includes `BOOKING_RATED` enum value.
8. **Plan 08 — Bookings.** `Booking` aggregate using `DateTimeRange`/`Money`/`ShortDescription`. Approval transaction with advisory lock + exclusion constraint. Nightly expiry job.
9. **Plan 09 — Ratings.** `Rating` aggregate. Customer create/edit endpoints. Public list with comment. Admin moderation. `Resource` GETs gain `rating_avg` + `rating_count` aggregates.
10. **Plan 10 — Seed + production wiring.** Bootstrap admin account (env-driven), seed `ResourceType("Football Field")`. Postgres-only. MSSQL files stay as the template provides them but unused.

## 9. Testing strategy

Mirrors the template's `tests/` layout.

| Level | Path | What it covers |
|---|---|---|
| Unit (VO) | `tests/unit/domain/shared/value_objects/` | One file per VO. Asserts on **error code constants** (e.g., `assert r.error == Name.NAME_CANNOT_BE_EMPTY`), never substring matches. |
| Unit (domain) | `tests/unit/domain/` | Pure invariants per aggregate. E.g., `Booking.approve()` from `APPROVED` raises; `Resource.compute_price(slot_range)` matches rules and falls back. |
| Unit (use cases) | `tests/unit/use_cases/` | Handler tests with in-memory fake repos implementing `domain/<feature>/repository.py` `Protocol`s. E.g., `RequestBookingHandler` rejects when subscription `INACTIVE`; `CreateRatingHandler` rejects past 90d window. |
| Integration | `tests/integration/` | Handler + real DB. Critical: partial unique index prevents two `APPROVED` overlaps; advisory lock serializes concurrent approvals; rating `booking_id` UNIQUE enforced. |
| End-to-end | `tests/e2e/` | One happy-path per role flow via FastAPI test client, plus the rating happy path (book → approve → wait → rate → see in public list). |
| Architecture | `tests/unit/architecture/` | Keep existing layer-import tests. Add: no `domain/<feature_a>/` imports from `domain/<feature_b>/`; entities import VOs from `domain/shared/value_objects/`. |

## 10. Out of scope (see `Opportunities.md`)

- Booking payment status field, in-platform payments (Stripe / Mercado Pago / PIX), marketplace split.
- Self-serve flat-rate subscription with PSP webhooks; tiered plans with per-tier limits.
- Per-slot price overrides for holidays / special dates.
- Full marketplace discovery: map, geosearch, sort by rating.
- WhatsApp / SMS notifications via the existing port.
- Auto-confirm trusted customers (per-resource allowlist that bypasses approval).
- Slot-time-based reminders and no-show flagging.
- Schedule exceptions / holidays at the resource level.
- Owner reply to a rating; helpful/not-helpful votes on ratings; rating disputes.
- Owner rating the customer (no-show flag).
- Reports / analytics module from the template (kept removable per Recipe B).
- Overnight `TimeWindow` (e.g., 18:00–02:00 wrapping past midnight).
- Denormalized `rating_avg`/`rating_count` cache on `Resource` (current MVP computes on-the-fly).

## 11. Open items (none blocking, flagging for awareness)

- Time zones: server stores all timestamps in UTC; resource's `timezone` field is used to interpret `WeeklySchedule` and `PricingRule` window times in the resource's local zone, and to compute the cutoff before customer cancellation.
- Email templates: pt-BR strings via a translation map; concrete templates are an implementation detail, not a design concern.
- Soft-delete semantics for `User` (deactivation) vs `Resource` (soft-delete via `deleted_at`): different fields, intentionally — users are never hard-deleted because of foreign keys on bookings; resources can be soft-deleted because they're owner property.
- Error code → pt-BR mapping table lives in `app/api/error_handler.py`. Adding a new VO error means adding both the code constant on the VO and an entry in the mapping. The architecture test in §9 should enforce 1:1 coverage so a new code without a translation fails CI.
