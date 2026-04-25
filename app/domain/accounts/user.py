from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Self
from app.domain.accounts.role import Role
from app.domain.shared.entity import BaseEntity
from app.domain.shared.result import Result
from app.domain.shared.value_objects.brazilian_phone import BrazilianPhone
from app.domain.shared.value_objects.email import Email


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(slots=True, kw_only=True)
class User(BaseEntity):
    email: Email
    password_hash: str
    role: Role
    full_name: str
    phone: BrazilianPhone | None = None
    is_active: bool = True

    @classmethod
    def create(
        cls,
        *,
        email: str,
        password_hash: str,
        role: Role,
        full_name: str,
        phone: str | None,
    ) -> Result[Self]:
        errors: list[str] = []

        email_r = Email.create(email)
        if email_r.is_failure:
            errors.append(email_r.error)

        full_name_clean = (full_name or "").strip()
        if not full_name_clean:
            errors.append("full_name: obrigatório.")

        if not password_hash:
            errors.append("password_hash: obrigatório.")

        phone_vo: BrazilianPhone | None = None
        if phone is not None and phone.strip():
            phone_r = BrazilianPhone.create(phone)
            if phone_r.is_failure:
                errors.append(phone_r.error)
            else:
                phone_vo = phone_r.value

        if errors:
            return Result.failure("; ".join(errors))

        return Result.success(cls(
            email=email_r.value,
            password_hash=password_hash,
            role=role,
            full_name=full_name_clean,
            phone=phone_vo,
        ))

    def change_password_hash(self, new_hash: str) -> None:
        self.password_hash = new_hash
        self.updated_at = _utcnow()

    def set_role(self, new_role: Role) -> None:
        self.role = new_role
        self.updated_at = _utcnow()

    def deactivate(self) -> None:
        self.is_active = False
        self.updated_at = _utcnow()

    def activate(self) -> None:
        self.is_active = True
        self.updated_at = _utcnow()
