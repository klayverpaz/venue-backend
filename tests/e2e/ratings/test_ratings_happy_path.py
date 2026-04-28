from __future__ import annotations
from datetime import datetime, timedelta, timezone
from urllib.parse import quote
from uuid import UUID, uuid4

import pytest

from app.domain.bookings.booking import Booking
from app.domain.bookings.booking_status import BookingStatus
from app.domain.shared.value_objects.date_time_range import DateTimeRange
from app.domain.shared.value_objects.money import Money
from app.infrastructure.repositories.booking_repository import (
    SQLAlchemyBookingRepository,
)
# Reuse the helper from Plan 08 e2e:
from tests.e2e.bookings.test_happy_path import (
    _register_owner_with_resource,
)


pytestmark = pytest.mark.asyncio


def _q(dt: datetime) -> str:
    """URL-encode datetime for query params (Plan 08 task 31 fix)."""
    return quote(dt.isoformat(), safe="")


async def _seed_approved_ended_booking(
    db_session, *, resource_id: str, customer_id: UUID,
) -> UUID:
    """Insert an APPROVED booking whose slot already ended (bypasses the
    request-API's future-only check). Returns the booking.id."""
    now = datetime.now(timezone.utc)
    end = now - timedelta(hours=1)
    start = end - timedelta(hours=1)
    sr = DateTimeRange.create(start_at=start, end_at=end).value
    b = Booking.create_pending(
        resource_id=UUID(resource_id), customer_id=customer_id,
        slot_range=sr, total_price_cents=Money.create(8000).value,
        customer_note=None, now=start - timedelta(days=1),
    )
    b.approve(actor_id=uuid4(), now=start - timedelta(days=1))
    repo = SQLAlchemyBookingRepository(db_session)
    await repo.add(b)
    await db_session.commit()
    return b.id


async def test_happy_path_rate_appears_in_listings(
    client, admin_token, customer_token, db_session,
):
    owner_token, owner_id, resource_id = await _register_owner_with_resource(
        client, admin_token,
    )
    me_resp = await client.get(
        "/v1/me", headers={"Authorization": f"Bearer {customer_token}"},
    )
    customer_id = UUID(me_resp.json()["id"])
    booking_id = await _seed_approved_ended_booking(
        db_session, resource_id=resource_id, customer_id=customer_id,
    )

    # 1. Customer creates a rating.
    create = await client.post(
        f"/v1/me/bookings/{booking_id}/rating",
        headers={"Authorization": f"Bearer {customer_token}"},
        json={"score": 5, "comment": "ótimo lugar"},
    )
    assert create.status_code == 201, create.text
    body = create.json()
    assert body["score"] == 5
    assert body["comment"] == "ótimo lugar"

    # 2. Customer's /me/ratings includes it.
    mine = await client.get(
        "/v1/me/ratings",
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert mine.status_code == 200
    items = mine.json()["items"]
    assert any(it["score"] == 5 and it["comment"] == "ótimo lugar" for it in items)

    # 3. Public ratings listing for the resource includes it.
    listing = await client.get("/v1/resources")
    target = next(
        (i for i in listing.json()["items"] if i["id"] == resource_id),
        None,
    )
    assert target is not None
    owner_slug = target["owner_slug"]
    resource_slug = target["slug"]

    pub = await client.get(
        f"/v1/owners/{owner_slug}/resources/{resource_slug}/ratings",
    )
    assert pub.status_code == 200
    pub_items = pub.json()["items"]
    assert len(pub_items) == 1
    assert pub_items[0]["score"] == 5
    assert pub_items[0]["comment"] == "ótimo lugar"
    # Privacy: public response must NOT carry customer_id or booking_id.
    assert "customer_id" not in pub_items[0]
    assert "booking_id" not in pub_items[0]

    # 4. Public resource list reflects rating_avg + rating_count.
    listing_after = await client.get("/v1/resources")
    target_after = next(
        (i for i in listing_after.json()["items"] if i["id"] == resource_id),
        None,
    )
    assert target_after is not None
    assert target_after["rating_count"] == 1
    assert target_after["rating_avg"] == 5.0
    assert isinstance(target_after["rating_avg"], (int, float))

    # 5. Customer updates the rating.
    upd = await client.patch(
        f"/v1/me/bookings/{booking_id}/rating",
        headers={"Authorization": f"Bearer {customer_token}"},
        json={"score": 4, "comment": "bom"},
    )
    assert upd.status_code == 200
    assert upd.json()["score"] == 4

    # 6. Public list reflects update.
    pub2 = await client.get(
        f"/v1/owners/{owner_slug}/resources/{resource_slug}/ratings",
    )
    assert pub2.json()["items"][0]["score"] == 4


async def test_cannot_rate_pending_booking(
    client, admin_token, customer_token, db_session,
):
    """Booking still PENDING → 422 BookingNotEligibleForRating."""
    owner_token, _, resource_id = await _register_owner_with_resource(
        client, admin_token,
    )
    me_resp = await client.get(
        "/v1/me", headers={"Authorization": f"Bearer {customer_token}"},
    )
    customer_id = UUID(me_resp.json()["id"])
    now = datetime.now(timezone.utc)
    end = now - timedelta(hours=1)
    start = end - timedelta(hours=1)
    sr = DateTimeRange.create(start_at=start, end_at=end).value
    b = Booking.create_pending(
        resource_id=UUID(resource_id), customer_id=customer_id,
        slot_range=sr, total_price_cents=Money.create(8000).value,
        customer_note=None, now=start - timedelta(days=1),
    )
    repo = SQLAlchemyBookingRepository(db_session)
    await repo.add(b)
    await db_session.commit()

    r = await client.post(
        f"/v1/me/bookings/{b.id}/rating",
        headers={"Authorization": f"Bearer {customer_token}"},
        json={"score": 5},
    )
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "BookingNotEligibleForRating"


async def test_cannot_rate_someone_elses_booking(
    client, admin_token, customer_token, db_session,
):
    owner_token, _, resource_id = await _register_owner_with_resource(
        client, admin_token,
    )
    booking_id = await _seed_approved_ended_booking(
        db_session, resource_id=resource_id, customer_id=uuid4(),
    )
    r = await client.post(
        f"/v1/me/bookings/{booking_id}/rating",
        headers={"Authorization": f"Bearer {customer_token}"},
        json={"score": 5},
    )
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "BookingNotEligibleForRating"


async def test_double_rate_returns_409(
    client, admin_token, customer_token, db_session,
):
    owner_token, _, resource_id = await _register_owner_with_resource(
        client, admin_token,
    )
    me_resp = await client.get(
        "/v1/me", headers={"Authorization": f"Bearer {customer_token}"},
    )
    customer_id = UUID(me_resp.json()["id"])
    booking_id = await _seed_approved_ended_booking(
        db_session, resource_id=resource_id, customer_id=customer_id,
    )

    first = await client.post(
        f"/v1/me/bookings/{booking_id}/rating",
        headers={"Authorization": f"Bearer {customer_token}"},
        json={"score": 5},
    )
    assert first.status_code == 201
    second = await client.post(
        f"/v1/me/bookings/{booking_id}/rating",
        headers={"Authorization": f"Bearer {customer_token}"},
        json={"score": 4},
    )
    assert second.status_code == 409
    assert second.json()["detail"]["code"] == "RatingAlreadyExists"
