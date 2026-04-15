import os
from datetime import datetime
from typing import Any

import requests
from langchain_core.tools import tool

PLACES_API_BASE = "https://places.googleapis.com/v1/places"

# Google Places API day-of-week: 0 = Sunday, 1 = Monday ... 6 = Saturday
# Python weekday():               0 = Monday ... 6 = Sunday
_PYTHON_TO_PLACES_DOW = [1, 2, 3, 4, 5, 6, 0]  # index by python weekday

_DAY_NAMES = [
    "Sunday",
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
]


def _api_key() -> str:
    key = os.environ.get("GOOGLE_PLACES_API_KEY")
    if not key:
        raise ValueError("GOOGLE_PLACES_API_KEY environment variable not set")
    return key


def _headers(field_mask: str) -> dict[str, str]:
    return {
        "X-Goog-Api-Key": _api_key(),
        "X-Goog-FieldMask": field_mask,
        "Content-Type": "application/json",
    }


def _format_place_line(p: dict) -> str:
    name = p.get("displayName", {}).get("text", "Unknown")
    address = p.get("formattedAddress", "N/A")
    rating = p.get("rating", "N/A")
    count = p.get("userRatingCount", 0)
    place_id = p.get("id", "N/A")
    return f"- {name} | {address} | Rating: {rating} ({count} reviews) | ID: {place_id}"


@tool
def search_places(query: str, max_results: int = 5) -> str:
    """Search for places using a text query. Returns a list of matching places
    with their name, address, rating, and place ID.

    Args:
        query: Free-text search string (e.g. "coffee shops in Austin TX").
        max_results: Maximum number of results to return (1-20, default 5).
    """
    field_mask = (
        "places.id,places.displayName,places.formattedAddress,"
        "places.rating,places.userRatingCount"
    )
    payload = {
        "textQuery": query,
        "pageSize": min(max(1, max_results), 20),
    }
    resp = requests.post(
        f"{PLACES_API_BASE}:searchText",
        headers=_headers(field_mask),
        json=payload,
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()

    places = data.get("places", [])
    if not places:
        return "No places found."

    return "\n".join(_format_place_line(p) for p in places)


@tool
def get_place_details(place_id: str) -> str:
    """Get detailed information about a specific place by its Place ID.
    Returns name, address, phone number, website, hours, and rating.

    Args:
        place_id: The Google Place ID (e.g. from search_places results).
    """
    field_mask = (
        "id,displayName,formattedAddress,nationalPhoneNumber,"
        "websiteUri,regularOpeningHours,rating,userRatingCount,"
        "priceLevel,editorialSummary,types"
    )
    resp = requests.get(
        f"{PLACES_API_BASE}/{place_id}",
        headers=_headers(field_mask),
        timeout=10,
    )
    resp.raise_for_status()
    p = resp.json()

    lines = [
        f"Name: {p.get('displayName', {}).get('text', 'N/A')}",
        f"Address: {p.get('formattedAddress', 'N/A')}",
        f"Phone: {p.get('nationalPhoneNumber', 'N/A')}",
        f"Website: {p.get('websiteUri', 'N/A')}",
        f"Rating: {p.get('rating', 'N/A')} ({p.get('userRatingCount', 0)} reviews)",
        f"Price level: {p.get('priceLevel', 'N/A')}",
        f"Types: {', '.join(p.get('types', []))}",
    ]

    summary = p.get("editorialSummary", {}).get("text")
    if summary:
        lines.append(f"Summary: {summary}")

    hours = p.get("regularOpeningHours", {}).get("weekdayDescriptions", [])
    if hours:
        lines.append("Hours:\n  " + "\n  ".join(hours))

    return "\n".join(lines)


@tool
def check_place_hours(place_id: str, datetime_str: str) -> str:
    """Check whether a place is open at a specific date and time, and report
    the next opening time if it is currently closed.

    Args:
        place_id: The Google Place ID.
        datetime_str: ISO 8601 datetime to check (e.g. "2026-04-13T18:00:00").
    """
    field_mask = "regularOpeningHours"
    resp = requests.get(
        f"{PLACES_API_BASE}/{place_id}",
        headers=_headers(field_mask),
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()

    periods = data.get("regularOpeningHours", {}).get("periods", [])
    if not periods:
        return "Opening hours not available for this venue."

    dt = datetime.fromisoformat(datetime_str)
    check_dow = _PYTHON_TO_PLACES_DOW[dt.weekday()]
    check_minutes = dt.hour * 60 + dt.minute

    for period in periods:
        open_info = period.get("open", {})
        close_info = period.get("close", {})
        if open_info.get("day") == check_dow:
            open_min = open_info["hour"] * 60 + open_info.get("minute", 0)
            close_min = close_info["hour"] * 60 + close_info.get("minute", 0)
            if open_min <= check_minutes < close_min:
                close_h = close_info["hour"]
                close_m = close_info.get("minute", 0)
                return f"Open — closing at {close_h:02d}:{close_m:02d}."

    sorted_periods = sorted(
        periods, key=lambda p: p["open"]["hour"] * 60 + p["open"].get("minute", 0)
    )
    for days_ahead in range(7):
        future_dow = (check_dow + days_ahead) % 7
        for period in sorted_periods:
            open_info = period.get("open", {})
            if open_info.get("day") != future_dow:
                continue
            open_min = open_info["hour"] * 60 + open_info.get("minute", 0)
            if days_ahead == 0 and open_min <= check_minutes:
                continue
            label = "today" if days_ahead == 0 else _DAY_NAMES[future_dow]
            return (
                f"Closed — next opening: {label} at "
                f"{open_info['hour']:02d}:{open_info.get('minute', 0):02d}."
            )

    return "Closed — no upcoming opening times found."


@tool
def find_nearby_places(
    latitude: float,
    longitude: float,
    radius_meters: float = 500,
    place_type: str = "",
) -> str:
    """Find places near a given latitude/longitude coordinate.

    Args:
        latitude: Latitude of the center point.
        longitude: Longitude of the center point.
        radius_meters: Search radius in meters (default 500, max 50000).
        place_type: Optional place type filter (e.g. "restaurant", "cafe",
                    "bar", "lodging"). Leave empty to return all types.
    """
    field_mask = (
        "places.id,places.displayName,places.formattedAddress,"
        "places.rating,places.userRatingCount"
    )
    payload: dict[str, Any] = {
        "locationRestriction": {
            "circle": {
                "center": {"latitude": latitude, "longitude": longitude},
                "radius": min(max(1, radius_meters), 50000),
            }
        },
        "maxResultCount": 10,
    }
    if place_type:
        payload["includedTypes"] = [place_type]

    resp = requests.post(
        f"{PLACES_API_BASE}:searchNearby",
        headers=_headers(field_mask),
        json=payload,
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()

    places = data.get("places", [])
    if not places:
        return "No nearby places found."

    return "\n".join(_format_place_line(p) for p in places)
