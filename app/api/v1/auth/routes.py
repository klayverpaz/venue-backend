from __future__ import annotations
from typing import Annotated
from fastapi import APIRouter, Depends

from app.api.deps import CurrentUser
from app.api.error_handler import unwrap
from app.api.v1.auth.deps import (
    get_get_user_by_id_handler, get_login_handler,
    get_refresh_token_handler, get_register_user_handler,
)
from app.api.v1.auth.schemas import (
    LoginRequest, RefreshRequest, RegisterRequest,
    TokenPairResponse, UserResponse,
)
from app.domain.accounts.role import Role
from app.use_cases.accounts.commands.login import LoginCommand, LoginHandler
from app.use_cases.accounts.commands.refresh_token import (
    RefreshTokenCommand, RefreshTokenHandler,
)
from app.use_cases.accounts.commands.register_user import (
    RegisterUserCommand, RegisterUserHandler,
)
from app.use_cases.accounts.queries.get_user_by_id import (
    GetUserByIdHandler, GetUserByIdQuery,
)


router = APIRouter(prefix="/v1", tags=["auth"])


@router.post("/auth/register", response_model=UserResponse, status_code=201)
async def register(
    req: RegisterRequest,
    handler: Annotated[RegisterUserHandler, Depends(get_register_user_handler)],
) -> UserResponse:
    dto = unwrap(await handler.handle(RegisterUserCommand(
        email=req.email, password=req.password,
        role=Role(req.role),
        full_name=req.full_name, phone=req.phone,
        public_slug=req.public_slug,
    )))
    return UserResponse.from_dto(dto)


@router.post("/auth/login", response_model=TokenPairResponse)
async def login(
    req: LoginRequest,
    handler: Annotated[LoginHandler, Depends(get_login_handler)],
) -> TokenPairResponse:
    dto = unwrap(await handler.handle(LoginCommand(
        email=req.email, password=req.password,
    )))
    return TokenPairResponse.from_dto(dto)


@router.post("/auth/refresh", response_model=TokenPairResponse)
async def refresh(
    req: RefreshRequest,
    handler: Annotated[RefreshTokenHandler, Depends(get_refresh_token_handler)],
) -> TokenPairResponse:
    dto = unwrap(await handler.handle(RefreshTokenCommand(refresh_token=req.refresh_token)))
    return TokenPairResponse.from_dto(dto)


@router.post("/auth/logout", status_code=204)
async def logout(_user: CurrentUser) -> None:
    """Stateless JWT — there's nothing to revoke server-side. Client drops the token.

    Returning 204 keeps the contract for the eventual blocklist-backed
    implementation (see Opportunities.md). The dep ensures the caller has a
    valid access token, so 401 leaks aren't possible from a missing-token call.
    """
    return None


@router.get("/me", response_model=UserResponse)
async def me(
    user: CurrentUser,
    handler: Annotated[GetUserByIdHandler, Depends(get_get_user_by_id_handler)],
) -> UserResponse:
    dto = unwrap(await handler.handle(GetUserByIdQuery(user_id=user.user_id)))
    return UserResponse.from_dto(dto)
