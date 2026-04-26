from __future__ import annotations

from app.domain.resources.custom_attribute import CustomAttribute
from app.domain.shared.value_objects.attribute_key import AttributeKey
from app.domain.shared.value_objects.short_description import ShortDescription
from app.domain.shared.value_objects.short_name import ShortName


def test_create_happy_path():
    r = CustomAttribute.create(key="wifi", label="Wi-Fi", value="Sim, gratuito")
    assert r.is_success
    attr = r.value
    assert attr.key.value == "wifi"
    assert attr.label.value == "Wi-Fi"
    assert attr.value.value == "Sim, gratuito"


def test_create_aggregates_field_errors():
    r = CustomAttribute.create(
        key="WIFI",       # uppercase forbidden by AttributeKey snake_case rule
        label="",          # empty short_name forbidden
        value="",          # ShortDescription allows empty — should NOT error
    )
    assert r.is_failure
    fields = {e.field for e in r.details}
    assert "key" in fields
    assert "label" in fields
    assert "value" not in fields  # empty description is allowed


def test_create_aggregates_all_three_fields():
    r = CustomAttribute.create(
        key="!!!invalid!!!",
        label="",
        value="X" * 600,   # exceeds ShortDescription max length
    )
    assert r.is_failure
    fields = {e.field for e in r.details}
    assert fields == {"key", "label", "value"}


def test_equality_by_value():
    a = CustomAttribute.create(key="wifi", label="Wi-Fi", value="ok").value
    b = CustomAttribute.create(key="wifi", label="Wi-Fi", value="ok").value
    assert a == b
    assert hash(a) == hash(b)
