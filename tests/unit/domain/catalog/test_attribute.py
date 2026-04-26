from __future__ import annotations
from app.domain.catalog.attribute import AttrType, AttributeDefinition
from app.domain.shared.value_objects.attribute_key import AttributeKey
from app.domain.shared.value_objects.short_name import ShortName


def test_attr_type_values_lowercase():
    assert AttrType.STRING.value == "string"
    assert AttrType.INT.value == "int"
    assert AttrType.BOOL.value == "bool"
    assert AttrType.ENUM.value == "enum"


def test_attribute_definition_create_string_success():
    r = AttributeDefinition.create(
        key="field_size",
        label="Tamanho do campo",
        data_type=AttrType.STRING,
        required=True,
    )
    assert r.is_success
    assert isinstance(r.value.key, AttributeKey)
    assert r.value.key.value == "field_size"
    assert isinstance(r.value.label, ShortName)
    assert r.value.label.value == "Tamanho do campo"
    assert r.value.data_type == AttrType.STRING
    assert r.value.required is True
    assert r.value.enum_values is None


def test_attribute_definition_create_int_default_not_required():
    r = AttributeDefinition.create(
        key="players",
        label="Jogadores",
        data_type=AttrType.INT,
    )
    assert r.is_success
    assert r.value.required is False


def test_attribute_definition_create_enum_with_values():
    r = AttributeDefinition.create(
        key="surface",
        label="Tipo de gramado",
        data_type=AttrType.ENUM,
        enum_values=["natural", "synthetic"],
    )
    assert r.is_success
    assert r.value.enum_values is not None
    assert tuple(v.value for v in r.value.enum_values) == ("natural", "synthetic")


def test_attribute_definition_enum_requires_values():
    r = AttributeDefinition.create(
        key="surface",
        label="Tipo de gramado",
        data_type=AttrType.ENUM,
        enum_values=None,
    )
    assert r.is_failure
    assert r.error is None
    assert r.details is not None
    codes = {(e.field, e.code) for e in r.details}
    assert ("enum_values", AttributeDefinition.ENUM_TYPE_REQUIRES_VALUES) in codes


def test_attribute_definition_enum_rejects_empty_values():
    r = AttributeDefinition.create(
        key="surface",
        label="Tipo de gramado",
        data_type=AttrType.ENUM,
        enum_values=[],
    )
    assert r.is_failure
    assert r.error is None
    assert r.details is not None
    codes = {(e.field, e.code) for e in r.details}
    assert ("enum_values", AttributeDefinition.ENUM_TYPE_REQUIRES_VALUES) in codes


def test_attribute_definition_non_enum_rejects_values():
    r = AttributeDefinition.create(
        key="players",
        label="Jogadores",
        data_type=AttrType.INT,
        enum_values=["a", "b"],
    )
    assert r.is_failure
    assert r.error is None
    assert r.details is not None
    codes = {(e.field, e.code) for e in r.details}
    assert ("enum_values", AttributeDefinition.NON_ENUM_TYPE_CANNOT_HAVE_VALUES) in codes


def test_attribute_definition_propagates_attribute_key_error():
    r = AttributeDefinition.create(
        key="Invalid Key!",
        label="Foo",
        data_type=AttrType.STRING,
    )
    assert r.is_failure
    assert r.error is None
    assert r.details is not None
    codes = {(e.field, e.code) for e in r.details}
    assert ("key", AttributeKey.ATTRIBUTE_KEY_INVALID_FORMAT) in codes


def test_attribute_definition_propagates_label_error():
    r = AttributeDefinition.create(
        key="ok",
        label="",
        data_type=AttrType.STRING,
    )
    assert r.is_failure
    assert r.error is None
    assert r.details is not None
    codes = {(e.field, e.code) for e in r.details}
    assert ("label", ShortName.SHORT_NAME_CANNOT_BE_EMPTY) in codes


def test_attribute_definition_propagates_enum_value_error():
    r = AttributeDefinition.create(
        key="surface",
        label="Tipo",
        data_type=AttrType.ENUM,
        enum_values=["valid", ""],
    )
    assert r.is_failure
    assert r.error is None
    assert r.details is not None
    codes = {(e.field, e.code) for e in r.details}
    assert ("enum_values[1]", ShortName.SHORT_NAME_CANNOT_BE_EMPTY) in codes


def test_attribute_definition_aggregates_multiple_field_failures():
    r = AttributeDefinition.create(
        key="Invalid Key!",
        label="",
        data_type=AttrType.STRING,
    )
    assert r.is_failure
    assert r.error is None
    assert r.details is not None
    fields = {e.field for e in r.details}
    assert "key" in fields
    assert "label" in fields


def test_attribute_definition_equality():
    a = AttributeDefinition.create(
        key="k", label="L", data_type=AttrType.STRING, required=True,
    ).value
    b = AttributeDefinition.create(
        key="k", label="L", data_type=AttrType.STRING, required=True,
    ).value
    assert a == b
    assert hash(a) == hash(b)
