from __future__ import annotations
from dataclasses import dataclass
from typing import Self
from app.domain.shared.result import Result
from app.domain.shared.value_object import BaseValueObject


@dataclass(frozen=True, slots=True)
class Percentage(BaseValueObject):
    value: float  # 0.0 <= value <= 100.0

    @classmethod
    def create(cls, raw) -> Result[Self]:
        if raw is None:
            return Result.failure("Percentage: valor obrigatório.")
        try:
            value = float(raw)
        except (TypeError, ValueError):
            return Result.failure(f"Percentage: '{raw}' não é um número.")
        if not 0.0 <= value <= 100.0:
            return Result.failure(f"Percentage: deve estar entre 0 e 100 (recebido: {value}).")
        return Result.success(cls(value=value))

    @property
    def as_ratio(self) -> float:
        return self.value / 100.0
