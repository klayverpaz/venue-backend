import pytest
from fastapi import HTTPException

from app.api.error_handler import unwrap
from app.domain.shared.field_error import FieldError
from app.domain.shared.result import Result


def test_unwrap_success_returns_value():
    assert unwrap(Result.success(42)) == 42


def test_unwrap_single_error_emits_flat_body():
    r = Result.failure("ResourceTypeNotFound", status_code=404)
    with pytest.raises(HTTPException) as exc_info:
        unwrap(r)
    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == {
        "code": "ResourceTypeNotFound",
        "message": "Tipo de recurso não encontrado.",
    }


def test_unwrap_details_emits_envelope():
    r = Result.failure_many(
        [
            FieldError(code="EmailInvalidFormat", field="email"),
            FieldError(code="NameCannotBeEmpty", field="full_name"),
        ],
        status_code=400,
    )
    with pytest.raises(HTTPException) as exc_info:
        unwrap(r)
    assert exc_info.value.status_code == 400
    detail = exc_info.value.detail
    assert detail["code"] == "ValidationFailed"
    assert detail["message"] == "Falha de validação."
    assert detail["details"] == [
        {"field": "email", "code": "EmailInvalidFormat", "message": "E-mail em formato inválido."},
        {"field": "full_name", "code": "NameCannotBeEmpty", "message": "Nome é obrigatório."},
    ]


def test_unwrap_details_defaults_status_code_to_400():
    r = Result.failure_many([FieldError(code="EmailInvalidFormat", field="email")])
    with pytest.raises(HTTPException) as exc_info:
        unwrap(r)
    assert exc_info.value.status_code == 400


def test_unwrap_unknown_code_in_details_uses_code_as_message():
    r = Result.failure_many([FieldError(code="NotMappedCode", field="x")])
    with pytest.raises(HTTPException) as exc_info:
        unwrap(r)
    detail_entries = exc_info.value.detail["details"]
    assert detail_entries[0] == {"field": "x", "code": "NotMappedCode", "message": "NotMappedCode"}
