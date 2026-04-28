from __future__ import annotations
from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.api.deps import CurrentUser, require_role
from app.api.error_handler import unwrap
from app.api.v1.me_bookings.deps import (
    get_agenda_handler,
    get_list_resource_bookings_handler,
)
from app.api.v1.me_bookings.schemas import (
    AgendaResponse,
    BookingListResponse,
)
from app.domain.bookings.booking_status import BookingStatus
from app.use_cases.bookings.queries.get_agenda import (
    GetAgendaHandler,
    GetAgendaQuery,
)
from app.use_cases.bookings.queries.list_resource_bookings import (
    ListResourceBookingsHandler,
    ListResourceBookingsQuery,
)
from app.api.v1.me_resources.deps import (
    get_create_handler, get_update_metadata_handler, get_replace_hours_handler,
    get_replace_rules_handler, get_replace_base_attrs_handler,
    get_replace_custom_attrs_handler, get_set_base_price_handler,
    get_set_cutoff_handler, get_set_slot_duration_handler,
    get_publish_handler, get_unpublish_handler, get_soft_delete_handler,
    get_get_my_handler, get_list_my_handler,
)
from app.api.v1.me_resources.schemas import (
    CreateResourceBody, UpdateResourceBody, ReplaceOperatingHoursBody,
    ReplacePricingRulesBody, SetSlotDurationBody,
    ResourceResponse, ResourceListResponse,
)
from app.domain.accounts.role import Role
from app.domain.shared.weekday import Weekday
from app.use_cases.resources.commands.create_resource import (
    CreateResourceCommand, CustomAttributeInput, OperatingHoursInput,
    PricingRuleInput, TimeWindowInput,
)
from app.use_cases.resources.commands.update_resource_metadata import UpdateResourceMetadataCommand
from app.use_cases.resources.commands.replace_operating_hours import ReplaceOperatingHoursCommand
from app.use_cases.resources.commands.replace_pricing_rules import ReplacePricingRulesCommand
from app.use_cases.resources.commands.replace_base_attributes import ReplaceBaseAttributesCommand
from app.use_cases.resources.commands.replace_custom_attributes import ReplaceCustomAttributesCommand
from app.use_cases.resources.commands.set_base_price import SetBasePriceCommand
from app.use_cases.resources.commands.set_cancellation_cutoff import SetCancellationCutoffCommand
from app.use_cases.resources.commands.set_slot_duration import SetSlotDurationCommand
from app.use_cases.resources.commands.publish_resource import (
    PublishResourceCommand, UnpublishResourceCommand,
)
from app.use_cases.resources.commands.soft_delete_resource import SoftDeleteResourceCommand
from app.use_cases.resources.queries.get_my_resource import GetMyResourceQuery
from app.use_cases.resources.queries.list_my_resources import ListMyResourcesQuery


router = APIRouter(
    prefix="/v1/me/resources",
    tags=["me:resources"],
    dependencies=[Depends(require_role(Role.OWNER))],
)


def _hours_from_schema(body) -> OperatingHoursInput:
    days_dict = body.dict() if hasattr(body, "dict") else body.model_dump()
    days: dict[Weekday, list[TimeWindowInput]] = {}
    for wd in Weekday:
        windows = days_dict.get(wd.value.lower(), []) or []
        days[wd] = [TimeWindowInput(start=w["start"], end=w["end"]) for w in windows]
    return OperatingHoursInput(days=days)


def _rules_from_schema(rules) -> list[PricingRuleInput]:
    return [
        PricingRuleInput(
            weekdays=[Weekday(w) for w in r.weekdays],
            window=TimeWindowInput(start=r.window.start, end=r.window.end),
            price_cents=r.price_cents,
        )
        for r in rules
    ]


def _customs_from_schema(customs) -> list[CustomAttributeInput]:
    return [
        CustomAttributeInput(key=c.key, label=c.label, value=c.value)
        for c in customs
    ]


@router.post("", response_model=ResourceResponse, status_code=201)
async def create_resource(
    body: CreateResourceBody,
    user: CurrentUser,
    handler=Depends(get_create_handler),
):
    cmd = CreateResourceCommand(
        actor_id=user.user_id,
        resource_type_id=body.resource_type_id,
        slug=body.slug, name=body.name, description=body.description,
        city=body.city, region=body.region, timezone=body.timezone,
        slot_duration_minutes=body.slot_duration_minutes,
        operating_hours=_hours_from_schema(body.operating_hours),
        base_price_cents=body.base_price_cents,
        customer_cancellation_cutoff_hours=body.customer_cancellation_cutoff_hours,
        base_attributes=body.base_attributes,
        pricing_rules=_rules_from_schema(body.pricing_rules),
        custom_attributes=_customs_from_schema(body.custom_attributes),
    )
    dto = unwrap(await handler.handle(cmd))
    return ResourceResponse.from_dto(dto)


@router.get("", response_model=ResourceListResponse)
async def list_my_resources(
    user: CurrentUser,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    handler=Depends(get_list_my_handler),
):
    dtos = unwrap(await handler.handle(ListMyResourcesQuery(
        actor_id=user.user_id, limit=limit, offset=offset,
    )))
    return ResourceListResponse(
        items=[ResourceResponse.from_dto(d) for d in dtos],
        limit=limit, offset=offset,
    )


@router.get("/{resource_id}", response_model=ResourceResponse)
async def get_my_resource(
    resource_id: UUID,
    user: CurrentUser,
    handler=Depends(get_get_my_handler),
):
    dto = unwrap(await handler.handle(GetMyResourceQuery(
        actor_id=user.user_id, resource_id=resource_id,
    )))
    return ResourceResponse.from_dto(dto)


@router.patch("/{resource_id}", response_model=ResourceResponse)
async def patch_resource(
    resource_id: UUID,
    body: UpdateResourceBody,
    user: CurrentUser,
    update_metadata=Depends(get_update_metadata_handler),
    set_base_price=Depends(get_set_base_price_handler),
    set_cutoff=Depends(get_set_cutoff_handler),
    replace_base_attrs=Depends(get_replace_base_attrs_handler),
    replace_custom_attrs=Depends(get_replace_custom_attrs_handler),
    get_my=Depends(get_get_my_handler),
):
    if any(v is not None for v in (body.name, body.description, body.city, body.region)):
        unwrap(await update_metadata.handle(UpdateResourceMetadataCommand(
            actor_id=user.user_id, resource_id=resource_id,
            name=body.name, description=body.description,
            city=body.city, region=body.region,
        )))
    if body.base_price_cents is not None:
        unwrap(await set_base_price.handle(SetBasePriceCommand(
            actor_id=user.user_id, resource_id=resource_id,
            base_price_cents=body.base_price_cents,
        )))
    if body.customer_cancellation_cutoff_hours is not None:
        unwrap(await set_cutoff.handle(SetCancellationCutoffCommand(
            actor_id=user.user_id, resource_id=resource_id,
            hours=body.customer_cancellation_cutoff_hours,
        )))
    if body.base_attributes is not None:
        unwrap(await replace_base_attrs.handle(ReplaceBaseAttributesCommand(
            actor_id=user.user_id, resource_id=resource_id,
            base_attributes=body.base_attributes,
        )))
    if body.custom_attributes is not None:
        unwrap(await replace_custom_attrs.handle(ReplaceCustomAttributesCommand(
            actor_id=user.user_id, resource_id=resource_id,
            custom_attributes=_customs_from_schema(body.custom_attributes),
        )))
    dto = unwrap(await get_my.handle(GetMyResourceQuery(
        actor_id=user.user_id, resource_id=resource_id,
    )))
    return ResourceResponse.from_dto(dto)


@router.patch("/{resource_id}/operating-hours", response_model=ResourceResponse)
async def replace_operating_hours(
    resource_id: UUID,
    body: ReplaceOperatingHoursBody,
    user: CurrentUser,
    handler=Depends(get_replace_hours_handler),
    get_my=Depends(get_get_my_handler),
):
    unwrap(await handler.handle(ReplaceOperatingHoursCommand(
        actor_id=user.user_id, resource_id=resource_id,
        operating_hours=_hours_from_schema(body.operating_hours),
    )))
    dto = unwrap(await get_my.handle(GetMyResourceQuery(
        actor_id=user.user_id, resource_id=resource_id,
    )))
    return ResourceResponse.from_dto(dto)


@router.patch("/{resource_id}/pricing-rules", response_model=ResourceResponse)
async def replace_pricing_rules(
    resource_id: UUID,
    body: ReplacePricingRulesBody,
    user: CurrentUser,
    handler=Depends(get_replace_rules_handler),
    get_my=Depends(get_get_my_handler),
):
    unwrap(await handler.handle(ReplacePricingRulesCommand(
        actor_id=user.user_id, resource_id=resource_id,
        pricing_rules=_rules_from_schema(body.pricing_rules),
    )))
    dto = unwrap(await get_my.handle(GetMyResourceQuery(
        actor_id=user.user_id, resource_id=resource_id,
    )))
    return ResourceResponse.from_dto(dto)


@router.patch("/{resource_id}/slot-duration", response_model=ResourceResponse)
async def set_slot_duration(
    resource_id: UUID,
    body: SetSlotDurationBody,
    user: CurrentUser,
    handler=Depends(get_set_slot_duration_handler),
    get_my=Depends(get_get_my_handler),
):
    unwrap(await handler.handle(SetSlotDurationCommand(
        actor_id=user.user_id, resource_id=resource_id, minutes=body.minutes,
    )))
    dto = unwrap(await get_my.handle(GetMyResourceQuery(
        actor_id=user.user_id, resource_id=resource_id,
    )))
    return ResourceResponse.from_dto(dto)


@router.post("/{resource_id}/publish", response_model=ResourceResponse)
async def publish(
    resource_id: UUID,
    user: CurrentUser,
    handler=Depends(get_publish_handler),
    get_my=Depends(get_get_my_handler),
):
    unwrap(await handler.handle(PublishResourceCommand(
        actor_id=user.user_id, resource_id=resource_id,
    )))
    dto = unwrap(await get_my.handle(GetMyResourceQuery(
        actor_id=user.user_id, resource_id=resource_id,
    )))
    return ResourceResponse.from_dto(dto)


@router.post("/{resource_id}/unpublish", response_model=ResourceResponse)
async def unpublish(
    resource_id: UUID,
    user: CurrentUser,
    handler=Depends(get_unpublish_handler),
    get_my=Depends(get_get_my_handler),
):
    unwrap(await handler.handle(UnpublishResourceCommand(
        actor_id=user.user_id, resource_id=resource_id,
    )))
    dto = unwrap(await get_my.handle(GetMyResourceQuery(
        actor_id=user.user_id, resource_id=resource_id,
    )))
    return ResourceResponse.from_dto(dto)


@router.delete("/{resource_id}", status_code=204)
async def soft_delete(
    resource_id: UUID,
    user: CurrentUser,
    handler=Depends(get_soft_delete_handler),
):
    unwrap(await handler.handle(SoftDeleteResourceCommand(
        actor_id=user.user_id, resource_id=resource_id,
    )))
    return None


@router.get(
    "/{resource_id}/bookings",
    response_model=BookingListResponse,
)
async def list_resource_bookings(
    resource_id: UUID,
    user: CurrentUser,
    handler: Annotated[
        ListResourceBookingsHandler, Depends(get_list_resource_bookings_handler),
    ],
    status_filter: BookingStatus | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
):
    dto = unwrap(await handler.handle(ListResourceBookingsQuery(
        actor_id=user.user_id, resource_id=resource_id,
        status=status_filter, page=page, page_size=page_size,
    )))
    return BookingListResponse.from_dto(dto)


@router.get(
    "/{resource_id}/agenda",
    response_model=AgendaResponse,
)
async def get_owner_agenda(
    resource_id: UUID,
    user: CurrentUser,
    handler: Annotated[GetAgendaHandler, Depends(get_agenda_handler)],
    range_start: datetime = Query(..., alias="from"),
    range_end: datetime = Query(..., alias="to"),
):
    dto = unwrap(await handler.handle(GetAgendaQuery(
        resource_id=resource_id,
        range_start=range_start,
        range_end=range_end,
        actor_id=user.user_id,
    )))
    return AgendaResponse.from_dto(dto)
