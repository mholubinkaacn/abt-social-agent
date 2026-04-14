from datetime import datetime

from langchain_core.tools import tool


@tool
def get_current_datetime() -> str:
    """Get the current local date and time.

    Returns the datetime in both ISO 8601 format (for use with other tools
    such as check_place_hours) and in plain English (for use in responses).
    """
    now = datetime.now()
    iso = now.strftime("%Y-%m-%dT%H:%M:%S")
    human = now.strftime("%A, %d %B %Y, %H:%M")
    return f"ISO: {iso}\nHuman: {human}"
