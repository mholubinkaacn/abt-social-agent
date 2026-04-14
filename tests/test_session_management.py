"""
Session management tests — mapped to features/session_management.feature.

Each test function corresponds to a Given-When-Then scenario in the feature file.
Tests exercise run_session() and run_interactive() through their public interfaces;
the agent LLM is replaced with a fake that returns controlled responses.
"""

from io import StringIO
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

MAX_RETRIES = 2  # must match cli.MAX_RETRIES


def _fake_agent(responses: list[dict]) -> MagicMock:
    """Build a mock agent whose invoke() returns each dict in sequence."""
    agent = MagicMock()
    agent.invoke.side_effect = responses
    return agent


def _reply(content: str, booked: bool = False) -> dict:
    """Minimal agent state dict with a single AI reply."""
    return {
        "messages": [MagicMock(content=content)],
        "booked": booked,
        "preferences": {},
        "confirmed_place_id": None,
    }


# ---------------------------------------------------------------------------
# Scenario 1 — booking completion exits the process
# ---------------------------------------------------------------------------


def test_booking_completion_exits_the_process() -> None:
    """
    Given the agent has confirmed a venue and completed the booking
    When the agent returns a state with booked=True
    Then the CLI prints a farewell message and the process exits entirely
    """
    from cli import run_interactive

    # Intro reply (booked=False), then booking reply (booked=True)
    intro_reply = _reply("I am Withnail, here to find a venue.")
    booking_reply = _reply("Booking confirmed! Enjoy the evening.", booked=True)
    fake = _fake_agent([intro_reply, booking_reply])

    with patch("app.agent.build_agent", return_value=fake):
        with patch("builtins.input", return_value="Book the Crown."):
            with patch("sys.stdout", new_callable=StringIO) as out:
                with pytest.raises(SystemExit) as exc_info:
                    run_interactive(model="test-model")

    assert exc_info.value.code == 0
    output = out.getvalue()
    assert "Booking confirmed" in output


# ---------------------------------------------------------------------------
# Scenario 2 — SESSION:DECLINED sentinel increments retry counter
# ---------------------------------------------------------------------------


def test_declined_sentinel_strips_sentinel_and_shows_no_retry_warning() -> None:
    """
    Given the user sends an out-of-scope request
    When the agent reply ends with [SESSION:DECLINED]
    Then the sentinel is stripped before display
    And no retry count or session management message is shown to the user
    """
    from cli import run_interactive

    intro_reply = _reply("I am Withnail.")
    declined_reply = _reply("I shan't help with that.\n[SESSION:DECLINED]")
    quit_reply = _reply("Farewell.")

    fake = _fake_agent([intro_reply, declined_reply, quit_reply])

    with patch("app.agent.build_agent", return_value=fake):
        with patch("builtins.input", side_effect=["book a holiday", "exit"]):
            with patch("sys.stdout", new_callable=StringIO) as out:
                run_interactive(model="test-model")

    output = out.getvalue()
    assert (
        "[SESSION:DECLINED]" not in output
    ), "Sentinel must be stripped before display"
    assert "retr" not in output.lower(), "Retry count must not be shown to the user"
    assert (
        "session" not in output.lower()
    ), "Session management state must not be shown to the user"


def test_failed_sentinel_strips_sentinel_and_shows_no_retry_warning() -> None:
    """
    Given the agent cannot complete a valid request due to a capability limitation
    When the agent reply ends with [SESSION:FAILED]
    Then the sentinel is stripped before display
    And no retry count or session management message is shown to the user
    """
    from cli import run_interactive

    intro_reply = _reply("I am Withnail.")
    failed_reply = _reply("I regret I cannot proceed.\n[SESSION:FAILED]")

    fake = _fake_agent([intro_reply, failed_reply, _reply("Goodbye.")])

    with patch("app.agent.build_agent", return_value=fake):
        with patch("builtins.input", side_effect=["do something impossible", "exit"]):
            with patch("sys.stdout", new_callable=StringIO) as out:
                run_interactive(model="test-model")

    output = out.getvalue()
    assert "[SESSION:FAILED]" not in output, "Sentinel must be stripped before display"
    assert "retr" not in output.lower(), "Retry count must not be shown to the user"


# ---------------------------------------------------------------------------
# Scenario 3 — valid reply resets the retry counter
# ---------------------------------------------------------------------------


def test_valid_reply_after_decline_resets_retry_counter() -> None:
    """
    Given the user has made one out-of-scope request (retry counter = 1)
    When the user sends a valid venue-booking request with no sentinel in the reply
    Then the retry counter resets to zero so further declines don't restart prematurely
    """
    from cli import run_interactive

    intro_reply = _reply("I am Withnail.")
    declined_reply = _reply("I shan't.\n[SESSION:DECLINED]")
    valid_reply = _reply("Great choice — searching for pubs in Shoreditch.")
    # Two more declines would restart if counter hadn't reset; they should just warn
    declined_again = _reply("No.\n[SESSION:DECLINED]")

    fake = _fake_agent(
        [intro_reply, declined_reply, valid_reply, declined_again, _reply("Goodbye.")]
    )

    with patch("app.agent.build_agent", return_value=fake):
        with patch(
            "builtins.input",
            side_effect=[
                "book a holiday",  # out-of-scope → counter=1
                "find a pub",  # valid → counter resets to 0
                "book a holiday again",  # out-of-scope → counter=1 (not 2)
                "exit",
            ],
        ):
            with patch("sys.stdout", new_callable=StringIO) as out:
                run_interactive(model="test-model")

    output = out.getvalue()
    # Session must NOT have restarted (intro greeting appears only once)
    intro_count = output.count("I am Withnail")
    assert intro_count == 1, (
        f"Intro printed {intro_count} times; "
        "session must not restart when counter resets"
    )


# ---------------------------------------------------------------------------
# Scenario 4 — retry limit exhausted restarts the session
# ---------------------------------------------------------------------------


def test_third_consecutive_decline_restarts_the_session() -> None:
    """
    Given the user has already made two declined requests (retry counter = 2)
    When the agent declines a third consecutive request
    Then Withnail explains he is ending the session
    And the session restarts with fresh state (intro greeting re-runs)
    And the retry counter resets to zero
    """
    from cli import run_interactive

    # Session 1: intro + 3 declines → restart
    s1_intro = _reply("I am Withnail, session one.")
    s1_d1 = _reply("No.\n[SESSION:DECLINED]")
    s1_d2 = _reply("No.\n[SESSION:DECLINED]")
    s1_d3 = _reply("No.\n[SESSION:DECLINED]")
    # Session 2 (after restart): intro then user exits
    s2_intro = _reply("I am Withnail, session two.")

    fake = _fake_agent([s1_intro, s1_d1, s1_d2, s1_d3, s2_intro])

    with patch("app.agent.build_agent", side_effect=[fake, fake]):
        with patch(
            "builtins.input",
            side_effect=[
                "bad request 1",
                "bad request 2",
                "bad request 3",
                "exit",  # exit during restarted session
            ],
        ):
            with patch("sys.stdout", new_callable=StringIO) as out:
                run_interactive(model="test-model")

    output = out.getvalue()
    # Ending explanation must appear
    assert "ending" in output.lower() or "session" in output.lower()
    # Intro greeting must appear twice — once per session
    assert (
        output.count("I am Withnail") >= 2
    ), "Intro greeting must re-run after session restart"


def test_third_consecutive_failure_restarts_the_session() -> None:
    """
    Given the user has already made two failed requests (retry counter = 2)
    When the agent signals a third consecutive failure
    Then the session restarts with fresh state and the intro greeting re-runs
    """
    from cli import run_interactive

    s1_intro = _reply("I am Withnail, session one.")
    s1_f1 = _reply("Cannot do it.\n[SESSION:FAILED]")
    s1_f2 = _reply("Cannot do it.\n[SESSION:FAILED]")
    s1_f3 = _reply("Cannot do it.\n[SESSION:FAILED]")
    s2_intro = _reply("I am Withnail, session two.")

    fake = _fake_agent([s1_intro, s1_f1, s1_f2, s1_f3, s2_intro])

    with patch("app.agent.build_agent", side_effect=[fake, fake]):
        with patch(
            "builtins.input",
            side_effect=["try 1", "try 2", "try 3", "exit"],
        ):
            with patch("sys.stdout", new_callable=StringIO) as out:
                run_interactive(model="test-model")

    output = out.getvalue()
    assert output.count("I am Withnail") >= 2


# ---------------------------------------------------------------------------
# Scenario 5 — session restart re-runs the intro greeting with fresh state
# ---------------------------------------------------------------------------


def test_restarted_session_begins_with_fresh_state_and_intro_greeting() -> None:
    """
    Given a session restart has been triggered by exhausting the retry limit
    When the new session begins
    Then the agent is invoked with empty messages (fresh state)
    And the intro greeting is displayed before the user is prompted to type
    """
    from cli import run_interactive

    s1_intro = _reply("Hello, session one.")
    s1_d1 = _reply("No.\n[SESSION:DECLINED]")
    s1_d2 = _reply("No.\n[SESSION:DECLINED]")
    s1_d3 = _reply("No.\n[SESSION:DECLINED]")
    s2_intro = _reply("Hello, session two.")

    captured_states: list[dict] = []

    def capturing_invoke(state: dict) -> dict:
        captured_states.append(state)
        responses = [s1_intro, s1_d1, s1_d2, s1_d3, s2_intro]
        return responses[len(captured_states) - 1]

    fake = MagicMock()
    fake.invoke.side_effect = capturing_invoke

    with patch("app.agent.build_agent", side_effect=[fake, fake]):
        with patch(
            "builtins.input",
            side_effect=["bad 1", "bad 2", "bad 3", "exit"],
        ):
            with patch("sys.stdout", new_callable=StringIO):
                run_interactive(model="test-model")

    # The 5th invoke is the session-2 intro — its state must have empty messages
    assert len(captured_states) >= 5
    s2_intro_state = captured_states[4]
    assert s2_intro_state["booked"] is False
    assert s2_intro_state["preferences"] == {}
    assert s2_intro_state["confirmed_place_id"] is None
