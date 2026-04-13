"""Tests for the CLI introductory greeting shown before the user types anything."""

from io import StringIO
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Scenario 1 — agent greets user before first input
# ---------------------------------------------------------------------------


def test_agent_greeting_is_printed_before_first_user_prompt() -> None:
    """
    Given a fresh interactive session
    When the CLI starts
    Then the agent prints a greeting before prompting the user to type
    """
    fake_agent = MagicMock()
    fake_agent.invoke.return_value = {
        "messages": [
            MagicMock(content="Hello! I'm Withnail, here to help find a venue.")
        ],
        "booked": False,
    }

    with patch("app.agent.build_agent", return_value=fake_agent):
        with patch("builtins.input", side_effect=["exit"]):
            with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
                import importlib

                import cli

                importlib.reload(cli)
                cli.run_interactive(model="test-model")

    output = mock_stdout.getvalue()
    assert "Withnail" in output or "Withnail:" in output


# ---------------------------------------------------------------------------
# Scenario 2 — intro invocation uses a HumanMessage, not SystemMessage
# ---------------------------------------------------------------------------


def test_intro_invocation_passes_human_message_to_agent() -> None:
    """
    Given a fresh interactive session
    When the CLI starts and triggers the intro
    Then the agent is invoked with a HumanMessage (not SystemMessage only),
    so that the Gemini API receives valid contents
    """
    from langchain_core.messages import HumanMessage, SystemMessage

    captured_states: list[dict] = []

    def capture_invoke(state: dict) -> dict:
        captured_states.append(state)
        return {
            "messages": [MagicMock(content="Hello! I'm Withnail.")],
            "booked": False,
        }

    fake_agent = MagicMock()
    fake_agent.invoke.side_effect = capture_invoke

    with patch("app.agent.build_agent", return_value=fake_agent):
        with patch("builtins.input", side_effect=["exit"]):
            with patch("sys.stdout", new_callable=StringIO):
                import importlib

                import cli

                importlib.reload(cli)
                cli.run_interactive(model="test-model")

    # The first invoke is the intro call
    intro_state = captured_states[0]
    messages = intro_state["messages"]
    assert any(
        isinstance(m, HumanMessage) for m in messages
    ), "Intro invocation must include a HumanMessage so Gemini receives valid contents"
    assert not any(isinstance(m, SystemMessage) for m in messages), (
        "Intro invocation must not pass a SystemMessage in state messages "
        "(the agent node adds the system prompt itself)"
    )


# ---------------------------------------------------------------------------
# Scenario 3 — intro trigger asks the agent to introduce itself by name
# ---------------------------------------------------------------------------


def test_intro_trigger_message_asks_agent_to_introduce_itself() -> None:
    """
    Given a fresh interactive session
    When the CLI starts and triggers the intro
    Then the trigger HumanMessage instructs the agent to state its name and role,
    so the greeting identifies Withnail rather than jumping to preference gathering
    """
    from langchain_core.messages import HumanMessage

    captured_states: list[dict] = []

    def capture_invoke(state: dict) -> dict:
        captured_states.append(state)
        return {
            "messages": [MagicMock(content="I'm Withnail, here to find a venue.")],
            "booked": False,
        }

    fake_agent = MagicMock()
    fake_agent.invoke.side_effect = capture_invoke

    with patch("app.agent.build_agent", return_value=fake_agent):
        with patch("builtins.input", side_effect=["exit"]):
            with patch("sys.stdout", new_callable=StringIO):
                import importlib

                import cli

                importlib.reload(cli)
                cli.run_interactive(model="test-model")

    intro_message = next(
        m for m in captured_states[0]["messages"] if isinstance(m, HumanMessage)
    )
    content = intro_message.content.lower()
    assert (
        "introduce" in content or "withnail" in content
    ), "Trigger message should ask for a self-introduction by name"
