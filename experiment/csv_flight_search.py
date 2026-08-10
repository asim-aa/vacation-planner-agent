"""
Side experiment: swap the live fast-flights scraper for a static CSV.

Mirrors the same pattern as agents/parse_request.py -- the model's ONLY
job is turning free text into a small structured JSON object (origin
airport, destination airport, budget). It never touches the CSV and
never decides what's "possible" -- that's a deterministic pandas filter
in code, same "don't trust the LLM with facts" split used everywhere
else in the real project.

Flow (matches the sketch: user prompt -> orchestrator -> model, step 1/2):
    1. user_request (free text) -> parse_flight_request() -> model -> JSON
    2. JSON -> search_flights_in_csv() -> deterministic pandas filter
    3. If nothing fits the budget: report how far off the cheapest
       still-real (non-cancelled) option is, not just "not found".
"""

import json
import re
from pathlib import Path

import pandas as pd

from agents.llm_client import get_llm

DATA_PATH = Path(__file__).parent / "data" / "flights.csv"

# The CSV only has these 10 airports -- giving the model this exact list
# (same idea as parse_request.py's SUPPORTED_COUNTRIES) keeps it from
# inventing a code that isn't actually in the data.
AIRPORT_NAMES = {
    "DFW": "Dallas/Fort Worth",
    "LAX": "Los Angeles",
    "PHX": "Phoenix",
    "SFO": "San Francisco",
    "MCO": "Orlando",
    "DEN": "Denver",
    "MIA": "Miami",
    "JFK": "New York (JFK)",
    "ORD": "Chicago (O'Hare)",
    "BOS": "Boston",
}

PROMPT_TEMPLATE = """Extract flight search parameters from the user's request below.

Respond with ONLY a JSON object (no markdown fences, no commentary) with these
exact keys:
- "origin_airport": the EXACT 3-letter IATA code (from the list below) for
  where the user is flying FROM.
- "destination_airport": the EXACT 3-letter IATA code (from the list below)
  for where the user wants to fly TO.
- "max_budget": number, the maximum total price in USD they're willing to pay.

Only these airports exist in the data -- pick the closest match, do not invent a code:
{airport_list}

User request: "{user_request}"

JSON:"""


def _extract_json(text: str) -> dict:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError(f"No JSON object found in LLM response: {text!r}")
    return json.loads(match.group(0))


def parse_flight_request(user_request: str, llm=None) -> dict:
    """Model step: free text -> {origin_airport, destination_airport, max_budget}.
    `llm` is injectable so this can be tested without hitting the real endpoint.
    """
    airport_list = "\n".join(f"- {code}: {name}" for code, name in AIRPORT_NAMES.items())
    prompt = PROMPT_TEMPLATE.format(airport_list=airport_list, user_request=user_request)

    llm = llm or get_llm()
    raw = llm.invoke(prompt).content
    parsed = _extract_json(raw)

    origin = str(parsed["origin_airport"]).strip().upper()
    destination = str(parsed["destination_airport"]).strip().upper()

    for code, label in (("origin_airport", origin), ("destination_airport", destination)):
        if label not in AIRPORT_NAMES:
            raise ValueError(f"Model returned an airport not in the dataset: {code}={label!r}")

    raw_budget = parsed.get("max_budget")

    return {
        "origin_airport": origin,
        "destination_airport": destination,
        # No made-up default here on purpose -- seen in practice: a shell
        # swallowing a "$100" argument left the model with no budget in
        # the text at all, and substituting a guessed number (even with a
        # warning) let a real "not possible" flip into a false "found".
        # None is a real, honest answer: the request didn't state one.
        "max_budget": float(raw_budget) if raw_budget is not None else None,
    }


def search_flights_in_csv(
    origin: str, destination: str, max_budget: float | None, df: pd.DataFrame | None = None
) -> dict:
    """Deterministic search -- no model involved. Returns one of three shapes:

    - route doesn't exist in the data at all: {"status": "no_route", ...}
    - route exists but nothing fits the budget: {"status": "over_budget",
      "shortfall": how much more you'd need, "cheapest": the closest option}
    - one or more real, non-cancelled flights fit: {"status": "found", "flights": [...]}

    `max_budget=None` means unfiltered -- return every real flight,
    cheapest first, with no affordability check (used when a caller just
    wants the real cheapest flight regardless of budget, e.g. as one leg
    of a combined flight+hotel calculation done elsewhere).
    """
    if df is None:
        df = pd.read_csv(DATA_PATH)

    route = df[(df["Departure_Airport"] == origin) & (df["Arrival_Airport"] == destination)]
    # A cancelled flight never happened -- it's not a real option to offer,
    # same reasoning as excluding scraper garbage in the real project.
    real = route[route["Flight_Status"] != "Cancelled"]

    if real.empty:
        return {
            "status": "no_route",
            "origin": origin,
            "destination": destination,
        }

    affordable = real if max_budget is None else real[real["Price_USD"] <= max_budget]
    affordable = affordable.sort_values("Price_USD")

    if affordable.empty:
        cheapest = real.sort_values("Price_USD").iloc[0]
        return {
            "status": "over_budget",
            "origin": origin,
            "destination": destination,
            "budget": max_budget,
            "cheapest_price": float(cheapest["Price_USD"]),
            "shortfall": round(float(cheapest["Price_USD"]) - max_budget, 2),
            "cheapest_flight": cheapest.to_dict(),
        }

    return {
        "status": "found",
        "origin": origin,
        "destination": destination,
        "budget": max_budget,
        "flights": affordable.to_dict("records"),
    }


def plan_flight(user_request: str, llm=None, df: pd.DataFrame | None = None) -> dict:
    """Full two-step flow: model extracts criteria, then a deterministic
    CSV search answers it. Returns the parsed criteria alongside the
    search result so a caller can show both.

    If no budget was stated, this does NOT search with a guessed number --
    it refuses outright, since a fabricated budget can silently turn a
    real "not possible" into a false "found" (verified: BOS->MIA at $100
    correctly says not possible, but at a made-up $500 wrongly says found).
    """
    criteria = parse_flight_request(user_request, llm=llm)

    if criteria["max_budget"] is None:
        return {
            "criteria": criteria,
            "result": {
                "status": "no_budget_stated",
                "origin": criteria["origin_airport"],
                "destination": criteria["destination_airport"],
            },
        }

    result = search_flights_in_csv(
        criteria["origin_airport"], criteria["destination_airport"], criteria["max_budget"], df=df
    )
    return {"criteria": criteria, "result": result}
