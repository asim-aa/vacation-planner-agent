"""
Flight Agent tool -- v3: live flight search via fast-flights (scrapes
Google Flights), replacing the earlier RapidAPI/Air Scraper backend,
which required an API key and was capped at 20 requests/month on its
free tier. fast-flights needs no key and has no formal quota.

Airport resolution is fully offline via the `airportsdata` package (a
local IATA database) -- unlike the RapidAPI version, there is no live
"resolve city to airport" call and nothing to cache or ration.
"""

import time

import airportsdata
from fast_flights import FlightQuery, Passengers, create_query, get_flights

# Seen in practice (same class of issue as tools/hotel_tool.py): a live
# scrape can transiently return zero results even though the exact same
# query succeeds on an immediate retry.
MAX_ATTEMPTS = 2
RETRY_DELAY_SECONDS = 2

_AIRPORTS = airportsdata.load("IATA")

# Country name -> ISO 3166-1 alpha-2, for the countries this project's
# destinations dataset covers. Used to disambiguate identically-named
# cities in different countries (e.g. "Paris, France" vs "Paris, Texas")
# when resolving a city name to an airport.
COUNTRY_ISO2 = {
    "Argentina": "AR", "Australia": "AU", "Brazil": "BR", "Canada": "CA",
    "China": "CN", "Egypt": "EG", "France": "FR", "Germany": "DE",
    "Greece": "GR", "India": "IN", "Italy": "IT", "Japan": "JP",
    "Kenya": "KE", "Mexico": "MX", "Morocco": "MA", "New Zealand": "NZ",
    "Peru": "PE", "South Africa": "ZA", "Spain": "ES", "Thailand": "TH",
    "USA": "US", "Vietnam": "VN",
}

SEAT_CLASS_MAP = {
    "Economy": "economy",
    "Premium Economy": "premium-economy",
    "Business": "business",
    "First": "first",
}


def resolve_city_to_iata(city_name: str, country_name: str | None = None) -> str | None:
    """Resolve a city name to its primary airport's IATA code, fully
    offline (no network call, no quota). When multiple airports share a
    city name, `country_name` narrows the match, and an "International"
    airport is preferred over smaller ones. Returns None if no match.
    """
    target = city_name.strip().lower()
    candidates = [
        code for code, a in _AIRPORTS.items()
        if a["city"].strip().lower() == target
    ]

    if country_name:
        iso2 = COUNTRY_ISO2.get(country_name)
        if iso2:
            narrowed = [c for c in candidates if _AIRPORTS[c]["country"] == iso2]
            if narrowed:
                candidates = narrowed

    if not candidates:
        return None

    intl = [c for c in candidates if "international" in _AIRPORTS[c]["name"].lower()]
    return intl[0] if intl else candidates[0]


def _format_datetime(dt) -> str:
    year, month, day = dt.date
    # Some scraped entries (seen on overnight/red-eye legs) carry a None
    # inside the time list rather than a short list -- coerce defensively
    # rather than let a single malformed record crash the whole search.
    time_parts = [t if t is not None else 0 for t in dt.time] + [0, 0]
    hour, minute = time_parts[0], time_parts[1]
    return f"{year:04d}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}"


def search_flights(
    origin: str,
    destination: str,
    departure_date: str,
    seat_class: str | None = None,
    max_price: float | None = None,
    limit: int = 10,
) -> list[dict]:
    """Return live Google Flights results for `origin` -> `destination`
    (IATA codes) departing on `departure_date` (YYYY-MM-DD), optionally
    filtered by seat class and/or capped at `max_price`, cheapest first.

    Returns an empty list on no results or any scrape failure (after
    retrying once) -- callers must handle that without crashing.
    """
    cabin = SEAT_CLASS_MAP.get(seat_class, "economy") if seat_class else "economy"

    flights = None
    for attempt in range(MAX_ATTEMPTS):
        try:
            query = create_query(
                flights=[FlightQuery(date=departure_date, from_airport=origin, to_airport=destination)],
                seat=cabin,
                trip="one-way",
                passengers=Passengers(adults=1),
            )
            flights = get_flights(query)
            if flights:
                break
        except Exception:
            flights = None
        if attempt < MAX_ATTEMPTS - 1:
            time.sleep(RETRY_DELAY_SECONDS)

    if not flights:
        return []

    results = []
    for f in flights:
        legs = f.flights
        if not legs:
            continue
        try:
            first_leg, last_leg = legs[0], legs[-1]
            results.append({
                "Airline": f.airlines[0] if f.airlines else "Unknown",
                "Departure_Airport": first_leg.from_airport.code,
                "Arrival_Airport": last_leg.to_airport.code,
                "Seat_Class": seat_class or "Economy",
                "Price_USD": float(f.price),
                "Departure_Time": _format_datetime(first_leg.departure),
                "Arrival_Time": _format_datetime(last_leg.arrival),
                "Stops": len(legs) - 1,
            })
        except (TypeError, ValueError, AttributeError, IndexError):
            # One malformed record (seen: None inside a time list on some
            # overnight legs) shouldn't drop the whole search -- skip it.
            continue

    if max_price is not None:
        results = [r for r in results if r["Price_USD"] <= max_price]

    results.sort(key=lambda r: r["Price_USD"])
    return results[:limit]


def get_baseline_price(results: list[dict]) -> float | None:
    """Average price across already-fetched flight results, for use as a
    baseline cost in budget math. Takes results directly -- it does NOT
    search again. Returns None for an empty list.
    """
    if not results:
        return None
    return round(sum(r["Price_USD"] for r in results) / len(results), 2)


if __name__ == "__main__":
    flights = search_flights("JFK", "ATL", "2026-09-15", limit=5)
    print("Baseline economy JFK->ATL:", get_baseline_price(flights))
    for flight in flights:
        print(flight)
    print("City resolution test:", resolve_city_to_iata("Paris", "France"))
