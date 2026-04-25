# Backend Template Restructure — Design

**Date:** 2026-04-24
**Status:** Draft for review
**Scope:** Estrutural-only refactor of `app/` and `tests/`. Zero mudança comportamental.

## Contexto e motivação

O `backend-template` hoje tem features espalhadas em arquivos planos: `app/api/v1/users.py` e `app/api/v1/schemas.py` no mesmo nível, `app/application/commands/create_user.py` ao lado de queries soltas, `app/domain/user/` ao lado de `common/` e `value_objects/`. Adicionar uma segunda feature (ex.: `project`) hoje significa misturar tudo em arquivos compartilhados — péssima coesão, conflitos de merge, baixa replicabilidade.

O objetivo deste refactor é tornar o template **vertical-sliced por feature**, de forma que adicionar uma nova feature seja apenas criar uma pasta nova em cada camada (`domain/<feature>/`, `application/<feature>/`, `api/v1/<feature>/`, `infrastructure/db/mappings/<feature>.py`, `tests/unit/.../​<feature>/`), sem tocar em features existentes.

Não é refactor comportamental. Toda lógica de negócio permanece idêntica. Schema do banco preservado. Testes existentes continuam todos verdes (mesma quantidade, só renomeados/realocados).

## Decisões arquiteturais (registradas durante brainstorm)

1. **`api/v1/`** → vertical slicing por feature, com `router.py` agregador.
2. **`application/`** → vertical slicing (feature no topo, `commands/queries/dtos.py` dentro).
3. **`domain/`** → `common/` + `value_objects/` consolidados em `shared/` (com `entity.py`, `result.py`, `value_object.py` e subpasta `value_objects/`).
4. **`infrastructure/db/models/`** → renomeado para `mappings/` (deixa de confundir com domain).
5. **`infrastructure/repositories/`** → permanece flat. Implementações de repositório continuam aqui, sem agrupamento por feature.
6. **`api/deps.py`** central permanece (DI cross-cutting), mas DI específica de feature vai para `api/v1/<feature>/deps.py`.
7. **AI module** → só `api/v1/ai_chat.py` vira pasta `ai_chat/`. O módulo `app/ai/` (graph, nodes, tools) permanece intacto.
8. **Convenção de nomes (híbrido)**: entidade do domain mantém nome (`user/user.py`); ORM mapping perde sufixo (`mappings/user.py`); commands/queries mantêm nome do caso de uso (`create_user.py`).
9. **`tests/`** espelha 100% a nova estrutura, incluindo `unit/`, `integration/` e `e2e/`.

## Estrutura final

```
app/
  main.py
  core/                          # intacto
  ai/                            # intacto — orquestração LangGraph

  api/
    __init__.py
    deps.py                      # DI cross-cutting (get_session; futuros: get_current_user)
    error_handler.py             # intacto
    middleware.py                # intacto
    v1/
      __init__.py
      router.py                  # APIRouter() agregando features
      users/
        __init__.py              # re-exporta `router`
        routes.py                # endpoints
        schemas.py               # Pydantic request/response
        deps.py                  # get_user_repository + handlers DI
      ai_chat/
        __init__.py              # re-exporta `router`
        routes.py

  application/
    __init__.py
    users/
      __init__.py
      dtos.py                    # UserDto
      commands/
        __init__.py
        create_user.py
        update_user_email.py
      queries/
        __init__.py
        get_user_by_id.py
        get_user_by_email.py
        list_active_users.py

  domain/
    __init__.py
    shared/                      # ex-common: shared kernel + VOs genéricos
      __init__.py
      entity.py                  # BaseEntity
      result.py                  # Result
      value_object.py            # ValueObject base
      value_objects/
        __init__.py
        email.py
        brazilian_phone.py
        percentage.py
        non_negative_float.py
    user/
      __init__.py
      user.py                    # entidade
      repository.py              # IUserRepository (Protocol)

  infrastructure/
    __init__.py
    cache/                       # intacto: cache_service.py + redis_client.py
    db/
      __init__.py
      base.py                    # Base + TimestampMixin (intacto)
      session.py                 # intacto
      mappings/                  # ex-models/
        __init__.py
        user.py                  # classe UserModel (sem prefixo no nome do arquivo)
    repositories/                # flat, sem subpastas por feature
      __init__.py
      base_repository.py
      user_repository.py

  migrations/                    # intacto — só atualiza imports em env.py

tests/
  conftest.py
  unit/
    core/                        # intacto
    application/
      users/
        __init__.py
        fakes/
          __init__.py
          in_memory_user_repository.py
        commands/
          __init__.py
          test_create_user.py
          test_update_user_email.py
        queries/
          __init__.py
          test_get_user_by_id.py
          test_get_user_by_email.py
          test_list_active_users.py
        test_dtos.py
    domain/
      shared/
        __init__.py
        test_entity.py
        test_result.py
        value_objects/
          __init__.py
          test_email.py
          test_brazilian_phone.py
          test_percentage.py
          test_non_negative_float.py
      user/
        __init__.py
        test_user.py
  integration/
    __init__.py
    conftest.py
    users/
      __init__.py
      test_repository.py
  e2e/
    __init__.py
    conftest.py
    users/
      __init__.py
      test_api.py
```

## Mapa de movimentações (origem → destino)

### `api/`

| Origem | Destino |
|---|---|
| `app/api/v1/users.py` | `app/api/v1/users/routes.py` |
| `app/api/v1/schemas.py` | `app/api/v1/users/schemas.py` |
| `app/api/v1/ai_chat.py` | `app/api/v1/ai_chat/routes.py` |
| `app/api/deps.py` (funções `get_user_repository` + `get_*_handler`) | `app/api/v1/users/deps.py` |
| `app/api/deps.py` (resto) | permanece (cross-cutting; pode ficar com docstring + futuras DIs) |
| **NOVO** | `app/api/v1/router.py` |
| **NOVO** | `app/api/v1/users/__init__.py` (re-exporta `router`) |
| **NOVO** | `app/api/v1/ai_chat/__init__.py` (re-exporta `router`) |

### `application/`

| Origem | Destino |
|---|---|
| `app/application/dtos.py` | `app/application/users/dtos.py` |
| `app/application/commands/create_user.py` | `app/application/users/commands/create_user.py` |
| `app/application/commands/update_user_email.py` | `app/application/users/commands/update_user_email.py` |
| `app/application/queries/get_user_by_id.py` | `app/application/users/queries/get_user_by_id.py` |
| `app/application/queries/get_user_by_email.py` | `app/application/users/queries/get_user_by_email.py` |
| `app/application/queries/list_active_users.py` | `app/application/users/queries/list_active_users.py` |
| `app/application/commands/__init__.py` | **deletar** (pasta `commands/` vazia também) |
| `app/application/queries/__init__.py` | **deletar** (pasta `queries/` vazia também) |

### `domain/`

| Origem | Destino |
|---|---|
| `app/domain/common/entity.py` | `app/domain/shared/entity.py` |
| `app/domain/common/result.py` | `app/domain/shared/result.py` |
| `app/domain/common/value_object.py` | `app/domain/shared/value_object.py` |
| `app/domain/value_objects/email.py` | `app/domain/shared/value_objects/email.py` |
| `app/domain/value_objects/brazilian_phone.py` | `app/domain/shared/value_objects/brazilian_phone.py` |
| `app/domain/value_objects/percentage.py` | `app/domain/shared/value_objects/percentage.py` |
| `app/domain/value_objects/non_negative_float.py` | `app/domain/shared/value_objects/non_negative_float.py` |
| `app/domain/user/user_repository.py` | `app/domain/user/repository.py` |
| `app/domain/common/` (pasta) | **deletar** após migração |
| `app/domain/value_objects/` (pasta) | **deletar** após migração |

### `infrastructure/`

| Origem | Destino |
|---|---|
| `app/infrastructure/db/models/user_model.py` | `app/infrastructure/db/mappings/user.py` (classe permanece `UserModel`) |
| `app/infrastructure/db/models/__init__.py` | `app/infrastructure/db/mappings/__init__.py` |
| `app/infrastructure/db/models/` (pasta) | **deletar** após migração |

### `tests/`

| Origem | Destino |
|---|---|
| `tests/unit/application/test_create_user_handler.py` | `tests/unit/application/users/commands/test_create_user.py` |
| `tests/unit/application/test_update_user_email_handler.py` | `tests/unit/application/users/commands/test_update_user_email.py` |
| `tests/unit/application/test_get_user_by_id_handler.py` | `tests/unit/application/users/queries/test_get_user_by_id.py` |
| `tests/unit/application/test_get_user_by_email_handler.py` | `tests/unit/application/users/queries/test_get_user_by_email.py` |
| `tests/unit/application/test_list_active_users_handler.py` | `tests/unit/application/users/queries/test_list_active_users.py` |
| `tests/unit/application/test_dtos.py` | `tests/unit/application/users/test_dtos.py` |
| `tests/unit/application/fakes/in_memory_user_repository.py` | `tests/unit/application/users/fakes/in_memory_user_repository.py` |
| `tests/unit/domain/common/test_entity.py` | `tests/unit/domain/shared/test_entity.py` |
| `tests/unit/domain/common/test_result.py` | `tests/unit/domain/shared/test_result.py` |
| `tests/unit/domain/value_objects/test_email.py` | `tests/unit/domain/shared/value_objects/test_email.py` |
| `tests/unit/domain/value_objects/test_brazilian_phone.py` | `tests/unit/domain/shared/value_objects/test_brazilian_phone.py` |
| `tests/unit/domain/value_objects/test_percentage.py` | `tests/unit/domain/shared/value_objects/test_percentage.py` |
| `tests/unit/domain/value_objects/test_non_negative_float.py` | `tests/unit/domain/shared/value_objects/test_non_negative_float.py` |
| `tests/unit/domain/common/` (pasta) | **deletar** após migração |
| `tests/unit/domain/value_objects/` (pasta) | **deletar** após migração |
| `tests/integration/test_user_repository.py` | `tests/integration/users/test_repository.py` |
| `tests/e2e/test_users_api.py` | `tests/e2e/users/test_api.py` |
| `tests/unit/application/fakes/__init__.py` (pasta antiga) | **deletar** após migração |

## Imports — busca-substitua global

| De | Para |
|---|---|
| `from app.api.v1.schemas import` | `from app.api.v1.users.schemas import` |
| `from app.api.deps import get_user_repository` | `from app.api.v1.users.deps import get_user_repository` |
| `from app.api.deps import get_create_user_handler` | `from app.api.v1.users.deps import get_create_user_handler` |
| `from app.api.deps import get_update_user_email_handler` | `from app.api.v1.users.deps import get_update_user_email_handler` |
| `from app.api.deps import get_get_user_by_id_handler` | `from app.api.v1.users.deps import get_get_user_by_id_handler` |
| `from app.api.deps import get_get_user_by_email_handler` | `from app.api.v1.users.deps import get_get_user_by_email_handler` |
| `from app.api.deps import get_list_active_users_handler` | `from app.api.v1.users.deps import get_list_active_users_handler` |
| `from app.application.dtos import UserDto` | `from app.application.users.dtos import UserDto` |
| `from app.application.commands.create_user import` | `from app.application.users.commands.create_user import` |
| `from app.application.commands.update_user_email import` | `from app.application.users.commands.update_user_email import` |
| `from app.application.queries.get_user_by_id import` | `from app.application.users.queries.get_user_by_id import` |
| `from app.application.queries.get_user_by_email import` | `from app.application.users.queries.get_user_by_email import` |
| `from app.application.queries.list_active_users import` | `from app.application.users.queries.list_active_users import` |
| `from app.domain.common.entity import` | `from app.domain.shared.entity import` |
| `from app.domain.common.result import` | `from app.domain.shared.result import` |
| `from app.domain.common.value_object import` | `from app.domain.shared.value_object import` |
| `from app.domain.value_objects.email import` | `from app.domain.shared.value_objects.email import` |
| `from app.domain.value_objects.brazilian_phone import` | `from app.domain.shared.value_objects.brazilian_phone import` |
| `from app.domain.value_objects.percentage import` | `from app.domain.shared.value_objects.percentage import` |
| `from app.domain.value_objects.non_negative_float import` | `from app.domain.shared.value_objects.non_negative_float import` |
| `from app.domain.user.user_repository import` | `from app.domain.user.repository import` |
| `from app.infrastructure.db.models.user_model import` | `from app.infrastructure.db.mappings.user import` |
| `from app.infrastructure.db.models import user_model` | `from app.infrastructure.db.mappings import user` |
| `from app.api.v1.users import router as users_router` (em `main.py`) | `from app.api.v1.router import api_router` |

## Novos arquivos `__init__.py` e `router.py`

### `app/api/v1/users/__init__.py`

```python
from .routes import router

__all__ = ["router"]
```

### `app/api/v1/ai_chat/__init__.py`

```python
from .routes import router

__all__ = ["router"]
```

### `app/api/v1/router.py`

```python
from fastapi import APIRouter

from app.api.v1.users import router as users_router

api_router = APIRouter()
api_router.include_router(users_router)
```

> O `ai_chat_router` continua sendo incluído condicionalmente em `app/main.py` no `lifespan` (depende de `settings.ai_provider != "none"`), portanto não entra no `api_router` global.

### `app/main.py` — diff conceitual

```python
# remover
from app.api.v1.users import router as users_router
...
app.include_router(users_router)

# adicionar
from app.api.v1.router import api_router
...
app.include_router(api_router)
```

A inclusão condicional do `ai_chat_router` (dentro do `lifespan`) continua **idêntica em código** — a linha `from app.api.v1.ai_chat import router as ai_chat_router` segue funcionando porque o novo `app/api/v1/ai_chat/__init__.py` re-exporta `router` a partir de `routes.py`. Nenhuma alteração necessária nesta linha.

### `app/migrations/env.py` — diff conceitual

```python
# de
from app.infrastructure.db.models import user_model  # noqa: F401

# para
from app.infrastructure.db.mappings import user  # noqa: F401
```

## Riscos e mitigações

| Risco | Mitigação |
|---|---|
| Modelo SQLAlchemy não registrado em `Base.metadata` (Alembic perde a tabela). | Após o refactor, rodar `make migrate-new msg="post_refactor_check"` e confirmar **diff vazio**. Apagar a migration depois. |
| Re-export quebrado em `__init__.py`. | Cada `__init__.py` novo de pasta de feature re-exporta `router` (`api/v1/users/__init__.py`, `api/v1/ai_chat/__init__.py`). Smoke test: `python -c "from app.main import app"`. |
| Pytest não descobre testes em pastas novas. | Toda pasta nova de teste recebe `__init__.py` (`tests/unit/application/users/__init__.py`, `commands/`, `queries/`, `fakes/`, etc.). |
| `IUserRepository` (Protocol) — rename do arquivo. | Structural typing; basta atualizar imports. Sem risco runtime. |
| `api/deps.py` central fica vazio após mover handlers de user. | Aceito. Permanece como ponto de entrada para futuras DIs cross-cutting (ex.: `get_current_user`). Adicionar docstring explicativo. |

## Validação ao final do refactor

Sequência obrigatória — todos os passos têm que passar antes de declarar "feito":

1. **Smoke import:**
   `.venv/bin/python -c "from app.main import app"`
2. **Test suite completa:**
   `make test` — toda a suite (unit + integration + e2e) verde, com a **mesma quantidade de testes** que antes do refactor.
3. **Schema preservado (Alembic):**
   `make migrate-new msg="post_refactor_check"` → migration gerada deve estar **vazia** (sem alterações de schema). Apagar a migration após verificar.
4. **Startup runtime:**
   `make run` (ou `.venv/bin/python -m app.main`) sobe sem erro; `GET /health` responde 200.

## O que NÃO muda

- `app/core/` — config, logging, context.
- `app/ai/` — graph, nodes, tools, state, streaming, model_factory, context. (Estruturalmente intacto. Atenção: `app/ai/tools/get_user_by_email.py` consome `app.application.queries.get_user_by_email` e portanto SOFRE atualização de import pela busca-substitua global, mesmo o módulo `app/ai/` permanecendo no lugar.)
- `app/infrastructure/cache/` — `cache_service.py` e `redis_client.py` permanecem separados (decisão registrada na análise: são camadas distintas — client de baixo nível vs serviço de aplicação).
- `app/infrastructure/db/base.py` — `Base` + `TimestampMixin`.
- `app/infrastructure/db/session.py`.
- `app/infrastructure/repositories/` — pasta flat. Apenas atualiza imports internos.
- `app/api/error_handler.py`, `app/api/middleware.py`.
- `app/migrations/versions/*` — migrations existentes intactas.
- Lógica de negócio — refactor é **estrutural-only**, zero mudança comportamental.
- `Dockerfile`, `Makefile`, `pytest.ini`, `pyrightconfig.json`, `requirements*.txt`, `start_services.sh`, `alembic.ini`, `.env.example`.

## Critério de "feito"

- [ ] Todos os arquivos movidos conforme mapa de movimentações.
- [ ] Todos os imports atualizados (busca-substitua global).
- [ ] Novos arquivos criados: `app/api/v1/router.py`, `app/api/v1/users/__init__.py`, `app/api/v1/ai_chat/__init__.py`, `app/api/v1/users/deps.py`, todos os `__init__.py` necessários.
- [ ] Pastas antigas deletadas: `app/domain/common/`, `app/domain/value_objects/`, `app/application/commands/`, `app/application/queries/`, `app/infrastructure/db/models/`, `tests/unit/domain/common/`, `tests/unit/domain/value_objects/`.
- [ ] Arquivos antigos deletados: `app/api/v1/schemas.py`, `app/api/v1/users.py`, `app/api/v1/ai_chat.py` (substituídos pelas pastas).
- [ ] `make test` 100% verde, mesmo número de testes que antes.
- [ ] `make migrate-new` gera migration vazia.
- [ ] `app/main.py` sobe sem erro; `/health` 200.
- [ ] Documentação de "Adding a new feature" adicionada ao `README.md` ou `docs/architecture.md`.

## Padrão para futuras features (entregável final do refactor)

Esta seção é parte da entrega — vai virar documentação no `README.md` ou `docs/architecture.md` para que o template seja replicável.

### Checklist "adicionar feature `X`"

Para criar uma nova feature (ex.: `project`):

**1. Domain**

```
app/domain/project/
  __init__.py
  project.py            # entidade rica (estende BaseEntity)
  repository.py         # interface IProjectRepository (Protocol)
```

- VOs específicos da feature ficam aqui (ex.: `project/project_status.py`).
- Quando um VO passar a ser reutilizado por outra feature → mover para `domain/shared/value_objects/`.

**2. Infrastructure (persistência)**

```
app/infrastructure/db/mappings/project.py        # ProjectModel(Base, TimestampMixin)
app/infrastructure/repositories/project_repository.py
```

- Adicionar import em `app/migrations/env.py`:
  `from app.infrastructure.db.mappings import project  # noqa: F401`
- Gerar migration: `make migrate-new msg="add_projects_table"`.

**3. Application**

```
app/application/projects/
  __init__.py
  dtos.py
  commands/
    __init__.py
    create_project.py     # CreateProjectCommand + CreateProjectHandler
    ...
  queries/
    __init__.py
    get_project_by_id.py
    list_projects.py
    ...
```

**4. API**

```
app/api/v1/projects/
  __init__.py             # re-exporta router
  routes.py               # endpoints
  schemas.py              # Pydantic request/response
  deps.py                 # get_project_repository + handlers DI
```

Registrar em `app/api/v1/router.py`:

```python
from app.api.v1.projects import router as projects_router
api_router.include_router(projects_router)
```

**5. Tests**

```
tests/unit/domain/project/test_project.py
tests/unit/application/projects/
  fakes/in_memory_project_repository.py
  commands/test_create_project.py
  queries/test_get_project_by_id.py
  test_dtos.py
tests/integration/projects/test_repository.py
tests/e2e/projects/test_api.py
```

### Regras de coesão e dependência

- **Cross-feature em `domain/`**: PROIBIDO. `domain/project/project.py` não importa de `domain/user/`. Se duas features compartilham conceito, ele sobe para `domain/shared/`.
- **Cross-feature em `application/`**: handler de uma feature pode depender de **interfaces** (Protocols) de outra, nunca de implementações concretas. Ex.: `CreateProjectHandler` pode receber `IUserRepository` injetado, jamais importar `UserRepository`.
- **Direção do fluxo de dependência**: API → Application → Domain → Shared. Nunca o oposto. `domain/` jamais importa de `infrastructure/` ou `application/`.
- **`shared/` é zona estável**: VOs e blocos compartilhados raramente mudam. Mudança em `shared/` impacta TUDO — exigir review extra.

## Próximos passos

Após aprovação desta spec:

1. Invocar a skill `writing-plans` para gerar plano de implementação detalhado (ordem das movimentações, validações intermediárias, comandos `git mv`).
2. Executar o plano.
3. Atualizar documentação (`README.md` ou novo `docs/architecture.md`) com o playbook "Adding a new feature".
