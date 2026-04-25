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
