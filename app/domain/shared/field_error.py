from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class FieldError:
    """Structured per-field error emitted by aggregators.

    Carried inside `Result.details` when an aggregate root or use-case handler
    aggregates multiple validation failures. Translated to pt-BR at the HTTP
    boundary via `app.api.error_codes.translate(code)`.
    """

    code: str
    field: str | None = None
