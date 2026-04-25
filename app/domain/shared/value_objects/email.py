from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Self
from app.domain.shared.result import Result
from app.domain.shared.value_object import BaseValueObject

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")


@dataclass(frozen=True, slots=True)
class Email(BaseValueObject):
    value: str  # sempre lowercase, sem espaços

    @classmethod
    def create(cls, raw) -> Result[Self]:
        if raw is None or not isinstance(raw, str):
            return Result.failure("Email: valor obrigatório.")
        normalized = raw.strip().lower()
        if not normalized:
            return Result.failure("Email: não pode ser vazio.")
        if len(normalized) > 254:
            return Result.failure("Email: excede 254 caracteres.")
        if not EMAIL_RE.match(normalized):
            return Result.failure(f"Email inválido: '{raw}'.")
        return Result.success(cls(value=normalized))

    def __str__(self) -> str:
        return self.value
