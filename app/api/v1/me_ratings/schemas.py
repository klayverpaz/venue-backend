from __future__ import annotations
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.use_cases.ratings.dtos import (
    PublicRatingDto, PublicRatingListDto, RatingDto, RatingListDto,
)


class CreateRatingBody(BaseModel):
    score: int
    comment: str | None = None


class UpdateRatingBody(BaseModel):
    """Both fields required: score must be present, comment is null|string.
    PATCH semantics here are PUT-like (whole-document replace of the two
    customer-mutable fields). See plan 09 design §3.4."""
    score: int
    comment: str | None = None


class RatingResponse(BaseModel):
    id: UUID
    booking_id: UUID
    resource_id: UUID
    customer_id: UUID
    score: int
    comment: str | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_dto(cls, dto: RatingDto) -> "RatingResponse":
        return cls(
            id=dto.id, booking_id=dto.booking_id,
            resource_id=dto.resource_id, customer_id=dto.customer_id,
            score=dto.score, comment=dto.comment,
            created_at=dto.created_at, updated_at=dto.updated_at,
        )


class RatingListResponse(BaseModel):
    items: list[RatingResponse]
    page: int
    page_size: int

    @classmethod
    def from_dto(cls, dto: RatingListDto) -> "RatingListResponse":
        return cls(
            items=[RatingResponse.from_dto(r) for r in dto.items],
            page=dto.page, page_size=dto.page_size,
        )


class PublicRatingResponse(BaseModel):
    score: int
    comment: str
    created_at: datetime

    @classmethod
    def from_dto(cls, dto: PublicRatingDto) -> "PublicRatingResponse":
        return cls(
            score=dto.score, comment=dto.comment,
            created_at=dto.created_at,
        )


class PublicRatingListResponse(BaseModel):
    items: list[PublicRatingResponse]
    page: int
    page_size: int

    @classmethod
    def from_dto(cls, dto: PublicRatingListDto) -> "PublicRatingListResponse":
        return cls(
            items=[PublicRatingResponse.from_dto(r) for r in dto.items],
            page=dto.page, page_size=dto.page_size,
        )
