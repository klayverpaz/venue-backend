from __future__ import annotations
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.shared.result import Result
from app.domain.subscriptions.owner_subscription import OwnerSubscription
from app.domain.subscriptions.sub_status import SubStatus
from app.infrastructure.db.mappings.owner_subscription import OwnerSubscriptionModel


def _ensure_utc(dt: datetime | None) -> datetime | None:
    """SQLite + aiosqlite drop tzinfo on roundtrip; assume stored values are UTC."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _to_entity(model: OwnerSubscriptionModel) -> OwnerSubscription:
    """Trusted reconstitution from DB row (bypasses factory validation)."""
    sub = OwnerSubscription(
        id=UUID(str(model.id)),
        owner_id=UUID(str(model.owner_id)),
        status=SubStatus(model.status),
        status_changed_at=_ensure_utc(model.status_changed_at),
        trial_ends_at=_ensure_utc(model.trial_ends_at),
    )
    sub.created_at = _ensure_utc(model.created_at)
    sub.updated_at = _ensure_utc(model.updated_at)
    return sub


def _to_model_kwargs(sub: OwnerSubscription) -> dict:
    return {
        "id": str(sub.id),
        "owner_id": str(sub.owner_id),
        "status": sub.status.value,
        "status_changed_at": sub.status_changed_at,
        "trial_ends_at": sub.trial_ends_at,
        "created_at": sub.created_at,
        "updated_at": sub.updated_at,
    }


class SQLAlchemyOwnerSubscriptionRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def add(self, sub: OwnerSubscription) -> Result[None]:
        model = OwnerSubscriptionModel(**_to_model_kwargs(sub))
        self._session.add(model)
        try:
            await self._session.flush()
        except IntegrityError:
            await self._session.rollback()
            return Result.failure("OwnerAlreadyHasSubscription", status_code=409)
        return Result.success(None)

    async def update(self, sub: OwnerSubscription) -> Result[None]:
        stmt = select(OwnerSubscriptionModel).where(
            OwnerSubscriptionModel.id == str(sub.id),
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        if row is None:
            return Result.failure("SubscriptionNotFound", status_code=404)
        row.status = sub.status.value
        row.status_changed_at = sub.status_changed_at
        row.trial_ends_at = sub.trial_ends_at
        row.updated_at = sub.updated_at
        await self._session.flush()
        return Result.success(None)

    async def get_by_id(self, sub_id: UUID) -> OwnerSubscription | None:
        stmt = select(OwnerSubscriptionModel).where(
            OwnerSubscriptionModel.id == str(sub_id),
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return _to_entity(row) if row else None

    async def get_by_owner_id(self, owner_id: UUID) -> OwnerSubscription | None:
        stmt = select(OwnerSubscriptionModel).where(
            OwnerSubscriptionModel.owner_id == str(owner_id),
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return _to_entity(row) if row else None

    async def list_all(
        self, *, status: str | None = None, limit: int = 50, offset: int = 0,
    ) -> list[OwnerSubscription]:
        stmt = select(OwnerSubscriptionModel).order_by(OwnerSubscriptionModel.created_at)
        if status is not None:
            stmt = stmt.where(OwnerSubscriptionModel.status == status)
        stmt = stmt.limit(limit).offset(offset)
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_entity(r) for r in rows]

    async def list_trialing_with_expiry_before(
        self, threshold: datetime,
    ) -> list[OwnerSubscription]:
        stmt = (
            select(OwnerSubscriptionModel)
            .where(OwnerSubscriptionModel.status == SubStatus.TRIALING.value)
            .where(OwnerSubscriptionModel.trial_ends_at < threshold)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_entity(r) for r in rows]

    async def list_by_owner_ids(self, owner_ids):
        ids_list = [str(i) for i in owner_ids]
        if not ids_list:
            return []
        stmt = select(OwnerSubscriptionModel).where(
            OwnerSubscriptionModel.owner_id.in_(ids_list),
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_entity(r) for r in rows]
