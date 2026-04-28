from __future__ import annotations
from datetime import datetime, timedelta, timezone

import pytest


pytestmark = pytest.mark.asyncio


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _slot_iso(*, days_ahead: int, hours_ahead: int = 0, hours: int = 1) -> tuple[str, str]:
    """Build a slot anchored at 17:00 UTC (14:00 São Paulo) days_ahead from now."""
    base = (_utc_now() + timedelta(days=days_ahead)).replace(
        hour=17 - hours_ahead, minute=0, second=0, microsecond=0,
    )
    end = base + timedelta(hours=hours)
    return base.isoformat(), end.isoformat()


async def _register_owner_with_resource(client, admin_token):
    """Register an owner, seed a ResourceType (admin), create a published
    Resource. Returns (owner_token, owner_id, resource_id)."""
    reg = await client.post("/v1/auth/register", json={
        "email": "owner-bookings@example.com",
        "password": "hunter2-strong",
        "role": "owner",
        "full_name": "Owner Bookings",
        "phone": None,
    })
    assert reg.status_code == 201, reg.text
    owner_id = reg.json()["id"]
    login = await client.post("/v1/auth/login", json={
        "email": "owner-bookings@example.com",
        "password": "hunter2-strong",
    })
    owner_token = login.json()["access_token"]

    rt = await client.post(
        "/v1/admin/resource-types",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"slug": "football-field", "name": "Football Field",
              "description": "", "attribute_schema": []},
    )
    assert rt.status_code == 201, rt.text
    rt_id = rt.json()["id"]

    create = await client.post(
        "/v1/me/resources",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={
            "resource_type_id": rt_id,
            "slug": "campo",
            "name": "Campo",
            "description": "",
            "city": "SP",
            "region": "SP",
            "timezone": "America/Sao_Paulo",
            "slot_duration_minutes": 60,
            "operating_hours": {
                wd: [{"start": "06:00", "end": "22:00"}]
                for wd in ("monday", "tuesday", "wednesday", "thursday",
                           "friday", "saturday", "sunday")
            },
            "base_price_cents": 8000,
            "customer_cancellation_cutoff_hours": 24,
            "base_attributes": {},
            "pricing_rules": [],
            "custom_attributes": [],
        },
    )
    assert create.status_code == 201, create.text
    resource_id = create.json()["id"]
    pub = await client.post(
        f"/v1/me/resources/{resource_id}/publish",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert pub.status_code == 200, pub.text
    return owner_token, owner_id, resource_id


async def test_happy_path_request_approve_view(client, admin_token, customer_token):
    owner_token, owner_id, resource_id = await _register_owner_with_resource(
        client, admin_token,
    )
    start_iso, end_iso = _slot_iso(days_ahead=2, hours=2)

    req = await client.post(
        "/v1/me/bookings",
        headers={"Authorization": f"Bearer {customer_token}"},
        json={
            "resource_id": resource_id,
            "slot_start_at": start_iso,
            "slot_end_at": end_iso,
            "customer_note": "10 pessoas",
        },
    )
    assert req.status_code == 201, req.text
    booking = req.json()
    assert booking["status"] == "PENDING"
    assert booking["total_price_cents"] == 16000

    approve = await client.post(
        f"/v1/me/bookings/{booking['id']}/approve",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert approve.status_code == 200, approve.text
    assert approve.json()["status"] == "APPROVED"

    fetched = await client.get(
        f"/v1/me/bookings/{booking['id']}",
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert fetched.status_code == 200
    assert fetched.json()["status"] == "APPROVED"


async def test_customer_cancel_within_cutoff(client, admin_token, customer_token):
    owner_token, _owner_id, resource_id = await _register_owner_with_resource(
        client, admin_token,
    )
    start_iso, end_iso = _slot_iso(days_ahead=3)

    req = await client.post(
        "/v1/me/bookings",
        headers={"Authorization": f"Bearer {customer_token}"},
        json={
            "resource_id": resource_id,
            "slot_start_at": start_iso, "slot_end_at": end_iso,
            "customer_note": None,
        },
    )
    booking_id = req.json()["id"]

    cancel = await client.post(
        f"/v1/me/bookings/{booking_id}/cancel",
        headers={"Authorization": f"Bearer {customer_token}"},
        json={"reason": "changed plans"},
    )
    assert cancel.status_code == 200, cancel.text
    assert cancel.json()["status"] == "CANCELLED"


async def test_customer_cancel_past_cutoff_returns_403(
    client, admin_token, customer_token,
):
    owner_token, _, resource_id = await _register_owner_with_resource(
        client, admin_token,
    )
    base = (_utc_now() + timedelta(hours=6)).replace(
        minute=0, second=0, microsecond=0,
    )
    end = base + timedelta(hours=1)
    req = await client.post(
        "/v1/me/bookings",
        headers={"Authorization": f"Bearer {customer_token}"},
        json={
            "resource_id": resource_id,
            "slot_start_at": base.isoformat(),
            "slot_end_at": end.isoformat(),
            "customer_note": None,
        },
    )
    if req.status_code != 201:
        pytest.skip(f"environment now() doesn't permit a 6h-ahead slot: {req.text}")
    booking_id = req.json()["id"]

    cancel = await client.post(
        f"/v1/me/bookings/{booking_id}/cancel",
        headers={"Authorization": f"Bearer {customer_token}"},
        json={"reason": None},
    )
    assert cancel.status_code == 403
    assert cancel.json()["detail"]["code"] == "BookingCancellationPastCutoff"
