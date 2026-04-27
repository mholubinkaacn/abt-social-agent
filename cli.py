#!/usr/bin/env python3
"""CLI entry point for the abt-social-agent."""

import argparse
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv()

from app.sentinel import _strip_sentinel  # noqa: E402

MAX_RETRIES = 2

LOGS_DIR = Path("logs")
FEEDBACK_DIR = Path("feedback")


def _initial_state(messages: list | None = None) -> dict:
    return {
        "messages": messages or [],
        "preferences": {},
        "confirmed_place_id": None,
        "booked": False,
    }


def _extract_tool_calls(state: dict, turn: int) -> list[dict]:
    """Extract tool call records from this turn's messages."""
    from langchain_core.messages import AIMessage, ToolMessage

    results: list[dict] = []
    messages = state.get("messages", [])
    # Find AI messages with tool_calls and pair with ToolMessage outputs.
    tool_outputs: dict[str, str] = {}
    for msg in messages:
        if isinstance(msg, ToolMessage):
            tool_outputs[msg.tool_call_id] = str(msg.content)
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


def run_query(query: str, model: str) -> None:
    from langchain_core.messages import HumanMessage

    from app.agent import build_agent

    agent = build_agent(model=model)
    print(f"\nQuery: {query}\n")
    print("-" * 60)

    result = agent.invoke(_initial_state([HumanMessage(content=query)]))
    print(f"Withnail: {result['messages'][-1].content}\n")


def _run_intro(agent: Any) -> None:
    """Invoke the agent for the opening greeting and print it."""
    from langchain_core.messages import HumanMessage

    result = agent.invoke(
        _initial_state(
            [
                HumanMessage(
                    content=(
                        "Introduce yourself: state your name (Withnail), your role "
                        "(helping find and book a venue for the ABT team social), "
                        "and what you will help with today."
                    )
                )
            ]
        )
    )
    print(f"Withnail: {result['messages'][-1].content}\n")


def _run_single_session(model: str) -> bool:
    """Run one interactive session.

    Returns True if the session should restart (retry limit hit),
    raises SystemExit(0) on successful booking completion.
    """
    from langchain_core.messages import HumanMessage

    import app.tools.feedback as fb_module
    from app.agent import build_agent
    from app.session_logger import SessionLogger

    print("Type 'quit' or 'exit' to stop.\n")

    session_id = str(uuid.uuid4())
    now = datetime.now(tz=timezone.utc)
    LOGS_DIR.mkdir(exist_ok=True)
    FEEDBACK_DIR.mkdir(exist_ok=True)
    logger = SessionLogger(
        session_id=session_id,
        logs_dir=LOGS_DIR,
        feedback_dir=FEEDBACK_DIR,
        now=now,
    )
    fb_module.set_active_logger(logger, turn=0)

    agent = build_agent(model=model)
    _run_intro(agent)

    state: dict = _initial_state()
    consecutive_failures = 0
    turn = 0

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            logger.close(outcome="abandoned", now=datetime.now(tz=timezone.utc))
            fb_module.set_active_logger(None)
            return False

        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit"):
            print("Goodbye.")
            logger.close(outcome="abandoned", now=datetime.now(tz=timezone.utc))
            fb_module.set_active_logger(None)
            return False

        turn += 1
        fb_module.update_turn(turn)

        turn_start_index = len(state["messages"])
        state["messages"] = state["messages"] + [HumanMessage(content=user_input)]

        final_state: dict = {}
        for chunk in agent.stream(state, stream_mode="values"):
            final_state = chunk
        state = final_state

        raw_reply = state["messages"][-1].content
        clean_reply, sentinel = _strip_sentinel(raw_reply)

        if not clean_reply.strip():
            clean_reply = "I appear to have lost my thread. Do try again."
            logger.record_turn(
                turn=turn,
                user=user_input,
                reply="[BLANK REPLY — streaming artifact]",
                sentinel=None,
                tool_calls=[],
            )
            print(f"\nWithnail: {clean_reply}\n")
            continue

        state["messages"][-1].content = clean_reply

        current_turn_state = state | {"messages": state["messages"][turn_start_index:]}
        tool_calls = _extract_tool_calls(current_turn_state, turn)
        logger.record_turn(
            turn=turn,
            user=user_input,
            reply=clean_reply,
            sentinel=sentinel,
            tool_calls=tool_calls,
        )

        print(f"\nWithnail: {clean_reply}\n")

        if state.get("booked"):
            logger.close(outcome="booked", now=datetime.now(tz=timezone.utc))
            fb_module.set_active_logger(None)
            print("Booking complete. Goodbye!")
            sys.exit(0)

        if sentinel:
            consecutive_failures += 1
            if consecutive_failures >= MAX_RETRIES:
                logger.close(outcome="restarted", now=datetime.now(tz=timezone.utc))
                fb_module.set_active_logger(None)
                print(
                    "\n[Withnail is ending this session — he has been unable to assist "
                    "with your last several requests. Starting a fresh session...]\n"
                )
                print("-" * 60)
                return True
        else:
            consecutive_failures = 0


def run_interactive(model: str) -> None:
    """Run interactive sessions, restarting automatically when needed."""
    while True:
        should_restart = _run_single_session(model=model)
        if not should_restart:
            break


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Agent with Google Places API tools powered by LangGraph + Gemini."
    )
    parser.add_argument(
        "query",
        nargs="?",
        help="Run a single query and exit. Omit to start interactive mode.",
    )
    parser.add_argument(
        "--model",
        default="gemini-2.5-flash",
        help="Gemini model ID to use (default: gemini-2.5-flash).",
    )
    args = parser.parse_args()

    if args.query:
        run_query(args.query, model=args.model)
    else:
        run_interactive(model=args.model)


if __name__ == "__main__":
    main()
