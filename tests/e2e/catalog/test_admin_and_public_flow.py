from __future__ import annotations
import pytest


pytestmark = pytest.mark.asyncio


async def test_admin_creates_resource_type_then_public_sees_it(http_client, admin_token):
    # Admin creates
    create = await http_client.post(
        "/v1/admin/resource-types",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "slug": "football-field",
            "name": "Football Field",
            "description": "Campos de futebol",
            "attribute_schema": [
                {"key": "surface", "label": "Tipo de gramado", "data_type": "enum",
                 "required": True, "enum_values": ["natural", "synthetic"]},
            ],
            "is_active": True,
        },
    )
    assert create.status_code == 201, create.text
    body = create.json()
    rt_id = body["id"]
    assert body["slug"] == "football-field"

    # Public sees it
    public_list = await http_client.get("/v1/catalog/resource-types")
    assert public_list.status_code == 200
    items = public_list.json()["items"]
    assert any(item["slug"] == "football-field" for item in items)

    # Admin deactivates
    patch = await http_client.patch(
        f"/v1/admin/resource-types/{rt_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"is_active": False},
    )
    assert patch.status_code == 200

    # Public no longer sees it
    public_list_after = await http_client.get("/v1/catalog/resource-types")
    assert public_list_after.status_code == 200
    items_after = public_list_after.json()["items"]
    assert not any(item["slug"] == "football-field" for item in items_after)


async def test_admin_create_rejects_duplicate_slug(http_client, admin_token):
    payload = {
        "slug": "padel-court",
        "name": "Padel Court",
        "description": "",
        "attribute_schema": [],
    }
    first = await http_client.post(
        "/v1/admin/resource-types",
        headers={"Authorization": f"Bearer {admin_token}"},
        json=payload,
    )
    assert first.status_code == 201

    second = await http_client.post(
        "/v1/admin/resource-types",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={**payload, "name": "Other Padel Court"},
    )
    assert second.status_code == 409
    assert second.json()["detail"]["code"] == "SlugAlreadyTaken"


async def test_public_listing_no_auth_required(http_client):
    response = await http_client.get("/v1/catalog/resource-types")
    assert response.status_code == 200


async def test_admin_create_rejects_non_admin_role(http_client, customer_token):
    response = await http_client.post(
        "/v1/admin/resource-types",
        headers={"Authorization": f"Bearer {customer_token}"},
        json={"slug": "x", "name": "X", "description": "", "attribute_schema": []},
    )
    assert response.status_code == 403


async def test_admin_create_propagates_slug_validation_error(http_client, admin_token):
    response = await http_client.post(
        "/v1/admin/resource-types",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "slug": "Invalid Slug!",
            "name": "Foo",
            "description": "",
            "attribute_schema": [],
        },
    )
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert "SlugInvalidFormat" in detail["code"]
