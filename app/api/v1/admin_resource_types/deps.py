from __future__ import annotations
from typing import Annotated
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.infrastructure.db.session import get_session
from app.infrastructure.repositories.resource_type_repository import (
    SQLAlchemyResourceTypeRepository,
)
from app.use_cases.catalog.commands.create_resource_type import CreateResourceTypeHandler
from app.use_cases.catalog.commands.delete_resource_type import DeleteResourceTypeHandler
from app.use_cases.catalog.commands.update_resource_type import UpdateResourceTypeHandler


async def get_resource_type_repo(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> SQLAlchemyResourceTypeRepository:
    return SQLAlchemyResourceTypeRepository(session)


async def get_create_handler(
    repo: Annotated[SQLAlchemyResourceTypeRepository, Depends(get_resource_type_repo)],
) -> CreateResourceTypeHandler:
    return CreateResourceTypeHandler(repo)


async def get_update_handler(
    repo: Annotated[SQLAlchemyResourceTypeRepository, Depends(get_resource_type_repo)],
) -> UpdateResourceTypeHandler:
    return UpdateResourceTypeHandler(repo)


async def get_delete_handler(
    repo: Annotated[SQLAlchemyResourceTypeRepository, Depends(get_resource_type_repo)],
) -> DeleteResourceTypeHandler:
    return DeleteResourceTypeHandler(repo)
