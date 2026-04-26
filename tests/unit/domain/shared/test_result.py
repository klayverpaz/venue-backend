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


# ---------------------------------------------------------------------------
# failure_many / details / from_failure (multi-error envelope)
# ---------------------------------------------------------------------------

from app.domain.shared.field_error import FieldError


def test_failure_many_sets_details_and_clears_error():
    errs = [FieldError(code="A", field="x"), FieldError(code="B", field="y")]
    r = Result.failure_many(errs)
    assert r.is_failure
    assert r.error is None
    assert r.details == tuple(errs)


def test_failure_many_propagates_status_code():
    r = Result.failure_many([FieldError(code="A")], status_code=400)
    assert r.status_code == 400


def test_failure_many_rejects_empty_list():
    with pytest.raises(ValueError, match="failure_many requires at least one"):
        Result.failure_many([])


def test_failure_many_accepts_iterable_not_just_list():
    r = Result.failure_many(iter([FieldError(code="A")]))
    assert r.details == (FieldError(code="A"),)


def test_failure_rejects_both_error_and_details():
    with pytest.raises(ValueError, match="exactly one of error or details"):
        Result(
            is_success=False,
            error="boom",
            details=(FieldError(code="A"),),
        )


def test_failure_rejects_neither_error_nor_details():
    with pytest.raises(ValueError, match="exactly one of error or details"):
        Result(is_success=False)


def test_success_rejects_details():
    with pytest.raises(ValueError, match="cannot carry error/details"):
        Result(is_success=True, value=1, details=(FieldError(code="A"),))


def test_from_failure_preserves_details():
    src = Result.failure_many([FieldError(code="A", field="x")], status_code=400)
    re = Result.from_failure(src)
    assert re.is_failure
    assert re.details == src.details
    assert re.status_code == 400


def test_from_failure_preserves_error_string():
    src = Result.failure("Boom", status_code=409)
    re = Result.from_failure(src)
    assert re.is_failure
    assert re.error == "Boom"
    assert re.status_code == 409


def test_from_failure_status_code_override():
    src = Result.failure_many([FieldError(code="A")], status_code=400)
    re = Result.from_failure(src, status_code=422)
    assert re.status_code == 422


def test_from_failure_status_code_override_keeps_details():
    src = Result.failure_many([FieldError(code="A", field="x")])
    re = Result.from_failure(src, status_code=422)
    assert re.details == src.details
    assert re.status_code == 422


def test_from_failure_raises_on_success():
    with pytest.raises(ValueError, match="from_failure called on a successful"):
        Result.from_failure(Result.success(1))
