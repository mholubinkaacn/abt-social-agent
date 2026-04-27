"""Session management helpers for the Withnail Streamlit app."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

import app.tools.feedback as fb_module
from app.agent import build_agent
from app.session_logger import SessionLogger
from app.ui.constants import FEEDBACK_DIR, LOGS_DIR, MAX_RETRIES


def _initial_agent_state() -> dict:
    return {
        "messages": [],
        "preferences": {},
        "confirmed_place_id": None,
        "booked": False,
    }


def _init_session(state: dict, model: str = "gemini-2.5-flash") -> None:
    """Initialise a fresh session into *state* (a dict-like, e.g. st.session_state)."""
    LOGS_DIR.mkdir(exist_ok=True)
    FEEDBACK_DIR.mkdir(exist_ok=True)

    session_id = str(uuid.uuid4())
    now = datetime.now(tz=timezone.utc)

    logger = SessionLogger(
        session_id=session_id,
        logs_dir=LOGS_DIR,
        feedback_dir=FEEDBACK_DIR,
        now=now,
    )

    agent = build_agent(model=model)

    state["session_id"] = session_id
    state["session_started_at"] = now
    state["logger"] = logger
    state["agent"] = agent
    state["agent_state"] = _initial_agent_state()
    state["consecutive_failures"] = 0
    state["chat_messages"] = state.get("chat_messages", [])
    state["feedback_messages"] = []
    state["feedback_unread"] = 0
    state["turn"] = 0
    state["booked"] = False
    fb_module.set_active_logger(logger, turn=0)


def _run_intro(agent: Any, state: dict) -> None:
    """Invoke (not stream) the intro greeting and append to chat_messages."""
    from langchain_core.messages import HumanMessage

    result = agent.invoke(
        _initial_agent_state()
        | {
            "messages": [
                HumanMessage(
                    content=(
                        "Introduce yourself: state your name (Withnail), your role "
                        "(helping find and book a venue for the ABT team social), "
                        "and what you will help with today."
                    )
                )
            ]
        }
    )
    greeting = result["messages"][-1].content
    now = datetime.now(tz=timezone.utc)
    state["chat_messages"].append(
        {"role": "assistant", "content": greeting, "ts": now.strftime("%H:%M")}
    )


def _handle_sentinel(
    state: dict, sentinel: str | None, max_retries: int = MAX_RETRIES
) -> bool:
    """Update consecutive_failures and return True if a restart is needed."""
    if sentinel:
        state["consecutive_failures"] += 1
        if state["consecutive_failures"] >= max_retries:
            return True
    else:
        state["consecutive_failures"] = 0
    return False


def _is_booked(agent_state: dict) -> bool:
    return bool(agent_state.get("booked"))


def _record_feedback_in_state(state: dict, new_messages: list[str]) -> None:
    """Append new feedback messages and increment the unread counter."""
    state["feedback_messages"] = list(state.get("feedback_messages", [])) + new_messages
    state["feedback_unread"] = state.get("feedback_unread", 0) + len(new_messages)


def _mark_feedback_read(state: dict) -> None:
    """Reset the unread counter — called when the feedback expander is opened."""
    state["feedback_unread"] = 0


def _do_restart(ss: Any) -> None:
    """Clear session and re-initialise — called when retry limit is hit."""
    from datetime import datetime, timezone

    old_messages = list(ss.chat_messages)
    ss.logger.close(outcome="restarted", now=datetime.now(tz=timezone.utc))
    fb_module.set_active_logger(None)

    _init_session(ss)
    ss.chat_messages = old_messages + [
        {
            "role": "system",
            "content": "Withnail is starting a fresh session\u2026",
            "ts": "",
        }
    ]
    _run_intro(ss.agent, ss)


def _extract_tool_calls(agent_state: dict) -> list[dict]:
    from langchain_core.messages import AIMessage, ToolMessage

    messages = agent_state.get("messages", [])
    tool_outputs: dict[str, str] = {}
    for msg in messages:
        if isinstance(msg, ToolMessage):
            tool_outputs[msg.tool_call_id] = str(msg.content)

    results: list[dict] = []
    for msg in messages:
        if isinstance(msg, AIMessage) and msg.tool_calls:
            for tc in msg.tool_calls:
                results.append(
                    {
                        "tool": tc["name"],
                        "input": tc["args"],
                        "output": tool_outputs.get(tc["id"], ""),
                    }
                )
    return results
