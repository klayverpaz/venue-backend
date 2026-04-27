from __future__ import annotations
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.notifications.notification import Notification
from app.domain.notifications.repository import INotificationRepository
from app.domain.notifications.service import NotifKind
from app.domain.shared.result import Result
from app.infrastructure.db.mappings.notification import NotificationModel


def _ensure_utc(dt: datetime | None) -> datetime | None:
    """SQLite + aiosqlite drop tzinfo on roundtrip; assume stored values are UTC."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _to_model_kwargs(notif: Notification) -> dict:
    return {
        "id": str(notif.id),
        "recipient_id": str(notif.recipient_id),
        "kind": notif.kind.value,
        "payload": dict(notif.payload),
        "read_at": notif.read_at,
        "created_at": notif.created_at,
        "updated_at": notif.updated_at,
    }


def _to_entity(model: NotificationModel) -> Notification:
    return Notification(
        id=UUID(str(model.id)),
        recipient_id=UUID(str(model.recipient_id)),
        kind=NotifKind(model.kind),
        payload=dict(model.payload or {}),
        read_at=_ensure_utc(model.read_at),
        created_at=_ensure_utc(model.created_at),
        updated_at=_ensure_utc(model.updated_at),
    )


class SQLAlchemyNotificationRepository(INotificationRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, notification: Notification) -> Result[None]:
        self._session.add(NotificationModel(**_to_model_kwargs(notification)))
        await self._session.flush()
        return Result.success(None)

    async def get_for_recipient(
        self, notification_id: UUID, recipient_id: UUID,
    ) -> Result[Notification | None]:
        stmt = select(NotificationModel).where(
            NotificationModel.id == str(notification_id),
            NotificationModel.recipient_id == str(recipient_id),
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return Result.success(_to_entity(row) if row else None)

    async def list_by_recipient(
        self,
        recipient_id: UUID,
        *,
        limit: int,
        cursor: UUID | None,
        unread_only: bool,
    ) -> Result[list[Notification]]:
        stmt = (
            select(NotificationModel)
            .where(NotificationModel.recipient_id == str(recipient_id))
            .order_by(NotificationModel.created_at.desc(), NotificationModel.id.desc())
            .limit(limit)
        )
        if unread_only:
            stmt = stmt.where(NotificationModel.read_at.is_(None))
        if cursor is not None:
            cursor_stmt = select(NotificationModel.created_at).where(
                NotificationModel.id == str(cursor),
                NotificationModel.recipient_id == str(recipient_id),
            )
            cursor_created = (
                await self._session.execute(cursor_stmt)
            ).scalar_one_or_none()
            if cursor_created is not None:
                stmt = stmt.where(
                    (NotificationModel.created_at < cursor_created)
                    | (
                        (NotificationModel.created_at == cursor_created)
                        & (NotificationModel.id < str(cursor))
                    )
                )
        rows = (await self._session.execute(stmt)).scalars().all()
        return Result.success([_to_entity(r) for r in rows])

    async def update(self, notification: Notification) -> Result[None]:
        stmt = select(NotificationModel).where(
            NotificationModel.id == str(notification.id),
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        if row is None:
            return Result.failure("NotificationNotFound", status_code=404)
        kwargs = _to_model_kwargs(notification)
        for k, v in kwargs.items():
            if k == "id":
                continue
            setattr(row, k, v)
        await self._session.flush()
        return Result.success(None)
