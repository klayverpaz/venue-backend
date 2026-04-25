# Template Customization Guide (for LLMs)

> **Audience:** This document is written for an LLM-based coding assistant (e.g., Claude Code) helping a developer adapt this template to their project. Read this **before** making any structural changes.

## Module Taxonomy

The template is organized so each module is either **core** (needed for the layered architecture to work) or **optional** (can be deleted cleanly).

### Core modules — DO NOT remove

| Path | Role |
|------|------|
| `app/core/` | Settings, logging, contextvars |
| `app/api/error_handler.py`, `app/api/middleware.py`, `app/api/deps.py` | HTTP layer infrastructure |
| `app/api/v1/router.py` | Aggregator router (always-on features go here) |
| `app/domain/shared/` | `Result`, `Entity`, `ValueObject` base classes |
| `app/infrastructure/db/`, `app/infrastructure/cache/`, `app/infrastructure/repositories/base_repository.py` | DB session, Redis, base repository |
| `app/main.py` | App entrypoint and lifespan |

### Optional modules — removable units

Each row below is a self-contained module. Removing one must not affect the others.

| Module | What it is | Files | When to remove |
|--------|-----------|-------|----------------|
| **AI** | LangGraph chat agent, tools, prompts | `app/ai/`, `app/api/v1/ai_chat/` | Project doesn't need LLM features |
| **Reports** | Analytics queries (Q anêmico) | `app/use_cases/reports/`, `app/api/v1/reports/` | Project doesn't need aggregations/dashboards |
| **Users sample** | Example feature with rich domain | `app/domain/user/`, `app/use_cases/users/`, `app/api/v1/users/`, `app/infrastructure/repositories/user_repository.py`, `app/infrastructure/db/mappings/user.py` | Replace with real first feature (use this as a template, not as production code) |

## Recipes

### Recipe A — Remove the AI module

The AI module is already gated by `BACKEND_AI_PROVIDER=none`, so the **runtime behavior** is opt-in. Full removal (deleting code + dependencies) takes these steps:

1. Delete the AI source directories AND the now-vacuous architecture test:
   ```bash
   rm -rf app/ai app/api/v1/ai_chat tests/unit/ai tests/integration/ai 2>/dev/null
   rm -f tests/unit/architecture/test_ai_isolation.py
   ```
   (The architecture test only enforces "no non-allowlisted file imports `app.ai.*`" — once `app/ai/` is gone, the rule is vacuous and the test's allowlist references dead paths.)
2. Remove the conditional AI block from `app/main.py` lifespan (the `if settings.ai_provider != "none":` block — usually ~10 lines, plus its `else:` clause if present). Also remove the `settings = get_settings()` line immediately above that block — it becomes unused once the AI conditional is gone.
3. Remove AI settings from `app/core/config.py`:
   - Delete: `ai_provider`, `ai_model_name`, `ai_api_key`, `ai_temperature` fields.
4. Remove AI dependency file: `rm requirements-ai.txt` and remove its install step from `Makefile` (`install-ai` target) if present. Also remove the `make install-ai` mention from the `## Python` section of `CLAUDE.md` so the docs don't lie.
5. Remove AI traces from tests:
   - Remove the `BACKEND_AI_PROVIDER=none` line from `tests/conftest.py` and `tests/e2e/conftest.py`.
   - Delete the `test_settings_ai_provider_default_none` test from `tests/unit/core/test_config.py` (it asserts on `s.ai_provider` which no longer exists).
6. Update the docstring at the top of `app/api/v1/router.py` to drop the sentence referencing `ai_chat depende de ai_provider` — that routing pattern no longer exists.
7. Run tests: `.venv/bin/pytest -q`. All non-AI tests must still pass.
8. Search for stragglers: `grep -rn "ai_provider\|app.ai\|ai_chat" app/ tests/` should return only matches inside files you've already modified or zero matches.

**Verification:** After removal, this must succeed without importing `langchain` or `langgraph` (the env var is required because `Settings` validates `database_url` at import time):
```bash
BACKEND_DATABASE_URL="sqlite+aiosqlite:///:memory:" python -c "from app.main import app; print('ok')"
```

### Recipe B — Remove the Reports module

1. Delete: `rm -rf app/use_cases/reports app/api/v1/reports tests/integration/reports tests/e2e/reports`
2. Remove the include line from `app/api/v1/router.py`:
   ```python
   from app.api.v1.reports import router as reports_router  # delete this
   api_router.include_router(reports_router)                # delete this
   ```
3. Run tests: `.venv/bin/pytest -q`.

### Recipe C — Replace the Users sample with the real first feature

Do NOT delete `users/` until your replacement is in place — it serves as the reference for the `Adding a new feature` playbook in `README.md`.

Workflow:
1. Read `README.md → "Adicionando uma nova feature"`.
2. Implement the new feature in parallel (e.g., `Project`).
3. Once tests pass for the new feature, delete the users sample:
   ```bash
   rm -rf app/domain/user app/use_cases/users app/api/v1/users \
          app/infrastructure/repositories/user_repository.py \
          app/infrastructure/db/mappings/user.py \
          tests/unit/domain/user tests/unit/use_cases/users tests/integration/users tests/e2e/users
   ```
4. Remove `from app.api.v1.users import router as users_router` and its `include_router` call from `app/api/v1/router.py`.
5. Remove `from app.infrastructure.db.mappings import user` from `app/migrations/env.py` and `tests/e2e/conftest.py`.
6. Remove the AI tool that depends on users: `rm app/ai/tools/get_user_by_email.py` and remove it from `app/ai/tools/__init__.py::TOOLS` if present.
7. Generate fresh migration: `make migrate-new msg="drop_users_keep_new_feature"`.
8. Run tests: `.venv/bin/pytest -q`.

### Recipe D — Add a new analytics report

Reports do **not** have a `domain/` folder. Pattern:

1. **Use case (Q anêmico):** create `app/use_cases/reports/queries/<report_name>.py`. The handler takes `AsyncSession` directly (not a repository) and uses `sqlalchemy.text(...)` or SQLAlchemy core. Returns a frozen-dataclass DTO defined in `app/use_cases/reports/dtos.py`.
2. **API:** add the endpoint in `app/api/v1/reports/routes.py`, wire DI in `app/api/v1/reports/deps.py`, add Pydantic schema in `app/api/v1/reports/schemas.py`.
3. **Test:** unit test against an in-memory SQLite for the handler, e2e test for the endpoint.

See `app/use_cases/reports/queries/active_users_by_month.py` as the canonical example.

### Recipe E — Add a new domain feature (the standard CRUD path)

This is the existing playbook — see `README.md → "Adicionando uma nova feature"`. Follow it for any feature with business invariants (rich domain). Use Recipe D instead for read-only/analytics features.

## Rules an LLM MUST NOT violate

These are derived from `CLAUDE.md` — re-stated here so they're impossible to miss:

1. `domain/` is pure Python — must never import from `infrastructure/` or `use_cases/`.
2. `use_cases/` must never import from `infrastructure/` (depend on interfaces in `domain/<feature>/repository.py` instead).
3. `domain/<feature_a>/` must never import from `domain/<feature_b>/`. Shared concepts go to `domain/shared/`.
4. There is no `services/` folder — the handler IS the service layer. A handler must never call another handler; if you need cross-feature orchestration, write a new handler that injects multiple repositories.
5. Business logic does not live in `routes.py`. Routes only validate HTTP and call handlers.
6. Analytics features (read-only aggregations) do **not** create a `domain/<feature>/` folder. They live only in `use_cases/<feature>/queries/` and `api/v1/<feature>/`. SQL-direct → DTO is the right pattern; reidratar aggregates para gerar relatório é desperdício.

## Order of operations when adapting the template

The recommended order when starting a new project from this template:

1. **Read this file end-to-end.** Understand the taxonomy.
2. **Decide which optional modules you want.** Apply the relevant remove recipes.
3. **Replace the users sample** with your first real feature (Recipe C).
4. **Add subsequent features** using Recipe E (rich domain) or Recipe D (analytics).
5. **Run tests after every recipe step.** If `pytest` fails after a removal, the recipe missed something — open an issue.
