"""Rendering helpers and CSS for the Withnail Streamlit app."""

from __future__ import annotations

from typing import Any

import streamlit as st

from app.ui.constants import AVATAR_PATH

_CSS = """
<style>
/* ── GLOBAL ── */
html, body, [data-testid="stApp"] {
    background: #0A0A0A !important;
    color: #FFFFFF;
    font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
}

/* Hide default Streamlit chrome */
[data-testid="stHeader"] { display: none !important; }
#MainMenu { visibility: hidden; }
footer { visibility: hidden; }

/* ── SIDEBAR ── */
[data-testid="stSidebar"] {
    background: #111111 !important;
    border-right: 1px solid #222222;
}
[data-testid="stSidebar"] * { color: #CCCCCC !important; }

/* ── CUSTOM HEADER ── */
.wn-header {
    background: #000000;
    border-bottom: 1px solid #A100FF;
    padding: 0 24px;
    height: 64px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 8px;
}
.wn-header-left { display: flex; align-items: center; gap: 14px; }
.wn-title {
    font-size: 18px;
    font-weight: 700;
    letter-spacing: 0.22em;
    color: #FFFFFF;
    text-transform: uppercase;
}
.wn-tagline { font-size: 12px; color: #555555; font-style: italic; }

/* ── CHAT BUBBLES ── */
.wn-row { display: flex; align-items: flex-start; gap: 12px; margin-bottom: 20px; }
.wn-row.user { flex-direction: row-reverse; }

.wn-bubble-wrap { display: flex; flex-direction: column; max-width: 72%; }
.wn-row.user .wn-bubble-wrap { align-items: flex-end; }

.wn-bubble {
    background: #1A1A1A;
    border-left: 3px solid #A100FF;
    border-radius: 0 10px 10px 0;
    padding: 14px 18px;
    font-size: 14px;
    line-height: 1.65;
    color: #ECECEC;
}
.wn-row.user .wn-bubble {
    background: #2A2A2A;
    border-left: none;
    border-right: 3px solid #555555;
    border-radius: 10px 0 0 10px;
    color: #FFFFFF;
}

.wn-ts {
    font-size: 11px;
    color: #444444;
    margin-top: 5px;
    padding: 0 2px;
}

/* ── STATUS LINE ── */
.wn-status {
    font-size: 13px;
    color: #666666;
    font-style: italic;
    padding: 6px 0 6px 4px;
    animation: wn-pulse 1.8s ease-in-out infinite;
}
@keyframes wn-pulse {
    0%, 100% { opacity: 0.5; }
    50% { opacity: 1; }
}

/* ── BLINKING CURSOR ── */
.wn-cursor {
    display: inline-block;
    width: 2px;
    height: 14px;
    background: #A100FF;
    margin-left: 2px;
    vertical-align: middle;
    animation: wn-blink 1s step-end infinite;
}
@keyframes wn-blink { 0%, 100% { opacity: 1; } 50% { opacity: 0; } }

/* ── SYSTEM NOTICE ── */
.wn-system-notice {
    text-align: center;
    font-size: 12px;
    color: #555555;
    font-style: italic;
    padding: 8px 0;
    border-top: 1px solid #1E1E1E;
    border-bottom: 1px solid #1E1E1E;
    margin: 8px 0;
}

/* ── SUCCESS CARD ── */
.wn-success {
    background: #0D1A0D;
    border: 1px solid #00CC44;
    border-radius: 8px;
    padding: 16px 20px;
    font-size: 14px;
    color: #00CC44;
    margin-bottom: 20px;
}

/* ── INPUT AREA ── */
[data-testid="stBottom"] {
    background: #111111 !important;
    border-top: 1px solid #333333 !important;
}
[data-testid="stChatInput"] textarea {
    background: #111111 !important;
    border: 1px solid #2A2A2A !important;
    color: #FFFFFF !important;
    border-radius: 8px !important;
    caret-color: #A100FF !important;
}
[data-testid="stChatInput"] textarea::placeholder { color: #444444 !important; }
[data-testid="stChatInput"] textarea:focus {
    border-color: #A100FF !important;
    box-shadow: 0 0 0 2px #A100FF18 !important;
}
[data-testid="stChatInputSubmitButton"] button {
    background: #A100FF !important;
    border-radius: 8px !important;
}
[data-testid="stChatInputSubmitButton"] button:hover {
    background: #C040FF !important;
}

/* ── BUTTONS ── */
[data-testid="stButton"] button {
    background: #1A1A1A !important;
    border: 1px solid #333333 !important;
    color: #CCCCCC !important;
}
[data-testid="stButton"] button:hover {
    border-color: #A100FF !important;
    color: #FFFFFF !important;
}
</style>
"""


def _feedback_highlight_css(unread: int) -> str:
    """Return CSS that highlights the feedback expander when there is unread feedback."""
    if unread <= 0:
        return ""
    return """
<style>
[data-testid="stSidebar"] [data-testid="stExpander"] {
    border: 1px solid #A100FF !important;
    border-radius: 6px !important;
    box-shadow: 0 0 8px #A100FF44 !important;
    background: #1A001A !important;
}
[data-testid="stSidebar"] [data-testid="stExpander"] summary {
    color: #C060FF !important;
}
</style>
"""


def _avatar_img_tag(size: int = 34) -> str:
    """Return an <img> tag for avatar.png encoded as base64."""
    import base64

    with open(AVATAR_PATH, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    return (
        f'<img src="data:image/png;base64,{b64}" '
        f'style="width:{size}px;height:{size}px;border-radius:50%;'
        f'border:1px solid #A100FF44;flex-shrink:0;margin-top:2px;">'
    )


def _render_message(msg: dict) -> None:
    role = msg["role"]
    content = msg["content"]
    ts = msg.get("ts", "")

    if role == "system":
        st.markdown(
            f'<div class="wn-system-notice">{content}</div>', unsafe_allow_html=True
        )
        return

    if role == "success":
        st.markdown(
            f'<div class="wn-success">\u2713 {content}</div>', unsafe_allow_html=True
        )
        return

    if role == "assistant":
        st.markdown(
            f"""<div class="wn-row agent">
  {_avatar_img_tag()}
  <div class="wn-bubble-wrap">
    <div class="wn-bubble">{content}</div>
    <span class="wn-ts">{ts}</span>
  </div>
</div>""",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f"""<div class="wn-row user">
  <div class="wn-bubble-wrap">
    <div class="wn-bubble">{content}</div>
    <span class="wn-ts">{ts}</span>
  </div>
</div>""",
            unsafe_allow_html=True,
        )


def _render_status(tool_name: str | None) -> Any:
    from app.ui.constants import _DEFAULT_STATUS, _TOOL_STATUS

    text = _TOOL_STATUS.get(tool_name, _DEFAULT_STATUS)
    return st.markdown(
        f'<div class="wn-status">\u2836 {text}</div>', unsafe_allow_html=True
    )
