from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Self
from app.domain.accounts.role import Role
from app.domain.shared.entity import BaseEntity
from app.domain.shared.field_error import FieldError
from app.domain.shared.result import Result
from app.domain.shared.value_objects.brazilian_phone import BrazilianPhone
from app.domain.shared.value_objects.email import Email
from app.domain.shared.value_objects.name import Name


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(slots=True, kw_only=True)
class User(BaseEntity):
    email: Email
    password_hash: str
    role: Role
    full_name: Name
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
        errors: list[FieldError] = []

        email_r = Email.create(email)
        if email_r.is_failure:
            errors.append(FieldError(code=email_r.error, field="email"))

        name_r = Name.create(full_name)
        if name_r.is_failure:
            errors.append(FieldError(code=name_r.error, field="full_name"))

        if not password_hash:
            errors.append(FieldError(code="PasswordHashCannotBeEmpty", field="password_hash"))

        phone_r = BrazilianPhone.create_if_not_empty(phone)
        if phone_r.is_failure:
            errors.append(FieldError(code=phone_r.error, field="phone"))

        if errors:
            return Result.failure_many(errors)

        return Result.success(cls(
            email=email_r.value,
            password_hash=password_hash,
            role=role,
            full_name=name_r.value,
            phone=phone_r.value,
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
