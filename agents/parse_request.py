"""
Orchestrator entry node: turns the user's natural-language request into the
structured fields the sub-agent nodes need. This is the only place raw user
text touches the LLM -- everything downstream operates on small, structured
tool outputs.

The LLM only extracts real-world names (cities, country, month) -- it does
NOT guess IATA airport codes. tools/flight_tool.resolve_city_to_iata()
handles that offline, which is what lets both origin and destination be
any real city rather than a fixed list.
"""

import json
import re

from agents.llm_client import get_llm
from agents.state import TripState

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
- "origin_city": string, the real-world city they say they're flying from.
  Default to "New York" if unstated.
- "origin_country": string or null, the country that origin city is in, if
  stated or obvious (e.g. "USA" for New York); otherwise null.
- "travel_month": string, full month name (e.g. "April"). If not stated, make
  a reasonable guess based on context, defaulting to the current season.
- "budget_total": number, total trip budget in USD. If not stated, use 2000.
- "duration_days": integer, trip length in days. If not stated, use 5.
- "seat_class": one of "Economy", "Premium Economy", "Business", "First" --
  default "Economy" if unstated.

User request: "{user_request}"

JSON:"""


def _extract_json(text: str) -> dict:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError(f"No JSON object found in LLM response: {text!r}")
    return json.loads(match.group(0))


def parse_request_node(state: TripState, llm=None) -> dict:
    """`llm` is injectable so tests can pass a fake instead of hitting the
    real endpoint; defaults to the real client when not provided."""
    prompt = PROMPT_TEMPLATE.format(
        user_request=state["user_request"],
        countries=", ".join(SUPPORTED_COUNTRIES),
    )
    llm = llm or get_llm()
    raw = llm.invoke(prompt).content
    parsed = _extract_json(raw)

    return {
        "destination_city": parsed["destination_city"],
        "destination_country": parsed["destination_country"],
        "origin_city": parsed.get("origin_city") or "New York",
        "origin_country": parsed.get("origin_country"),
        "travel_month": parsed.get("travel_month", "April"),
        "budget_total": float(parsed.get("budget_total", 2000)),
        "duration_days": int(parsed.get("duration_days", 5)),
        "seat_class": parsed.get("seat_class", "Economy"),
    }
