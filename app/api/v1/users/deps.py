from __future__ import annotations
from typing import Annotated
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.use_cases.users.commands.create_user import CreateUserHandler
from app.use_cases.users.commands.update_user_email import UpdateUserEmailHandler
from app.use_cases.users.queries.get_user_by_email import GetUserByEmailHandler
from app.use_cases.users.queries.get_user_by_id import GetUserByIdHandler
from app.use_cases.users.queries.list_active_users import ListActiveUsersHandler
from app.domain.user.repository import IUserRepository
from app.infrastructure.db.session import get_session
from app.infrastructure.repositories.user_repository import UserRepository


def get_user_repository(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> IUserRepository:
    return UserRepository(session)


UserRepo = Annotated[IUserRepository, Depends(get_user_repository)]


def get_create_user_handler(repo: UserRepo) -> CreateUserHandler:
    return CreateUserHandler(repo)


def get_update_user_email_handler(repo: UserRepo) -> UpdateUserEmailHandler:
    return UpdateUserEmailHandler(repo)


def get_get_user_by_id_handler(repo: UserRepo) -> GetUserByIdHandler:
    return GetUserByIdHandler(repo)


def get_get_user_by_email_handler(repo: UserRepo) -> GetUserByEmailHandler:
    return GetUserByEmailHandler(repo)


def get_list_active_users_handler(repo: UserRepo) -> ListActiveUsersHandler:
    return ListActiveUsersHandler(repo)
