from __future__ import annotations
from typing import Annotated
from uuid import UUID
from fastapi import APIRouter, Depends, Query

from app.api.v1.users.deps import (
    get_create_user_handler, get_get_user_by_id_handler,
    get_list_active_users_handler, get_update_user_email_handler,
)
from app.api.error_handler import unwrap
from app.api.v1.users.schemas import (
    CreateUserRequest, ListUsersResponse, UpdateUserEmailRequest, UserResponse,
)
from app.use_cases.users.commands.create_user import CreateUserCommand, CreateUserHandler
from app.use_cases.users.commands.update_user_email import (
    UpdateUserEmailCommand, UpdateUserEmailHandler,
)
from app.use_cases.users.queries.get_user_by_id import GetUserByIdHandler, GetUserByIdQuery
from app.use_cases.users.queries.list_active_users import (
    ListActiveUsersHandler, ListActiveUsersQuery,
)

router = APIRouter(prefix="/v1/users", tags=["users"])


@router.post("", response_model=UserResponse, status_code=201)
async def create_user(
    req: CreateUserRequest,
    handler: Annotated[CreateUserHandler, Depends(get_create_user_handler)],
) -> UserResponse:
    result = await handler.handle(CreateUserCommand(
        name=req.name, email=req.email, phone=req.phone,
        credit_score=req.credit_score, balance=req.balance,
    ))
    return UserResponse.from_dto(unwrap(result))


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: UUID,
    handler: Annotated[GetUserByIdHandler, Depends(get_get_user_by_id_handler)],
) -> UserResponse:
    dto = unwrap(await handler.handle(GetUserByIdQuery(user_id=user_id)))
    return UserResponse.from_dto(dto)


@router.get("", response_model=ListUsersResponse)
async def list_users(
    handler: Annotated[ListActiveUsersHandler, Depends(get_list_active_users_handler)],
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> ListUsersResponse:
    items = unwrap(await handler.handle(ListActiveUsersQuery(limit=limit, offset=offset)))
    return ListUsersResponse(items=[UserResponse.from_dto(i) for i in items])


@router.patch("/{user_id}/email", response_model=UserResponse)
async def update_email(
    user_id: UUID,
    req: UpdateUserEmailRequest,
    handler: Annotated[UpdateUserEmailHandler, Depends(get_update_user_email_handler)],
) -> UserResponse:
    dto = unwrap(await handler.handle(UpdateUserEmailCommand(
        user_id=user_id, new_email=req.new_email,
    )))
    return UserResponse.from_dto(dto)
