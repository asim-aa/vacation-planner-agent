"""
Spots/Places tool -- v2: real tourist attractions via OpenStreetMap, no
API key, no quota. Replaces the mock destinations dataset's fake
"Destination Name" values (e.g. "Serene Temple") with real, named places.

Two free public services, chained:
  1. Nominatim (geocoding): city name -> lat/lon
  2. Overpass API (OSM data query): real tourism=* POIs near that point

Note: OSM has no star ratings and rarely has real per-visit prices, so
"EstimatedCostUSD" here is a coarse heuristic (0 if the place is tagged
fee=no or has no fee tag, a flat estimate otherwise) -- stated plainly,
not hidden. Distance from the city center substitutes for "rating" as
the ranking signal (closest first).
"""

import math

import requests

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]
HEADERS = {
    "User-Agent": "vacation-planner-agent/1.0 (educational project)",
    "Accept": "application/json",
}

# tourism=* values that are genuine attractions/activities. Excludes
# accommodation-ish tourism values (hotel, hostel, guest_house, motel,
# apartment, camp_site) which OSM also tags under the same tourism key.
ATTRACTION_TYPES = [
    "attraction", "museum", "gallery", "viewpoint", "artwork",
    "zoo", "theme_park", "aquarium", "picnic_site",
]

PAID_FEE_ESTIMATE_USD = 15.0
FREE_FEE_ESTIMATE_USD = 0.0


def geocode_city(city: str, country: str | None = None) -> tuple[float, float] | None:
    """Resolve a city (optionally "City, Country") to (lat, lon) via
    Nominatim. Returns None if not found or the request fails."""
    query = f"{city}, {country}" if country else city
    try:
        resp = requests.get(
            NOMINATIM_URL,
            params={"q": query, "format": "json", "limit": 1},
            headers=HEADERS,
            timeout=15,
        )
        resp.raise_for_status()
        results = resp.json()
    except requests.exceptions.RequestException:
        return None

    if not results:
        return None
    return float(results[0]["lat"]), float(results[0]["lon"])


def _haversine_km(lat1, lon1, lat2, lon2) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _query_overpass(lat: float, lon: float, radius_m: int) -> list[dict] | None:
    tourism_filter = "|".join(ATTRACTION_TYPES)
    query = f"""
    [out:json][timeout:25];
    (
      node["tourism"~"{tourism_filter}"](around:{radius_m},{lat},{lon});
    );
    out body 40;
    """
    for url in OVERPASS_URLS:
        try:
            resp = requests.post(url, data={"data": query}, headers=HEADERS, timeout=45)
            if resp.status_code == 200:
                return resp.json().get("elements", [])
        except requests.exceptions.RequestException:
            continue
    return None


def search_places_by_coords(lat: float, lon: float, radius_km: float = 8.0, limit: int = 10) -> list[dict]:
    """Core search: real named tourist attractions near (lat, lon), closest
    first. Use this when the caller already has coordinates (e.g. it also
    needs them for a weather check) to avoid geocoding twice -- see
    search_places() for the geocode-then-search convenience wrapper.
    """
    elements = _query_overpass(lat, lon, int(radius_km * 1000))
    if not elements:
        return []

    seen_names = set()
    results = []
    for el in elements:
        tags = el.get("tags", {})
        name = tags.get("name")
        if not name or name in seen_names:
            continue
        seen_names.add(name)

        fee_tag = tags.get("fee")
        estimated_cost = FREE_FEE_ESTIMATE_USD if fee_tag in (None, "no") else PAID_FEE_ESTIMATE_USD

        el_lat, el_lon = el.get("lat"), el.get("lon")
        distance_km = round(_haversine_km(lat, lon, el_lat, el_lon), 2) if el_lat and el_lon else None

        results.append({
            "Destination Name": name,
            "Type": tags.get("tourism", "attraction").replace("_", " ").title(),
            "EstimatedCostUSD": estimated_cost,
            "DistanceFromCenterKm": distance_km,
        })

    results.sort(key=lambda r: (r["DistanceFromCenterKm"] is None, r["DistanceFromCenterKm"]))
    return results[:limit]


def search_places(
    city: str,
    country: str | None = None,
    radius_km: float = 8.0,
    limit: int = 10,
) -> list[dict]:
    """Convenience wrapper: geocodes `city` then searches. Returns an empty
    list if the city can't be geocoded, Overpass is unreachable, or there
    are no tagged attractions nearby -- callers must handle that without
    crashing.
    """
    center = geocode_city(city, country)
    if not center:
        return []
    return search_places_by_coords(center[0], center[1], radius_km, limit)


if __name__ == "__main__":
    for place in search_places("Paris", "France", limit=8):
        print(place)
    print("No-match test:", search_places("Nonexistentcityxyz123"))
