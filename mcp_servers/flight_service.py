from typing import Any, List, Optional
import requests
from mcp.server.fastmcp import FastMCP
import os

mcp = FastMCP("Flight Service", host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))

FLIGHT_API_BASE = "https://standing-fish-574.convex.site/flights"


def _fetch_json(url: str, params: Optional[dict] = None) -> Any:
    try:
        response = requests.get(url, params=params)
        return response.json()
    except Exception as e:
        print(f"Error fetching data from {url}: {e}")
        return None


@mcp.tool()
def get_flights() -> List[dict]:
    """
    Get a list of all available flights.
    Use this when the user asks to show/list all flights.
    """
    data = _fetch_json(FLIGHT_API_BASE)
    if isinstance(data, dict):
        return data.get("flights", [])
    return []


@mcp.tool()
def search_flights(
    origin: str,
    destination: str,
    date: Optional[str] = None,
) -> List[dict]:
    """
    Search for flights by origin, destination, and optional travel date.

    Args:
        origin: Flight origin city or airport code. Example: CMB, Bangkok.
        destination: Flight destination city or airport code. Example: BKK, Singapore.
        date: Optional flight date in YYYY-MM-DD format.
    """
    if origin and len(origin) == 3 and origin.isalpha():
        normalized_origin = origin.upper()
    else:
        normalized_origin = origin

    if destination and len(destination) == 3 and destination.isalpha():
        normalized_destination = destination.upper()
    else:
        normalized_destination = destination

    params = {
        "origin": normalized_origin,
        "destination": normalized_destination,
    }
    if date:
        params["date"] = date

    data = _fetch_json(f"{FLIGHT_API_BASE}/search", params=params)
    if isinstance(data, dict):
        return data.get("flights", [])
    return []


@mcp.tool()
def book_flight(flight_id: str, passenger_name: str, passenger_email: str) -> dict:
    """Book a flight ticket.

    Args:
        flight_id: ID of the flight to book
        passenger_name: Full name of the passenger
        passenger_email: Email of the passenger
    """
    payload = {
        "flightId": flight_id,
        "passengerName": passenger_name,
        "passengerEmail": passenger_email,
    }
    response = requests.post(f"{FLIGHT_API_BASE}/book", json=payload)
    return response.json()


if __name__ == "__main__":
    mcp.run(transport="streamable-http")