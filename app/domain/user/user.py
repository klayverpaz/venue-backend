from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Self
from app.domain.shared.entity import BaseEntity
from app.domain.shared.result import Result
from app.domain.shared.value_objects.brazilian_phone import BrazilianPhone
from app.domain.shared.value_objects.email import Email
from app.domain.shared.value_objects.non_negative_float import NonNegativeFloat
from app.domain.shared.value_objects.percentage import Percentage


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(slots=True, kw_only=True)
class User(BaseEntity):
    name: str
    email: Email
    phone: BrazilianPhone
    credit_score: Percentage
    balance: NonNegativeFloat

    @classmethod
    def create(
        cls,
        *,
        name: str,
        email: str,
        phone: str,
        credit_score: float = 0.0,
        balance: float = 0.0,
    ) -> Result[Self]:
        name_clean = (name or "").strip()
        errors: list[str] = []
        if not name_clean:
            errors.append("name: obrigatório.")

        email_r = Email.create(email)
        phone_r = BrazilianPhone.create(phone)
        score_r = Percentage.create(credit_score)
        balance_r = NonNegativeFloat.create(balance)

        for r in (email_r, phone_r, score_r, balance_r):
            if r.is_failure:
                errors.append(r.error)

        if errors:
            return Result.failure("; ".join(errors))

        return Result.success(cls(
            name=name_clean,
            email=email_r.value,
            phone=phone_r.value,
            credit_score=score_r.value,
            balance=balance_r.value,
        ))

    def change_email(self, new_email: str) -> Result[None]:
        r = Email.create(new_email)
        if r.is_failure:
            return Result.failure(r.error)
        self.email = r.value
        self.updated_at = _utcnow()
        return Result.success(None)
