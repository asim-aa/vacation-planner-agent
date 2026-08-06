"""
Hotel Agent tool: queries the local hotels table (tbo-hotels-dataset, loaded
into SQLite by data_check.py) by city and price. Never reads the raw CSV --
callers only ever get back a small, structured list of dicts, so this is
safe to feed directly into an LLM prompt.

Note: the raw dataset has no price field. EstimatedPriceUSD is a synthetic
nightly rate derived at load time (see data_check.py). Swapping in a real
price source later only requires changing how that column is populated --
this tool's interface does not need to change.
"""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "vacation.db"


def search_hotels(
    city: str,
    max_price: float | None = None,
    min_rating: str | None = None,
    limit: int = 10,
) -> list[dict]:
    """Return hotels in `city`, optionally capped at `max_price` per night
    and/or filtered to an exact `min_rating` tier (e.g. "ThreeStar"),
    cheapest first.

    Tries an exact case-insensitive match on `cityName` first. US entries in
    this dataset are stored as "City,   State" (e.g. "Atlanta,   Georgia"),
    so a plain city name falls back to a prefix match on "city,%" before
    giving up.

    Returns an empty list if no hotels match -- callers must handle that
    without crashing, per the orchestrator's zero-result requirement.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        base_query = """
            SELECT HotelName, cityName, HotelRating, EstimatedPriceUSD, HotelFacilities
            FROM hotels
            WHERE {city_clause}
        """
        filters = ""
        params: list = []

        if max_price is not None:
            filters += " AND EstimatedPriceUSD <= ?"
            params.append(max_price)

        if min_rating is not None:
            filters += " AND HotelRating = ?"
            params.append(min_rating)

        filters += " ORDER BY EstimatedPriceUSD ASC LIMIT ?"

        city_clean = city.strip()

        exact_query = base_query.format(city_clause="LOWER(cityName) = LOWER(?)") + filters
        rows = conn.execute(exact_query, [city_clean, *params, limit]).fetchall()

        if not rows:
            prefix_query = base_query.format(city_clause="LOWER(cityName) LIKE LOWER(?)") + filters
            rows = conn.execute(prefix_query, [f"{city_clean},%", *params, limit]).fetchall()

        return [dict(row) for row in rows]
    finally:
        conn.close()


if __name__ == "__main__":
    for hotel in search_hotels("Paris", max_price=200):
        print(hotel["HotelName"], hotel["HotelRating"], hotel["EstimatedPriceUSD"])
