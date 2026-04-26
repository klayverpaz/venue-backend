from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Callable, Generic, Iterable, Optional, TypeVar

from app.domain.shared.field_error import FieldError

T = TypeVar("T")
U = TypeVar("U")


@dataclass(frozen=True, slots=True)
class Result(Generic[T]):
    """Wrapper sucesso/falha para evitar controle de fluxo por exceção."""
    is_success: bool
    value: Optional[T] = None
    error: Optional[str] = None
    details: Optional[tuple[FieldError, ...]] = None
    status_code: Optional[int] = None

    def __post_init__(self) -> None:
        if self.is_success:
            if self.error is not None or self.details is not None:
                raise ValueError("Successful result cannot carry error/details.")
        else:
            if self.value is not None:
                raise ValueError("Value cannot be set for a failure result.")
            if (self.error is None) == (self.details is None):
                raise ValueError(
                    "Failed result must have exactly one of error or details."
                )

    @property
    def is_failure(self) -> bool:
        return not self.is_success

    @staticmethod
    def success(value: Optional[T] = None, *, status_code: Optional[int] = None) -> "Result[T]":
        return Result(is_success=True, value=value, error=None, status_code=status_code)

    @staticmethod
    def failure(error: str, *, status_code: Optional[int] = None) -> "Result[T]":
        return Result(is_success=False, value=None, error=error, status_code=status_code)

    @staticmethod
    def failure_many(
        errors: Iterable[FieldError],
        *,
        status_code: Optional[int] = None,
    ) -> "Result[T]":
        details = tuple(errors)
        if not details:
            raise ValueError("failure_many requires at least one FieldError.")
        return Result(is_success=False, details=details, status_code=status_code)

    @staticmethod
    def from_failure(
        other: "Result[Any]",
        *,
        status_code: Optional[int] = None,
    ) -> "Result[T]":
        """Re-wrap a failed Result preserving error vs. details path; useful in
        handlers that need to convert Result[User] → Result[UserDto] on failure."""
        if other.is_success:
            raise ValueError("from_failure called on a successful Result.")
        sc = status_code if status_code is not None else other.status_code
        if other.details is not None:
            return Result.failure_many(other.details, status_code=sc)
        return Result.failure(other.error or "InternalError", status_code=sc)

    @staticmethod
    def from_exception(exc: Exception, *, prefix: str | None = None) -> "Result[T]":
        msg = f"{exc.__class__.__name__}: {exc}"
        return Result.failure(f"{prefix}: {msg}" if prefix else msg)

    def map(self, fn: Callable[[T], U]) -> "Result[U]":
        if self.is_failure:
            if self.details is not None:
                return Result.failure_many(self.details, status_code=self.status_code)
            return Result.failure(self.error or "Unknown error", status_code=self.status_code)
        try:
            return Result.success(fn(self.value))  # type: ignore[arg-type]
        except Exception as exc:
            return Result.from_exception(exc, prefix="Result.map failed")

    def unwrap_or(self, default: T) -> T:
        return self.value if self.is_success and self.value is not None else default
