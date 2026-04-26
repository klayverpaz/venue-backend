from __future__ import annotations
import pytest


@pytest.mark.asyncio
async def test_create_resource_validation_envelope_aggregates_errors(
    client, db_session,
):
    register = await client.post("/v1/auth/register", json={
        "email": "envelope-owner@example.com",
        "password": "senha-forte-1",
        "role": "owner",
        "full_name": "Envelope Tester",
        "phone": None,
    })
    login = await client.post("/v1/auth/login", json={
        "email": "envelope-owner@example.com", "password": "senha-forte-1",
    })
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    from app.domain.catalog.attribute import AttrType, AttributeDefinition
    from app.domain.catalog.resource_type import ResourceType
    from app.infrastructure.repositories.resource_type_repository import (
        SQLAlchemyResourceTypeRepository,
    )
    rt = ResourceType.create(
        slug="football-field-3", name="F", description="",
        attribute_schema=[
            AttributeDefinition.create(
                key="surface_type", label="Surface", data_type=AttrType.ENUM,
                required=True, enum_values=["GRASS", "SAND"],
            ).value,
        ],
    ).value
    repo = SQLAlchemyResourceTypeRepository(db_session)
    await repo.add(rt)
    await db_session.commit()

    body = {
        "resource_type_id": str(rt.id),
        "slug": "INVALID!!!",
        "name": "",
        "description": "",
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
    response = await client.post("/v1/me/resources", json=body, headers=headers)
    assert response.status_code == 400, response.text
    detail = response.json()["detail"]
    assert detail["code"] == "ValidationFailed"
    fields = {entry["field"] for entry in detail["details"]}
    assert "slug" in fields
    assert "name" in fields
    assert "base_attributes.surface_type" in fields
