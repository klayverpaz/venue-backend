from __future__ import annotations
import pytest
from app.domain.catalog.attribute import AttrType, AttributeDefinition
from app.domain.catalog.resource_type import ResourceType
from app.infrastructure.repositories.resource_type_repository import (
    SQLAlchemyResourceTypeRepository,
)


pytestmark = pytest.mark.asyncio


def _make_rt(slug: str = "football-field", name: str = "Football Field", active: bool = True):
    rt = ResourceType.create(
        slug=slug,
        name=name,
        description="Campo gramado para futebol",
        attribute_schema=[
            AttributeDefinition.create(
                key="surface", label="Tipo de gramado", data_type=AttrType.ENUM,
                enum_values=["natural", "synthetic"],
            ).value,
            AttributeDefinition.create(
                key="players", label="Jogadores", data_type=AttrType.INT, required=True,
            ).value,
        ],
        is_active=active,
    )
    return rt.value


async def test_add_and_get_by_id(db_session):
    repo = SQLAlchemyResourceTypeRepository(db_session)
    rt = _make_rt()
    r = await repo.add(rt)
    assert r.is_success
    fetched = await repo.get_by_id(rt.id)
    assert fetched is not None
    assert fetched.slug.value == "football-field"
    assert fetched.name.value == "Football Field"
    assert len(fetched.attribute_schema) == 2
    surface = fetched.attribute_schema[0]
    assert surface.data_type == AttrType.ENUM
    assert surface.enum_values is not None
    assert tuple(v.value for v in surface.enum_values) == ("natural", "synthetic")


async def test_add_rejects_duplicate_slug(db_session):
    repo = SQLAlchemyResourceTypeRepository(db_session)
    await repo.add(_make_rt(slug="court"))
    r = await repo.add(_make_rt(slug="court"))
    assert r.is_failure
    assert r.error == "SlugAlreadyTaken"


async def test_get_by_slug(db_session):
    repo = SQLAlchemyResourceTypeRepository(db_session)
    rt = _make_rt(slug="padel-court")
    await repo.add(rt)
    fetched = await repo.get_by_slug("padel-court")
    assert fetched is not None
    assert fetched.id == rt.id


async def test_get_by_slug_returns_none_when_absent(db_session):
    repo = SQLAlchemyResourceTypeRepository(db_session)
    assert await repo.get_by_slug("missing") is None


async def test_update_persists_changes(db_session):
    repo = SQLAlchemyResourceTypeRepository(db_session)
    rt = _make_rt()
    await repo.add(rt)
    assert rt.update_metadata(name="Campo de Futebol", description="atualizado").is_success
    rt.deactivate()
    r = await repo.update(rt)
    assert r.is_success
    fetched = await repo.get_by_id(rt.id)
    assert fetched is not None
    assert fetched.name.value == "Campo de Futebol"
    assert fetched.is_active is False


async def test_delete_removes_row(db_session):
    repo = SQLAlchemyResourceTypeRepository(db_session)
    rt = _make_rt()
    await repo.add(rt)
    r = await repo.delete(rt.id)
    assert r.is_success
    assert await repo.get_by_id(rt.id) is None


async def test_delete_returns_not_found_when_absent(db_session):
    from uuid import uuid4
    repo = SQLAlchemyResourceTypeRepository(db_session)
    r = await repo.delete(uuid4())
    assert r.is_failure
    assert r.error == "ResourceTypeNotFound"


async def test_list_all_includes_inactive(db_session):
    repo = SQLAlchemyResourceTypeRepository(db_session)
    await repo.add(_make_rt(slug="active-1", active=True))
    await repo.add(_make_rt(slug="inactive-1", active=False))
    rows = await repo.list_all()
    slugs = {r.slug.value for r in rows}
    assert {"active-1", "inactive-1"} <= slugs


async def test_list_active_excludes_inactive(db_session):
    repo = SQLAlchemyResourceTypeRepository(db_session)
    await repo.add(_make_rt(slug="active-2", active=True))
    await repo.add(_make_rt(slug="inactive-2", active=False))
    rows = await repo.list_active()
    slugs = {r.slug.value for r in rows}
    assert "active-2" in slugs
    assert "inactive-2" not in slugs


async def test_list_pagination(db_session):
    repo = SQLAlchemyResourceTypeRepository(db_session)
    for i in range(5):
        await repo.add(_make_rt(slug=f"page-{i}"))
    page1 = await repo.list_all(limit=2, offset=0)
    page2 = await repo.list_all(limit=2, offset=2)
    assert len(page1) == 2
    assert len(page2) == 2
    assert {r.id for r in page1}.isdisjoint({r.id for r in page2})
