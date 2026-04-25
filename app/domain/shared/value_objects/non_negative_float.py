from __future__ import annotations
from dataclasses import dataclass
from typing import Self
from app.domain.shared.result import Result
from app.domain.shared.value_object import BaseValueObject


@dataclass(frozen=True, slots=True)
class NonNegativeFloat(BaseValueObject):
    value: float

    @classmethod
    def create(cls, raw) -> Result[Self]:
        if raw is None:
            return Result.failure("NonNegativeFloat: valor obrigatório.")
        try:
            value = float(raw)
        except (TypeError, ValueError):
            return Result.failure(f"NonNegativeFloat: '{raw}' não é um número.")
        if value != value:  # NaN
            return Result.failure("NonNegativeFloat: NaN não é permitido.")
        if value < 0:
            return Result.failure(f"NonNegativeFloat: valor não pode ser negativo ({value}).")
        return Result.success(cls(value=value))

    def __float__(self) -> float:
        return self.value
