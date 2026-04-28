from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable
from uuid import UUID

from app.domain.bookings.booking_status import BookingStatus
from app.domain.bookings.repository import IBookingRepository
from app.domain.ratings.rating import Rating
from app.domain.ratings.repository import IRatingRepository
from app.domain.shared.field_error import FieldError
from app.domain.shared.result import Result
from app.domain.shared.value_objects.rating_score import RatingScore
from app.domain.shared.value_objects.short_description import ShortDescription
from app.use_cases.ratings.dtos import RatingDto


_RATING_WINDOW_DAYS = 90


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True, kw_only=True, slots=True)
class CreateRatingCommand:
    actor_id: UUID
    booking_id: UUID
    score: int
    comment: str | None


class CreateRatingHandler:
    def __init__(
        self,
        *,
        ratings: IRatingRepository,
        bookings: IBookingRepository,
        clock: Callable[[], datetime] = _utcnow,
    ) -> None:
        self._ratings = ratings
        self._bookings = bookings
        self._clock = clock

    async def handle(self, cmd: CreateRatingCommand) -> Result[RatingDto]:
        # 1. VO-validate inputs.
        errors: list[FieldError] = []
        score_r = RatingScore.create(cmd.score)
        if score_r.is_failure:
            errors.append(FieldError(field="score", code=score_r.error))
        comment: ShortDescription | None = None
        if cmd.comment is not None and cmd.comment != "":
            note_r = ShortDescription.create(cmd.comment)
            if note_r.is_failure:
                errors.append(FieldError(field="comment", code=note_r.error))
            else:
                comment = note_r.value
        if errors:
            return Result.failure_many(errors, status_code=422)
        score = score_r.value

        # 2. Load booking; verify eligibility.
        booking_r = await self._bookings.get_by_id(cmd.booking_id)
        if booking_r.is_failure:
            return Result.from_failure(booking_r)
        booking = booking_r.value
        if booking is None:
            return Result.failure("BookingNotFound", status_code=404)

        if booking.customer_id != cmd.actor_id:
            return Result.failure("BookingNotEligibleForRating", status_code=422)
        if booking.status is not BookingStatus.APPROVED:
            return Result.failure("BookingNotEligibleForRating", status_code=422)

        now = self._clock()
        if booking.slot_range.end_at >= now:
            return Result.failure("BookingNotEligibleForRating", status_code=422)
        if now > booking.slot_range.end_at + timedelta(days=_RATING_WINDOW_DAYS):
            return Result.failure("BookingNotEligibleForRating", status_code=422)

        # 3. Dedup check (UNIQUE booking_id at the DB layer is the actual
        # race protection — this short-circuits the common single-shot case).
        existing = await self._ratings.get_by_booking_id(cmd.booking_id)
        if existing.is_failure:
            return Result.from_failure(existing)
        if existing.value is not None:
            return Result.failure("RatingAlreadyExists", status_code=409)

        # 4. Persist.
        rating = Rating.create(
            booking_id=booking.id,
            resource_id=booking.resource_id,
            customer_id=booking.customer_id,
            score=score,
            comment=comment,
            now=now,
        )
        add_r = await self._ratings.add(rating)
        if add_r.is_failure:
            return Result.from_failure(add_r)
        return Result.success(RatingDto.from_entity(rating))
