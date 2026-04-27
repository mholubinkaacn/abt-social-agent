"""Streamlit UI entry point for Withnail.

Launch with:  streamlit run streamlit_app.py
"""

from __future__ import annotations

from datetime import datetime, timezone

import streamlit as st
from dotenv import load_dotenv

from app.ui.render import (
    _CSS,
    _avatar_img_tag,
    _feedback_highlight_css,
    _render_message,
)
from app.ui.session import (
    _do_restart,
    _init_session,
    _mark_feedback_read,
    _run_intro,
)
from app.ui.streaming import _run_streaming_turn

load_dotenv()


def main() -> None:
    st.set_page_config(
        page_title="Withnail", layout="wide", initial_sidebar_state="expanded"
    )
    st.markdown(_CSS, unsafe_allow_html=True)

    ss = st.session_state

    # ── Session init ──────────────────────────────────────────────────────
    if "session_id" not in ss:
        _init_session(ss)
        _run_intro(ss.agent, ss)

    # ── Header ────────────────────────────────────────────────────────────
    st.markdown(
        f"""<div class="wn-header">
  <div class="wn-header-left">
    {_avatar_img_tag(size=40)}
    <span class="wn-title">Withnail</span>
  </div>
  <span class="wn-tagline">the finest wines available to humanity</span>
</div>""",
        unsafe_allow_html=True,
    )

    # ── Sidebar ───────────────────────────────────────────────────────────
    with st.sidebar:
        if st.button("\u21ba Restart session"):
            _do_restart(ss)
            st.rerun()

        st.markdown("---")

        unread = ss.get("feedback_unread", 0)
        highlight = _feedback_highlight_css(unread)
        if highlight:
            st.markdown(highlight, unsafe_allow_html=True)

        with st.expander("Feedback", expanded=False):
            if unread > 0:
                _mark_feedback_read(ss)
            fb_msgs = ss.get("feedback_messages", [])
            if fb_msgs:
                for msg in fb_msgs:
                    st.markdown(f"\u2022 {msg}")
            else:
                st.markdown(
                    '<span style="color:#555555;font-size:13px;">No feedback this session.</span>',
                    unsafe_allow_html=True,
                )

    # ── Input ─────────────────────────────────────────────────────────────
    booked = ss.get("booked", False)
    if not booked:
        user_input = st.chat_input("Tell Withnail what you're looking for\u2026")
    else:
        st.chat_input("Booking complete.", disabled=True)
        user_input = None

    # ── Chat history ──────────────────────────────────────────────────────
    chat_container = st.container()
    with chat_container:
        for msg in ss.get("chat_messages", []):
            _render_message(msg)

    # ── Handle new input ──────────────────────────────────────────────────
    if user_input and user_input.strip():
        ts = datetime.now(tz=timezone.utc).strftime("%H:%M")
        user_msg = {"role": "user", "content": user_input.strip(), "ts": ts}
        ss.chat_messages.append(user_msg)
        with chat_container:
            _render_message(user_msg)
        _run_streaming_turn(user_input.strip(), ss, chat_container)
        st.rerun()


if __name__ == "__main__":
    main()
