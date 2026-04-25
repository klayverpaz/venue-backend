from __future__ import annotations
from app.domain.shared.value_objects.email import Email


def test_email_create_success_lowercases_and_strips():
    r = Email.create("  USER@Example.COM  ")
    assert r.is_success
    assert r.value.value == "user@example.com"
    assert str(r.value) == "user@example.com"


def test_email_create_rejects_none():
    r = Email.create(None)
    assert r.is_failure
    assert r.error == Email.EMAIL_CANNOT_BE_EMPTY


def test_email_create_rejects_empty():
    r = Email.create("")
    assert r.is_failure
    assert r.error == Email.EMAIL_CANNOT_BE_EMPTY


def test_email_create_rejects_whitespace_only():
    r = Email.create("   ")
    assert r.is_failure
    assert r.error == Email.EMAIL_CANNOT_BE_EMPTY


def test_email_create_rejects_non_string():
    r = Email.create(123)
    assert r.is_failure
    assert r.error == Email.EMAIL_CANNOT_BE_EMPTY


def test_email_create_rejects_invalid_format():
    for bad in ["no-at-sign", "@nodomain.com", "user@", "user@nodot"]:
        r = Email.create(bad)
        assert r.is_failure, f"expected failure for {bad!r}"
        assert r.error == Email.EMAIL_INVALID_FORMAT


def test_email_create_rejects_over_max_length():
    over = "a" * 250 + "@x.io"   # 255 chars
    r = Email.create(over)
    assert r.is_failure
    assert r.error == Email.EMAIL_CANNOT_BE_GREATER_THAN_MAX_LENGTH


def test_email_create_if_not_empty_returns_none_for_blank():
    for blank in [None, "", "   "]:
        r = Email.create_if_not_empty(blank)
        assert r.is_success
        assert r.value is None


def test_email_create_if_not_empty_validates_when_provided():
    r = Email.create_if_not_empty("user@example.com")
    assert r.is_success
    assert r.value is not None
    assert r.value.value == "user@example.com"


def test_email_create_if_not_empty_propagates_failure():
    r = Email.create_if_not_empty("not-an-email")
    assert r.is_failure
    assert r.error == Email.EMAIL_INVALID_FORMAT
