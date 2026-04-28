from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable
from uuid import UUID

from app.domain.ratings.repository import IRatingRepository
from app.domain.shared.field_error import FieldError
from app.domain.shared.result import Result
from app.domain.shared.value_objects.rating_score import RatingScore
from app.domain.shared.value_objects.short_description import ShortDescription
from app.use_cases.ratings.dtos import RatingDto


_EDIT_WINDOW_DAYS = 7


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True, kw_only=True, slots=True)
class UpdateRatingCommand:
    actor_id: UUID
    booking_id: UUID         # route is booking-keyed; handler resolves to rating
    score: int
    comment: str | None


class UpdateRatingHandler:
    def __init__(
        self,
        *,
        ratings: IRatingRepository,
        clock: Callable[[], datetime] = _utcnow,
    ) -> None:
        self._ratings = ratings
        self._clock = clock

    async def handle(self, cmd: UpdateRatingCommand) -> Result[RatingDto]:
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

        # 2. Load rating by booking; verify ownership + edit window.
        rating_r = await self._ratings.get_by_booking_id(cmd.booking_id)
        if rating_r.is_failure:
            return Result.from_failure(rating_r)
        rating = rating_r.value
        if rating is None or rating.customer_id != cmd.actor_id:
            # Cross-customer access masked as not-found per spec §3.9 privacy
            # convention (matches Plan 08 BookingNotFound pattern).
            return Result.failure("RatingNotFound", status_code=404)

        now = self._clock()
        if now > rating.created_at + timedelta(days=_EDIT_WINDOW_DAYS):
            return Result.failure("RatingEditWindowExpired", status_code=403)

        # 3. Mutate + persist.
        rating.update_text(score=score_r.value, comment=comment, now=now)
        update_r = await self._ratings.update(rating)
        if update_r.is_failure:
            return Result.from_failure(update_r)
        return Result.success(RatingDto.from_entity(rating))
