"""BDD tests for Feature 1 — Reliable Agent Invocation via Streaming.

Each test maps to a Given-When-Then scenario from FEATURES.md.
"""

from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ai_chunk(content: str) -> MagicMock:
    from langchain_core.messages import AIMessageChunk

    chunk = AIMessageChunk(content=content)
    return chunk


def _make_tool_chunk(tool_name: str, tool_id: str) -> MagicMock:
    from langchain_core.messages import AIMessageChunk

    chunk = AIMessageChunk(
        content="",
        tool_call_chunks=[{"name": tool_name, "id": tool_id, "args": "", "index": 0}],
    )
    return chunk


def _make_tool_message(tool_call_id: str, content: str) -> MagicMock:
    from langchain_core.messages import ToolMessage

    return ToolMessage(content=content, tool_call_id=tool_call_id)


def _make_ai_message(content: str, tool_calls: list | None = None) -> MagicMock:
    from langchain_core.messages import AIMessage

    return AIMessage(content=content, tool_calls=tool_calls or [])


def _make_streaming_session_state(stream_chunks: list) -> MagicMock:
    """Build a minimal session state mock whose agent streams the given chunks."""
    ss = MagicMock()
    ss.turn = 0
    ss.agent_state = {
        "messages": [],
        "preferences": {},
        "confirmed_place_id": None,
        "booked": False,
    }
    ss.chat_messages = []
    ss.consecutive_failures = 0

    ss.agent.stream.return_value = iter(
        [(chunk, {"langgraph_node": "agent"}) for chunk in stream_chunks]
    )
    # Prevent invoke from being called; if it is, return a non-booked state
    ss.agent.invoke.return_value = {
        "messages": [],
        "preferences": {},
        "confirmed_place_id": None,
        "booked": False,
    }
    return ss


# ---------------------------------------------------------------------------
# Scenario 1 — streamed reply is the authoritative reply
# ---------------------------------------------------------------------------


def test_streamed_text_is_recorded_not_overwritten_by_invoke() -> None:
    """
    Given the agent streams a complete text reply
    When the turn completes
    Then the logged reply matches the streamed text, not a blank invoke artifact
    """
    from app.ui.streaming import _run_streaming_turn

    streamed_text = "There are several excellent wine bars nearby."
    chunks = [_make_ai_chunk(streamed_text)]
    ss = _make_streaming_session_state(chunks)

    chat_container = MagicMock()
    chat_container.__enter__ = MagicMock(return_value=MagicMock())
    chat_container.__exit__ = MagicMock(return_value=False)

    with (
        patch("app.ui.streaming.st"),
        patch("app.ui.streaming.fb_module"),
        patch("app.ui.render._avatar_img_tag", return_value=""),
        patch("app.ui.render._render_status"),
    ):
        _run_streaming_turn("find me a wine bar", ss, chat_container)

    logged_reply = ss.chat_messages[-1]["content"]
    assert logged_reply == streamed_text
    assert logged_reply.strip() != ""
    # The second invoke must NOT have been called
    ss.agent.invoke.assert_not_called()


# ---------------------------------------------------------------------------
# Scenario 2 — blank reply triggers fallback, never logged as empty
# ---------------------------------------------------------------------------


def test_blank_reply_shows_fallback_and_logs_failure_condition() -> None:
    """
    Given the stream yields only whitespace
    When the turn completes
    Then the user sees a fallback message and the log records the failure, not the blank
    """
    from app.ui.streaming import _run_streaming_turn

    chunks = [_make_ai_chunk("\n")]
    ss = _make_streaming_session_state(chunks)

    chat_container = MagicMock()
    chat_container.__enter__ = MagicMock(return_value=MagicMock())
    chat_container.__exit__ = MagicMock(return_value=False)

    with (
        patch("app.ui.streaming.st"),
        patch("app.ui.streaming.fb_module"),
        patch("app.ui.render._avatar_img_tag", return_value=""),
        patch("app.ui.render._render_status"),
    ):
        _run_streaming_turn("find me a wine bar", ss, chat_container)

    # User sees a non-empty fallback
    displayed = ss.chat_messages[-1]["content"]
    assert displayed.strip() != ""

    # Logger records the failure condition, not the blank
    logged_reply = ss.logger.record_turn.call_args[1]["reply"]
    assert logged_reply != "\n"
    assert "BLANK" in logged_reply or logged_reply.strip() != ""


# ---------------------------------------------------------------------------
# Scenario 3 — tool calls scoped to current turn only
# ---------------------------------------------------------------------------


def test_tool_calls_logged_for_current_turn_only() -> None:
    """
    Given a prior turn already placed tool call messages in the agent state
    When the current turn completes with its own tool call
    Then only the current turn's tool call appears in the log
    """
    from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

    from app.ui.streaming import _run_streaming_turn

    # Seed prior turn messages in agent_state
    prior_ai = AIMessage(
        content="",
        tool_calls=[
            {"name": "search_places", "args": {"query": "pub"}, "id": "tc_old"}
        ],
    )
    prior_tool = ToolMessage(content="old results", tool_call_id="tc_old")
    prior_reply = AIMessage(content="Here are some pubs.")

    current_tool_chunk = _make_tool_chunk("get_place_details", "tc_new")
    current_text_chunk = _make_ai_chunk("The Anchor is excellent.")

    ss = _make_streaming_session_state([current_tool_chunk, current_text_chunk])
    ss.agent_state["messages"] = [
        HumanMessage(content="first turn"),
        prior_ai,
        prior_tool,
        prior_reply,
    ]

    chat_container = MagicMock()
    chat_container.__enter__ = MagicMock(return_value=MagicMock())
    chat_container.__exit__ = MagicMock(return_value=False)

    with (
        patch("app.ui.streaming.st"),
        patch("app.ui.streaming.fb_module"),
        patch("app.ui.render._avatar_img_tag", return_value=""),
        patch("app.ui.render._render_status"),
    ):
        _run_streaming_turn("tell me about The Anchor", ss, chat_container)

    logged_tool_calls = ss.logger.record_turn.call_args[1]["tool_calls"]
    tool_names = [tc["tool"] for tc in logged_tool_calls]
    assert (
        "search_places" not in tool_names
    ), "prior turn tool call leaked into current turn log"


# ---------------------------------------------------------------------------
# Scenario 4 — CLI uses streaming, not invoke
# ---------------------------------------------------------------------------


def test_cli_turn_uses_streaming_not_invoke() -> None:
    """
    Given the CLI runs a turn
    When the agent responds
    Then the reply is collected via agent.stream(), not agent.invoke()
    """
    from langchain_core.messages import HumanMessage

    import cli

    streamed_reply = "Withnail recommends The Anchor."
    final_state: dict = {
        "messages": [
            HumanMessage(content="find me a pub"),
            _make_ai_message(streamed_reply),
        ],
        "preferences": {},
        "confirmed_place_id": None,
        "booked": False,
    }

    intro_state: dict = {
        "messages": [_make_ai_message("I am Withnail.")],
        "preferences": {},
        "confirmed_place_id": None,
        "booked": False,
    }

    mock_agent = MagicMock()
    mock_agent.invoke.return_value = intro_state  # allowed for intro only
    mock_agent.stream.return_value = iter([final_state])

    with (
        patch("app.agent.build_agent", return_value=mock_agent),
        patch("app.session_logger.SessionLogger"),
        patch("app.tools.feedback.set_active_logger"),
        patch("app.tools.feedback.update_turn"),
        patch("builtins.input", side_effect=["find me a pub", KeyboardInterrupt]),
        patch("builtins.print"),
    ):
        try:
            cli._run_single_session(model="gemini-2.5-flash")
        except (KeyboardInterrupt, SystemExit):
            pass

    # stream must have been called for the user turn
    mock_agent.stream.assert_called()
    # invoke only called once — for the intro, not the turn loop
    assert mock_agent.invoke.call_count == 1
