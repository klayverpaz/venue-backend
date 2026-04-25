from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal
from typing import Self
from app.domain.shared.result import Result
from app.domain.shared.value_object import BaseValueObject


@dataclass(frozen=True, slots=True)
class Money(BaseValueObject):
    MONEY_INVALID_TYPE = "MoneyInvalidType"
    MONEY_CANNOT_BE_NEGATIVE = "MoneyCannotBeNegative"
    MONEY_EXCEEDS_MAX = "MoneyExceedsMax"
    MONEY_INVALID_CENTAVOS = "MoneyInvalidCentavos"
    MAX_CENTS = 10_000_000_000  # R$ 100,000,000.00

    cents: int

    @classmethod
    def create(cls, cents) -> Result[Self]:
        # Reject bool (which is an int subclass) explicitly — money is never a flag.
        if isinstance(cents, bool) or not isinstance(cents, int):
            return Result.failure(cls.MONEY_INVALID_TYPE)
        if cents < 0:
            return Result.failure(cls.MONEY_CANNOT_BE_NEGATIVE)
        if cents > cls.MAX_CENTS:
            return Result.failure(cls.MONEY_EXCEEDS_MAX)
        return Result.success(cls(cents=cents))

    @classmethod
    def from_reais(cls, reais: int, centavos: int = 0) -> Result[Self]:
        if not isinstance(reais, int) or isinstance(reais, bool):
            return Result.failure(cls.MONEY_INVALID_TYPE)
        if not isinstance(centavos, int) or isinstance(centavos, bool):
            return Result.failure(cls.MONEY_INVALID_CENTAVOS)
        if reais < 0:
            return Result.failure(cls.MONEY_CANNOT_BE_NEGATIVE)
        if not 0 <= centavos < 100:
            return Result.failure(cls.MONEY_INVALID_CENTAVOS)
        return cls.create(reais * 100 + centavos)

    def to_decimal(self) -> Decimal:
        """For display only. Never use the result for arithmetic."""
        return Decimal(self.cents) / Decimal(100)

    def __str__(self) -> str:
        reais, cents = divmod(self.cents, 100)
        return f"R$ {reais},{cents:02d}"
