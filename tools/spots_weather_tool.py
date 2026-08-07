"""
Spots & Weather Agent tool -- v2: real named tourist attractions via
OpenStreetMap (tools/places_tool.py), replacing the mock destinations
dataset's fake "Destination Name" values (e.g. "Serene Temple"). Real
season/climate fit is checked at the destination's actual coordinates
(tools/weather_tool.py), not a country-level proxy.

Note: OSM has no star ratings and rarely has real per-visit prices --
places are ranked by distance from the city center instead, and
EstimatedCostUSD is a coarse fee-tag-based heuristic (see
places_tool.py). This is real place data, not real pricing/rating data.
"""

from tools.places_tool import geocode_city, search_places_by_coords
from tools.weather_tool import get_climate_suitability_for_coords


def search_destinations(
    city: str,
    country: str | None = None,
    category: str | None = None,
    travel_month: str | None = None,
    limit: int = 10,
) -> list[dict]:
    """Return real tourist attractions in `city`, closest to the city
    center first, optionally filtered by `category` (e.g. "Museum").

    If `travel_month` is given, every result gets the same `season_match`
    bool and `climate` details, from one real historical-climate lookup
    at the city's actual coordinates. Returns an empty list if the city
    can't be geocoded or has no tagged attractions nearby.
    """
    center = geocode_city(city, country)
    if not center:
        return []
    lat, lon = center

    rows = search_places_by_coords(lat, lon, limit=limit * 3 if category else limit)

    if category is not None:
        rows = [r for r in rows if r["Type"].lower() == category.lower()][:limit]

    if travel_month is not None and rows:
        climate = get_climate_suitability_for_coords(lat, lon, travel_month)
        for row in rows:
            row["season_match"] = climate["suitable"] if climate else None
            row["climate"] = climate

    return rows


if __name__ == "__main__":
    for spot in search_destinations("Paris", "France", travel_month="April", limit=5):
        print(spot)
    print("No-match test:", search_destinations("Nonexistentcityxyz123"))
