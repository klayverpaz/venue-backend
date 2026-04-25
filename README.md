# venue-backend

Backend Python para uma plataforma de aluguel de espaços por slots horários. Três papéis (Admin, Owner, Customer), com cada Owner gerenciando um ou mais `Resource`s rentáveis e Customers solicitando bookings que o Owner aprova ou rejeita.

Design: [docs/superpowers/specs/2026-04-25-venue-backend-design.md](docs/superpowers/specs/2026-04-25-venue-backend-design.md).
Planos: [docs/superpowers/plans/](docs/superpowers/plans/).
Construído sobre o template `ai-ready-backend-template` (módulo de IA removido).

## Estrutura

Vertical slicing por feature dentro de cada camada — adicionar uma feature é criar uma pasta nova em cada camada, sem tocar nas outras.

```
app/
├── api/
│   ├── deps.py              # DI cross-cutting (futuras: get_current_user, etc.)
│   └── v1/
│       ├── router.py        # APIRouter agregador
│       ├── users/           # uma pasta por feature
│       │   ├── routes.py
│       │   ├── schemas.py
│       │   └── deps.py
│       └── reports/           # endpoints analíticos
│           ├── routes.py
│           ├── schemas.py
│           └── deps.py
├── use_cases/
│   ├── users/               # CQRS dentro da feature
│   │   ├── dtos.py
│   │   ├── commands/
│   │   └── queries/
│   └── reports/             # Analytics — só queries (Q anêmico)
│       ├── dtos.py
│       └── queries/
├── domain/
│   ├── shared/              # shared kernel + VOs reutilizáveis
│   │   ├── entity.py        # BaseEntity
│   │   ├── result.py        # Result
│   │   ├── value_object.py
│   │   └── value_objects/   # Email, Percentage, BrazilianPhone, …
│   └── user/                # um aggregate por pasta
│       ├── user.py          # entidade rica
│       └── repository.py    # IUserRepository (Protocol)
├── infrastructure/
│   ├── cache/               # cache_service + redis_client
│   ├── db/
│   │   ├── base.py          # Base SQLAlchemy + TimestampMixin
│   │   ├── session.py
│   │   └── mappings/        # ORM mappings (UserModel, …)
│   └── repositories/        # implementações concretas
├── core/                    # config, logging, context
├── migrations/              # Alembic
└── main.py
```

Regra de dependência: `api → use_cases → domain ← infrastructure`. `domain/` é puro Python e jamais importa de `infrastructure/` ou `use_cases/`.

## Setup

**Pré-requisitos:** Python 3.12, `uv`, Docker (para Redis local).

```bash
# 1. Cria venv (com pip) e instala deps (base + dev)
make install

# 2. Instala o driver do DB escolhido
make install-postgres      # ou make install-mssql

# 3. Configura o ambiente
cp .env.example .env
# Edite .env com suas credenciais
```

**Redis local (via Docker):**
```bash
make redis-dev
```

## Migrations

```bash
make migrate-new msg="add <entidade>"   # cria revision
make migrate-up                          # aplica
make migrate-down                        # reverte 1
make migrate-history                     # lista
```

## Rodando

```bash
make run
# ou ./start_services.sh
```

Swagger em [http://localhost:8000/docs](http://localhost:8000/docs).

## Testes

```bash
make test                                # pytest
make lint                                # ruff + mypy
```

Estrutura espelha o `app/` (vertical slicing):
- `tests/unit/domain/shared/` — VOs e shared kernel, sem I/O.
- `tests/unit/domain/<feature>/` — entity da feature.
- `tests/unit/use_cases/<feature>s/{commands,queries,fakes}/` — handlers com fakes in-memory.
- `tests/integration/<feature>s/` — repositórios com SQLite in-memory.
- `tests/e2e/<feature>s/` — API completa via httpx.

## Adicionando uma nova feature

Para adicionar uma nova feature `<feature>` (ex.: `project`):

### 1. Domain
```
app/domain/<feature>/
├── __init__.py
├── <feature>.py        # entidade rica (estende BaseEntity)
└── repository.py       # interface I<Feature>Repository (Protocol)
```
VOs específicos da feature ficam aqui. VOs reutilizáveis sobem para `domain/shared/value_objects/`.

### 2. Infrastructure
```
app/infrastructure/db/mappings/<feature>.py            # <Feature>Model(Base, TimestampMixin)
app/infrastructure/repositories/<feature>_repository.py
```
Adicionar import em `app/migrations/env.py`:
```python
from app.infrastructure.db.mappings import <feature>  # noqa: F401
```
Gerar migration: `make migrate-new msg="add_<feature>s_table"`.

### 3. Use Cases
```
app/use_cases/<feature>s/
├── __init__.py
├── dtos.py
├── commands/
│   ├── __init__.py
│   └── create_<feature>.py     # CreateXCommand + CreateXHandler
└── queries/
    ├── __init__.py
    └── get_<feature>_by_id.py
```

### 4. API
```
app/api/v1/<feature>s/
├── __init__.py        # re-exporta `router`
├── routes.py
├── schemas.py
└── deps.py            # get_<feature>_repository + handlers DI
```
Registrar em `app/api/v1/router.py`:
```python
from app.api.v1.<feature>s import router as <feature>s_router
api_router.include_router(<feature>s_router)
```

### 5. Tests
```
tests/unit/domain/<feature>/test_<feature>.py
tests/unit/use_cases/<feature>s/
├── fakes/in_memory_<feature>_repository.py
├── commands/test_create_<feature>.py
├── queries/test_get_<feature>_by_id.py
└── test_dtos.py
tests/integration/<feature>s/test_repository.py
tests/e2e/<feature>s/test_api.py
```

### Regras de dependência

- **Cross-feature em `domain/`**: PROIBIDO. Se duas features compartilham conceito, ele sobe para `domain/shared/`.
- **Cross-feature em `use_cases/`**: handler pode depender de **interfaces** (Protocols) de outra feature, nunca de implementações concretas.
- **Direção do fluxo**: API → Use Cases → Domain → Shared. Nunca o oposto.
- **`domain/shared/`**: zona estável; mudanças impactam tudo — exigir review extra.

### Regra cross-entity (sem camada de serviço)

Não existe `services/` — o handler **é** a camada de serviço. Para uma regra que envolve duas features (ex.: `Project` + `User`), o handler recebe os dois repositórios via DI:

```python
# app/use_cases/projects/commands/assign_owner.py
class AssignProjectOwnerHandler:
    def __init__(
        self,
        projects: IProjectRepository,   # interface da feature dona
        users: IUserRepository,         # interface da outra feature
    ) -> None:
        self._projects = projects
        self._users = users

    async def handle(self, cmd: AssignProjectOwnerCommand) -> Result[ProjectDto]:
        user = await self._users.get_by_id(cmd.user_id)
        if user is None:
            return Result.failure("Usuário não encontrado.", status_code=404)
        project = await self._projects.get_by_id(cmd.project_id)
        if project is None:
            return Result.failure("Projeto não encontrado.", status_code=404)
        r = project.assign_owner(user)        # regra de domínio na entidade
        if r.is_failure:
            return Result.failure(r.error, status_code=422)
        await self._projects.update(project)
        return Result.success(ProjectDto.from_entity(project))
```

Anti-patterns: handler chamando outro handler, importar `UserRepository` (impl concreta) em vez de `IUserRepository`, ou colocar a regra em `routes.py`.

## Analytics / Relatórios

Features analíticas seguem um padrão diferente do CRUD com domínio rico: elas **não criam pasta em `domain/`**. O lado de leitura do CQRS pode ser "Q anêmico" — SQL direto via `sqlalchemy.text(...)` para um DTO frozen-dataclass, sem reidratar aggregates.

Exemplo canônico: [`app/use_cases/reports/queries/active_users_by_month.py`](app/use_cases/reports/queries/active_users_by_month.py).

Para adicionar um novo relatório, siga **Recipe D** em [docs/template-customization.md](docs/template-customization.md).

## Stack

| Camada | Ferramenta |
|---|---|
| HTTP | FastAPI + Starlette + Uvicorn |
| Validação HTTP | Pydantic v2 |
| Config | pydantic-settings |
| ORM | SQLAlchemy 2.0 async |
| Migrations | Alembic |
| DB | PostgreSQL (recomendado) ou SQL Server |
| Cache/Sessão | Redis (ou Valkey) |
| Testes | pytest + pytest-asyncio + aiosqlite |
| Lint/Type | ruff + mypy |

## Licenças

Todos os componentes base são gratuitos para uso comercial em produto próprio. Detalhes do raciocínio de licenças por componente: ver a [especificação do template-base](docs/superpowers/specs/2026-04-24-backend-template-design.md#2-stack-e-rationale-de-licenças) (este projeto herda essas escolhas).

Produção 100% permissiva: PostgreSQL + Valkey.
