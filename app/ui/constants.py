"""UI constants for the Withnail Streamlit app."""

from pathlib import Path

MAX_RETRIES = 2

LOGS_DIR = Path("logs")
FEEDBACK_DIR = Path("feedback")
AVATAR_PATH = "avatar.png"

_TOOL_STATUS: dict[str | None, str] = {
    None: "I'm making time\u2026",
    "search_places": "Free to those who can afford it, very expensive to those who can't.",
    "get_place_details": "Black puddings are no good to us. I want something's flesh!",
    "get_current_location": "We've gone on holiday by mistake.",
    "get_current_datetime": "Don't threaten me with a dead fish.",
    "get_weather": "Look at my tongue. It's wearing a yellow sock.",
    "leave_feedback": "Monty, you terrible\u2026",
}
_DEFAULT_STATUS = "I've only had a few ales."

WITHNAIL_SVG = ""
