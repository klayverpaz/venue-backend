# Template Extensions: Analytics + AI Customization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend `backend-template` with (1) an analytics feature demonstrating the "Q anêmico" CQRS pattern, (2) clear AI module boundaries so it's a clean removable unit, and (3) LLM-facing customization documentation so a developer cloning this template can ask Claude Code to add/remove modules without breaking the architecture.

**Architecture:** Three independent additions on top of the existing `api → use_cases → domain ← infrastructure` layout:
- `reports/` feature lives only in `api/` and `use_cases/` (no `domain/` folder), with queries that bypass aggregates and read SQL directly into DTOs.
- `app/ai/` stays as-is structurally but gets a README and is verified as a leaf module (no other module imports into it that aren't conditional).
- `docs/template-customization.md` becomes the entrypoint for LLM-driven customization, with explicit removal/adaptation recipes referenced from `CLAUDE.md`.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2 async, pytest, LangGraph (AI module, optional). All dependencies already in `requirements*.txt`.

---

## Status (executed 2026-04-25)

All phases complete. Final test count: 108 passed (101 baseline + 3 reports integration + 2 reports e2e + 1 architecture + 1 already-passing baseline adjustment, etc.). Recipe A smoke-tested on a throwaway branch; gaps surfaced and patched into `docs/template-customization.md` (Recipe A now produces 106 passed + zero stragglers when followed verbatim).

Commit history (relevant subset, oldest → newest):
1. `89e4364` — `docs: add template customization guide for LLM assistants`
2. `600e83a` — `docs(claude): point to template-customization.md for clone-time edits`
3. `e1d6ba9` — `docs: tighten AI-removal recipe — also strip CLAUDE.md mention`
4. `08655ab` — `feat(reports): add active-users-by-month query (Q anêmico pattern)`
5. `34de424` — `test(reports): tighten canonical-example tests + clarify SQLite-only SQL`
6. `4d854f8` — `feat(api): expose /v1/reports/active-users-by-month`
7. `01d38ae` — `docs(readme): document the reports feature and analytics path`
8. `e1ba3d9` — `docs(ai): document module layout + enforce leaf-import invariant`
9. `1302216` — `docs: tighten Recipe A based on smoke-test findings`

---

## Pre-flight

- Confirm clean working tree and tests pass before starting.
- Run `.venv/bin/pytest -q` to verify baseline (101 passed at start).

---

## Phase 1 — LLM-Facing Customization Documentation

A future developer clones this template and uses Claude Code (or any LLM) as their pair-programmer. The LLM needs a single doc it can read upfront to know which modules are core, which are optional, and how to add/remove pieces without breaking the architecture.

### Task 1: Create `docs/template-customization.md`

Create the file with the full customization guide: module taxonomy (core vs optional) + 5 recipes (A: remove AI, B: remove reports, C: replace users sample, D: add analytics report, E: add CRUD feature) + LLM-must-not-violate rules + order of operations.

Commit: `docs: add template customization guide for LLM assistants`.

### Task 2: Update `CLAUDE.md` to reference the customization guide

Insert a new `## Adaptando o template (clonou agora? leia isto)` section above `## Arquitetura`, pointing the assistant to `docs/template-customization.md`.

Commit: `docs(claude): point to template-customization.md for clone-time edits`.

---

## Phase 2 — Analytics: the `reports/` feature

Prove the "Q anêmico" pattern with a working, tested example so future analytics features have a canonical reference.

The example feature: **active users by month** — a query that returns `[(year, month, active_count)]` aggregated from the `users` table. It demonstrates:
- No `domain/reports/` folder.
- Handler takes `AsyncSession` directly, not a repository.
- Uses `sqlalchemy.text(...)` for portability between SQLite (tests) and the production DB.
- Returns a frozen-dataclass DTO; route maps it to a Pydantic response.

### Task 3: Create the `reports/` use-case package + DTO

- Create `app/use_cases/reports/__init__.py` (empty).
- Create `app/use_cases/reports/queries/__init__.py` (empty).
- Create `app/use_cases/reports/dtos.py` with `ActiveUsersByMonthRow(year, month, active_count)` and `ActiveUsersByMonthDto(items: list[Row])` as frozen dataclasses with `slots=True`.

### Task 4: Write the failing test for the query handler

The handler hits a real DB (uses `sqlalchemy.text(...)`), so the test belongs in `tests/integration/`, not `tests/unit/`. The existing `tests/integration/conftest.py` already provides a `db_session` fixture wired to in-memory SQLite — reuse it.

- Create `tests/integration/reports/__init__.py` (empty).
- Create `tests/integration/reports/test_active_users_by_month.py` with 3 tests:
  - `test_groups_active_users_by_year_and_month` — seeds 3 active users across 2 months, asserts grouping AND ordering (`assert rows == sorted(rows)`).
  - `test_excludes_inactive_users` — seeds active + inactive in same month, asserts active row exists AND `(year, month, 2)` NOT in rows.
  - `test_returns_empty_dto_when_no_users` — asserts `result.value.items == []`.
  - `test_distinguishes_same_month_across_years` — seeds Jan 2025 + Jan 2026, asserts both appear as separate rows (covers GROUP BY year regression).

The seed helper uses `id=str(uuid4())` because `UserModel.id` is `CHAR(36)` (SQLite does not auto-coerce raw `UUID`).

Run `.venv/bin/pytest tests/integration/reports/ -v` — must FAIL with `ModuleNotFoundError`.

### Task 5: Implement the query handler

- Create `app/use_cases/reports/queries/active_users_by_month.py`.
- Define `ActiveUsersByMonthQuery` (frozen dataclass, no fields) and `ActiveUsersByMonthHandler(session)`.
- `handle(self, query: ActiveUsersByMonthQuery) -> Result[ActiveUsersByMonthDto]` runs:
  ```sql
  SELECT
      CAST(strftime('%Y', created_at) AS INTEGER) AS year,
      CAST(strftime('%m', created_at) AS INTEGER) AS month,
      COUNT(*) AS active_count
  FROM users
  WHERE is_active = 1
  GROUP BY year, month
  ORDER BY year, month
  ```
- Docstring references "Q anêmico" + Recipe D, AND notes that `strftime` is SQLite-specific (Postgres needs `EXTRACT(YEAR FROM ...)`).

Run `.venv/bin/pytest -q` — expect 105 passed (101 baseline + 4 reports integration after the post-review tightening).

Commit: `feat(reports): add active-users-by-month query (Q anêmico pattern)` followed by `test(reports): tighten canonical-example tests + clarify SQLite-only SQL`.

### Task 6: Wire the report into the API

Mirror the `app/api/v1/users/` convention exactly:
- `app/api/v1/reports/__init__.py` re-exports `router`.
- `app/api/v1/reports/deps.py` provides `get_active_users_by_month_handler` via `Annotated[AsyncSession, Depends(get_session)]`.
- `app/api/v1/reports/schemas.py` defines `ActiveUsersByMonthRowResponse` and `ActiveUsersByMonthResponse` (Pydantic) with a `from_dto` classmethod.
- `app/api/v1/reports/routes.py` defines `GET /v1/reports/active-users-by-month` returning `ActiveUsersByMonthResponse`. Uses `unwrap(await handler.handle(...))`.
- `app/api/v1/router.py` adds `from app.api.v1.reports import router as reports_router` and `api_router.include_router(reports_router)`.

E2E tests in `tests/e2e/reports/test_api.py`:
- `test_active_users_by_month_endpoint_empty` — empty DB, returns `{"items": []}`.
- `test_active_users_by_month_after_creating_users` — POSTs a user, GETs the report, asserts `len(items) == 1` and types.

Run full suite: 107 passed.

Commit: `feat(api): expose /v1/reports/active-users-by-month`.

### Task 7: Document the reports feature in README.md

- Add `reports/` to the structure tree (under `use_cases/` and `api/v1/`).
- Add a new `## Analytics / Relatórios` section after `## Módulo de IA` cross-referencing Recipe D.

Commit: `docs(readme): document the reports feature and analytics path`.

---

## Phase 3 — AI Module: solidify as a removable unit

The AI module is already runtime-toggled via `BACKEND_AI_PROVIDER=none`. The remaining work is making the **structure** unambiguous: a README inside `app/ai/`, an architecture test that fails if non-AI code starts to import from `app/ai/`, and a documented end-to-end removal smoke test.

### Task 8: Add `app/ai/README.md`

Document the AI module's layout (graph, state, nodes, tools, prompts, model_factory, streaming, context), the constraints (only `app/main.py` and `app/api/v1/ai_chat/` may import from `app.ai.*`), and how to add a new tool or replace a prompt. Cross-reference Recipe A.

### Task 9: Add architecture test that enforces the AI module's leaf status

- Create `tests/unit/architecture/__init__.py` (empty).
- Create `tests/unit/architecture/test_ai_isolation.py` with a single test that scans `app/` for `from app.ai.*` or `import app.ai*` imports and fails on any file outside `ALLOWED_IMPORTERS = {app/main.py, app/api/v1/ai_chat/routes.py, app/api/v1/ai_chat/__init__.py}` (and excluding `app/ai/` itself).
- Failure message points to `docs/template-customization.md → Recipe A`.

Run full suite: 108 passed.

Commit: `docs(ai): document module layout + enforce leaf-import invariant`.

### Task 10: Smoke-test the AI removal recipe

A manual verification step on a throwaway branch — we don't commit removal; we verify the recipe works.

Procedure:
1. `git checkout -b throwaway/verify-ai-removal`
2. Execute every step of Recipe A from `docs/template-customization.md` verbatim.
3. Run `.venv/bin/pytest -q`. All tests must pass.
4. `grep -rn "ai_provider\|app.ai\|ai_chat" app/ tests/` must return only matches in modified files (or zero).
5. If anything fails, switch back to the working branch and patch Recipe A. Commit the recipe fix.
6. Discard the throwaway branch (`git checkout` + `git branch -D`). **CAUTION:** previous attempts had the throwaway-branch deletions migrate back to `refactor/vertical-slicing` because uncommitted changes can survive `git checkout`. Run `git checkout -- .` and `git clean -fd` (with care for untracked files you want to keep — the plan file itself is untracked) before switching branches, OR commit the deletions on the throwaway branch first.

Smoke-test outcome: 5 gaps in Recipe A surfaced and were patched in commit `1302216`:
- Step 1 also deletes `tests/unit/architecture/test_ai_isolation.py` (now vacuous).
- Step 2 also removes `settings = get_settings()` (now unused).
- Step 5 also deletes `test_settings_ai_provider_default_none` from `tests/unit/core/test_config.py`.
- Step 6 (new) cleans the stale `ai_chat`/`ai_provider` docstring in `app/api/v1/router.py`.
- Verification command includes `BACKEND_DATABASE_URL` env var.

Re-smoke-test after patching: 106 passed, 0 stragglers, verification prints `ok`.

---

## Final verification

- Working tree clean on `refactor/vertical-slicing`.
- `.venv/bin/pytest -q` → 108 passed.
- All 9 commits listed above present in `git log`.
- `docs/template-customization.md` Recipe A verified end-to-end (smoke test + re-smoke test).
