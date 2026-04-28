from __future__ import annotations
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.ratings.aggregate import RatingAggregate
from app.domain.ratings.rating import Rating
from app.domain.ratings.repository import IRatingRepository
from app.domain.shared.result import Result
from app.domain.shared.value_objects.rating_score import RatingScore
from app.domain.shared.value_objects.short_description import ShortDescription
from app.infrastructure.db.mappings.rating import RatingModel


def _ensure_utc(dt: datetime | None) -> datetime | None:
    """SQLite drops tzinfo on roundtrip; assume stored values are UTC."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _to_model_kwargs(r: Rating) -> dict:
    return {
        "id": str(r.id),
        "booking_id": str(r.booking_id),
        "resource_id": str(r.resource_id),
        "customer_id": str(r.customer_id),
        "score": r.score.value,
        "comment": r.comment.value if r.comment is not None else None,
        "created_at": r.created_at,
        "updated_at": r.updated_at,
    }


def _to_entity(m: RatingModel) -> Rating:
    return Rating(
        id=UUID(str(m.id)),
        booking_id=UUID(str(m.booking_id)),
        resource_id=UUID(str(m.resource_id)),
        customer_id=UUID(str(m.customer_id)),
        score=RatingScore.create(m.score).value,
        comment=(
            ShortDescription.create(m.comment).value
            if m.comment is not None else None
        ),
        created_at=_ensure_utc(m.created_at),
        updated_at=_ensure_utc(m.updated_at),
    )


class SQLAlchemyRatingRepository(IRatingRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, rating: Rating) -> Result[None]:
        self._session.add(RatingModel(**_to_model_kwargs(rating)))
        try:
            await self._session.flush()
        except IntegrityError:
            await self._session.rollback()
            return Result.failure("RatingAlreadyExists", status_code=409)
        return Result.success(None)

    async def update(self, rating: Rating) -> Result[None]:
        stmt = select(RatingModel).where(RatingModel.id == str(rating.id))
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        if row is None:
            return Result.failure("RatingNotFound", status_code=404)
        kwargs = _to_model_kwargs(rating)
        for k, v in kwargs.items():
            if k == "id":
                continue
            setattr(row, k, v)
        await self._session.flush()
        return Result.success(None)

    async def get_by_id(self, rating_id: UUID) -> Result[Rating | None]:
        stmt = select(RatingModel).where(RatingModel.id == str(rating_id))
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return Result.success(_to_entity(row) if row else None)

    async def get_by_booking_id(
        self, booking_id: UUID,
    ) -> Result[Rating | None]:
        stmt = select(RatingModel).where(
            RatingModel.booking_id == str(booking_id),
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return Result.success(_to_entity(row) if row else None)

    async def list_by_customer(
        self,
        customer_id: UUID,
        *,
        page: int,
        page_size: int,
    ) -> Result[list[Rating]]:
        stmt = (
            select(RatingModel)
            .where(RatingModel.customer_id == str(customer_id))
            .order_by(RatingModel.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return Result.success([_to_entity(r) for r in rows])

    async def list_with_comment_for_resource(
        self,
        resource_id: UUID,
        *,
        page: int,
        page_size: int,
    ) -> Result[list[Rating]]:
        stmt = (
            select(RatingModel)
            .where(
                RatingModel.resource_id == str(resource_id),
                RatingModel.comment.isnot(None),
            )
            .order_by(RatingModel.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return Result.success([_to_entity(r) for r in rows])

    async def get_aggregates_for_resources(
        self,
        resource_ids: list[UUID],
    ) -> Result[dict[UUID, RatingAggregate]]:
        out: dict[UUID, RatingAggregate] = {
            rid: RatingAggregate(avg_score=None, count=0)
            for rid in resource_ids
        }
        if not resource_ids:
            return Result.success(out)

        str_ids = [str(rid) for rid in resource_ids]
        stmt = (
            select(
                RatingModel.resource_id,
                func.avg(RatingModel.score).label("avg"),
                func.count(RatingModel.id).label("count"),
            )
            .where(RatingModel.resource_id.in_(str_ids))
            .group_by(RatingModel.resource_id)
        )
        rows = (await self._session.execute(stmt)).all()
        for r in rows:
            avg_value: Decimal | None = (
                Decimal(str(r.avg)).quantize(Decimal("0.1"))
                if r.avg is not None else None
            )
            count_value = int(r.count) if r.count is not None else 0
            out[UUID(str(r.resource_id))] = RatingAggregate(
                avg_score=avg_value, count=count_value,
            )
        return Result.success(out)
