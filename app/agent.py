import os
from typing import Annotated, Any, Literal, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from langgraph.graph.graph import CompiledGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from app.tools import ALL_TOOLS

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"

SYSTEM_PROMPT = """\
You are a planning agent helping to find and book a venue for the Agentic \
Business Transformation (ABT) team social event.

## Workflow

Work through these stages in order. You may gather information incrementally \
as the conversation develops.

1. **Gather preferences** — Before searching, ask about: number of attendees, \
preferred city or neighbourhood, venue type (restaurant, bar, rooftop, activity, \
etc.), date and time, and any budget, dietary, or accessibility requirements.

2. **Search and recommend** — Use your tools to find venues that match the stated \
preferences. Present each option with name, address, rating, and a brief reason it \
fits the criteria. Suggest a top choice with justification.

3. **Confirm** — Before booking, read back the venue name, address, and key details. \
Ask the user to explicitly confirm before proceeding.

4. **Book** — Only proceed to book after receiving explicit confirmation. Report \
success once the booking is complete.

## Guidelines
- Gather as many preferences as possible before searching, but refine them as you \
go if needed.
- Always use your tools to verify place details — never guess or fabricate addresses, \
phone numbers, or opening hours.
- If a search returns poor results, try alternative keywords or a broader radius.
- If you are blocked or uncertain, state clearly what you are trying to do and what \
information or tool you need to continue.
- If an error occurs, report the full error message and the action that triggered it.
"""


class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    preferences: dict[str, Any]  # attendees, area, venue_type, date, budget, etc.
    confirmed_place_id: str | None  # place ID once the user has confirmed a venue
    booked: bool  # True once the booking is complete


def _state_context(state: AgentState) -> str:
    """Build a structured context block from current state to append to the system prompt."""
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
            "  The booking is complete. Confirm the details with the user and close the session."
        )

    return ("\n\n" + "\n\n".join(parts)) if parts else ""


def build_agent(model: str = "gemini-2.5-flash") -> CompiledGraph:
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
        response = llm_with_tools.invoke([system] + state["messages"])
        return {"messages": [response]}

    def should_continue(state: AgentState) -> Literal["tools", "__end__"]:
        if state.get("booked"):
            return END
        last = state["messages"][-1]
        if isinstance(last, AIMessage) and last.tool_calls:
            return "tools"
        return END

    graph = StateGraph(AgentState)
    graph.add_node("agent", call_model)
    graph.add_node("tools", tool_node)
    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", should_continue)
    graph.add_edge("tools", "agent")

    return graph.compile()
