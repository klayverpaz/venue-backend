from __future__ import annotations
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from app.api.deps import require_role
from app.api.error_codes import translate
from app.api.error_handler import unwrap
from app.api.v1.admin_resource_types.deps import (
    get_create_handler, get_delete_handler, get_resource_type_repo, get_update_handler,
)
from app.api.v1.admin_resource_types.schemas import (
    CreateResourceTypeRequest,
    ResourceTypeListResponse,
    ResourceTypeResponse,
    UpdateResourceTypeRequest,
)
from app.domain.accounts.role import Role
from app.infrastructure.repositories.resource_type_repository import SQLAlchemyResourceTypeRepository
from app.use_cases.catalog.commands.create_resource_type import (
    CreateResourceTypeCommand, CreateResourceTypeHandler,
)
from app.use_cases.catalog.commands.delete_resource_type import (
    DeleteResourceTypeCommand, DeleteResourceTypeHandler,
)
from app.use_cases.catalog.commands.update_resource_type import (
    UpdateResourceTypeCommand, UpdateResourceTypeHandler,
)
from app.use_cases.catalog.dtos import ResourceTypeDto


router = APIRouter(
    prefix="/v1/admin/resource-types",
    tags=["admin:catalog"],
    dependencies=[Depends(require_role(Role.ADMIN))],
)


@router.post("", response_model=ResourceTypeResponse, status_code=201)
async def create_resource_type(
    body: CreateResourceTypeRequest,
    handler: CreateResourceTypeHandler = Depends(get_create_handler),
):
    cmd = CreateResourceTypeCommand(
        slug=body.slug,
        name=body.name,
        description=body.description,
        attribute_schema=[a.model_dump() for a in body.attribute_schema],
        is_active=body.is_active,
    )
    dto: ResourceTypeDto = unwrap(await handler.handle(cmd))
    return ResourceTypeResponse.from_dto(dto)


@router.get("", response_model=ResourceTypeListResponse)
async def list_resource_types(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    repo: SQLAlchemyResourceTypeRepository = Depends(get_resource_type_repo),
):
    rows = await repo.list_all(limit=limit, offset=offset)
    return ResourceTypeListResponse(
        items=[ResourceTypeResponse.from_dto(ResourceTypeDto.from_entity(rt)) for rt in rows],
        limit=limit,
        offset=offset,
    )


@router.get("/{rt_id}", response_model=ResourceTypeResponse)
async def get_resource_type(
    rt_id: UUID,
    repo: SQLAlchemyResourceTypeRepository = Depends(get_resource_type_repo),
):
    rt = await repo.get_by_id(rt_id)
    if rt is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "ResourceTypeNotFound", "message": translate("ResourceTypeNotFound")},
        )
    return ResourceTypeResponse.from_dto(ResourceTypeDto.from_entity(rt))


@router.patch("/{rt_id}", response_model=ResourceTypeResponse)
async def update_resource_type(
    rt_id: UUID,
    body: UpdateResourceTypeRequest,
    handler: UpdateResourceTypeHandler = Depends(get_update_handler),
):
    cmd = UpdateResourceTypeCommand(
        id=rt_id,
        name=body.name,
        description=body.description,
        attribute_schema=(
            [a.model_dump() for a in body.attribute_schema]
            if body.attribute_schema is not None
            else None
        ),
        is_active=body.is_active,
    )
    dto = unwrap(await handler.handle(cmd))
    return ResourceTypeResponse.from_dto(dto)


@router.delete("/{rt_id}", status_code=204)
async def delete_resource_type(
    rt_id: UUID,
    handler: DeleteResourceTypeHandler = Depends(get_delete_handler),
):
    unwrap(await handler.handle(DeleteResourceTypeCommand(id=rt_id)))
    return None
