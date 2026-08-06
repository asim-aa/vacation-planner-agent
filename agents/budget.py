"""
Merge node: runs after Flight and Spots/Weather (parallel branch) complete,
before the Hotel Agent. Turns the remaining budget into a per-night ceiling
so the Hotel Agent can actually filter by price toward staying in budget,
rather than picking a hotel first and hoping the rest fits.
"""

from agents.state import TripState

MIN_NIGHTLY_HOTEL_PRICE = 30.0


def compute_hotel_budget_node(state: TripState) -> dict:
    duration_days = state.get("duration_days", 5)
    flight_cost = state.get("flight_cost_estimate", 0.0)
    activities_cost = state.get("activities_cost_estimate", 0.0)

    remaining = state["budget_total"] - flight_cost - activities_cost
    max_nightly = remaining / duration_days if duration_days else remaining

    # Never hand the hotel tool a ceiling so low it can't return anything
    # useful -- the itemized budget breakdown will surface an over-budget
    # trip explicitly rather than silently returning zero hotel options.
    max_nightly = max(max_nightly, MIN_NIGHTLY_HOTEL_PRICE)

    return {"max_nightly_hotel_price": round(max_nightly, 2)}
