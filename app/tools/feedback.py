from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from langchain_core.tools import tool

if TYPE_CHECKING:
    from app.session_logger import SessionLogger

LOG_PATH = Path(f"feedback-{datetime.now().strftime('%Y%m%dT%H%M%S')}.log")

# Set by the CLI when a session starts; cleared on session end.
_active_logger: "SessionLogger | None" = None
_active_turn: int = 0


def set_active_logger(logger: "SessionLogger | None", turn: int = 0) -> None:
    global _active_logger, _active_turn
    _active_logger = logger
    _active_turn = turn


def update_turn(turn: int) -> None:
    global _active_turn
    _active_turn = turn


@tool
def leave_feedback(message: str) -> str:
    """MANDATORY: call this whenever you cannot fully answer a user's question.
    This includes: missing tools (weather, distance, pricing, etc.), missing
    context, or any capability gap — however small. Call it before replying to
    the user. Do not skip it. Do not wait for a second attempt first.

    Args:
        message: Specific description of what was asked, what you lacked, and
            how it blocked you. Example: "User asked for walking distance to a
            venue. No distance/travel-time tool available."
    """
    now = datetime.now(tz=timezone.utc)
    if _active_logger is not None:
        try:
            _active_logger.record_feedback(
                turn=_active_turn, message=message, timestamp=now
            )
            return "Feedback recorded"
        except OSError as e:
            return f"Failed to record feedback: {e}"

    # Fallback: write to flat log when no session logger is active.
    try:
        with LOG_PATH.open("a") as f:
            f.write(f"[{now.isoformat()}] {message}\n")
        return f"Feedback recorded in {LOG_PATH}"
    except OSError as e:
        return f"Failed to record feedback: {e}"
