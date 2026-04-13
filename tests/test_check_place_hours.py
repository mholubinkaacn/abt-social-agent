"""Tests for the check_place_hours tool."""

import contextlib
from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest

from app.tools.places import check_place_hours

# Google Places API day-of-week: 0=Sunday, 1=Monday ... 6=Saturday
_OPEN_ALL_WEEK_17_23 = {
    "regularOpeningHours": {
        "periods": [
            {
                "open": {"day": d, "hour": 17, "minute": 0},
                "close": {"day": d, "hour": 23, "minute": 0},
            }
            for d in range(7)
        ]
    }
}


def _mock_response(data: dict) -> MagicMock:
    resp = MagicMock()
    resp.json.return_value = data
    return resp


def _patched(data: dict) -> contextlib.AbstractContextManager[None]:
    """Context manager: patch requests.get and the API key together."""

    @contextlib.contextmanager
    def _ctx() -> Generator[None, None, None]:
        with patch("app.tools.places.requests.get", return_value=_mock_response(data)):
            with patch("app.tools.places._api_key", return_value="test-key"):
                yield

    return _ctx()


# ---------------------------------------------------------------------------
# Scenario 1 — venue is open at the checked time
# ---------------------------------------------------------------------------


def test_open_status_returned_when_venue_is_open_at_checked_time() -> None:
    """
    Given a venue open every day 17:00–23:00
    When checked at 18:00 on a Monday (2026-04-13)
    Then it returns that the venue is open
    """
    with _patched(_OPEN_ALL_WEEK_17_23):
        result = check_place_hours.invoke(
            {"place_id": "ChIJ_test", "datetime_str": "2026-04-13T18:00:00"}
        )

    assert "open" in result.lower()


# ---------------------------------------------------------------------------
# Scenario 2 — venue closed at checked time, opens later the same day
# ---------------------------------------------------------------------------

_OPEN_ALL_WEEK_20_23 = {
    "regularOpeningHours": {
        "periods": [
            {
                "open": {"day": d, "hour": 20, "minute": 0},
                "close": {"day": d, "hour": 23, "minute": 0},
            }
            for d in range(7)
        ]
    }
}


def test_closed_with_next_opening_today_when_venue_opens_later_same_day() -> None:
    """
    Given a venue open every day 20:00–23:00
    When checked at 18:00 on a Monday (2026-04-13)
    Then it returns closed and reports "today at 20:00"
    """
    with _patched(_OPEN_ALL_WEEK_20_23):
        result = check_place_hours.invoke(
            {"place_id": "ChIJ_test", "datetime_str": "2026-04-13T18:00:00"}
        )

    assert "closed" in result.lower()
    assert "today" in result.lower()
    assert "20:00" in result


# ---------------------------------------------------------------------------
# Scenario 3 — venue closed all day Monday, opens Tuesday at 17:00
# ---------------------------------------------------------------------------

# Places API: 0=Sun, 1=Mon, 2=Tue, 3=Wed, 4=Thu, 5=Fri, 6=Sat
_CLOSED_MONDAY_OPEN_TUESDAY_17 = {
    "regularOpeningHours": {
        "periods": [
            {
                "open": {"day": 2, "hour": 17, "minute": 0},
                "close": {"day": 2, "hour": 23, "minute": 0},
            },
        ]
    }
}


def test_closed_with_next_opening_next_day_when_venue_closed_all_day() -> None:
    """
    Given a venue closed on Mondays but open Tuesday 17:00–23:00
    When checked at 18:00 on Monday (2026-04-13)
    Then it returns closed and reports "Tuesday at 17:00"
    """
    with _patched(_CLOSED_MONDAY_OPEN_TUESDAY_17):
        result = check_place_hours.invoke(
            {"place_id": "ChIJ_test", "datetime_str": "2026-04-13T18:00:00"}
        )

    assert "closed" in result.lower()
    assert "tuesday" in result.lower()
    assert "17:00" in result


# ---------------------------------------------------------------------------
# Scenario 4 — venue has no opening hours data
# ---------------------------------------------------------------------------


def test_unavailable_returned_when_venue_has_no_hours_data() -> None:
    """
    Given a venue with no opening hours in the API response
    When checked at any time
    Then it returns that hours are unavailable
    """
    with _patched({}):
        result = check_place_hours.invoke(
            {"place_id": "ChIJ_test", "datetime_str": "2026-04-13T18:00:00"}
        )

    assert "not available" in result.lower()


# ---------------------------------------------------------------------------
# Scenario 5 — Places API is unreachable
# ---------------------------------------------------------------------------


def test_http_error_propagates_when_api_is_unreachable() -> None:
    """
    Given the Places API is unreachable
    When check_place_hours is called
    Then the error propagates to the caller
    """
    with patch(
        "app.tools.places.requests.get", side_effect=Exception("Connection refused")
    ):
        with patch("app.tools.places._api_key", return_value="test-key"):
            with pytest.raises(Exception, match="Connection refused"):
                check_place_hours.invoke(
                    {"place_id": "ChIJ_test", "datetime_str": "2026-04-13T18:00:00"}
                )
