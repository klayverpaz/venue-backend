import pytest

from app.use_cases.resources.commands.soft_delete_resource import (
    SoftDeleteResourceCommand, SoftDeleteResourceHandler,
)
from tests.unit.use_cases.bookings.fakes.in_memory_booking_repository import (
    InMemoryBookingRepository,
)
from tests.unit.use_cases.resources.fakes.in_memory_resource_repository import InMemoryResourceRepository
from tests.unit.use_cases.resources.fixtures import seed_resource
from tests.unit.use_cases.subscriptions.fakes.fake_notification_service import (
    FakeNotificationService,
)


def _build_owned_resource():
    """Return (resource, InMemoryResourceRepository) with the resource pre-seeded."""
    import asyncio
    repo = InMemoryResourceRepository()
    res, _, _ = asyncio.get_event_loop().run_until_complete(seed_resource(repo))
    return res, repo


@pytest.mark.asyncio
async def test_soft_delete_happy():
    repo = InMemoryResourceRepository()
    res, _, _ = await seed_resource(repo)
    handler = SoftDeleteResourceHandler(
        resources=repo,
        bookings=InMemoryBookingRepository(),
        notifications=FakeNotificationService(),
    )
    r = await handler.handle(SoftDeleteResourceCommand(
        actor_id=res.owner_id, resource_id=res.id,
    ))
    assert r.is_success
    r2 = await handler.handle(SoftDeleteResourceCommand(
        actor_id=res.owner_id, resource_id=res.id,
    ))
    assert r2.is_failure
    assert r2.error == "ResourceNotFound"


# --- Plan 08 cascade tests ---

from app.domain.bookings.booking import Booking
from app.domain.bookings.booking_status import BookingStatus
from app.domain.notifications.service import NotifKind
from app.domain.shared.value_objects.date_time_range import DateTimeRange
from app.domain.shared.value_objects.money import Money


def _build_pending_booking(*, resource_id, days_ahead=2):
    from datetime import datetime, timedelta, timezone
    from uuid import uuid4
    now = datetime(2026, 4, 27, 12, 0, 0, tzinfo=timezone.utc)
    sr = DateTimeRange.create(
        start_at=now + timedelta(days=days_ahead),
        end_at=now + timedelta(days=days_ahead, hours=1),
    ).value
    return Booking.create_pending(
        resource_id=resource_id, customer_id=uuid4(), slot_range=sr,
        total_price_cents=Money.create(8000).value,
        customer_note=None, now=now,
    )


@pytest.mark.asyncio
async def test_cascade_cancels_pending_bookings_and_notifies():
    from uuid import uuid4

    repo = InMemoryResourceRepository()
    res, _, _ = await seed_resource(repo)
    owner_id = res.owner_id

    bookings_repo = InMemoryBookingRepository()
    notifs = FakeNotificationService()
    pending_a = _build_pending_booking(resource_id=res.id)
    pending_b = _build_pending_booking(resource_id=res.id)
    other = _build_pending_booking(resource_id=uuid4())
    await bookings_repo.add(pending_a)
    await bookings_repo.add(pending_b)
    await bookings_repo.add(other)

    handler = SoftDeleteResourceHandler(
        resources=repo,
        bookings=bookings_repo,
        notifications=notifs,
    )
    r = await handler.handle(SoftDeleteResourceCommand(
        actor_id=owner_id, resource_id=res.id,
    ))
    assert r.is_success

    a_after = (await bookings_repo.get_by_id(pending_a.id)).value
    b_after = (await bookings_repo.get_by_id(pending_b.id)).value
    other_after = (await bookings_repo.get_by_id(other.id)).value
    assert a_after.status is BookingStatus.CANCELLED
    assert b_after.status is BookingStatus.CANCELLED
    assert other_after.status is BookingStatus.PENDING
    cancellations = [c for c in notifs.calls if c[1] is NotifKind.BOOKING_CANCELLED]
    recipients = {c[0] for c in cancellations}
    assert recipients == {pending_a.customer_id, pending_b.customer_id}
    for c in cancellations:
        assert c[2]["cancelled_by"] == "owner"
        assert c[2]["reason"] == "resource_deleted"


@pytest.mark.asyncio
async def test_blocks_when_future_approved_bookings_exist():
    from uuid import uuid4

    repo = InMemoryResourceRepository()
    res, _, _ = await seed_resource(repo)
    owner_id = res.owner_id

    bookings_repo = InMemoryBookingRepository()
    notifs = FakeNotificationService()
    approved_future = _build_pending_booking(resource_id=res.id, days_ahead=5)
    approved_future.approve(actor_id=owner_id, now=approved_future.created_at)
    await bookings_repo.add(approved_future)

    handler = SoftDeleteResourceHandler(
        resources=repo,
        bookings=bookings_repo,
        notifications=notifs,
    )
    r = await handler.handle(SoftDeleteResourceCommand(
        actor_id=owner_id, resource_id=res.id,
    ))
    assert r.is_failure
    assert r.error == "ResourceHasFutureApprovedBookings"
    assert r.status_code == 409
