from __future__ import annotations
import pytest


@pytest.mark.asyncio
async def test_owner_lifecycle_happy_path(client, db_session):
    register = await client.post("/v1/auth/register", json={
        "email": "owner1@example.com",
        "password": "senha-forte-1",
        "role": "owner",
        "full_name": "Joana da Silva",
        "phone": None,
    })
    assert register.status_code == 201, register.text
    owner_dto = register.json()
    assert owner_dto["public_slug"] == "joana-da-silva"

    login = await client.post("/v1/auth/login", json={
        "email": "owner1@example.com",
        "password": "senha-forte-1",
    })
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    rt_id = await _seed_resource_type(client, db_session, slug="football-field")

    create_body = {
        "resource_type_id": rt_id,
        "slug": "arena-zl",
        "name": "Arena Zona Leste",
        "description": "campo society",
        "city": "São Paulo",
        "region": "SP",
        "timezone": "America/Sao_Paulo",
        "slot_duration_minutes": 60,
        "operating_hours": {"monday": [{"start": "08:00", "end": "22:00"}]},
        "base_price_cents": 8000,
        "customer_cancellation_cutoff_hours": 24,
        "base_attributes": {},
        "pricing_rules": [],
        "custom_attributes": [],
    }
    created = await client.post("/v1/me/resources", json=create_body, headers=headers)
    assert created.status_code == 201, created.text
    res_id = created.json()["id"]

    pub = await client.post(f"/v1/me/resources/{res_id}/publish", headers=headers)
    assert pub.status_code == 200
    assert pub.json()["is_published"] is True

    public_list = await client.get("/v1/resources")
    slugs = {r["slug"] for r in public_list.json()["items"]}
    assert "arena-zl" in slugs

    deleted = await client.delete(f"/v1/me/resources/{res_id}", headers=headers)
    assert deleted.status_code == 204

    public_list_after = await client.get("/v1/resources")
    slugs_after = {r["slug"] for r in public_list_after.json()["items"]}
    assert "arena-zl" not in slugs_after


async def _seed_resource_type(client, db_session, *, slug: str) -> str:
    from app.domain.catalog.resource_type import ResourceType
    from app.infrastructure.repositories.resource_type_repository import (
        SQLAlchemyResourceTypeRepository,
    )
    rt = ResourceType.create(
        slug=slug, name="Football Field", description="",
        attribute_schema=[],
    ).value
    repo = SQLAlchemyResourceTypeRepository(db_session)
    await repo.add(rt)
    await db_session.commit()
    return str(rt.id)
