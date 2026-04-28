from __future__ import annotations
from datetime import datetime, timedelta, timezone

import pytest

from app.use_cases.bookings.commands.expire_pending_bookings import (
    ExpirePendingBookingsCommand, ExpirePendingBookingsHandler,
)
from app.infrastructure.notifications.persistent_notification_service import (
    PersistentNotificationService,
)
from app.infrastructure.repositories.booking_repository import (
    SQLAlchemyBookingRepository,
)
from app.infrastructure.repositories.notification_repository import (
    SQLAlchemyNotificationRepository,
)
from tests.e2e.bookings.test_happy_path import (
    _register_owner_with_resource,
    _slot_iso,
)


pytestmark = pytest.mark.asyncio


async def test_inactive_owner_cannot_approve(
    client, admin_token, customer_token,
):
    owner_token, owner_id, resource_id = await _register_owner_with_resource(
        client, admin_token,
    )
    start_iso, end_iso = _slot_iso(days_ahead=2)
    req = await client.post(
        "/v1/me/bookings",
        headers={"Authorization": f"Bearer {customer_token}"},
        json={"resource_id": resource_id, "slot_start_at": start_iso,
              "slot_end_at": end_iso, "customer_note": None},
    )
    assert req.status_code == 201
    booking_id = req.json()["id"]

    set_status = await client.post(
        f"/v1/admin/owners/{owner_id}/subscription",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"status": "INACTIVE"},
    )
    assert set_status.status_code == 200

    approve = await client.post(
        f"/v1/me/bookings/{booking_id}/approve",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert approve.status_code == 403
    assert approve.json()["detail"]["code"] == "OwnerSubscriptionInactive"


async def test_resource_delete_cascades_pendings(
    client, admin_token, customer_token, db_session,
):
    owner_token, owner_id, resource_id = await _register_owner_with_resource(
        client, admin_token,
    )
    start_iso, end_iso = _slot_iso(days_ahead=2)
    req = await client.post(
        "/v1/me/bookings",
        headers={"Authorization": f"Bearer {customer_token}"},
        json={"resource_id": resource_id, "slot_start_at": start_iso,
              "slot_end_at": end_iso, "customer_note": None},
    )
    assert req.status_code == 201
    booking_id = req.json()["id"]

    delete = await client.delete(
        f"/v1/me/resources/{resource_id}",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert delete.status_code == 204, delete.text

    fetched = await client.get(
        f"/v1/me/bookings/{booking_id}",
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert fetched.status_code == 200
    body = fetched.json()
    assert body["status"] == "CANCELLED"
    assert body["status_history"][-1]["reason"] == "resource_deleted"


async def test_cron_expires_past_pendings(
    client, admin_token, customer_token, db_session,
):
    """Inserts a PENDING booking with slot_start_at in the past directly via
    the SQL repo (the API rejects past slots), then runs the handler against
    the same session and verifies transition to EXPIRED."""
    owner_token, _, resource_id = await _register_owner_with_resource(
        client, admin_token,
    )
    from uuid import UUID
    from app.domain.bookings.booking import Booking
    from app.domain.shared.value_objects.date_time_range import DateTimeRange
    from app.domain.shared.value_objects.money import Money

    customer_resp = await client.get(
        "/v1/me", headers={"Authorization": f"Bearer {customer_token}"},
    )
    customer_id = UUID(customer_resp.json()["id"])
    now = datetime.now(timezone.utc)
    past = now - timedelta(hours=2)
    sr = DateTimeRange.create(
        start_at=past, end_at=past + timedelta(hours=1),
    ).value
    repo = SQLAlchemyBookingRepository(db_session)
    booking = Booking.create_pending(
        resource_id=UUID(resource_id),
        customer_id=customer_id,
        slot_range=sr,
        total_price_cents=Money.create(8000).value,
        customer_note=None,
        now=past - timedelta(days=1),
    )
    await repo.add(booking)
    await db_session.commit()

    notifs = PersistentNotificationService(
        SQLAlchemyNotificationRepository(db_session),
    )
    handler = ExpirePendingBookingsHandler(bookings=repo, notifications=notifs)
    r = await handler.handle(ExpirePendingBookingsCommand())
    assert r.is_success
    assert r.value >= 1

    fetched = (await repo.get_by_id(booking.id)).value
    assert fetched.status.value == "EXPIRED"
