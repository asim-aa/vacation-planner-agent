"""
Flight Agent tool -- v3: live flight search via fast-flights (scrapes
Google Flights), replacing the earlier RapidAPI/Air Scraper backend,
which required an API key and was capped at 20 requests/month on its
free tier. fast-flights needs no key and has no formal quota.

Airport resolution is fully offline via the `airportsdata` package (a
local IATA database) -- unlike the RapidAPI version, there is no live
"resolve city to airport" call and nothing to cache or ration.
"""

import datetime
import math
import time

import airportsdata

import tools._fast_flights_patch  # noqa: F401 -- applies a parser bugfix as an import side effect
from fast_flights import FlightQuery, Passengers, create_query, get_flights
from tools.cache import ttl_cache

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


def resolve_city_to_iata_candidates(
    city_name: str, country_name: str | None = None, max_candidates: int = 3
) -> list[str]:
    """Resolve a city name to a ranked list of candidate airport IATA
    codes, fully offline (no network call, no quota). When multiple
    airports share a city name, `country_name` narrows the match, and
    "International"-named airports are ranked above smaller ones.

    Some metro areas (e.g. Jakarta: CGK and HLP) have more than one
    "International"-named airport, so that heuristic alone can't always
    pick the true primary hub -- callers that search flights should try
    candidates in order and fall back to the next one on a zero-result
    search rather than trusting candidate[0] blindly. Returns [] if no
    match.
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
        return []

    intl = [c for c in candidates if "international" in _AIRPORTS[c]["name"].lower()]
    rest = [c for c in candidates if c not in intl]
    return (intl + rest)[:max_candidates]


def resolve_city_to_iata(city_name: str, country_name: str | None = None) -> str | None:
    """Resolve a city name to its single best-guess airport IATA code.
    Thin wrapper over resolve_city_to_iata_candidates() for callers that
    don't need fallback behavior. Returns None if no match.
    """
    candidates = resolve_city_to_iata_candidates(city_name, country_name, max_candidates=1)
    return candidates[0] if candidates else None


def _format_datetime(dt) -> str:
    year, month, day = dt.date
    # Some scraped entries (seen on overnight/red-eye legs) carry a None
    # inside the time list rather than a short list -- coerce defensively
    # rather than let a single malformed record crash the whole search.
    time_parts = [t if t is not None else 0 for t in dt.time] + [0, 0]
    hour, minute = time_parts[0], time_parts[1]
    return f"{year:04d}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}"


@ttl_cache()
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


# Curated global hub airports, used only as a last resort when Google
# Flights' own itinerary engine can't build any route at all (verified
# live: e.g. Boise -> Jakarta returns zero results even for round-trip,
# while Boise -> Tokyo works fine -- Google just won't auto-extend a
# connection that far from a small regional origin). airportsdata has no
# traffic/size field to derive this list from, so it's hand-picked rather
# than data-driven; it only needs to be "a well-connected airport", not
# "the objectively correct one".
MAJOR_HUBS = [
    "JFK", "LAX", "ORD", "ATL", "DFW", "SFO", "SEA", "MIA",
    "LHR", "CDG", "FRA", "AMS", "MAD", "IST",
    "DXB", "DOH", "AUH",
    "NRT", "HND", "ICN", "HKG", "SIN", "PEK", "PVG", "BKK",
    "SYD", "YYZ", "GRU",
]

MAX_HUB_ATTEMPTS = 2


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _nearest_hubs(from_code: str, exclude: set[str], limit: int) -> list[str]:
    origin = _AIRPORTS.get(from_code)
    if not origin:
        return []
    candidates = [h for h in MAJOR_HUBS if h in _AIRPORTS and h not in exclude]
    candidates.sort(
        key=lambda h: _haversine_km(origin["lat"], origin["lon"], _AIRPORTS[h]["lat"], _AIRPORTS[h]["lon"])
    )
    return candidates[:limit]


def _next_day(iso_date: str) -> str:
    return (datetime.date.fromisoformat(iso_date) + datetime.timedelta(days=1)).isoformat()


def search_flights_via_hub(
    origin: str,
    destination: str,
    departure_date: str,
    seat_class: str | None = None,
    limit: int = 10,
) -> list[dict]:
    """Last-resort fallback for when search_flights(origin, destination, ...)
    finds nothing at all -- not a scrape failure, but Google's own engine
    failing to construct any itinerary (direct or connecting) for the
    pair. Self-assembles a connection through the nearest curated major
    hub to `origin`: search origin->hub, then hub->destination on the
    hub-arrival date (or the day after, for a late arrival), and combine
    the two cheapest legs into one synthetic itinerary.

    This is NOT a single bookable ticket -- it's two separate tickets the
    traveler would book themselves, with real misconnection risk if the
    first leg runs late. Combined results carry a "SelfConnectedVia" key
    so callers can (and should) surface that caveat. Returns [] if no hub
    yields a working two-leg combination.
    """
    for hub in _nearest_hubs(origin, exclude={origin, destination}, limit=MAX_HUB_ATTEMPTS):
        leg1 = search_flights(origin, hub, departure_date, seat_class=seat_class, limit=5)
        if not leg1:
            continue
        leg1_best = leg1[0]

        arrival_date, arrival_time = leg1_best["Arrival_Time"].split(" ")
        connect_date = arrival_date if int(arrival_time.split(":")[0]) < 20 else _next_day(arrival_date)

        leg2 = search_flights(hub, destination, connect_date, seat_class=seat_class, limit=5)
        if not leg2 and connect_date == arrival_date:
            leg2 = search_flights(hub, destination, _next_day(arrival_date), seat_class=seat_class, limit=5)
        if not leg2:
            continue
        leg2_best = leg2[0]

        return [{
            "Airline": f"{leg1_best['Airline']} + {leg2_best['Airline']} (self-connect via {hub})",
            "Departure_Airport": origin,
            "Arrival_Airport": destination,
            "Seat_Class": seat_class or "Economy",
            "Price_USD": round(leg1_best["Price_USD"] + leg2_best["Price_USD"], 2),
            "Departure_Time": leg1_best["Departure_Time"],
            "Arrival_Time": leg2_best["Arrival_Time"],
            "Stops": leg1_best["Stops"] + leg2_best["Stops"] + 1,
            "SelfConnectedVia": hub,
        }][:limit]

    return []


def select_flight(results: list[dict], optimize_for: str = "cheapest", max_price: float | None = None) -> dict:
    """Pick one flight from already-fetched `results` -- no new search.

    "cheapest" (default): results[0] (results are already price-sorted).
    "comfort": fewest stops among options at or under `max_price` (ties
    broken toward the cheaper option); falls back to the cheapest overall
    if nothing fits under `max_price`, so this never raises or picks
    something the trip can't afford.
    """
    if optimize_for == "comfort":
        affordable = [r for r in results if max_price is None or r["Price_USD"] <= max_price]
        if affordable:
            return min(affordable, key=lambda r: (r["Stops"], r["Price_USD"]))
    return results[0]


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
