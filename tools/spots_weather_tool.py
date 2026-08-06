"""
Spots & Weather Agent tool: queries the local destinations table
(popular-tourist-destinations-and-their-features, loaded into SQLite by
data_check.py) for activity-type spots and checks travel-month climate fit.

Note: "Destination Name" values are generic/templated (e.g. "Serene Temple"
recurs across multiple countries) rather than real place names -- Country
is the only realistic, stable field to query by. There is no itemized
per-destination activity list in the raw data; the "Type" column (Beach,
Adventure, Nature, Historical, Religious, City) stands in as the activity
category, per row.
"""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "vacation.db"

MONTH_TO_SEASON = {
    "december": "Winter", "january": "Winter", "february": "Winter",
    "march": "Spring", "april": "Spring", "may": "Spring",
    "june": "Summer", "july": "Summer", "august": "Summer",
    "september": "Autumn", "october": "Autumn", "november": "Autumn",
}


def search_destinations(
    country: str,
    category: str | None = None,
    travel_month: str | None = None,
    limit: int = 10,
) -> list[dict]:
    """Return destination/activity rows for `country` (exact match,
    case-insensitive), optionally filtered by activity `category` (Type).

    If `travel_month` is given, each result includes a `season_match` bool
    comparing the destination's Best Season against the month's season
    (Northern Hemisphere mapping). Returns an empty list if no rows match.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        query = """
            SELECT "Destination Name", Country, Type, "Avg Cost (USD/day)",
                   "Best Season", "Avg Rating", "UNESCO Site"
            FROM destinations
            WHERE LOWER(Country) = LOWER(?)
        """
        params: list = [country.strip()]

        if category is not None:
            query += " AND Type = ?"
            params.append(category)

        query += " ORDER BY \"Avg Rating\" DESC LIMIT ?"
        params.append(limit)

        rows = [dict(row) for row in conn.execute(query, params).fetchall()]
    finally:
        conn.close()

    if travel_month is not None:
        target_season = MONTH_TO_SEASON.get(travel_month.strip().lower())
        for row in rows:
            row["season_match"] = (
                target_season is not None and row["Best Season"] == target_season
            )

    return rows


if __name__ == "__main__":
    for spot in search_destinations("Japan", travel_month="April", limit=5):
        print(spot)
    print("No-match test:", search_destinations("Nowhereland"))
