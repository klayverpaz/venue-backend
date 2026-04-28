from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID

from app.domain.bookings.booking import Booking
from app.domain.bookings.repository import IBookingRepository
from app.domain.notifications.service import INotificationService, NotifKind
from app.domain.resources.repository import IResourceRepository
from app.domain.shared.field_error import FieldError
from app.domain.shared.result import Result
from app.domain.shared.value_objects.date_time_range import DateTimeRange
from app.domain.shared.value_objects.short_description import ShortDescription
from app.domain.shared.weekday import Weekday
from app.domain.subscriptions.repository import ISubscriptionRepository
from app.use_cases.bookings.dtos import BookingDto


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True, kw_only=True, slots=True)
class RequestBookingCommand:
    actor_id: UUID                       # customer
    resource_id: UUID
    slot_start_at: datetime
    slot_end_at: datetime
    customer_note: str | None


class RequestBookingHandler:
    def __init__(
        self,
        *,
        bookings: IBookingRepository,
        resources: IResourceRepository,
        subscriptions: ISubscriptionRepository,
        notifications: INotificationService,
    ) -> None:
        self._bookings = bookings
        self._resources = resources
        self._subscriptions = subscriptions
        self._notifications = notifications

    async def handle(self, cmd: RequestBookingCommand) -> Result[BookingDto]:
        # 1. VO-validate inputs.
        errors: list[FieldError] = []
        slot_r = DateTimeRange.create(
            start_at=cmd.slot_start_at, end_at=cmd.slot_end_at,
        )
        if slot_r.is_failure:
            errors.append(FieldError(field="slot_range", code=slot_r.error))
        note: ShortDescription | None = None
        if cmd.customer_note is not None and cmd.customer_note != "":
            note_r = ShortDescription.create(cmd.customer_note)
            if note_r.is_failure:
                errors.append(FieldError(field="customer_note", code=note_r.error))
            else:
                note = note_r.value
        if errors:
            return Result.failure_many(errors, status_code=422)
        slot_range = slot_r.value

        # 2. Resource lookup + soft-delete + published gates.
        # IResourceRepository.get_by_id returns Resource | None (not Result).
        resource = await self._resources.get_by_id(cmd.resource_id)
        if resource is None or resource.is_deleted():
            return Result.failure("ResourceNotFound", status_code=404)
        if not resource.is_published:
            return Result.failure("ResourceNotPublished", status_code=404)

        # 3. Owner subscription operational.
        # ISubscriptionRepository.get_by_owner_id returns OwnerSubscription | None.
        sub = await self._subscriptions.get_by_owner_id(resource.owner_id)
        if sub is None or not sub.status.is_operational():
            # Same code as unpublished — don't reveal owner state to customer.
            return Result.failure("ResourceNotPublished", status_code=404)

        # 4. Slot must be in the future.
        if slot_range.start_at <= _utcnow():
            return Result.failure("BookingSlotInPast", status_code=422)

        # 5. Slot grid alignment + operating hours containment.
        align_r = self._validate_alignment_and_hours(resource, slot_range)
        if align_r.is_failure:
            return Result.from_failure(align_r)

        # 6. Natural dedup.
        actives_r = await self._bookings.list_active_by_customer_for_resource(
            cmd.actor_id, resource.id, slot_range,
        )
        if actives_r.is_failure:
            return Result.from_failure(actives_r)
        if actives_r.value:
            return Result.failure("BookingAlreadyExists", status_code=409)

        # 7. Compute price + persist.
        price = resource.compute_price(slot_range)
        booking = Booking.create_pending(
            resource_id=resource.id,
            customer_id=cmd.actor_id,
            slot_range=slot_range,
            total_price_cents=price,
            customer_note=note,
            now=_utcnow(),
        )
        add_r = await self._bookings.add(booking)
        if add_r.is_failure:
            return Result.from_failure(add_r)

        # 8. Notify owner (fire-and-forget).
        await self._notifications.notify(
            recipient_id=resource.owner_id,
            kind=NotifKind.BOOKING_REQUESTED,
            payload={
                "booking_id": str(booking.id),
                "resource_id": str(resource.id),
                "customer_id": str(cmd.actor_id),
                "slot_start_at": slot_range.start_at.isoformat(),
                "slot_end_at": slot_range.end_at.isoformat(),
            },
        )
        return Result.success(BookingDto.from_entity(booking))

    @staticmethod
    def _validate_alignment_and_hours(
        resource, slot_range: DateTimeRange,
    ) -> Result[None]:
        slot_minutes = resource.slot_duration_minutes.minutes
        tz = resource.timezone.to_zoneinfo()
        # Alignment in local time: minutes-from-midnight must be a multiple
        # of slot_duration; total duration must also be a multiple.
        local_start = slot_range.start_at.astimezone(tz)
        local_end = slot_range.end_at.astimezone(tz)
        start_minutes = local_start.hour * 60 + local_start.minute
        duration = slot_range.duration_minutes()
        if (start_minutes % slot_minutes) != 0 or (duration % slot_minutes) != 0:
            return Result.failure("BookingSlotNotAligned", status_code=422)

        # Containment: walk slot-by-slot in local time; each slot's local
        # start time must fall inside some operating-hours window of its weekday.
        cursor = local_start
        while cursor < local_end:
            weekday = Weekday.from_iso(cursor.isoweekday())
            tod = cursor.time()
            windows = resource.operating_hours.for_weekday(weekday)
            in_window = any(w.start <= tod < w.end for w in windows)
            if not in_window:
                return Result.failure(
                    "BookingOutsideOperatingHours", status_code=422,
                )
            cursor = cursor + timedelta(minutes=slot_minutes)
        return Result.success(None)
