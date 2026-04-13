"""Tests for the get_current_location tool."""

from unittest.mock import MagicMock, patch

import pytest

from app.tools.location import get_current_location

# ---------------------------------------------------------------------------
# Scenario 1 — happy path
# ---------------------------------------------------------------------------


def test_location_returned_when_api_responds_with_full_data() -> None:
    """
    Given the IP geolocation API returns full location data
    When get_current_location is called
    Then a formatted string with city, region, country, and coordinates is returned
    """
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "city": "London",
        "region": "England",
        "country_name": "United Kingdom",
        "latitude": 51.5074,
        "longitude": -0.1278,
    }

    with patch("app.tools.location.requests.get", return_value=mock_response):
        result = get_current_location.invoke({})

    assert "London" in result
    assert "England" in result
    assert "United Kingdom" in result
    assert "51.5074" in result
    assert "-0.1278" in result


# ---------------------------------------------------------------------------
# Scenario 2 — API failure
# ---------------------------------------------------------------------------


def test_http_error_is_raised_when_api_is_unreachable() -> None:
    """
    Given the IP geolocation API is unreachable
    When get_current_location is called
    Then the HTTP error propagates to the caller
    """
    with patch(
        "app.tools.location.requests.get",
        side_effect=Exception("Connection refused"),
    ):
        with pytest.raises(Exception, match="Connection refused"):
            get_current_location.invoke({})
