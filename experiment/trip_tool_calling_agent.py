"""
Combined flight + hotel tool-calling experiment.

The model is given TWO tools (search_flights, search_hotels) and decides
for itself which one(s) a request needs -- flight-only, hotel-only, or
both. That part is genuinely the model's call, and is verified live
rather than assumed (see run_trip_experiment.py).

What is NOT left to the model: any arithmetic that combines flight and
hotel prices. If both tools get called, this module computes
combined_price / remaining_budget / amount_over_budget /
amount_needed_for_next_tier itself, in plain Python, over every real
hotel tier, and hands the model a pre-verified result to describe. This
is the only way to honor the hard requirement: the model must never
claim a combination fits unless flight_price + hotel_price <= budget is
actually true -- which we can only guarantee if code checks it, not the
model.

Two-tool tool-calling is also why the hotel tool always returns EVERY
real tier (not just the one that fits under whatever budget the model
happened to pass it) -- the combined analysis needs all three prices to
find the best fitting tier and the cost of the next one up, regardless
of what a single-tool filter would have hidden.
"""

import json

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool

from agents.llm_client import get_llm
from experiment.csv_flight_search import AIRPORT_NAMES, search_flights_in_csv
from experiment.csv_hotel_search import search_hotels_in_csv

_AIRPORT_LIST_TEXT = ", ".join(f"{code} ({name})" for code, name in AIRPORT_NAMES.items())

SYSTEM_PROMPT = f"""You are a trip-planning assistant with two tools backed by
real data: search_flights and search_hotels. You cannot answer from your own
knowledge -- you must call the tool(s) that match what the user actually asked
for.

The dataset only covers these airports/cities: {_AIRPORT_LIST_TEXT}.

Decide which tool(s) to call based on the request:
- Flight only -> call ONLY search_flights.
- Hotel only -> call ONLY search_hotels.
- Flight AND hotel together -> call BOTH.
Never call a tool the request didn't ask for.

Budget handling:
- If the user gives ONE budget for a combined flight+hotel request, that is
  the TOTAL combined budget -- pass it as max_budget to BOTH search_flights
  and search_hotels (you are not choosing how to split it; the combined math
  is handled separately after both tools return).
- If the user did not state a budget at all, do not invent one -- omit
  max_budget from the tool call(s) entirely.

After tools return, you may also see a message starting with "VERIFIED budget
analysis" -- that is pre-computed, exact, and authoritative for any combined
flight+hotel affordability question. Use ONLY those numbers for combined math;
do not recompute or estimate combined totals yourself. For single-tool
(flight-only or hotel-only) requests, use the numbers the tool itself
returned.

Never claim a flight+hotel combination fits the budget unless the verified
analysis says so. Never invent a flight, hotel, or price that wasn't in a
tool's real result."""


@tool
def search_flights(origin_airport: str, destination_airport: str, max_budget: float | None = None) -> dict:
    """Search real flight data for non-cancelled flights between two airports.

    Args:
        origin_airport: 3-letter IATA code the user is flying FROM.
        destination_airport: 3-letter IATA code the user wants to fly TO.
        max_budget: maximum price in USD for this flight. Omit if the user
            didn't state a budget, or if this is part of a combined
            flight+hotel request (pass the total there per system instructions).
    """
    origin = origin_airport.strip().upper()
    destination = destination_airport.strip().upper()
    return search_flights_in_csv(origin, destination, float(max_budget) if max_budget is not None else None)


@tool
def search_hotels(city: str, max_budget: float | None = None) -> dict:
    """Search real hotel data (cheap/mid/expensive tiers) for a city.

    Args:
        city: 3-letter IATA code for the city.
        max_budget: maximum price in USD. Omit if the user didn't state a
            budget. For a combined flight+hotel request, pass the TOTAL
            combined budget here (not a hotel-only sub-budget).
    """
    return search_hotels_in_csv(city.strip().upper(), max_budget=max_budget)


def _extract_flight_price(flight_result: dict) -> float | None:
    """Real cheapest flight price regardless of the flight tool's own
    budget-filter outcome -- both "found" and "over_budget" carry a real
    price; only "no_route" has none."""
    if flight_result["status"] == "found":
        return flight_result["flights"][0]["Price_USD"]
    if flight_result["status"] == "over_budget":
        return flight_result["cheapest_price"]
    return None


def _compute_combined_analysis(flight_result: dict, hotel_result: dict) -> dict | None:
    """The deterministic core: real flight price x every real hotel tier,
    literal formulas from the spec, no model involved. Returns None if
    there's nothing to compute against (no route, or city not in data).
    """
    flight_price = _extract_flight_price(flight_result)
    hotel_tiers = hotel_result.get("all_tiers") or []
    budget = hotel_result.get("budget", flight_result.get("budget"))

    if flight_price is None:
        return {"status": "no_flight_available", "origin": flight_result.get("origin"), "destination": flight_result.get("destination")}
    if not hotel_tiers:
        return {"status": "no_hotels_available", "city": hotel_result.get("city")}
    if budget is None:
        return {"status": "no_budget_stated", "note": "The user did not state a budget for this combined request. Ask them for one."}

    per_tier = []
    for tier in hotel_tiers:
        combined_price = round(flight_price + tier["Hotel_Price"], 2)
        per_tier.append({
            "tier": tier["Hotel_Tier"],
            "hotel_name": tier["Hotel_Name"],
            "hotel_price": tier["Hotel_Price"],
            "flight_price": flight_price,
            "combined_price": combined_price,
            "fits": combined_price <= budget,
            "remaining_budget": round(budget - combined_price, 2),
            "amount_over_budget": round(max(0, combined_price - budget), 2),
        })

    affordable = [t for t in per_tier if t["fits"]]

    if affordable:
        # Tiers are strictly increasing in price, so affordability is
        # monotonic -- `affordable` is always a prefix of `per_tier`, and
        # the last affordable entry is always the best (highest) tier.
        best = affordable[-1]
        best_index = per_tier.index(best)
        next_tier = per_tier[best_index + 1] if best_index + 1 < len(per_tier) else None
        return {
            "status": "fits",
            "budget": budget,
            "flight_price": flight_price,
            "per_tier": per_tier,
            "selected_tier": best,
            "amount_needed_for_next_tier": max(0, round(next_tier["combined_price"] - budget, 2)) if next_tier else 0,
            "next_tier": next_tier,
        }

    cheapest_combo = per_tier[0]
    return {
        "status": "does_not_fit",
        "budget": budget,
        "flight_price": flight_price,
        "per_tier": per_tier,
        "cheapest_combined_price": cheapest_combo["combined_price"],
        "amount_over_budget": cheapest_combo["amount_over_budget"],
        "flight_alone_fits": flight_price <= budget,
        "cheapest_hotel_alone_fits": hotel_tiers[0]["Hotel_Price"] <= budget,
    }


def plan_trip_via_tool_calling(user_request: str, llm=None, max_rounds: int = 4) -> dict:
    """Full flow: model decides which tool(s) to call -> tools execute for
    real -> if both ran, code computes the verified combined analysis ->
    model writes the final answer using only verified numbers.

    This model does NOT reliably request both tools in a single response
    even when a combined request needs both (verified empirically: it
    would call search_flights, then stop, never requesting search_hotels).
    So this loops -- feed each round's tool result(s) back and let the
    model decide whether it still needs another tool -- rather than
    trusting one response to contain every call a combined request needs.
    """
    llm = llm or get_llm()
    bound_llm = llm.bind_tools([search_flights, search_hotels])

    messages = [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=user_request)]

    tool_calls_made = []
    flight_result = None
    hotel_result = None
    budget_analysis = None
    analysis_injected = False

    response: AIMessage = bound_llm.invoke(messages)
    messages.append(response)

    rounds = 0
    while response.tool_calls and rounds < max_rounds:
        rounds += 1
        for tool_call in response.tool_calls:
            tool_calls_made.append({"name": tool_call["name"], "args": tool_call["args"]})
            if tool_call["name"] == "search_flights":
                flight_result = search_flights.invoke(tool_call["args"])
                messages.append(ToolMessage(content=json.dumps(flight_result, default=str), tool_call_id=tool_call["id"]))
            elif tool_call["name"] == "search_hotels":
                hotel_result = search_hotels.invoke(tool_call["args"])
                messages.append(ToolMessage(content=json.dumps(hotel_result, default=str), tool_call_id=tool_call["id"]))

        if flight_result is not None and hotel_result is not None and not analysis_injected:
            budget_analysis = _compute_combined_analysis(flight_result, hotel_result)
            messages.append(SystemMessage(content=(
                "VERIFIED budget analysis (computed in code, exact -- use ONLY these "
                f"numbers for combined affordability):\n{json.dumps(budget_analysis, default=str)}"
            )))
            analysis_injected = True

        response = bound_llm.invoke(messages)
        messages.append(response)

    return {
        "tool_calls": tool_calls_made,
        "flight_result": flight_result,
        "hotel_result": hotel_result,
        "budget_analysis": budget_analysis,
        "final_answer": response.content,
    }
