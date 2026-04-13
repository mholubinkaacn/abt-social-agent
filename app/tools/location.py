import requests
from langchain_core.tools import tool


@tool
def get_current_location() -> str:
    """Get the approximate geographic location of the machine running this code,
    based on its public IP address. Returns city, region, country, and
    latitude/longitude coordinates.
    """
    resp = requests.get("https://ipapi.co/json/", timeout=10)
    resp.raise_for_status()
    data = resp.json()

    return (
        f"City: {data.get('city', 'N/A')}\n"
        f"Region: {data.get('region', 'N/A')}\n"
        f"Country: {data.get('country_name', 'N/A')}\n"
        f"Latitude: {data.get('latitude', 'N/A')}\n"
        f"Longitude: {data.get('longitude', 'N/A')}"
    )
