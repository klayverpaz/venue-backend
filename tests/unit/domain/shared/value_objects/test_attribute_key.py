from __future__ import annotations
from app.domain.shared.value_objects.attribute_key import AttributeKey


def test_attribute_key_create_success():
    r = AttributeKey.create("  field_size  ")
    assert r.is_success
    assert r.value.value == "field_size"


def test_attribute_key_rejects_none():
    r = AttributeKey.create(None)
    assert r.is_failure
    assert r.error == AttributeKey.ATTRIBUTE_KEY_CANNOT_BE_EMPTY


def test_attribute_key_rejects_empty():
    r = AttributeKey.create("")
    assert r.is_failure
    assert r.error == AttributeKey.ATTRIBUTE_KEY_CANNOT_BE_EMPTY


def test_attribute_key_rejects_too_long():
    r = AttributeKey.create("a" * 51)
    assert r.is_failure
    assert r.error == AttributeKey.ATTRIBUTE_KEY_CANNOT_BE_GREATER_THAN_MAX_LENGTH


def test_attribute_key_accepts_max_length():
    r = AttributeKey.create("a" * 50)
    assert r.is_success


def test_attribute_key_rejects_uppercase_or_kebab():
    for bad in ["FieldSize", "field-size", "field size", "1field", "_field", "field!", "ção"]:
        r = AttributeKey.create(bad)
        assert r.is_failure, f"expected failure for {bad!r}"
        assert r.error == AttributeKey.ATTRIBUTE_KEY_INVALID_FORMAT


def test_attribute_key_accepts_digits_after_first():
    r = AttributeKey.create("field_1")
    assert r.is_success
