from datetime import datetime
from pathlib import Path

from langchain_core.tools import tool

_EXECUTION_TIME = datetime.now().strftime("%Y%m%dT%H%M%S")
LOG_PATH = Path(f"feedback-{_EXECUTION_TIME}.log")


@tool
def leave_feedback(message: str) -> str:
    """Leave feedback for the agent's creators. Use this when you are struggling
    to complete a task — for example, when you need a tool that doesn't exist yet,
    or when you lack context required to proceed.

    Args:
        message: A description of what you need or what is missing.
    """
    try:
        with LOG_PATH.open("a") as f:
            timestamp = datetime.now().isoformat()
            f.write(f"[{timestamp}] {message}\n")
        return f"Feedback recorded in {LOG_PATH}"
    except OSError as e:
        return f"Failed to record feedback: {e}"
