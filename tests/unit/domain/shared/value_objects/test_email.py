import pytest
from app.domain.shared.value_objects.email import Email


@pytest.mark.parametrize("raw,expected", [
    ("foo@bar.com", "foo@bar.com"),
    ("  Foo@BAR.com  ", "foo@bar.com"),
    ("a.b+tag@sub.example.com.br", "a.b+tag@sub.example.com.br"),
])
def test_normaliza_e_aceita_validos(raw, expected):
    r = Email.create(raw)
    assert r.is_success
    assert r.value.value == expected
    assert str(r.value) == expected


@pytest.mark.parametrize("raw", [
    None, "", "   ", "sem-arroba", "a@", "@b.com", "a@b", "a@b.c",
])
def test_rejeita_invalidos(raw):
    r = Email.create(raw)
    assert r.is_failure


def test_rejeita_acima_de_254_chars():
    raw = "a" * 250 + "@b.com"
    r = Email.create(raw)
    assert r.is_failure
