from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID

from app.domain.bookings.booking import Booking
from app.domain.bookings.booking_status import BookingStatus
from app.domain.bookings.repository import IBookingRepository
from app.domain.resources.repository import IResourceRepository
from app.domain.shared.result import Result
from app.domain.shared.value_objects.date_time_range import DateTimeRange
from app.domain.shared.weekday import Weekday
from app.use_cases.bookings.dtos import AgendaDto, AgendaSlotDto


_MAX_RANGE_DAYS = 31
_UTC = timezone.utc


@dataclass(frozen=True, kw_only=True, slots=True)
class GetAgendaQuery:
    range_start: datetime                # inclusive, UTC
    range_end: datetime                  # exclusive, UTC
    resource_id: UUID | None = None
    owner_slug: str | None = None
    resource_slug: str | None = None
    actor_id: UUID | None = None         # owner view if matches resource.owner_id


class GetAgendaHandler:
    def __init__(
        self,
        *,
        bookings: IBookingRepository,
        resources: IResourceRepository,
    ) -> None:
        self._bookings = bookings
        self._resources = resources

    async def handle(self, query: GetAgendaQuery) -> Result[AgendaDto]:
        if (query.range_end - query.range_start) > timedelta(days=_MAX_RANGE_DAYS):
            return Result.failure("AgendaRangeTooWide", status_code=422)

        if query.resource_id is not None:
            resource = await self._resources.get_by_id(query.resource_id)
        elif query.resource_slug is not None:
            resource = await self._resources.get_by_owner_slug_and_resource_slug(
                query.owner_slug or "", query.resource_slug,
            )
        else:
            return Result.failure("ResourceNotFound", status_code=404)

        if resource is None or resource.is_deleted():
            return Result.failure("ResourceNotFound", status_code=404)

        is_owner_view = (
            query.actor_id is not None and resource.owner_id == query.actor_id
        )

        bookings_r = await self._bookings.list_in_range_for_resource(
            resource.id, query.range_start, query.range_end,
        )
        if bookings_r.is_failure:
            return Result.from_failure(bookings_r)
        bookings = bookings_r.value

        slots = self._generate_slots(
            resource=resource,
            bookings=bookings,
            range_start=query.range_start,
            range_end=query.range_end,
            include_owner_detail=is_owner_view,
        )
        return Result.success(AgendaDto(resource_id=resource.id, slots=slots))

    @staticmethod
    def _generate_slots(
        *,
        resource,
        bookings: list[Booking],
        range_start: datetime,
        range_end: datetime,
        include_owner_detail: bool,
    ) -> tuple[AgendaSlotDto, ...]:
        slot_minutes = resource.slot_duration_minutes.minutes
        tz = resource.timezone.to_zoneinfo()
        local_start = range_start.astimezone(tz)
        local_end = range_end.astimezone(tz)

        approved = [b for b in bookings if b.status is BookingStatus.APPROVED]
        pending = [b for b in bookings if b.status is BookingStatus.PENDING]

        out: list[AgendaSlotDto] = []
        cursor = local_start
        while cursor < local_end:
            weekday = Weekday.from_iso(cursor.isoweekday())
            tod = cursor.time()
            windows = resource.operating_hours.for_weekday(weekday)
            window = next(
                (w for w in windows if w.start <= tod < w.end), None,
            )
            if window is None:
                cursor = cursor + timedelta(minutes=slot_minutes)
                continue

            slot_start = cursor
            slot_end = cursor + timedelta(minutes=slot_minutes)
            if slot_end.time() > window.end and slot_end.date() == cursor.date():
                cursor = slot_end
                continue

            slot_range_utc = DateTimeRange.create(
                start_at=slot_start.astimezone(_UTC),
                end_at=slot_end.astimezone(_UTC),
            ).value

            approved_match = next(
                (b for b in approved if b.slot_range.overlaps(slot_range_utc)),
                None,
            )
            pending_match = next(
                (b for b in pending if b.slot_range.overlaps(slot_range_utc)),
                None,
            )

            if approved_match is not None:
                status = "APPROVED"
                booking_id = approved_match.id if include_owner_detail else None
                customer_id = approved_match.customer_id if include_owner_detail else None
            elif pending_match is not None:
                status = "PENDING"
                booking_id = pending_match.id if include_owner_detail else None
                customer_id = pending_match.customer_id if include_owner_detail else None
            else:
                status = "AVAILABLE"
                booking_id = None
                customer_id = None

            price = resource.compute_price(slot_range_utc).cents
            out.append(AgendaSlotDto(
                slot_start_at=slot_range_utc.start_at,
                slot_end_at=slot_range_utc.end_at,
                status=status,
                price_cents=price,
                booking_id=booking_id,
                customer_id=customer_id,
            ))
            cursor = slot_end
        return tuple(out)
