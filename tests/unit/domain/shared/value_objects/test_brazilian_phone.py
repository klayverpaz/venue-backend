from __future__ import annotations
from app.domain.shared.value_objects.brazilian_phone import BrazilianPhone


def test_phone_mobile_e164_parsing():
    r = BrazilianPhone.create("+55 21 99694-9389")
    assert r.is_success
    assert r.value.value == "+5521996949389"
    assert r.value.is_mobile is True
    assert r.value.ddd == "21"


def test_phone_landline_parsing():
    r = BrazilianPhone.create("(11) 3333-4444")
    assert r.is_success
    assert r.value.is_mobile is False


def test_phone_rejects_none():
    r = BrazilianPhone.create(None)
    assert r.is_failure
    assert r.error == BrazilianPhone.PHONE_CANNOT_BE_EMPTY


def test_phone_rejects_non_string():
    r = BrazilianPhone.create(12345)
    assert r.is_failure
    assert r.error == BrazilianPhone.PHONE_CANNOT_BE_EMPTY


def test_phone_rejects_alpha_chars():
    r = BrazilianPhone.create("11 99999-9999 ext 100")
    assert r.is_failure
    assert r.error == BrazilianPhone.PHONE_CONTAINS_INVALID_CHARACTERS


def test_phone_rejects_no_digits():
    r = BrazilianPhone.create("()-")
    assert r.is_failure
    assert r.error == BrazilianPhone.PHONE_HAS_NO_DIGITS


def test_phone_rejects_wrong_length():
    r = BrazilianPhone.create("12345")
    assert r.is_failure
    assert r.error == BrazilianPhone.PHONE_INVALID_LENGTH


def test_phone_rejects_invalid_ddd():
    r = BrazilianPhone.create("(10) 99999-9999")
    assert r.is_failure
    assert r.error == BrazilianPhone.PHONE_INVALID_DDD


def test_phone_mobile_must_start_with_9():
    r = BrazilianPhone.create("(11) 8888-9999")  # 10 digits — landline; first digit valid (8 not in 2-7)
    assert r.is_failure
    assert r.error == BrazilianPhone.PHONE_LANDLINE_MUST_START_WITH_2_TO_7


def test_phone_create_if_not_empty_returns_none_for_blank():
    for blank in [None, "", "   "]:
        r = BrazilianPhone.create_if_not_empty(blank)
        assert r.is_success
        assert r.value is None


def test_phone_create_if_not_empty_propagates_failure():
    r = BrazilianPhone.create_if_not_empty("no digits")
    assert r.is_failure
