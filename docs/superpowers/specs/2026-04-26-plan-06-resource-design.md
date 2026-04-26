# Plan 06 — Resource Design Doc

**Status:** Approved 2026-04-26.
**Author:** klayver + Claude (brainstorm session).
**Scope:** Plan 06 of the venue-backend roadmap (`docs/superpowers/specs/2026-04-25-venue-backend-design.md` §8). Refines and extends `Resource` aggregate beyond what §5.3 specified.

## 1. Motivation

`Resource` is the largest aggregate in the venue domain: it carries the operating schedule, pricing rules, attribute values, and lifecycle state that `Booking` (Plan 08), `Rating` (Plan 09), and the public discovery endpoints all read from. Spec §5.3 sketches the shape but leaves the business rules implicit: how multiple time windows per weekday compose, how pricing rules interact, how soft-delete and the owner subscription gate compose, and how cross-feature validation (`base_attributes` × `ResourceType.attribute_schema`) flows.

This doc nails those rules down so Plan 06 can be implemented without re-deriving the policy at every TDD checkpoint.

This refinement deviates from §5.3 in five places (all approved by the user during brainstorming):

- **`WeeklySchedule.hours`** is `tuple[TimeWindow, ...]` per weekday (0..N windows, ordered, non-overlapping, slot-aligned), not a single `TimeWindow | None`. Splits like 8h-12h + 14h-22h are first-class.
- **`Resource.slug`** is unique **per owner**, not globally. Public URL keys off both owner and resource slugs.
- **`User.public_slug: Slug | None`** is added to `accounts` (mandatory for OWNER) so owner-keyed routes can use a human-readable slug instead of UUIDs.
- **`is_published`** is a first-class lifecycle field (defaults to `False`); spec §5.3 already lists it but didn't pin down draft-vs-published semantics.
- **`base_attributes` schema validation** runs at the handler level, not in `Resource.create()`. Cross-feature dependency (`Resource` would otherwise need to import `ResourceType`) is resolved by the handler aggregating both error sources.

## 2. Scope

### In scope

- `Resource` aggregate (`app/domain/resources/resource.py`) + composite VOs (`WeeklySchedule`, `PricingRule`, `CustomAttribute`) + shared `Weekday` enum.
- `IResourceRepository` Protocol + `SQLAlchemyResourceRepository`. Storage: one `resources` row per resource with `operating_hours`, `pricing_rules`, `custom_attributes`, and `base_attributes` as `JSONB`.
- Owner-scoped command handlers: create, update metadata, replace operating hours / pricing rules / base_attributes / custom_attributes, set base_price / cancellation_cutoff / slot_duration, publish/unpublish, soft-delete.
- Owner-scoped query handlers: get-mine, list-mine.
- Public query handlers: get-public-resource, list-public-resources, get-owner-public-page. All apply the `is_owner_operational` gate (Plan 05 §7 pattern: subscription operational AND user.is_active).
- `User.public_slug` extension to `accounts`: domain field, mapping column, repository method `get_by_public_slug`, generation logic in `RegisterUserHandler`, migration. Mandatory for OWNER role; forbidden for ADMIN/CUSTOMER.
- Endpoints: owner CRUD under `/v1/me/resources/...` (one generic `PATCH` plus dedicated routes for ops-hours, pricing-rules, slot-duration, publish/unpublish, soft-delete), public reads under `/v1/resources`, `/v1/owners/{owner_slug}`, `/v1/owners/{owner_slug}/resources/{resource_slug}`.
- Stable error codes registered in `ERROR_MESSAGES_PT_BR` + arch test allowlist.
- **Plan 05 follow-up #5** (raw-pt-BR strings in `RegisterUserHandler` → stable codes) folded in as a final task before merge.
- **Plan 05 follow-up #6** (canonical spec §5.5 update with Plan 05 deltas) folded in as a final task before merge.

### Out of scope (deliberate)

- `Booking` aggregate, request/approval flow, advisory lock + exclusion constraint — Plan 08.
- Auto-rejection of `PENDING` bookings on `Resource.soft_delete()` — Plan 08 extends `SoftDeleteResourceHandler` with `IBookingRepository`. Plan 06 ships the soft-delete plumbing (no booking checks); the future-`APPROVED`-blocks-delete invariant is enforced when bookings exist.
- `rating_avg` / `rating_count` on resource DTOs — Plan 09 adds the aggregation.
- `Resource.compute_price()` integration with booking flow — the method ships in Plan 06 (used by tests), but its caller `RequestBookingHandler` arrives in Plan 08.
- Geosearch, map, sort by rating, schedule exceptions / holidays — backlog (per the canonical spec §10).
- Per-slot price overrides for holidays / special dates — backlog.
- "Restore" endpoint for soft-deleted resources — admin/DB operation if a real case ever arises.
- Diff-based updates for composite collections. `replace_*` mutators do full replacement (DELETE-all + INSERT-all serialized; with JSONB, this is just overwriting the column).

## 3. Domain shape

### 3.1 `Weekday` enum

`app/domain/shared/weekday.py` (new, shared between `WeeklySchedule` and `PricingRule`):

```python
from enum import Enum

class Weekday(str, Enum):
    MONDAY = "MONDAY"
    TUESDAY = "TUESDAY"
    WEDNESDAY = "WEDNESDAY"
    THURSDAY = "THURSDAY"
    FRIDAY = "FRIDAY"
    SATURDAY = "SATURDAY"
    SUNDAY = "SUNDAY"
```

Not a Value Object — no `create()`, no validation. Just a domain enum. Lives in `app/domain/shared/` (not `value_objects/`) because it's a primitive-style enum, not a wrapped value.

### 3.2 `WeeklySchedule` composite VO

`app/domain/resources/weekly_schedule.py`:

```python
@dataclass(frozen=True, slots=True)
class WeeklySchedule(BaseValueObject):
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
        """Aggregates errors via failure_many. Per weekday's window list:
        - Ordered by start: if windows[i].start >= windows[i+1].start, emit
          WINDOWS_NOT_ORDERED for index i+1.
        - No overlap (after ordering): if windows[i].end > windows[i+1].start,
          emit WINDOWS_OVERLAP for index i+1.
        - Each window aligned to the slot grid: window.start.minute %
          slot_duration_minutes == 0 AND window.duration_minutes() %
          slot_duration_minutes == 0. Otherwise emit
          WINDOW_NOT_ALIGNED_TO_SLOT_GRID for that index.
        FieldError.field = f"days.{weekday.value.lower()}[{idx}]".
        Closed days are represented by an empty list for that key (or the key absent).
        """
        ...

    def for_weekday(self, day: Weekday) -> tuple[TimeWindow, ...]:
        return getattr(self, day.value.lower())
```

7 explicit fields (not a `dict`) keep the dataclass `frozen=True`-friendly and serialize cleanly to/from JSON. Closed days are `()`. The factory takes a `dict` for ergonomics — the input shape is "what the API delivers", the storage shape is "what the entity exposes".

### 3.3 `PricingRule` composite VO

`app/domain/resources/pricing_rule.py`:

```python
@dataclass(frozen=True, slots=True)
class PricingRule(BaseValueObject):
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

Cross-rule validation (overlap, alignment, containment) is at the **`Resource`** level — those rules need `slot_duration` and `operating_hours` that `PricingRule` alone doesn't know.

### 3.4 `CustomAttribute` composite VO

`app/domain/resources/custom_attribute.py`:

```python
@dataclass(frozen=True, slots=True)
class CustomAttribute(BaseValueObject):
    key: AttributeKey
    label: ShortName
    value: ShortDescription

    @classmethod
    def create(cls, *, key: str, label: str, value: str) -> Result[Self]:
        """Aggregate via failure_many across the three VO factories.
        FieldError.field = "key" | "label" | "value".
        """
        ...
```

`value` is `ShortDescription` (string-only). Owners who need typed/filterable attributes (`max_players: 10`, `surface_type: SAND`) request the admin to add them to `ResourceType.attribute_schema` (which becomes `Resource.base_attributes`). This preserves the base-vs-custom distinction:

- **base** = curated by admin, standard across all resources of that type, filterable globally.
- **custom** = freeform local to one resource, not globally filterable, just descriptive.

### 3.5 `Resource` aggregate

`app/domain/resources/resource.py`:

```python
@dataclass(slots=True, kw_only=True)
class Resource(BaseEntity):
    PRICING_RULES_OVERLAP = "PricingRulesOverlap"
    PRICING_RULE_NOT_ALIGNED_TO_SLOT_GRID = "PricingRuleNotAlignedToSlotGrid"
    PRICING_RULE_OUTSIDE_OPERATING_HOURS = "PricingRuleOutsideOperatingHours"
    DUPLICATE_CUSTOM_ATTRIBUTE_KEY = "DuplicateCustomAttributeKey"
    CUSTOM_ATTRIBUTE_KEY_CONFLICTS_WITH_BASE = "CustomAttributeKeyConflictsWithBase"
    RESOURCE_ALREADY_DELETED = "ResourceAlreadyDeleted"
    DELETED_AT_NOT_TZ_AWARE = "ResourceDeletedAtNotTzAware"

    # Identity (immutable after create)
    owner_id: UUID
    resource_type_id: UUID

    # VO-typed fields
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

    # Schema-validated dict (HANDLER validates against ResourceType.attribute_schema)
    base_attributes: dict[str, Any] = field(default_factory=dict)

    # Lifecycle
    is_published: bool = False
    deleted_at: datetime | None = None  # tz-aware UTC when set

    # Private collections
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
        operating_hours: WeeklySchedule,        # pre-built by handler
        base_price_cents: int,
        customer_cancellation_cutoff_hours: int,
        base_attributes: dict[str, Any],
        pricing_rules: list[PricingRule],       # pre-built list
        custom_attributes: list[CustomAttribute],  # pre-built list
        is_published: bool = False,
    ) -> Result[Self]:
        """Aggregates errors via failure_many. Validates:
        - Each scalar VO field via its create() factory (slug, name, description,
          city, region, timezone, slot_duration_minutes, base_price_cents, cutoff).
        - Composite VOs (operating_hours, pricing_rules, custom_attributes) are
          assumed already built by the handler — their internal validation
          happened upstream and any errors must already have been merged into
          the handler-level envelope before Resource.create is called.
        - Cross-rule on pricing_rules:
          - No two rules overlap (same weekday + overlapping TimeWindow).
          - Each rule's window aligned to the slot grid (start.minute % slot_dur == 0
            AND duration_minutes() % slot_dur == 0).
          - Each rule's window contained in some operating_hours window for each
            weekday in its weekdays set.
        - custom_attribute.key values unique among themselves.
        - custom_attribute.key values disjoint from base_attributes.keys().
        - base_attributes type validation against ResourceType.attribute_schema is
          NOT performed here (cross-feature dependency). The HANDLER aggregates
          rt.validate_attributes errors with `field=f"base_attributes.{key}"`.
        """
        ...

    @property
    def pricing_rules(self) -> tuple[PricingRule, ...]:
        return tuple(self._pricing_rules)

    @property
    def custom_attributes(self) -> tuple[CustomAttribute, ...]:
        return tuple(self._custom_attributes)

    # Mutators returning Result[None] (invariant can fail)
    def update_metadata(
        self,
        *,
        name: str | None = None,
        description: str | None = None,
        city: str | None = None,
        region: str | None = None,
    ) -> Result[None]: ...

    def replace_operating_hours(self, hours: WeeklySchedule) -> Result[None]:
        """Re-runs cross-rule validation: existing pricing_rules must remain
        contained in new operating_hours."""

    def replace_pricing_rules(self, rules: list[PricingRule]) -> Result[None]:
        """Cross-rule: overlap, alignment, containment vs current operating_hours."""

    def replace_base_attributes(self, attrs: dict[str, Any]) -> Result[None]:
        """Re-validates custom_attributes.keys() disjoint from new attrs.keys().
        Schema validation (handler's job) happens before this mutator is called."""

    def replace_custom_attributes(self, attrs: list[CustomAttribute]) -> Result[None]:
        """Validates uniqueness and disjointness vs current base_attributes."""

    def set_slot_duration(self, duration: SlotDuration) -> Result[None]:
        """Re-validates operating_hours alignment + pricing_rules alignment +
        containment. Returns Result[None] because all three can fail under a
        new slot duration."""

    def soft_delete(self, *, now: datetime) -> Result[None]:
        """Idempotent failure on already-deleted. Plan 06 has no booking checks;
        Plan 08's SoftDeleteResourceHandler will inject IBookingRepository to
        block when an APPROVED future booking exists and to auto-reject PENDINGs
        in the same transaction."""
        if self.deleted_at is not None:
            return Result.failure(self.RESOURCE_ALREADY_DELETED)
        if now.tzinfo is None:
            return Result.failure(self.DELETED_AT_NOT_TZ_AWARE)
        self.deleted_at = now
        self.updated_at = now
        return Result.success(None)

    # Mutators returning None (no invariant can fail)
    def set_base_price(self, price: Money) -> None:
        self.base_price_cents = price
        self.updated_at = _utcnow()

    def set_cancellation_cutoff(self, cutoff: CancellationCutoff) -> None:
        self.customer_cancellation_cutoff_hours = cutoff
        self.updated_at = _utcnow()

    def publish(self) -> None:
        self.is_published = True
        self.updated_at = _utcnow()

    def unpublish(self) -> None:
        self.is_published = False
        self.updated_at = _utcnow()

    # Read methods (no Result wrapping)
    def is_deleted(self) -> bool:
        return self.deleted_at is not None

    def compute_price(self, slot_range: DateTimeRange) -> Money:
        """Iterates slots in slot_range (slot_count = duration / slot_duration).
        For each slot:
        - Convert slot_start (UTC) to the resource's timezone via
          slot_start.astimezone(ZoneInfo(self.timezone)). Extract weekday and
          time-of-day from that local datetime.
        - Match a rule when: weekday in rule.weekdays AND
          rule.window.start <= local_time_of_day < rule.window.end (half-open
          interval). The no-overlap invariant guarantees at most one rule
          matches per slot.
        - If no rule matches, use base_price_cents.
        - Sum across all slots; return as Money.

        Used by Plan 08's RequestBookingHandler. Resource carries the data and the
        algorithm; the handler injects the resource and calls compute_price.
        """
        ...
```

#### Cross-rule helpers (private)

`Resource._validate_pricing_rules(slot_dur, hours, rules) -> list[FieldError]` is a `@staticmethod` invoked from `create`, `replace_operating_hours`, `replace_pricing_rules`, and `set_slot_duration`. It encodes the three pricing rule cross-checks (overlap, alignment, containment) and emits `FieldError(code=..., field=f"pricing_rules[{idx}]")` per failing rule.

#### Cross-field invariants (`__post_init__`)

- `deleted_at`, when set, must be tz-aware. Otherwise → `DELETED_AT_NOT_TZ_AWARE`.

`updated_at`, `created_at` are inherited from `BaseEntity` and validated there per existing convention.

## 4. `User.public_slug` extension

### 4.1 Domain change

`app/domain/accounts/user.py`:

```python
@dataclass(slots=True, kw_only=True)
class User(BaseEntity):
    PUBLIC_SLUG_REQUIRED_FOR_OWNER = "PublicSlugRequiredForOwner"
    PUBLIC_SLUG_FORBIDDEN_FOR_NON_OWNER = "PublicSlugForbiddenForNonOwner"
    ...

    public_slug: Slug | None = None
    ...
```

Cross-field invariant added to `User.__post_init__`:

- `role == Role.OWNER` ⇔ `public_slug is not None`. Two failure paths:
  - OWNER without `public_slug` → `PUBLIC_SLUG_REQUIRED_FOR_OWNER`.
  - non-OWNER with `public_slug` → `PUBLIC_SLUG_FORBIDDEN_FOR_NON_OWNER`.

`User.create(...)` factory accepts an optional `public_slug: str | None` parameter; the role-based requirement is enforced through the `__post_init__` after VO factory + `failure_many` aggregation, consistent with the other cross-field rules.

### 4.2 Generation logic in `RegisterUserHandler`

`app/use_cases/accounts/commands/register_user.py` gains a slug-generation step when `cmd.role == Role.OWNER`:

```python
async def _generate_owner_public_slug(self, full_name: str) -> Slug:
    base = _slugify(full_name)  # "João Silva" → "joao-silva"
    candidate = base
    suffix = 2
    while await self._users.get_by_public_slug(candidate) is not None:
        candidate = f"{base}-{suffix}"
        suffix += 1
    return Slug.create(candidate).value  # safe: _slugify guarantees Slug-valid output
```

`_slugify` is a small private helper in the handler module (or `app/use_cases/shared/`):
- Lowercase the input.
- Strip accents (`unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode()`).
- Replace any non-`[a-z0-9]` run with `-`.
- Trim leading/trailing `-`.
- Collapse repeated `-`.
- If the result is empty (e.g., user named only with non-ASCII characters and the strip produced nothing), fall back to a UUID4-based slug to guarantee Slug validity. Edge case; acceptable.

The collision loop is bounded by linearly probing suffixes. Concurrency: two simultaneous OWNER registrations with names that slugify to the same base could both pick `joao-silva` before either commits. The DB `UNIQUE(public_slug)` constraint catches this — repository `add` returns a `PublicSlugAlreadyTaken` error which the handler retries (with `suffix += 1`). Retry budget: **5 attempts**. After exhaustion, the handler surfaces `Result.failure("PublicSlugAlreadyTaken", status_code=409)` and the registration fails. Given names that produce the exact same slug at the same instant are rare, the retry budget is enough for MVP.

### 4.3 Repository extension

`app/domain/accounts/repository.py` adds:

```python
async def get_by_public_slug(self, slug: str) -> User | None: ...
```

`SQLAlchemyUserRepository` implements via standard `SELECT ... WHERE public_slug = :slug LIMIT 1`.

### 4.4 Migration

`make migrate-new msg="users add public_slug"`:
- ADD COLUMN `public_slug TEXT NULL`.
- ADD UNIQUE CONSTRAINT on `public_slug` (NULL-safe — multiple NULLs allowed for ADMIN/CUSTOMER per ANSI SQL default; both Postgres and SQLite respect this).
- No backfill needed (greenfield: project has no users in production yet at the time Plan 06 lands).

## 5. Repository ports

`app/domain/resources/repository.py`:

```python
class IResourceRepository(Protocol):
    async def add(self, resource: Resource) -> Result[None]:
        """Persist a new Resource. Returns SlugAlreadyTaken (409) on
        (owner_id, slug) conflict."""

    async def update(self, resource: Resource) -> Result[None]:
        """Persist changes. Returns ResourceNotFound (404) if missing."""

    async def get_by_id(self, resource_id: UUID) -> Resource | None: ...

    async def get_by_owner_and_slug(
        self, owner_id: UUID, slug: str,
    ) -> Resource | None: ...

    async def list_by_owner(
        self,
        owner_id: UUID,
        *,
        include_deleted: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Resource]: ...

    async def list_published(
        self,
        *,
        resource_type_slug: str | None = None,
        city: str | None = None,
        region: str | None = None,
        owner_ids_filter: list[UUID] | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Resource]:
        """Excludes deleted_at IS NOT NULL and is_published=False rows.
        Owner-operational filtering is at HANDLER level (composes
        ISubscriptionRepository + IUserRepository); the optional
        `owner_ids_filter` lets the handler pre-compute operational owners
        and pass the allow-list down."""

    async def list_published_by_owner(
        self,
        owner_id: UUID,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Resource]: ...
```

Soft-delete is `update`-only — there is no `delete` method on the port. Hard-delete is admin-only / DB-level if it ever matters.

`ISubscriptionRepository` (Plan 05) and `IUserRepository` (Plan 02) gain batch helpers used by `ListPublicResourcesHandler`:

```python
# IUserRepository
async def list_by_ids(self, ids: Iterable[UUID]) -> list[User]: ...

# ISubscriptionRepository
async def list_by_owner_ids(self, owner_ids: Iterable[UUID]) -> list[OwnerSubscription]: ...
```

Both return entities whose IDs are a subset of the input (missing IDs simply absent from the response).

## 6. Use cases

### 6.1 Owner-scoped commands (`app/use_cases/resources/commands/`)

| Handler | Repos / config | Auth | Returns |
|---|---|---|---|
| `CreateResourceHandler` | `IResourceRepository`, `IResourceTypeRepository`, `IUserRepository` | OWNER | `Result[ResourceDto]` |
| `UpdateResourceMetadataHandler` | `IResourceRepository` | OWNER (resource owner) | `Result[ResourceDto]` |
| `ReplaceOperatingHoursHandler` | `IResourceRepository` | OWNER | `Result[ResourceDto]` |
| `ReplacePricingRulesHandler` | `IResourceRepository` | OWNER | `Result[ResourceDto]` |
| `ReplaceBaseAttributesHandler` | `IResourceRepository`, `IResourceTypeRepository` | OWNER | `Result[ResourceDto]` |
| `ReplaceCustomAttributesHandler` | `IResourceRepository` | OWNER | `Result[ResourceDto]` |
| `SetBasePriceHandler` | `IResourceRepository` | OWNER | `Result[ResourceDto]` |
| `SetCancellationCutoffHandler` | `IResourceRepository` | OWNER | `Result[ResourceDto]` |
| `SetSlotDurationHandler` | `IResourceRepository` | OWNER | `Result[ResourceDto]` |
| `PublishResourceHandler` | `IResourceRepository` | OWNER | `Result[ResourceDto]` |
| `UnpublishResourceHandler` | `IResourceRepository` | OWNER | `Result[ResourceDto]` |
| `SoftDeleteResourceHandler` | `IResourceRepository` | OWNER | `Result[None]` |

Common ownership pattern for every owner-scoped command:

```python
res = await self._resources.get_by_id(cmd.resource_id)
if res is None or res.owner_id != cmd.actor_id or res.is_deleted():
    return Result.failure("ResourceNotFound", status_code=404)
```

`is_deleted()` blocks edits to a soft-deleted resource (consistent UX: deleted = gone for the owner too).

### 6.2 `CreateResourceHandler` — cross-feature aggregation

Sequence:

1. Load `user = users.get_by_id(cmd.actor_id)`. If `None` or `user.role != OWNER` → `UserIsNotOwner` (403). (The route's auth middleware should already reject non-OWNER, but defense in depth.)
2. Load `rt = resource_types.get_by_id(cmd.resource_type_id)`. If `None` → `ResourceTypeNotFound` (404). If `not rt.is_active` → `ResourceTypeInactive` (422).
3. Build composite VOs from raw input — accumulate errors in a local `errors: list[FieldError]`:
   - `WeeklySchedule.create(slot_duration_minutes=..., days=...)`. On failure, prefix sub-errors with `field=f"operating_hours.{e.field}"`.
   - Each `PricingRule.create(...)` over the input list. On failure, prefix with `field=f"pricing_rules[{idx}]"` (or pass-through if `EMPTY_WEEKDAYS`, since that's the only single-error code).
   - Each `CustomAttribute.create(...)` over the input list. On failure, prefix with `field=f"custom_attributes[{idx}].{e.field}"`.
4. Call `rt.validate_attributes(cmd.base_attributes)`. Accumulate sub-errors into the same list with `field=f"base_attributes.{e.field}"`.
5. If `errors` is non-empty after steps 3-4, return `Result.failure_many(errors, status_code=400)` immediately — no point calling `Resource.create` if composites/attributes already failed.
6. Call `Resource.create(...)` with the pre-built composite VOs. Its errors (from VO scalar factories and cross-rule pricing checks) come out in the same `failure_many` shape; the handler returns those directly via `Result.from_failure(res_r, status_code=400)`.
7. Persist via `resources.add(res)`. On `SlugAlreadyTaken` (409), surface the repo failure directly (single-error `Result.failure`).
8. Return `Result.success(ResourceDto.from_entity(res))`.

The merge pattern follows `CreateResourceTypeHandler` (Plan 04) exactly — that handler aggregates `AttributeDefinition.create()` failures over a list. Plan 06 extends to two **cross-feature** error sources.

### 6.3 Owner-scoped queries (`app/use_cases/resources/queries/`)

| Handler | Repos | Notes |
|---|---|---|
| `GetMyResourceHandler` | `IResourceRepository` | 404-on-mismatch (non-owner or non-existent or deleted treated as 404). |
| `ListMyResourcesHandler` | `IResourceRepository` | Includes drafts (is_published=False). Excludes deleted (deleted_at IS NOT NULL). |

### 6.4 Public queries

`app/use_cases/resources/queries/`:

| Handler | Repos | Notes |
|---|---|---|
| `GetPublicResourceHandler` | `IResourceRepository`, `ISubscriptionRepository`, `IUserRepository` | Loads via `(owner_slug, resource_slug)`. 404 if non-published, soft-deleted, or owner not operational. |
| `ListPublicResourcesHandler` | `IResourceRepository`, `ISubscriptionRepository`, `IUserRepository` | Computes operational owner allow-list once per request, passes via `owner_ids_filter` to repo. |
| `GetOwnerPublicPageHandler` (in `app/use_cases/accounts/queries/`) | `IUserRepository`, `IResourceRepository`, `ISubscriptionRepository` | Returns owner DTO + their published resources. Cross-feature handler lives in `accounts` because the query keys off owner. |

#### 6.4.1 The `is_owner_operational` consumer pattern (Plan 05 §7)

For single-resource lookups (`GetPublicResourceHandler`):

```python
async def _is_operational(self, owner_id: UUID) -> bool:
    sub = await self._subscriptions.get_by_owner_id(owner_id)
    user = await self._users.get_by_id(owner_id)
    return bool(sub and sub.is_operational() and user and user.is_active)
```

For listings (`ListPublicResourcesHandler`):

```python
async def _operational_owner_ids(self) -> set[UUID]:
    """Compute once per request. We could narrow further by pre-fetching only
    owners with at least one published resource, but for MVP the small
    overhead of loading all operational owners is acceptable."""
    # Two batched queries instead of N+1.
    # Get all operational subs first.
    operational_subs = await self._subscriptions.list_all(
        status=SubStatus.ACTIVE.value, limit=10_000,
    )
    operational_subs += await self._subscriptions.list_all(
        status=SubStatus.TRIALING.value, limit=10_000,
    )
    op_owner_ids = [s.owner_id for s in operational_subs]
    users = await self._users.list_by_ids(op_owner_ids)
    return {u.id for u in users if u.is_active}
```

The handler then calls `resources.list_published(owner_ids_filter=list(op_ids), ...)`.

> **MVP note.** The `limit=10_000` ceiling exists to keep the batch single-call. If owner counts exceed that, the listing handler must paginate operational owners. Spec §10 / out-of-scope: handle this when it bites; for MVP no platform has 10k operational owners.

### 6.5 `PATCH /v1/me/resources/{id}` dispatch design

The route accepts a partial `ResourceUpdateBody`:

```json
{
  "name": "Arena ZL Sub-20",
  "description": "...",
  "city": "São Paulo",
  "region": "SP",
  "base_price_cents": 9000,
  "customer_cancellation_cutoff_hours": 24,
  "base_attributes": {"surface_type": "GRASS"},
  "custom_attributes": [{"key": "wifi", "label": "Wi-Fi", "value": "free"}]
}
```

Each present field maps to a corresponding handler call. The route layer orchestrates:

```python
@router.patch("/me/resources/{resource_id}")
async def patch_resource(
    resource_id: UUID,
    body: ResourceUpdateBody,
    actor: User = Depends(current_owner),
    handlers: ResourceHandlers = Depends(get_resource_handlers),
) -> ResourceResponse:
    if any_metadata_field_present(body):
        unwrap(await handlers.update_metadata.handle(...))
    if body.base_price_cents is not None:
        unwrap(await handlers.set_base_price.handle(...))
    if body.customer_cancellation_cutoff_hours is not None:
        unwrap(await handlers.set_cancellation_cutoff.handle(...))
    if body.base_attributes is not None:
        unwrap(await handlers.replace_base_attributes.handle(...))
    if body.custom_attributes is not None:
        unwrap(await handlers.replace_custom_attributes.handle(...))
    res = unwrap(await handlers.get_my.handle(...))
    return ResourceResponse.from_dto(res)
```

Operating-hours, pricing-rules, slot-duration, and publish/unpublish each get their own dedicated route — they're "heavy" replacements with their own validation re-runs and don't fit the partial-PATCH pattern as cleanly.

**Failure semantics:** the dispatch is sequential. All handlers share the same request-scoped `AsyncSession`; each successful handler call writes to the session in-memory (via `flush`) but does NOT commit. The commit happens at the end of the request lifecycle in the FastAPI dependency. If any handler returns a `Result.failure`, `unwrap` raises an `HTTPException` and the FastAPI session middleware (already wired in by Plan 02) rolls back the entire request's session. Net effect: partial PATCH is **transactional in practice** — either every change in the body commits, or none of them do. No extra savepoint mechanism needed.

## 7. Endpoints + DTOs

### 7.1 Owner routes (`app/api/v1/me_resources/routes.py`)

| Method + Path | Handler |
|---|---|
| `POST /v1/me/resources` | `CreateResourceHandler` |
| `GET /v1/me/resources` | `ListMyResourcesHandler` |
| `GET /v1/me/resources/{id}` | `GetMyResourceHandler` |
| `PATCH /v1/me/resources/{id}` | dispatch (see §6.5) |
| `PATCH /v1/me/resources/{id}/operating-hours` | `ReplaceOperatingHoursHandler` |
| `PATCH /v1/me/resources/{id}/pricing-rules` | `ReplacePricingRulesHandler` |
| `PATCH /v1/me/resources/{id}/slot-duration` | `SetSlotDurationHandler` |
| `POST /v1/me/resources/{id}/publish` | `PublishResourceHandler` |
| `POST /v1/me/resources/{id}/unpublish` | `UnpublishResourceHandler` |
| `DELETE /v1/me/resources/{id}` | `SoftDeleteResourceHandler` |

All routes require OWNER role (via JWT + role check middleware). Returns 200/204 with `ResourceResponse`.

### 7.2 Public routes (`app/api/v1/public_resources/routes.py`)

| Method + Path | Handler |
|---|---|
| `GET /v1/resources` | `ListPublicResourcesHandler` (filters: `type=<resource_type_slug>&city=&region=&page=&page_size=`) |
| `GET /v1/owners/{owner_slug}` | `GetOwnerPublicPageHandler` |
| `GET /v1/owners/{owner_slug}/resources/{resource_slug}` | `GetPublicResourceHandler` |

### 7.3 DTOs

`app/use_cases/resources/dtos.py`:

```python
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
class TimeWindowDto:
    start: str  # "HH:MM"
    end: str

@dataclass(frozen=True, slots=True)
class PricingRuleDto:
    weekdays: list[str]   # Weekday.value
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
    owner_slug: str       # denormalized — joined at handler from User
    resource_type_id: UUID
    resource_type_slug: str  # denormalized — joined at handler from ResourceType
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
    # rating_avg + rating_count are added in Plan 09.

    @classmethod
    def from_entity(
        cls,
        res: Resource,
        *,
        owner_slug: str,
        resource_type_slug: str,
    ) -> Self: ...
```

`PublicResourceDto` is a subset for anonymous endpoints — drops `owner_id` (UUID is internal), `deleted_at`, and any draft-only fields. The list response includes a slimmer `PublicResourceListItemDto` with the most-used fields (id, owner_slug, slug, name, city, region, base_price_cents, resource_type_slug) to keep payload small.

Pydantic response models in `app/api/v1/<resource>/schemas.py` mirror the DTOs.

### 7.4 Pagination

`{items, limit, offset}` envelope, consistent with Plan 04 (`ResourceTypeListResponse`) and Plan 05. Default `limit=50`, max `100`.

## 8. Persistence

### 8.1 Schema

One table, three composites stored as JSONB.

`app/infrastructure/db/mappings/resource.py`:

| Column | Type (Postgres / SQLite) | Notes |
|---|---|---|
| `id` | UUID PK | |
| `owner_id` | UUID FK→users.id ON DELETE RESTRICT | |
| `resource_type_id` | UUID FK→resource_types.id ON DELETE RESTRICT | |
| `slug` | TEXT NOT NULL | |
| `name` | TEXT NOT NULL | |
| `description` | TEXT NOT NULL | (empty string allowed) |
| `city` | TEXT NOT NULL | |
| `region` | TEXT NOT NULL | |
| `timezone` | TEXT NOT NULL | |
| `slot_duration_minutes` | INT NOT NULL | |
| `base_price_cents` | BIGINT NOT NULL | |
| `customer_cancellation_cutoff_hours` | INT NOT NULL | |
| `operating_hours` | JSONB NOT NULL | serialized `WeeklyScheduleDto` shape |
| `pricing_rules` | JSONB NOT NULL | serialized list of `PricingRuleDto` |
| `custom_attributes` | JSONB NOT NULL | serialized list of `CustomAttributeDto` |
| `base_attributes` | JSONB NOT NULL | dict (schema dynamic per ResourceType) |
| `is_published` | BOOLEAN NOT NULL DEFAULT FALSE | |
| `deleted_at` | TIMESTAMPTZ NULL | |
| `created_at` | TIMESTAMPTZ NOT NULL | |
| `updated_at` | TIMESTAMPTZ NOT NULL | |

**Constraints:**

- `UNIQUE(owner_id, slug)` (per-owner slug).
- Index `idx_resources_published` on `(is_published, deleted_at)` for the public listing query.
- Index `idx_resources_owner` on `owner_id` for `list_by_owner` and the owner page.
- Index `idx_resources_type_slug` on `resource_type_id` for filtered public listing.
- FK `owner_id` ON DELETE RESTRICT (users are never hard-deleted per spec).
- FK `resource_type_id` ON DELETE RESTRICT (mirrors Plan 04 invariant).

### 8.2 Repository implementation

`app/infrastructure/repositories/resource_repository.py`:

- Reuse the `_ensure_utc` helper (introduced in `owner_subscription_repository.py` for SQLite tz roundtrips); apply to `deleted_at`, `created_at`, `updated_at` in `_to_entity`.
- `_to_entity` rebuilds composites from JSON: `WeeklySchedule(monday=tuple(TimeWindow(...) for w in json["monday"]), ...)`. Bypasses `WeeklySchedule.create()` validation — trusted reconstitution from DB (DB invariants guarantee correctness).
- `_to_model_kwargs` serializes composites to JSON via `json.dumps`-friendly dicts (`time` → `"HH:MM"` string, `frozenset[Weekday]` → sorted `list[str]`, `Money` → int cents).
- `add` returns `Result.failure("SlugAlreadyTaken", status_code=409)` on `IntegrityError`, mirroring the pattern in `owner_subscription_repository.add`.

### 8.3 Migrations

Two separate migrations for ordering clarity:

1. `make migrate-new msg="users add public_slug"` — adds `public_slug TEXT NULL UNIQUE` to `users`.
2. `make migrate-new msg="resources table"` — creates `resources` with all columns + indexes + constraints.

Both must be added before the repository implementation lands, per the project's TDD-friendly "mappings → migration → repo" cadence.

### 8.4 SQLite tradeoffs

- SQLite stores `JSONB` as `TEXT`; SQLAlchemy `JSON` column type handles dispatch transparently.
- SQLite doesn't index inside JSON; this is fine because all our JSON-typed composites are loaded/written whole.
- `_ensure_utc` already documented as the project pattern (Plan 05).

## 9. Stable error codes

Add to `app/api/error_codes.py` (`ERROR_MESSAGES_PT_BR`):

```python
# Resource aggregate-level
"PricingRulesOverlap": "Regras de preço se sobrepõem.",
"PricingRuleNotAlignedToSlotGrid": "Regra de preço não alinhada à grade de slots.",
"PricingRuleOutsideOperatingHours": "Regra de preço fora do horário de funcionamento.",
"DuplicateCustomAttributeKey": "Atributo customizado duplicado.",
"CustomAttributeKeyConflictsWithBase": "Atributo customizado conflita com atributo base.",
"ResourceAlreadyDeleted": "Recurso já está deletado.",
"ResourceDeletedAtNotTzAware": "Data de exclusão precisa ser tz-aware UTC.",

# Composite VO codes
"WeeklyScheduleWindowsNotOrdered": "Janelas de horário fora de ordem.",
"WeeklyScheduleWindowsOverlap": "Janelas de horário se sobrepõem.",
"WeeklyScheduleWindowNotAlignedToSlotGrid": "Janela de horário não alinhada à grade de slots.",
"PricingRuleEmptyWeekdays": "Regra de preço precisa de pelo menos um dia da semana.",

# Handler-level (resources)
"ResourceNotFound": "Recurso não encontrado.",
"ResourceTypeNotFound": "Tipo de recurso não encontrado.",   # may already exist from Plan 04
"ResourceTypeInactive": "Tipo de recurso está inativo.",
"SlugAlreadyTaken": "Slug já em uso.",

# User extension (accounts)
"PublicSlugRequiredForOwner": "Owner precisa de slug público.",
"PublicSlugForbiddenForNonOwner": "Slug público é exclusivo de owners.",
"PublicSlugAlreadyTaken": "Slug público já em uso.",

# Plan 05 follow-up #5 — RegisterUserHandler raw-pt-BR codes
"AdminRegistrationForbidden": "Não é permitido registrar contas admin via cadastro público.",
"PasswordTooShort": "Senha precisa ter ao menos {min} caracteres.",
"EmailAlreadyRegistered": "Email já cadastrado.",
```

(`PasswordTooShort` keeps the `{min}` placeholder so `error_handler.translate` can interpolate the configured minimum from `Settings`. If the i18n translation layer doesn't yet support param interpolation, either fix that as part of the task or hard-code the current `min=8` in the message — depends on what already exists; the implementation step decides.)

Add **all** of these codes to `handler_level_allowlist` in `tests/unit/architecture/test_error_code_coverage.py` (the arch-test scanner only auto-discovers `BaseValueObject` subclasses; `Resource` extends `BaseEntity`, and handler-level codes need explicit allowlist entries).

## 10. Tests

| Layer | Path | Coverage |
|---|---|---|
| Unit (enum) | `tests/unit/domain/shared/test_weekday.py` | enum values present + serialize. |
| Unit (VO) | `tests/unit/domain/resources/test_weekly_schedule.py` | ordered, no-overlap, slot-aligned per weekday; failure_many aggregation across weekdays; `for_weekday`. |
| Unit (VO) | `tests/unit/domain/resources/test_pricing_rule.py` | empty weekdays; happy path; equality. |
| Unit (VO) | `tests/unit/domain/resources/test_custom_attribute.py` | aggregate errors over key/label/value. |
| Unit (entity) | `tests/unit/domain/resources/test_resource.py` | `create()` happy + each cross-rule failure (pricing overlap, alignment, containment, duplicate custom key, base/custom collision); cross-field invariants in `__post_init__`; mutator `Result[None]` paths; `compute_price` with rule + fallback; soft_delete already-deleted; immutability of owner_id/resource_type_id (no mutator path exposed). |
| Unit (handler) | `tests/unit/use_cases/resources/commands/test_create_resource.py` | aggregates `Resource.create` + `validate_attributes` errors with `base_attributes.<key>` prefix; rejects non-OWNER (404 ResourceTypeNotFound or 403 UserIsNotOwner per route); rejects inactive ResourceType. |
| Unit (handler) | one test file per command handler | 404-on-mismatch ownership; happy paths; soft-deleted resource blocks edits. |
| Unit (handler) | `tests/unit/use_cases/resources/queries/test_list_public_resources.py` | filters by `is_owner_operational` (with fakes returning mixed sub statuses); paginação; combined `type`/`city`/`region` filters. |
| Unit (handler) | `tests/unit/use_cases/accounts/queries/test_get_owner_public_page.py` | 404 when owner not found, role≠OWNER, sub not operational, or user.is_active=False. |
| Unit (handler) | `tests/unit/use_cases/accounts/commands/test_register_user.py` | OWNER registration generates `public_slug`; collision generates `-2` suffix; CUSTOMER registration leaves `public_slug=None`; the new stable codes (`AdminRegistrationForbidden`, `PasswordTooShort`, `EmailAlreadyRegistered`) replace the raw pt-BR strings. |
| Integration | `tests/integration/resources/test_resource_repository.py` | `UNIQUE(owner_id, slug)` constraint; round-trip JSONB for all three composites; `_ensure_utc` on deleted_at; public listing excludes deleted+unpublished+inactive-owner-via-handler. |
| Integration | `tests/integration/accounts/test_user_repository_public_slug.py` | `UNIQUE(public_slug)` allows multiple NULLs; `get_by_public_slug` returns the right user. |
| E2E | `tests/e2e/resources/test_owner_lifecycle.py` | OWNER flow: register → has public_slug → create resource → publish → list em `/v1/resources` → soft-delete → some da lista. |
| E2E | `tests/e2e/resources/test_inactive_owner_filter.py` | Owner com sub INACTIVE: `/v1/resources` exclui resources dele; `/v1/me/resources` ainda lista; admin reativa → resources voltam. |
| E2E | `tests/e2e/resources/test_create_resource_validation_envelope.py` | POST com base_attributes inválidos + slug inválido → 400 com `code: ValidationFailed` e `details` contendo entradas em `slug` e em `base_attributes.<key>`. |

Test fakes:
- `tests/unit/use_cases/resources/fakes/fake_resource_repository.py` — in-memory `IResourceRepository`.
- Reuse `FakeUserRepository` and `FakeSubscriptionRepository` from Plans 02/05.

## 11. Migration order (TDD task sequence)

Each step lands as one (or a few) commits with passing tests before moving on.

1. `Weekday` enum + tests.
2. `WeeklySchedule` VO + tests.
3. `PricingRule` VO + tests.
4. `CustomAttribute` VO + tests.
5. `Resource` aggregate (`create`, mutators, `compute_price`, cross-rule helpers) + tests.
6. `IResourceRepository` Protocol.
7. `User.public_slug` extension: domain field + cross-field invariant + factory + tests.
8. SQLAlchemy mapping `users.public_slug` + migration + integration test.
9. `IUserRepository.get_by_public_slug` + implementation + integration test.
10. SQLAlchemy mapping `resources` + migration.
11. `SQLAlchemyResourceRepository` + integration tests.
12. `RegisterUserHandler` slug generation + tests update.
13. Owner-scoped command handlers (Create + Update variants + SoftDelete) + tests.
14. Owner-scoped query handlers (My + List) + tests.
15. Public query handlers (Get / List / OwnerPage) + tests, including batch operational filter.
16. Routes (`me_resources`, `public_resources`) + e2e tests.
17. Stable codes em `error_codes.py` + arch test allowlist update — for the **Plan 06** codes only (Resource aggregate-level + composite VO + handler-level + User extension). The three Plan 05 follow-up codes are added together with the handler change in task 18, not here, so the arch test stays green at every commit boundary.
18. **Plan 05 follow-up #5** — register codes (`AdminRegistrationForbidden`, `PasswordTooShort`, `EmailAlreadyRegistered`) in `error_codes.py` + arch test allowlist AND switch `RegisterUserHandler:43-59` raw-pt-BR strings to those codes in the same commit; update tests asserting on the new codes.
19. **Plan 05 follow-up #6** — update canonical `2026-04-25-venue-backend-design.md` §5.5 with Plan 05 deltas (drop `notes`, add `trial_ends_at`, mention auto-create on owner registration). Doc-only commit.
20. Final verification: full suite green, `grep "; "` em `app/domain` `app/use_cases` tripwire clean, e2e validation envelope exercised.

## 12. Configuration

No new `Settings` fields. The trial-duration setting (Plan 05) is unchanged.

`_slugify` uses Python stdlib (`unicodedata`); no new dependency.

## 13. Out of scope / Follow-ups (post-merge)

- **Plan 08 booking-aware soft-delete extension.** `SoftDeleteResourceHandler` injects `IBookingRepository`; rejects soft-delete when `APPROVED` future booking exists; auto-rejects `PENDING` bookings on the resource in the same transaction with reason `resource_deleted`.
- **Plan 08 `RequestBookingHandler` integration.** Calls `Resource.compute_price(slot_range)` to freeze the booking total at request time. Plan 08 also enforces the `customer_cancellation_cutoff_hours` invariant at cancel time using the *current* Resource value (per Pergunta 7b decision: cutoff is "policy now", no Booking snapshot).
- **Plan 09 rating aggregation on `ResourceDto`.** `rating_avg` + `rating_count` joined at the handler level when serving owner/public reads.
- **Plan 09 owner public page extension.** Aggregate rating across all of owner's published resources (count-weighted average).
- **Concurrent owner-slug collision.** If real-world contention emerges, switch the linear suffix probe to a ULID-based slug fallback (`{base}-{ulid_short}`).
- **Pagination beyond 10k operational owners.** When the platform exceeds that scale, refactor `ListPublicResourcesHandler` to push the operational filter into SQL (likely via a JOIN against `owner_subscriptions` and `users` rather than the in-memory allow-list).
- **Per-resource hard-delete admin tool.** If a real case arises, add an admin-only handler that hard-deletes a soft-deleted resource and cascades to orphan `Booking` rows. Out of scope for MVP.
