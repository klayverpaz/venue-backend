from __future__ import annotations
from fastapi import APIRouter, Depends, Query
from app.api.v1.admin_resource_types.deps import get_resource_type_repo
from app.api.v1.admin_resource_types.schemas import ResourceTypeResponse
from app.api.v1.catalog.schemas import ResourceTypeListResponse
from app.infrastructure.repositories.resource_type_repository import SQLAlchemyResourceTypeRepository
from app.use_cases.catalog.dtos import ResourceTypeDto


router = APIRouter(prefix="/v1/catalog", tags=["catalog"])


@router.get("/resource-types", response_model=ResourceTypeListResponse)
async def list_active_resource_types(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    repo: SQLAlchemyResourceTypeRepository = Depends(get_resource_type_repo),
):
    rows = await repo.list_active(limit=limit, offset=offset)
    return ResourceTypeListResponse(
        items=[ResourceTypeResponse.from_dto(ResourceTypeDto.from_entity(rt)) for rt in rows],
        limit=limit,
        offset=offset,
    )
