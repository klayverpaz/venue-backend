from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, Generic, Optional, TypeVar

T = TypeVar("T")
U = TypeVar("U")


@dataclass(frozen=True, slots=True)
class Result(Generic[T]):
    """Wrapper sucesso/falha para evitar controle de fluxo por exceção."""
    is_success: bool
    value: Optional[T] = None
    error: Optional[str] = None
    status_code: Optional[int] = None

    def __post_init__(self) -> None:
        if self.is_success:
            if self.error is not None:
                raise ValueError("Error cannot be set for a successful result.")
        else:
            if self.value is not None:
                raise ValueError("Value cannot be set for a failure result.")

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
    def from_exception(exc: Exception, *, prefix: str | None = None) -> "Result[T]":
        msg = f"{exc.__class__.__name__}: {exc}"
        return Result.failure(f"{prefix}: {msg}" if prefix else msg)

    def map(self, fn: Callable[[T], U]) -> "Result[U]":
        if self.is_failure:
            return Result.failure(self.error or "Unknown error")
        try:
            return Result.success(fn(self.value))  # type: ignore[arg-type]
        except Exception as exc:
            return Result.from_exception(exc, prefix="Result.map failed")

    def unwrap_or(self, default: T) -> T:
        return self.value if self.is_success and self.value is not None else default
