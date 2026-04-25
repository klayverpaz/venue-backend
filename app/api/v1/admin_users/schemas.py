from __future__ import annotations
from typing import Literal
from pydantic import BaseModel
from app.api.v1.auth.schemas import UserResponse  # reuse


AnyRole = Literal["admin", "owner", "customer"]


class ChangeRoleRequest(BaseModel):
    new_role: AnyRole


class ListUsersResponse(BaseModel):
    items: list[UserResponse]
