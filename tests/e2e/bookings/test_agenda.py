from __future__ import annotations
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

import pytest

from tests.e2e.bookings.test_happy_path import (
    _register_owner_with_resource,
    _slot_iso,
    _utc_now,
)


def _q(dt: str) -> str:
    """URL-encode a datetime string so that '+00:00' isn't mangled to ' 00:00'."""
    return quote(dt, safe="")


pytestmark = pytest.mark.asyncio


async def test_public_agenda_returns_slots_without_booking_ids(
    client, admin_token, customer_token,
):
    owner_token, _, resource_id = await _register_owner_with_resource(
        client, admin_token,
    )
    listing = await client.get("/v1/resources")
    items = listing.json()["items"]
    target = next((i for i in items if i["id"] == resource_id), None)
    assert target is not None, f"resource not in public listing: {items}"
    owner_slug = target["owner_slug"]
    resource_slug = target["slug"]

    start_iso, end_iso = _slot_iso(days_ahead=3, hours=1)
    req = await client.post(
        "/v1/me/bookings",
        headers={"Authorization": f"Bearer {customer_token}"},
        json={"resource_id": resource_id, "slot_start_at": start_iso,
              "slot_end_at": end_iso, "customer_note": None},
    )
    assert req.status_code == 201

    range_start = _q((_utc_now() + timedelta(days=2)).isoformat())
    range_end = _q((_utc_now() + timedelta(days=4)).isoformat())
    agenda = await client.get(
        f"/v1/resources/{owner_slug}/{resource_slug}/agenda"
        f"?from={range_start}&to={range_end}",
    )
    assert agenda.status_code == 200, agenda.text
    body = agenda.json()
    assert body["resource_id"] == resource_id
    pending = [s for s in body["slots"] if s["status"] == "PENDING"]
    assert len(pending) >= 1
    for s in pending:
        assert s["booking_id"] is None
        assert s["customer_id"] is None


async def test_owner_agenda_includes_booking_ids(
    client, admin_token, customer_token,
):
    owner_token, _, resource_id = await _register_owner_with_resource(
        client, admin_token,
    )
    start_iso, end_iso = _slot_iso(days_ahead=3, hours=1)
    req = await client.post(
        "/v1/me/bookings",
        headers={"Authorization": f"Bearer {customer_token}"},
        json={"resource_id": resource_id, "slot_start_at": start_iso,
              "slot_end_at": end_iso, "customer_note": None},
    )
    assert req.status_code == 201
    booking_id = req.json()["id"]

    range_start = _q((_utc_now() + timedelta(days=2)).isoformat())
    range_end = _q((_utc_now() + timedelta(days=4)).isoformat())
    agenda = await client.get(
        f"/v1/me/resources/{resource_id}/agenda"
        f"?from={range_start}&to={range_end}",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert agenda.status_code == 200, agenda.text
    body = agenda.json()
    occupied = [s for s in body["slots"] if s["status"] == "PENDING"]
    assert any(s["booking_id"] == booking_id for s in occupied)


async def test_agenda_range_too_wide_returns_422(client, admin_token):
    owner_token, _, resource_id = await _register_owner_with_resource(
        client, admin_token,
    )
    range_start = _q(_utc_now().isoformat())
    range_end = _q((_utc_now() + timedelta(days=60)).isoformat())
    agenda = await client.get(
        f"/v1/me/resources/{resource_id}/agenda"
        f"?from={range_start}&to={range_end}",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert agenda.status_code == 422
    assert agenda.json()["detail"]["code"] == "AgendaRangeTooWide"
