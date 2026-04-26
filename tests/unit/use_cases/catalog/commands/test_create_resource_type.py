from __future__ import annotations
import pytest
from app.use_cases.catalog.commands.create_resource_type import (
    CreateResourceTypeCommand,
    CreateResourceTypeHandler,
)
from tests.unit.use_cases.catalog.fakes.in_memory_resource_type_repository import (
    InMemoryResourceTypeRepository,
)


pytestmark = pytest.mark.asyncio


def _cmd(**kw) -> CreateResourceTypeCommand:
    base = dict(
        slug="football-field",
        name="Football Field",
        description="Campo de futebol",
        attribute_schema=[
            {"key": "size", "label": "Tamanho", "data_type": "string", "required": True, "enum_values": None},
        ],
    )
    base.update(kw)
    return CreateResourceTypeCommand(**base)


async def test_create_resource_type_success():
    repo = InMemoryResourceTypeRepository()
    handler = CreateResourceTypeHandler(repo)
    r = await handler.handle(_cmd())
    assert r.is_success
    assert r.value.slug == "football-field"
    assert r.value.is_active is True
    assert (await repo.get_by_id(r.value.id)) is not None


async def test_create_resource_type_propagates_slug_failure():
    repo = InMemoryResourceTypeRepository()
    handler = CreateResourceTypeHandler(repo)
    r = await handler.handle(_cmd(slug="Invalid Slug!"))
    assert r.is_failure
    assert r.error is None
    assert r.details is not None
    codes = {(e.field, e.code) for e in r.details}
    assert ("slug", "SlugInvalidFormat") in codes


async def test_create_resource_type_aggregates_attribute_schema_failures():
    """Handler aggregates per-element AttributeDefinition.create failures and
    InvalidDataType branches, returning structured FieldError per row."""
    repo = InMemoryResourceTypeRepository()
    handler = CreateResourceTypeHandler(repo)
    r = await handler.handle(_cmd(
        attribute_schema=[
            {"key": "ok", "label": "OK", "data_type": "not-a-type",
             "required": False, "enum_values": None},
            {"key": "BAD KEY", "label": "Bad", "data_type": "string",
             "required": False, "enum_values": None},
        ],
    ))
    assert r.is_failure
    assert r.status_code == 400
    assert r.error is None
    assert r.details is not None
    fields = {e.field for e in r.details}
    assert "attribute_schema[0].data_type" in fields
    # The second row has an invalid AttributeKey (uppercase + space).
    assert any(f == "attribute_schema[1]" for f in fields)
    codes = {(e.field, e.code) for e in r.details}
    assert ("attribute_schema[0].data_type", "InvalidDataType") in codes


async def test_create_resource_type_rejects_duplicate_slug():
    repo = InMemoryResourceTypeRepository()
    handler = CreateResourceTypeHandler(repo)
    await handler.handle(_cmd())
    r = await handler.handle(_cmd(name="Other"))
    assert r.is_failure
    assert r.error == "SlugAlreadyTaken"


async def test_create_resource_type_with_enum_attribute():
    repo = InMemoryResourceTypeRepository()
    handler = CreateResourceTypeHandler(repo)
    r = await handler.handle(_cmd(
        slug="padel-court",
        attribute_schema=[
            {"key": "surface", "label": "Tipo", "data_type": "enum", "required": False,
             "enum_values": ["natural", "synthetic"]},
        ],
    ))
    assert r.is_success
    assert r.value.attribute_schema[0].data_type == "enum"
    assert r.value.attribute_schema[0].enum_values == ["natural", "synthetic"]
