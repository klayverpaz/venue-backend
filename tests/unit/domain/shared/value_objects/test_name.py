from __future__ import annotations
from app.domain.shared.value_objects.name import Name


def test_name_create_success():
    r = Name.create("  Arena Mané Garrincha — Campo 1  ")
    assert r.is_success
    assert r.value.value == "Arena Mané Garrincha — Campo 1"
    assert str(r.value) == "Arena Mané Garrincha — Campo 1"


def test_name_rejects_none():
    r = Name.create(None)
    assert r.is_failure
    assert r.error == Name.NAME_CANNOT_BE_EMPTY


def test_name_rejects_empty():
    r = Name.create("")
    assert r.is_failure
    assert r.error == Name.NAME_CANNOT_BE_EMPTY


def test_name_rejects_whitespace_only():
    r = Name.create("   ")
    assert r.is_failure
    assert r.error == Name.NAME_CANNOT_BE_EMPTY


def test_name_rejects_too_long():
    r = Name.create("a" * 501)
    assert r.is_failure
    assert r.error == Name.NAME_CANNOT_BE_GREATER_THAN_MAX_LENGTH


def test_name_accepts_max_length():
    r = Name.create("a" * 500)
    assert r.is_success


def test_name_rejects_control_chars():
    for bad in ["foo\nbar", "foo\rbar", "foo\tbar", "foo\x00bar"]:
        r = Name.create(bad)
        assert r.is_failure, f"expected failure for {bad!r}"
        assert r.error == Name.NAME_CONTAINS_INVALID_CHARACTERS


def test_name_create_if_not_empty_returns_none_for_blank():
    for blank in [None, "", "   "]:
        r = Name.create_if_not_empty(blank)
        assert r.is_success
        assert r.value is None
