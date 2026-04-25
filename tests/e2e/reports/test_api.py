import pytest


@pytest.mark.asyncio
async def test_active_users_by_month_endpoint_empty(client):
    r = await client.get("/v1/reports/active-users-by-month")
    assert r.status_code == 200
    assert r.json() == {"items": []}


@pytest.mark.asyncio
async def test_active_users_by_month_after_creating_users(client):
    await client.post("/v1/users", json={
        "name": "Ana", "email": "ana@x.com",
        "phone": "(21) 99694-9389",
        "credit_score": 0, "balance": 0,
    })
    r = await client.get("/v1/reports/active-users-by-month")
    assert r.status_code == 200
    body = r.json()
    assert len(body["items"]) == 1
    row = body["items"][0]
    assert row["active_count"] == 1
    assert isinstance(row["year"], int)
    assert isinstance(row["month"], int)
