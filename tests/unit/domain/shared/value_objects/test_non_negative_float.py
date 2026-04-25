import math
import pytest
from app.domain.shared.value_objects.non_negative_float import NonNegativeFloat


@pytest.mark.parametrize("raw,expected", [
    (0, 0.0),
    (0.0, 0.0),
    (3.5, 3.5),
    ("12.34", 12.34),
    (1000, 1000.0),
])
def test_aceita_numeros_nao_negativos(raw, expected):
    r = NonNegativeFloat.create(raw)
    assert r.is_success
    assert r.value.value == expected


def test_rejeita_negativo():
    r = NonNegativeFloat.create(-1.0)
    assert r.is_failure
    assert "negativ" in r.error.lower()


def test_rejeita_nan():
    r = NonNegativeFloat.create(math.nan)
    assert r.is_failure


@pytest.mark.parametrize("raw", [None, "abc", "xyz"])
def test_rejeita_entradas_invalidas(raw):
    r = NonNegativeFloat.create(raw)
    assert r.is_failure


def test_float_dunder():
    r = NonNegativeFloat.create(7.5)
    assert float(r.value) == 7.5
