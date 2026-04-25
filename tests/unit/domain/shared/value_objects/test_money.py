from __future__ import annotations
from decimal import Decimal
from app.domain.shared.value_objects.money import Money


def test_money_create_success_zero():
    r = Money.create(0)
    assert r.is_success
    assert r.value.cents == 0


def test_money_create_success_positive():
    r = Money.create(4990)
    assert r.is_success
    assert r.value.cents == 4990


def test_money_rejects_negative():
    r = Money.create(-1)
    assert r.is_failure
    assert r.error == Money.MONEY_CANNOT_BE_NEGATIVE


def test_money_rejects_above_max():
    r = Money.create(10**10 + 1)
    assert r.is_failure
    assert r.error == Money.MONEY_EXCEEDS_MAX


def test_money_accepts_max():
    r = Money.create(10**10)
    assert r.is_success


def test_money_rejects_non_int():
    for bad in [1.5, "100", None, True]:
        r = Money.create(bad)
        assert r.is_failure, f"expected failure for {bad!r}"
        assert r.error == Money.MONEY_INVALID_TYPE


def test_money_from_reais_success():
    r = Money.from_reais(49, 90)
    assert r.is_success
    assert r.value.cents == 4990


def test_money_from_reais_zero_centavos():
    r = Money.from_reais(100)
    assert r.is_success
    assert r.value.cents == 10000


def test_money_from_reais_rejects_negative_reais():
    r = Money.from_reais(-1, 0)
    assert r.is_failure
    assert r.error == Money.MONEY_CANNOT_BE_NEGATIVE


def test_money_from_reais_rejects_invalid_centavos():
    for bad_centavos in [-1, 100, 200]:
        r = Money.from_reais(10, bad_centavos)
        assert r.is_failure
        assert r.error == Money.MONEY_INVALID_CENTAVOS


def test_money_to_decimal_for_display():
    m = Money.create(4990).value
    assert m.to_decimal() == Decimal("49.90")


def test_money_str_brl_format():
    m = Money.create(4990).value
    assert str(m) == "R$ 49,90"


def test_money_equality_by_value():
    a = Money.create(4990).value
    b = Money.create(4990).value
    assert a == b
    assert hash(a) == hash(b)
