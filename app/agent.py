import os
from typing import Annotated, Any, Literal, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from langgraph.pregel import Pregel

from app.prompt import SYSTEM_PROMPT
from app.retry import invoke_with_exponential_backoff
from app.tools import ALL_TOOLS

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
NODE_TOOLS: Literal["tools"] = "tools"


class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    preferences: dict[str, Any]  # attendees, area, venue_type, date, budget, etc.
    confirmed_place_id: str | None  # place ID once the user has confirmed a venue
    booked: bool  # True once the booking is complete


def _state_context(state: AgentState) -> str:
    """Build a context block from current state to inject into the system prompt."""
    parts: list[str] = []

    prefs = state.get("preferences") or {}
    if prefs:
        lines = "\n".join(f"  - {k}: {v}" for k, v in prefs.items())
        parts.append(f"## Gathered preferences\n{lines}")

    confirmed = state.get("confirmed_place_id")
    if confirmed:
        parts.append(
            f"## Confirmed venue\n"
            f"  Place ID: {confirmed}\n"
            f"  The user has confirmed this venue — proceed directly to booking."
        )

    if state.get("booked"):
        parts.append(
            "## Status\n"
            "  The booking is complete. Confirm the details with the user and close "
            "the session."
        )

    return ("\n\n" + "\n\n".join(parts)) if parts else ""


def build_agent(model: str = "gemini-2.5-flash") -> Pregel:
    llm = ChatOpenAI(
        model=model,
        api_key=os.environ["GEMINI_API_KEY"],
        base_url=GEMINI_BASE_URL,
        temperature=0,
    )
    llm_with_tools = llm.bind_tools(ALL_TOOLS)
    tool_node = ToolNode(ALL_TOOLS)

    def call_model(state: AgentState) -> dict[str, list[BaseMessage]]:
        system = SystemMessage(content=SYSTEM_PROMPT + _state_context(state))
        response = invoke_with_exponential_backoff(
            llm_with_tools.invoke, [system] + state["messages"]
        )
        return {"messages": [response]}

    def should_continue(state: AgentState) -> Literal["tools", "__end__"]:
        if state.get("booked"):
            return END
        last = state["messages"][-1]
        if isinstance(last, AIMessage) and last.tool_calls:
            return NODE_TOOLS
        return END

    graph = StateGraph(AgentState)
    graph.add_node("agent", call_model)
    graph.add_node(NODE_TOOLS, tool_node)
    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", should_continue)
    graph.add_edge(NODE_TOOLS, "agent")

    return graph.compile()
