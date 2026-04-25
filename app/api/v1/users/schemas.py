from __future__ import annotations
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field
from app.use_cases.users.dtos import UserDto


class CreateUserRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    email: str
    phone: str
    credit_score: float = 0.0
    balance: float = 0.0


class UpdateUserEmailRequest(BaseModel):
    new_email: str


class UserResponse(BaseModel):
    id: UUID
    name: str
    email: str
    phone: str
    phone_display: str
    credit_score: float
    balance: float
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_dto(cls, d: UserDto) -> "UserResponse":
        return cls(
            id=d.id, name=d.name, email=d.email, phone=d.phone,
            phone_display=d.phone_display,
            credit_score=d.credit_score, balance=d.balance,
            created_at=d.created_at, updated_at=d.updated_at,
        )


class ListUsersResponse(BaseModel):
    items: list[UserResponse]
