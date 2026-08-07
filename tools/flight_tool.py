"""
Flight Agent tool -- v2: live flight search via the Air Scraper API
(RapidAPI, wrapping Skyscanner-style data), replacing the v1 mock dataset
that only covered 8 US airports. Any real airport code (or city name) now
works.

Air Scraper's search needs a skyId + entityId per airport, not just the
IATA code -- resolved via a separate lookup endpoint. Airport IDs never
change, so the 8 airports this project previously hardcoded support for
are resolved once (see scripts/resolve_airport_ids.py) and cached here,
meaning routine searches on those routes cost 0 extra resolve requests.
Any other airport/city is resolved live on demand -- 1 request.

The free RapidAPI tier for this API is capped at 20 requests/month.
search_flights() makes exactly ONE search request per call regardless of
how many results/filters are applied, and get_baseline_price() takes
already-fetched results rather than searching again -- keep call sites
structured that way (resolve once, search once, derive everything else
from that one response) or the quota disappears fast.
"""

import os

import requests
from dotenv import load_dotenv

load_dotenv()

RAPIDAPI_HOST = "sky-scrapper.p.rapidapi.com"
BASE_URL = f"https://{RAPIDAPI_HOST}/api"

# Resolved once via scripts/resolve_airport_ids.py. Airport IDs are stable,
# so this cache never needs refreshing.
KNOWN_AIRPORTS = {
    "JFK": {"skyId": "JFK", "entityId": "95565058"},
    "ORD": {"skyId": "ORD", "entityId": "95673392"},
    "SEA": {"skyId": "SEA", "entityId": "95673694"},
    "LAX": {"skyId": "LAX", "entityId": "95673368"},
    "SFO": {"skyId": "SFO", "entityId": "95673577"},
    "ATL": {"skyId": "ATL", "entityId": "95673800"},
    "DFW": {"skyId": "DFW", "entityId": "95673499"},
    "DEN": {"skyId": "DEN", "entityId": "95673705"},
}

SEAT_CLASS_MAP = {
    "Economy": "economy",
    "Premium Economy": "premium_economy",
    "Business": "business",
    "First": "first",
}


def _headers() -> dict:
    return {
        "x-rapidapi-host": RAPIDAPI_HOST,
        "x-rapidapi-key": os.environ["RAPIDAPI_KEY"],
    }


def resolve_airport(code: str) -> dict | None:
    """Resolve an exact airport code to {skyId, entityId}. Uses the local
    cache for the 8 known airports (0 requests); otherwise calls the live
    resolver (1 request). Returns None if the code doesn't match a real
    airport.
    """
    code = code.strip().upper()
    if code in KNOWN_AIRPORTS:
        return KNOWN_AIRPORTS[code]

    try:
        resp = requests.get(
            f"{BASE_URL}/v1/flights/searchAirport",
            params={"query": code, "locale": "en-US"},
            headers=_headers(),
            timeout=20,
        )
        resp.raise_for_status()
    except requests.exceptions.RequestException:
        return None

    for item in resp.json().get("data", []):
        params = item.get("navigation", {}).get("relevantFlightParams", {})
        if params.get("skyId") == code and item["navigation"]["entityType"] == "AIRPORT":
            return {"skyId": params["skyId"], "entityId": params["entityId"]}
    return None


def resolve_city_to_airport(city_name: str) -> dict | None:
    """Resolve a free-text city name (e.g. "Paris") to its primary airport's
    {skyId, entityId, displayCode}. Unlike resolve_airport(), this doesn't
    require an exact IATA code -- it takes the first AIRPORT-type match,
    which is what lets any real destination work, not just the 8 airports
    this project originally hardcoded. Costs 1 live API request; never
    cached, since arbitrary destinations vary per trip.
    """
    try:
        resp = requests.get(
            f"{BASE_URL}/v1/flights/searchAirport",
            params={"query": city_name.strip(), "locale": "en-US"},
            headers=_headers(),
            timeout=20,
        )
        resp.raise_for_status()
    except requests.exceptions.RequestException:
        return None

    for item in resp.json().get("data", []):
        nav = item.get("navigation", {})
        if nav.get("entityType") != "AIRPORT":
            continue
        params = nav.get("relevantFlightParams", {})
        return {
            "skyId": params["skyId"],
            "entityId": params["entityId"],
            "displayCode": params["skyId"],
        }
    return None


def search_flights_by_ids(
    origin_ids: dict,
    destination_ids: dict,
    departure_date: str,
    seat_class: str | None = None,
    max_price: float | None = None,
    limit: int = 10,
) -> list[dict]:
    """Core search: one live API call given already-resolved
    {skyId, entityId} dicts for both airports. Use this when the caller has
    already resolved origin/destination (e.g. once per agent run) to avoid
    re-resolving on every call -- see search_flights() for the
    resolve-then-search convenience wrapper.

    Returns cheapest-first; empty list on no results or a non-200 response.
    """
    cabin_class = SEAT_CLASS_MAP.get(seat_class, "economy") if seat_class else "economy"

    resp = requests.get(
        f"{BASE_URL}/v2/flights/searchFlights",
        params={
            "originSkyId": origin_ids["skyId"],
            "destinationSkyId": destination_ids["skyId"],
            "originEntityId": origin_ids["entityId"],
            "destinationEntityId": destination_ids["entityId"],
            "date": departure_date,
            "adults": 1,
            "cabinClass": cabin_class,
            "sortBy": "price",
            "currency": "USD",
            "market": "en-US",
            "countryCode": "US",
        },
        headers=_headers(),
        timeout=25,
    )
    if resp.status_code != 200:
        return []

    itineraries = (resp.json().get("data") or {}).get("itineraries") or []

    results = []
    for it in itineraries:
        legs = it.get("legs") or []
        if not legs:
            continue
        leg = legs[0]
        marketing_carriers = leg.get("carriers", {}).get("marketing") or []
        airline = marketing_carriers[0]["name"] if marketing_carriers else "Unknown"
        results.append({
            "Airline": airline,
            "Departure_Airport": leg["origin"]["displayCode"],
            "Arrival_Airport": leg["destination"]["displayCode"],
            "Seat_Class": seat_class or "Economy",
            "Price_USD": round(it["price"]["raw"], 2),
            "Departure_Time": leg["departure"],
            "Arrival_Time": leg["arrival"],
            "Stops": leg["stopCount"],
        })

    if max_price is not None:
        results = [r for r in results if r["Price_USD"] <= max_price]

    results.sort(key=lambda r: r["Price_USD"])
    return results[:limit]


def search_flights(
    origin: str,
    destination: str,
    departure_date: str,
    seat_class: str | None = None,
    max_price: float | None = None,
    limit: int = 10,
) -> list[dict]:
    """Convenience wrapper: resolves `origin` and `destination` (airport
    codes or city names) and searches in one call. Costs up to 2 resolve
    requests (0 for known airports) + 1 search request. Prefer
    search_flights_by_ids() when you already have resolved IDs, to avoid
    paying the resolve cost twice across a single agent run.

    Returns an empty list if either side can't be resolved or no flights
    are found.
    """
    origin_ids = resolve_airport(origin)
    destination_ids = resolve_airport(destination) or resolve_city_to_airport(destination)
    if not origin_ids or not destination_ids:
        return []
    return search_flights_by_ids(
        origin_ids, destination_ids, departure_date, seat_class, max_price, limit
    )


def get_baseline_price(results: list[dict]) -> float | None:
    """Average price across already-fetched flight results, for use as a
    baseline cost in budget math. Takes results directly -- it does NOT
    search again -- so call search_flights()/search_flights_by_ids() once
    and pass its output here. Returns None for an empty list.
    """
    if not results:
        return None
    return round(sum(r["Price_USD"] for r in results) / len(results), 2)


if __name__ == "__main__":
    origin_ids = resolve_airport("JFK")
    destination_ids = resolve_airport("ATL")
    flights = search_flights_by_ids(origin_ids, destination_ids, "2026-09-15", limit=5)
    print("Baseline economy JFK->ATL:", get_baseline_price(flights))
    for flight in flights:
        print(flight)
