from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Self
from app.domain.shared.result import Result
from app.domain.shared.value_object import BaseValueObject

_DIGITS_RE = re.compile(r"\D+")
_VALID_DDDS = {
    11, 12, 13, 14, 15, 16, 17, 18, 19,
    21, 22, 24, 27, 28,
    31, 32, 33, 34, 35, 37, 38,
    41, 42, 43, 44, 45, 46, 47, 48, 49,
    51, 53, 54, 55,
    61, 62, 63, 64, 65, 66, 67, 68, 69,
    71, 73, 74, 75, 77, 79,
    81, 82, 83, 84, 85, 86, 87, 88, 89,
    91, 92, 93, 94, 95, 96, 97, 98, 99,
}


@dataclass(frozen=True, slots=True)
class BrazilianPhone(BaseValueObject):
    PHONE_CANNOT_BE_EMPTY = "PhoneCannotBeEmpty"
    PHONE_CONTAINS_INVALID_CHARACTERS = "PhoneContainsInvalidCharacters"
    PHONE_HAS_NO_DIGITS = "PhoneHasNoDigits"
    PHONE_INVALID_LENGTH = "PhoneInvalidLength"
    PHONE_INVALID_DDD = "PhoneInvalidDdd"
    PHONE_MOBILE_MUST_START_WITH_9 = "PhoneMobileMustStartWith9"
    PHONE_LANDLINE_MUST_START_WITH_2_TO_7 = "PhoneLandlineMustStartWith2To7"

    value: str           # E.164: "+5521996949389"
    is_mobile: bool

    @classmethod
    def create(cls, raw) -> Result[Self]:
        if raw is None or not isinstance(raw, str):
            return Result.failure(cls.PHONE_CANNOT_BE_EMPTY)
        if re.search(r"[a-zA-Z]", raw):
            return Result.failure(cls.PHONE_CONTAINS_INVALID_CHARACTERS)
        digits = _DIGITS_RE.sub("", raw)
        if not digits:
            return Result.failure(cls.PHONE_HAS_NO_DIGITS)
        if len(digits) in (12, 13) and digits.startswith("55"):
            digits = digits[2:]
        if len(digits) not in (10, 11):
            return Result.failure(cls.PHONE_INVALID_LENGTH)
        ddd = int(digits[:2])
        if ddd not in _VALID_DDDS:
            return Result.failure(cls.PHONE_INVALID_DDD)
        is_mobile = len(digits) == 11
        if is_mobile and digits[2] != "9":
            return Result.failure(cls.PHONE_MOBILE_MUST_START_WITH_9)
        if not is_mobile and digits[2] not in "234567":
            return Result.failure(cls.PHONE_LANDLINE_MUST_START_WITH_2_TO_7)
        return Result.success(cls(value=f"+55{digits}", is_mobile=is_mobile))

    @classmethod
    def create_if_not_empty(cls, raw) -> Result[Self | None]:
        if raw is None or (isinstance(raw, str) and not raw.strip()):
            return Result.success(None)
        return cls.create(raw)

    @property
    def ddd(self) -> str:
        return self.value[3:5]

    @property
    def national(self) -> str:
        rest = self.value[5:]
        if self.is_mobile:
            return f"({self.ddd}) {rest[:5]}-{rest[5:]}"
        return f"({self.ddd}) {rest[:4]}-{rest[4:]}"

    def __str__(self) -> str:
        return self.value
