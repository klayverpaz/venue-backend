# Plan 09 — Ratings Design Doc

**Status:** Approved 2026-04-28.
**Author:** klayver + Claude (brainstorm session).
**Scope:** Plan 09 of the venue-backend roadmap (`docs/superpowers/specs/2026-04-25-venue-backend-design.md` §8). Refines and extends `Rating` aggregate beyond what §5.7 specified, and retrofits resource listings with the rating aggregates §5.7 promised.

## 1. Motivation

Decisions §3 #18, §3 #19, and §5.7 of the venue spec define ratings: per-booking (one rating per `APPROVED` ended booking), 1–5 score, optional comment, on-the-fly SQL aggregation onto `Resource` GETs. Plan 08 just shipped the `Booking` aggregate (range `c39eb4a..be7adfd`), so APPROVED-and-ended bookings exist as the eligibility gate. Plan 09 closes the loop: customers can rate, the public discovery surface reflects their judgment, owners see the rolled-up `rating_avg`/`rating_count` on their resource listings (no per-rating drill-down owner-side in MVP — see §3.6).

This refinement deviates from canonical §3 #20, §5.7, and §7.5 in two places (both approved during brainstorming):

- **Admin moderation dropped for MVP.** Spec §3 #20 + §5.7 + §7.5 introduced `is_hidden`, `hidden_reason`, `HideRatingHandler`, and three admin endpoints (`GET /admin/ratings`, `POST /hide`, `POST /unhide`). Pre-launch with zero users, the moderation queue would never be exercised; reintroducing it post-volume is a one-column Alembic migration plus one filter clause plus one admin endpoint pair. YAGNI.
- **Rating survives owner-side post-rating cancellation.** Plan 08 lets owners cancel an `APPROVED` booking with no time bound — including a booking whose slot has already ended and which a customer has already rated. The rating stays as-is; the booking's `status_history` documents the cancellation; the public aggregate still includes the rating. Audit-honest, no cascade complexity, low real-world frequency. (Brainstorm option A.)

## 2. Scope

### In scope

- `Rating` aggregate (`app/domain/ratings/rating.py`): factory `create(...)`, mutator `update_text(...)`, no moderation methods.
- `IRatingRepository` Protocol (`app/domain/ratings/repository.py`): `add`, `update`, `get_by_id`, `get_by_booking_id`, `list_by_customer`, `list_with_comment_for_resource`, `get_aggregates_for_resources`.
- Use cases in `app/use_cases/ratings/`:
  - `commands/create_rating.py` → `CreateRatingHandler`
  - `commands/update_rating.py` → `UpdateRatingHandler`
  - `queries/list_my_ratings.py` → `ListMyRatingsHandler` (customer)
  - `queries/list_public_ratings.py` → `ListPublicRatingsForResourceHandler` (public-by-slug pair, comments-only)
- Persistence: `RatingModel` declarative mapping in `app/infrastructure/db/mappings/rating.py`; `ratings` table; Alembic migration. UNIQUE on `booking_id`, b-tree index on `resource_id` for aggregate queries, b-tree index on `(customer_id, created_at DESC)` for "my ratings" pagination. No Postgres-specific extensions.
- API in `app/api/v1/me_ratings/` (customer mutations + reads) and `app/api/v1/public_resources/` extension (public ratings list per resource). Plus retrofits to existing endpoints (see §3.5).
- Resource listing retrofit: `GET /v1/resources` (public list), `GET /v1/resources/{owner_slug}/{resource_slug}` (public detail), `GET /v1/me/resources` (owner list), `GET /v1/me/resources/{id}` (owner detail) all gain `rating_avg` (one decimal, `null` when no ratings) + `rating_count` (int). `GET /v1/owners/{slug}` gains a count-weighted average across the owner's published resources.
- Stable error codes registered in `app/api/error_codes.py` + arch test allowlist + pt-BR translations.
- Test coverage: unit (Rating VO + 4 handlers), integration (SQLAlchemy repo + UNIQUE constraint + aggregate query), e2e (happy path: book → approve → rate → public list reflects → resource agg reflects).
- Canonical spec refresh (`docs/superpowers/specs/2026-04-25-venue-backend-design.md` §3 #20 dropped, §5.7 simplified, §7.1 path aligned to two-slug, §7.5 admin ratings block dropped, §8 Plan 09 description) capturing the dropped moderation decision and the post-rating-cancellation semantics.

### Out of scope

- **Admin moderation infrastructure** (`is_hidden`, `hidden_reason`, `HideRatingHandler`, 3 admin routes, `GET /admin/ratings`).
- **Owner reply / response to a rating.** Spec didn't include it; rating signal flows owner → product, not customer ↔ owner threads.
- **`BOOKING_RATED` notification.** Plan 07 closure already dropped this NotifKind value because owners have no actionable response. Confirmed.
- **Rating analytics** (per-month breakdowns, score distribution histograms, etc.). Future plan, not MVP.
- **Per-rating photo uploads.** No file-upload infrastructure in MVP.
- **Editing a rating after the 7-day window** by any actor. Without moderation, after 7 days the rating is immutable.
- **Cascading rating deletion when booking soft-deletes.** Bookings have `ON DELETE RESTRICT` to `users` and `resources`; ratings will have `ON DELETE RESTRICT` to `bookings`/`users`/`resources`. No soft-delete on rating rows.

## 3. Design

### 3.1 `RatingScore` VO

Already exists in Plan 03's `app/domain/shared/value_objects/`. `int ∈ {1, 2, 3, 4, 5}`. No work in this plan.

### 3.2 `Rating` aggregate

```
Rating(BaseEntity)
├── id: UUID                      # inherited
├── booking_id: UUID
├── resource_id: UUID             # denormalized (matches booking.resource_id)
├── customer_id: UUID             # denormalized (matches booking.customer_id)
├── score: RatingScore
├── comment: ShortDescription | None
└── created_at, updated_at        # inherited
```

**Factory** `Rating.create(*, booking_id, resource_id, customer_id, score, comment, now) -> Rating`. Pure construction; all eligibility validation lives in `CreateRatingHandler` because it requires `Booking` context. Sets `created_at = updated_at = now`.

**Mutator** `Rating.update_text(*, score, comment, now) -> None`. Updates score (required) and comment (optional). Bumps `updated_at` to `now`. No failure mode at the aggregate level — both inputs arrive as already-validated VOs; the 7-day window check lives in `UpdateRatingHandler` because it requires comparing against `created_at` and `now()`.

No moderation mutators. No `hide()`/`unhide()`. No `is_hidden` field.

### 3.3 `IRatingRepository` Protocol

```python
class IRatingRepository(Protocol):
    """Persistence port for the ratings feature."""

    async def add(self, rating: Rating) -> Result[None]:
        ...

    async def update(self, rating: Rating) -> Result[None]:
        """Persists score/comment changes. Returns RatingNotFound if id absent."""
        ...

    async def get_by_id(self, rating_id: UUID) -> Result[Rating | None]:
        ...

    async def get_by_booking_id(self, booking_id: UUID) -> Result[Rating | None]:
        """Used by CreateRatingHandler for the dedup check + by route layer
        when redirecting from a booking detail to its rating."""
        ...

    async def list_by_customer(
        self,
        customer_id: UUID,
        *,
        page: int,
        page_size: int,
    ) -> Result[list[Rating]]:
        """Customer's own ratings, newest first. Used by GET /v1/me/ratings."""
        ...

    async def list_with_comment_for_resource(
        self,
        resource_id: UUID,
        *,
        page: int,
        page_size: int,
    ) -> Result[list[Rating]]:
        """Public listing — only ratings whose comment is non-NULL.
        Newest first."""
        ...

    async def get_aggregates_for_resources(
        self,
        resource_ids: list[UUID],
    ) -> Result[dict[UUID, RatingAggregate]]:
        """Batch aggregate. For each resource_id provided, returns the
        (avg_score, count) pair. Resources with zero ratings are present
        in the dict with (None, 0). Used by every resource listing/detail
        endpoint to avoid N+1."""
        ...
```

`RatingAggregate` is a small frozen dataclass (`avg_score: Decimal | None`, `count: int`), defined in `app/domain/ratings/aggregate.py` so both domain (handler responses) and infra (the SQL `SELECT AVG, COUNT GROUP BY resource_id`) can reference it.

### 3.4 Use cases

| Handler | Inputs | Behavior |
|---|---|---|
| `CreateRatingHandler` | `IRatingRepository`, `IBookingRepository`, `clock` | Loads booking by id. Validates: booking exists; `customer_id == actor_id`; `status == APPROVED`; `slot_range.end_at < now`; `now ≤ slot_range.end_at + 90 days`; no rating exists for this booking. Persists rating; returns DTO. Errors: `BookingNotFound` (404, no leak), `BookingNotEligibleForRating` (422, covers status/end_at/customer mismatch/past 90d), `RatingAlreadyExists` (409). |
| `UpdateRatingHandler` | `IRatingRepository`, `clock` | Loads rating by id. Validates: `customer_id == actor_id`; `now ≤ created_at + 7 days`. Mutates score/comment. Errors: `RatingNotFound` (404, also when actor mismatch — no leak), `RatingEditWindowExpired` (403). |
| `ListMyRatingsHandler` | `IRatingRepository` | Pagination (page ≥ 1; page_size ∈ [1, 100], default 50). Returns `RatingListDto`. |
| `ListPublicRatingsForResourceHandler` | `IRatingRepository`, `IResourceRepository` | Resolves resource by `(owner_slug, resource_slug)` — returns `ResourceNotFound` (404) if missing or soft-deleted. Lists rating rows with non-empty comment, paginated. Returns `PublicRatingListDto` (no `customer_id` in DTO — privacy; see §3.7). |

`CreateRatingHandler` and `UpdateRatingHandler` take a `clock: Callable[[], datetime] = _utcnow` constructor arg per the Plan 08 polish pattern (avoids date-driven test brittleness).

`CreateRatingHandler` does NOT acquire a lock. The `booking_id` UNIQUE constraint at the DB layer handles the "two concurrent rates on the same booking" race deterministically: one wins, the other's `INSERT` raises `IntegrityError`, repository translates to `RatingAlreadyExists`. No advisory lock needed because there's only one customer per booking.

### 3.5 Resource listing retrofit

Every endpoint that returns a `Resource` (or list) gets `rating_avg` + `rating_count`. Implementation pattern:

1. Resource handler loads resources as today (`Resource` aggregate, no rating fields).
2. Handler calls `IRatingRepository.get_aggregates_for_resources(ids)` once for the page (or `[id]` for detail).
3. Resource DTO grows two optional fields:
   - `rating_avg: Decimal | None` — `null` when zero ratings; otherwise rounded to one decimal (e.g. `4.3`).
   - `rating_count: int` — always present, `0` when no ratings.
4. Public response schema serializes `Decimal` as a number (`4.3`, not `"4.3"`).

For `GET /v1/owners/{slug}` (the public owner page): handler loads the owner's published resources; calls `get_aggregates_for_resources` for the page; computes a count-weighted average across all aggregates: `weighted_avg = sum(avg_i * count_i for i in resources) / sum(count_i for i in resources)`. If `sum(count_i) == 0`, result is `null`. The response includes the per-resource breakdown the endpoint already returns plus the new rolled-up `owner_rating_avg`/`owner_rating_count`.

Endpoints retrofitted (the implementation plan will confirm which already exist in Plan 06's surface and which are new this round):
- `GET /v1/resources` (public list)
- `GET /v1/resources/{owner_slug}/{resource_slug}` (public detail)
- `GET /v1/me/resources` (owner's list)
- `GET /v1/me/resources/{id}` (owner detail)
- `GET /v1/owners/{slug}` (public owner page)

`GET /v1/me/resources/{id}/agenda` and `GET /v1/resources/{owner_slug}/{resource_slug}/agenda` are NOT retrofitted — agenda responses are slot grids, not resource details.

### 3.6 API surface

**Customer:**
```
POST   /v1/me/bookings/{booking_id}/rating       # body: { score, comment? }
PATCH  /v1/me/bookings/{booking_id}/rating       # body: { score?, comment? }
GET    /v1/me/ratings?page=&page_size=
```

**Public:**
```
GET    /v1/owners/{owner_slug}/resources/{resource_slug}/ratings?page=&page_size=
```

The path mirrors the existing public resource detail endpoint `GET /v1/owners/{owner_slug}/resources/{resource_slug}` (Plan 06's owners-prefixed style). The single-slug form §7.1 originally specified is dropped in the spec refresh. Plan 08's agenda endpoint uses a different prefix (`/v1/resources/{owner_slug}/{resource_slug}/agenda`); aligning that to the owners-prefix is out of scope for Plan 09 and tracked in the polish backlog.

**Removed compared to canonical §7:**
- `GET /v1/admin/ratings?hidden=&resource_id=` — moderation dropped.
- `POST /v1/admin/ratings/{id}/hide` — moderation dropped.
- `POST /v1/admin/ratings/{id}/unhide` — moderation dropped.
- `GET /v1/me/resources/{id}/ratings` — owner read of their own resource's ratings is **dropped from MVP**. The owner already sees `rating_avg`/`rating_count` on the resource detail; per-rating drill-down with comments is unnecessary owner-side polish. Reintroducible later if owner feedback demands it. (This trims the §7.4 owner block by one route.)

### 3.7 Privacy: customer identity in public ratings

The public ratings list (`GET /v1/owners/{owner_slug}/resources/{resource_slug}/ratings`) returns `RatingResponseDto` which **omits `customer_id`** and only includes `score`, `comment`, `created_at`. The resource owner viewing aggregates also doesn't get per-customer attribution at the resource level (no owner read endpoint in MVP). Customers reviewing their own ratings (`GET /v1/me/ratings`) see their own `customer_id` echoed back (or it can be omitted — equivalent since they're the only customer in the response).

Internal DB and admin DB pokes always preserve `customer_id` for compliance / future moderation.

### 3.8 Persistence shape

`ratings` table:

| Column | Type | Constraint |
|---|---|---|
| `id` | `CHAR(36)` | PK |
| `booking_id` | `CHAR(36)` | FK → `bookings.id` ON DELETE RESTRICT, **UNIQUE** |
| `resource_id` | `CHAR(36)` | FK → `resources.id` ON DELETE RESTRICT |
| `customer_id` | `CHAR(36)` | FK → `users.id` ON DELETE RESTRICT |
| `score` | `INTEGER` | CHECK (1 ≤ score ≤ 5) — domain VO enforces, DB belt-and-suspenders |
| `comment` | `TEXT` | nullable |
| `created_at`, `updated_at` | `TIMESTAMPTZ` | NOT NULL |

Indexes:
- UNIQUE on `booking_id` (already implied by the constraint).
- `idx_ratings_resource` on `(resource_id)` — supports `get_aggregates_for_resources` and `list_with_comment_for_resource`.
- `idx_ratings_customer_created_desc` on `(customer_id, created_at DESC)` — supports `list_by_customer` pagination.

No partial indexes, no Postgres extensions, no exclusion constraints.

### 3.9 Stable error codes

Four new codes registered in `app/api/error_codes.py` + handler-level allowlist:

| Code | HTTP | Used by |
|---|---|---|
| `RatingNotFound` | 404 | `UpdateRatingHandler` (also masks customer-mismatch) |
| `RatingAlreadyExists` | 409 | `CreateRatingHandler` |
| `BookingNotEligibleForRating` | 422 | `CreateRatingHandler` (covers booking missing, status, end_at, customer mismatch, past 90d window — single code with `details` if multi-error envelope helps) |
| `RatingEditWindowExpired` | 403 | `UpdateRatingHandler` |

The aggregate `BookingNotEligibleForRating` deliberately collapses several validation failures behind one code rather than fragmenting (`BookingNotApproved`, `BookingSlotNotEnded`, `BookingNotOwnedByCustomer`, `RatingWindowExpired`). The frontend cannot meaningfully distinguish them — every case maps to "you can't rate this booking" — and the `details` field carries the specific reason for logging if needed. This matches Plan 06's approach with `ResourceNotFound` masking ownership mismatches.

## 4. Concurrency

No advisory locks. The DB-level UNIQUE on `booking_id` is the only race protection needed:
- Two clients submit `POST /v1/me/bookings/{booking_id}/rating` simultaneously → both pass the handler-level dedup check (race window) → first `INSERT` succeeds, second `INSERT` raises `IntegrityError` on the UNIQUE constraint → `SQLAlchemyRatingRepository.add` translates to `Result.failure("RatingAlreadyExists", status_code=409)`.

The customer is the same across both requests (auth subject), so this is a self-conflict — duplicate `POST` from a double-clicked submit button, basically. Same shape as Plan 08's natural-dedup, simpler in implementation.

## 5. Tests

### Unit (~12 tests)

- `Rating.create` — happy path, invariant on score, comment optional.
- `Rating.update_text` — happy path, mutates score+comment, bumps `updated_at`.
- `CreateRatingHandler` — happy path; missing booking → `BookingNotFound`; wrong customer → `BookingNotEligibleForRating`; PENDING booking → ineligible; future slot_end_at → ineligible; >90 days past → ineligible; rating already exists → `RatingAlreadyExists`.
- `UpdateRatingHandler` — happy path within 7d; >7d → `RatingEditWindowExpired`; wrong customer → `RatingNotFound`.
- `ListMyRatingsHandler` — pagination clamp to [1, 100].
- `ListPublicRatingsForResourceHandler` — slug resolution; soft-deleted resource → `ResourceNotFound`; comment-empty rows excluded.

### Integration (~5 tests)

- `SQLAlchemyRatingRepository.add` + `get_by_booking_id` round-trip.
- UNIQUE on `booking_id` rejects duplicate insert with `IntegrityError`.
- `list_with_comment_for_resource` excludes rows where `comment IS NULL`.
- `list_by_customer` orders by `created_at DESC`.
- `get_aggregates_for_resources` — multiple resources, with/without ratings, returns full coverage map (zero-rating resources present with `(None, 0)`).

### E2E (~5 tests)

- Happy path: register customer/owner, owner creates+publishes resource, customer requests booking, owner approves, time-warp slot to past via direct DB poke, customer rates, public list reflects, public resource detail's `rating_avg`/`rating_count` reflects, owner's `GET /v1/me/resources/{id}` reflects.
- Cannot rate before slot ends.
- Cannot rate someone else's booking.
- Update within 7d works; "after 7d" simulated via direct `created_at` poke → 403.
- Public ratings list pagination + comment-only filter.

Total target: ~600 + 22 = ~622 tests at Plan 09 close.

## 6. Plan ordering

The implementation plan (`docs/superpowers/plans/2026-04-28-plan-09-ratings.md`) will follow the sequencing pattern Plans 06–08 established: domain → infrastructure → use cases → API → e2e → canonical spec refresh.

Estimated task count: **~14 tasks**. Concretely:

1. `RatingAggregate` value type + `Rating` aggregate (entity).
2. `IRatingRepository` Protocol.
3. `RatingModel` SQLAlchemy mapping + Alembic migration registration.
4. Alembic migration file.
5. `SQLAlchemyRatingRepository` + integration tests.
6. Use case DTOs (`RatingDto`, `RatingListDto`, `PublicRatingListDto`).
7. `InMemoryRatingRepository` test fake.
8. `CreateRatingHandler` + tests.
9. `UpdateRatingHandler` + tests.
10. `ListMyRatingsHandler` + `ListPublicRatingsForResourceHandler` + tests.
11. Resource listing retrofit (DTOs + handlers + 4-5 endpoints get aggregates merged in).
12. API schemas + routes for the 4 ratings endpoints.
13. Stable error codes registration.
14. E2E tests + canonical spec refresh.

Smaller than Plan 08 (32 tasks) for the reasons captured in §1: no concurrency primitives beyond a UNIQUE constraint, no cron, no cross-feature cascade, fewer handlers, and the moderation cut.

## 7. Spec refresh impact

The implementation plan's last task will refresh `docs/superpowers/specs/2026-04-25-venue-backend-design.md`:

- **§3 #20** — drop entirely (admin moderation removed from MVP).
- **§5.7** — drop `is_hidden`/`hidden_reason` fields, drop the moderation invariants and the `WHERE is_hidden = FALSE` clause from the aggregation snippet, add a "Plan 09 deliberate cuts" callout.
- **§7.1** — change `GET /resources/{slug}/ratings` to `GET /resources/{owner_slug}/{resource_slug}/ratings` (matches the Plan 08 agenda precedent).
- **§7.4** — drop `GET /me/resources/{id}/ratings` (owner per-resource ratings list out of MVP).
- **§7.5** — drop the entire "Ratings (moderation)" block (3 endpoints).
- **§4.2** — drop `HideRatingHandler` row.
- **§8** — refresh Plan 09 description with what actually shipped (no moderation, retrofit count, route count).

## 8. Open questions resolved during brainstorm

- **Owner cancels APPROVED post-rating:** Rating stays as-is (option A). Locked.
- **Admin moderation:** Dropped for MVP. Locked.
- **Customer rating list with hidden flag:** Moot (no moderation).
- **Hide/unhide reason persistence:** Moot (no moderation).
- **Aggregation pattern:** Batch via `get_aggregates_for_resources(ids)` to avoid N+1, single roundtrip per page.
- **Public ratings path:** Two-slug `{owner_slug}/{resource_slug}` matching Plan 08 agenda.
- **Owner per-resource ratings list:** Dropped from MVP scope.

---

End of design doc. Implementation plan to follow at `docs/superpowers/plans/2026-04-28-plan-09-ratings.md`.
