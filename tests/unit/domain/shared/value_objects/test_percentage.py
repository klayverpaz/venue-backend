import pytest
from app.domain.shared.value_objects.percentage import Percentage


@pytest.mark.parametrize("raw,expected", [
    (0, 0.0),
    (50, 50.0),
    (100, 100.0),
    ("37.5", 37.5),
    (0.001, 0.001),
])
def test_aceita_valores_em_0_100(raw, expected):
    r = Percentage.create(raw)
    assert r.is_success
    assert r.value.value == expected


@pytest.mark.parametrize("raw", [-0.01, 100.01, 101, -1, 200])
def test_rejeita_fora_do_range(raw):
    r = Percentage.create(raw)
    assert r.is_failure


@pytest.mark.parametrize("raw", [None, "abc"])
def test_rejeita_entradas_invalidas(raw):
    r = Percentage.create(raw)
    assert r.is_failure


def test_as_ratio_retorna_0_1():
    p = Percentage.create(37).value
    assert p.as_ratio == pytest.approx(0.37)
    assert Percentage.create(100).value.as_ratio == 1.0
    assert Percentage.create(0).value.as_ratio == 0.0
