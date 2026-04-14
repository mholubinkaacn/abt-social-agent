"""Tests for the get_current_datetime tool."""

from datetime import datetime
from unittest.mock import patch

# ---------------------------------------------------------------------------
# Scenario 1 — tool returns a parseable ISO 8601 datetime string
# ---------------------------------------------------------------------------


def test_result_contains_parseable_iso_datetime() -> None:
    """
    Given the system clock is set to a known time
    When get_current_datetime is called
    Then the result contains an ISO 8601 datetime string that can be parsed
    """
    from app.tools.datetime import get_current_datetime

    fixed = datetime(2026, 4, 14, 9, 30, 0)
    with patch("app.tools.datetime.datetime") as mock_dt:
        mock_dt.now.return_value = fixed

        result = get_current_datetime.invoke({})

    assert "2026-04-14T09:30:00" in result


# ---------------------------------------------------------------------------
# Scenario 2 — tool includes a human-readable date and time
# ---------------------------------------------------------------------------


def test_result_contains_human_readable_date_and_time() -> None:
    """
    Given the system clock is set to a known time (Tuesday 14 April 2026, 09:30)
    When get_current_datetime is called
    Then the result contains the full day name, date, and time in plain English
    """
    from app.tools.datetime import get_current_datetime

    fixed = datetime(2026, 4, 14, 9, 30, 0)
    with patch("app.tools.datetime.datetime") as mock_dt:
        mock_dt.now.return_value = fixed

        result = get_current_datetime.invoke({})

    assert "Tuesday" in result
    assert "14 April 2026" in result
    assert "09:30" in result


# ---------------------------------------------------------------------------
# Scenario 3 — tool reflects the live clock, not a cached value
# ---------------------------------------------------------------------------


def test_result_reflects_live_clock() -> None:
    """
    Given the system clock advances between two calls
    When get_current_datetime is called twice
    Then the two results reflect different times
    """
    from app.tools.datetime import get_current_datetime

    first = datetime(2026, 4, 14, 9, 0, 0)
    second = datetime(2026, 4, 14, 10, 0, 0)

    with patch("app.tools.datetime.datetime") as mock_dt:
        mock_dt.now.side_effect = [first, second]

        result_a = get_current_datetime.invoke({})
        result_b = get_current_datetime.invoke({})

    assert result_a != result_b


# ---------------------------------------------------------------------------
# Scenario 4 — tool is registered and available to the agent
# ---------------------------------------------------------------------------


def test_tool_is_registered_in_all_tools() -> None:
    """
    Given the agent is built
    When the list of available tools is inspected
    Then get_current_datetime is present
    """
    from app.tools import ALL_TOOLS
    from app.tools.datetime import get_current_datetime

    tool_names = [t.name for t in ALL_TOOLS]
    assert get_current_datetime.name in tool_names
