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
