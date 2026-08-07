"""
Manual test harness for the sub-agent nodes. Edit the `state` dict below
and rerun to try different trips.

Usage:
    python demo.py
"""

from agents.flight_agent import flight_agent_node
from agents.hotel_agent import hotel_agent_node
from agents.spots_weather_agent import spots_weather_agent_node
from agents.state import TripState

# Edit these to try a different trip. origin_city/destination_city can be
# any real city -- flight/hotel search are both live now, no fixed list.
# destination_country must be a real country name present in the
# destinations dataset (22 countries total -- try France, Japan, Italy,
# Australia, etc.) since that dataset is still mock data.
state: TripState = {
    "destination_city": "Paris",
    "destination_country": "France",
    "origin_city": "New York",
    "origin_country": "USA",
    "travel_month": "April",
    "duration_days": 6,
    "max_nightly_hotel_price": 150,
    "seat_class": "Economy",
}


def main() -> None:
    print(f"Trip: {state.get('destination_city')}, {state.get('destination_country')}")
    print(f"Route: {state.get('origin_city')} -> {state.get('destination_city')} ({state.get('seat_class')})")
    print(f"Month: {state.get('travel_month')} | Max hotel/night: ${state.get('max_nightly_hotel_price')}")
    print("=" * 70)

    print("\nHOTEL AGENT")
    print("-" * 70)
    hotel = hotel_agent_node(state)
    print(f"({len(hotel['hotel_results'])} candidates found)")
    print(hotel["hotel_recommendation"])

    print("\nFLIGHT AGENT")
    print("-" * 70)
    flight = flight_agent_node(state)
    print(f"({len(flight['flight_results'])} candidates found)")
    print(flight["flight_recommendation"])

    print("\nSPOTS & WEATHER AGENT")
    print("-" * 70)
    spots = spots_weather_agent_node(state)
    print(f"({len(spots['spot_results'])} candidates found)")
    print(spots["spot_recommendation"])


if __name__ == "__main__":
    main()
