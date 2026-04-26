from dataclasses import FrozenInstanceError

import pytest

from app.domain.shared.field_error import FieldError


def test_field_error_carries_code_and_field():
    err = FieldError(code="EmailInvalidFormat", field="email")
    assert err.code == "EmailInvalidFormat"
    assert err.field == "email"


def test_field_error_field_defaults_to_none():
    err = FieldError(code="DuplicateAttributeKey")
    assert err.field is None


def test_field_error_is_frozen():
    err = FieldError(code="X")
    with pytest.raises(FrozenInstanceError):
        err.code = "Y"  # type: ignore[misc]


def test_field_error_equality_by_value():
    a = FieldError(code="X", field="email")
    b = FieldError(code="X", field="email")
    c = FieldError(code="X", field="phone")
    assert a == b
    assert a != c


def test_field_error_is_hashable():
    s = {FieldError(code="X", field="email"), FieldError(code="X", field="email")}
    assert len(s) == 1
