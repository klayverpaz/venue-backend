# AI Module

Self-contained LangGraph-based chat agent. **Optional** — the entire module is removable. See [Recipe A](../../docs/template-customization.md#recipe-a--remove-the-ai-module) in the customization guide.

## Layout

| Path | Role |
|------|------|
| `graph.py` | LangGraph `StateGraph` definition (chat agent) |
| `state.py` | `ChatState` TypedDict |
| `nodes/` | Graph nodes — `agent_node`, `tool_executor_node` |
| `tools/` | `@tool`-decorated callables exposed to the LLM. Each tool is a thin adapter that calls a use-case handler. |
| `prompts/` | Prompt files (currently `system_prompt.txt`). Treat prompts as versioned artifacts. |
| `model_factory.py` | LLM provider abstraction (Anthropic / OpenAI). |
| `streaming.py`, `context.py` | Streaming response helpers, contextvars for AI requests. |

## Constraints

- The AI module **may** import from `app.use_cases.*` and `app.domain.*` (tools call into existing handlers).
- Nothing outside `app/ai/` and `app/api/v1/ai_chat/` is allowed to import from `app/ai/*` (architecture invariant — see `tests/unit/architecture/test_ai_isolation.py`).
- Removing this module is a single recipe — see [Recipe A](../../docs/template-customization.md#recipe-a--remove-the-ai-module) for the full surface (deletes `app/ai/` and `app/api/v1/ai_chat/`, edits `app/main.py`, `app/core/config.py`, `app/api/v1/router.py`, `Makefile`, `CLAUDE.md`, the test conftests, and `tests/unit/core/test_config.py`; deletes `requirements-ai.txt` and the architecture test).

## Adding a new tool

1. Create `app/ai/tools/<tool_name>.py` with a single `@tool`-decorated async function.
2. The tool body should instantiate the relevant use-case handler (with a session pulled from `db_session` contextvar) and call its `handle(...)`.
3. Append the tool to `TOOLS` in `app/ai/tools/__init__.py`.
4. Tests: write a unit test that mocks the handler and asserts the tool returns the expected serialized payload.

## Adding/replacing a prompt

Prompts live in `app/ai/prompts/`. Treat them as code:
- Name the file with a version suffix when it stabilizes (`system_prompt_v2.txt`).
- Reference it explicitly in `app/ai/nodes/agent.py`.
- Don't inline prompt text in Python — keep them as files.
