from __future__ import annotations
from app.domain.shared.value_objects.short_description import ShortDescription


def test_short_description_accepts_empty_string():
    r = ShortDescription.create("")
    assert r.is_success
    assert r.value.value == ""


def test_short_description_accepts_whitespace_only():
    r = ShortDescription.create("   ")
    assert r.is_success
    assert r.value.value == ""  # stripped


def test_short_description_accepts_text():
    r = ShortDescription.create("  Campo gramado, com vestiário e estacionamento.  ")
    assert r.is_success
    assert r.value.value == "Campo gramado, com vestiário e estacionamento."


def test_short_description_rejects_none():
    r = ShortDescription.create(None)
    assert r.is_failure
    assert r.error == ShortDescription.SHORT_DESCRIPTION_INVALID_TYPE


def test_short_description_rejects_too_long():
    r = ShortDescription.create("a" * 501)
    assert r.is_failure
    assert r.error == ShortDescription.SHORT_DESCRIPTION_CANNOT_BE_GREATER_THAN_MAX_LENGTH


def test_short_description_accepts_max_length():
    r = ShortDescription.create("a" * 500)
    assert r.is_success


def test_short_description_accepts_newlines_and_tabs():
    r = ShortDescription.create("Linha 1\nLinha 2\n\tIndentado")
    assert r.is_success
