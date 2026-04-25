from __future__ import annotations
from dataclasses import dataclass
from typing import Self
from app.domain.shared.result import Result
from app.domain.shared.value_object import BaseValueObject


@dataclass(frozen=True, slots=True)
class RatingScore(BaseValueObject):
    RATING_SCORE_INVALID_TYPE = "RatingScoreInvalidType"
    RATING_SCORE_OUT_OF_RANGE = "RatingScoreOutOfRange"
    MIN_VALUE = 1
    MAX_VALUE = 5

    value: int

    @classmethod
    def create(cls, raw) -> Result[Self]:
        if isinstance(raw, bool) or not isinstance(raw, int):
            return Result.failure(cls.RATING_SCORE_INVALID_TYPE)
        if not (cls.MIN_VALUE <= raw <= cls.MAX_VALUE):
            return Result.failure(cls.RATING_SCORE_OUT_OF_RANGE)
        return Result.success(cls(value=raw))
