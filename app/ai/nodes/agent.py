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
