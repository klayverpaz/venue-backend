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
