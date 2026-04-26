from __future__ import annotations
import pytest


@pytest.mark.asyncio
async def test_inactive_owner_subscription_hides_resources_from_public(
    client, db_session, admin_token,
):
    register = await client.post("/v1/auth/register", json={
        "email": "owner2@example.com",
        "password": "senha-forte-1",
        "role": "owner",
        "full_name": "Pedro Costa",
        "phone": None,
    })
    owner_id = register.json()["id"]
    login = await client.post("/v1/auth/login", json={
        "email": "owner2@example.com", "password": "senha-forte-1",
    })
    owner_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    from tests.e2e.resources.test_owner_lifecycle import _seed_resource_type
    rt_id = await _seed_resource_type(client, db_session, slug="football-field-2")

    body = {
        "resource_type_id": rt_id, "slug": "ar-2", "name": "Arena 2",
        "description": "", "city": "SP", "region": "SP",
        "timezone": "America/Sao_Paulo", "slot_duration_minutes": 60,
        "operating_hours": {"monday": [{"start": "08:00", "end": "22:00"}]},
        "base_price_cents": 8000, "customer_cancellation_cutoff_hours": 24,
        "base_attributes": {}, "pricing_rules": [], "custom_attributes": [],
    }
    created = await client.post("/v1/me/resources", json=body, headers=owner_headers)
    res_id = created.json()["id"]
    await client.post(f"/v1/me/resources/{res_id}/publish", headers=owner_headers)

    pub1 = await client.get("/v1/resources")
    assert "ar-2" in {r["slug"] for r in pub1.json()["items"]}

    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    deact = await client.post(
        f"/v1/admin/owners/{owner_id}/subscription",
        json={"status": "INACTIVE"},
        headers=admin_headers,
    )
    assert deact.status_code == 200

    pub2 = await client.get("/v1/resources")
    assert "ar-2" not in {r["slug"] for r in pub2.json()["items"]}

    mine = await client.get("/v1/me/resources", headers=owner_headers)
    assert "ar-2" in {r["slug"] for r in mine.json()["items"]}

    react = await client.post(
        f"/v1/admin/owners/{owner_id}/subscription",
        json={"status": "ACTIVE"},
        headers=admin_headers,
    )
    assert react.status_code == 200
    pub3 = await client.get("/v1/resources")
    assert "ar-2" in {r["slug"] for r in pub3.json()["items"]}
