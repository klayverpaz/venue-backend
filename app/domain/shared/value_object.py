from __future__ import annotations
from dataclasses import dataclass
from typing import Self
from app.domain.shared.result import Result


@dataclass(frozen=True, slots=True)
class BaseValueObject:
    """Base para Value Objects.

    Equality por valor vem de graça do `frozen=True` dataclass.

    ## Convenção (estabelecida pelos 14 VOs do Plan 03)

    Todo VO concreto:

    - É `@dataclass(frozen=True, slots=True)` herdando `BaseValueObject`.
    - Tem fábrica pública `cls.create(...) -> Result[Self]` — única forma de
      construir a partir de input não confiável. Falha com `Result.failure(<code>)`
      onde `<code>` é uma constante de classe (ver abaixo).
    - VOs string com nullability útil expõem `cls.create_if_not_empty(raw) ->
      Result[Self | None]` que retorna `Success(None)` para `None` ou string em branco.
      Usado em campos opcionais (e.g., `User.phone`).
    - VOs com validação simples inlinam tudo em `create()`. VOs com validação
      complexa (vários ramos, múltiplas mensagens) extraem `_validate(raw) -> str`
      privado-estático que retorna o code identifier ou string vazia.
    - **Mensagens de erro são códigos identificadores estáveis, não strings pt-BR.**
      Constante de classe nomeada `UPPER_SNAKE = "PascalCase"`. Ex.:
      `Email.EMAIL_CANNOT_BE_EMPTY = "EmailCannotBeEmpty"`. A tradução pt-BR vive
      em `app/api/error_codes.py`. Ver spec §3 decisão 15.
    - Limites (`MAX_LENGTH`, `MIN_VALUE`, `ALLOWED`) são constantes de classe
      expostas. Constantes que **não** são fields da dataclass precisam de
      `ClassVar[...]` quando têm anotação de tipo (caso contrário a dataclass tenta
      tornar-las fields e quebra). Constantes string sem anotação não precisam.
    - VOs string fazem `strip()` na entrada.
    - VOs compostos (e.g., `TimeWindow`, `DateTimeRange`) seguem o mesmo padrão
      com múltiplos fields; equality e hash continuam vindo do `frozen=True`.
    - `__str__` é definido em VOs string para serializar como o valor underlying.

    ## Reconstituição

    Construtor direto (`cls(value=...)`) é usado **apenas** para reconstituir
    dados confiáveis vindos do banco. Repositórios usam essa porta no
    `_to_entity` para evitar passar de novo pela validação. Em qualquer outro
    contexto (input de API, comando externo), use `cls.create(...)`.

    ## Adicionando um novo VO error code

    1. Declarar a constante na classe do VO: `FOO_INVALID = "FooInvalid"`.
    2. Adicionar entrada correspondente em `app/api/error_codes.py` no
       `ERROR_MESSAGES_PT_BR`.
    3. O architecture test em `tests/unit/architecture/test_error_code_coverage.py`
       falha CI se faltar tradução ou se a entrada virar órfã (constante removida).
    """

    @classmethod
    def create(cls, raw) -> Result[Self]:
        raise NotImplementedError
