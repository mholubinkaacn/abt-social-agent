#!/usr/bin/env python3
"""CLI entry point for the abt-social-agent."""

import argparse
import sys
from typing import Any

from dotenv import load_dotenv

load_dotenv()

# Maximum number of consecutive declined/failed turns before the session restarts.
MAX_RETRIES = 2

# Sentinel tokens the LLM appends to signal session events.
_SENTINEL_DECLINED = "[SESSION:DECLINED]"
_SENTINEL_FAILED = "[SESSION:FAILED]"


def _strip_sentinel(reply: str) -> tuple[str, str | None]:
    """
    Remove any trailing sentinel token from *reply*.

    Returns (clean_reply, sentinel_or_None).
    """
    for sentinel in (_SENTINEL_DECLINED, _SENTINEL_FAILED):
        if reply.rstrip().endswith(sentinel):
            clean = reply.rstrip()[: -len(sentinel)].rstrip()
            return clean, sentinel
    return reply, None


def run_query(query: str, model: str) -> None:
    from langchain_core.messages import HumanMessage

    from app.agent import build_agent

    agent = build_agent(model=model)
    print(f"\nQuery: {query}\n")
    print("-" * 60)

    result = agent.invoke(
        {
            "messages": [HumanMessage(content=query)],
            "preferences": {},
            "confirmed_place_id": None,
            "booked": False,
        }
    )
    final_message = result["messages"][-1].content
    print(f"Withnail: {final_message}\n")


def _run_intro(agent: Any) -> None:
    """Invoke the agent for the opening greeting and print it."""
    from langchain_core.messages import HumanMessage

    intro_state: dict = {
        "messages": [
            HumanMessage(
                content=(
                    "Introduce yourself: state your name (Withnail), your role "
                    "(helping find and book a venue for the ABT team social), "
                    "and what you will help with today."
                )
            )
        ],
        "preferences": {},
        "confirmed_place_id": None,
        "booked": False,
    }
    intro_result = agent.invoke(intro_state)
    print(f"Withnail: {intro_result['messages'][-1].content}\n")


def _run_single_session(model: str) -> bool:
    """
    Run one interactive session.

    Returns True if the session should restart (retry limit hit),
    raises SystemExit(0) on successful booking completion.
    """
    from langchain_core.messages import HumanMessage

    from app.agent import build_agent

    print("Type 'quit' or 'exit' to stop.\n")

    agent = build_agent(model=model)
    _run_intro(agent)

    state: dict = {
        "messages": [],
        "preferences": {},
        "confirmed_place_id": None,
        "booked": False,
    }

    consecutive_failures = 0

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            return False  # clean exit, no restart

        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit"):
            print("Goodbye.")
            return False  # clean exit, no restart

        state["messages"] = state["messages"] + [HumanMessage(content=user_input)]
        state = agent.invoke(state)

        raw_reply = state["messages"][-1].content
        clean_reply, sentinel = _strip_sentinel(raw_reply)

        # Update stored reply so future context doesn't include the sentinel.
        state["messages"][-1].content = clean_reply

        if state.get("booked"):
            print(f"\nWithnail: {clean_reply}\n")
            print("Booking complete. Goodbye!")
            sys.exit(0)

        if sentinel:
            consecutive_failures += 1
            print(f"\nWithnail: {clean_reply}\n")

            if consecutive_failures >= MAX_RETRIES:
                # Retry limit reached — explain and restart.
                print(
                    "\n[Withnail is ending this session — he has been unable to assist "
                    "with your last several requests. Starting a fresh session...]\n"
                )
                print("-" * 60)
                return True  # signal restart
        else:
            # Successful response — reset the failure counter.
            consecutive_failures = 0
            print(f"\nWithnail: {clean_reply}\n")


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
