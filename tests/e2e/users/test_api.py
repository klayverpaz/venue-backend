import pytest


@pytest.mark.asyncio
async def test_health(client):
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_create_get_update_list(client):
    # create
    r = await client.post("/v1/users", json={
        "name": "João", "email": "JOAO@x.com",
        "phone": "(21) 99694-9389",
        "credit_score": 80, "balance": 1000,
    })
    assert r.status_code == 201, r.text
    user = r.json()
    assert user["email"] == "joao@x.com"
    assert user["phone"] == "+5521996949389"

    # get by id
    r2 = await client.get(f"/v1/users/{user['id']}")
    assert r2.status_code == 200
    assert r2.json()["id"] == user["id"]

    # update email
    r3 = await client.patch(
        f"/v1/users/{user['id']}/email",
        json={"new_email": "novo@x.com"},
    )
    assert r3.status_code == 200
    assert r3.json()["email"] == "novo@x.com"

    # list
    r4 = await client.get("/v1/users")
    assert r4.status_code == 200
    assert len(r4.json()["items"]) == 1


@pytest.mark.asyncio
async def test_422_em_vo_invalido(client):
    r = await client.post("/v1/users", json={
        "name": "X", "email": "not-email", "phone": "xxx",
    })
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_409_em_email_duplicado(client):
    payload = {
        "name": "A", "email": "dup@x.com", "phone": "(21) 99694-9389",
    }
    await client.post("/v1/users", json=payload)
    r = await client.post("/v1/users", json={**payload, "name": "B"})
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_404_quando_user_nao_existe(client):
    r = await client.get("/v1/users/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404
