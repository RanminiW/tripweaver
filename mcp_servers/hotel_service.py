from typing import Any, List, Optional
import requests
from mcp.server.fastmcp import FastMCP
import os

mcp = FastMCP("Hotel Service", host="0.0.0.0", port=int(os.environ.get("PORT", 8001)))

HOTEL_API_BASE = "https://standing-fish-574.convex.site/hotels"


def _fetch_json(url: str, params: Optional[dict] = None) -> Any:
    try:
        response = requests.get(url, params=params)
        return response.json()
    except Exception as e:
        print(f"Error fetching data from {url}: {e}")
        return None


@mcp.tool()
def get_hotels() -> List[dict]:
    """
    Get a list of all available hotels.
    Use this when the user asks to show/list all hotels.
    """
    data = _fetch_json(HOTEL_API_BASE)
    if isinstance(data, dict):
        return data.get("hotels", [])
    return []


@mcp.tool()
def search_hotel(
    city: str,
    checkIn: Optional[str] = None,
    checkOut: Optional[str] = None,
) -> List[dict]:
    """
    Search for hotels by city and optional check-in/check-out dates.

    Args:
        city: Hotel city name. Example: Bangkok, Colombo, Singapore.
        checkIn: Optional check-in date in YYYY-MM-DD format.
        checkOut: Optional check-out date in YYYY-MM-DD format.
    """
    params = {"city": city}
    if checkIn:
        params["checkIn"] = checkIn
    if checkOut:
        params["checkOut"] = checkOut

    data = _fetch_json(f"{HOTEL_API_BASE}/search", params=params)
    if isinstance(data, dict):
        return data.get("hotels", [])
    return []


@mcp.tool()
def book_hotel(
    hotel_id: str,
    guest_name: str,
    guest_email: str,
    check_in_date: str,
    check_out_date: str,
    room_type: str,
) -> dict:
    """Book a hotel room.

    Args:
        hotel_id: ID of the hotel to book
        guest_name: Full name of the guest
        guest_email: Email of the guest
        check_in_date: Check-in date (YYYY-MM-DD)
        check_out_date: Check-out date (YYYY-MM-DD)
        room_type: Type of room (single, double, suite)
    """
    payload = {
        "hotelId": hotel_id,
        "guestName": guest_name,
        "guestEmail": guest_email,
        "checkInDate": check_in_date,
        "checkOutDate": check_out_date,
        "roomType": room_type,
    }
    response = requests.post(f"{HOTEL_API_BASE}/book", json=payload)
    return response.json()


if __name__ == "__main__":
    mcp.run(transport="streamable-http")