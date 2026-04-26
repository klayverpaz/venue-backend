from __future__ import annotations
import pytest
from app.domain.catalog.attribute import AttrType, AttributeDefinition
from app.domain.catalog.resource_type import ResourceType
from app.use_cases.catalog.commands.update_resource_type import (
    UpdateResourceTypeCommand,
    UpdateResourceTypeHandler,
)
from tests.unit.use_cases.catalog.fakes.in_memory_resource_type_repository import (
    InMemoryResourceTypeRepository,
)


pytestmark = pytest.mark.asyncio


async def _setup_repo_with_one():
    repo = InMemoryResourceTypeRepository()
    rt = ResourceType.create(
        slug="football-field", name="Football Field", description="",
        attribute_schema=[
            AttributeDefinition.create(
                key="size", label="Tamanho", data_type=AttrType.STRING,
            ).value,
        ],
    ).value
    await repo.add(rt)
    return repo, rt


async def test_update_changes_name_and_description():
    repo, rt = await _setup_repo_with_one()
    handler = UpdateResourceTypeHandler(repo)
    r = await handler.handle(UpdateResourceTypeCommand(
        id=rt.id, name="Campo de Futebol", description="atualizado",
    ))
    assert r.is_success
    fetched = await repo.get_by_id(rt.id)
    assert fetched.name.value == "Campo de Futebol"
    assert fetched.description.value == "atualizado"


async def test_update_replaces_attribute_schema_wholesale():
    repo, rt = await _setup_repo_with_one()
    handler = UpdateResourceTypeHandler(repo)
    r = await handler.handle(UpdateResourceTypeCommand(
        id=rt.id,
        attribute_schema=[
            {"key": "players", "label": "Jogadores", "data_type": "int", "required": True, "enum_values": None},
        ],
    ))
    assert r.is_success
    fetched = await repo.get_by_id(rt.id)
    assert len(fetched.attribute_schema) == 1
    assert fetched.attribute_schema[0].key.value == "players"


async def test_update_toggles_is_active():
    repo, rt = await _setup_repo_with_one()
    handler = UpdateResourceTypeHandler(repo)
    r = await handler.handle(UpdateResourceTypeCommand(id=rt.id, is_active=False))
    assert r.is_success
    fetched = await repo.get_by_id(rt.id)
    assert fetched.is_active is False


async def test_update_returns_not_found_for_missing_id():
    from uuid import uuid4
    repo, _ = await _setup_repo_with_one()
    handler = UpdateResourceTypeHandler(repo)
    r = await handler.handle(UpdateResourceTypeCommand(id=uuid4(), name="x"))
    assert r.is_failure
    assert r.error == "ResourceTypeNotFound"


async def test_update_propagates_attribute_schema_validation_failure():
    repo, rt = await _setup_repo_with_one()
    handler = UpdateResourceTypeHandler(repo)
    r = await handler.handle(UpdateResourceTypeCommand(
        id=rt.id,
        attribute_schema=[
            {"key": "size", "label": "A", "data_type": "string", "required": False, "enum_values": None},
            {"key": "size", "label": "B", "data_type": "string", "required": False, "enum_values": None},
        ],
    ))
    assert r.is_failure
    assert r.error is None
    assert r.details is not None
    codes = {(e.field, e.code) for e in r.details}
    assert ("attribute_schema", "DuplicateAttributeKey") in codes


async def test_update_propagates_name_validation_failure():
    repo, rt = await _setup_repo_with_one()
    handler = UpdateResourceTypeHandler(repo)
    r = await handler.handle(UpdateResourceTypeCommand(id=rt.id, name=""))
    assert r.is_failure
    assert r.error is None
    assert r.details is not None
    codes = {(e.field, e.code) for e in r.details}
    assert ("name", "NameCannotBeEmpty") in codes


async def test_update_aggregates_attribute_schema_per_row_failures():
    repo, rt = await _setup_repo_with_one()
    handler = UpdateResourceTypeHandler(repo)
    r = await handler.handle(UpdateResourceTypeCommand(
        id=rt.id,
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
    assert "attribute_schema[1]" in fields
    codes = {(e.field, e.code) for e in r.details}
    assert ("attribute_schema[0].data_type", "InvalidDataType") in codes
