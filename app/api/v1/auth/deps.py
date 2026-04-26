from __future__ import annotations
from typing import Annotated
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_jwt_service
from app.core.config import Settings, get_settings
from app.domain.accounts.password_hasher import IPasswordHasher
from app.domain.accounts.repository import IUserRepository
from app.domain.accounts.jwt_service import IJwtService
from app.domain.subscriptions.repository import ISubscriptionRepository
from app.infrastructure.auth.argon2_password_hasher import Argon2PasswordHasher
from app.infrastructure.db.session import get_session
from app.infrastructure.repositories.owner_subscription_repository import (
    SQLAlchemyOwnerSubscriptionRepository,
)
from app.infrastructure.repositories.user_repository import UserRepository
from app.use_cases.accounts.commands.login import LoginHandler
from app.use_cases.accounts.commands.refresh_token import RefreshTokenHandler
from app.use_cases.accounts.commands.register_user import RegisterUserHandler
from app.use_cases.accounts.queries.get_user_by_id import GetUserByIdHandler


def get_user_repository(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> IUserRepository:
    return UserRepository(session)


def get_password_hasher() -> IPasswordHasher:
    s = get_settings()
    return Argon2PasswordHasher(
        time_cost=s.argon2_time_cost,
        memory_cost_kib=s.argon2_memory_cost_kib,
        parallelism=s.argon2_parallelism,
    )


def get_subscription_repository(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ISubscriptionRepository:
    return SQLAlchemyOwnerSubscriptionRepository(session)


def get_app_settings() -> Settings:
    return get_settings()


UserRepo = Annotated[IUserRepository, Depends(get_user_repository)]
Hasher = Annotated[IPasswordHasher, Depends(get_password_hasher)]
Jwt = Annotated[IJwtService, Depends(get_jwt_service)]
SubsRepo = Annotated[ISubscriptionRepository, Depends(get_subscription_repository)]
SettingsDep = Annotated[Settings, Depends(get_app_settings)]


def get_register_user_handler(
    repo: UserRepo, hasher: Hasher, subs: SubsRepo, settings: SettingsDep,
) -> RegisterUserHandler:
    return RegisterUserHandler(repo, hasher, subs, settings)


def get_login_handler(repo: UserRepo, hasher: Hasher, jwt: Jwt) -> LoginHandler:
    return LoginHandler(repo, hasher, jwt)


def get_refresh_token_handler(repo: UserRepo, jwt: Jwt) -> RefreshTokenHandler:
    return RefreshTokenHandler(repo, jwt)


def get_get_user_by_id_handler(repo: UserRepo) -> GetUserByIdHandler:
    return GetUserByIdHandler(repo)
