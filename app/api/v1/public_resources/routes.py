from __future__ import annotations
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.error_handler import unwrap
from app.api.v1.me_bookings.deps import get_agenda_handler
from app.api.v1.me_bookings.schemas import AgendaResponse
from app.api.v1.me_ratings.deps import get_list_public_ratings_handler
from app.api.v1.me_ratings.schemas import PublicRatingListResponse
from app.api.v1.me_resources.schemas import ResourceListResponse, ResourceResponse
from app.api.v1.public_resources.deps import (
    get_list_public_handler, get_owner_page_handler, get_public_resource_handler,
)
from app.api.v1.public_resources.schemas import OwnerPublicPageResponse
from app.use_cases.accounts.queries.get_owner_public_page import GetOwnerPublicPageQuery
from app.use_cases.bookings.queries.get_agenda import (
    GetAgendaHandler, GetAgendaQuery,
)
from app.use_cases.ratings.queries.list_public_ratings import (
    ListPublicRatingsForResourceHandler,
    ListPublicRatingsForResourceQuery,
)
from app.use_cases.resources.queries.get_public_resource import GetPublicResourceQuery
from app.use_cases.resources.queries.list_public_resources import ListPublicResourcesQuery


router = APIRouter(prefix="/v1", tags=["public:resources"])


@router.get("/resources", response_model=ResourceListResponse)
async def list_public_resources(
    type: str | None = Query(default=None, description="ResourceType slug"),
    city: str | None = Query(default=None),
    region: str | None = Query(default=None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    handler=Depends(get_list_public_handler),
):
    dtos = unwrap(await handler.handle(ListPublicResourcesQuery(
        resource_type_slug=type, city=city, region=region,
        limit=limit, offset=offset,
    )))
    return ResourceListResponse(
        items=[ResourceResponse.from_dto(d) for d in dtos],
        limit=limit, offset=offset,
    )


@router.get("/owners/{owner_slug}", response_model=OwnerPublicPageResponse)
async def get_owner_page(
    owner_slug: str,
    handler=Depends(get_owner_page_handler),
):
    page = unwrap(await handler.handle(GetOwnerPublicPageQuery(owner_slug=owner_slug)))
    return OwnerPublicPageResponse(
        owner_id=page.owner_id,
        owner_slug=page.owner_slug,
        full_name=page.full_name,
        resources=[ResourceResponse.from_dto(d) for d in page.resources],
        owner_rating_avg=page.owner_rating_avg,
        owner_rating_count=page.owner_rating_count,
    )


@router.get(
    "/owners/{owner_slug}/resources/{resource_slug}",
    response_model=ResourceResponse,
)
async def get_public_resource(
    owner_slug: str,
    resource_slug: str,
    handler=Depends(get_public_resource_handler),
):
    dto = unwrap(await handler.handle(GetPublicResourceQuery(
        owner_slug=owner_slug, resource_slug=resource_slug,
    )))
    return ResourceResponse.from_dto(dto)


@router.get(
    "/resources/{owner_slug}/{resource_slug}/agenda",
    response_model=AgendaResponse,
)
async def get_public_agenda(
    owner_slug: str,
    resource_slug: str,
    handler: Annotated[GetAgendaHandler, Depends(get_agenda_handler)],
    range_start: datetime = Query(..., alias="from"),
    range_end: datetime = Query(..., alias="to"),
):
    dto = unwrap(await handler.handle(GetAgendaQuery(
        owner_slug=owner_slug,
        resource_slug=resource_slug,
        range_start=range_start,
        range_end=range_end,
        actor_id=None,
    )))
    return AgendaResponse.from_dto(dto)


@router.get(
    "/owners/{owner_slug}/resources/{resource_slug}/ratings",
    response_model=PublicRatingListResponse,
)
async def list_public_ratings(
    owner_slug: str,
    resource_slug: str,
    handler: Annotated[
        ListPublicRatingsForResourceHandler,
        Depends(get_list_public_ratings_handler),
    ],
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
):
    dto = unwrap(await handler.handle(ListPublicRatingsForResourceQuery(
        owner_slug=owner_slug, resource_slug=resource_slug,
        page=page, page_size=page_size,
    )))
    return PublicRatingListResponse.from_dto(dto)
