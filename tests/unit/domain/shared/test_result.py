import pytest
from app.domain.shared.result import Result


def test_success_tem_value_e_sem_error():
    r = Result.success(42)
    assert r.is_success and not r.is_failure
    assert r.value == 42
    assert r.error is None


def test_failure_tem_error_e_sem_value():
    r = Result.failure("boom")
    assert r.is_failure and not r.is_success
    assert r.value is None
    assert r.error == "boom"


def test_success_rejeita_error_simultaneo():
    with pytest.raises(ValueError):
        Result(is_success=True, value=1, error="x")


def test_failure_rejeita_value_simultaneo():
    with pytest.raises(ValueError):
        Result(is_success=False, value=1, error="x")


def test_from_exception_formata_prefix():
    r = Result.from_exception(ValueError("bad"), prefix="Parser")
    assert r.is_failure
    assert "Parser" in r.error and "ValueError" in r.error


def test_map_aplica_em_sucesso_apenas():
    r = Result.success(3).map(lambda x: x * 2)
    assert r.is_success and r.value == 6


def test_map_preserva_falha():
    r = Result.failure("err").map(lambda x: x * 2)
    assert r.is_failure and r.error == "err"


def test_unwrap_or_devolve_default_em_falha():
    assert Result.failure("x").unwrap_or(99) == 99
    assert Result.success(5).unwrap_or(99) == 5


def test_status_code_opcional():
    r = Result.failure("nope", status_code=404)
    assert r.status_code == 404
