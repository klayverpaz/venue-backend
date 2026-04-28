from __future__ import annotations
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, field_serializer

from app.api.v1.me_resources.schemas import ResourceResponse, ResourceListResponse


class OwnerPublicPageResponse(BaseModel):
    owner_id: UUID
    owner_slug: str
    full_name: str
    resources: list[ResourceResponse]
    owner_rating_avg: Decimal | None = None
    owner_rating_count: int = 0

    @field_serializer("owner_rating_avg")
    def _serialize_owner_rating_avg(self, v: Decimal | None) -> float | None:
        return float(v) if v is not None else None
