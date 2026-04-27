"""Streaming turn execution for the Withnail Streamlit app."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import streamlit as st
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage, ToolMessage

import app.tools.feedback as fb_module
from app.sentinel import _strip_sentinel
from app.ui.constants import _DEFAULT_STATUS, _TOOL_STATUS, MAX_RETRIES
from app.ui.session import (
    _do_restart,
    _extract_tool_calls,
    _handle_sentinel,
    _is_booked,
    _record_feedback_in_state,
)


def _status_text_for_tool(tool_name: str | None) -> str:
    return _TOOL_STATUS.get(tool_name, _DEFAULT_STATUS)


def _extract_feedback_from_tool_calls(tool_calls: list[dict]) -> list[str]:
    messages = []
    for tc in tool_calls:
        if tc.get("tool") == "leave_feedback":
            msg = tc.get("input", {}).get("message", "")
            if msg:
                messages.append(msg)
    return messages


def _run_streaming_turn(user_input: str, ss: Any, chat_container: Any) -> None:
    """Execute one user turn with streaming and update session_state."""
    from app.ui.render import _avatar_img_tag, _render_status

    turn = ss.turn + 1
    ss.turn = turn
    fb_module.update_turn(turn)

    turn_start_index = len(ss.agent_state["messages"])
    ss.agent_state["messages"] = ss.agent_state["messages"] + [
        HumanMessage(content=user_input)
    ]

    with chat_container:
        status_placeholder = st.empty()
        chat_placeholder = st.empty()

    accumulated = ""
    current_tool: str | None = None
    streaming_started = False
    # Collect tool-call AI messages and tool response messages from the stream
    streamed_messages: list[AIMessage | ToolMessage] = []
    current_ai_chunks: list[AIMessageChunk] = []

    with status_placeholder:
        _render_status(None)

    stream = ss.agent.stream(ss.agent_state, stream_mode="messages")

    for chunk, metadata in stream:
        if isinstance(chunk, ToolMessage):
            # Flush any accumulated AI chunks into a message first
            if current_ai_chunks:
                combined = current_ai_chunks[0]
                for c in current_ai_chunks[1:]:
                    combined = combined + c
                streamed_messages.append(combined)
                current_ai_chunks = []
            streamed_messages.append(chunk)
            current_tool = None
            with status_placeholder:
                _render_status(None)

        elif isinstance(chunk, AIMessageChunk):
            current_ai_chunks.append(chunk)

            if chunk.tool_call_chunks:
                for tc in chunk.tool_call_chunks:
                    name = tc.get("name")
                    if name:
                        current_tool = name
                        with status_placeholder:
                            _render_status(current_tool)

            if chunk.content:
                if not streaming_started:
                    streaming_started = True
                    status_placeholder.empty()
                accumulated += chunk.content
                with chat_placeholder:
                    st.markdown(
                        f"""<div class="wn-row agent">
  {_avatar_img_tag()}
  <div class="wn-bubble-wrap">
    <div class="wn-bubble">{accumulated}<span class="wn-cursor"></span></div>
  </div>
</div>""",
                        unsafe_allow_html=True,
                    )

    # Flush any remaining AI chunks
    if current_ai_chunks:
        combined = current_ai_chunks[0]
        for c in current_ai_chunks[1:]:
            combined = combined + c
        streamed_messages.append(combined)

    status_placeholder.empty()
    chat_placeholder.empty()

    clean_reply, sentinel = _strip_sentinel(accumulated)

    # Guard: blank reply — log failure, show fallback, never display empty content
    if not clean_reply.strip():
        clean_reply = "I appear to have lost my thread. Do try again."
        sentinel = None
        ss.logger.record_turn(
            turn=turn,
            user=user_input,
            reply="[BLANK REPLY — streaming artifact]",
            sentinel=None,
            tool_calls=[],
        )
        now = datetime.now(tz=timezone.utc)
        ss.chat_messages.append(
            {"role": "assistant", "content": clean_reply, "ts": now.strftime("%H:%M")}
        )
        return

    # Build final state from all streamed messages — tool calls and responses included
    final_ai = AIMessage(content=clean_reply)
    # Replace the last streamed AI message (which has the text) with the clean version
    turn_messages = [
        m for m in streamed_messages if not (isinstance(m, AIMessage) and m.content)
    ] + [final_ai]
    updated_messages = ss.agent_state["messages"] + turn_messages
    ss.agent_state = ss.agent_state | {"messages": updated_messages}

    current_turn_state = ss.agent_state | {
        "messages": ss.agent_state["messages"][turn_start_index:]
    }
    tool_calls = _extract_tool_calls(current_turn_state)
    now = datetime.now(tz=timezone.utc)

    ss.logger.record_turn(
        turn=turn,
        user=user_input,
        reply=clean_reply,
        sentinel=sentinel,
        tool_calls=tool_calls,
    )

    new_fb = _extract_feedback_from_tool_calls(tool_calls)
    if new_fb:
        _record_feedback_in_state(ss, new_fb)

    ts = now.strftime("%H:%M")
    ss.chat_messages.append({"role": "assistant", "content": clean_reply, "ts": ts})

    if _is_booked(ss.agent_state):
        ss.booked = True
        ss.logger.close(outcome="booked", now=datetime.now(tz=timezone.utc))
        fb_module.set_active_logger(None)
        ss.chat_messages.append(
            {
                "role": "success",
                "content": "Booking confirmed. Withnail has done his duty. You may proceed.",
                "ts": ts,
            }
        )
        return

    should_restart = _handle_sentinel(
        {"consecutive_failures": ss.consecutive_failures, "chat_messages": []},
        sentinel=sentinel,
    )
    if sentinel:
        ss.consecutive_failures = ss.consecutive_failures + (
            1 if not should_restart else MAX_RETRIES
        )
    else:
        ss.consecutive_failures = 0

    if should_restart or ss.consecutive_failures >= MAX_RETRIES:
        _do_restart(ss)
