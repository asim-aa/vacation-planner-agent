"""
Orchestrator entry node: turns the user's natural-language request into the
structured fields the sub-agent nodes need. This is the only place raw user
text touches the LLM -- everything downstream operates on small, structured
tool outputs.
"""

import json
import re

from agents.llm_client import get_llm
from agents.state import TripState

SUPPORTED_AIRPORTS = {
    "JFK": "New York",
    "ORD": "Chicago",
    "SEA": "Seattle",
    "LAX": "Los Angeles",
    "SFO": "San Francisco",
    "ATL": "Atlanta",
    "DFW": "Dallas",
    "DEN": "Denver",
}

# Exact country-name strings the destinations dataset uses -- e.g. "USA", not
# "United States". If the LLM writes anything else, the Spots/Weather Agent
# will just find zero rows (handled gracefully), so keep the model on this
# exact vocabulary whenever the trip's country is one of these.
SUPPORTED_COUNTRIES = [
    "Argentina", "Australia", "Brazil", "Canada", "China", "Egypt", "France",
    "Germany", "Greece", "India", "Italy", "Japan", "Kenya", "Mexico",
    "Morocco", "New Zealand", "Peru", "South Africa", "Spain", "Thailand",
    "USA", "Vietnam",
]

PROMPT_TEMPLATE = """Extract vacation-planning parameters from the user's request below.

Respond with ONLY a JSON object (no markdown fences, no commentary) with these
exact keys:
- "destination_city": string, the city name they want to visit
- "destination_country": string, the country that city is in. If the country
  matches one of {countries}, use that EXACT spelling (e.g. write "USA", not
  "United States" or "the US").
- "travel_month": string, full month name (e.g. "April"). If not stated, make
  a reasonable guess based on context, defaulting to the current season.
- "budget_total": number, total trip budget in USD. If not stated, use 2000.
- "duration_days": integer, trip length in days. If not stated, use 5.
- "origin_airport": one of {airports} -- pick the one matching where the user
  says they're flying from, defaulting to "JFK" if unstated or not one of these.
- "destination_airport": one of {airports}, ONLY if destination_city IS one of
  the cities listed for those airports ({airport_cities}); otherwise null.
- "seat_class": one of "Economy", "Premium Economy", "Business", "First" --
  default "Economy" if unstated.

User request: "{user_request}"

JSON:"""


def _extract_json(text: str) -> dict:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError(f"No JSON object found in LLM response: {text!r}")
    return json.loads(match.group(0))


def parse_request_node(state: TripState) -> dict:
    prompt = PROMPT_TEMPLATE.format(
        user_request=state["user_request"],
        airports=list(SUPPORTED_AIRPORTS.keys()),
        airport_cities=", ".join(SUPPORTED_AIRPORTS.values()),
        countries=", ".join(SUPPORTED_COUNTRIES),
    )
    llm = get_llm()
    raw = llm.invoke(prompt).content
    parsed = _extract_json(raw)

    destination_airport = parsed.get("destination_airport")
    if destination_airport not in SUPPORTED_AIRPORTS:
        destination_airport = None

    origin_airport = parsed.get("origin_airport")
    if origin_airport not in SUPPORTED_AIRPORTS:
        origin_airport = "JFK"

    return {
        "destination_city": parsed["destination_city"],
        "destination_country": parsed["destination_country"],
        "travel_month": parsed.get("travel_month", "April"),
        "budget_total": float(parsed.get("budget_total", 2000)),
        "duration_days": int(parsed.get("duration_days", 5)),
        "origin_airport": origin_airport,
        "destination_airport": destination_airport,
        "seat_class": parsed.get("seat_class", "Economy"),
    }
