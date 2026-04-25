# Backend Template Restructure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Aplicar vertical slicing por feature em `app/api/v1/`, `app/application/`, `app/domain/` (consolidando `common/` + `value_objects/` em `shared/`), renomear `infrastructure/db/models/` → `mappings/`, e espelhar a estrutura em `tests/`. **Zero mudança comportamental** — só refactor estrutural.

**Architecture:** Vertical slicing ortodoxo (DDD/Clean Arch). Cada feature tem suas próprias subpastas em domain/application/api/tests, isolada de outras features. `domain/shared/` abriga shared kernel (BaseEntity, Result) e VOs reutilizáveis (Email, Percentage, etc.). `infrastructure/repositories/` permanece flat. AI module (`app/ai/`) intacto estruturalmente, com imports atualizados.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0 async, Alembic, pytest-asyncio. Comandos via `make`. Renomeações com `git mv` para preservar histórico. Atualização de imports com `perl -pi -e` (portável macOS/Linux).

**Spec:** `docs/superpowers/specs/2026-04-24-backend-template-restructure-design.md`

**Working dir:** `/Users/klayver/Arke/Agilean/agent-workspace/backend-template`

**Pre-requisito:** rodar `make test` ANTES de começar; tem que estar tudo verde. Anotar quantidade de testes (será o baseline).

---

## Task 0: Baseline e branch

**Files:** —

- [ ] **Step 1: Criar branch dedicada para o refactor**

```bash
git checkout -b refactor/vertical-slicing
git status
```

Expected: branch criada, working tree limpa.

- [ ] **Step 2: Rodar baseline de testes e anotar quantidade**

```bash
make test 2>&1 | tail -20
```

Expected: todos os testes verdes. Anotar a linha tipo `==== N passed in Xs ====` — esse N é o **baseline** que tem que se manter ao longo do refactor.

- [ ] **Step 3: Smoke import baseline**

```bash
.venv/bin/python -c "from app.main import app; print('OK')"
```

Expected: `OK`.

---

## Task 1: Migrar `domain/common/` → `domain/shared/`

**Files:**
- Move: `app/domain/common/entity.py` → `app/domain/shared/entity.py`
- Move: `app/domain/common/result.py` → `app/domain/shared/result.py`
- Move: `app/domain/common/value_object.py` → `app/domain/shared/value_object.py`
- Move: `app/domain/common/__init__.py` → `app/domain/shared/__init__.py`
- Test: `tests/unit/domain/common/` → `tests/unit/domain/shared/`

- [ ] **Step 1: `git mv` da pasta inteira**

```bash
git mv app/domain/common app/domain/shared
git mv tests/unit/domain/common tests/unit/domain/shared
```

Expected: ambas as pastas renomeadas; `git status` mostra renames.

- [ ] **Step 2: Atualizar imports `app.domain.common` → `app.domain.shared` em todo o projeto**

```bash
grep -rl 'app\.domain\.common' app tests | xargs perl -pi -e 's/app\.domain\.common/app.domain.shared/g'
```

Expected: arquivos modificados:
- `app/domain/shared/value_object.py`
- `app/domain/user/user.py`
- `app/domain/value_objects/email.py`, `brazilian_phone.py`, `percentage.py`, `non_negative_float.py`
- `app/application/queries/*.py`, `app/application/commands/*.py`
- `app/infrastructure/cache/cache_service.py`
- `app/api/error_handler.py`
- `tests/unit/domain/shared/test_entity.py`, `test_result.py`

- [ ] **Step 3: Verificar que não restou nenhuma referência ao path antigo**

```bash
grep -rn 'app\.domain\.common' app tests || echo "OK: zero matches"
```

Expected: `OK: zero matches`.

- [ ] **Step 4: Rodar testes**

```bash
make test
```

Expected: mesmo N de testes que o baseline, todos verdes.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "refactor(domain): rename common/ to shared/

Shared kernel (BaseEntity, Result, ValueObject) + corresponding tests."
```

---

## Task 2: Consolidar `domain/value_objects/` em `domain/shared/value_objects/`

**Files:**
- Move: `app/domain/value_objects/email.py` → `app/domain/shared/value_objects/email.py`
- Move: `app/domain/value_objects/brazilian_phone.py` → `app/domain/shared/value_objects/brazilian_phone.py`
- Move: `app/domain/value_objects/percentage.py` → `app/domain/shared/value_objects/percentage.py`
- Move: `app/domain/value_objects/non_negative_float.py` → `app/domain/shared/value_objects/non_negative_float.py`
- Move: `app/domain/value_objects/__init__.py` → `app/domain/shared/value_objects/__init__.py`
- Test moves: `tests/unit/domain/value_objects/test_*.py` → `tests/unit/domain/shared/value_objects/test_*.py`

- [ ] **Step 1: Mover a pasta `value_objects/` para dentro de `shared/`**

```bash
git mv app/domain/value_objects app/domain/shared/value_objects
git mv tests/unit/domain/value_objects tests/unit/domain/shared/value_objects
```

Expected: ambas as pastas movidas; `git status` mostra renames.

- [ ] **Step 2: Atualizar imports em todo o projeto**

```bash
grep -rl 'app\.domain\.value_objects' app tests | xargs perl -pi -e 's/app\.domain\.value_objects/app.domain.shared.value_objects/g'
```

Expected: imports atualizados em:
- `app/domain/user/user.py`
- `app/infrastructure/repositories/user_repository.py`
- `tests/unit/domain/shared/value_objects/test_*.py`

- [ ] **Step 3: Verificar zero referências antigas**

```bash
grep -rn 'app\.domain\.value_objects' app tests || echo "OK: zero matches"
```

Expected: `OK: zero matches`.

- [ ] **Step 4: Rodar testes**

```bash
make test
```

Expected: mesmo N de testes que o baseline, todos verdes.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "refactor(domain): consolidate value_objects/ under shared/

Generic VOs (Email, BrazilianPhone, Percentage, NonNegativeFloat)
movem para domain/shared/value_objects/ — shared kernel."
```

---

## Task 3: Renomear `domain/user/user_repository.py` → `domain/user/repository.py`

**Files:**
- Move: `app/domain/user/user_repository.py` → `app/domain/user/repository.py`

- [ ] **Step 1: `git mv` do arquivo**

```bash
git mv app/domain/user/user_repository.py app/domain/user/repository.py
```

- [ ] **Step 2: Atualizar imports**

```bash
grep -rl 'app\.domain\.user\.user_repository' app tests | xargs perl -pi -e 's/app\.domain\.user\.user_repository/app.domain.user.repository/g'
```

Expected: imports atualizados em:
- `app/api/deps.py`
- `app/application/commands/*.py`, `app/application/queries/*.py`
- `app/infrastructure/repositories/user_repository.py`
- `tests/unit/application/fakes/in_memory_user_repository.py`

- [ ] **Step 3: Verificar zero referências antigas**

```bash
grep -rn 'app\.domain\.user\.user_repository' app tests || echo "OK: zero matches"
```

Expected: `OK: zero matches`.

- [ ] **Step 4: Rodar testes**

```bash
make test
```

Expected: mesmo N, todos verdes.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "refactor(domain): rename user_repository.py to repository.py

A pasta user/ já dá o contexto — drop the redundant prefix."
```

---

## Task 4: Renomear `infrastructure/db/models/` → `mappings/` e arquivo `user_model.py` → `user.py`

**Files:**
- Move: `app/infrastructure/db/models/` → `app/infrastructure/db/mappings/`
- Move: `app/infrastructure/db/mappings/user_model.py` → `app/infrastructure/db/mappings/user.py`
- Modify: `app/migrations/env.py` (atualizar import)

- [ ] **Step 1: Renomear pasta e arquivo**

```bash
git mv app/infrastructure/db/models app/infrastructure/db/mappings
git mv app/infrastructure/db/mappings/user_model.py app/infrastructure/db/mappings/user.py
```

- [ ] **Step 2: Atualizar imports `app.infrastructure.db.models.user_model` → `app.infrastructure.db.mappings.user`**

```bash
grep -rl 'app\.infrastructure\.db\.models\.user_model' app tests | xargs perl -pi -e 's/app\.infrastructure\.db\.models\.user_model/app.infrastructure.db.mappings.user/g'
```

Expected: arquivos modificados:
- `app/infrastructure/repositories/user_repository.py`

- [ ] **Step 3: Atualizar imports `from app.infrastructure.db.models import user_model` → `from app.infrastructure.db.mappings import user`**

```bash
grep -rl 'app\.infrastructure\.db\.models import user_model' app tests | xargs perl -pi -e 's/app\.infrastructure\.db\.models import user_model/app.infrastructure.db.mappings import user/g'
```

Expected: arquivos modificados:
- `app/migrations/env.py`
- `tests/integration/conftest.py`
- `tests/e2e/conftest.py`

- [ ] **Step 4: Cobertura adicional para `app.infrastructure.db.models` genérico (se sobrar)**

```bash
grep -rl 'app\.infrastructure\.db\.models' app tests | xargs perl -pi -e 's/app\.infrastructure\.db\.models/app.infrastructure.db.mappings/g'
```

- [ ] **Step 5: Verificar zero referências antigas**

```bash
grep -rn 'app\.infrastructure\.db\.models' app tests || echo "OK: zero matches"
grep -rn 'user_model' app tests || echo "OK: zero matches"
```

Expected: `OK: zero matches` em ambos.

- [ ] **Step 6: Confirmar que classe `UserModel` permanece com esse nome**

```bash
grep -n 'class UserModel' app/infrastructure/db/mappings/user.py
```

Expected: linha como `class UserModel(Base, TimestampMixin):` — a CLASSE permanece `UserModel`, só o ARQUIVO mudou de nome.

- [ ] **Step 7: Rodar testes**

```bash
make test
```

Expected: mesmo N, todos verdes.

- [ ] **Step 8: Validar registro de modelos em `Base.metadata`**

```bash
.venv/bin/python -c "
from app.infrastructure.db.base import Base
from app.infrastructure.db.mappings import user  # registra UserModel
tables = Base.metadata.tables
assert 'users' in tables, f'tabela users não registrada. tables={list(tables)}'
cols = sorted(c.name for c in tables['users'].columns)
expected = ['balance', 'created_at', 'credit_score', 'email', 'id', 'is_active', 'name', 'phone', 'updated_at']
assert cols == expected, f'colunas divergentes: {cols} vs {expected}'
print('OK: schema preservado')
"
```

Expected: `OK: schema preservado`. Se falhar, o módulo `mappings/user.py` não está sendo importado / registrado — investigar antes de commit.

- [ ] **Step 9 (opcional, requer DB ativo): Validação Alembic — diff vazio**

Pular se não houver DB configurado em `.env`. Caso contrário:

```bash
make migrate-new msg="post_refactor_check_task4"
```

Abrir o arquivo gerado em `app/migrations/versions/` e confirmar que `upgrade()` e `downgrade()` estão **vazios** (só `pass`). Se houver operação, falhou.

Apagar a migration de validação:

```bash
rm $(ls -t app/migrations/versions/*post_refactor_check_task4*.py)
```

- [ ] **Step 10: Commit**

```bash
git add -A
git commit -m "refactor(infra): rename db/models/ to db/mappings/

Diferencia mapeamento O/R (mappings/) da entidade de domínio
(domain/user/user.py). Arquivo user_model.py vira user.py
(pasta já dá o contexto). Classe UserModel permanece."
```

---

## Task 5: Vertical slicing em `app/application/` — feature `users`

**Files:**
- Create: `app/application/users/__init__.py`
- Create: `app/application/users/commands/__init__.py`
- Create: `app/application/users/queries/__init__.py`
- Move: `app/application/dtos.py` → `app/application/users/dtos.py`
- Move: `app/application/commands/create_user.py` → `app/application/users/commands/create_user.py`
- Move: `app/application/commands/update_user_email.py` → `app/application/users/commands/update_user_email.py`
- Move: `app/application/queries/get_user_by_id.py` → `app/application/users/queries/get_user_by_id.py`
- Move: `app/application/queries/get_user_by_email.py` → `app/application/users/queries/get_user_by_email.py`
- Move: `app/application/queries/list_active_users.py` → `app/application/users/queries/list_active_users.py`
- Delete: `app/application/commands/__init__.py`, `app/application/queries/__init__.py` (após mover, pastas vazias)

- [ ] **Step 1: Criar pastas vazias (com `__init__.py`) para a nova estrutura**

```bash
mkdir -p app/application/users/commands app/application/users/queries
touch app/application/users/__init__.py
touch app/application/users/commands/__init__.py
touch app/application/users/queries/__init__.py
```

- [ ] **Step 2: Mover `dtos.py`**

```bash
git mv app/application/dtos.py app/application/users/dtos.py
```

- [ ] **Step 3: Mover commands**

```bash
git mv app/application/commands/create_user.py app/application/users/commands/create_user.py
git mv app/application/commands/update_user_email.py app/application/users/commands/update_user_email.py
```

- [ ] **Step 4: Mover queries**

```bash
git mv app/application/queries/get_user_by_id.py app/application/users/queries/get_user_by_id.py
git mv app/application/queries/get_user_by_email.py app/application/users/queries/get_user_by_email.py
git mv app/application/queries/list_active_users.py app/application/users/queries/list_active_users.py
```

- [ ] **Step 5: Remover pastas antigas vazias (após mover, só o `__init__.py` antigo sobra)**

```bash
git rm app/application/commands/__init__.py
git rm app/application/queries/__init__.py
rmdir app/application/commands app/application/queries
```

Expected: pastas `commands/` e `queries/` no nível antigo deixam de existir.

- [ ] **Step 6: Atualizar imports — `app.application.dtos` → `app.application.users.dtos`**

```bash
grep -rl 'app\.application\.dtos' app tests | xargs perl -pi -e 's/app\.application\.dtos/app.application.users.dtos/g'
```

- [ ] **Step 7: Atualizar imports — `app.application.commands.create_user` → `app.application.users.commands.create_user`**

```bash
grep -rl 'app\.application\.commands\.create_user' app tests | xargs perl -pi -e 's/app\.application\.commands\.create_user/app.application.users.commands.create_user/g'
```

- [ ] **Step 8: Atualizar imports — `app.application.commands.update_user_email` → `app.application.users.commands.update_user_email`**

```bash
grep -rl 'app\.application\.commands\.update_user_email' app tests | xargs perl -pi -e 's/app\.application\.commands\.update_user_email/app.application.users.commands.update_user_email/g'
```

- [ ] **Step 9: Atualizar imports — `app.application.queries.get_user_by_id` → `app.application.users.queries.get_user_by_id`**

```bash
grep -rl 'app\.application\.queries\.get_user_by_id' app tests | xargs perl -pi -e 's/app\.application\.queries\.get_user_by_id/app.application.users.queries.get_user_by_id/g'
```

- [ ] **Step 10: Atualizar imports — `app.application.queries.get_user_by_email` → `app.application.users.queries.get_user_by_email`**

```bash
grep -rl 'app\.application\.queries\.get_user_by_email' app tests | xargs perl -pi -e 's/app\.application\.queries\.get_user_by_email/app.application.users.queries.get_user_by_email/g'
```

- [ ] **Step 11: Atualizar imports — `app.application.queries.list_active_users` → `app.application.users.queries.list_active_users`**

```bash
grep -rl 'app\.application\.queries\.list_active_users' app tests | xargs perl -pi -e 's/app\.application\.queries\.list_active_users/app.application.users.queries.list_active_users/g'
```

- [ ] **Step 12: Verificar zero referências antigas**

```bash
grep -rEn 'app\.application\.(dtos|commands|queries)' app tests || echo "OK: zero matches"
```

Expected: `OK: zero matches`.

- [ ] **Step 13: Rodar testes**

```bash
make test
```

Expected: mesmo N, todos verdes.

- [ ] **Step 14: Commit**

```bash
git add -A
git commit -m "refactor(application): vertical slicing for users feature

application/dtos.py -> application/users/dtos.py
application/commands/* -> application/users/commands/*
application/queries/* -> application/users/queries/*

Ortodoxo DDD/Clean Arch: tudo da feature 'users' agrupado."
```

---

## Task 6: Vertical slicing em `app/api/v1/` — feature `users` (rotas + schemas + deps)

**Files:**
- Create: `app/api/v1/users/__init__.py` (re-export `router`)
- Create: `app/api/v1/users/deps.py` (DI específica de user)
- Move: `app/api/v1/users.py` → `app/api/v1/users/routes.py`
- Move: `app/api/v1/schemas.py` → `app/api/v1/users/schemas.py`
- Modify: `app/api/deps.py` (esvazia — só docstring + import de `get_session` se houver)

- [ ] **Step 1: Criar pasta `users/`**

```bash
mkdir -p app/api/v1/users
```

- [ ] **Step 2: Mover `users.py` → `users/routes.py` e `schemas.py` → `users/schemas.py`**

```bash
git mv app/api/v1/users.py app/api/v1/users/routes.py
git mv app/api/v1/schemas.py app/api/v1/users/schemas.py
```

- [ ] **Step 3: Criar `app/api/v1/users/__init__.py` re-exportando `router`**

Conteúdo do arquivo:

```python
from .routes import router

__all__ = ["router"]
```

- [ ] **Step 4: Criar `app/api/v1/users/deps.py` com a DI de users**

Conteúdo do arquivo (copiado de `app/api/deps.py` — todos os getters):

```python
from __future__ import annotations
from typing import Annotated
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.users.commands.create_user import CreateUserHandler
from app.application.users.commands.update_user_email import UpdateUserEmailHandler
from app.application.users.queries.get_user_by_email import GetUserByEmailHandler
from app.application.users.queries.get_user_by_id import GetUserByIdHandler
from app.application.users.queries.list_active_users import ListActiveUsersHandler
from app.domain.user.repository import IUserRepository
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

- [ ] **Step 5: Atualizar `app/api/v1/users/routes.py` para importar de `app.api.v1.users.deps` ao invés de `app.api.deps`**

```bash
perl -pi -e 's/from app\.api\.deps import/from app.api.v1.users.deps import/g' app/api/v1/users/routes.py
perl -pi -e 's/from app\.api\.v1\.schemas import/from app.api.v1.users.schemas import/g' app/api/v1/users/routes.py
```

- [ ] **Step 6: Esvaziar `app/api/deps.py` deixando apenas docstring**

Reescrever `app/api/deps.py` com este conteúdo:

```python
"""Cross-cutting API dependencies (e.g., authenticated user, request context).

DI específica de feature mora em `app/api/v1/<feature>/deps.py`.
Este módulo recebe DIs compartilhadas entre features (ex.: `get_current_user`,
rate limiter) à medida que forem adicionadas.
"""
from __future__ import annotations
```

- [ ] **Step 7: Atualizar imports nos consumidores externos (testes e2e, se houver)**

```bash
grep -rln 'from app\.api\.deps import' tests | xargs --no-run-if-empty perl -pi -e 's/from app\.api\.deps import/from app.api.v1.users.deps import/g'
```

Nota: o `users/routes.py` já foi atualizado no step 5.

- [ ] **Step 8: Verificar zero imports vindo de `app.api.v1.schemas` e `app.api.deps`**

```bash
grep -rn 'from app\.api\.v1\.schemas' app tests || echo "OK: schemas zero matches"
grep -rn 'from app\.api\.deps import get_' app tests || echo "OK: deps user-getters zero matches"
```

Expected: ambos `OK: zero matches`.

- [ ] **Step 9: Rodar testes**

```bash
make test
```

Expected: mesmo N, todos verdes.

- [ ] **Step 10: Commit**

```bash
git add -A
git commit -m "refactor(api): vertical slicing for users feature

api/v1/users.py -> api/v1/users/routes.py
api/v1/schemas.py -> api/v1/users/schemas.py
+ api/v1/users/__init__.py (re-exporta router)
+ api/v1/users/deps.py (DI específica de users)

api/deps.py central esvazia, fica como entry-point para
DIs cross-cutting futuras (get_current_user, etc.)."
```

---

## Task 7: Mover `app/api/v1/ai_chat.py` para pasta `ai_chat/`

**Files:**
- Move: `app/api/v1/ai_chat.py` → `app/api/v1/ai_chat/routes.py`
- Create: `app/api/v1/ai_chat/__init__.py` (re-export `router`)

- [ ] **Step 1: Criar pasta e mover arquivo**

```bash
mkdir -p app/api/v1/ai_chat
git mv app/api/v1/ai_chat.py app/api/v1/ai_chat/routes.py
```

- [ ] **Step 2: Criar `app/api/v1/ai_chat/__init__.py`**

Conteúdo:

```python
from .routes import router

__all__ = ["router"]
```

- [ ] **Step 3: Validar que `app/main.py` ainda funciona sem alteração (re-export resolve)**

```bash
.venv/bin/python -c "from app.api.v1.ai_chat import router; print('OK')"
```

Expected: `OK`.

- [ ] **Step 4: Rodar testes**

```bash
make test
```

Expected: mesmo N, todos verdes.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "refactor(api): turn ai_chat.py into ai_chat/ package

Consistência com vertical slicing. __init__.py re-exporta router,
então imports em main.py permanecem idênticos."
```

---

## Task 8: Criar `app/api/v1/router.py` agregador e atualizar `main.py`

**Files:**
- Create: `app/api/v1/router.py`
- Modify: `app/main.py`

- [ ] **Step 1: Criar `app/api/v1/router.py`**

Conteúdo:

```python
"""API router agregador: include cada feature router aqui.

Uso em main.py:
    from app.api.v1.router import api_router
    app.include_router(api_router)

Features que dependem de configuração runtime (ex.: ai_chat depende de
ai_provider) continuam sendo incluídas condicionalmente em main.py
no lifespan, fora deste agregador.
"""
from fastapi import APIRouter

from app.api.v1.users import router as users_router

api_router = APIRouter()
api_router.include_router(users_router)
```

- [ ] **Step 2: Atualizar `app/main.py`**

Localizar a linha:
```python
from app.api.v1.users import router as users_router
```
Substituir por:
```python
from app.api.v1.router import api_router
```

E localizar a linha:
```python
app.include_router(users_router)
```
Substituir por:
```python
app.include_router(api_router)
```

Comandos:

```bash
perl -pi -e 's/from app\.api\.v1\.users import router as users_router/from app.api.v1.router import api_router/g' app/main.py
perl -pi -e 's/app\.include_router\(users_router\)/app.include_router(api_router)/g' app/main.py
```

- [ ] **Step 3: Smoke import**

```bash
.venv/bin/python -c "from app.main import app; print([r.path for r in app.routes if hasattr(r, 'path')])"
```

Expected: lista incluindo `/v1/users`, `/v1/users/{user_id}`, etc.

- [ ] **Step 4: Rodar testes**

```bash
make test
```

Expected: mesmo N, todos verdes.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat(api): add v1 router aggregator

api/v1/router.py concentra include_router de cada feature.
main.py passa a usar api_router; ai_chat continua condicional
no lifespan (depende de ai_provider)."
```

---

## Task 9: Realinhar testes — espelhar nova estrutura

**Files:** múltiplos. Ver mapa abaixo.

**Mapa de moves:**

| Origem | Destino |
|---|---|
| `tests/unit/application/test_create_user_handler.py` | `tests/unit/application/users/commands/test_create_user.py` |
| `tests/unit/application/test_update_user_email_handler.py` | `tests/unit/application/users/commands/test_update_user_email.py` |
| `tests/unit/application/test_get_user_by_id_handler.py` | `tests/unit/application/users/queries/test_get_user_by_id.py` |
| `tests/unit/application/test_get_user_by_email_handler.py` | `tests/unit/application/users/queries/test_get_user_by_email.py` |
| `tests/unit/application/test_list_active_users_handler.py` | `tests/unit/application/users/queries/test_list_active_users.py` |
| `tests/unit/application/test_dtos.py` | `tests/unit/application/users/test_dtos.py` |
| `tests/unit/application/fakes/in_memory_user_repository.py` | `tests/unit/application/users/fakes/in_memory_user_repository.py` |
| `tests/integration/test_user_repository.py` | `tests/integration/users/test_repository.py` |
| `tests/e2e/test_users_api.py` | `tests/e2e/users/test_api.py` |

- [ ] **Step 1: Criar pastas de destino e seus `__init__.py`**

```bash
mkdir -p tests/unit/application/users/commands
mkdir -p tests/unit/application/users/queries
mkdir -p tests/unit/application/users/fakes
mkdir -p tests/integration/users
mkdir -p tests/e2e/users
touch tests/unit/application/users/__init__.py
touch tests/unit/application/users/commands/__init__.py
touch tests/unit/application/users/queries/__init__.py
touch tests/unit/application/users/fakes/__init__.py
touch tests/integration/users/__init__.py
touch tests/e2e/users/__init__.py
```

- [ ] **Step 2: Mover testes de `application/` (commands)**

```bash
git mv tests/unit/application/test_create_user_handler.py tests/unit/application/users/commands/test_create_user.py
git mv tests/unit/application/test_update_user_email_handler.py tests/unit/application/users/commands/test_update_user_email.py
```

- [ ] **Step 3: Mover testes de `application/` (queries)**

```bash
git mv tests/unit/application/test_get_user_by_id_handler.py tests/unit/application/users/queries/test_get_user_by_id.py
git mv tests/unit/application/test_get_user_by_email_handler.py tests/unit/application/users/queries/test_get_user_by_email.py
git mv tests/unit/application/test_list_active_users_handler.py tests/unit/application/users/queries/test_list_active_users.py
```

- [ ] **Step 4: Mover `test_dtos.py` e a pasta `fakes/`**

```bash
git mv tests/unit/application/test_dtos.py tests/unit/application/users/test_dtos.py
git mv tests/unit/application/fakes/in_memory_user_repository.py tests/unit/application/users/fakes/in_memory_user_repository.py
git rm tests/unit/application/fakes/__init__.py
rmdir tests/unit/application/fakes
```

- [ ] **Step 5: Mover testes de integration e e2e**

```bash
git mv tests/integration/test_user_repository.py tests/integration/users/test_repository.py
git mv tests/e2e/test_users_api.py tests/e2e/users/test_api.py
```

- [ ] **Step 6: Atualizar imports dentro dos testes movidos (se houver imports relativos ou referências a `tests.unit.application.fakes`)**

```bash
grep -rln 'tests\.unit\.application\.fakes' tests | xargs --no-run-if-empty perl -pi -e 's/tests\.unit\.application\.fakes/tests.unit.application.users.fakes/g'
grep -rln 'from \.fakes' tests | xargs --no-run-if-empty perl -pi -e 's/from \.fakes/from .users.fakes/g' || true
```

- [ ] **Step 7: Verificar referências quebradas**

```bash
grep -rn 'tests\.unit\.application\.fakes' tests || echo "OK: zero matches"
```

Expected: `OK: zero matches`.

- [ ] **Step 8: Rodar testes — validar coleta correta**

```bash
make test
```

Expected: mesmo N de testes que o baseline. Se pytest reportar menos testes, há conftest/`__init__.py` faltando — investigar.

- [ ] **Step 9: Commit**

```bash
git add -A
git commit -m "refactor(tests): mirror new vertical-sliced structure

Testes de unit/application, integration e e2e agrupados sob users/.
Nomes encurtados: test_create_user_handler.py -> test_create_user.py
(pasta commands/ já dá o contexto)."
```

---

## Task 10: Validação final completa

**Files:** —

- [ ] **Step 1: Smoke import do app inteiro**

```bash
.venv/bin/python -c "from app.main import app; print('OK', len(app.routes))"
```

Expected: `OK <N>` onde N é o número de rotas (>= 5: health, root, /v1/users, /v1/users/{id}, /v1/users/{id}/email).

- [ ] **Step 2: Test suite completa**

```bash
make test
```

Expected: mesmo N do baseline (Task 0). Zero falhas.

- [ ] **Step 3: Validar registro de modelos em `Base.metadata` (sempre funciona)**

```bash
.venv/bin/python -c "
from app.infrastructure.db.base import Base
from app.infrastructure.db.mappings import user
tables = Base.metadata.tables
assert 'users' in tables, f'tabela users não registrada. tables={list(tables)}'
print('OK: users table registered with', len(tables['users'].columns), 'columns')
"
```

Expected: `OK: users table registered with 9 columns`.

- [ ] **Step 4 (opcional, requer DB ativo): Validar Alembic — schema preservado**

Pular se não houver DB configurado em `.env`. Caso contrário:

```bash
make migrate-new msg="post_refactor_check_final"
```

Abrir o arquivo gerado e confirmar `upgrade()` e `downgrade()` **vazios** (só `pass`). Apagar:

```bash
rm $(ls -t app/migrations/versions/*post_refactor_check_final*.py)
```

- [ ] **Step 5: Startup runtime (smoke)**

Em um terminal:

```bash
make run &
APP_PID=$!
sleep 3
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8000/health
kill $APP_PID
wait $APP_PID 2>/dev/null
```

Expected: `200`.

(Alternativa se `make run` precisar de Postgres real: rodar com `BACKEND_DATABASE_URL=sqlite+aiosqlite:///:memory:` exportado antes — mas as migrations não rodariam. Se o ambiente exigir DB, pular este step e usar apenas o test suite + smoke import como validação final.)

- [ ] **Step 6: Lint + type-check**

```bash
make lint
```

Expected: zero erros novos comparados com o baseline (se houver erros pré-existentes, eles continuam, mas nada novo).

- [ ] **Step 7: Confirmar pastas antigas removidas**

```bash
ls app/domain/common 2>/dev/null && echo "ERRO: pasta antiga sobrou" || echo "OK: removida"
ls app/domain/value_objects 2>/dev/null && echo "ERRO: pasta antiga sobrou" || echo "OK: removida"
ls app/application/commands 2>/dev/null && echo "ERRO: pasta antiga sobrou" || echo "OK: removida"
ls app/application/queries 2>/dev/null && echo "ERRO: pasta antiga sobrou" || echo "OK: removida"
ls app/infrastructure/db/models 2>/dev/null && echo "ERRO: pasta antiga sobrou" || echo "OK: removida"
ls app/api/v1/users.py 2>/dev/null && echo "ERRO: arquivo antigo sobrou" || echo "OK: removido"
ls app/api/v1/schemas.py 2>/dev/null && echo "ERRO: arquivo antigo sobrou" || echo "OK: removido"
ls app/api/v1/ai_chat.py 2>/dev/null && echo "ERRO: arquivo antigo sobrou" || echo "OK: removido"
```

Expected: oito linhas `OK: removida` / `OK: removido`.

- [ ] **Step 8: Commit (caso `make migrate-new` tenha deixado algum vestígio inadvertido — normalmente nada)**

```bash
git status
```

Se houver mudanças residuais (não deveria ter), `git add -A && git commit -m "chore: post-validation cleanup"`. Se não, pular.

---

## Task 11: Documentar "Adding a new feature" no README

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Localizar seção apropriada no README**

```bash
grep -n '^##' README.md
```

Encontrar uma seção tipo "## Estrutura" ou "## Convenções" para inserir a nova seção logo depois. Se não houver lugar óbvio, adicionar ao final.

- [ ] **Step 2: Adicionar seção "Adding a new feature" ao README.md**

Conteúdo a adicionar (ajustar localização conforme estrutura existente):

```markdown
## Adicionando uma nova feature

O template segue **vertical slicing por feature**. Para adicionar uma nova feature `<feature>` (ex.: `project`):

### 1. Domain
```
app/domain/<feature>/
  __init__.py
  <feature>.py         # entidade rica (estende BaseEntity)
  repository.py        # interface I<Feature>Repository (Protocol)
```
VOs específicos da feature ficam aqui. VOs reutilizáveis sobem para `domain/shared/value_objects/`.

### 2. Infrastructure
```
app/infrastructure/db/mappings/<feature>.py        # <Feature>Model(Base, TimestampMixin)
app/infrastructure/repositories/<feature>_repository.py
```
Adicionar import em `app/migrations/env.py`:
```python
from app.infrastructure.db.mappings import <feature>  # noqa: F401
```
Gerar migration: `make migrate-new msg="add_<feature>s_table"`.

### 3. Application
```
app/application/<feature>s/
  __init__.py
  dtos.py
  commands/
    __init__.py
    create_<feature>.py
  queries/
    __init__.py
    get_<feature>_by_id.py
```

### 4. API
```
app/api/v1/<feature>s/
  __init__.py             # re-exporta router
  routes.py
  schemas.py
  deps.py                 # get_<feature>_repository + handlers DI
```
Registrar em `app/api/v1/router.py`:
```python
from app.api.v1.<feature>s import router as <feature>s_router
api_router.include_router(<feature>s_router)
```

### 5. Tests
```
tests/unit/domain/<feature>/test_<feature>.py
tests/unit/application/<feature>s/
  fakes/in_memory_<feature>_repository.py
  commands/test_create_<feature>.py
  queries/test_get_<feature>_by_id.py
  test_dtos.py
tests/integration/<feature>s/test_repository.py
tests/e2e/<feature>s/test_api.py
```

### Regras de dependência

- **Cross-feature em `domain/`**: PROIBIDO. Se duas features compartilham conceito, ele sobe para `domain/shared/`.
- **Cross-feature em `application/`**: handler de uma feature pode depender de **interfaces** (Protocols) de outra, nunca de implementações concretas.
- **Direção do fluxo**: API → Application → Domain → Shared. Nunca o oposto.
- **`domain/shared/`**: zona estável; mudanças impactam tudo — exigir review extra.
```

- [ ] **Step 3: Verificar render do markdown**

```bash
head -120 README.md
```

Expected: seção visualmente correta (sem indentação quebrada, sem code-fences mal-fechados).

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs(readme): add 'Adding a new feature' playbook

Replicabilidade: novo dev tem checklist exato do que criar
em cada camada para adicionar uma feature."
```

---

## Task 12: Push da branch e abertura de PR (opcional — manual)

**Files:** —

- [ ] **Step 1: Push**

```bash
git push -u origin refactor/vertical-slicing
```

- [ ] **Step 2: Abrir PR (manual ou via gh)**

Recomendação de título: `refactor: vertical slicing por feature em api/application/domain/tests`

Recomendação de body:
- Linkar a spec: `docs/superpowers/specs/2026-04-24-backend-template-restructure-design.md`
- Marcar como "estrutural-only, zero mudança comportamental"
- Test plan: `make test` verde, `make migrate-new` produz diff vazio, `/health` 200

---

## Resumo de validação contínua

A cada commit acima, a invariante é:

| Validação | Comando | Esperado |
|---|---|---|
| Smoke import | `.venv/bin/python -c "from app.main import app"` | sem erro |
| Tests verdes | `make test` | mesmo N do baseline |
| Schema preservado (sempre) | introspecção de `Base.metadata.tables` (Task 4 step 8) | tabela `users` com 9 colunas |
| Schema preservado (opcional) | `make migrate-new msg=check` | upgrade()/downgrade() vazios — só se DB ativo |

Se em qualquer task uma dessas validações falhar, **parar, investigar, corrigir antes do commit**. O refactor não pode introduzir nem 1 falha de teste.
