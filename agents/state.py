"""Shared state schema passed between LangGraph nodes."""

from typing import TypedDict


class TripState(TypedDict, total=False):
    # Inputs, parsed from the user's natural-language request (Phase 4)
    destination_city: str  # for the Hotel Agent (e.g. "Paris")
    origin_airport: str  # IATA code, e.g. "JFK"
    destination_airport: str  # IATA code, e.g. "CDG" -- must be one of the 8 covered airports
    destination_country: str  # for the Spots & Weather Agent (e.g. "France")
    travel_month: str  # e.g. "April"
    max_nightly_hotel_price: float
    seat_class: str

    # Outputs, filled in by each sub-agent node
    hotel_results: list[dict]
    hotel_recommendation: str
    flight_results: list[dict]
    flight_recommendation: str
    spot_results: list[dict]
    spot_recommendation: str
