from __future__ import annotations
import pytest

pytestmark = pytest.mark.asyncio


async def _register_owner(client, *, email: str) -> tuple[str, str]:
    """Register an owner inline. Returns (token, owner_id)."""
    register = await client.post("/v1/auth/register", json={
        "email": email, "password": "hunter2-strong",
        "role": "owner", "full_name": "Owner Notif",
        "phone": None,
    })
    assert register.status_code == 201, register.text
    owner_id = register.json()["id"]
    login = await client.post("/v1/auth/login", json={
        "email": email, "password": "hunter2-strong",
    })
    assert login.status_code == 200, login.text
    return login.json()["access_token"], owner_id


async def test_owner_sees_notification_after_subscription_transition(
    client, admin_token,
):
    """End-to-end: admin transitions an owner's subscription → owner reads
    GET /v1/me/notifications and sees the SUBSCRIPTION_CHANGED row → owner
    POSTs /read → second GET shows read_at populated."""
    owner_token, owner_id = await _register_owner(
        client, email="owner-inbox-1@example.com",
    )

    # Admin transitions the subscription to INACTIVE
    resp = await client.post(
        f"/v1/admin/owners/{owner_id}/subscription",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"status": "INACTIVE"},
    )
    assert resp.status_code == 200, resp.text

    # Owner lists notifications — expects exactly 1 (TRIALING→INACTIVE)
    resp = await client.get(
        "/v1/me/notifications",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["next_cursor"] is None
    assert len(body["items"]) == 1
    notif = body["items"][0]
    assert notif["kind"] == "SUBSCRIPTION_CHANGED"
    assert notif["payload"]["new_status"] == "INACTIVE"
    assert notif["read_at"] is None

    # Mark read
    notif_id = notif["id"]
    resp = await client.post(
        f"/v1/me/notifications/{notif_id}/read",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert resp.status_code == 204, resp.text

    # Verify read_at is now populated
    resp = await client.get(
        "/v1/me/notifications",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    body = resp.json()
    assert body["items"][0]["read_at"] is not None

    # And unread_only=true returns empty
    resp = await client.get(
        "/v1/me/notifications?unread_only=true",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    body = resp.json()
    assert body["items"] == []


async def test_customer_inbox_starts_empty(client, customer_token):
    """Customers haven't done anything — inbox is empty."""
    resp = await client.get(
        "/v1/me/notifications",
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["items"] == []
    assert body["next_cursor"] is None


async def test_mark_read_returns_204_when_already_read(
    client, admin_token,
):
    owner_token, owner_id = await _register_owner(
        client, email="owner-inbox-2@example.com",
    )
    await client.post(
        f"/v1/admin/owners/{owner_id}/subscription",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"status": "INACTIVE"},
    )
    resp = await client.get(
        "/v1/me/notifications",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    notif_id = resp.json()["items"][0]["id"]

    # First read
    resp = await client.post(
        f"/v1/me/notifications/{notif_id}/read",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert resp.status_code == 204

    # Second read — idempotent
    resp = await client.post(
        f"/v1/me/notifications/{notif_id}/read",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert resp.status_code == 204


async def test_cross_recipient_mark_read_returns_404(
    client, admin_token, customer_token,
):
    owner_token, owner_id = await _register_owner(
        client, email="owner-inbox-3@example.com",
    )

    # Trigger a notification on the owner.
    await client.post(
        f"/v1/admin/owners/{owner_id}/subscription",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"status": "INACTIVE"},
    )
    resp = await client.get(
        "/v1/me/notifications",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    notif_id = resp.json()["items"][0]["id"]

    # Customer tries to mark it read — should be 404 (no leak).
    resp = await client.post(
        f"/v1/me/notifications/{notif_id}/read",
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert resp.status_code == 404, resp.text
    body = resp.json()
    assert body["detail"]["code"] == "NotificationNotFound"


async def test_unknown_id_returns_404(client, customer_token):
    resp = await client.post(
        "/v1/me/notifications/00000000-0000-0000-0000-000000000000/read",
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert resp.status_code == 404, resp.text
    assert resp.json()["detail"]["code"] == "NotificationNotFound"
