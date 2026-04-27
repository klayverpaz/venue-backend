from __future__ import annotations
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.accounts.role import Role
from app.domain.bookings.booking import Booking
from app.domain.bookings.booking_status import BookingStatus
from app.domain.bookings.repository import IBookingRepository
from app.domain.bookings.status_change import StatusChange
from app.domain.shared.result import Result
from app.domain.shared.value_objects.date_time_range import DateTimeRange
from app.domain.shared.value_objects.money import Money
from app.domain.shared.value_objects.short_description import ShortDescription
from app.infrastructure.db.mappings.booking import BookingModel


def _ensure_utc(dt: datetime | None) -> datetime | None:
    """SQLite + aiosqlite drop tzinfo on roundtrip; assume stored values are UTC."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _serialize_status_history(history: tuple[StatusChange, ...]) -> list[dict]:
    return [
        {
            "from_status": sc.from_status.value,
            "to_status": sc.to_status.value,
            "actor_id": str(sc.actor_id),
            "actor_role": sc.actor_role.value,
            "at": sc.at.isoformat(),
            "reason": sc.reason,
        }
        for sc in history
    ]


def _deserialize_status_history(rows: list[dict]) -> tuple[StatusChange, ...]:
    return tuple(
        StatusChange.create(
            from_status=BookingStatus(r["from_status"]),
            to_status=BookingStatus(r["to_status"]),
            actor_id=UUID(r["actor_id"]),
            actor_role=Role(r["actor_role"]),
            at=_ensure_utc(datetime.fromisoformat(r["at"])),
            reason=r.get("reason"),
        ).value
        for r in rows
    )


def _to_model_kwargs(b: Booking) -> dict:
    return {
        "id": str(b.id),
        "resource_id": str(b.resource_id),
        "customer_id": str(b.customer_id),
        "slot_start_at": b.slot_range.start_at,
        "slot_end_at": b.slot_range.end_at,
        "status": b.status.value,
        "customer_note": b.customer_note.value if b.customer_note else None,
        "total_price_cents": b.total_price_cents.cents,
        "status_history": _serialize_status_history(b.status_history),
        "created_at": b.created_at,
        "updated_at": b.updated_at,
    }


def _to_entity(m: BookingModel) -> Booking:
    note = (
        ShortDescription.create(m.customer_note).value
        if m.customer_note is not None else None
    )
    return Booking(
        id=UUID(str(m.id)),
        resource_id=UUID(str(m.resource_id)),
        customer_id=UUID(str(m.customer_id)),
        slot_range=DateTimeRange.create(
            start_at=_ensure_utc(m.slot_start_at),
            end_at=_ensure_utc(m.slot_end_at),
        ).value,
        status=BookingStatus(m.status),
        total_price_cents=Money.create(m.total_price_cents).value,
        customer_note=note,
        _status_history=_deserialize_status_history(m.status_history or []),
        created_at=_ensure_utc(m.created_at),
        updated_at=_ensure_utc(m.updated_at),
    )


def _overlaps_clause(slot_range: DateTimeRange):
    """Build a SQLAlchemy clause for half-open interval overlap:
    slot_start_at < range.end_at AND slot_end_at > range.start_at."""
    return and_(
        BookingModel.slot_start_at < slot_range.end_at,
        BookingModel.slot_end_at > slot_range.start_at,
    )


class SQLAlchemyBookingRepository(IBookingRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, booking: Booking) -> Result[None]:
        self._session.add(BookingModel(**_to_model_kwargs(booking)))
        await self._session.flush()
        return Result.success(None)

    async def get_by_id(self, booking_id: UUID) -> Result[Booking | None]:
        stmt = select(BookingModel).where(BookingModel.id == str(booking_id))
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return Result.success(_to_entity(row) if row else None)

    async def list_by_customer(
        self,
        customer_id: UUID,
        *,
        status: BookingStatus | None,
        page: int,
        page_size: int,
    ) -> Result[list[Booking]]:
        stmt = (
            select(BookingModel)
            .where(BookingModel.customer_id == str(customer_id))
            .order_by(BookingModel.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        if status is not None:
            stmt = stmt.where(BookingModel.status == status.value)
        rows = (await self._session.execute(stmt)).scalars().all()
        return Result.success([_to_entity(r) for r in rows])

    async def list_active_by_customer_for_resource(
        self,
        customer_id: UUID,
        resource_id: UUID,
        slot_range: DateTimeRange,
    ) -> Result[list[Booking]]:
        stmt = (
            select(BookingModel)
            .where(
                BookingModel.customer_id == str(customer_id),
                BookingModel.resource_id == str(resource_id),
                BookingModel.status.in_([
                    BookingStatus.PENDING.value,
                    BookingStatus.APPROVED.value,
                ]),
                _overlaps_clause(slot_range),
            )
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return Result.success([_to_entity(r) for r in rows])

    async def list_pending_overlapping(
        self,
        resource_id: UUID,
        slot_range: DateTimeRange,
        *,
        exclude_booking_id: UUID | None = None,
    ) -> Result[list[Booking]]:
        stmt = (
            select(BookingModel)
            .where(
                BookingModel.resource_id == str(resource_id),
                BookingModel.status == BookingStatus.PENDING.value,
                _overlaps_clause(slot_range),
            )
        )
        if exclude_booking_id is not None:
            stmt = stmt.where(BookingModel.id != str(exclude_booking_id))
        rows = (await self._session.execute(stmt)).scalars().all()
        return Result.success([_to_entity(r) for r in rows])

    async def list_by_resource(
        self,
        resource_id: UUID,
        *,
        status: BookingStatus | None,
        page: int,
        page_size: int,
    ) -> Result[list[Booking]]:
        stmt = (
            select(BookingModel)
            .where(BookingModel.resource_id == str(resource_id))
            .order_by(BookingModel.slot_start_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        if status is not None:
            stmt = stmt.where(BookingModel.status == status.value)
        rows = (await self._session.execute(stmt)).scalars().all()
        return Result.success([_to_entity(r) for r in rows])

    async def list_in_range_for_resource(
        self,
        resource_id: UUID,
        range_start: datetime,
        range_end: datetime,
    ) -> Result[list[Booking]]:
        stmt = (
            select(BookingModel)
            .where(
                BookingModel.resource_id == str(resource_id),
                BookingModel.slot_start_at < range_end,
                BookingModel.slot_end_at > range_start,
            )
            .order_by(BookingModel.slot_start_at)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return Result.success([_to_entity(r) for r in rows])

    async def list_pending_with_start_before(
        self, cutoff: datetime,
    ) -> Result[list[Booking]]:
        stmt = (
            select(BookingModel)
            .where(
                BookingModel.status == BookingStatus.PENDING.value,
                BookingModel.slot_start_at < cutoff,
            )
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return Result.success([_to_entity(r) for r in rows])

    async def list_pending_for_resource(
        self, resource_id: UUID,
    ) -> Result[list[Booking]]:
        stmt = (
            select(BookingModel)
            .where(
                BookingModel.resource_id == str(resource_id),
                BookingModel.status == BookingStatus.PENDING.value,
            )
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return Result.success([_to_entity(r) for r in rows])

    async def list_approved_with_start_after(
        self, resource_id: UUID, cutoff: datetime,
    ) -> Result[list[Booking]]:
        stmt = (
            select(BookingModel)
            .where(
                BookingModel.resource_id == str(resource_id),
                BookingModel.status == BookingStatus.APPROVED.value,
                BookingModel.slot_start_at >= cutoff,
            )
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return Result.success([_to_entity(r) for r in rows])

    async def update(self, booking: Booking) -> Result[None]:
        stmt = select(BookingModel).where(BookingModel.id == str(booking.id))
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        if row is None:
            return Result.failure("BookingNotFound", status_code=404)
        kwargs = _to_model_kwargs(booking)
        for k, v in kwargs.items():
            if k == "id":
                continue
            setattr(row, k, v)
        await self._session.flush()
        return Result.success(None)
