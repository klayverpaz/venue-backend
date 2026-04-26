from __future__ import annotations
import pytest


pytestmark = pytest.mark.asyncio


@pytest.mark.skip(reason="OWNER public_slug generation implemented in Task 13 of Plan 06")
async def test_owner_register_creates_trialing_subscription_and_can_read_it(
    http_client,
):
    register = await http_client.post(
        "/v1/auth/register",
        json={
            "email": "owner-e2e@example.com",
            "password": "hunter2-strong",
            "role": "owner",
            "full_name": "Owner E2E",
            "phone": None,
        },
    )
    assert register.status_code == 201, register.text

    login = await http_client.post(
        "/v1/auth/login",
        json={"email": "owner-e2e@example.com", "password": "hunter2-strong"},
    )
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]

    me = await http_client.get(
        "/v1/me/subscription",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me.status_code == 200, me.text
    body = me.json()
    assert body["status"] == "TRIALING"
    assert body["is_operational"] is True
    assert body["trial_ends_at"] is not None


@pytest.mark.skip(reason="OWNER public_slug generation implemented in Task 13 of Plan 06")
async def test_admin_changes_status_then_owner_sees_new_status(
    http_client, admin_token,
):
    register = await http_client.post(
        "/v1/auth/register",
        json={
            "email": "owner2-e2e@example.com",
            "password": "hunter2-strong",
            "role": "owner",
            "full_name": "Owner",
            "phone": None,
        },
    )
    assert register.status_code == 201, register.text
    owner_id = register.json()["id"]

    set_status = await http_client.post(
        f"/v1/admin/owners/{owner_id}/subscription",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"status": "INACTIVE"},
    )
    assert set_status.status_code == 200, set_status.text
    assert set_status.json()["status"] == "INACTIVE"
    assert set_status.json()["is_operational"] is False

    # Idempotent — same payload again returns 200 with same status_changed_at.
    again = await http_client.post(
        f"/v1/admin/owners/{owner_id}/subscription",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"status": "INACTIVE"},
    )
    assert again.status_code == 200
    assert again.json()["status_changed_at"] == set_status.json()["status_changed_at"]


async def test_admin_endpoint_rejects_non_admin(http_client, customer_token):
    response = await http_client.post(
        "/v1/admin/owners/00000000-0000-0000-0000-000000000000/subscription",
        headers={"Authorization": f"Bearer {customer_token}"},
        json={"status": "ACTIVE"},
    )
    assert response.status_code == 403


async def test_admin_endpoint_rejects_non_owner_target(
    http_client, admin_token,
):
    register = await http_client.post(
        "/v1/auth/register",
        json={
            "email": "customer3-e2e@example.com",
            "password": "hunter2-strong",
            "role": "customer",
            "full_name": "C",
            "phone": None,
        },
    )
    assert register.status_code == 201, register.text
    customer_id = register.json()["id"]

    response = await http_client.post(
        f"/v1/admin/owners/{customer_id}/subscription",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"status": "ACTIVE"},
    )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "UserIsNotOwner"
