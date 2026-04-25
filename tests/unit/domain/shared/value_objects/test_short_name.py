from __future__ import annotations
from app.domain.shared.value_objects.short_name import ShortName


def test_short_name_create_success():
    r = ShortName.create("  Tamanho do campo  ")
    assert r.is_success
    assert r.value.value == "Tamanho do campo"


def test_short_name_rejects_none():
    r = ShortName.create(None)
    assert r.is_failure
    assert r.error == ShortName.SHORT_NAME_CANNOT_BE_EMPTY


def test_short_name_rejects_empty():
    r = ShortName.create("")
    assert r.is_failure
    assert r.error == ShortName.SHORT_NAME_CANNOT_BE_EMPTY


def test_short_name_rejects_too_long():
    r = ShortName.create("a" * 41)
    assert r.is_failure
    assert r.error == ShortName.SHORT_NAME_CANNOT_BE_GREATER_THAN_MAX_LENGTH


def test_short_name_accepts_max_length():
    r = ShortName.create("a" * 40)
    assert r.is_success


def test_short_name_rejects_control_chars():
    r = ShortName.create("foo\nbar")
    assert r.is_failure
    assert r.error == ShortName.SHORT_NAME_CONTAINS_INVALID_CHARACTERS


def test_short_name_create_if_not_empty_returns_none_for_blank():
    for blank in [None, "", "   "]:
        r = ShortName.create_if_not_empty(blank)
        assert r.is_success
        assert r.value is None
