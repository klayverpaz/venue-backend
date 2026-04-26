from __future__ import annotations
from typing import Literal
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field
from app.domain.accounts.role import Role
from app.use_cases.accounts.dtos import TokenPairDto, UserDto


SelfRegisterableRole = Literal["customer", "owner"]


class RegisterRequest(BaseModel):
    email: EmailStr
    # password is NOT VO-backed; API boundary owns the minimum-length policy.
    password: str = Field(min_length=8, max_length=200)
    role: SelfRegisterableRole
    # full_name and phone are VO-backed (Name, BrazilianPhone) — VOs own
    # length validation. Per spec §3 decision 17, the Pydantic boundary
    # does not duplicate length checks on VO-backed fields.
    full_name: str
    phone: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class UserResponse(BaseModel):
    id: UUID
    email: str
    role: Role
    full_name: str
    phone: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_dto(cls, dto: UserDto) -> "UserResponse":
        return cls(
            id=dto.id,
            email=dto.email,
            role=dto.role,
            full_name=dto.full_name,
            phone=dto.phone,
            is_active=dto.is_active,
            created_at=dto.created_at,
            updated_at=dto.updated_at,
        )


class TokenPairResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int
    user: UserResponse

    @classmethod
    def from_dto(cls, dto: TokenPairDto) -> "TokenPairResponse":
        return cls(
            access_token=dto.access_token,
            refresh_token=dto.refresh_token,
            token_type=dto.token_type,
            expires_in=dto.expires_in,
            user=UserResponse.from_dto(dto.user),
        )
