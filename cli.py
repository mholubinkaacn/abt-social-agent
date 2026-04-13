#!/usr/bin/env python3
"""CLI entry point for the abt-social-agent."""

import argparse

from dotenv import load_dotenv

load_dotenv()


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
    print(f"Agent: {final_message}\n")


def run_interactive(model: str) -> None:
    from langchain_core.messages import HumanMessage

    from app.agent import build_agent

    print("abt-social-agent (Google Places)")
    print("Type 'quit' or 'exit' to stop.\n")

    agent = build_agent(model=model)
    state: dict = {
        "messages": [],
        "preferences": {},
        "confirmed_place_id": None,
        "booked": False,
    }

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            break

        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit"):
            print("Goodbye.")
            break

        state["messages"] = state["messages"] + [HumanMessage(content=user_input)]
        state = agent.invoke(state)
        reply = state["messages"][-1].content
        print(f"\nAgent: {reply}\n")

        if state.get("booked"):
            print("Booking complete. Goodbye!")
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
