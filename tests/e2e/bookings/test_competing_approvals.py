from __future__ import annotations
from datetime import datetime, timedelta, timezone

import pytest

from tests.e2e.bookings.test_happy_path import (
    _register_owner_with_resource,
    _slot_iso,
    _utc_now,
)


pytestmark = pytest.mark.asyncio


async def _register_customer(client, *, email: str) -> tuple[str, str]:
    reg = await client.post("/v1/auth/register", json={
        "email": email, "password": "hunter2-strong",
        "role": "customer", "full_name": "C", "phone": None,
    })
    assert reg.status_code == 201, reg.text
    cid = reg.json()["id"]
    login = await client.post("/v1/auth/login", json={
        "email": email, "password": "hunter2-strong",
    })
    return login.json()["access_token"], cid


async def test_two_customers_same_slot_one_approved_other_rejected(
    client, admin_token,
):
    owner_token, _, resource_id = await _register_owner_with_resource(
        client, admin_token,
    )
    a_token, _ = await _register_customer(client, email="a-bk@example.com")
    b_token, _ = await _register_customer(client, email="b-bk@example.com")
    start_iso, end_iso = _slot_iso(days_ahead=4, hours=2)

    a_req = await client.post(
        "/v1/me/bookings",
        headers={"Authorization": f"Bearer {a_token}"},
        json={"resource_id": resource_id, "slot_start_at": start_iso,
              "slot_end_at": end_iso, "customer_note": None},
    )
    assert a_req.status_code == 201
    b_req = await client.post(
        "/v1/me/bookings",
        headers={"Authorization": f"Bearer {b_token}"},
        json={"resource_id": resource_id, "slot_start_at": start_iso,
              "slot_end_at": end_iso, "customer_note": None},
    )
    assert b_req.status_code == 201
    a_id = a_req.json()["id"]
    b_id = b_req.json()["id"]

    approve = await client.post(
        f"/v1/me/bookings/{a_id}/approve",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert approve.status_code == 200
    assert approve.json()["status"] == "APPROVED"

    b_after = await client.get(
        f"/v1/me/bookings/{b_id}",
        headers={"Authorization": f"Bearer {b_token}"},
    )
    assert b_after.status_code == 200
    body = b_after.json()
    assert body["status"] == "REJECTED"
    last_change = body["status_history"][-1]
    assert last_change["to_status"] == "REJECTED"
    assert last_change["reason"] == "auto_rejected_competing_request"


async def test_natural_dedup_returns_409(client, admin_token, customer_token):
    _, _, resource_id = await _register_owner_with_resource(
        client, admin_token,
    )
    start_iso, end_iso = _slot_iso(days_ahead=5, hours=1)
    first = await client.post(
        "/v1/me/bookings",
        headers={"Authorization": f"Bearer {customer_token}"},
        json={"resource_id": resource_id, "slot_start_at": start_iso,
              "slot_end_at": end_iso, "customer_note": None},
    )
    assert first.status_code == 201
    second = await client.post(
        "/v1/me/bookings",
        headers={"Authorization": f"Bearer {customer_token}"},
        json={"resource_id": resource_id, "slot_start_at": start_iso,
              "slot_end_at": end_iso, "customer_note": None},
    )
    assert second.status_code == 409
    assert second.json()["detail"]["code"] == "BookingAlreadyExists"
