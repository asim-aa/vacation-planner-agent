"""Shared state schema passed between LangGraph nodes."""

from typing import TypedDict


class TripState(TypedDict, total=False):
    # Raw natural-language request, and the fields parsed out of it
    user_request: str
    destination_city: str  # for the Hotel Agent (e.g. "Paris")
    origin_airport: str  # IATA code, e.g. "JFK"
    destination_airport: str | None  # IATA code -- only set if it's one of the 8 covered airports
    destination_country: str  # for the Spots & Weather Agent (e.g. "France")
    travel_month: str  # e.g. "April"
    budget_total: float
    duration_days: int
    seat_class: str

    # Outputs, filled in by each sub-agent node
    hotel_results: list[dict]
    hotel_recommendation: str
    max_nightly_hotel_price: float
    flight_results: list[dict]
    flight_recommendation: str
    spot_results: list[dict]
    spot_recommendation: str

    # Budget math, filled in by compute_hotel_budget / compile_itinerary
    flight_cost_estimate: float
    activities_cost_estimate: float
    lodging_cost_estimate: float
    total_cost_estimate: float

    # Final output
    itinerary_markdown: str
