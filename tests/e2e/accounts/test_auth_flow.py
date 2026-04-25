from __future__ import annotations
import pytest


@pytest.mark.asyncio
async def test_full_register_login_me_refresh_flow(client):
    # Register a customer
    r = await client.post("/v1/auth/register", json={
        "email": "alice@example.com",
        "password": "hunter2-strong",
        "role": "customer",
        "full_name": "Alice",
        "phone": "+5511999999999",
    })
    assert r.status_code == 201, r.text
    user = r.json()
    assert user["email"] == "alice@example.com"
    assert user["role"] == "customer"

    # Login
    r = await client.post("/v1/auth/login", json={
        "email": "alice@example.com",
        "password": "hunter2-strong",
    })
    assert r.status_code == 200, r.text
    tokens = r.json()
    access = tokens["access_token"]
    refresh = tokens["refresh_token"]
    assert tokens["user"]["email"] == "alice@example.com"

    # /me with the access token
    r = await client.get("/v1/me", headers={"Authorization": f"Bearer {access}"})
    assert r.status_code == 200, r.text
    me = r.json()
    assert me["email"] == "alice@example.com"

    # /me without a token → 401 (FastAPI 0.136 HTTPBearer returns 401 for missing creds)
    r = await client.get("/v1/me")
    assert r.status_code == 401

    # /me with garbage token → 401
    r = await client.get("/v1/me", headers={"Authorization": "Bearer not-a-jwt"})
    assert r.status_code == 401

    # Refresh
    r = await client.post("/v1/auth/refresh", json={"refresh_token": refresh})
    assert r.status_code == 200, r.text
    new_tokens = r.json()
    assert new_tokens["access_token"] != access  # new pair issued

    # Logout (no-op, just verifies the dep works)
    r = await client.post("/v1/auth/logout", headers={
        "Authorization": f"Bearer {new_tokens['access_token']}",
    })
    assert r.status_code == 204


@pytest.mark.asyncio
async def test_register_admin_role_rejected(client):
    r = await client.post("/v1/auth/register", json={
        "email": "admin@example.com", "password": "hunter2-strong",
        "role": "admin",  # not in the SelfRegisterableRole literal
        "full_name": "Adm", "phone": None,
    })
    # Pydantic validation rejects the literal — 422, not 403
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_login_unknown_email_returns_401(client):
    r = await client.post("/v1/auth/login", json={
        "email": "nobody@example.com", "password": "anything",
    })
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_admin_endpoint_blocks_non_admin(client):
    # Register and log in as a customer
    await client.post("/v1/auth/register", json={
        "email": "cust@example.com", "password": "hunter2-strong",
        "role": "customer", "full_name": "Cust", "phone": None,
    })
    r = await client.post("/v1/auth/login", json={
        "email": "cust@example.com", "password": "hunter2-strong",
    })
    access = r.json()["access_token"]

    # Try to call an admin endpoint
    r = await client.get(
        "/v1/admin/users",
        headers={"Authorization": f"Bearer {access}"},
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_register_duplicate_email_409(client):
    # First registration succeeds
    r = await client.post("/v1/auth/register", json={
        "email": "dupe@example.com", "password": "hunter2-strong",
        "role": "customer", "full_name": "Dupe", "phone": None,
    })
    assert r.status_code == 201, r.text

    # Second registration with same email returns 409
    r = await client.post("/v1/auth/register", json={
        "email": "dupe@example.com", "password": "hunter2-strong",
        "role": "customer", "full_name": "Dupe2", "phone": None,
    })
    assert r.status_code == 409, r.text


@pytest.mark.asyncio
async def test_me_without_token_401(client):
    # GET /v1/me with no Authorization header — HTTPBearer returns 403 for
    # missing credentials by default. Accept either 401 or 403 to remain
    # robust against HTTPBearer config changes.
    r = await client.get("/v1/me")
    assert r.status_code in (401, 403)


@pytest.mark.asyncio
async def test_refresh_with_invalid_token_401(client):
    r = await client.post("/v1/auth/refresh", json={"refresh_token": "garbage"})
    assert r.status_code == 401
