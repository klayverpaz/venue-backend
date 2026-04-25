# Backend Template Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Construir um template Python backend AI-ready, com FastAPI + CQRS + Value Objects + SQLAlchemy async + Redis + LangGraph opcional, pronto para ser clonado como base de novos projetos.

**Architecture:** Camadas `api → application → domain ← infrastructure` com módulo `ai/` opcional/removível e `core/` cross-cutting. Result type propagado em todas as camadas. Entity pura no domínio, mapping explícito com model ORM. Ver [design spec](../specs/2026-04-24-backend-template-design.md).

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2.0 async, Alembic, Redis, LangGraph, LangSmith, pytest, uv.

**Phases:**
- Fase A (Tasks 1–3): Bootstrap + core
- Fase B (Tasks 4–11): Domain (Result, VOs, User, interface)
- Fase C (Tasks 12–16): Infrastructure (DB, repo, Redis)
- Fase D (Tasks 17–23): Application (CQRS handlers)
- Fase E (Tasks 24–29): API layer + main.py + E2E
- Fase F (Tasks 30–31): Alembic + initial migration
- Fase G (Tasks 32–37): AI module opcional
- Fase H (Tasks 38–39): Docker + README final

Execução pode pausar no fim de qualquer fase — cada uma produz software testável.

---

## Fase A — Bootstrap

### Task 1: Projeto bootstrap (git, venv, requirements, configs)

**Files:**
- Create: `backend-template/.gitignore`
- Create: `backend-template/.python-version`
- Create: `backend-template/requirements.txt`
- Create: `backend-template/requirements-postgres.txt`
- Create: `backend-template/requirements-mssql.txt`
- Create: `backend-template/requirements-ai.txt`
- Create: `backend-template/requirements-dev.txt`
- Create: `backend-template/pytest.ini`
- Create: `backend-template/pyrightconfig.json`
- Create: `backend-template/.env.example`
- Create: `backend-template/Makefile`
- Create: `backend-template/CLAUDE.md`

- [ ] **Step 1: Confirmar working dir**

O repo já foi inicializado (branch `main`, remote `origin` apontando para `git@github.com:klayverpaz/ai-ready-backend-template.git`, com um commit inicial contendo stub de `README.md`). Apenas confirme:

```bash
cd /Users/klayver/Arke/Agilean/agent-workspace/backend-template
git status
git remote -v
```

Expected: branch main, remote origin configurado.

- [ ] **Step 2: .gitignore**

Create `.gitignore`:
```
.venv/
__pycache__/
*.pyc
*.pyo
.pytest_cache/
.mypy_cache/
.ruff_cache/
.pyre/
.env
.DS_Store
*.egg-info/
dist/
build/
```

- [ ] **Step 3: .python-version**

Create `.python-version`:
```
3.12
```

- [ ] **Step 4: requirements.txt (base)**

Create `requirements.txt`:
```
fastapi>=0.115.8
uvicorn[standard]>=0.40.0
pydantic>=2.11.7
pydantic-settings>=2.7.0
sqlalchemy[asyncio]>=2.0.35
alembic>=1.13.0
redis>=5.2.1
httpx>=0.28.1
typing_extensions>=4.15.0
```

- [ ] **Step 5: requirements-postgres.txt**

Create `requirements-postgres.txt`:
```
asyncpg>=0.30.0
```

- [ ] **Step 6: requirements-mssql.txt**

Create `requirements-mssql.txt`:
```
aioodbc>=0.5.0
```

- [ ] **Step 7: requirements-ai.txt**

Create `requirements-ai.txt`:
```
langchain>=0.3.15
langchain-core>=0.3.30
langgraph>=0.2.45
langgraph-checkpoint-redis>=0.3.6
langchain-anthropic>=0.3.0
langchain-openai>=0.3.0
langsmith>=0.2.0
```

- [ ] **Step 8: requirements-dev.txt**

Create `requirements-dev.txt`:
```
pytest>=8.0.0
pytest-asyncio>=0.24.0
aiosqlite>=0.20.0
ruff>=0.7.0
mypy>=1.11.0
```

- [ ] **Step 9: pytest.ini**

Create `pytest.ini`:
```ini
[pytest]
testpaths = tests
asyncio_mode = auto
filterwarnings =
    ignore::DeprecationWarning
addopts = -ra --strict-markers
```

- [ ] **Step 10: pyrightconfig.json**

Create `pyrightconfig.json`:
```json
{
  "include": ["app", "tests"],
  "exclude": ["**/__pycache__", ".venv", "**/node_modules"],
  "pythonVersion": "3.12",
  "typeCheckingMode": "basic",
  "reportMissingImports": "warning"
}
```

- [ ] **Step 11: .env.example**

Create `.env.example`:
```bash
# App
BACKEND_ENVIRONMENT=development
BACKEND_HOST=0.0.0.0
BACKEND_PORT=8000
BACKEND_CORS_ORIGINS=["http://localhost:3000"]
LOG_LEVEL=INFO

# DB — escolha um dos dois descomentando a linha correspondente
BACKEND_DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/mydb
# BACKEND_DATABASE_URL=mssql+aioodbc://user:pass@localhost/mydb?driver=ODBC+Driver+18+for+SQL+Server
BACKEND_DB_POOL_SIZE=5

# Redis
BACKEND_REDIS_HOST=localhost
BACKEND_REDIS_PORT=6379
BACKEND_REDIS_USERNAME=
BACKEND_REDIS_PASSWORD=

# AI (ai_provider=none desativa o módulo inteiro)
BACKEND_AI_PROVIDER=none
BACKEND_AI_MODEL_NAME=claude-sonnet-4-5-20250929
BACKEND_AI_API_KEY=
BACKEND_AI_TEMPERATURE=0.3

# LangSmith (tracing automático quando TRACING_V2=true)
LANGCHAIN_TRACING_V2=false
LANGCHAIN_API_KEY=
LANGCHAIN_PROJECT=backend-template
```

- [ ] **Step 12: Makefile**

Create `Makefile`:
```makefile
.PHONY: install install-postgres install-mssql install-ai run test lint \
        migrate-new migrate-up migrate-down migrate-history redis-dev clean

PYTHON  ?= .venv/bin/python
PIP     ?= .venv/bin/pip
ALEMBIC ?= .venv/bin/alembic
PYTEST  ?= .venv/bin/pytest

install:
	uv venv --seed --python 3.12
	$(PIP) install -r requirements.txt -r requirements-dev.txt

install-postgres:
	$(PIP) install -r requirements-postgres.txt

install-mssql:
	$(PIP) install -r requirements-mssql.txt

install-ai:
	$(PIP) install -r requirements-ai.txt

run:
	$(PYTHON) -m app.main

redis-dev:
	docker run -d --name redis-dev -p 6379:6379 redis/redis-stack-server:latest

test:
	$(PYTEST)

lint:
	$(PYTHON) -m ruff check app tests
	$(PYTHON) -m mypy app

migrate-new:
	@test -n "$(msg)" || (echo "Uso: make migrate-new msg='descricao'" && exit 1)
	$(ALEMBIC) revision --autogenerate -m "$(msg)"

migrate-up:
	$(ALEMBIC) upgrade head

migrate-down:
	$(ALEMBIC) downgrade -1

migrate-history:
	$(ALEMBIC) history

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name .pytest_cache -exec rm -rf {} +
	find . -type d -name .mypy_cache -exec rm -rf {} +
```

- [ ] **Step 13: CLAUDE.md**

Create `CLAUDE.md`:
```markdown
# Backend Template - Instruções

## Python

Projeto Python 3.12. Virtualenv local em `.venv/` — **sempre use o Python do venv**, nunca o Python global.

- Ativar o venv: `source .venv/bin/activate && python ...`
- Chamar o binário direto: `.venv/bin/python ...` ou `.venv/bin/pytest ...`

Nunca rode `python ...` / `pip install ...` sem o venv ativo.

Dependências em `requirements*.txt`. Instalação: `make install` (base + dev). Extras: `make install-postgres`, `make install-mssql`, `make install-ai`.

Testes: `make test` (`.venv/bin/pytest`).

Migrações: `make migrate-new msg="..."`, `make migrate-up`.

Start local: `./start_services.sh` (ou `make run`).
```

- [ ] **Step 14: Criar venv e instalar dev deps**

Run:
```bash
cd /Users/klayver/Arke/Agilean/agent-workspace/backend-template
uv venv --python 3.12
.venv/bin/pip install -r requirements.txt -r requirements-dev.txt
```

Expected: venv criado sem erros, deps instalados.

- [ ] **Step 15: Commit**

```bash
git add .gitignore .python-version requirements*.txt pytest.ini \
        pyrightconfig.json .env.example Makefile CLAUDE.md
git commit -m "chore: bootstrap project config and deps"
```

---

### Task 2: Core config (Pydantic Settings)

**Files:**
- Create: `app/__init__.py`
- Create: `app/core/__init__.py`
- Create: `app/core/config.py`
- Test: `tests/__init__.py`, `tests/conftest.py`, `tests/unit/__init__.py`, `tests/unit/core/__init__.py`, `tests/unit/core/test_config.py`

- [ ] **Step 1: Criar skeleton de pastas**

```bash
mkdir -p app/core tests/unit/core
touch app/__init__.py app/core/__init__.py tests/__init__.py \
      tests/unit/__init__.py tests/unit/core/__init__.py
```

- [ ] **Step 2: conftest.py base**

Create `tests/conftest.py`:
```python
import os
import pytest


@pytest.fixture(autouse=True)
def _env_defaults(monkeypatch):
    """Defaults previsíveis para os testes unitários."""
    monkeypatch.setenv("BACKEND_ENVIRONMENT", "test")
    monkeypatch.setenv("BACKEND_DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    monkeypatch.setenv("BACKEND_AI_PROVIDER", "none")
    yield
```

- [ ] **Step 3: Test falhando para Settings**

Create `tests/unit/core/test_config.py`:
```python
import pytest
from app.core.config import Settings, get_settings


def test_settings_carrega_env_com_prefix_backend(monkeypatch):
    monkeypatch.setenv("BACKEND_ENVIRONMENT", "test")
    monkeypatch.setenv("BACKEND_DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    monkeypatch.setenv("BACKEND_HOST", "127.0.0.1")
    monkeypatch.setenv("BACKEND_PORT", "9000")
    get_settings.cache_clear()
    s = get_settings()
    assert s.environment == "test"
    assert str(s.database_url) == "sqlite+aiosqlite:///:memory:"
    assert s.host == "127.0.0.1"
    assert s.port == 9000


def test_settings_ai_provider_default_none(monkeypatch):
    monkeypatch.setenv("BACKEND_DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    get_settings.cache_clear()
    s = get_settings()
    assert s.ai_provider == "none"


def test_settings_exige_database_url(monkeypatch):
    monkeypatch.delenv("BACKEND_DATABASE_URL", raising=False)
    get_settings.cache_clear()
    with pytest.raises(Exception):
        get_settings()
```

- [ ] **Step 4: Rodar e confirmar falha**

Run: `.venv/bin/pytest tests/unit/core/test_config.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'app.core.config'`.

- [ ] **Step 5: Implementar Settings**

Create `app/core/config.py`:
```python
from __future__ import annotations
from functools import lru_cache
from pathlib import Path
from typing import Literal
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

DOTENV_PATH = Path(__file__).resolve().parent.parent.parent / ".env"


class Settings(BaseSettings):
    app_name: str = "backend-template"
    environment: Literal["development", "production", "test"] = "development"
    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: list[str] = ["http://localhost:3000"]

    database_url: str
    db_pool_size: int = 5

    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_username: str = ""
    redis_password: SecretStr = SecretStr("")

    ai_provider: Literal["anthropic", "openai", "none"] = "none"
    ai_model_name: str = ""
    ai_api_key: SecretStr = SecretStr("")
    ai_temperature: float = 0.3

    model_config = SettingsConfigDict(
        env_prefix="BACKEND_",
        env_file=DOTENV_PATH,
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 6: Confirmar que passa**

Run: `.venv/bin/pytest tests/unit/core/test_config.py -v`
Expected: 3 passed.

- [ ] **Step 7: Commit**

```bash
git add app/__init__.py app/core/__init__.py app/core/config.py \
        tests/__init__.py tests/conftest.py tests/unit/__init__.py \
        tests/unit/core/__init__.py tests/unit/core/test_config.py
git commit -m "feat(core): add Pydantic Settings with BACKEND_ env prefix"
```

---

### Task 3: Core context + logging_config

**Files:**
- Create: `app/core/context.py`
- Create: `app/core/logging_config.py`
- Test: `tests/unit/core/test_logging_config.py`

- [ ] **Step 1: Test falhando para logging filter**

Create `tests/unit/core/test_logging_config.py`:
```python
import logging
from app.core.context import correlation_id
from app.core.logging_config import CorrelationIdFilter, setup_logging


def test_filter_injeta_correlation_id_do_contextvar():
    f = CorrelationIdFilter()
    record = logging.LogRecord("x", logging.INFO, "", 0, "msg", None, None)
    token = correlation_id.set("abc123")
    try:
        f.filter(record)
    finally:
        correlation_id.reset(token)
    assert record.correlation_id == "abc123"


def test_filter_usa_default_quando_nao_setado():
    f = CorrelationIdFilter()
    record = logging.LogRecord("x", logging.INFO, "", 0, "msg", None, None)
    f.filter(record)
    assert record.correlation_id == "-"


def test_setup_logging_configura_handler(caplog):
    setup_logging()
    root = logging.getLogger()
    assert any(isinstance(h, logging.StreamHandler) for h in root.handlers)
```

- [ ] **Step 2: Confirmar falha**

Run: `.venv/bin/pytest tests/unit/core/test_logging_config.py -v`
Expected: FAIL por imports ausentes.

- [ ] **Step 3: Implementar context.py**

Create `app/core/context.py`:
```python
from __future__ import annotations
from contextvars import ContextVar
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

correlation_id: ContextVar[str] = ContextVar("correlation_id", default="-")
db_session: ContextVar[Optional["AsyncSession"]] = ContextVar("db_session", default=None)
user_id: ContextVar[str] = ContextVar("user_id", default="")
```

- [ ] **Step 4: Implementar logging_config.py**

Create `app/core/logging_config.py`:
```python
from __future__ import annotations
import logging
import os
import sys
from app.core.context import correlation_id


class CorrelationIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = correlation_id.get()
        return True


def setup_logging() -> None:
    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] [%(correlation_id)s] %(name)s - %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    ))
    handler.addFilter(CorrelationIdFilter())

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)

    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
```

- [ ] **Step 5: Confirmar que passa**

Run: `.venv/bin/pytest tests/unit/core/test_logging_config.py -v`
Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add app/core/context.py app/core/logging_config.py \
        tests/unit/core/test_logging_config.py
git commit -m "feat(core): add ContextVars and logging config with correlation-id"
```

---

## Fase B — Domain

### Task 4: Result type + tests

**Files:**
- Create: `app/domain/__init__.py`, `app/domain/common/__init__.py`, `app/domain/common/result.py`
- Test: `tests/unit/domain/__init__.py`, `tests/unit/domain/common/__init__.py`, `tests/unit/domain/common/test_result.py`

- [ ] **Step 1: Skeleton**

```bash
mkdir -p app/domain/common tests/unit/domain/common
touch app/domain/__init__.py app/domain/common/__init__.py \
      tests/unit/domain/__init__.py tests/unit/domain/common/__init__.py
```

- [ ] **Step 2: Test falhando para Result**

Create `tests/unit/domain/common/test_result.py`:
```python
import pytest
from app.domain.common.result import Result


def test_success_tem_value_e_sem_error():
    r = Result.success(42)
    assert r.is_success and not r.is_failure
    assert r.value == 42
    assert r.error is None


def test_failure_tem_error_e_sem_value():
    r = Result.failure("boom")
    assert r.is_failure and not r.is_success
    assert r.value is None
    assert r.error == "boom"


def test_success_rejeita_error_simultaneo():
    with pytest.raises(ValueError):
        Result(is_success=True, value=1, error="x")


def test_failure_rejeita_value_simultaneo():
    with pytest.raises(ValueError):
        Result(is_success=False, value=1, error="x")


def test_from_exception_formata_prefix():
    r = Result.from_exception(ValueError("bad"), prefix="Parser")
    assert r.is_failure
    assert "Parser" in r.error and "ValueError" in r.error


def test_map_aplica_em_sucesso_apenas():
    r = Result.success(3).map(lambda x: x * 2)
    assert r.is_success and r.value == 6


def test_map_preserva_falha():
    r = Result.failure("err").map(lambda x: x * 2)
    assert r.is_failure and r.error == "err"


def test_unwrap_or_devolve_default_em_falha():
    assert Result.failure("x").unwrap_or(99) == 99
    assert Result.success(5).unwrap_or(99) == 5


def test_status_code_opcional():
    r = Result.failure("nope", status_code=404)
    assert r.status_code == 404
```

- [ ] **Step 3: Confirmar falha**

Run: `.venv/bin/pytest tests/unit/domain/common/test_result.py -v`
Expected: FAIL (no module).

- [ ] **Step 4: Implementar result.py**

Create `app/domain/common/result.py`:
```python
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
```

- [ ] **Step 5: Confirmar que passa**

Run: `.venv/bin/pytest tests/unit/domain/common/test_result.py -v`
Expected: 9 passed.

- [ ] **Step 6: Commit**

```bash
git add app/domain/__init__.py app/domain/common/__init__.py \
        app/domain/common/result.py tests/unit/domain/__init__.py \
        tests/unit/domain/common/__init__.py tests/unit/domain/common/test_result.py
git commit -m "feat(domain): add Result type with map/unwrap_or/from_exception"
```

---

### Task 5: BaseEntity e BaseValueObject

**Files:**
- Create: `app/domain/common/entity.py`, `app/domain/common/value_object.py`
- Test: `tests/unit/domain/common/test_entity.py`

- [ ] **Step 1: Test falhando**

Create `tests/unit/domain/common/test_entity.py`:
```python
from dataclasses import dataclass
from uuid import uuid4
from app.domain.common.entity import BaseEntity


@dataclass(slots=True, kw_only=True)
class SampleEntity(BaseEntity):
    name: str


def test_entity_gera_id_e_timestamps_automaticos():
    e = SampleEntity(name="x")
    assert e.id is not None
    assert e.created_at is not None
    assert e.updated_at is not None


def test_entity_equality_por_id():
    id_ = uuid4()
    a = SampleEntity(id=id_, name="A")
    b = SampleEntity(id=id_, name="B")  # nome diferente, mesmo id
    assert a == b
    assert hash(a) == hash(b)


def test_entity_diferentes_com_ids_diferentes():
    a = SampleEntity(name="A")
    b = SampleEntity(name="A")
    assert a != b
```

- [ ] **Step 2: Confirmar falha**

Run: `.venv/bin/pytest tests/unit/domain/common/test_entity.py -v`
Expected: FAIL.

- [ ] **Step 3: Implementar entity.py**

Create `app/domain/common/entity.py`:
```python
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID, uuid4


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


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

- [ ] **Step 4: Implementar value_object.py**

Create `app/domain/common/value_object.py`:
```python
from __future__ import annotations
from dataclasses import dataclass
from typing import Self
from app.domain.common.result import Result


@dataclass(frozen=True, slots=True)
class BaseValueObject:
    """Base para VOs. Equality por valor (via frozen dataclass).

    Criação pública via classmethod `create(raw) -> Result[Self]` que
    sanitiza e valida. Construtor direto (`cls(value=...)`) é usado só
    para reconstituição de dados confiáveis (vindos do DB)."""

    @classmethod
    def create(cls, raw) -> Result[Self]:
        raise NotImplementedError
```

- [ ] **Step 5: Confirmar que passa**

Run: `.venv/bin/pytest tests/unit/domain/common/test_entity.py -v`
Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add app/domain/common/entity.py app/domain/common/value_object.py \
        tests/unit/domain/common/test_entity.py
git commit -m "feat(domain): add BaseEntity and BaseValueObject"
```

---

### Task 6: Value Object — NonNegativeFloat

**Files:**
- Create: `app/domain/value_objects/__init__.py`, `app/domain/value_objects/non_negative_float.py`
- Test: `tests/unit/domain/value_objects/__init__.py`, `tests/unit/domain/value_objects/test_non_negative_float.py`

- [ ] **Step 1: Skeleton**

```bash
mkdir -p app/domain/value_objects tests/unit/domain/value_objects
touch app/domain/value_objects/__init__.py tests/unit/domain/value_objects/__init__.py
```

- [ ] **Step 2: Test falhando**

Create `tests/unit/domain/value_objects/test_non_negative_float.py`:
```python
import math
import pytest
from app.domain.value_objects.non_negative_float import NonNegativeFloat


@pytest.mark.parametrize("raw,expected", [
    (0, 0.0),
    (0.0, 0.0),
    (3.5, 3.5),
    ("12.34", 12.34),
    (1000, 1000.0),
])
def test_aceita_numeros_nao_negativos(raw, expected):
    r = NonNegativeFloat.create(raw)
    assert r.is_success
    assert r.value.value == expected


def test_rejeita_negativo():
    r = NonNegativeFloat.create(-1.0)
    assert r.is_failure
    assert "negativ" in r.error.lower()


def test_rejeita_nan():
    r = NonNegativeFloat.create(math.nan)
    assert r.is_failure


@pytest.mark.parametrize("raw", [None, "abc", "xyz"])
def test_rejeita_entradas_invalidas(raw):
    r = NonNegativeFloat.create(raw)
    assert r.is_failure


def test_float_dunder():
    r = NonNegativeFloat.create(7.5)
    assert float(r.value) == 7.5
```

- [ ] **Step 3: Confirmar falha**

Run: `.venv/bin/pytest tests/unit/domain/value_objects/test_non_negative_float.py -v`
Expected: FAIL (no module).

- [ ] **Step 4: Implementar**

Create `app/domain/value_objects/non_negative_float.py`:
```python
from __future__ import annotations
from dataclasses import dataclass
from typing import Self
from app.domain.common.result import Result
from app.domain.common.value_object import BaseValueObject


@dataclass(frozen=True, slots=True)
class NonNegativeFloat(BaseValueObject):
    value: float

    @classmethod
    def create(cls, raw) -> Result[Self]:
        if raw is None:
            return Result.failure("NonNegativeFloat: valor obrigatório.")
        try:
            value = float(raw)
        except (TypeError, ValueError):
            return Result.failure(f"NonNegativeFloat: '{raw}' não é um número.")
        if value != value:  # NaN
            return Result.failure("NonNegativeFloat: NaN não é permitido.")
        if value < 0:
            return Result.failure(f"NonNegativeFloat: valor não pode ser negativo ({value}).")
        return Result.success(cls(value=value))

    def __float__(self) -> float:
        return self.value
```

- [ ] **Step 5: Confirmar que passa**

Run: `.venv/bin/pytest tests/unit/domain/value_objects/test_non_negative_float.py -v`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add app/domain/value_objects/__init__.py \
        app/domain/value_objects/non_negative_float.py \
        tests/unit/domain/value_objects/__init__.py \
        tests/unit/domain/value_objects/test_non_negative_float.py
git commit -m "feat(domain): add NonNegativeFloat value object"
```

---

### Task 7: Value Object — Percentage

**Files:**
- Create: `app/domain/value_objects/percentage.py`
- Test: `tests/unit/domain/value_objects/test_percentage.py`

- [ ] **Step 1: Test falhando**

Create `tests/unit/domain/value_objects/test_percentage.py`:
```python
import pytest
from app.domain.value_objects.percentage import Percentage


@pytest.mark.parametrize("raw,expected", [
    (0, 0.0),
    (50, 50.0),
    (100, 100.0),
    ("37.5", 37.5),
    (0.001, 0.001),
])
def test_aceita_valores_em_0_100(raw, expected):
    r = Percentage.create(raw)
    assert r.is_success
    assert r.value.value == expected


@pytest.mark.parametrize("raw", [-0.01, 100.01, 101, -1, 200])
def test_rejeita_fora_do_range(raw):
    r = Percentage.create(raw)
    assert r.is_failure


@pytest.mark.parametrize("raw", [None, "abc"])
def test_rejeita_entradas_invalidas(raw):
    r = Percentage.create(raw)
    assert r.is_failure


def test_as_ratio_retorna_0_1():
    p = Percentage.create(37).value
    assert p.as_ratio == pytest.approx(0.37)
    assert Percentage.create(100).value.as_ratio == 1.0
    assert Percentage.create(0).value.as_ratio == 0.0
```

- [ ] **Step 2: Confirmar falha**

Run: `.venv/bin/pytest tests/unit/domain/value_objects/test_percentage.py -v`
Expected: FAIL.

- [ ] **Step 3: Implementar**

Create `app/domain/value_objects/percentage.py`:
```python
from __future__ import annotations
from dataclasses import dataclass
from typing import Self
from app.domain.common.result import Result
from app.domain.common.value_object import BaseValueObject


@dataclass(frozen=True, slots=True)
class Percentage(BaseValueObject):
    value: float  # 0.0 <= value <= 100.0

    @classmethod
    def create(cls, raw) -> Result[Self]:
        if raw is None:
            return Result.failure("Percentage: valor obrigatório.")
        try:
            value = float(raw)
        except (TypeError, ValueError):
            return Result.failure(f"Percentage: '{raw}' não é um número.")
        if not 0.0 <= value <= 100.0:
            return Result.failure(f"Percentage: deve estar entre 0 e 100 (recebido: {value}).")
        return Result.success(cls(value=value))

    @property
    def as_ratio(self) -> float:
        return self.value / 100.0
```

- [ ] **Step 4: Confirmar que passa**

Run: `.venv/bin/pytest tests/unit/domain/value_objects/test_percentage.py -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add app/domain/value_objects/percentage.py \
        tests/unit/domain/value_objects/test_percentage.py
git commit -m "feat(domain): add Percentage value object (0..100 with as_ratio)"
```

---

### Task 8: Value Object — Email

**Files:**
- Create: `app/domain/value_objects/email.py`
- Test: `tests/unit/domain/value_objects/test_email.py`

- [ ] **Step 1: Test falhando**

Create `tests/unit/domain/value_objects/test_email.py`:
```python
import pytest
from app.domain.value_objects.email import Email


@pytest.mark.parametrize("raw,expected", [
    ("foo@bar.com", "foo@bar.com"),
    ("  Foo@BAR.com  ", "foo@bar.com"),
    ("a.b+tag@sub.example.com.br", "a.b+tag@sub.example.com.br"),
])
def test_normaliza_e_aceita_validos(raw, expected):
    r = Email.create(raw)
    assert r.is_success
    assert r.value.value == expected
    assert str(r.value) == expected


@pytest.mark.parametrize("raw", [
    None, "", "   ", "sem-arroba", "a@", "@b.com", "a@b", "a@b.c",
])
def test_rejeita_invalidos(raw):
    r = Email.create(raw)
    assert r.is_failure


def test_rejeita_acima_de_254_chars():
    raw = "a" * 250 + "@b.com"
    r = Email.create(raw)
    assert r.is_failure
```

- [ ] **Step 2: Confirmar falha**

Run: `.venv/bin/pytest tests/unit/domain/value_objects/test_email.py -v`
Expected: FAIL.

- [ ] **Step 3: Implementar**

Create `app/domain/value_objects/email.py`:
```python
from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Self
from app.domain.common.result import Result
from app.domain.common.value_object import BaseValueObject

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")


@dataclass(frozen=True, slots=True)
class Email(BaseValueObject):
    value: str  # sempre lowercase, sem espaços

    @classmethod
    def create(cls, raw) -> Result[Self]:
        if raw is None or not isinstance(raw, str):
            return Result.failure("Email: valor obrigatório.")
        normalized = raw.strip().lower()
        if not normalized:
            return Result.failure("Email: não pode ser vazio.")
        if len(normalized) > 254:
            return Result.failure("Email: excede 254 caracteres.")
        if not EMAIL_RE.match(normalized):
            return Result.failure(f"Email inválido: '{raw}'.")
        return Result.success(cls(value=normalized))

    def __str__(self) -> str:
        return self.value
```

- [ ] **Step 4: Confirmar que passa**

Run: `.venv/bin/pytest tests/unit/domain/value_objects/test_email.py -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add app/domain/value_objects/email.py \
        tests/unit/domain/value_objects/test_email.py
git commit -m "feat(domain): add Email value object with normalization"
```

---

### Task 9: Value Object — BrazilianPhone

**Files:**
- Create: `app/domain/value_objects/brazilian_phone.py`
- Test: `tests/unit/domain/value_objects/test_brazilian_phone.py`

- [ ] **Step 1: Test falhando**

Create `tests/unit/domain/value_objects/test_brazilian_phone.py`:
```python
import pytest
from app.domain.value_objects.brazilian_phone import BrazilianPhone


@pytest.mark.parametrize("raw", [
    "(21) 99694-9389",
    "21 99694-9389",
    "5521996949389",
    "+5521996949389",
    "+55 21 9 9694 9389",
    "21996949389",
])
def test_celular_normalizado_para_e164(raw):
    r = BrazilianPhone.create(raw)
    assert r.is_success, r.error
    assert r.value.value == "+5521996949389"
    assert r.value.is_mobile is True


def test_fixo_valido():
    r = BrazilianPhone.create("(21) 3333-4444")
    assert r.is_success
    assert r.value.value == "+552133334444"
    assert r.value.is_mobile is False


def test_ddd_property():
    r = BrazilianPhone.create("(21) 99694-9389")
    assert r.value.ddd == "21"


def test_national_celular():
    r = BrazilianPhone.create("+5521996949389")
    assert r.value.national == "(21) 99694-9389"


def test_national_fixo():
    r = BrazilianPhone.create("(21) 3333-4444")
    assert r.value.national == "(21) 3333-4444"


@pytest.mark.parametrize("raw", [
    None, "", "   ", "abc",
    "123",                    # poucos dígitos
    "00 99694-9389",          # DDD inválido (00)
    "10 99694-9389",          # DDD inválido (10)
    "(21) 8694-9389",         # celular sem dígito 9
    "(21) 9 9694 9389 extra", # extra de dígitos → 12, nem fixo nem celular
])
def test_rejeita_invalidos(raw):
    r = BrazilianPhone.create(raw)
    assert r.is_failure
```

- [ ] **Step 2: Confirmar falha**

Run: `.venv/bin/pytest tests/unit/domain/value_objects/test_brazilian_phone.py -v`
Expected: FAIL.

- [ ] **Step 3: Implementar**

Create `app/domain/value_objects/brazilian_phone.py`:
```python
from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Self
from app.domain.common.result import Result
from app.domain.common.value_object import BaseValueObject

_DIGITS_RE = re.compile(r"\D+")
_VALID_DDDS = {
    11, 12, 13, 14, 15, 16, 17, 18, 19,
    21, 22, 24, 27, 28,
    31, 32, 33, 34, 35, 37, 38,
    41, 42, 43, 44, 45, 46, 47, 48, 49,
    51, 53, 54, 55,
    61, 62, 63, 64, 65, 66, 67, 68, 69,
    71, 73, 74, 75, 77, 79,
    81, 82, 83, 84, 85, 86, 87, 88, 89,
    91, 92, 93, 94, 95, 96, 97, 98, 99,
}


@dataclass(frozen=True, slots=True)
class BrazilianPhone(BaseValueObject):
    value: str           # E.164: "+5521996949389"
    is_mobile: bool

    @classmethod
    def create(cls, raw) -> Result[Self]:
        if raw is None or not isinstance(raw, str):
            return Result.failure("BrazilianPhone: valor obrigatório.")
        digits = _DIGITS_RE.sub("", raw)
        if not digits:
            return Result.failure(f"BrazilianPhone: '{raw}' sem dígitos.")

        # Remove DDI 55 se presente
        if len(digits) in (12, 13) and digits.startswith("55"):
            digits = digits[2:]

        if len(digits) not in (10, 11):
            return Result.failure(
                f"BrazilianPhone: '{raw}' deve ter 10 (fixo) ou 11 (celular) dígitos após o DDI."
            )

        ddd = int(digits[:2])
        if ddd not in _VALID_DDDS:
            return Result.failure(f"BrazilianPhone: DDD inválido ({ddd}).")

        is_mobile = len(digits) == 11
        if is_mobile and digits[2] != "9":
            return Result.failure("BrazilianPhone: celular deve começar com 9 após DDD.")
        if not is_mobile and digits[2] == "9":
            return Result.failure("BrazilianPhone: número fixo não deve começar com 9.")

        return Result.success(cls(value=f"+55{digits}", is_mobile=is_mobile))

    @property
    def ddd(self) -> str:
        return self.value[3:5]

    @property
    def national(self) -> str:
        rest = self.value[5:]
        if self.is_mobile:
            return f"({self.ddd}) {rest[:5]}-{rest[5:]}"
        return f"({self.ddd}) {rest[:4]}-{rest[4:]}"

    def __str__(self) -> str:
        return self.value
```

- [ ] **Step 4: Confirmar que passa**

Run: `.venv/bin/pytest tests/unit/domain/value_objects/test_brazilian_phone.py -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add app/domain/value_objects/brazilian_phone.py \
        tests/unit/domain/value_objects/test_brazilian_phone.py
git commit -m "feat(domain): add BrazilianPhone value object with E.164 normalization"
```

---

### Task 10: User entity

**Files:**
- Create: `app/domain/user/__init__.py`, `app/domain/user/user.py`
- Test: `tests/unit/domain/user/__init__.py`, `tests/unit/domain/user/test_user.py`

- [ ] **Step 1: Skeleton**

```bash
mkdir -p app/domain/user tests/unit/domain/user
touch app/domain/user/__init__.py tests/unit/domain/user/__init__.py
```

- [ ] **Step 2: Test falhando**

Create `tests/unit/domain/user/test_user.py`:
```python
import pytest
from app.domain.user.user import User


def test_cria_user_valido():
    r = User.create(
        name="João Silva",
        email="JOAO@EXEMPLO.com",
        phone="(21) 99694-9389",
        credit_score=85,
        balance=1500.50,
    )
    assert r.is_success, r.error
    u = r.value
    assert u.name == "João Silva"
    assert u.email.value == "joao@exemplo.com"
    assert u.phone.value == "+5521996949389"
    assert u.credit_score.value == 85.0
    assert u.balance.value == 1500.50


def test_rejeita_name_vazio():
    r = User.create(name="  ", email="a@b.com", phone="(21) 99694-9389")
    assert r.is_failure
    assert "name" in r.error


def test_agrega_erros_de_multiplos_vos():
    r = User.create(
        name="X",
        email="invalido",
        phone="00 00000 0000",
        credit_score=150,      # fora de range
        balance=-10,           # negativo
    )
    assert r.is_failure
    # Espera ver pelo menos 4 menções de erro agregadas
    err = r.error.lower()
    assert "email" in err
    assert "phone" in err or "brazilianphone" in err
    assert "percentage" in err or "credit" in err or "score" in err[:200]
    assert "negativ" in err


def test_change_email_valida_novo_email():
    u = User.create(name="X", email="a@b.com", phone="(21) 99694-9389").value
    old_updated = u.updated_at
    r = u.change_email("NEW@x.com")
    assert r.is_success
    assert u.email.value == "new@x.com"
    assert u.updated_at >= old_updated


def test_change_email_rejeita_invalido():
    u = User.create(name="X", email="a@b.com", phone="(21) 99694-9389").value
    r = u.change_email("not-an-email")
    assert r.is_failure
    assert u.email.value == "a@b.com"  # inalterado
```

- [ ] **Step 3: Confirmar falha**

Run: `.venv/bin/pytest tests/unit/domain/user/test_user.py -v`
Expected: FAIL.

- [ ] **Step 4: Implementar user.py**

Create `app/domain/user/user.py`:
```python
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Self
from app.domain.common.entity import BaseEntity
from app.domain.common.result import Result
from app.domain.value_objects.brazilian_phone import BrazilianPhone
from app.domain.value_objects.email import Email
from app.domain.value_objects.non_negative_float import NonNegativeFloat
from app.domain.value_objects.percentage import Percentage


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(slots=True, kw_only=True)
class User(BaseEntity):
    name: str
    email: Email
    phone: BrazilianPhone
    credit_score: Percentage
    balance: NonNegativeFloat

    @classmethod
    def create(
        cls,
        *,
        name: str,
        email: str,
        phone: str,
        credit_score: float = 0.0,
        balance: float = 0.0,
    ) -> Result[Self]:
        name_clean = (name or "").strip()
        errors: list[str] = []
        if not name_clean:
            errors.append("name: obrigatório.")

        email_r = Email.create(email)
        phone_r = BrazilianPhone.create(phone)
        score_r = Percentage.create(credit_score)
        balance_r = NonNegativeFloat.create(balance)

        for r in (email_r, phone_r, score_r, balance_r):
            if r.is_failure:
                errors.append(r.error)

        if errors:
            return Result.failure("; ".join(errors))

        return Result.success(cls(
            name=name_clean,
            email=email_r.value,
            phone=phone_r.value,
            credit_score=score_r.value,
            balance=balance_r.value,
        ))

    def change_email(self, new_email: str) -> Result[None]:
        r = Email.create(new_email)
        if r.is_failure:
            return Result.failure(r.error)
        self.email = r.value
        self.updated_at = _utcnow()
        return Result.success(None)
```

- [ ] **Step 5: Confirmar que passa**

Run: `.venv/bin/pytest tests/unit/domain/user/test_user.py -v`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add app/domain/user/__init__.py app/domain/user/user.py \
        tests/unit/domain/user/__init__.py tests/unit/domain/user/test_user.py
git commit -m "feat(domain): add User entity with aggregated VO validation"
```

---

### Task 11: IUserRepository Protocol

**Files:**
- Create: `app/domain/user/user_repository.py`

- [ ] **Step 1: Implementar Protocol**

Create `app/domain/user/user_repository.py`:
```python
from __future__ import annotations
from typing import Protocol, Sequence
from uuid import UUID
from app.domain.user.user import User


class IUserRepository(Protocol):
    async def get_by_id(self, user_id: UUID) -> User | None: ...
    async def get_by_email(self, email: str) -> User | None: ...
    async def list_active(
        self, *, limit: int = 50, offset: int = 0
    ) -> Sequence[User]: ...
    async def add(self, user: User) -> None: ...
    async def update(self, user: User) -> None: ...
    async def remove(self, user: User) -> None: ...
```

- [ ] **Step 2: Smoke — confirmar import**

Run:
```bash
.venv/bin/python -c "from app.domain.user.user_repository import IUserRepository; print('ok')"
```
Expected: `ok`.

- [ ] **Step 3: Rodar suite de domínio**

Run: `.venv/bin/pytest tests/unit/domain -v`
Expected: all pass.

- [ ] **Step 4: Commit**

```bash
git add app/domain/user/user_repository.py
git commit -m "feat(domain): add IUserRepository protocol"
```

---

## Fase C — Infrastructure

### Task 12: DB session, Base e UserModel

**Files:**
- Create: `app/infrastructure/__init__.py`, `app/infrastructure/db/__init__.py`, `app/infrastructure/db/session.py`, `app/infrastructure/db/base.py`, `app/infrastructure/db/models/__init__.py`, `app/infrastructure/db/models/user_model.py`

- [ ] **Step 1: Skeleton**

```bash
mkdir -p app/infrastructure/db/models
touch app/infrastructure/__init__.py app/infrastructure/db/__init__.py \
      app/infrastructure/db/models/__init__.py
```

- [ ] **Step 2: Implementar base.py**

Create `app/infrastructure/db/base.py`:
```python
from __future__ import annotations
from datetime import datetime, timezone
from sqlalchemy import DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def _utcnow():
    return datetime.now(timezone.utc)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False,
    )
```

- [ ] **Step 3: Implementar session.py**

Create `app/infrastructure/db/session.py`:
```python
from __future__ import annotations
from typing import AsyncIterator
from sqlalchemy.ext.asyncio import (
    AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine,
)
from app.core.config import get_settings

_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def init_engine() -> AsyncEngine:
    global _engine, _sessionmaker
    settings = get_settings()
    _engine = create_async_engine(
        settings.database_url,
        pool_size=settings.db_pool_size,
        pool_pre_ping=True,
        echo=settings.environment == "development",
    )
    _sessionmaker = async_sessionmaker(_engine, expire_on_commit=False)
    return _engine


async def dispose_engine() -> None:
    global _engine, _sessionmaker
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _sessionmaker = None


async def get_session() -> AsyncIterator[AsyncSession]:
    assert _sessionmaker is not None, "init_engine() não foi chamado no lifespan"
    async with _sessionmaker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
```

- [ ] **Step 4: Implementar user_model.py**

Create `app/infrastructure/db/models/user_model.py`:
```python
from __future__ import annotations
from uuid import UUID
from sqlalchemy import String, Float, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import CHAR
from app.infrastructure.db.base import Base, TimestampMixin


class UserModel(Base, TimestampMixin):
    __tablename__ = "users"

    # CHAR(36) funciona em Postgres, SQL Server e SQLite (para testes).
    # Para produção em Postgres, pode-se migrar para postgresql.UUID(as_uuid=True).
    id: Mapped[UUID] = mapped_column(CHAR(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str] = mapped_column(String(254), nullable=False, unique=True, index=True)
    phone: Mapped[str] = mapped_column(String(14), nullable=False)
    credit_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    balance: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
```

- [ ] **Step 5: Smoke test**

Run:
```bash
.venv/bin/python -c "
from app.infrastructure.db.base import Base
from app.infrastructure.db.models.user_model import UserModel
print('users columns:', [c.name for c in UserModel.__table__.columns])
"
```
Expected: `users columns: ['id', 'name', 'email', 'phone', 'credit_score', 'balance', 'is_active', 'created_at', 'updated_at']`

- [ ] **Step 6: Commit**

```bash
git add app/infrastructure/__init__.py app/infrastructure/db/__init__.py \
        app/infrastructure/db/base.py app/infrastructure/db/session.py \
        app/infrastructure/db/models/__init__.py \
        app/infrastructure/db/models/user_model.py
git commit -m "feat(infra): add DB session, Base, TimestampMixin and UserModel"
```

---

### Task 13: BaseRepository

**Files:**
- Create: `app/infrastructure/repositories/__init__.py`, `app/infrastructure/repositories/base_repository.py`

- [ ] **Step 1: Skeleton**

```bash
mkdir -p app/infrastructure/repositories
touch app/infrastructure/repositories/__init__.py
```

- [ ] **Step 2: Implementar base_repository.py**

Create `app/infrastructure/repositories/base_repository.py`:
```python
from __future__ import annotations
from typing import Generic, Sequence, TypeVar
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

TModel = TypeVar("TModel")


class BaseRepository(Generic[TModel]):
    def __init__(self, session: AsyncSession, model: type[TModel]) -> None:
        self._session = session
        self._model = model

    async def get_by_id(self, id: UUID) -> TModel | None:
        return await self._session.get(self._model, str(id))

    def add_row(self, row: TModel) -> None:
        self._session.add(row)

    async def remove_row(self, row: TModel) -> None:
        await self._session.delete(row)

    async def _first_or_default(self, stmt: Select) -> TModel | None:
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def _to_list(self, stmt: Select) -> Sequence[TModel]:
        return (await self._session.execute(stmt)).scalars().all()
```

- [ ] **Step 3: Smoke check**

Run:
```bash
.venv/bin/python -c "from app.infrastructure.repositories.base_repository import BaseRepository; print('ok')"
```
Expected: `ok`.

- [ ] **Step 4: Commit**

```bash
git add app/infrastructure/repositories/__init__.py \
        app/infrastructure/repositories/base_repository.py
git commit -m "feat(infra): add BaseRepository with session helpers"
```

---

### Task 14: UserRepository + integration tests

**Files:**
- Create: `app/infrastructure/repositories/user_repository.py`
- Test: `tests/integration/__init__.py`, `tests/integration/conftest.py`, `tests/integration/test_user_repository.py`

- [ ] **Step 1: Skeleton**

```bash
mkdir -p tests/integration
touch tests/integration/__init__.py
```

- [ ] **Step 2: conftest de integração**

Create `tests/integration/conftest.py`:
```python
from __future__ import annotations
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from app.infrastructure.db.base import Base
# Registra todos os modelos em Base.metadata:
from app.infrastructure.db.models import user_model  # noqa: F401


@pytest_asyncio.fixture
async def db_session() -> AsyncSession:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        yield s
    await engine.dispose()
```

- [ ] **Step 3: Test falhando**

Create `tests/integration/test_user_repository.py`:
```python
import pytest
from app.domain.user.user import User
from app.infrastructure.repositories.user_repository import UserRepository


@pytest.mark.asyncio
async def test_add_e_get_by_id(db_session):
    repo = UserRepository(db_session)
    user = User.create(
        name="Maria", email="maria@x.com",
        phone="(21) 99694-9389", credit_score=80, balance=2000,
    ).value
    await repo.add(user)
    await db_session.commit()

    fetched = await repo.get_by_id(user.id)
    assert fetched is not None
    assert fetched.email.value == "maria@x.com"
    assert fetched.phone.value == "+5521996949389"


@pytest.mark.asyncio
async def test_get_by_email_normaliza(db_session):
    repo = UserRepository(db_session)
    user = User.create(
        name="X", email="someone@x.com", phone="(21) 99694-9389",
    ).value
    await repo.add(user)
    await db_session.commit()

    fetched = await repo.get_by_email("  SOMEONE@X.COM  ")
    assert fetched is not None
    assert fetched.id == user.id


@pytest.mark.asyncio
async def test_list_active_ordenada_por_created_at_desc(db_session):
    repo = UserRepository(db_session)
    u1 = User.create(name="1", email="a@x.com", phone="(21) 99694-9389").value
    u2 = User.create(name="2", email="b@x.com", phone="(21) 99694-9388").value
    await repo.add(u1); await repo.add(u2)
    await db_session.commit()

    out = await repo.list_active()
    assert len(out) == 2


@pytest.mark.asyncio
async def test_update_sincroniza_colunas(db_session):
    repo = UserRepository(db_session)
    user = User.create(
        name="X", email="a@x.com", phone="(21) 99694-9389",
    ).value
    await repo.add(user)
    await db_session.commit()

    user.change_email("new@x.com")
    await repo.update(user)
    await db_session.commit()

    fetched = await repo.get_by_email("new@x.com")
    assert fetched is not None


@pytest.mark.asyncio
async def test_remove(db_session):
    repo = UserRepository(db_session)
    user = User.create(
        name="X", email="a@x.com", phone="(21) 99694-9389",
    ).value
    await repo.add(user)
    await db_session.commit()

    await repo.remove(user)
    await db_session.commit()

    assert await repo.get_by_id(user.id) is None
```

- [ ] **Step 4: Confirmar falha**

Run: `.venv/bin/pytest tests/integration/test_user_repository.py -v`
Expected: FAIL (no module user_repository).

- [ ] **Step 5: Implementar UserRepository**

Create `app/infrastructure/repositories/user_repository.py`:
```python
from __future__ import annotations
from typing import Sequence
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.user.user import User
from app.domain.user.user_repository import IUserRepository
from app.domain.value_objects.brazilian_phone import BrazilianPhone
from app.domain.value_objects.email import Email
from app.domain.value_objects.non_negative_float import NonNegativeFloat
from app.domain.value_objects.percentage import Percentage
from app.infrastructure.db.models.user_model import UserModel
from app.infrastructure.repositories.base_repository import BaseRepository


class UserRepository(BaseRepository[UserModel], IUserRepository):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, UserModel)

    async def get_by_id(self, user_id: UUID) -> User | None:
        row = await super().get_by_id(user_id)
        return self._to_entity(row) if row else None

    async def get_by_email(self, email: str) -> User | None:
        normalized = email.strip().lower()
        stmt = select(UserModel).where(UserModel.email == normalized)
        row = await self._first_or_default(stmt)
        return self._to_entity(row) if row else None

    async def list_active(self, *, limit: int = 50, offset: int = 0) -> Sequence[User]:
        stmt = (
            select(UserModel)
            .where(UserModel.is_active == True)
            .order_by(UserModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = await self._to_list(stmt)
        return [self._to_entity(r) for r in rows]

    async def add(self, user: User) -> None:
        self._session.add(self._to_model(user))

    async def update(self, user: User) -> None:
        row = await self._session.get(UserModel, str(user.id))
        if row is None:
            raise LookupError(f"User {user.id} not found.")
        row.name = user.name
        row.email = user.email.value
        row.phone = user.phone.value
        row.credit_score = user.credit_score.value
        row.balance = user.balance.value
        row.updated_at = user.updated_at

    async def remove(self, user: User) -> None:
        row = await self._session.get(UserModel, str(user.id))
        if row is not None:
            await self._session.delete(row)

    @staticmethod
    def _to_model(u: User) -> UserModel:
        return UserModel(
            id=str(u.id),
            name=u.name,
            email=u.email.value,
            phone=u.phone.value,
            credit_score=u.credit_score.value,
            balance=u.balance.value,
            is_active=True,
            created_at=u.created_at,
            updated_at=u.updated_at,
        )

    @staticmethod
    def _to_entity(row: UserModel) -> User:
        from uuid import UUID as _UUID
        return User(
            id=_UUID(str(row.id)),
            name=row.name,
            email=Email(value=row.email),
            phone=BrazilianPhone(value=row.phone, is_mobile=len(row.phone) == 14),
            credit_score=Percentage(value=row.credit_score),
            balance=NonNegativeFloat(value=row.balance),
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
```

- [ ] **Step 6: Confirmar que passa**

Run: `.venv/bin/pytest tests/integration/test_user_repository.py -v`
Expected: 5 passed.

- [ ] **Step 7: Commit**

```bash
git add app/infrastructure/repositories/user_repository.py \
        tests/integration/__init__.py tests/integration/conftest.py \
        tests/integration/test_user_repository.py
git commit -m "feat(infra): add UserRepository implementing IUserRepository with integration tests"
```

---

### Task 15: Redis client + CacheService

**Files:**
- Create: `app/infrastructure/cache/__init__.py`, `app/infrastructure/cache/redis_client.py`, `app/infrastructure/cache/cache_service.py`

- [ ] **Step 1: Skeleton**

```bash
mkdir -p app/infrastructure/cache
touch app/infrastructure/cache/__init__.py
```

- [ ] **Step 2: Implementar redis_client.py**

Create `app/infrastructure/cache/redis_client.py`:
```python
from __future__ import annotations
import redis.asyncio as redis_lib
from redis.asyncio.retry import Retry
from redis.backoff import NoBackoff
from app.core.config import get_settings


def build_redis_pool() -> redis_lib.ConnectionPool:
    s = get_settings()
    kwargs: dict = dict(
        host=s.redis_host,
        port=s.redis_port,
        decode_responses=False,
        socket_keepalive=True,
        health_check_interval=30,
        retry=Retry(NoBackoff(), retries=1),
        retry_on_error=[ConnectionError, TimeoutError, OSError, RuntimeError],
    )
    if s.environment != "development":
        kwargs["connection_class"] = redis_lib.SSLConnection
    if s.redis_username:
        kwargs["username"] = s.redis_username
    if s.redis_password.get_secret_value():
        kwargs["password"] = s.redis_password.get_secret_value()
    return redis_lib.ConnectionPool(**kwargs)
```

- [ ] **Step 3: Implementar cache_service.py**

Create `app/infrastructure/cache/cache_service.py`:
```python
from __future__ import annotations
import json
from typing import Any
import redis.asyncio as redis_lib
from app.domain.common.result import Result


class CacheService:
    def __init__(self, client: redis_lib.Redis) -> None:
        self._c = client

    async def get(self, key: str) -> Result[Any | None]:
        try:
            raw = await self._c.get(key)
            return Result.success(json.loads(raw) if raw else None)
        except Exception as e:
            return Result.from_exception(e, prefix="CacheService.get")

    async def set(self, key: str, value: Any, *, ttl_seconds: int | None = None) -> Result[None]:
        try:
            await self._c.set(key, json.dumps(value), ex=ttl_seconds)
            return Result.success(None)
        except Exception as e:
            return Result.from_exception(e, prefix="CacheService.set")

    async def delete(self, key: str) -> Result[None]:
        try:
            await self._c.delete(key)
            return Result.success(None)
        except Exception as e:
            return Result.from_exception(e, prefix="CacheService.delete")
```

- [ ] **Step 4: Smoke check**

Run:
```bash
.venv/bin/python -c "from app.infrastructure.cache.redis_client import build_redis_pool; from app.infrastructure.cache.cache_service import CacheService; print('ok')"
```
Expected: `ok`.

- [ ] **Step 5: Commit**

```bash
git add app/infrastructure/cache/__init__.py \
        app/infrastructure/cache/redis_client.py \
        app/infrastructure/cache/cache_service.py
git commit -m "feat(infra): add Redis pool builder and CacheService"
```

---

### Task 16: Verificação intermediária da fase C

- [ ] **Step 1: Rodar toda a suite até aqui**

Run: `.venv/bin/pytest tests -v`
Expected: todos os testes de unit + integration passando.

- [ ] **Step 2: Lint rápido**

Run: `.venv/bin/python -m ruff check app tests`
Expected: sem erros (ou apenas warnings aceitáveis).

Se houver erros, corrigir inline antes de prosseguir.

---

## Fase D — Application (CQRS)

### Task 17: DTOs

**Files:**
- Create: `app/application/__init__.py`, `app/application/dtos.py`
- Test: `tests/unit/application/__init__.py`, `tests/unit/application/test_dtos.py`

- [ ] **Step 1: Skeleton**

```bash
mkdir -p app/application tests/unit/application
touch app/application/__init__.py tests/unit/application/__init__.py
```

- [ ] **Step 2: Test falhando**

Create `tests/unit/application/test_dtos.py`:
```python
from app.application.dtos import UserDto
from app.domain.user.user import User


def test_user_dto_from_entity():
    u = User.create(
        name="A", email="a@x.com", phone="(21) 99694-9389",
        credit_score=75, balance=100.50,
    ).value
    d = UserDto.from_entity(u)
    assert d.id == u.id
    assert d.email == "a@x.com"
    assert d.phone == "+5521996949389"
    assert d.phone_display == "(21) 99694-9389"
    assert d.credit_score == 75.0
    assert d.balance == 100.50
```

- [ ] **Step 3: Confirmar falha**

Run: `.venv/bin/pytest tests/unit/application/test_dtos.py -v`
Expected: FAIL.

- [ ] **Step 4: Implementar**

Create `app/application/dtos.py`:
```python
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID
from app.domain.user.user import User


@dataclass(frozen=True, slots=True)
class UserDto:
    id: UUID
    name: str
    email: str
    phone: str
    phone_display: str
    credit_score: float
    balance: float
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_entity(cls, u: User) -> "UserDto":
        return cls(
            id=u.id,
            name=u.name,
            email=str(u.email),
            phone=str(u.phone),
            phone_display=u.phone.national,
            credit_score=u.credit_score.value,
            balance=u.balance.value,
            created_at=u.created_at,
            updated_at=u.updated_at,
        )
```

- [ ] **Step 5: Confirmar que passa**

Run: `.venv/bin/pytest tests/unit/application/test_dtos.py -v`
Expected: pass.

- [ ] **Step 6: Commit**

```bash
git add app/application/__init__.py app/application/dtos.py \
        tests/unit/application/__init__.py tests/unit/application/test_dtos.py
git commit -m "feat(application): add UserDto with from_entity"
```

---

### Task 18: InMemoryUserRepository fake (para testes)

**Files:**
- Create: `tests/unit/application/fakes/__init__.py`, `tests/unit/application/fakes/in_memory_user_repository.py`

- [ ] **Step 1: Skeleton**

```bash
mkdir -p tests/unit/application/fakes
touch tests/unit/application/fakes/__init__.py
```

- [ ] **Step 2: Implementar fake**

Create `tests/unit/application/fakes/in_memory_user_repository.py`:
```python
from __future__ import annotations
from typing import Sequence
from uuid import UUID
from app.domain.user.user import User
from app.domain.user.user_repository import IUserRepository


class InMemoryUserRepository(IUserRepository):
    def __init__(self) -> None:
        self._by_id: dict[UUID, User] = {}

    async def get_by_id(self, user_id: UUID) -> User | None:
        return self._by_id.get(user_id)

    async def get_by_email(self, email: str) -> User | None:
        normalized = email.strip().lower()
        return next(
            (u for u in self._by_id.values() if u.email.value == normalized),
            None,
        )

    async def list_active(
        self, *, limit: int = 50, offset: int = 0
    ) -> Sequence[User]:
        values = list(self._by_id.values())
        return values[offset: offset + limit]

    async def add(self, user: User) -> None:
        self._by_id[user.id] = user

    async def update(self, user: User) -> None:
        self._by_id[user.id] = user

    async def remove(self, user: User) -> None:
        self._by_id.pop(user.id, None)
```

- [ ] **Step 3: Commit**

```bash
git add tests/unit/application/fakes/__init__.py \
        tests/unit/application/fakes/in_memory_user_repository.py
git commit -m "test(application): add InMemoryUserRepository fake"
```

---

### Task 19: CreateUserHandler + tests

**Files:**
- Create: `app/application/commands/__init__.py`, `app/application/commands/create_user.py`
- Test: `tests/unit/application/test_create_user_handler.py`

- [ ] **Step 1: Skeleton**

```bash
mkdir -p app/application/commands
touch app/application/commands/__init__.py
```

- [ ] **Step 2: Test falhando**

Create `tests/unit/application/test_create_user_handler.py`:
```python
import pytest
from app.application.commands.create_user import CreateUserCommand, CreateUserHandler
from tests.unit.application.fakes.in_memory_user_repository import InMemoryUserRepository


@pytest.mark.asyncio
async def test_cria_user_valido():
    repo = InMemoryUserRepository()
    h = CreateUserHandler(repo)
    r = await h.handle(CreateUserCommand(
        name="João", email="joao@x.com", phone="(21) 99694-9389",
        credit_score=80, balance=500,
    ))
    assert r.is_success
    assert r.status_code == 201
    assert r.value.email == "joao@x.com"


@pytest.mark.asyncio
async def test_rejeita_email_duplicado():
    repo = InMemoryUserRepository()
    h = CreateUserHandler(repo)
    await h.handle(CreateUserCommand(
        name="A", email="dup@x.com", phone="(21) 99694-9389",
    ))
    r = await h.handle(CreateUserCommand(
        name="B", email="dup@x.com", phone="(21) 99694-9388",
    ))
    assert r.is_failure
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_rejeita_vo_invalido_422():
    repo = InMemoryUserRepository()
    h = CreateUserHandler(repo)
    r = await h.handle(CreateUserCommand(
        name="X", email="nao-eh-email", phone="xxx",
    ))
    assert r.is_failure
    assert r.status_code == 422
```

- [ ] **Step 3: Confirmar falha**

Run: `.venv/bin/pytest tests/unit/application/test_create_user_handler.py -v`
Expected: FAIL.

- [ ] **Step 4: Implementar**

Create `app/application/commands/create_user.py`:
```python
from __future__ import annotations
from dataclasses import dataclass
from app.application.dtos import UserDto
from app.domain.common.result import Result
from app.domain.user.user import User
from app.domain.user.user_repository import IUserRepository


@dataclass(frozen=True, slots=True)
class CreateUserCommand:
    name: str
    email: str
    phone: str
    credit_score: float = 0.0
    balance: float = 0.0


class CreateUserHandler:
    def __init__(self, users: IUserRepository) -> None:
        self._users = users

    async def handle(self, cmd: CreateUserCommand) -> Result[UserDto]:
        existing = await self._users.get_by_email(cmd.email)
        if existing is not None:
            return Result.failure(
                f"Email já cadastrado: {cmd.email}",
                status_code=409,
            )

        user_r = User.create(
            name=cmd.name,
            email=cmd.email,
            phone=cmd.phone,
            credit_score=cmd.credit_score,
            balance=cmd.balance,
        )
        if user_r.is_failure:
            return Result.failure(user_r.error, status_code=422)

        user = user_r.value
        await self._users.add(user)
        return Result.success(UserDto.from_entity(user), status_code=201)
```

- [ ] **Step 5: Confirmar que passa**

Run: `.venv/bin/pytest tests/unit/application/test_create_user_handler.py -v`
Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add app/application/commands/__init__.py app/application/commands/create_user.py \
        tests/unit/application/test_create_user_handler.py
git commit -m "feat(application): add CreateUserCommand + Handler"
```

---

### Task 20: GetUserByIdHandler + tests

**Files:**
- Create: `app/application/queries/__init__.py`, `app/application/queries/get_user_by_id.py`
- Test: `tests/unit/application/test_get_user_by_id_handler.py`

- [ ] **Step 1: Skeleton**

```bash
mkdir -p app/application/queries
touch app/application/queries/__init__.py
```

- [ ] **Step 2: Test falhando**

Create `tests/unit/application/test_get_user_by_id_handler.py`:
```python
from uuid import uuid4
import pytest
from app.application.queries.get_user_by_id import (
    GetUserByIdHandler, GetUserByIdQuery,
)
from app.domain.user.user import User
from tests.unit.application.fakes.in_memory_user_repository import InMemoryUserRepository


@pytest.mark.asyncio
async def test_retorna_user_existente():
    repo = InMemoryUserRepository()
    u = User.create(name="A", email="a@x.com", phone="(21) 99694-9389").value
    await repo.add(u)

    r = await GetUserByIdHandler(repo).handle(GetUserByIdQuery(user_id=u.id))
    assert r.is_success
    assert r.value.email == "a@x.com"


@pytest.mark.asyncio
async def test_retorna_404_quando_nao_existe():
    repo = InMemoryUserRepository()
    r = await GetUserByIdHandler(repo).handle(GetUserByIdQuery(user_id=uuid4()))
    assert r.is_failure
    assert r.status_code == 404
```

- [ ] **Step 3: Confirmar falha**

Run: `.venv/bin/pytest tests/unit/application/test_get_user_by_id_handler.py -v`
Expected: FAIL.

- [ ] **Step 4: Implementar**

Create `app/application/queries/get_user_by_id.py`:
```python
from __future__ import annotations
from dataclasses import dataclass
from uuid import UUID
from app.application.dtos import UserDto
from app.domain.common.result import Result
from app.domain.user.user_repository import IUserRepository


@dataclass(frozen=True, slots=True)
class GetUserByIdQuery:
    user_id: UUID


class GetUserByIdHandler:
    def __init__(self, users: IUserRepository) -> None:
        self._users = users

    async def handle(self, q: GetUserByIdQuery) -> Result[UserDto]:
        user = await self._users.get_by_id(q.user_id)
        if user is None:
            return Result.failure(
                f"Usuário {q.user_id} não encontrado.",
                status_code=404,
            )
        return Result.success(UserDto.from_entity(user))
```

- [ ] **Step 5: Confirmar que passa**

Run: `.venv/bin/pytest tests/unit/application/test_get_user_by_id_handler.py -v`
Expected: 2 passed.

- [ ] **Step 6: Commit**

```bash
git add app/application/queries/__init__.py \
        app/application/queries/get_user_by_id.py \
        tests/unit/application/test_get_user_by_id_handler.py
git commit -m "feat(application): add GetUserByIdQuery + Handler"
```

---

### Task 21: GetUserByEmailHandler + tests

**Files:**
- Create: `app/application/queries/get_user_by_email.py`
- Test: `tests/unit/application/test_get_user_by_email_handler.py`

- [ ] **Step 1: Test falhando**

Create `tests/unit/application/test_get_user_by_email_handler.py`:
```python
import pytest
from app.application.queries.get_user_by_email import (
    GetUserByEmailHandler, GetUserByEmailQuery,
)
from app.domain.user.user import User
from tests.unit.application.fakes.in_memory_user_repository import InMemoryUserRepository


@pytest.mark.asyncio
async def test_retorna_user_por_email_normalizado():
    repo = InMemoryUserRepository()
    u = User.create(name="A", email="Found@x.COM", phone="(21) 99694-9389").value
    await repo.add(u)

    r = await GetUserByEmailHandler(repo).handle(
        GetUserByEmailQuery(email="  FOUND@X.com  ")
    )
    assert r.is_success
    assert r.value.email == "found@x.com"


@pytest.mark.asyncio
async def test_404_quando_nao_existe():
    repo = InMemoryUserRepository()
    r = await GetUserByEmailHandler(repo).handle(
        GetUserByEmailQuery(email="ghost@x.com")
    )
    assert r.is_failure
    assert r.status_code == 404
```

- [ ] **Step 2: Confirmar falha**

Run: `.venv/bin/pytest tests/unit/application/test_get_user_by_email_handler.py -v`
Expected: FAIL.

- [ ] **Step 3: Implementar**

Create `app/application/queries/get_user_by_email.py`:
```python
from __future__ import annotations
from dataclasses import dataclass
from app.application.dtos import UserDto
from app.domain.common.result import Result
from app.domain.user.user_repository import IUserRepository


@dataclass(frozen=True, slots=True)
class GetUserByEmailQuery:
    email: str


class GetUserByEmailHandler:
    def __init__(self, users: IUserRepository) -> None:
        self._users = users

    async def handle(self, q: GetUserByEmailQuery) -> Result[UserDto]:
        user = await self._users.get_by_email(q.email)
        if user is None:
            return Result.failure(
                f"Nenhum usuário com email '{q.email}'.",
                status_code=404,
            )
        return Result.success(UserDto.from_entity(user))
```

- [ ] **Step 4: Confirmar que passa**

Run: `.venv/bin/pytest tests/unit/application/test_get_user_by_email_handler.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add app/application/queries/get_user_by_email.py \
        tests/unit/application/test_get_user_by_email_handler.py
git commit -m "feat(application): add GetUserByEmailQuery + Handler"
```

---

### Task 22: ListActiveUsersHandler + tests

**Files:**
- Create: `app/application/queries/list_active_users.py`
- Test: `tests/unit/application/test_list_active_users_handler.py`

- [ ] **Step 1: Test falhando**

Create `tests/unit/application/test_list_active_users_handler.py`:
```python
import pytest
from app.application.queries.list_active_users import (
    ListActiveUsersHandler, ListActiveUsersQuery,
)
from app.domain.user.user import User
from tests.unit.application.fakes.in_memory_user_repository import InMemoryUserRepository


@pytest.mark.asyncio
async def test_lista_todos_ate_limit():
    repo = InMemoryUserRepository()
    for i in range(3):
        u = User.create(
            name=f"U{i}", email=f"u{i}@x.com",
            phone="(21) 99694-9389",
        ).value
        await repo.add(u)

    r = await ListActiveUsersHandler(repo).handle(ListActiveUsersQuery())
    assert r.is_success
    assert len(r.value) == 3


@pytest.mark.asyncio
async def test_aplica_limit_e_offset():
    repo = InMemoryUserRepository()
    for i in range(5):
        u = User.create(
            name=f"U{i}", email=f"u{i}@x.com",
            phone="(21) 99694-9389",
        ).value
        await repo.add(u)

    r = await ListActiveUsersHandler(repo).handle(
        ListActiveUsersQuery(limit=2, offset=1)
    )
    assert r.is_success
    assert len(r.value) == 2
```

- [ ] **Step 2: Confirmar falha**

Run: `.venv/bin/pytest tests/unit/application/test_list_active_users_handler.py -v`
Expected: FAIL.

- [ ] **Step 3: Implementar**

Create `app/application/queries/list_active_users.py`:
```python
from __future__ import annotations
from dataclasses import dataclass
from app.application.dtos import UserDto
from app.domain.common.result import Result
from app.domain.user.user_repository import IUserRepository


@dataclass(frozen=True, slots=True)
class ListActiveUsersQuery:
    limit: int = 50
    offset: int = 0


class ListActiveUsersHandler:
    def __init__(self, users: IUserRepository) -> None:
        self._users = users

    async def handle(self, q: ListActiveUsersQuery) -> Result[list[UserDto]]:
        users = await self._users.list_active(limit=q.limit, offset=q.offset)
        return Result.success([UserDto.from_entity(u) for u in users])
```

- [ ] **Step 4: Confirmar que passa**

Run: `.venv/bin/pytest tests/unit/application/test_list_active_users_handler.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add app/application/queries/list_active_users.py \
        tests/unit/application/test_list_active_users_handler.py
git commit -m "feat(application): add ListActiveUsersQuery + Handler"
```

---

### Task 23: UpdateUserEmailHandler + tests

**Files:**
- Create: `app/application/commands/update_user_email.py`
- Test: `tests/unit/application/test_update_user_email_handler.py`

- [ ] **Step 1: Test falhando**

Create `tests/unit/application/test_update_user_email_handler.py`:
```python
from uuid import uuid4
import pytest
from app.application.commands.update_user_email import (
    UpdateUserEmailCommand, UpdateUserEmailHandler,
)
from app.domain.user.user import User
from tests.unit.application.fakes.in_memory_user_repository import InMemoryUserRepository


@pytest.mark.asyncio
async def test_atualiza_email_valido():
    repo = InMemoryUserRepository()
    u = User.create(name="A", email="old@x.com", phone="(21) 99694-9389").value
    await repo.add(u)

    r = await UpdateUserEmailHandler(repo).handle(
        UpdateUserEmailCommand(user_id=u.id, new_email="NEW@x.com")
    )
    assert r.is_success
    assert r.value.email == "new@x.com"


@pytest.mark.asyncio
async def test_404_quando_user_nao_existe():
    repo = InMemoryUserRepository()
    r = await UpdateUserEmailHandler(repo).handle(
        UpdateUserEmailCommand(user_id=uuid4(), new_email="x@x.com")
    )
    assert r.is_failure
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_422_quando_novo_email_invalido():
    repo = InMemoryUserRepository()
    u = User.create(name="A", email="old@x.com", phone="(21) 99694-9389").value
    await repo.add(u)

    r = await UpdateUserEmailHandler(repo).handle(
        UpdateUserEmailCommand(user_id=u.id, new_email="not-an-email")
    )
    assert r.is_failure
    assert r.status_code == 422
```

- [ ] **Step 2: Confirmar falha**

Run: `.venv/bin/pytest tests/unit/application/test_update_user_email_handler.py -v`
Expected: FAIL.

- [ ] **Step 3: Implementar**

Create `app/application/commands/update_user_email.py`:
```python
from __future__ import annotations
from dataclasses import dataclass
from uuid import UUID
from app.application.dtos import UserDto
from app.domain.common.result import Result
from app.domain.user.user_repository import IUserRepository


@dataclass(frozen=True, slots=True)
class UpdateUserEmailCommand:
    user_id: UUID
    new_email: str


class UpdateUserEmailHandler:
    def __init__(self, users: IUserRepository) -> None:
        self._users = users

    async def handle(self, cmd: UpdateUserEmailCommand) -> Result[UserDto]:
        user = await self._users.get_by_id(cmd.user_id)
        if user is None:
            return Result.failure(
                f"Usuário {cmd.user_id} não encontrado.",
                status_code=404,
            )

        change_r = user.change_email(cmd.new_email)
        if change_r.is_failure:
            return Result.failure(change_r.error, status_code=422)

        await self._users.update(user)
        return Result.success(UserDto.from_entity(user))
```

- [ ] **Step 4: Confirmar que passa**

Run: `.venv/bin/pytest tests/unit/application/test_update_user_email_handler.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add app/application/commands/update_user_email.py \
        tests/unit/application/test_update_user_email_handler.py
git commit -m "feat(application): add UpdateUserEmailCommand + Handler"
```

---

## Fase E — API Layer

### Task 24: Error handler + middleware

**Files:**
- Create: `app/api/__init__.py`, `app/api/error_handler.py`, `app/api/middleware.py`

- [ ] **Step 1: Skeleton**

```bash
mkdir -p app/api
touch app/api/__init__.py
```

- [ ] **Step 2: Implementar error_handler.py**

Create `app/api/error_handler.py`:
```python
from __future__ import annotations
import logging
from typing import TypeVar
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from app.domain.common.result import Result

T = TypeVar("T")
logger = logging.getLogger(__name__)


def unwrap(result: Result[T]) -> T:
    if result.is_success:
        return result.value  # type: ignore[return-value]
    raise HTTPException(
        status_code=result.status_code or 500,
        detail=result.error or "Erro interno.",
    )


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(Exception)
    async def on_unhandled(request: Request, exc: Exception):
        logger.exception(
            "Unhandled error on %s %s", request.method, request.url.path
        )
        return JSONResponse(
            status_code=500,
            content={"detail": f"{exc.__class__.__name__}: internal error."},
        )
```

- [ ] **Step 3: Implementar middleware.py**

Create `app/api/middleware.py`:
```python
from __future__ import annotations
import logging
import time
import uuid
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from app.core.context import correlation_id

logger = logging.getLogger(__name__)


class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        cid = request.headers.get("X-Correlation-Id") or uuid.uuid4().hex
        correlation_id.set(cid)
        start = time.perf_counter()
        try:
            response = await call_next(request)
            ms = (time.perf_counter() - start) * 1000
            logger.info(
                "%s %s -> %d (%.1fms)",
                request.method, request.url.path, response.status_code, ms,
            )
            response.headers["X-Correlation-Id"] = cid
            return response
        except Exception:
            ms = (time.perf_counter() - start) * 1000
            logger.exception(
                "%s %s -> ERROR (%.1fms)",
                request.method, request.url.path, ms,
            )
            raise
```

- [ ] **Step 4: Smoke check**

Run:
```bash
.venv/bin/python -c "
from app.api.error_handler import unwrap, register_exception_handlers
from app.api.middleware import LoggingMiddleware
print('ok')
"
```
Expected: `ok`.

- [ ] **Step 5: Commit**

```bash
git add app/api/__init__.py app/api/error_handler.py app/api/middleware.py
git commit -m "feat(api): add unwrap(Result) and LoggingMiddleware"
```

---

### Task 25: Schemas Pydantic

**Files:**
- Create: `app/api/v1/__init__.py`, `app/api/v1/schemas.py`

- [ ] **Step 1: Skeleton**

```bash
mkdir -p app/api/v1
touch app/api/v1/__init__.py
```

- [ ] **Step 2: Implementar**

Create `app/api/v1/schemas.py`:
```python
from __future__ import annotations
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field
from app.application.dtos import UserDto


class CreateUserRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    email: str
    phone: str
    credit_score: float = 0.0
    balance: float = 0.0


class UpdateUserEmailRequest(BaseModel):
    new_email: str


class UserResponse(BaseModel):
    id: UUID
    name: str
    email: str
    phone: str
    phone_display: str
    credit_score: float
    balance: float
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_dto(cls, d: UserDto) -> "UserResponse":
        return cls(
            id=d.id, name=d.name, email=d.email, phone=d.phone,
            phone_display=d.phone_display,
            credit_score=d.credit_score, balance=d.balance,
            created_at=d.created_at, updated_at=d.updated_at,
        )


class ListUsersResponse(BaseModel):
    items: list[UserResponse]
```

- [ ] **Step 3: Smoke**

Run: `.venv/bin/python -c "from app.api.v1.schemas import UserResponse, CreateUserRequest; print('ok')"`
Expected: `ok`.

- [ ] **Step 4: Commit**

```bash
git add app/api/v1/__init__.py app/api/v1/schemas.py
git commit -m "feat(api): add Pydantic request/response schemas for users"
```

---

### Task 26: API deps.py

**Files:**
- Create: `app/api/deps.py`

- [ ] **Step 1: Implementar**

Create `app/api/deps.py`:
```python
from __future__ import annotations
from typing import Annotated
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.commands.create_user import CreateUserHandler
from app.application.commands.update_user_email import UpdateUserEmailHandler
from app.application.queries.get_user_by_email import GetUserByEmailHandler
from app.application.queries.get_user_by_id import GetUserByIdHandler
from app.application.queries.list_active_users import ListActiveUsersHandler
from app.domain.user.user_repository import IUserRepository
from app.infrastructure.db.session import get_session
from app.infrastructure.repositories.user_repository import UserRepository


def get_user_repository(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> IUserRepository:
    return UserRepository(session)


UserRepo = Annotated[IUserRepository, Depends(get_user_repository)]


def get_create_user_handler(repo: UserRepo) -> CreateUserHandler:
    return CreateUserHandler(repo)


def get_update_user_email_handler(repo: UserRepo) -> UpdateUserEmailHandler:
    return UpdateUserEmailHandler(repo)


def get_get_user_by_id_handler(repo: UserRepo) -> GetUserByIdHandler:
    return GetUserByIdHandler(repo)


def get_get_user_by_email_handler(repo: UserRepo) -> GetUserByEmailHandler:
    return GetUserByEmailHandler(repo)


def get_list_active_users_handler(repo: UserRepo) -> ListActiveUsersHandler:
    return ListActiveUsersHandler(repo)
```

- [ ] **Step 2: Smoke**

Run: `.venv/bin/python -c "from app.api.deps import get_user_repository; print('ok')"`
Expected: `ok`.

- [ ] **Step 3: Commit**

```bash
git add app/api/deps.py
git commit -m "feat(api): add dependency wiring (session→repo→handlers)"
```

---

### Task 27: Users router

**Files:**
- Create: `app/api/v1/users.py`

- [ ] **Step 1: Implementar**

Create `app/api/v1/users.py`:
```python
from __future__ import annotations
from typing import Annotated
from uuid import UUID
from fastapi import APIRouter, Depends, Query

from app.api.deps import (
    get_create_user_handler, get_get_user_by_id_handler,
    get_list_active_users_handler, get_update_user_email_handler,
)
from app.api.error_handler import unwrap
from app.api.v1.schemas import (
    CreateUserRequest, ListUsersResponse, UpdateUserEmailRequest, UserResponse,
)
from app.application.commands.create_user import CreateUserCommand, CreateUserHandler
from app.application.commands.update_user_email import (
    UpdateUserEmailCommand, UpdateUserEmailHandler,
)
from app.application.queries.get_user_by_id import GetUserByIdHandler, GetUserByIdQuery
from app.application.queries.list_active_users import (
    ListActiveUsersHandler, ListActiveUsersQuery,
)

router = APIRouter(prefix="/v1/users", tags=["users"])


@router.post("", response_model=UserResponse, status_code=201)
async def create_user(
    req: CreateUserRequest,
    handler: Annotated[CreateUserHandler, Depends(get_create_user_handler)],
) -> UserResponse:
    result = await handler.handle(CreateUserCommand(
        name=req.name, email=req.email, phone=req.phone,
        credit_score=req.credit_score, balance=req.balance,
    ))
    return UserResponse.from_dto(unwrap(result))


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: UUID,
    handler: Annotated[GetUserByIdHandler, Depends(get_get_user_by_id_handler)],
) -> UserResponse:
    dto = unwrap(await handler.handle(GetUserByIdQuery(user_id=user_id)))
    return UserResponse.from_dto(dto)


@router.get("", response_model=ListUsersResponse)
async def list_users(
    handler: Annotated[ListActiveUsersHandler, Depends(get_list_active_users_handler)],
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> ListUsersResponse:
    items = unwrap(await handler.handle(ListActiveUsersQuery(limit=limit, offset=offset)))
    return ListUsersResponse(items=[UserResponse.from_dto(i) for i in items])


@router.patch("/{user_id}/email", response_model=UserResponse)
async def update_email(
    user_id: UUID,
    req: UpdateUserEmailRequest,
    handler: Annotated[UpdateUserEmailHandler, Depends(get_update_user_email_handler)],
) -> UserResponse:
    dto = unwrap(await handler.handle(UpdateUserEmailCommand(
        user_id=user_id, new_email=req.new_email,
    )))
    return UserResponse.from_dto(dto)
```

- [ ] **Step 2: Commit**

```bash
git add app/api/v1/users.py
git commit -m "feat(api): add users router (CRUD + list + update email)"
```

---

### Task 28: main.py (sem AI ainda)

**Files:**
- Create: `app/main.py`, `start_services.sh`

- [ ] **Step 1: Implementar main.py**

Create `app/main.py`:
```python
from __future__ import annotations
import logging
from contextlib import asynccontextmanager

import redis.asyncio as redis_lib
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from app.api.error_handler import register_exception_handlers
from app.api.middleware import LoggingMiddleware
from app.api.v1.users import router as users_router
from app.core.config import get_settings
from app.core.logging_config import setup_logging
from app.infrastructure.cache.redis_client import build_redis_pool
from app.infrastructure.db.session import dispose_engine, init_engine

setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_engine()
    pool = build_redis_pool()
    app.state.redis_client = redis_lib.Redis(connection_pool=pool)
    app.state.redis_pool = pool
    logger.info("DB engine + Redis pool inicializados.")
    yield
    await app.state.redis_client.aclose()
    await pool.aclose()
    await dispose_engine()
    logger.info("Recursos liberados.")


app = FastAPI(title="Backend Template", version="0.1.0", lifespan=lifespan)
app.add_middleware(LoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
register_exception_handlers(app)

app.include_router(users_router)


@app.get("/health", tags=["system"])
async def health() -> dict:
    return {"status": "ok"}


@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse(url="/docs")


def main() -> None:
    s = get_settings()
    uvicorn.run(
        "app.main:app",
        host=s.host, port=s.port,
        reload=s.environment == "development",
        proxy_headers=True, forwarded_allow_ips="*",
    )


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: start_services.sh**

Create `start_services.sh`:
```bash
#!/usr/bin/env bash
set -e
source .venv/bin/activate
exec python -m app.main
```

Then:
```bash
chmod +x start_services.sh
```

- [ ] **Step 3: Commit**

```bash
git add app/main.py start_services.sh
git commit -m "feat(api): add FastAPI app with lifespan, CORS, middleware and users router"
```

---

### Task 29: E2E tests for users API

**Files:**
- Create: `tests/e2e/__init__.py`, `tests/e2e/conftest.py`, `tests/e2e/test_users_api.py`

- [ ] **Step 1: Skeleton**

```bash
mkdir -p tests/e2e
touch tests/e2e/__init__.py
```

- [ ] **Step 2: conftest e2e**

Create `tests/e2e/conftest.py`:
```python
from __future__ import annotations
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from app.infrastructure.db import session as session_mod
from app.infrastructure.db.base import Base
from app.infrastructure.db.models import user_model  # noqa: F401
from app.main import app


@pytest_asyncio.fixture
async def client():
    # Substitui o engine por um sqlite in-memory isolado por teste
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_mod._engine = engine
    session_mod._sessionmaker = async_sessionmaker(engine, expire_on_commit=False)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

    await engine.dispose()
    session_mod._engine = None
    session_mod._sessionmaker = None
```

- [ ] **Step 3: Test falhando**

Create `tests/e2e/test_users_api.py`:
```python
import pytest


@pytest.mark.asyncio
async def test_health(client):
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_create_get_update_list(client):
    # create
    r = await client.post("/v1/users", json={
        "name": "João", "email": "JOAO@x.com",
        "phone": "(21) 99694-9389",
        "credit_score": 80, "balance": 1000,
    })
    assert r.status_code == 201, r.text
    user = r.json()
    assert user["email"] == "joao@x.com"
    assert user["phone"] == "+5521996949389"

    # get by id
    r2 = await client.get(f"/v1/users/{user['id']}")
    assert r2.status_code == 200
    assert r2.json()["id"] == user["id"]

    # update email
    r3 = await client.patch(
        f"/v1/users/{user['id']}/email",
        json={"new_email": "novo@x.com"},
    )
    assert r3.status_code == 200
    assert r3.json()["email"] == "novo@x.com"

    # list
    r4 = await client.get("/v1/users")
    assert r4.status_code == 200
    assert len(r4.json()["items"]) == 1


@pytest.mark.asyncio
async def test_422_em_vo_invalido(client):
    r = await client.post("/v1/users", json={
        "name": "X", "email": "not-email", "phone": "xxx",
    })
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_409_em_email_duplicado(client):
    payload = {
        "name": "A", "email": "dup@x.com", "phone": "(21) 99694-9389",
    }
    await client.post("/v1/users", json=payload)
    r = await client.post("/v1/users", json={**payload, "name": "B"})
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_404_quando_user_nao_existe(client):
    r = await client.get("/v1/users/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404
```

- [ ] **Step 4: Confirmar falha / rodar**

Run: `.venv/bin/pytest tests/e2e -v`
Expected: todos os 5 testes passando (código já foi escrito em tasks anteriores).

Se algum falhar, debugar antes de commitar.

- [ ] **Step 5: Commit**

```bash
git add tests/e2e/__init__.py tests/e2e/conftest.py tests/e2e/test_users_api.py
git commit -m "test(e2e): add users API coverage (201/200/422/409/404)"
```

---

## Fase F — Alembic + initial migration

### Task 30: Alembic setup

**Files:**
- Create: `alembic.ini`, `app/migrations/__init__.py`, `app/migrations/env.py`, `app/migrations/script.py.mako`, `app/migrations/versions/.gitkeep`

- [ ] **Step 1: alembic.ini**

Create `alembic.ini`:
```ini
[alembic]
script_location = app/migrations
file_template = %%(year)d%%(month).2d%%(day).2d_%%(hour).2d%%(minute).2d_%%(slug)s
sqlalchemy.url = driver://user:pass@localhost/dbname

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

- [ ] **Step 2: script.py.mako**

Create `app/migrations/script.py.mako`:
```python
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

revision: str = ${repr(up_revision)}
down_revision: Union[str, None] = ${repr(down_revision)}
branch_labels: Union[str, Sequence[str], None] = ${repr(branch_labels)}
depends_on: Union[str, Sequence[str], None] = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
```

- [ ] **Step 3: env.py**

Create `app/migrations/env.py`:
```python
from __future__ import annotations
import asyncio
from logging.config import fileConfig
from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.core.config import get_settings
from app.infrastructure.db.base import Base

# Registra modelos em Base.metadata (imports com side-effect).
# Adicionar novo model = adicionar o import aqui.
from app.infrastructure.db.models import user_model  # noqa: F401

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", get_settings().database_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    section = config.get_section(config.config_ini_section, {})
    connectable = async_engine_from_config(
        section, prefix="sqlalchemy.", poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
```

- [ ] **Step 4: Skeleton das versions**

```bash
mkdir -p app/migrations/versions
touch app/migrations/__init__.py app/migrations/versions/.gitkeep
```

- [ ] **Step 5: Commit scaffold**

```bash
git add alembic.ini app/migrations/__init__.py app/migrations/env.py \
        app/migrations/script.py.mako app/migrations/versions/.gitkeep
git commit -m "feat(migrations): add Alembic scaffold (env.py async + script template)"
```

---

### Task 31: Initial migration + roundtrip validation

- [ ] **Step 1: Setar DATABASE_URL para SQLite temporário**

```bash
cp .env.example .env
```

Edite `.env` e troque a `BACKEND_DATABASE_URL` para:
```
BACKEND_DATABASE_URL=sqlite+aiosqlite:///./dev.db
```

- [ ] **Step 2: Gerar migration inicial**

Run:
```bash
.venv/bin/alembic revision --autogenerate -m "initial users table"
```

Expected: arquivo novo em `app/migrations/versions/<timestamp>_initial_users_table.py` contendo `op.create_table("users", ...)`.

- [ ] **Step 3: Revisar o arquivo gerado**

Abra o arquivo gerado e confirme que `upgrade()` tem:
- `op.create_table("users", ...)` com colunas `id`, `name`, `email`, `phone`, `credit_score`, `balance`, `is_active`, `created_at`, `updated_at`.
- Index único em `email`.

E que `downgrade()` tem `op.drop_table("users")`.

- [ ] **Step 4: Aplicar migration**

Run:
```bash
.venv/bin/alembic upgrade head
```

Expected: sem erros, `dev.db` criado com a tabela `users`.

- [ ] **Step 5: Verificar**

Run:
```bash
.venv/bin/python -c "
import sqlite3
con = sqlite3.connect('dev.db')
rows = con.execute(\"SELECT name FROM sqlite_master WHERE type='table';\").fetchall()
print(rows)
"
```

Expected: `[('alembic_version',), ('users',)]`

- [ ] **Step 6: Downgrade roundtrip**

Run:
```bash
.venv/bin/alembic downgrade base
.venv/bin/alembic upgrade head
```

Expected: sem erros em nenhum dos dois.

- [ ] **Step 7: Commit**

```bash
git add app/migrations/versions/*.py
git commit -m "feat(migrations): add initial users table migration"
```

- [ ] **Step 8: Rodar suite inteira**

Run: `.venv/bin/pytest -v`
Expected: all green.

---

## Fase G — AI Module

### Task 32: AI deps, state, model factory, prompt

**Files:**
- Create: `app/ai/__init__.py`, `app/ai/state.py`, `app/ai/model_factory.py`, `app/ai/context.py`, `app/ai/prompts/system_prompt.txt`

- [ ] **Step 1: Instalar deps de AI**

Run:
```bash
.venv/bin/pip install -r requirements-ai.txt
```

Expected: langchain, langgraph, langsmith, etc. instalados.

- [ ] **Step 2: Skeleton**

```bash
mkdir -p app/ai/nodes app/ai/tools app/ai/prompts
touch app/ai/__init__.py app/ai/nodes/__init__.py app/ai/tools/__init__.py
```

- [ ] **Step 3: state.py**

Create `app/ai/state.py`:
```python
from __future__ import annotations
from typing import Annotated, TypedDict
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class ChatState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
```

- [ ] **Step 4: model_factory.py**

Create `app/ai/model_factory.py`:
```python
from __future__ import annotations
from functools import lru_cache
from langchain_core.language_models import BaseChatModel
from app.core.config import get_settings


@lru_cache(maxsize=1)
def get_chat_model() -> BaseChatModel:
    s = get_settings()
    common = dict(temperature=s.ai_temperature, streaming=True)
    provider = s.ai_provider.lower()
    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model=s.ai_model_name,
            api_key=s.ai_api_key.get_secret_value(),
            **common,
        )
    if provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=s.ai_model_name,
            api_key=s.ai_api_key.get_secret_value(),
            **common,
        )
    raise ValueError(f"AI provider não suportado: {s.ai_provider}")
```

- [ ] **Step 5: context.py**

Create `app/ai/context.py`:
```python
from __future__ import annotations
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.context import db_session


@asynccontextmanager
async def ai_tool_context(session: AsyncSession):
    """Expõe AsyncSession para tools do agente via ContextVar."""
    token = db_session.set(session)
    try:
        yield
    finally:
        db_session.reset(token)
```

- [ ] **Step 6: system_prompt.txt**

Create `app/ai/prompts/system_prompt.txt`:
```
Você é um assistente útil de atendimento ao cliente. Responda em português, de forma concisa.

Ferramentas disponíveis:
- get_current_time: quando precisar da hora atual em UTC.
- get_user_by_email: quando o usuário perguntar sobre um cliente mencionando o email dele.

Nunca invente dados de clientes — sempre use a ferramenta.
```

- [ ] **Step 7: Commit**

```bash
git add app/ai/__init__.py app/ai/state.py app/ai/model_factory.py \
        app/ai/context.py app/ai/nodes/__init__.py app/ai/tools/__init__.py \
        app/ai/prompts/system_prompt.txt
git commit -m "feat(ai): add state, model factory, context helper and system prompt"
```

---

### Task 33: AI tools (get_current_time + get_user_by_email)

**Files:**
- Create: `app/ai/tools/get_current_time.py`, `app/ai/tools/get_user_by_email.py`, `app/ai/tools/__init__.py` (sobrescrever)

- [ ] **Step 1: get_current_time tool**

Create `app/ai/tools/get_current_time.py`:
```python
from __future__ import annotations
from datetime import datetime, timezone
from langchain_core.tools import tool


@tool
def get_current_time() -> str:
    """Retorna a hora atual em UTC no formato ISO-8601."""
    return datetime.now(timezone.utc).isoformat()
```

- [ ] **Step 2: get_user_by_email tool**

Create `app/ai/tools/get_user_by_email.py`:
```python
from __future__ import annotations
import logging
from langchain_core.tools import tool

from app.application.queries.get_user_by_email import (
    GetUserByEmailHandler, GetUserByEmailQuery,
)
from app.core.context import db_session
from app.infrastructure.repositories.user_repository import UserRepository

logger = logging.getLogger(__name__)


@tool
async def get_user_by_email(email: str) -> str:
    """Busca um usuário pelo email. Retorna nome, telefone, score de crédito e saldo."""
    session = db_session.get()
    if session is None:
        logger.error("get_user_by_email chamada sem sessão de DB na ContextVar")
        return "Erro interno: contexto de banco não disponível."

    handler = GetUserByEmailHandler(UserRepository(session))
    result = await handler.handle(GetUserByEmailQuery(email=email))

    if result.is_failure:
        return result.error

    u = result.value
    return (
        f"Nome: {u.name}\n"
        f"Email: {u.email}\n"
        f"Telefone: {u.phone_display}\n"
        f"Score de crédito: {u.credit_score:.1f}%\n"
        f"Saldo: R$ {u.balance:.2f}"
    )
```

- [ ] **Step 3: Registry**

Overwrite `app/ai/tools/__init__.py`:
```python
from app.ai.tools.get_current_time import get_current_time
from app.ai.tools.get_user_by_email import get_user_by_email

TOOLS = [get_current_time, get_user_by_email]
TOOL_REGISTRY = {t.name: t for t in TOOLS}
```

- [ ] **Step 4: Smoke**

Run: `.venv/bin/python -c "from app.ai.tools import TOOLS, TOOL_REGISTRY; print([t.name for t in TOOLS])"`
Expected: `['get_current_time', 'get_user_by_email']`

- [ ] **Step 5: Commit**

```bash
git add app/ai/tools/__init__.py app/ai/tools/get_current_time.py \
        app/ai/tools/get_user_by_email.py
git commit -m "feat(ai): add get_current_time and get_user_by_email tools"
```

---

### Task 34: AI nodes (agent + tool_executor)

**Files:**
- Create: `app/ai/nodes/agent.py`, `app/ai/nodes/tool_executor.py`

- [ ] **Step 1: agent.py**

Create `app/ai/nodes/agent.py`:
```python
from __future__ import annotations
import logging
from pathlib import Path
from langchain_core.messages import SystemMessage

from app.ai.model_factory import get_chat_model
from app.ai.state import ChatState
from app.ai.tools import TOOLS

logger = logging.getLogger(__name__)

_PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "system_prompt.txt"
SYSTEM_PROMPT = _PROMPT_PATH.read_text(encoding="utf-8")


async def agent_node(state: ChatState) -> ChatState:
    model = get_chat_model().bind_tools(TOOLS)
    messages = [SystemMessage(content=SYSTEM_PROMPT), *state["messages"]]
    response = await model.ainvoke(messages)
    logger.debug(
        "agent_node: tool_calls=%s",
        bool(getattr(response, "tool_calls", None)),
    )
    return {"messages": [response]}
```

- [ ] **Step 2: tool_executor.py**

Create `app/ai/nodes/tool_executor.py`:
```python
from __future__ import annotations
import logging
from langchain_core.messages import ToolMessage

from app.ai.state import ChatState
from app.ai.tools import TOOL_REGISTRY

logger = logging.getLogger(__name__)


async def tool_executor_node(state: ChatState) -> ChatState:
    last = state["messages"][-1]
    calls = getattr(last, "tool_calls", []) or []
    outputs: list[ToolMessage] = []

    for call in calls:
        tool = TOOL_REGISTRY.get(call["name"])
        if tool is None:
            outputs.append(ToolMessage(
                tool_call_id=call["id"],
                content=f"Tool desconhecida: {call['name']}",
            ))
            continue
        try:
            result = await tool.ainvoke(call.get("args", {}))
        except Exception as e:
            logger.exception("Tool %s falhou", call["name"])
            result = f"Erro ao executar {call['name']}: {e}"
        outputs.append(ToolMessage(tool_call_id=call["id"], content=str(result)))

    return {"messages": outputs}
```

- [ ] **Step 3: Commit**

```bash
git add app/ai/nodes/agent.py app/ai/nodes/tool_executor.py
git commit -m "feat(ai): add agent and tool_executor nodes"
```

---

### Task 35: AI graph + streaming

**Files:**
- Create: `app/ai/graph.py`, `app/ai/streaming.py`

- [ ] **Step 1: graph.py**

Create `app/ai/graph.py`:
```python
from __future__ import annotations
from typing import Literal
from langgraph.graph import END, START, StateGraph

from app.ai.nodes.agent import agent_node
from app.ai.nodes.tool_executor import tool_executor_node
from app.ai.state import ChatState


def _route_after_agent(state: ChatState) -> Literal["tool_executor", "end"]:
    last = state["messages"][-1] if state["messages"] else None
    return "tool_executor" if getattr(last, "tool_calls", None) else "end"


def build_chat_graph() -> StateGraph:
    g = StateGraph(ChatState)
    g.add_node("agent", agent_node)
    g.add_node("tool_executor", tool_executor_node)

    g.add_edge(START, "agent")
    g.add_conditional_edges(
        "agent",
        _route_after_agent,
        {"tool_executor": "tool_executor", "end": END},
    )
    g.add_edge("tool_executor", "agent")
    return g
```

- [ ] **Step 2: streaming.py**

Create `app/ai/streaming.py`:
```python
from __future__ import annotations
import json
import logging
from typing import AsyncIterator
from uuid import uuid4
from langchain_core.messages import AIMessageChunk, HumanMessage
from langgraph.graph.state import CompiledStateGraph

logger = logging.getLogger(__name__)


def _sse(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


async def stream_chat(
    *,
    message: str,
    session_id: str | None,
    compiled_graph: CompiledStateGraph,
) -> AsyncIterator[str]:
    sid = session_id or uuid4().hex
    config = {"configurable": {"thread_id": sid}}

    yield _sse("session", {"session_id": sid})

    try:
        async for chunk, _meta in compiled_graph.astream(
            {"messages": [HumanMessage(content=message)]},
            config=config,
            stream_mode="messages",
        ):
            if isinstance(chunk, AIMessageChunk) and chunk.content:
                yield _sse("token", {"content": chunk.content})
        yield _sse("done", {})
    except Exception as e:
        logger.exception("Erro no stream de chat (session=%s)", sid)
        yield _sse("error", {"message": f"{type(e).__name__}: {e}"})
```

- [ ] **Step 3: Smoke — graph compila**

Run:
```bash
.venv/bin/python -c "
from app.ai.graph import build_chat_graph
g = build_chat_graph()
print('nodes:', list(g.nodes.keys()))
"
```
Expected: `nodes: ['agent', 'tool_executor']` (ou conjunto similar incluindo START).

- [ ] **Step 4: Commit**

```bash
git add app/ai/graph.py app/ai/streaming.py
git commit -m "feat(ai): add graph builder and SSE streaming"
```

---

### Task 36: AI chat router

**Files:**
- Create: `app/api/v1/ai_chat.py`

- [ ] **Step 1: Implementar router**

Create `app/api/v1/ai_chat.py`:
```python
from __future__ import annotations
from typing import Annotated
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.context import ai_tool_context
from app.ai.streaming import stream_chat
from app.infrastructure.db.session import get_session

router = APIRouter(prefix="/v1/ai", tags=["ai"])


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None


@router.post("/chat")
async def chat(
    req: ChatRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> StreamingResponse:
    compiled = request.app.state.chat_graph

    async def gen():
        async with ai_tool_context(session):
            async for chunk in stream_chat(
                message=req.message,
                session_id=req.session_id,
                compiled_graph=compiled,
            ):
                yield chunk

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
```

- [ ] **Step 2: Commit**

```bash
git add app/api/v1/ai_chat.py
git commit -m "feat(api): add AI chat router (SSE with ai_tool_context)"
```

---

### Task 37: Integrar AI no main.py

**Files:**
- Modify: `app/main.py`

- [ ] **Step 1: Atualizar main.py**

Overwrite `app/main.py`:
```python
from __future__ import annotations
import logging
from contextlib import asynccontextmanager

import redis.asyncio as redis_lib
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from app.api.error_handler import register_exception_handlers
from app.api.middleware import LoggingMiddleware
from app.api.v1.users import router as users_router
from app.core.config import get_settings
from app.core.logging_config import setup_logging
from app.infrastructure.cache.redis_client import build_redis_pool
from app.infrastructure.db.session import dispose_engine, init_engine

setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    init_engine()
    pool = build_redis_pool()
    redis_client = redis_lib.Redis(connection_pool=pool)
    app.state.redis_client = redis_client
    app.state.redis_pool = pool

    # AI module opcional — só carrega se provider != 'none'
    if settings.ai_provider != "none":
        from langgraph.checkpoint.redis.aio import AsyncRedisSaver
        from app.ai.graph import build_chat_graph
        from app.api.v1.ai_chat import router as ai_chat_router

        checkpointer = AsyncRedisSaver(
            redis_client=redis_client,
            ttl={"default_ttl": 7200, "refresh_on_read": True},
        )
        await checkpointer.asetup()
        app.state.chat_graph = build_chat_graph().compile(checkpointer=checkpointer)
        app.include_router(ai_chat_router)
        logger.info("AI module ativado (provider=%s).", settings.ai_provider)
    else:
        logger.info("AI module desativado (BACKEND_AI_PROVIDER=none).")

    logger.info("Startup completo.")
    yield

    await redis_client.aclose()
    await pool.aclose()
    await dispose_engine()
    logger.info("Recursos liberados.")


app = FastAPI(title="Backend Template", version="0.1.0", lifespan=lifespan)
app.add_middleware(LoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
register_exception_handlers(app)

app.include_router(users_router)


@app.get("/health", tags=["system"])
async def health() -> dict:
    return {"status": "ok"}


@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse(url="/docs")


def main() -> None:
    s = get_settings()
    uvicorn.run(
        "app.main:app",
        host=s.host, port=s.port,
        reload=s.environment == "development",
        proxy_headers=True, forwarded_allow_ips="*",
    )


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Rodar suite inteira**

Run: `.venv/bin/pytest -v`
Expected: all green (AI não é carregado porque `BACKEND_AI_PROVIDER=none` nos testes).

- [ ] **Step 3: Commit**

```bash
git add app/main.py
git commit -m "feat(api): conditionally load AI module in lifespan based on provider"
```

---

## Fase H — Docker + README

### Task 38: Dockerfile

**Files:**
- Create: `Dockerfile`

- [ ] **Step 1: Dockerfile**

Create `Dockerfile`:
```dockerfile
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential curl gnupg2 unixodbc-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements-postgres.txt ./
RUN pip install -r requirements.txt -r requirements-postgres.txt

# AI é opcional — descomente se for usar no container:
# COPY requirements-ai.txt ./
# RUN pip install -r requirements-ai.txt

COPY . .

EXPOSE 8000
CMD ["python", "-m", "app.main"]
```

- [ ] **Step 2: Commit**

```bash
git add Dockerfile
git commit -m "feat(docker): add Dockerfile (python 3.12-slim, base + postgres extras)"
```

---

### Task 39: README.md

**Files:**
- Create: `README.md`

- [ ] **Step 1: README.md**

Create `README.md`:
```markdown
# Backend Template

Python backend template, AI-ready, clonável como ponto de partida para novos projetos. Arquitetura em camadas com CQRS, Value Objects no domínio, SQLAlchemy async, Alembic, Redis e módulo opcional de IA com LangGraph.

Ver [docs/superpowers/specs/2026-04-24-backend-template-design.md](docs/superpowers/specs/2026-04-24-backend-template-design.md) para o design completo.

## Estrutura

```
app/
├── api/             # HTTP (FastAPI) — routers, schemas, deps, middleware
├── application/     # CQRS — commands, queries, handlers, DTOs
├── domain/          # Regras puras — entities, VOs, repository interfaces
├── infrastructure/  # Técnico — SQLAlchemy, Redis, external APIs
├── ai/              # Opcional — LangGraph, tools, streaming SSE
├── core/            # Cross-cutting — config, logging, context
├── migrations/      # Alembic
└── main.py
```

Regra de dependência: `api → application → domain ← infrastructure`. `domain` é puro Python.

## Setup

**Pré-requisitos:** Python 3.12, `uv`, Docker (para Redis local).

```bash
# 1. Cria venv e instala deps (base + dev)
make install

# 2. Instala o driver do DB escolhido
make install-postgres      # ou make install-mssql

# 3. (Opcional) Instala deps de IA
make install-ai

# 4. Configura o ambiente
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

Estrutura:
- `tests/unit/domain/` — VOs e entity, sem I/O.
- `tests/unit/application/` — handlers com `InMemoryUserRepository`.
- `tests/integration/` — UserRepository com SQLite in-memory.
- `tests/e2e/` — API completa via httpx.

## Adicionar nova entidade

1. Criar `app/domain/<entity>/<entity>.py` + VOs + `I<Entity>Repository`.
2. Criar `app/infrastructure/db/models/<entity>_model.py` e `app/infrastructure/repositories/<entity>_repository.py`.
3. Registrar import em `app/migrations/env.py`.
4. `make migrate-new msg="add <entity>"` e revisar.
5. `make migrate-up`.
6. Commands/Queries em `app/application/`.
7. Schemas + router em `app/api/v1/`.
8. Incluir router em `app/main.py`.
9. Testes.

## Módulo de IA

Controlado por `BACKEND_AI_PROVIDER` (`anthropic`, `openai` ou `none`).

Endpoint: `POST /v1/ai/chat` com body `{"message": "...", "session_id": "..."}` retorna SSE com frames `session`, `token`, `done`, `error`.

Tools em `app/ai/tools/`. A tool exemplo `get_user_by_email` mostra como integrar o agente com o domínio via query handler.

LangSmith: setar `LANGCHAIN_TRACING_V2=true` + `LANGCHAIN_API_KEY` ativa tracing automaticamente.

**Remover IA:** deletar `app/ai/`, não usar `requirements-ai.txt`, setar `BACKEND_AI_PROVIDER=none`. O `main.py` não carrega o módulo nesse caso.

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
| AI (opcional) | LangChain + LangGraph + LangSmith |
| Testes | pytest + pytest-asyncio + aiosqlite |
| Lint/Type | ruff + mypy |

## Licenças

Todos os componentes base são gratuitos para uso comercial em produto próprio. Detalhes em [docs/superpowers/specs/2026-04-24-backend-template-design.md](docs/superpowers/specs/2026-04-24-backend-template-design.md#2-stack-e-rationale-de-licenças).

Produção 100% permissiva: PostgreSQL + Valkey.
```

- [ ] **Step 2: Validação final — smoke test da stack inteira**

Run:
```bash
# Verifica todos os componentes carregam
.venv/bin/python -c "
from app.main import app
from app.infrastructure.db.session import get_session
from app.infrastructure.repositories.user_repository import UserRepository
from app.application.commands.create_user import CreateUserHandler
print('ok')
"
```

Expected: `ok`.

```bash
# Verifica Alembic vê os modelos
.venv/bin/alembic history
```

Expected: lista a migration inicial.

```bash
# Suite completa
.venv/bin/pytest -v
```

Expected: all green.

- [ ] **Step 3: Commit final**

```bash
git add README.md
git commit -m "docs: add README with setup, structure and usage"
```

---

## Critérios de aceitação (conforme spec Seção 14)

Ao final desta execução, todos os itens abaixo devem estar verdadeiros:

- [ ] `make install && make install-postgres && make migrate-up && make run` ergue a API em `/docs` (após configurar `.env`).
- [ ] `POST /v1/users` cria user válido (201), rejeita inválido (422), rejeita duplicado (409).
- [ ] `GET /v1/users/{id}` retorna 200 ou 404.
- [ ] `PATCH /v1/users/{id}/email` valida novo email via VO (200 ou 422).
- [ ] `POST /v1/ai/chat` (com `BACKEND_AI_PROVIDER` configurado) abre SSE com frames session/token/done.
- [ ] `get_user_by_email` tool responde corretamente quando email existe e quando não.
- [ ] Todos os VOs têm testes unitários cobrindo caminhos felizes + inválidos.
- [ ] `CreateUserHandler` e `GetUserByEmailHandler` têm testes com `InMemoryUserRepository`.
- [ ] Logs mostram correlation-id coerente em toda linha de um mesmo request.
- [ ] Deletar `app/ai/` + não usar `requirements-ai.txt` + setar `BACKEND_AI_PROVIDER=none` não quebra build nem testes do resto.
