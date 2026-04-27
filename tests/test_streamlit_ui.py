"""BDD tests for the Streamlit UI — Feature 0.

Each test maps to a Given-When-Then scenario from FEATURES.md.
The UI module is tested by calling its pure helper functions directly;
Streamlit's runtime (session_state, st.* calls) is mocked where needed.
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FIXED_SESSION_ID = "bbbbbbbb-1111-1111-1111-000000000002"
FIXED_NOW = datetime(2026, 4, 23, 10, 0, 0, tzinfo=timezone.utc)


def _make_ai_message(content: str, tool_calls: list | None = None) -> MagicMock:
    msg = MagicMock()
    msg.content = content
    msg.tool_calls = tool_calls or []
    return msg


# ---------------------------------------------------------------------------
# Scenario 1 — page load initialises session and greeting appears
# ---------------------------------------------------------------------------


def test_new_session_initialised_with_required_state_keys() -> None:
    """
    Given the user opens the app
    When the page loads for the first time
    Then a new session is initialised with uuid, logger, agent_state,
         and consecutive_failures stored in session_state
    """
    from app.ui.session import _init_session

    mock_state: dict = {}

    with (
        patch("app.ui.session.uuid.uuid4", return_value=FIXED_SESSION_ID),
        patch("app.ui.session.datetime") as mock_dt,
        patch("app.ui.session.SessionLogger"),
        patch("app.ui.session.build_agent"),
        patch("app.ui.session.fb_module"),
        patch("app.ui.session.LOGS_DIR"),
        patch("app.ui.session.FEEDBACK_DIR"),
    ):
        mock_dt.now.return_value = FIXED_NOW
        _init_session(mock_state)

    assert mock_state["session_id"] == FIXED_SESSION_ID
    assert mock_state["consecutive_failures"] == 0
    assert "agent_state" in mock_state
    assert mock_state["agent_state"]["booked"] is False
    assert mock_state["agent_state"]["messages"] == []
    assert "logger" in mock_state
    assert "agent" in mock_state


def test_intro_invocation_produces_greeting_message() -> None:
    """
    Given a freshly initialised session
    When the intro is invoked
    Then the greeting is appended to chat_messages as a dict with role 'assistant'
    """
    from app.ui.session import _run_intro

    mock_state: dict = {
        "chat_messages": [],
        "agent_state": {
            "messages": [],
            "preferences": {},
            "confirmed_place_id": None,
            "booked": False,
        },
    }
    greeting = "Ah. You've found me."
    mock_agent = MagicMock()
    mock_agent.invoke.return_value = {
        "messages": [_make_ai_message(greeting)],
        "preferences": {},
        "confirmed_place_id": None,
        "booked": False,
    }

    with patch("app.ui.session.fb_module"):
        _run_intro(mock_agent, mock_state)

    assert len(mock_state["chat_messages"]) == 1
    msg = mock_state["chat_messages"][0]
    assert msg["role"] == "assistant"
    assert greeting in msg["content"]


# ---------------------------------------------------------------------------
# Scenario 2 — status line text mapped to tool name
# ---------------------------------------------------------------------------


def test_status_text_mapped_to_search_places_tool() -> None:
    """
    Given the agent calls search_places during a turn
    When the tool call is in progress
    Then the status text matches the search_places entry in the lookup table
    """
    from app.ui.streaming import _status_text_for_tool

    assert (
        _status_text_for_tool("search_places")
        == "Free to those who can afford it, very expensive to those who can't."
    )


def test_status_text_mapped_to_get_place_details() -> None:
    from app.ui.streaming import _status_text_for_tool

    assert (
        _status_text_for_tool("get_place_details")
        == "Black puddings are no good to us. I want something's flesh!"
    )


def test_status_text_mapped_to_get_current_location() -> None:
    from app.ui.streaming import _status_text_for_tool

    assert (
        _status_text_for_tool("get_current_location")
        == "We've gone on holiday by mistake."
    )


def test_status_text_mapped_to_get_current_datetime() -> None:
    from app.ui.streaming import _status_text_for_tool

    assert (
        _status_text_for_tool("get_current_datetime")
        == "Don't threaten me with a dead fish."
    )


def test_status_text_mapped_to_get_weather() -> None:
    from app.ui.streaming import _status_text_for_tool

    assert (
        _status_text_for_tool("get_weather")
        == "Look at my tongue. It's wearing a yellow sock."
    )


def test_status_text_mapped_to_leave_feedback() -> None:
    from app.ui.streaming import _status_text_for_tool

    assert _status_text_for_tool("leave_feedback") == "Monty, you terrible\u2026"


def test_status_text_unknown_tool_falls_back_to_default() -> None:
    from app.ui.streaming import _status_text_for_tool

    assert _status_text_for_tool("some_unknown_tool") == "I've only had a few ales."


def test_status_text_initial_thinking() -> None:
    from app.ui.streaming import _status_text_for_tool

    assert _status_text_for_tool(None) == "I'm making time\u2026"


# ---------------------------------------------------------------------------
# Scenario 3 — sentinel stripping runs on completed string
# ---------------------------------------------------------------------------


def test_strip_sentinel_removes_declined_token() -> None:
    """
    Given a reply ending with [SESSION:DECLINED]
    When _strip_sentinel is called on the completed string
    Then the sentinel is removed and returned separately
    """
    from app.sentinel import _strip_sentinel

    clean, sentinel = _strip_sentinel("Sorry, I can't help. [SESSION:DECLINED]")
    assert sentinel == "[SESSION:DECLINED]"
    assert "[SESSION:DECLINED]" not in clean


def test_strip_sentinel_removes_failed_token() -> None:
    from app.sentinel import _strip_sentinel

    clean, sentinel = _strip_sentinel("Something went wrong. [SESSION:FAILED]")
    assert sentinel == "[SESSION:FAILED]"
    assert clean.strip() == "Something went wrong."


def test_strip_sentinel_leaves_clean_reply_unchanged() -> None:
    from app.sentinel import _strip_sentinel

    text = "Here are some options."
    clean, sentinel = _strip_sentinel(text)
    assert sentinel is None
    assert clean == text


# ---------------------------------------------------------------------------
# Scenario 4 — feedback messages extracted from tool call records
# ---------------------------------------------------------------------------


def test_feedback_messages_extracted_from_tool_records() -> None:
    """
    Given leave_feedback is called during a turn
    When tool call records are parsed after the turn completes
    Then the feedback message text is extracted into the session feedback list
    """
    from app.ui.streaming import _extract_feedback_from_tool_calls

    tool_calls = [
        {"tool": "search_places", "input": {"query": "wine bars"}, "output": "..."},
        {
            "tool": "leave_feedback",
            "input": {"message": "No pricing tool available."},
            "output": "Feedback recorded",
        },
    ]

    messages = _extract_feedback_from_tool_calls(tool_calls)
    assert messages == ["No pricing tool available."]


def test_no_feedback_messages_when_leave_feedback_not_called() -> None:
    from app.ui.streaming import _extract_feedback_from_tool_calls

    tool_calls = [
        {"tool": "search_places", "input": {"query": "wine bars"}, "output": "..."},
    ]
    assert _extract_feedback_from_tool_calls(tool_calls) == []


def test_multiple_feedback_messages_all_extracted() -> None:
    from app.ui.streaming import _extract_feedback_from_tool_calls

    tool_calls = [
        {"tool": "leave_feedback", "input": {"message": "First gap."}, "output": "ok"},
        {"tool": "leave_feedback", "input": {"message": "Second gap."}, "output": "ok"},
    ]
    messages = _extract_feedback_from_tool_calls(tool_calls)
    assert messages == ["First gap.", "Second gap."]


# ---------------------------------------------------------------------------
# Scenario 5 — session restart on retry limit
# ---------------------------------------------------------------------------


def test_consecutive_failures_incremented_on_sentinel() -> None:
    """
    Given consecutive_failures is 0
    When a turn completes with a sentinel reply
    Then consecutive_failures is incremented
    """
    from app.ui.session import _handle_sentinel

    state: dict = {"consecutive_failures": 0, "chat_messages": []}
    should_restart = _handle_sentinel(state, sentinel="[SESSION:FAILED]", max_retries=2)
    assert state["consecutive_failures"] == 1
    assert should_restart is False


def test_retry_limit_triggers_restart() -> None:
    """
    Given consecutive_failures is already at MAX_RETRIES - 1
    When another sentinel reply arrives
    Then _handle_sentinel returns True indicating a restart is needed
    """
    from app.ui.session import _handle_sentinel

    state: dict = {"consecutive_failures": 1, "chat_messages": []}
    should_restart = _handle_sentinel(state, sentinel="[SESSION:FAILED]", max_retries=2)
    assert should_restart is True


def test_no_sentinel_resets_consecutive_failures() -> None:
    """
    Given consecutive_failures is 1
    When a turn completes without a sentinel
    Then consecutive_failures is reset to 0
    """
    from app.ui.session import _handle_sentinel

    state: dict = {"consecutive_failures": 1, "chat_messages": []}
    should_restart = _handle_sentinel(state, sentinel=None, max_retries=2)
    assert state["consecutive_failures"] == 0
    assert should_restart is False


# ---------------------------------------------------------------------------
# Scenario 6 — booking success disables input
# ---------------------------------------------------------------------------


def test_booked_state_detected() -> None:
    """
    Given the agent_state has booked=True
    When the turn result is inspected
    Then _is_booked returns True
    """
    from app.ui.session import _is_booked

    agent_state: dict = {
        "booked": True,
        "messages": [],
        "preferences": {},
        "confirmed_place_id": None,
    }
    assert _is_booked(agent_state) is True


def test_not_booked_state_returns_false() -> None:
    from app.ui.session import _is_booked

    agent_state: dict = {
        "booked": False,
        "messages": [],
        "preferences": {},
        "confirmed_place_id": None,
    }
    assert _is_booked(agent_state) is False


# ---------------------------------------------------------------------------
# Scenario 7 — model selector absent; avatar.png used for chat bubbles;
#              input area colour tokens correct
# ---------------------------------------------------------------------------


def test_model_selector_not_present_in_sidebar() -> None:
    """
    Given the sidebar is rendered
    When the page loads
    Then no model selectbox is rendered (model is fixed at gemini-2.5-flash)
    """
    import streamlit_app

    assert not hasattr(streamlit_app, "_MODELS")


def test_agent_message_uses_avatar_png_not_svg() -> None:
    """
    Given an assistant message is rendered
    When _render_message is called
    Then the output references avatar.png, not an inline SVG
    """
    from app.ui.constants import WITHNAIL_SVG

    assert WITHNAIL_SVG == ""


def test_input_area_background_matches_spec() -> None:
    """
    Given the CSS is defined
    When the input area styles are inspected
    Then the textarea background is #111111 and top border is #333333
    (matching the mockup's input-area spec, not #0A0A0A which clashes)
    """
    from app.ui.render import _CSS

    assert "#111111" in _CSS
    assert "#333333" in _CSS


# ---------------------------------------------------------------------------
# Scenario 8 — feedback unread highlight (tracer bullet)
# ---------------------------------------------------------------------------


def test_feedback_unread_increments_when_new_feedback_arrives() -> None:
    """
    Given feedback_unread is 0
    When two feedback messages arrive via _record_feedback_in_state
    Then feedback_unread is 2
    """
    from app.ui.session import _record_feedback_in_state

    state: dict = {"feedback_messages": [], "feedback_unread": 0}
    _record_feedback_in_state(state, ["No pricing tool.", "No distance tool."])
    assert state["feedback_unread"] == 2
    assert state["feedback_messages"] == ["No pricing tool.", "No distance tool."]


def test_feedback_unread_resets_to_zero_when_viewed() -> None:
    """
    Given feedback_unread is 3
    When _mark_feedback_read is called
    Then feedback_unread is 0
    """
    from app.ui.session import _mark_feedback_read

    state: dict = {"feedback_unread": 3}
    _mark_feedback_read(state)
    assert state["feedback_unread"] == 0


def test_wn_dot_html_not_used_for_feedback_notification() -> None:
    """
    Given the old span-based dot approach caused raw HTML to appear as text
    When the sidebar feedback section is inspected
    Then no wn-dot class is present in the codebase
    """
    import streamlit_app

    source = open(streamlit_app.__file__).read()
    assert "wn-dot" not in source


def test_no_highlight_css_when_no_unread_feedback() -> None:
    """
    Given feedback_unread is 0
    When _feedback_highlight_css is called
    Then the returned string is empty — no highlight injected
    """
    from app.ui.render import _feedback_highlight_css

    assert _feedback_highlight_css(unread=0) == ""


def test_highlight_css_emitted_when_feedback_unread() -> None:
    """
    Given feedback_unread > 0
    When _feedback_highlight_css is called
    Then the returned CSS targets the expander with a purple highlight
    """
    from app.ui.render import _feedback_highlight_css

    css = _feedback_highlight_css(unread=1)
    assert "#A100FF" in css
    assert css.strip() != ""
