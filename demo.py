"""
Manual test harness for the Phase 3 sub-agent nodes. Edit the `state` dict
below and rerun to try different trips.

Usage:
    python demo.py
"""

from agents.flight_agent import flight_agent_node
from agents.hotel_agent import hotel_agent_node
from agents.spots_weather_agent import spots_weather_agent_node

# Edit these to try a different trip.
# origin_airport / destination_airport must be one of:
#   JFK, ORD, SEA, LAX, SFO, ATL, DFW, DEN  (US domestic only, see Phase 2 notes)
# destination_country must be a real country name present in the destinations
# dataset (22 countries total -- try France, Japan, Italy, Australia, etc.)
state = {
    "destination_city": "Paris",
    "origin_airport": "JFK",
    "destination_airport": "ATL",
    "destination_country": "France",
    "travel_month": "April",
    "max_nightly_hotel_price": 150,
    "seat_class": "Economy",
}


def main() -> None:
    print(f"Trip: {state['destination_city']}, {state['destination_country']}")
    print(f"Route: {state['origin_airport']} -> {state['destination_airport']} ({state['seat_class']})")
    print(f"Month: {state['travel_month']} | Max hotel/night: ${state['max_nightly_hotel_price']}")
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
