from __future__ import annotations
from typing import Annotated
from uuid import UUID
from fastapi import APIRouter, Depends, Query

from app.api.deps import require_role
from app.api.error_handler import unwrap
from app.api.v1.admin_users.deps import (
    get_deactivate_user_handler, get_promote_user_role_handler,
)
from app.api.v1.admin_users.schemas import ChangeRoleRequest, ListUsersResponse
from app.api.v1.auth.deps import UserRepo
from app.api.v1.auth.schemas import UserResponse
from app.domain.accounts.role import Role
from app.use_cases.accounts.commands.deactivate_user import (
    DeactivateUserCommand, DeactivateUserHandler,
)
from app.use_cases.accounts.commands.promote_user_role import (
    PromoteUserRoleCommand, PromoteUserRoleHandler,
)
from app.use_cases.accounts.dtos import UserDto


router = APIRouter(
    prefix="/v1/admin/users",
    tags=["admin", "users"],
    dependencies=[Depends(require_role(Role.ADMIN))],
)


@router.get("", response_model=ListUsersResponse)
async def list_users(
    repo: UserRepo,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> ListUsersResponse:
    users = await repo.list_active(limit=limit, offset=offset)
    items = [UserResponse.from_dto(UserDto.from_entity(u)) for u in users]
    return ListUsersResponse(items=items)


@router.post("/{user_id}/role", response_model=UserResponse)
async def change_role(
    user_id: UUID,
    req: ChangeRoleRequest,
    handler: Annotated[PromoteUserRoleHandler, Depends(get_promote_user_role_handler)],
) -> UserResponse:
    dto = unwrap(await handler.handle(PromoteUserRoleCommand(
        user_id=user_id, new_role=Role(req.new_role),
    )))
    return UserResponse.from_dto(dto)


@router.post("/{user_id}/deactivate", response_model=UserResponse)
async def deactivate(
    user_id: UUID,
    handler: Annotated[DeactivateUserHandler, Depends(get_deactivate_user_handler)],
) -> UserResponse:
    dto = unwrap(await handler.handle(DeactivateUserCommand(user_id=user_id)))
    return UserResponse.from_dto(dto)
