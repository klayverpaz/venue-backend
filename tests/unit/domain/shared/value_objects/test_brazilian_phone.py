import pytest
from app.domain.shared.value_objects.brazilian_phone import BrazilianPhone


@pytest.mark.parametrize("raw", [
    "(21) 99694-9389",
    "21 99694-9389",
    "5521996949389",
    "+5521996949389",
    "+55 21 9 9694 9389",
    "21996949389",
])
def test_celular_normalizado_para_e164(raw):
    r = BrazilianPhone.create(raw)
    assert r.is_success, r.error
    assert r.value.value == "+5521996949389"
    assert r.value.is_mobile is True


def test_fixo_valido():
    r = BrazilianPhone.create("(21) 3333-4444")
    assert r.is_success
    assert r.value.value == "+552133334444"
    assert r.value.is_mobile is False


def test_ddd_property():
    r = BrazilianPhone.create("(21) 99694-9389")
    assert r.value.ddd == "21"


def test_national_celular():
    r = BrazilianPhone.create("+5521996949389")
    assert r.value.national == "(21) 99694-9389"


def test_national_fixo():
    r = BrazilianPhone.create("(21) 3333-4444")
    assert r.value.national == "(21) 3333-4444"


@pytest.mark.parametrize("raw", [
    None, "", "   ", "abc",
    "123",                    # poucos dígitos
    "00 99694-9389",          # DDD inválido (00)
    "10 99694-9389",          # DDD inválido (10)
    "(21) 8694-9389",         # celular sem dígito 9
    "(21) 9 9694 9389 extra", # extra de dígitos
])
def test_rejeita_invalidos(raw):
    r = BrazilianPhone.create(raw)
    assert r.is_failure
