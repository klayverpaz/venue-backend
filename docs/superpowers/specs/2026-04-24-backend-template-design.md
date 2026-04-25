# Backend Template — Design

**Data:** 2026-04-24
**Autor:** Klayver (via brainstorm colaborativo)

## 1. Objetivo e escopo

Template Python para backends AI-ready, clonável como ponto de partida para novos projetos. O template entrega:

- API HTTP com FastAPI + Swagger automático.
- Arquitetura em camadas (API → Application → Domain ← Infrastructure) com **CQRS** e **Value Objects** no domínio.
- Persistência agnóstica de dialeto (**PostgreSQL** ou **SQL Server**) via SQLAlchemy 2.0 async + Alembic.
- Cache/sessão em **Redis**.
- Módulo opcional de **IA** com LangGraph + LangSmith + streaming SSE + sessão persistente, removível sem afetar o resto.
- **Result type** em todas as camadas (da criação de VO até o retorno HTTP).
- Logging com correlation-id.
- Alembic com autogenerate (fluxo "nova entidade → migration → endpoint" em poucos passos).

**Não é escopo:** autenticação/autorização completa (fica como extension point), filas/background jobs, observabilidade avançada (métricas, tracing distribuído), multi-tenancy.

## 2. Stack e rationale de licenças

| Ferramenta | Licença | Uso comercial? |
|---|---|---|
| Python 3.12 | PSF License | ✅ |
| FastAPI / Starlette / Uvicorn | MIT / BSD | ✅ |
| Pydantic / pydantic-settings | MIT | ✅ |
| SQLAlchemy 2.0 + Alembic | MIT | ✅ |
| asyncpg | Apache 2.0 | ✅ |
| aioodbc (p/ SQL Server) | Apache 2.0 | ✅ |
| PostgreSQL | PostgreSQL License | ✅ sem pegadinha |
| SQL Server Express | EULA Microsoft | ✅ com limites (10GB/DB, 1.4GB RAM) |
| Redis 7.4+ | RSALv2 + SSPLv1 | ✅ enquanto usado como infra interna (não revendido como serviço) |
| Valkey | BSD-3 | ✅ alternativa sem restrição |
| LangChain / LangGraph / LangSmith | MIT | ✅ |

Produção recomendada: **PostgreSQL + Valkey** (stack 100% permissiva).

## 3. Princípios arquiteturais

### 3.1 Regras de dependência entre camadas

```
api → application → domain ← infrastructure
                       ↑
                      ai (lê domínio, não o contrário)
core é importado por qualquer camada
```

- **Domain** não importa FastAPI, SQLAlchemy, nem LangChain. Python puro.
- **Application** conhece domain + abstrações (`IUserRepository`), nunca detalhes de ORM.
- **Infrastructure** implementa as abstrações do domain.
- **API** orquestra: HTTP → Command/Query → Handler → HTTP.
- **AI** é opcional e removível. Pode usar domain/application, nunca o contrário.

### 3.2 Regra geral de abstração

> Só abstraia o que tem lógica própria. Não abstraia APIs que já são boas nativamente.

- ✅ Repository — encapsula mapping Entity↔ORM e queries nomeadas por intenção.
- ✅ Result — lógica de sucesso/falha com `map`, `unwrap_or`.
- ✅ Value Object — regra de sanitização + validação.
- ❌ Query builder EF-like — `select()` do SQLAlchemy 2.0 já é fluente o bastante.
- ❌ Mediator/Command bus — YAGNI para o template.

### 3.3 Result em todas as camadas

`Result[T]` flui do construtor do VO até a resposta HTTP:

- VO `create()` → `Result[VO]`.
- Entity `create()` → agrega erros de VOs → `Result[Entity]`.
- Handler `handle()` → `Result[DTO]` com `status_code` embutido.
- Router chama `unwrap(result)` → HTTPException em falha, DTO em sucesso.

## 4. Estrutura de pastas

```
backend-template/
├── app/
│   ├── main.py
│   ├── api/
│   │   ├── deps.py
│   │   ├── middleware.py
│   │   ├── error_handler.py
│   │   └── v1/
│   │       ├── schemas.py
│   │       ├── users.py
│   │       └── ai_chat.py
│   ├── application/
│   │   ├── commands/
│   │   │   ├── create_user.py
│   │   │   └── update_user_email.py
│   │   ├── queries/
│   │   │   ├── get_user_by_id.py
│   │   │   ├── get_user_by_email.py
│   │   │   └── list_active_users.py
│   │   └── dtos.py
│   ├── domain/
│   │   ├── common/
│   │   │   ├── result.py
│   │   │   ├── entity.py
│   │   │   └── value_object.py
│   │   ├── value_objects/
│   │   │   ├── email.py
│   │   │   ├── brazilian_phone.py
│   │   │   ├── non_negative_float.py
│   │   │   └── percentage.py
│   │   └── user/
│   │       ├── user.py
│   │       └── user_repository.py
│   ├── infrastructure/
│   │   ├── db/
│   │   │   ├── session.py
│   │   │   ├── base.py
│   │   │   └── models/
│   │   │       └── user_model.py
│   │   ├── repositories/
│   │   │   ├── base_repository.py
│   │   │   └── user_repository.py
│   │   ├── cache/
│   │   │   ├── redis_client.py
│   │   │   └── cache_service.py
│   │   └── external/
│   ├── ai/
│   │   ├── state.py
│   │   ├── model_factory.py
│   │   ├── graph.py
│   │   ├── context.py
│   │   ├── streaming.py
│   │   ├── nodes/
│   │   │   ├── agent.py
│   │   │   └── tool_executor.py
│   │   ├── tools/
│   │   │   ├── __init__.py
│   │   │   ├── get_current_time.py
│   │   │   └── get_user_by_email.py
│   │   └── prompts/
│   │       └── system_prompt.txt
│   ├── core/
│   │   ├── config.py
│   │   ├── context.py
│   │   └── logging_config.py
│   └── migrations/
│       ├── env.py
│       ├── script.py.mako
│       └── versions/
├── tests/
│   ├── conftest.py
│   ├── unit/
│   │   ├── domain/
│   │   └── application/
│   ├── integration/
│   └── e2e/
├── .env.example
├── alembic.ini
├── requirements.txt
├── requirements-postgres.txt
├── requirements-mssql.txt
├── requirements-ai.txt
├── requirements-dev.txt
├── Makefile
├── Dockerfile
├── start_services.sh
├── pytest.ini
├── pyrightconfig.json
├── CLAUDE.md
└── README.md
```

## 5. Domain

### 5.1 Result — `domain/common/result.py`

Copiado 1:1 do `agilean-mcp-server/app/shared/utils/result.py`. Dataclass frozen, construtores `success`/`failure`/`from_exception`, métodos `map` e `unwrap_or`. Campo opcional `status_code` usado pela API layer para mapear HTTP.

### 5.2 BaseEntity — `domain/common/entity.py`

```python
@dataclass(slots=True, kw_only=True)
class BaseEntity:
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=_utcnow)
    updated_at: datetime = field(default_factory=_utcnow)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, BaseEntity) and self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)
```

Mutável (estado muda via métodos que retornam `Result`). Equality por id.

### 5.3 BaseValueObject — `domain/common/value_object.py`

```python
@dataclass(frozen=True, slots=True)
class BaseValueObject:
    @classmethod
    def create(cls, raw) -> Result[Self]:
        raise NotImplementedError
```

Convenção:
- VO é frozen (imutável, equality por valor).
- `__init__` direto confia no input (assume já normalizado).
- API pública de criação é `create(raw) -> Result[Self]`.
- Reconstituição a partir do DB usa `__init__` direto (dados confiáveis, sem revalidar).

### 5.4 Value Objects concretos

**`NonNegativeFloat`** — coage para float, rejeita NaN e valores negativos.

**`Percentage`** — valor em 0..100 (legível para UI e DB). Property `.as_ratio` retorna 0..1 para cálculos.

**`Email`** — normaliza (`strip().lower()`), valida com regex RFC-5322 simplificada, rejeita vazio e > 254 chars.

**`BrazilianPhone`** — aceita formatos variados (`"(21) 99694-9389"`, `"+5521996949389"`, `"21 99694-9389"`), strip de não-dígitos, detecta/remove DDI `55`, valida DDD contra lista oficial, valida regras de celular (9 na 3ª posição, 11 dígitos) vs fixo (10 dígitos, sem 9). Armazena em E.164 (`"+5521996949389"`), expõe `.ddd`, `.national` (`"(21) 99694-9389"`), `.is_mobile`.

Padrão de todos: `VO.create(raw)` retorna `Result.failure("mensagem descritiva")` em inválidos, `Result.success(cls(...))` em válidos.

### 5.5 User — `domain/user/user.py`

Entidade composta por VOs. Factory `create()` agrega erros de todos os VOs (não para no primeiro):

```python
@dataclass(slots=True, kw_only=True)
class User(BaseEntity):
    name: str
    email: Email
    phone: BrazilianPhone
    credit_score: Percentage
    balance: NonNegativeFloat

    @classmethod
    def create(cls, *, name, email, phone, credit_score=0.0, balance=0.0) -> Result[Self]:
        errors = []
        name_clean = (name or "").strip()
        if not name_clean: errors.append("name: obrigatório.")

        email_r = Email.create(email)
        phone_r = BrazilianPhone.create(phone)
        score_r = Percentage.create(credit_score)
        balance_r = NonNegativeFloat.create(balance)

        for r in (email_r, phone_r, score_r, balance_r):
            if r.is_failure: errors.append(r.error)

        if errors: return Result.failure("; ".join(errors))
        return Result.success(cls(
            name=name_clean,
            email=email_r.value, phone=phone_r.value,
            credit_score=score_r.value, balance=balance_r.value,
        ))

    def change_email(self, new_email: str) -> Result[None]:
        r = Email.create(new_email)
        if r.is_failure: return Result.failure(r.error)
        self.email = r.value
        self.updated_at = _utcnow()
        return Result.success(None)
```

### 5.6 IUserRepository — `domain/user/user_repository.py`

Protocol (interface) define o contrato. Implementação fica na infra.

```python
class IUserRepository(Protocol):
    async def get_by_id(self, user_id: UUID) -> User | None: ...
    async def get_by_email(self, email: str) -> User | None: ...
    async def list_active(self, *, limit: int = 50, offset: int = 0) -> Sequence[User]: ...
    async def add(self, user: User) -> None: ...
    async def update(self, user: User) -> None: ...
    async def remove(self, user: User) -> None: ...
```

## 6. Application (CQRS)

### 6.1 Convenções

- Commands = escrita. Queries = leitura. Cada caso de uso em seu arquivo.
- Commands/Queries são `@dataclass(frozen=True)` sem Pydantic.
- Handlers retornam `Result[DTO]` ou `Result[list[DTO]]` — nunca entidades cruas.
- Sem Bus/Mediator. Handlers são injetados diretamente via `Depends`.

### 6.2 DTO — `application/dtos.py`

```python
@dataclass(frozen=True, slots=True)
class UserDto:
    id: UUID; name: str; email: str; phone: str; phone_display: str
    credit_score: float; balance: float
    created_at: datetime; updated_at: datetime

    @classmethod
    def from_entity(cls, u: User) -> "UserDto": ...
```

### 6.3 Command exemplo — `CreateUserHandler`

Fluxo: verifica unicidade (email) → `User.create` (VOs validam) → `repo.add` → commit automático no fim do request → retorna `Result.success(UserDto, status_code=201)`.

Falha de VO → `Result.failure(..., status_code=422)`. Conflito de email → `Result.failure(..., status_code=409)`.

### 6.4 Command com mutação — `UpdateUserEmailHandler`

Carrega entidade pelo `repo.get_by_id`, chama `user.change_email(new_email)` (que valida via VO), e explicitamente chama `repo.update(user)` para sincronizar com o modelo ORM.

**Nota:** `repo.update(user)` é necessário porque mantemos `User` (domínio) separado de `UserModel` (ORM). O identity map do SQLAlchemy rastreia o model, não a entidade. Trade-off consciente: 1 linha a mais por domínio testável sem banco.

### 6.5 Queries

`GetUserByIdQuery`, `GetUserByEmailQuery`, `ListActiveUsersQuery` seguem o mesmo padrão: dataclass de entrada + handler que retorna `Result[UserDto]` ou `Result[list[UserDto]]`.

## 7. Infrastructure

### 7.1 Session — `infrastructure/db/session.py`

Engine + session maker globais inicializados no `lifespan`. Dependency `get_session()` abre transação, commita ao fim do request ou rollback em exceção.

`DATABASE_URL` define o dialeto (`postgresql+asyncpg://...` ou `mssql+aioodbc://...`).

### 7.2 DeclarativeBase e TimestampMixin — `infrastructure/db/base.py`

Base para todos os modelos ORM. `TimestampMixin` injeta `created_at` / `updated_at` com default UTC.

### 7.3 UserModel — `infrastructure/db/models/user_model.py`

SQLAlchemy model com colunas planas (phone como VARCHAR(14) E.164, email VARCHAR(254) único indexado, credit_score/balance Float, is_active Boolean).

**Para SQL Server:** trocar `PG_UUID(as_uuid=True)` por `Uniqueidentifier` ou `String(36)`.

### 7.4 BaseRepository — `infrastructure/repositories/base_repository.py`

Mínimo. ~25 linhas. Só o que padroniza a injeção:

```python
class BaseRepository(Generic[TModel]):
    def __init__(self, session, model): ...
    async def get_by_id(self, id) -> TModel | None:
        return await self._session.get(self._model, id)
    def add_row(self, row): self._session.add(row)
    async def remove_row(self, row): await self._session.delete(row)

    # privados para reduzir ruído em repos concretos
    async def _first_or_default(self, stmt: Select) -> TModel | None: ...
    async def _to_list(self, stmt: Select) -> Sequence[TModel]: ...
```

Sem query builder EF-like. Concrete repos usam `select()` do SQLAlchemy 2.0 diretamente.

### 7.5 UserRepository — `infrastructure/repositories/user_repository.py`

Implementa `IUserRepository`. Responsabilidade: mapping `User` ↔ `UserModel`.

- `get_by_id`, `get_by_email`, `list_active` executam `select()` e convertem resultados via `_to_entity`.
- `add(user)` converte via `_to_model` e chama `session.add`.
- `update(user)` carrega o row ORM, copia campos um a um.
- `remove(user)` carrega e deleta.
- `_to_entity(row)` reconstitui `User` via construtores diretos dos VOs (bypass de validação — DB é confiável).
- `_to_model(user)` constrói `UserModel` com os `.value` dos VOs.

### 7.6 Redis — `infrastructure/cache/`

`redis_client.py` constrói pool com SSL automático quando `environment != "development"` (compatível com AWS MemoryDB / Elasticache).

`cache_service.py` oferece `get/set/delete` com JSON serialization, retornando `Result[...]`.

Mesmo client é usado pelo LangGraph `AsyncRedisSaver` no módulo AI.

## 8. API Layer

### 8.1 error_handler.py — ponte Result→HTTP

```python
def unwrap(result: Result[T]) -> T:
    if result.is_success: return result.value
    raise HTTPException(
        status_code=result.status_code or 500,
        detail=result.error or "Erro interno.",
    )
```

Handler global para exceções não-tratadas retorna 500 JSON padronizado.

### 8.2 Schemas — `api/v1/schemas.py`

Pydantic **apenas aqui**. Request schemas validam tipos básicos (string, number). Validação de negócio (email/phone/etc) é responsabilidade dos VOs, não de regex no schema.

Response schemas (`UserResponse`) mirram DTOs com método `from_dto()`.

### 8.3 Deps — `api/deps.py`

Wiring explícito: `get_session` → `UserRepo` → `Handler`. Usa `Annotated[X, Depends(f)]` moderno.

### 8.4 Router — `api/v1/users.py`

Rotas: `POST /v1/users`, `GET /v1/users/{id}`, `GET /v1/users?limit=&offset=`, `PATCH /v1/users/{id}/email`. Cada rota monta `Command`/`Query`, chama `await handler.handle(...)`, passa por `unwrap()`, retorna `Response.from_dto()`.

### 8.5 LoggingMiddleware — `api/middleware.py`

Injeta/propaga `X-Correlation-Id` header, loga `METHOD PATH -> STATUS (Xms)` com correlation id. Usa `ContextVar` de `core/context.py`.

### 8.6 Lifespan — `app/main.py`

Inicializa engine SQLAlchemy, pool Redis, checkpointer LangGraph, compila grafo do agente. Tudo `await ...aclose()` no shutdown.

## 9. Observabilidade (Logging)

`core/context.py` define `correlation_id` e `db_session` como `ContextVar`s.

`core/logging_config.py`:
- Lê `LOG_LEVEL` do env.
- Handler `StreamHandler(stdout)`.
- Formatter inclui `%(correlation_id)s` em cada linha.
- `CorrelationIdFilter` injeta o valor da ContextVar em cada LogRecord.
- Silencia `uvicorn.access` (middleware já loga) e `sqlalchemy.engine` (controlado por `echo=` do engine).

Formato: `2026-04-24T10:32:17 [INFO] [a7f3c2] app.api.middleware - POST /v1/users -> 201 (43.2ms)`

Texto (não JSON) por padrão. Documentado no README como migrar pra JSON se integrar com CloudWatch/Datadog.

## 10. Módulo AI (opcional)

### 10.1 Escopo

Agente conversacional simples seguindo o padrão de nodes do mcp-server. Grafo:

```
START → agent → {tool_calls?} ──yes──> tool_executor ──loop──> agent
                     └─no──> END
```

### 10.2 State — `ai/state.py`

```python
class ChatState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
```

### 10.3 Model factory — `ai/model_factory.py`

`@lru_cache` sobre `get_chat_model()`. Lê `ai_provider` (`anthropic`/`openai`/`none`) e instancia `ChatAnthropic` ou `ChatOpenAI` com `streaming=True`.

### 10.4 Nodes

- **`agent.py`** — chama o LLM com `SystemMessage(prompt)` + histórico, binda tools via `bind_tools(TOOLS)`, retorna `{"messages": [response]}`.
- **`tool_executor.py`** — percorre `tool_calls` da última mensagem, resolve via `TOOL_REGISTRY`, executa, devolve `ToolMessage` por call (inclusive em caso de erro).

### 10.5 Tools

**`get_current_time`** — tool trivial ilustrando o padrão.

**`get_user_by_email`** — tool end-to-end mostrando integração com application/infra. Lê `db_session` da ContextVar (`core/context.py`), monta `UserRepository`, chama `GetUserByEmailHandler`. Retorna string formatada pro LLM. Erro → retorna `result.error` como observação visível.

**`TOOL_REGISTRY`** é um dict plano em `tools/__init__.py`. Adicionar tool = criar arquivo + incluir no `TOOLS`.

### 10.6 Graph — `ai/graph.py`

Builder padrão. Roteamento condicional após `agent`: se última mensagem tem `tool_calls` → `tool_executor` → volta para `agent`; senão → `END`.

Grafo compilado **uma vez** no lifespan com `AsyncRedisSaver` (TTL 7200s, refresh on read). Lição aprendida do mcp-server: compilar por request duplica checkpoints no Redis.

### 10.7 Context bridge — `ai/context.py`

```python
@asynccontextmanager
async def ai_tool_context(session: AsyncSession):
    token = db_session.set(session)
    try: yield
    finally: db_session.reset(token)
```

Router abre esse contexto antes do streaming. Tools leem `db_session.get()`.

### 10.8 Streaming — `ai/streaming.py`

Gerador assíncrono que emite eventos SSE:
- `session` — primeiro frame, com `session_id`.
- `token` — chunks de texto do LLM (via `stream_mode="messages"`).
- `done` — fim do stream.
- `error` — exceção; stream termina.

Filtra apenas `AIMessageChunk` (ignora ToolMessage).

### 10.9 Router — `api/v1/ai_chat.py`

`POST /v1/ai/chat` recebe `{message, session_id?}`, abre `ai_tool_context(session)` dentro de um gerador async, streama `stream_chat(...)`. Retorna `StreamingResponse` com headers SSE.

### 10.10 LangSmith

Zero código. Setar `LANGCHAIN_TRACING_V2=true` + `LANGCHAIN_API_KEY` no `.env` habilita tracing automático (ficam fora do prefix `BACKEND_` porque são envs do LangChain).

## 11. Configuração & dev ergonomics

### 11.1 Settings — `core/config.py`

Pydantic Settings com prefix `BACKEND_`. Campos: app (env, host, port, cors), database (url, pool), redis (host, port, auth, SSL automático), AI (provider, model, key, temperature).

`@lru_cache` em `get_settings()`.

### 11.2 `.env.example`

Seções comentadas: App, DB (exemplo Postgres e SQL Server), Redis, AI, LangSmith. `LOG_LEVEL` fora do prefix.

### 11.3 Requirements particionado

- `requirements.txt` — fastapi, uvicorn, pydantic, pydantic-settings, sqlalchemy[asyncio], alembic, redis, httpx.
- `requirements-postgres.txt` — asyncpg.
- `requirements-mssql.txt` — aioodbc.
- `requirements-ai.txt` — langchain, langgraph, langsmith, langgraph-checkpoint-redis, langchain-anthropic, langchain-openai.
- `requirements-dev.txt` — pytest, pytest-asyncio, ruff, mypy.

### 11.4 Alembic — `app/migrations/env.py`

- Importa `Base` de `infrastructure/db/base.py` e **todos os models** (side-effect de import) para popular `Base.metadata`.
- Puxa `database_url` de `get_settings()`.
- Suporte async via `async_engine_from_config` + `connection.run_sync(do_run_migrations)`.
- `alembic.ini` na raiz aponta `script_location = app/migrations`.

### 11.5 Makefile

Targets: `install`, `install-postgres`, `install-mssql`, `install-ai`, `run`, `redis-dev` (Docker), `test`, `lint` (ruff+mypy), `migrate-new msg="..."`, `migrate-up`, `migrate-down`, `migrate-history`, `clean`.

### 11.6 Dockerfile

Base `python:3.12-slim`, instala deps de sistema (ODBC driver para SQL Server opcional), instala requirements, copia app, expõe 8000, CMD `python -m app.main`.

### 11.7 Tests

Estrutura espelha o app:
- `tests/unit/domain/` — VOs e entidade User. Sem dependência externa.
- `tests/unit/application/` — handlers com `InMemoryUserRepository` (fake implementando `IUserRepository`).
- `tests/integration/` — UserRepository real contra SQLite in-memory (ou testcontainers).
- `tests/e2e/` — httpx.AsyncClient contra FastAPI app.

`pytest.ini` com `asyncio_mode = auto`.

### 11.8 CLAUDE.md do template

Copia filosofia do mcp-server: venv obrigatório (`.venv/bin/python`, não Python global), dependências em `requirements*.txt`, pytest via `.venv/bin/pytest`, start via `./start_services.sh`.

## 12. Fluxo "adicionar nova entidade"

1. Domain: criar `domain/<entity>/<entity>.py` + VOs específicos + interface `IEntityRepository`.
2. Infra: criar `infrastructure/db/models/<entity>_model.py` e `infrastructure/repositories/<entity>_repository.py`.
3. Registrar o import em `app/migrations/env.py`.
4. `make migrate-new msg="add <entity> table"` — Alembic autogenera.
5. Inspecionar script gerado em `app/migrations/versions/`.
6. `make migrate-up`.
7. Application: criar `application/commands/<action>.py` e `application/queries/<query>.py`.
8. API: criar router em `api/v1/<entity>.py` + schemas + deps.
9. Incluir router no `main.py`.
10. Testes: adicionar em `tests/unit/`, `tests/integration/`, `tests/e2e/`.

## 13. Trade-offs e decisões conscientes

1. **Entity ≠ ORM model**: domínio fica puro e testável, mas `UserRepository.update(user)` é explícito. Se virar problema, migrar para mapeamento imperativo do SQLAlchemy não toca a API.
2. **Sem query builder custom**: aceitamos `select(...).where(...).options(selectinload(...))` em vez de EF-style. Zero camada extra a manter.
3. **`Result` em tudo**: verbosidade extra vs exceções implícitas. Escolhemos verbosidade + previsibilidade. `unwrap()` centraliza o mapeamento HTTP.
4. **Sem auth no template base**: cada projeto clonado decide (JWT, Bearer externo, OAuth). Extension point claro no `api/deps.py`.
5. **Percentage em 0..100**: escolhido pelo critério "humano/DB-friendly". `.as_ratio` cobre cálculos.
6. **Texto em logs, não JSON**: legível em dev/CI. Migração para JSON documentada.
7. **AI compartilha pool Redis**: evita fragmentação de infra, mas um `CacheService` muito carregado pode pressionar o checkpointer. Em produção real, separar em dois pools é trivial.
8. **Tools via `ContextVar` para session**: alternativa seria passar via `RunnableConfig` do LangGraph, mais explícito porém LangGraph-específico. Escolhemos o padrão do mcp-server por consistência.
9. **Grafo compilado no startup**: economiza Redis keys. Custo: mudanças no grafo requerem restart.
10. **`remove` é hard delete no template**: projetos com soft-delete adaptam `UserModel` com `deleted_at` e ajustam queries.

## 14. Critérios de aceitação

Template considerado pronto quando:

- [ ] `make install && make install-postgres && make migrate-up && make run` ergue a API em `/docs`.
- [ ] `POST /v1/users` cria user válido (201), rejeita inválido com mensagem agregada (422), rejeita duplicado (409).
- [ ] `GET /v1/users/{id}` retorna 200 ou 404.
- [ ] `PATCH /v1/users/{id}/email` valida novo email via VO.
- [ ] `POST /v1/ai/chat` (com `BACKEND_AI_PROVIDER` configurado) abre SSE com frames session/token/done.
- [ ] `get_user_by_email` tool responde corretamente quando email existe e quando não.
- [ ] Todos os VOs têm testes unitários cobrindo caminhos felizes + inválidos.
- [ ] `CreateUserHandler` e `GetUserByEmailHandler` têm testes com `InMemoryUserRepository`.
- [ ] Logs mostram correlation-id coerente em toda linha de um mesmo request.
- [ ] Deletar `app/ai/`, tirar router e `requirements-ai.txt` não quebra build nem testes do resto.

## 15. Referências e inspirações

- **agilean-mcp-server**: lifespan pattern, Result type, ContextVar para request-scoped data, LangGraph + AsyncRedisSaver, LoggingMiddleware, SSE streaming, padrão de nodes (planner/budget).
- **Pontos em que evoluímos vs mcp-server**:
  - Separação clara domain/application/infrastructure (mcp usa `shared/` ambíguo).
  - Entity ≠ ORM model (mcp não persiste entidades; Planner é stateless).
  - CQRS explícito (mcp tem commands/queries implícitos via tools do LangGraph).
  - Value Objects no domínio (mcp usa Pydantic models sem sanitização).
  - Repository com interface no domínio (mcp tem `services/` sem abstração).
  - Correlation-id no logging (mcp loga por request sem id).
  - `Result` propagado até a API (mcp usa `Result` em services mas o router usa exceções).
