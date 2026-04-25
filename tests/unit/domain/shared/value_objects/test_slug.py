from __future__ import annotations
from app.domain.shared.value_objects.slug import Slug


def test_slug_create_success_lowercase_and_strip():
    r = Slug.create("  Football-Field  ")
    assert r.is_success
    assert r.value.value == "football-field"
    assert str(r.value) == "football-field"


def test_slug_rejects_none():
    r = Slug.create(None)
    assert r.is_failure
    assert r.error == Slug.SLUG_CANNOT_BE_EMPTY


def test_slug_rejects_empty():
    r = Slug.create("")
    assert r.is_failure
    assert r.error == Slug.SLUG_CANNOT_BE_EMPTY


def test_slug_rejects_too_short():
    r = Slug.create("a")
    assert r.is_failure
    assert r.error == Slug.SLUG_INVALID_FORMAT


def test_slug_rejects_too_long():
    r = Slug.create("a" + "b" * 80)  # 81 chars
    assert r.is_failure
    assert r.error == Slug.SLUG_CANNOT_BE_GREATER_THAN_MAX_LENGTH


def test_slug_rejects_invalid_chars():
    for bad in ["foo bar", "foo_bar", "foo.bar", "foo!bar", "ção"]:
        r = Slug.create(bad)
        assert r.is_failure, f"expected failure for {bad!r}"


def test_slug_rejects_leading_or_trailing_dash():
    assert Slug.create("-foo").error == Slug.SLUG_INVALID_FORMAT
    assert Slug.create("foo-").error == Slug.SLUG_INVALID_FORMAT


def test_slug_rejects_consecutive_dashes():
    r = Slug.create("foo--bar")
    assert r.is_failure
    assert r.error == Slug.SLUG_INVALID_FORMAT


def test_slug_rejects_leading_digit():
    r = Slug.create("1foo")
    assert r.is_failure
    assert r.error == Slug.SLUG_INVALID_FORMAT


def test_slug_accepts_digits_after_first_char():
    r = Slug.create("field-1")
    assert r.is_success
    assert r.value.value == "field-1"


def test_slug_create_if_not_empty_returns_none_for_blank():
    for blank in [None, "", "   "]:
        r = Slug.create_if_not_empty(blank)
        assert r.is_success
        assert r.value is None


def test_slug_create_if_not_empty_propagates_failure():
    r = Slug.create_if_not_empty("Invalid Slug!")
    assert r.is_failure
