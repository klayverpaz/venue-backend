from __future__ import annotations
from dataclasses import dataclass
from typing import Self
from app.domain.shared.result import Result


@dataclass(frozen=True, slots=True)
class BaseValueObject:
    """Base para VOs. Equality por valor (via frozen dataclass).

    Criação pública via classmethod `create(raw) -> Result[Self]` que
    sanitiza e valida. Construtor direto (`cls(value=...)`) é usado só
    para reconstituição de dados confiáveis (vindos do DB)."""

    @classmethod
    def create(cls, raw) -> Result[Self]:
        raise NotImplementedError
