from __future__ import annotations
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.session import get_session
from app.infrastructure.repositories.resource_repository import SQLAlchemyResourceRepository
from app.infrastructure.repositories.resource_type_repository import SQLAlchemyResourceTypeRepository
from app.infrastructure.repositories.user_repository import UserRepository
from app.use_cases.resources.commands.create_resource import CreateResourceHandler
from app.use_cases.resources.commands.update_resource_metadata import UpdateResourceMetadataHandler
from app.use_cases.resources.commands.replace_operating_hours import ReplaceOperatingHoursHandler
from app.use_cases.resources.commands.replace_pricing_rules import ReplacePricingRulesHandler
from app.use_cases.resources.commands.replace_base_attributes import ReplaceBaseAttributesHandler
from app.use_cases.resources.commands.replace_custom_attributes import ReplaceCustomAttributesHandler
from app.use_cases.resources.commands.set_base_price import SetBasePriceHandler
from app.use_cases.resources.commands.set_cancellation_cutoff import SetCancellationCutoffHandler
from app.use_cases.resources.commands.set_slot_duration import SetSlotDurationHandler
from app.use_cases.resources.commands.publish_resource import (
    PublishResourceHandler, UnpublishResourceHandler,
)
from app.use_cases.resources.commands.soft_delete_resource import SoftDeleteResourceHandler
from app.use_cases.resources.queries.get_my_resource import GetMyResourceHandler
from app.use_cases.resources.queries.list_my_resources import ListMyResourcesHandler


def _r(s: Annotated[AsyncSession, Depends(get_session)]):
    return SQLAlchemyResourceRepository(s)


def _u(s: Annotated[AsyncSession, Depends(get_session)]):
    return UserRepository(s)


def _rt(s: Annotated[AsyncSession, Depends(get_session)]):
    return SQLAlchemyResourceTypeRepository(s)


async def get_create_handler(
    res=Depends(_r), rt=Depends(_rt), users=Depends(_u),
) -> CreateResourceHandler:
    return CreateResourceHandler(res, rt, users)


async def get_update_metadata_handler(res=Depends(_r)):
    return UpdateResourceMetadataHandler(res)


async def get_replace_hours_handler(res=Depends(_r)):
    return ReplaceOperatingHoursHandler(res)


async def get_replace_rules_handler(res=Depends(_r)):
    return ReplacePricingRulesHandler(res)


async def get_replace_base_attrs_handler(res=Depends(_r), rt=Depends(_rt)):
    return ReplaceBaseAttributesHandler(res, rt)


async def get_replace_custom_attrs_handler(res=Depends(_r)):
    return ReplaceCustomAttributesHandler(res)


async def get_set_base_price_handler(res=Depends(_r)):
    return SetBasePriceHandler(res)


async def get_set_cutoff_handler(res=Depends(_r)):
    return SetCancellationCutoffHandler(res)


async def get_set_slot_duration_handler(res=Depends(_r)):
    return SetSlotDurationHandler(res)


async def get_publish_handler(res=Depends(_r)):
    return PublishResourceHandler(res)


async def get_unpublish_handler(res=Depends(_r)):
    return UnpublishResourceHandler(res)


async def get_soft_delete_handler(res=Depends(_r)):
    return SoftDeleteResourceHandler(res)


async def get_get_my_handler(res=Depends(_r), u=Depends(_u), rt=Depends(_rt)):
    return GetMyResourceHandler(res, u, rt)


async def get_list_my_handler(res=Depends(_r), u=Depends(_u), rt=Depends(_rt)):
    return ListMyResourcesHandler(res, u, rt)
