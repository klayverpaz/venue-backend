# Plan 01 — Bootstrap venue-backend

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Clone `ai-ready-backend-template` into the existing `venue-backend/` repo, install dependencies, then apply the template's Recipe A (`docs/template-customization.md`) to remove the AI module. Final state: a green test suite, a working `python -c "from app.main import app"` smoke import without `langchain`/`langgraph`, and the `users` CRUD sample left intact (it'll be replaced by `accounts` in Plan 02).

**Architecture:** Mechanical bootstrap. No new business logic in this plan. The template ships with FastAPI + SQLAlchemy 2.0 async + Alembic + Redis + a `users` CRUD sample + an `ai/` module guarded by `BACKEND_AI_PROVIDER`. Recipe A removes the `ai/` directory tree, the lifespan branch that loads it, the four `Settings` fields, the `requirements-ai.txt` install path, and AI references in tests and docs.

**Tech Stack:** Python 3.12, `uv` (for venv creation), FastAPI, Pydantic v2, pydantic-settings, SQLAlchemy 2.0 async, Alembic, asyncpg (Postgres), aiosqlite (tests), Redis, pytest, pytest-asyncio, httpx, ruff, mypy.

---

## File Structure

After this plan, `venue-backend/` will look like the template minus the AI module:

```
venue-backend/
├── .git/                                   # already initialized (Plan 00)
├── .gitignore                              # ← from template
├── .python-version                         # ← from template (3.12)
├── .env                                    # ← created locally (NOT committed)
├── .env.example                            # ← from template, AI block stripped
├── CLAUDE.md                               # ← from template, AI mention stripped, project name updated
├── Dockerfile                              # ← from template
├── Makefile                                # ← from template, install-ai target removed
├── Opportunities.md                        # already present
├── README.md                               # ← from template, project name updated
├── alembic.ini                             # ← from template
├── pyrightconfig.json                      # ← from template
├── pytest.ini                              # ← from template
├── requirements.txt                        # ← from template
├── requirements-dev.txt                    # ← from template
├── requirements-postgres.txt               # ← from template
├── requirements-mssql.txt                  # ← from template (kept; cheap to leave)
├── start_services.sh                       # ← from template
├── app/
│   ├── api/
│   │   ├── deps.py
│   │   ├── error_handler.py
│   │   ├── middleware.py
│   │   └── v1/
│   │       ├── router.py                   # ← AI docstring sentence stripped
│   │       ├── reports/                    # left intact (Plan 03+ may remove via Recipe B)
│   │       └── users/                      # left intact (Plan 02 replaces it)
│   ├── core/
│   │   └── config.py                       # ← ai_provider, ai_model_name, ai_api_key, ai_temperature stripped
│   ├── domain/
│   │   ├── shared/
│   │   └── user/
│   ├── infrastructure/
│   ├── main.py                             # ← lifespan AI branch stripped
│   ├── migrations/
│   └── use_cases/
├── docs/
│   ├── superpowers/
│   │   ├── specs/2026-04-25-venue-backend-design.md   # already present
│   │   └── plans/2026-04-25-plan-01-bootstrap.md      # this file
│   └── template-customization.md           # ← from template, kept as reference
└── tests/
    ├── conftest.py                         # ← BACKEND_AI_PROVIDER line removed
    ├── e2e/conftest.py                     # ← BACKEND_AI_PROVIDER line removed
    └── unit/core/test_config.py            # ← test_settings_ai_provider_default_none deleted
```

**Removed entirely (Recipe A):**

```
app/ai/                                     # AI graph + tools + prompts
app/api/v1/ai_chat/                         # AI chat HTTP endpoint
tests/unit/ai/
tests/integration/ai/
tests/unit/architecture/test_ai_isolation.py
requirements-ai.txt
```

---

### Task 1: Copy template files into the existing `venue-backend/` repo

The repo already exists with `.git/`, `Opportunities.md`, and `docs/superpowers/specs/2026-04-25-venue-backend-design.md`. We need to merge the template's contents in **without** clobbering those three. Using `rsync` with `--ignore-existing` is the cleanest way: it copies every template file that is not already present, preserving what's there.

**Files:**
- Modify: `venue-backend/` (mass file copy)

- [ ] **Step 1: Run the rsync copy**

```bash
rsync -av --exclude='.git' --ignore-existing \
  /Users/klayver/Repositories/agentic-workbench/ai-ready-backend-template/ \
  /Users/klayver/Repositories/agentic-workbench/venue-backend/
```

Expected output: a long list of files copied (`.gitignore`, `app/...`, `tests/...`, `Makefile`, `requirements*.txt`, etc.) — and the existing `docs/superpowers/specs/2026-04-25-venue-backend-design.md` and `Opportunities.md` are NOT touched.

- [ ] **Step 2: Verify the merge**

```bash
cd /Users/klayver/Repositories/agentic-workbench/venue-backend
ls -la
# Expect to see: app/, tests/, docs/, Makefile, requirements*.txt, README.md,
# CLAUDE.md, .env.example, .python-version, .gitignore, alembic.ini, pytest.ini,
# Dockerfile, pyrightconfig.json, start_services.sh, Opportunities.md
test -f docs/superpowers/specs/2026-04-25-venue-backend-design.md && echo "spec preserved"
test -f Opportunities.md && echo "opportunities preserved"
```

Expected: both `echo` lines fire, confirming the existing files were preserved.

- [ ] **Step 3: Verify the template's own existing docs came over too**

```bash
test -f docs/template-customization.md && echo "template-customization preserved"
ls docs/superpowers/specs/
# expect: 2026-04-24-backend-template-design.md  AND  2026-04-25-venue-backend-design.md
```

The template ships with its own design spec (`2026-04-24-backend-template-design.md`); we keep it for reference alongside our own.

- [ ] **Step 4: Stage and commit**

```bash
git add -A
git status      # eyeball: should show new files only, no deletes/modifications
git commit -m "$(cat <<'EOF'
chore: bootstrap from ai-ready-backend-template

Mirror the ai-ready-backend-template into venue-backend (excluding .git
and preserving the existing design spec + Opportunities.md). The AI
module comes in along with everything else; the next tasks strip it out
per Recipe A in docs/template-customization.md.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: Create the Python 3.12 virtualenv and install base + dev + Postgres deps

The Makefile uses `uv venv --seed --python 3.12` for venv creation, then `pip` for installs. We need `uv` available on the host. If it isn't, fall back to `python3.12 -m venv .venv && .venv/bin/pip install --upgrade pip`.

**Files:**
- Create: `venue-backend/.venv/` (gitignored)

- [ ] **Step 1: Confirm Python 3.12 is available**

```bash
cd /Users/klayver/Repositories/agentic-workbench/venue-backend
python3.12 --version
# Expected: Python 3.12.x
```

If missing, install it (e.g., `brew install python@3.12`) before continuing.

- [ ] **Step 2: Create the venv via Make (or fallback)**

Try the Makefile target first:

```bash
make install
```

Expected: `uv venv ...` runs, then `pip install -r requirements.txt -r requirements-dev.txt` runs and completes.

If `uv` is missing on the host (`make: uv: command not found`):

```bash
python3.12 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt -r requirements-dev.txt
```

- [ ] **Step 3: Install the Postgres driver group**

```bash
make install-postgres
# equivalent to: .venv/bin/pip install -r requirements-postgres.txt
```

Expected: installs `asyncpg` (and any psycopg2 binding the requirements file lists).

- [ ] **Step 4: Verify the venv is usable**

```bash
.venv/bin/python -c "import fastapi, sqlalchemy, alembic, pytest, asyncpg, redis; print('deps ok')"
# Expected: "deps ok"
```

- [ ] **Step 5: Confirm `.venv/` is gitignored**

```bash
grep -n '.venv' .gitignore || echo "MISSING — must add"
```

Expected: at least one line matching `.venv` already in the template's `.gitignore`. If "MISSING" prints, append `.venv/` to `.gitignore` and commit. (As of the template's current `.gitignore`, this should already be present.)

- [ ] **Step 6: No commit needed**

The venv is gitignored. Nothing to commit yet.

---

### Task 3: Set up the local `.env` from `.env.example`

Tests use SQLite in-memory and don't need `.env`, but `make run` (and any local manual run) does. Get the file in place now so the engineer can run the app once the template is clean.

**Files:**
- Create: `venue-backend/.env` (gitignored)

- [ ] **Step 1: Copy `.env.example` to `.env`**

```bash
cd /Users/klayver/Repositories/agentic-workbench/venue-backend
cp .env.example .env
```

- [ ] **Step 2: Confirm `.env` is gitignored**

```bash
grep -n '^.env$\|^/.env$\|^.env\b' .gitignore || echo "MISSING"
```

Expected: a line that matches `.env`. The template's `.gitignore` should already have it.

- [ ] **Step 3: Edit `.env` for local development**

Open `.env` and adjust:

- `BACKEND_DATABASE_URL` to a real local Postgres URL the engineer has access to (e.g., `postgresql+asyncpg://venue:venue@localhost:5432/venue_dev`). If the engineer doesn't have a local Postgres yet, leave the placeholder — Plan 1 doesn't require running migrations.
- Leave Redis values as defaults (the engineer can `make redis-dev` later if needed).
- Leave `BACKEND_AI_PROVIDER=none` for now; Recipe A will delete the AI block from `.env.example` in Task 7, and we'll mirror that into `.env` then.

- [ ] **Step 4: No commit (file is gitignored)**

---

### Task 4: Run the baseline test suite to prove the un-modified template is green

Before stripping anything, confirm the copied template passes its own tests on this machine. Establishing a green baseline is what makes the deletions in subsequent tasks safe.

**Files:**
- None modified.

- [ ] **Step 1: Run pytest**

```bash
cd /Users/klayver/Repositories/agentic-workbench/venue-backend
.venv/bin/pytest -q
```

Expected: all tests pass. If any fail, **stop and diagnose** — the deletions in later tasks must be applied to a known-green state. Common pitfalls:

- Missing `langchain` / `langgraph` — install via `pip install -r requirements-ai.txt` to make AI tests pass *for now* (we delete them in Task 5, so this is throwaway). Or skip the AI tests with `pytest -q --ignore=tests/unit/ai --ignore=tests/integration/ai`. The latter is the right move — AI tests are about to be deleted anyway.
- Missing `aiosqlite` — should be in `requirements-dev.txt`; if not, `pip install aiosqlite`.

If you needed `--ignore` flags, **note that** in the commit message of Task 11's verification — the test suite should be unconditionally green by then.

- [ ] **Step 2: No commit (no code change)**

---

### Task 5: Recipe A step 1 — Delete the AI source directories

Per `docs/template-customization.md` Recipe A step 1.

**Files:**
- Delete: `app/ai/`
- Delete: `app/api/v1/ai_chat/`
- Delete: `tests/unit/ai/`
- Delete: `tests/integration/ai/`
- Delete: `tests/unit/architecture/test_ai_isolation.py`

- [ ] **Step 1: Remove the directories and the architecture test**

```bash
cd /Users/klayver/Repositories/agentic-workbench/venue-backend
rm -rf app/ai app/api/v1/ai_chat tests/unit/ai tests/integration/ai
rm -f tests/unit/architecture/test_ai_isolation.py
```

- [ ] **Step 2: Verify deletions**

```bash
test ! -e app/ai && echo "app/ai gone"
test ! -e app/api/v1/ai_chat && echo "app/api/v1/ai_chat gone"
test ! -e tests/unit/ai && echo "tests/unit/ai gone"
test ! -e tests/integration/ai && echo "tests/integration/ai gone"
test ! -e tests/unit/architecture/test_ai_isolation.py && echo "test_ai_isolation gone"
```

Expected: five "gone" lines.

- [ ] **Step 3: Run tests — they will fail**

```bash
.venv/bin/pytest -q
```

Expected: failures originating from `app/main.py` (the lifespan still tries to import `app.ai.graph`) and possibly from `app/core/config.py` if any test references AI fields. **This is the expected red state** — the next tasks fix it.

- [ ] **Step 4: Commit the deletions**

Even though tests are red, commit so each removal step is a discrete, revertible change. The next task makes them green again.

```bash
git add -A
git commit -m "$(cat <<'EOF'
chore: recipe A step 1 — delete AI source directories

Removes app/ai, app/api/v1/ai_chat, the AI test directories, and the
tests/unit/architecture/test_ai_isolation.py architecture test (its
allowlist references paths we just removed and the rule it enforces is
now vacuous). Tests are red until the next commit (main.py still imports
from app.ai inside its lifespan).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 6: Recipe A step 2 — Strip the AI block from `app/main.py` lifespan

The lifespan currently has an `if settings.ai_provider != "none":` block that imports from `app.ai.graph` and `app.api.v1.ai_chat`. Both modules just got deleted. Remove the `if/else` block, and remove the `settings = get_settings()` line that fed it (it becomes unused).

**Files:**
- Modify: `venue-backend/app/main.py`

- [ ] **Step 1: Edit `app/main.py`**

Replace the existing lifespan body so it reads as below. The diff:
- removes the `settings = get_settings()` call (line 25 in the template).
- removes the entire `if settings.ai_provider != "none": ... else: logger.info(...)` block (lines 32–47).

Final state of the lifespan:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    init_engine()
    pool = build_redis_pool()
    redis_client = redis_lib.Redis(connection_pool=pool)
    app.state.redis_client = redis_client
    app.state.redis_pool = pool

    logger.info("Startup completo.")
    yield

    await redis_client.aclose()
    await pool.aclose()
    await dispose_engine()
    logger.info("Recursos liberados.")
```

- [ ] **Step 2: Verify the import-time smoke test passes**

```bash
BACKEND_DATABASE_URL="sqlite+aiosqlite:///:memory:" \
  .venv/bin/python -c "from app.main import app; print('ok')"
```

Expected: `ok`. No `ModuleNotFoundError` for `langchain`, `langgraph`, or `app.ai.*`.

- [ ] **Step 3: Run the test suite**

```bash
.venv/bin/pytest -q
```

Expected: most tests pass. Two known failures may remain:

1. `tests/unit/core/test_config.py::test_settings_ai_provider_default_none` — still references `s.ai_provider`. We delete this test in Task 9.
2. Any test that asserts `BACKEND_AI_PROVIDER` env var presence — also fixed in Task 9.

If the count of failing tests is more than those two cases, stop and diagnose.

- [ ] **Step 4: Commit**

```bash
git add app/main.py
git commit -m "$(cat <<'EOF'
chore: recipe A step 2 — strip AI block from main.py lifespan

Removes the if settings.ai_provider != "none" branch (and its else)
from the lifespan, plus the now-unused settings = get_settings() that
fed it. The smoke import "from app.main import app" no longer requires
langchain or langgraph.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 7: Recipe A step 3 — Remove AI fields from `app/core/config.py` and `.env.example`

The four AI fields in `Settings` are no longer referenced anywhere. Delete them. Mirror the cleanup into `.env.example` so the file stops advertising obsolete env vars.

**Files:**
- Modify: `venue-backend/app/core/config.py`
- Modify: `venue-backend/.env.example`

- [ ] **Step 1: Edit `app/core/config.py`**

Delete these four lines from the `Settings` class body (currently lines 26–29):

```python
    ai_provider: Literal["anthropic", "openai", "none"] = "none"
    ai_model_name: str = ""
    ai_api_key: SecretStr = SecretStr("")
    ai_temperature: float = 0.3
```

Also delete the `Literal` import if `Literal` is no longer used after the removal. Check: the field `environment: Literal["development", "production", "test"]` still uses it, so **keep** the import.

- [ ] **Step 2: Edit `.env.example`**

Delete the AI block (lines 19–28 of the template's `.env.example`):

```
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

The LangSmith block goes too — it was only relevant to the AI module.

- [ ] **Step 3: Mirror the cleanup into your local `.env`**

Edit `.env` (gitignored) to drop the same lines. Otherwise `BaseSettings(extra="ignore")` will tolerate them but they pollute the file.

- [ ] **Step 4: Smoke import**

```bash
BACKEND_DATABASE_URL="sqlite+aiosqlite:///:memory:" \
  .venv/bin/python -c "from app.main import app; from app.core.config import get_settings; get_settings.cache_clear(); s = get_settings(); print(s.environment, s.database_url)"
```

Expected: prints `test sqlite+aiosqlite:///:memory:` (or the values from your `.env`). No errors about extra env vars.

- [ ] **Step 5: Run tests**

```bash
.venv/bin/pytest -q
```

Expected: only `test_settings_ai_provider_default_none` should fail now (asserts on a removed field). All other tests pass.

- [ ] **Step 6: Commit**

```bash
git add app/core/config.py .env.example
git commit -m "$(cat <<'EOF'
chore: recipe A step 3 — strip AI settings + LangSmith env block

Removes ai_provider, ai_model_name, ai_api_key, ai_temperature from
Settings (no consumer remaining). Drops the AI and LangSmith sections
from .env.example so the example file no longer documents obsolete
configuration. Local .env mirrored manually (gitignored, not in commit).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 8: Recipe A step 4 — Delete `requirements-ai.txt` + `install-ai` Make target + CLAUDE.md mention

The `requirements-ai.txt` install path is wired into the Makefile and mentioned in `CLAUDE.md`. Remove all three references in the same commit.

**Files:**
- Delete: `venue-backend/requirements-ai.txt`
- Modify: `venue-backend/Makefile`
- Modify: `venue-backend/CLAUDE.md`

- [ ] **Step 1: Delete the requirements file**

```bash
cd /Users/klayver/Repositories/agentic-workbench/venue-backend
rm -f requirements-ai.txt
test ! -e requirements-ai.txt && echo "requirements-ai.txt gone"
```

- [ ] **Step 2: Edit `Makefile`**

Two edits:

a) Drop `install-ai` from the `.PHONY` line at the top:

Before:
```
.PHONY: install install-postgres install-mssql install-ai run test lint \
        migrate-new migrate-up migrate-down migrate-history redis-dev clean
```

After:
```
.PHONY: install install-postgres install-mssql run test lint \
        migrate-new migrate-up migrate-down migrate-history redis-dev clean
```

b) Remove the `install-ai` target body:

Before (lines 19–20 in the template's Makefile):
```
install-ai:
	$(PIP) install -r requirements-ai.txt
```

Delete those two lines.

- [ ] **Step 3: Edit `CLAUDE.md`**

The template's `CLAUDE.md` line 12 mentions `make install-ai`:

Before:
```
Dependências em `requirements*.txt`. Instalação: `make install` (base + dev). Extras: `make install-postgres`, `make install-mssql`, `make install-ai`.
```

After:
```
Dependências em `requirements*.txt`. Instalação: `make install` (base + dev). Extras: `make install-postgres`, `make install-mssql`.
```

- [ ] **Step 4: Verify the Makefile parses**

```bash
make -n install      # dry-run; just prints commands without executing
```

Expected: prints `uv venv --seed --python 3.12` and the `pip install -r requirements.txt -r requirements-dev.txt` lines. No error about an undefined target.

- [ ] **Step 5: Run tests**

```bash
.venv/bin/pytest -q
```

Expected: same state as Task 7 — only `test_settings_ai_provider_default_none` fails. Task 9 fixes that.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "$(cat <<'EOF'
chore: recipe A step 4 — drop requirements-ai.txt + install-ai target

Deletes requirements-ai.txt, the install-ai Makefile target, and the
"make install-ai" reference in CLAUDE.md. The AI dependency surface no
longer exists in the project.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 9: Recipe A step 5 — Clean `BACKEND_AI_PROVIDER=none` from test conftests + delete dead test

Two test conftests hard-code `BACKEND_AI_PROVIDER=none`. Now that the field is gone, those lines do nothing harmful but are dead. The `test_settings_ai_provider_default_none` test references the removed field and currently fails.

**Files:**
- Modify: `venue-backend/tests/conftest.py`
- Modify: `venue-backend/tests/e2e/conftest.py`
- Modify: `venue-backend/tests/unit/core/test_config.py` (delete one test function)

- [ ] **Step 1: Edit `tests/conftest.py`**

Delete the line:
```python
    monkeypatch.setenv("BACKEND_AI_PROVIDER", "none")
```

The fixture body now reads:
```python
@pytest.fixture(autouse=True)
def _env_defaults(monkeypatch):
    """Defaults previsíveis para os testes unitários."""
    monkeypatch.setenv("BACKEND_ENVIRONMENT", "test")
    monkeypatch.setenv("BACKEND_DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    yield
```

- [ ] **Step 2: Edit `tests/e2e/conftest.py`**

Delete the line:
```python
os.environ.setdefault("BACKEND_AI_PROVIDER", "none")
```

The header now reads:
```python
os.environ.setdefault("BACKEND_DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("BACKEND_ENVIRONMENT", "test")
```

- [ ] **Step 3: Edit `tests/unit/core/test_config.py`**

Delete the `test_settings_ai_provider_default_none` function (lines 18–22 in the template):

```python
def test_settings_ai_provider_default_none(monkeypatch):
    monkeypatch.setenv("BACKEND_DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    get_settings.cache_clear()
    s = get_settings()
    assert s.ai_provider == "none"
```

The remaining tests in that file (`test_settings_carrega_env_com_prefix_backend` and `test_settings_exige_database_url`) stay unchanged.

- [ ] **Step 4: Run the test suite — should now be green**

```bash
.venv/bin/pytest -q
```

Expected: ALL tests pass. No skips, no failures, no errors.

If anything still references `ai_provider` and fails, grep for it:
```bash
grep -rn "ai_provider" tests/
```
Should return zero matches inside `tests/`.

- [ ] **Step 5: Commit**

```bash
git add tests/conftest.py tests/e2e/conftest.py tests/unit/core/test_config.py
git commit -m "$(cat <<'EOF'
chore: recipe A step 5 — drop AI traces from test conftests

Removes the BACKEND_AI_PROVIDER env-var stubs from tests/conftest.py and
tests/e2e/conftest.py (no consumer remaining) and deletes
test_settings_ai_provider_default_none, which asserted on a Settings
field that no longer exists. Test suite is now green.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 10: Recipe A step 6 — Update the docstring at the top of `app/api/v1/router.py`

The router's docstring documents how `ai_chat` is conditionally registered in `main.py`. That sentence is misleading now — there's no `ai_chat` and no conditional registration.

**Files:**
- Modify: `venue-backend/app/api/v1/router.py`

- [ ] **Step 1: Edit the docstring**

Replace the existing top docstring (lines 1–10) with:

```python
"""API router agregador: include cada feature router aqui.

Uso em main.py:
    from app.api.v1.router import api_router
    app.include_router(api_router)
"""
```

The "Features que dependem de configuração runtime ..." paragraph is gone.

- [ ] **Step 2: Verify the imports below the docstring are unchanged**

The body of the file should still contain:
```python
from fastapi import APIRouter

from app.api.v1.users import router as users_router
from app.api.v1.reports import router as reports_router

api_router = APIRouter()
api_router.include_router(users_router)
api_router.include_router(reports_router)
```

(`users` and `reports` stay; both will be touched by later plans, not this one.)

- [ ] **Step 3: Run tests**

```bash
.venv/bin/pytest -q
```

Expected: green.

- [ ] **Step 4: Commit**

```bash
git add app/api/v1/router.py
git commit -m "$(cat <<'EOF'
chore: recipe A step 6 — strip AI sentence from router docstring

The api/v1/router.py docstring referenced "ai_chat depende de
ai_provider" and the conditional-include-in-main pattern. Neither
exists anymore — drop the sentence so the docs don't lie.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 11: Recipe A step 7 — Final verification (grep, smoke import, full test run)

Recipe A is complete. Run the three checks the recipe prescribes and confirm a clean state.

**Files:**
- None modified.

- [ ] **Step 1: Grep for stragglers**

```bash
cd /Users/klayver/Repositories/agentic-workbench/venue-backend
grep -rn "ai_provider\|app\.ai\b\|ai_chat" app/ tests/
```

Expected: zero matches. If any match shows up:
- It's in a file you've already modified — re-edit and remove.
- It's in a file you missed — that's the bug; fix it.
- It's in a string literal that's actually about a different concept — false positive, ignore.

- [ ] **Step 2: Smoke import without `langchain`/`langgraph` available**

The point: even on a venv where AI deps aren't installed, the app must import.

```bash
BACKEND_DATABASE_URL="sqlite+aiosqlite:///:memory:" \
  .venv/bin/python -c "from app.main import app; print('ok')"
```

Expected: `ok`.

To prove it does NOT need `langchain`:

```bash
.venv/bin/python -c "import langchain" 2>&1 | head -1
```

Expected: either `ModuleNotFoundError: No module named 'langchain'` (if `requirements-ai.txt` was never installed in this venv — the right state) OR a successful import (if AI deps got pulled in for Task 4's baseline run). If the second case, that's not a Recipe A bug, just an artifact of how Task 4 ran. The smoke test in Step 2 already proved AI deps aren't *required*.

- [ ] **Step 3: Full test run**

```bash
.venv/bin/pytest -q
```

Expected: all green, no skips, no errors.

- [ ] **Step 4: Run linters**

```bash
make lint
# = .venv/bin/python -m ruff check app tests
#   .venv/bin/python -m mypy app
```

Expected: ruff clean. mypy may surface some pre-existing issues in template code that are not Recipe-A-related — note them but do not fix in this plan.

- [ ] **Step 5: No commit (verification only)**

---

### Task 12: Update `CLAUDE.md` and `README.md` to reflect the new project identity

The cloned `CLAUDE.md` and `README.md` still call the project "Backend Template" / "backend-template". Replace those with `venue-backend` strings so an LLM reading the repo from cold doesn't think it's a fresh template.

**Files:**
- Modify: `venue-backend/CLAUDE.md`
- Modify: `venue-backend/README.md`
- Modify: `venue-backend/app/core/config.py` (one line: `app_name`)
- Modify: `venue-backend/app/main.py` (one line: `FastAPI(title=...)`)

- [ ] **Step 1: Edit `CLAUDE.md`**

a) Replace the H1 if there is one (currently `# Backend Template - Instruções`) with:
```
# venue-backend — Instruções
```

b) Add a short context paragraph at the very top, ABOVE the existing `## Python` section, summarizing what this project is:

```markdown
Backend de uma plataforma de aluguel de espaços por slots horários (ex.: campos de futebol, quadras, salões). Construído sobre o `ai-ready-backend-template` com o módulo de IA já removido. O design completo está em [docs/superpowers/specs/2026-04-25-venue-backend-design.md](docs/superpowers/specs/2026-04-25-venue-backend-design.md). Os planos de implementação ficam em [docs/superpowers/plans/](docs/superpowers/plans/).
```

c) The "Adaptando o template" section (lines 20–28 of the cloned file) is no longer relevant — this *is* the adapted project. Delete that section.

- [ ] **Step 2: Edit `README.md`**

a) Replace the H1 (currently `# Backend Template`) with:
```
# venue-backend
```

b) Replace the opening paragraph that describes the template with a project-specific summary:

```markdown
Backend Python para uma plataforma de aluguel de espaços por slots horários. Três papéis (Admin, Owner, Customer), com cada Owner gerenciando um ou mais `Resource`s rentáveis e Customers solicitando bookings que o Owner aprova ou rejeita.

Design: [docs/superpowers/specs/2026-04-25-venue-backend-design.md](docs/superpowers/specs/2026-04-25-venue-backend-design.md).
Planos: [docs/superpowers/plans/](docs/superpowers/plans/).
Construído sobre o template `ai-ready-backend-template` (módulo de IA removido).
```

c) Delete the **"Módulo de IA"** section entirely — it documents a feature that no longer exists.

- [ ] **Step 3: Edit `app/core/config.py` `app_name`**

```python
# Before:
    app_name: str = "backend-template"
# After:
    app_name: str = "venue-backend"
```

- [ ] **Step 4: Edit `app/main.py` FastAPI title**

```python
# Before:
app = FastAPI(title="Backend Template", version="0.1.0", lifespan=lifespan)
# After:
app = FastAPI(title="venue-backend", version="0.1.0", lifespan=lifespan)
```

- [ ] **Step 5: Run tests**

```bash
.venv/bin/pytest -q
```

Expected: green.

- [ ] **Step 6: Commit**

```bash
git add CLAUDE.md README.md app/core/config.py app/main.py
git commit -m "$(cat <<'EOF'
chore: rename project identity to venue-backend

Updates CLAUDE.md and README.md to describe the venue-backend project
(rental marketplace) instead of the generic backend-template, drops the
no-longer-relevant "Módulo de IA" README section and the
"Adaptando o template" CLAUDE.md section, and renames Settings.app_name
+ FastAPI(title=...) accordingly.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 13: Push to GitHub and confirm green CI-equivalent

Final step. Push the branch and confirm everything is on the remote.

**Files:**
- None modified.

- [ ] **Step 1: Push to origin**

```bash
cd /Users/klayver/Repositories/agentic-workbench/venue-backend
git push origin main
```

Expected: pushes 11 new commits (Tasks 1, 5–10, 12 above; Tasks 2, 3, 4, 11 don't commit).

- [ ] **Step 2: One last full test run on the pushed state**

```bash
.venv/bin/pytest -q
make lint
```

Expected: pytest green; ruff green; mypy may have unrelated issues, document them in the next-plan-input section.

- [ ] **Step 3: Verify the remote**

```bash
git log --oneline origin/main | head -15
```

Expected: see 12 commits — the original docs commit plus the 11 from this plan.

- [ ] **Step 4: No further commit. Plan 1 done.**

---

## Self-review

**Spec coverage.** This plan covers Section 8 step 1 (template copy) and step 2 (Recipe A) of the design spec. Section 8 step 3 (replace `users` with `accounts`) is intentionally deferred to Plan 02 because the template has no auth/JWT — `accounts` is a from-scratch build, not a port. Section 8 step 4 (build catalog/subscriptions/resources/notifications/bookings) is Plans 03–07. Section 8 step 5 (seed data) is Plan 07.

**Placeholder scan.** No "TBD", "TODO", or "implement later" in the steps. Every command and every code edit is concrete.

**Type consistency.** No new types introduced; deletions only.

**Risks the engineer should watch for during execution.**

1. The host might not have Python 3.12. Task 2 asks first; install before continuing if missing.
2. The host might not have `uv`. Task 2 has a fallback path.
3. Task 4's baseline pytest may fail due to missing AI deps — the documented `--ignore` workaround is OK because those tests are about to be deleted in Task 5 anyway.
4. Task 3's `.env` setup names a Postgres URL the engineer might not have running yet. That's fine for Plan 1 (tests use SQLite in-memory). Plan 02 will require a real Postgres for migrations.
5. mypy in Task 11 / 13 may surface pre-existing template warnings. Don't fix them in this plan.

---

## Execution handoff

Plan complete. Two execution options:

1. **Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.
2. **Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

Reply with **"subagent"** or **"inline"** to proceed.
