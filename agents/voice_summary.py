"""
Builds a SHORT, ear-friendly spoken summary of a finished trip.

The LLM only ever sees a small block of facts pulled from the trip state
(not the Markdown itinerary, and no airport codes), so it has little to
get wrong. The result is still run through the same narrative guard the
other agents use; if the LLM fails, is unavailable, or names a city that
isn't part of this trip, we fall back to a plain templated summary built
from the same facts (safe, if less polished).

Limitation: the guard only catches invented *cities*. It cannot detect an
invented price or other detail -- that is handled by the prompt only.
"""

from agents.llm_client import get_llm
from agents.narrative_guard import mentions_unexpected_city
from agents.state import TripState
from tools.voice import DEFAULT_MAX_CHARS, clean_for_speech


def _facts(state: TripState) -> dict:
    flights = state.get("flight_results") or []
    hotels = state.get("hotel_results") or []
    spots = state.get("spot_results") or []
    flight = flights[0] if flights else None
    hotel = hotels[0] if hotels else None
    return {
        "destination": f"{state.get('destination_city', '')}, {state.get('destination_country', '')}".strip(", "),
        "origin": state.get("origin_city"),
        "month": state.get("travel_month"),
        "days": state.get("duration_days"),
        "budget": round(state.get("budget_total", 0.0)),
        "total": round(state.get("total_cost_estimate", 0.0)),
        "airline": flight["Airline"] if flight else None,
        "flight_price_each_way": round(flight["Price_USD"]) if flight else None,
        "flight_stops": flight["Stops"] if flight else None,
        "hotel": hotel["HotelName"] if hotel else None,
        "hotel_price_per_night": round(hotel["EstimatedPriceUSD"]) if hotel else None,
        "hotel_rating": hotel.get("GuestRating") if hotel else None,
        "top_activities": [s["Destination Name"] for s in spots[:3]],
    }


def _allowed_names(facts: dict) -> set:
    names = {facts["destination"], facts["origin"], facts["airline"], facts["hotel"], facts["month"]}
    names.update(facts["destination"].replace(",", " ").split())
    names.update(facts["top_activities"])
    return {n for n in names if n}


def template_summary(facts: dict) -> str:
    parts = [f"Here's your {facts['days']} day trip to {facts['destination']}"
             + (f" in {facts['month']}." if facts["month"] else ".")]
    if facts["airline"]:
        stops = facts["flight_stops"]
        stop_text = "nonstop" if stops == 0 else f"with {stops} stop{'s' if stops != 1 else ''}"
        parts.append(
            f"You'll fly {facts['airline']}, {stop_text}, for about {facts['flight_price_each_way']} dollars each way."
        )
    if facts["hotel"]:
        parts.append(f"You'll stay at {facts['hotel']} for about {facts['hotel_price_per_night']} dollars a night.")
    if facts["top_activities"]:
        parts.append("Top things to do: " + ", ".join(facts["top_activities"]) + ".")
    verdict = "inside" if facts["total"] <= facts["budget"] else "over"
    parts.append(
        f"Your estimated total is about {facts['total']} dollars, {verdict} your {facts['budget']} dollar budget."
    )
    return " ".join(parts)


def build_voice_summary(state: TripState, llm=None, max_chars: int = DEFAULT_MAX_CHARS) -> str:
    """Return a spoken-style summary of at most `max_chars` characters.
    `llm` is injectable for tests; defaults to the real client."""
    facts = _facts(state)
    prompt = (
        "Write a spoken trip summary of about 400 to 600 characters, to be read aloud by a "
        "text-to-speech voice. Rules: plain sentences only -- no markdown, bullets, tables, "
        "emoji, or airport codes. Say dates, prices and numbers the way a person would say them "
        "(for example 'about three hundred dollars'). Use ONLY the facts below; do not add any "
        "place name, price, or detail that is not listed.\n\nFacts (JSON):\n"
        f"{facts}"
    )
    try:
        llm = llm or get_llm()
        text = clean_for_speech(llm.invoke(prompt).content, max_chars)
    except Exception:
        text = ""

    if not text or mentions_unexpected_city(text, _allowed_names(facts)):
        text = template_summary(facts)
    return clean_for_speech(text, max_chars)
