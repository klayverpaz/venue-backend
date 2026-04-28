from __future__ import annotations
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel

from app.api.v1.me_resources.schemas import ResourceResponse, ResourceListResponse


class OwnerPublicPageResponse(BaseModel):
    owner_id: UUID
    owner_slug: str
    full_name: str
    resources: list[ResourceResponse]
    owner_rating_avg: Decimal | None = None
    owner_rating_count: int = 0
