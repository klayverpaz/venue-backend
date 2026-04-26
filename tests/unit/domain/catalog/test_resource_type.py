from __future__ import annotations
from app.domain.catalog.attribute import AttrType, AttributeDefinition
from app.domain.catalog.resource_type import ResourceType
from app.domain.shared.value_objects.name import Name
from app.domain.shared.value_objects.short_description import ShortDescription
from app.domain.shared.value_objects.slug import Slug


def _ad(key: str, label: str, dt: AttrType = AttrType.STRING, **kw):
    return AttributeDefinition.create(key=key, label=label, data_type=dt, **kw).value


def test_resource_type_create_minimal():
    r = ResourceType.create(
        slug="football-field",
        name="Football Field",
        description="",
        attribute_schema=[],
    )
    assert r.is_success
    rt = r.value
    assert isinstance(rt.slug, Slug)
    assert isinstance(rt.name, Name)
    assert isinstance(rt.description, ShortDescription)
    assert rt.slug.value == "football-field"
    assert rt.name.value == "Football Field"
    assert rt.description.value == ""
    assert rt.attribute_schema == ()
    assert rt.is_active is True


def test_resource_type_create_with_schema():
    r = ResourceType.create(
        slug="padel-court",
        name="Padel Court",
        description="Quadras de padel cobertas",
        attribute_schema=[
            _ad("surface", "Tipo de gramado", AttrType.ENUM, enum_values=["sintetico", "natural"]),
            _ad("players", "Jogadores", AttrType.INT, required=True),
        ],
    )
    assert r.is_success
    assert len(r.value.attribute_schema) == 2


def test_resource_type_create_propagates_slug_error():
    r = ResourceType.create(
        slug="Invalid Slug!",
        name="Foo",
        description="",
        attribute_schema=[],
    )
    assert r.is_failure
    assert r.error is None
    assert r.details is not None
    codes = {(e.field, e.code) for e in r.details}
    assert ("slug", Slug.SLUG_INVALID_FORMAT) in codes


def test_resource_type_create_propagates_name_error():
    r = ResourceType.create(
        slug="football-field",
        name="",
        description="",
        attribute_schema=[],
    )
    assert r.is_failure
    assert r.error is None
    assert r.details is not None
    codes = {(e.field, e.code) for e in r.details}
    assert ("name", Name.NAME_CANNOT_BE_EMPTY) in codes


def test_resource_type_create_rejects_duplicate_attribute_keys():
    a1 = _ad("size", "Tamanho")
    a2 = _ad("size", "Outro tamanho")
    r = ResourceType.create(
        slug="football-field",
        name="Football Field",
        description="",
        attribute_schema=[a1, a2],
    )
    assert r.is_failure
    assert r.error is None
    assert r.details is not None
    codes = {(e.field, e.code) for e in r.details}
    assert ("attribute_schema", ResourceType.DUPLICATE_ATTRIBUTE_KEY) in codes


def test_resource_type_create_aggregates_multiple_field_failures():
    r = ResourceType.create(
        slug="BAD slug",
        name="",
        description="",
        attribute_schema=[],
    )
    assert r.is_failure
    assert r.error is None
    assert r.details is not None
    codes = {(e.field, e.code) for e in r.details}
    assert ("slug", Slug.SLUG_INVALID_FORMAT) in codes
    assert ("name", Name.NAME_CANNOT_BE_EMPTY) in codes


def test_resource_type_attribute_schema_returns_tuple_view():
    rt = ResourceType.create(
        slug="football-field",
        name="Football Field",
        description="",
        attribute_schema=[_ad("size", "Tamanho")],
    ).value
    schema = rt.attribute_schema
    assert isinstance(schema, tuple)


def test_resource_type_update_metadata_success():
    rt = ResourceType.create(
        slug="football-field", name="Football Field", description="", attribute_schema=[],
    ).value
    before = rt.updated_at
    r = rt.update_metadata(name="Campo de Futebol", description="atualizado")
    assert r.is_success
    assert rt.name.value == "Campo de Futebol"
    assert rt.description.value == "atualizado"
    assert rt.updated_at > before


def test_resource_type_update_metadata_propagates_name_failure():
    rt = ResourceType.create(
        slug="football-field", name="Football Field", description="", attribute_schema=[],
    ).value
    r = rt.update_metadata(name="")
    assert r.is_failure
    assert r.error is None
    assert r.details is not None
    codes = {(e.field, e.code) for e in r.details}
    assert ("name", Name.NAME_CANNOT_BE_EMPTY) in codes
    # Entity should not have mutated.
    assert rt.name.value == "Football Field"


def test_resource_type_update_metadata_aggregates_failures():
    rt = ResourceType.create(
        slug="football-field", name="Football Field", description="", attribute_schema=[],
    ).value
    r = rt.update_metadata(
        name="",
        description="x" * (ShortDescription.MAX_LENGTH + 1),
    )
    assert r.is_failure
    assert r.error is None
    assert r.details is not None
    codes = {(e.field, e.code) for e in r.details}
    assert ("name", Name.NAME_CANNOT_BE_EMPTY) in codes
    assert ("description", ShortDescription.SHORT_DESCRIPTION_CANNOT_BE_GREATER_THAN_MAX_LENGTH) in codes
    # Entity not mutated.
    assert rt.name.value == "Football Field"


def test_resource_type_update_metadata_no_args_is_noop():
    rt = ResourceType.create(
        slug="football-field", name="Football Field", description="", attribute_schema=[],
    ).value
    before = rt.updated_at
    r = rt.update_metadata()
    assert r.is_success
    # No-op: updated_at NOT bumped when both args are None.
    assert rt.updated_at == before


def test_resource_type_replace_attribute_schema_success():
    rt = ResourceType.create(
        slug="football-field", name="Football Field", description="", attribute_schema=[],
    ).value
    new_schema = [_ad("size", "Tamanho"), _ad("players", "Jogadores", AttrType.INT)]
    r = rt.replace_attribute_schema(new_schema)
    assert r.is_success
    assert len(rt.attribute_schema) == 2


def test_resource_type_replace_attribute_schema_rejects_duplicates():
    rt = ResourceType.create(
        slug="football-field", name="Football Field", description="", attribute_schema=[],
    ).value
    r = rt.replace_attribute_schema([_ad("size", "A"), _ad("size", "B")])
    assert r.is_failure
    assert r.error is None
    assert r.details is not None
    codes = {(e.field, e.code) for e in r.details}
    assert ("attribute_schema", ResourceType.DUPLICATE_ATTRIBUTE_KEY) in codes


def test_resource_type_activate_deactivate():
    rt = ResourceType.create(
        slug="football-field", name="Football Field", description="", attribute_schema=[],
    ).value
    assert rt.is_active is True
    rt.deactivate()
    assert rt.is_active is False
    rt.activate()
    assert rt.is_active is True


def test_resource_type_validate_attributes_required_present():
    rt = ResourceType.create(
        slug="football-field", name="Football Field", description="",
        attribute_schema=[_ad("players", "Jogadores", AttrType.INT, required=True)],
    ).value
    assert rt.validate_attributes({"players": 10}).is_success


def test_resource_type_validate_attributes_required_missing():
    rt = ResourceType.create(
        slug="football-field", name="Football Field", description="",
        attribute_schema=[_ad("players", "Jogadores", AttrType.INT, required=True)],
    ).value
    r = rt.validate_attributes({})
    assert r.is_failure
    assert r.error is None
    assert r.details is not None
    codes = {(e.field, e.code) for e in r.details}
    assert ("players", ResourceType.REQUIRED_ATTRIBUTE_MISSING) in codes


def test_resource_type_validate_attributes_type_mismatch_int():
    rt = ResourceType.create(
        slug="football-field", name="Football Field", description="",
        attribute_schema=[_ad("players", "Jogadores", AttrType.INT, required=True)],
    ).value
    r = rt.validate_attributes({"players": "ten"})
    assert r.is_failure
    assert r.error is None
    assert r.details is not None
    codes = {(e.field, e.code) for e in r.details}
    assert ("players", ResourceType.ATTRIBUTE_TYPE_MISMATCH) in codes


def test_resource_type_validate_attributes_type_mismatch_bool():
    rt = ResourceType.create(
        slug="football-field", name="Football Field", description="",
        attribute_schema=[_ad("lit", "Iluminado", AttrType.BOOL)],
    ).value
    r = rt.validate_attributes({"lit": "yes"})
    assert r.is_failure
    assert r.error is None
    assert r.details is not None
    codes = {(e.field, e.code) for e in r.details}
    assert ("lit", ResourceType.ATTRIBUTE_TYPE_MISMATCH) in codes


def test_resource_type_validate_attributes_enum_value_in_set():
    rt = ResourceType.create(
        slug="football-field", name="Football Field", description="",
        attribute_schema=[_ad("surface", "Tipo", AttrType.ENUM, enum_values=["natural", "synthetic"])],
    ).value
    assert rt.validate_attributes({"surface": "natural"}).is_success


def test_resource_type_validate_attributes_enum_value_not_in_set():
    rt = ResourceType.create(
        slug="football-field", name="Football Field", description="",
        attribute_schema=[_ad("surface", "Tipo", AttrType.ENUM, enum_values=["natural", "synthetic"])],
    ).value
    r = rt.validate_attributes({"surface": "concrete"})
    assert r.is_failure
    assert r.error is None
    assert r.details is not None
    codes = {(e.field, e.code) for e in r.details}
    assert ("surface", ResourceType.ATTRIBUTE_ENUM_VALUE_NOT_ALLOWED) in codes


def test_resource_type_validate_attributes_unknown_key():
    rt = ResourceType.create(
        slug="football-field", name="Football Field", description="",
        attribute_schema=[_ad("size", "Tamanho")],
    ).value
    r = rt.validate_attributes({"size": "ok", "unknown": "value"})
    assert r.is_failure
    assert r.error is None
    assert r.details is not None
    codes = {(e.field, e.code) for e in r.details}
    assert ("unknown", ResourceType.UNKNOWN_ATTRIBUTE_KEY) in codes


def test_resource_type_validate_attributes_optional_absent_is_ok():
    rt = ResourceType.create(
        slug="football-field", name="Football Field", description="",
        attribute_schema=[_ad("size", "Tamanho", AttrType.STRING, required=False)],
    ).value
    assert rt.validate_attributes({}).is_success
