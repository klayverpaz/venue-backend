# Opportunities — deferred features and how they'd plug in

This file captures everything we deferred from the MVP design (`docs/superpowers/specs/2026-04-25-venue-backend-design.md`). Each item lists: the feature, why it was deferred, and a sketch of how it integrates into the existing model when revived.

---

## 1. In-platform booking payments

**What.** Customer pays through the platform at booking-request or approval time. Refunds on cancellation. Optional marketplace commission split for the platform.

**Why deferred.** Largest single scope add in the system. PSP integration (Stripe, Mercado Pago, PIX), webhook handling, refund flow, dispute states, KYC for owners, escrow concerns. Easily doubles the project. Not needed for the MVP because owners are happy to settle off-platform.

**Integration sketch.**
- Add a `payments` feature with `Payment` aggregate referenced by `booking_id`. State machine: `PENDING → AUTHORIZED → CAPTURED → REFUNDED | FAILED`.
- Add `Booking.payment_status: PaymentStatus | None`. `None` means "off-platform" (current default).
- Port `IPaymentProvider` in `domain/payments/`, with adapters in `infrastructure/payments/stripe.py`, `mercadopago.py`, `pix.py`.
- Webhook route under `/api/v1/payments/webhooks/{provider}` that flips `Payment.status` and notifies the booking handlers.
- Cancellation handlers gain a "refund-if-captured" branch.

## 2. Self-serve owner subscription with PSP

**What.** Owners pay a monthly subscription via Stripe / Mercado Pago. Webhook updates `OwnerSubscription.status`. Dunning when payment fails.

**Why deferred.** The MVP gates owner operation by `OwnerSubscription.status` already. The MVP just has Admin set status manually. Swapping in real billing doesn't touch the gating logic — it touches how the status field changes.

**Integration sketch.**
- Add `infrastructure/billing/` with adapter for the chosen PSP.
- New webhook route: subscription events flip `OwnerSubscription.status`.
- New handler `SyncSubscriptionFromProviderHandler` consumed by webhook.
- `SetOwnerSubscriptionStatusHandler` gains a `source: ADMIN | WEBHOOK` field for audit.
- Optional self-serve onboarding flow under `/me/subscription/checkout`.

## 3. Tiered subscription plans

**What.** Free / Pro / Enterprise tiers with per-tier limits (e.g., free = 1 resource max, pro = unlimited).

**Why deferred.** Premature without traction; you don't know what to gate yet.

**Integration sketch.**
- Extend `OwnerSubscription` with `plan_id` and `Plan` aggregate (admin-managed in `subscriptions/` or a new `billing` feature).
- Add a `PlanLimits` value object (`max_resources`, `max_bookings_per_month`, etc.).
- Resource creation handler injects `ISubscriptionRepository` and rejects when limit reached.

## 4. Per-slot price overrides

**What.** Owner overrides the default pricing on specific slots (e.g., a holiday, a tournament, a one-off discount).

**Why deferred.** The day/time-of-week pricing rules cover ~95% of real cases. Overrides add a UX surface (per-slot edit UI) and conflict-resolution logic.

**Integration sketch.**
- New entity inside `Resource` aggregate: `PriceOverride { date, slot_index, price_cents, reason }`.
- `Resource.compute_price(slot_range)` checks overrides before applying `pricing_rules`.
- API: `PATCH /me/resources/{id}/price-overrides`.

## 5. Full marketplace discovery

**What.** Map view, geosearch by radius, ratings, sort by price/popularity, recommendations.

**Why deferred.** Owners drive their own traffic via social. Discovery is a "we have a marketplace" feature, not a "we have rental software" feature. Wait for traction.

**Integration sketch.**
- Add `latitude`, `longitude` to `Resource` (already have city/region).
- New read-side query module under `use_cases/discovery/queries/` (Q anêmico, per Recipe D in template-customization.md).
- Postgres `cube` + `earthdistance` extensions or PostGIS for geosearch.
- Add `Review` aggregate in a new `reviews` feature, referenced by `booking_id` (only customers with completed bookings can review).

## 6. WhatsApp / SMS notifications

**What.** A WhatsApp Business API or SMS provider behind the existing `IEmailSender`-style port.

**Why deferred.** Email + in-app is enough for MVP. WhatsApp Business API has cost, approval cycles, and template approval per message kind.

**Integration sketch.**
- Generalize `IEmailSender` to `INotificationChannel` with implementations for email and WhatsApp.
- `NotificationService` fans out to all enabled channels per recipient preference.
- `User` gains `notification_preferences: { email: bool, whatsapp: bool }`.

## 7. Auto-confirm trusted customers

**What.** Per-resource allowlist of customers whose bookings auto-approve, bypassing the owner's approval queue.

**Why deferred.** Niche; comes from owner feedback after the platform is in use.

**Integration sketch.**
- Add `Resource.trusted_customer_ids: set[UUID]`.
- `RequestBookingHandler` checks the allowlist and goes directly to `APPROVED` if present (still runs the auto-rejection of competing pendings).

## 8. Slot-time reminders and no-show flagging

**What.** Send reminders to both parties N hours before slot start. Allow owner to mark a booking as `NO_SHOW` after slot end.

**Why deferred.** Pure addition, no architectural impact.

**Integration sketch.**
- New cron jobs alongside `ExpirePendingBookings`: `SendBookingReminders`.
- Add `NO_SHOW` to `BookingStatus` enum (terminal). New handler `MarkBookingNoShowHandler`.

## 9. Resource-level schedule exceptions / holidays

**What.** Owner marks a date or date range as "closed" overriding `WeeklySchedule`.

**Why deferred.** Modeling cost vs. how rarely owners need it; for now they can simply reject incoming requests on those dates.

**Integration sketch.**
- New VO `ScheduleException { date_range: DateRange, reason: str }` inside `Resource`.
- `Resource.compute_slots(date)` and `Booking` validation skip excepted dates.

## 10. Reviews and ratings

**What.** Customer reviews owner / resource after a completed booking; aggregate rating displayed on listing.

**Why deferred.** Marketplace-tier feature. Tied to discovery (#5). Also requires moderation tooling.

**Integration sketch.**
- New `reviews` feature with `Review` aggregate.
- One-to-one with `Booking` where `status == APPROVED` and `slot_range.end_at < now`.
- Aggregate rating cached on `Resource` (denormalized; updated by an event handler when a review is created/updated).

## 11. Analytics / Reports module from template

**What.** The template ships a `reports/` analytics module (Recipe D pattern: `Q anêmico`, no `domain/` folder). MVP doesn't include it but template Recipe B keeps it removable.

**Why deferred.** No dashboard requirements yet.

**Integration sketch.**
- Re-add per Recipe D in `docs/template-customization.md`. First reports likely: bookings per resource per month, revenue per owner per month, peak-hours utilization.
